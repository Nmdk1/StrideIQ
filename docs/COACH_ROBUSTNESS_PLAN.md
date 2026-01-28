# AI Coach Robustness & Completeness Plan

**Status**: Draft  
**Created**: 2026-01-27  
**Priority**: Critical (Marquee Feature)  
**Target**: Production Beta Ready

---

## Executive Summary

The AI Coach is functional but **systemically brittle**. The core issue is not missing features—it's architectural: too many hardcoded shortcuts bypass the AI, message routing logic is too narrow, and the AI lacks access to critical data. This creates trust-breaking misfires where the Coach:

1. **Deflects** instead of answering direct questions
2. **Misclassifies** questions and routes to wrong handlers
3. **Ignores context** from earlier in the conversation
4. **Lacks data** needed to give evidence-based answers

This plan addresses the **systemic** issues, not symptoms.

---

## Current State Assessment

### What Works Well
- Propose → Confirm → Apply flow with transactional safety
- 18 bounded tools with structured evidence output
- Citation enforcement post-processing
- Thin history fallback with baseline intake
- Pain flag guardrails
- Thread persistence via OpenAI Assistants API

### Critical Failures

| Issue | Root Cause | Impact |
|-------|------------|--------|
| "Self-guided" deflection | Hardcoded shortcut at lines 1083-1096 triggered by "this week" keyword | Ignores athlete's question entirely |
| Timeline questions ignored | Benchmark detection requires BOTH benchmark AND timeline phrases | Many valid questions bypass detection |
| AI analyzes wrong thing | Context injection doesn't reinforce question intent | AI pattern-matches to "analyze recent run" |
| Repeated clarification asks | Thread context only checks 10 messages, doesn't remember earlier answers | Frustrating UX |
| Missing data in answers | Tools don't expose elevation, environmental, wellness data | AI can't use data that exists |

### Architecture Debt

| File | Lines | Issue |
|------|-------|-------|
| `ai_coach.py` | ~2,887 | Monolithic, hard to test |
| Deterministic shortcuts | Lines 1054-1248 | 15+ bypasses, complex conditionals |
| Context injection | Lines 1280-1321 | 4 injections in sequence, hard to reason about |
| Detection methods | Lines 1672-1771 | Simple keyword matching, miss variations |

---

## Root Cause Analysis

### Why the Coach Deflects

```
User: "Would it be reasonable to think I'll be at 3:08 shape in time?"
                            ↓
_is_prescription_request() → TRUE (contains "this week")
                            ↓
snap_stale check → TRUE (intent snapshot is stale)
                            ↓
HARDCODED RESPONSE: "To make this self-guided..."
                            ↓
User question NEVER reaches the AI
```

**Fix required**: Exclusion logic must detect judgment/timeline questions BEFORE prescription routing, not after.

### Why the AI Ignores Context

```
Context Injection Order:
1. Thin history injection (if applicable)
2. Ambiguity context injection (if comparison language)
3. Benchmark injection (if detected)
4. User message

Problem: 
- Injections are "user" role messages, not system
- Thread may have 20+ prior messages
- Injections get buried
- AI pattern-matches to most recent activity data
```

**Fix required**: Use `additional_instructions` on the run, not more user messages.

### Why Detection Misses Questions

```python
# Current: Requires BOTH conditions
has_benchmark = any(phrase in ml for phrase in benchmark_phrases)
has_timeline = any(phrase in ml for phrase in timeline_phrases)
return has_benchmark and has_timeline  # Too strict!

# User says: "I was in 3:08 shape, am I on track?"
# has_benchmark = True ("3:08 shape")
# has_timeline = False ("am I on track" not in list)
# Result: NOT DETECTED
```

**Fix required**: Expand phrase lists, use OR logic for some patterns, consider LLM-based classification.

---

## The Plan

### Phase 1: Critical Routing Fix (1-2 hours) ✅ COMPLETE

**Status**: Completed 2026-01-27  
**Commit**: `e1adb98` feat(coach): Phase 1 routing fix - judgment questions bypass shortcuts + return-context clarification gate

**Goal**: Stop hardcoded shortcuts from hijacking judgment questions.

#### 1.1 Reorder Detection Logic

Move judgment/timeline detection to the TOP of `chat()`, before any deterministic shortcuts.

```python
# FIRST: Check if this is a judgment/opinion question
if self._is_judgment_question(message):
    # Route directly to AI with reinforced context
    return self._handle_judgment_question(athlete_id, message)

# THEN: Deterministic shortcuts for simple lookups
if self._is_prescription_request(message):
    # ... existing logic
```

#### 1.2 Expand Detection Coverage

Current `_is_benchmark_timeline_question` is too narrow. Create broader `_is_judgment_question`:

```python
def _is_judgment_question(self, message: str) -> bool:
    """Detect opinion/judgment/timeline questions that need AI reasoning."""
    ml = (message or "").lower()
    
    # Opinion-seeking patterns (should go to AI, not shortcuts)
    opinion_patterns = (
        "would it be reasonable",
        "do you think",
        "is it realistic",
        "am i on track",
        "will i make it",
        "can i achieve",
        "should i be worried",
        "is it possible",
        "what do you think",
        "your opinion",
        "your assessment",
    )
    
    # Past benchmark references (need comparison to current)
    benchmark_patterns = (
        "was in.*shape",
        "used to run",
        "before (my )?injury",
        "at my (peak|best)",
        "my (pb|pr|personal best)",
        r"\d:\d{2} (marathon|half|10k|5k)",
    )
    
    # Goal/timeline references
    goal_patterns = (
        "by (march|april|may|june|july|august|september|october|november|december)",
        "by the (race|marathon|event)",
        "in time for",
        "before the",
        "in \d+ weeks",
    )
    
    has_opinion = any(p in ml for p in opinion_patterns)
    has_benchmark = any(re.search(p, ml) for p in benchmark_patterns)
    has_goal = any(re.search(p, ml) for p in goal_patterns)
    
    # Any ONE of these is enough to route to AI
    return has_opinion or (has_benchmark and has_goal)
```

#### 1.3 Remove Aggressive Hardcoded Shortcuts

The "self-guided" shortcut (lines 1083-1096) should ONLY trigger if the user explicitly asks for a prescription AND provides no constraints. NOT when they're asking a judgment question that happens to mention "this week".

```python
# OLD (too aggressive)
if req_days >= 7 and (snap_stale or ...):
    return {"response": "To make this self-guided..."}

# NEW (check intent first)
if self._is_judgment_question(message):
    pass  # Let AI handle it
elif self._is_explicit_prescription_request(message):
    if req_days >= 7 and (snap_stale or ...):
        return {"response": "To make this self-guided..."}
```

#### Phase 1 Completion Summary

**Implemented:**
- `_is_judgment_question()` method: Detects 25+ opinion patterns, 20+ benchmark indicators, 17+ goal/timeline patterns
- `_needs_return_clarification()` method: Forces clarification when return-context + comparison language detected
- `_skip_deterministic_shortcuts` flag: Applied to all 8 deterministic shortcuts in `chat()`
- Expanded `_RETURN_CONTEXT_PHRASES`: 30+ new phrases (post-injury, recovery phase, first week back, etc.)
- New test file: `apps/api/tests/test_coach_routing.py` (17 tests, 6 test classes)

**Key Fix:**
The exact message that was failing ("Since I was in 3:08 marathon shape...would it be reasonable...") now:
1. Detected as judgment question (bypasses all shortcuts)
2. Routes directly to LLM with full context
3. No more "self-guided" deflection

---

### Phase 2: Context Architecture Overhaul (2-4 hours) ✅ COMPLETE

**Status**: Completed 2026-01-27  
**Commit**: `cf0c995` feat(coach): Phase 2 context architecture overhaul (beta-ready delivery)

**Goal**: Give the AI the right context, in the right way, at the right time.

#### 2.1 Use `additional_instructions` Instead of User Messages

The current approach of injecting context as "user" messages pollutes the thread and gets lost. OpenAI Assistants API supports `additional_instructions` on the run:

```python
# BEFORE (current)
self.client.beta.threads.messages.create(
    thread_id=thread_id,
    role="user",
    content="CRITICAL INSTRUCTION..."
)

# AFTER (correct)
run = self.client.beta.threads.runs.create(
    thread_id=thread_id,
    assistant_id=self.assistant_id,
    model=model,
    additional_instructions=self._build_run_instructions(athlete_id, message)
)
```

Benefits:
- Instructions are system-level, not user messages
- Don't pollute thread history
- Always fresh for each run
- Can include athlete-specific context

#### 2.2 Build Dynamic Run Instructions

```python
def _build_run_instructions(self, athlete_id: UUID, message: str) -> str:
    """Build per-run instructions based on message type and athlete state."""
    instructions = []
    
    # Always include current state
    load = coach_tools.get_training_load(self.db, athlete_id)
    instructions.append(f"Current training state: ATL={load['atl']}, CTL={load['ctl']}, TSB={load['tsb']}")
    
    # Add question-type-specific instructions
    if self._is_judgment_question(message):
        instructions.append(
            "CRITICAL: The athlete is asking for your JUDGMENT/OPINION. "
            "Answer DIRECTLY first (yes/no/maybe with confidence level), "
            "then provide evidence and caveats. Do NOT deflect or ask for more info."
        )
    
    if self._has_benchmark_reference(message):
        instructions.append(
            "The athlete referenced a past benchmark. Compare their CURRENT metrics "
            "to that benchmark and estimate timeline to return. Be specific with numbers."
        )
    
    if self._is_post_injury_context(athlete_id, message):
        instructions.append(
            "CONTEXT: This athlete is returning from injury. All comparisons should "
            "default to post-return period unless explicitly stated otherwise."
        )
    
    return "\n\n".join(instructions)
```

#### 2.3 Increase Thread Context Window

Current limits are too restrictive:
- `get_thread_history`: 50 messages default, 200 max
- Context injection: only looks at last 10 messages

Increase to capture more conversation context:
```python
# In get_thread_history
limit = min(limit or 100, 500)  # Increase default to 100, max to 500

# In context injection
prior_user_messages = []  # Last 20 instead of 10
```

#### Phase 2 Completion Summary

**Implemented:**
- `_build_run_instructions()` method: Builds dynamic per-run instructions based on question type
- Switched from user message injection to `additional_instructions` on the run
- Thread history limits increased: default 50→100, max 200→500
- Prior messages: fetch 40, cap at 20 user messages
- Training state (ATL/CTL/TSB) with form label always included
- Question-type-specific instructions: CRITICAL JUDGMENT, RETURN-FROM-INJURY, BENCHMARK REFERENCE, PRESCRIPTION REQUEST
- Expanded `_RETURN_CONTEXT_PHRASES` with 6 additional phrases

**Key Improvement:**
Context injection is now system-level via `additional_instructions`:
1. Higher priority than user messages
2. Doesn't pollute thread history (cleaner conversation)
3. Always fresh for each run
4. Includes athlete-specific context dynamically

**Tests Added:** 11 new tests (26 total) covering dynamic instructions, limits, and injection.

---

### Phase 3: Tool Data Expansion (2-3 hours) ✅ COMPLETE

**Status**: Completed 2026-01-27  
**Commit**: `9ac11f7` feat(coach): Phase 3 tool data expansion (beta-ready N=1 depth)

**Goal**: Give the AI access to data it needs but currently can't see.

#### 3.1 Missing Activity Data

Add to `get_recent_runs` and `get_best_runs`:

```python
# Currently missing
"total_elevation_gain": activity.total_elevation_gain,  # meters
"temperature_f": activity.temperature_f,
"humidity_pct": activity.humidity_pct,
"weather_condition": activity.weather_condition,
"max_hr": activity.max_hr,
"performance_percentage": activity.performance_percentage,  # age-graded
```

#### 3.2 New Wellness Tool

Create `get_wellness_trends` tool:

```python
def get_wellness_trends(db: Session, athlete_id: UUID, days: int = 30) -> Dict:
    """Get wellness data (sleep, stress, soreness) with performance correlations."""
    checkins = db.query(DailyCheckin).filter(
        DailyCheckin.athlete_id == athlete_id,
        DailyCheckin.checkin_date >= date.today() - timedelta(days=days)
    ).all()
    
    return {
        "ok": True,
        "data": {
            "avg_sleep_hours": mean([c.sleep_h for c in checkins if c.sleep_h]),
            "avg_stress": mean([c.stress_1_5 for c in checkins if c.stress_1_5]),
            "avg_soreness": mean([c.soreness_1_5 for c in checkins if c.soreness_1_5]),
            "sleep_trend": calculate_trend(...),
            "correlation_sleep_efficiency": calculate_correlation(...),
        },
        "evidence": [...]
    }
```

#### 3.3 New Athlete Profile Tool

Create `get_athlete_profile` tool:

```python
def get_athlete_profile(db: Session, athlete_id: UUID) -> Dict:
    """Get athlete's profile, thresholds, and consistency metrics."""
    athlete = db.query(Athlete).get(athlete_id)
    
    return {
        "ok": True,
        "data": {
            "runner_type": athlete.runner_type,
            "threshold_pace_per_km": athlete.threshold_pace_per_km,
            "threshold_hr": athlete.threshold_hr,
            "current_streak_weeks": athlete.current_streak_weeks,
            "longest_streak_weeks": athlete.longest_streak_weeks,
            "consistency_index": athlete.consistency_index,
            "injury_history_summary": get_injury_summary(db, athlete_id),
        },
        "evidence": [...]
    }
```

#### 3.4 New Historical Load Tool

Create `get_training_load_history` tool:

```python
def get_training_load_history(db: Session, athlete_id: UUID, days: int = 90) -> Dict:
    """Get historical training load time series."""
    # Return daily ATL/CTL/TSB values for the period
    return {
        "ok": True,
        "data": {
            "time_series": [
                {"date": "2026-01-26", "atl": 31.2, "ctl": 22.6, "tsb": -8.6},
                {"date": "2026-01-25", "atl": 30.1, "ctl": 22.4, "tsb": -7.7},
                # ...
            ],
            "peak_ctl_date": "2025-12-15",
            "peak_ctl_value": 45.2,
            "current_vs_peak_pct": 50.0,
        },
        "evidence": [...]
    }
```

#### Phase 3 Completion Summary

**Implemented:**
- **Expanded `get_recent_runs`**: Added `max_hr`, `elevation_gain_m/ft`, `temperature_f`, `humidity_pct`, `weather_condition`
- **New `get_wellness_trends`**: Sleep/stress/soreness with trends, HRV rMSSD, resting HR, mindset (enjoyment/confidence/motivation)
- **New `get_athlete_profile`**: Physiological (max_hr, threshold pace/HR, VDOT), HR zones, runner typing (speedster/endurance/balanced), training metrics (durability, recovery half-life, consistency, streaks)
- **New `get_training_load_history`**: Daily ATL/CTL/TSB snapshots, form state labels, injury risk (acute:chronic ratio), CTL trend direction

**Key Improvement:**
The AI Coach now has access to critical data that was previously missing:
1. Environmental context (temperature, humidity, elevation) for run analysis
2. Wellness/recovery data for readiness assessment
3. Athlete profile for personalized recommendations
4. Training load history for periodization context

**Tests Added:** 12 new tests covering all new tools and expanded fields.

---

### Phase 4: Code Architecture Refactor (3-4 hours) ✅ COMPLETE

**Goal**: Make the code maintainable and testable.

**Status:** ✅ Complete (Commit: `a99047b`)

**Phase 4 completed:** Code refactor into coach_modules package (routing.py for detection/classification, context.py for dynamic instructions/injection), updated imports/entry points, 23 new tests for modular components (total 61 passing in 1.15s).

#### 4.1 Split ai_coach.py into Modules

```
apps/api/services/
├── ai_coach/
│   ├── __init__.py          # AICoach class (core orchestration only)
│   ├── routing.py           # Message classification and routing
│   ├── shortcuts.py         # Deterministic shortcut handlers
│   ├── context.py           # Context injection builders
│   ├── citations.py         # Citation enforcement
│   ├── thread_manager.py    # Thread persistence and history
│   └── run_instructions.py  # Per-run instruction builders
├── coach_tools.py           # Keep as-is (tool implementations)
```

#### 4.2 Extract Detection Methods

Move all `_is_*` detection methods to `routing.py`:

```python
# routing.py
class MessageRouter:
    def classify(self, message: str, athlete_context: dict) -> MessageType:
        """Classify message and return appropriate handler."""
        if self._is_judgment_question(message):
            return MessageType.JUDGMENT
        if self._is_prescription_request(message):
            return MessageType.PRESCRIPTION
        if self._is_comparison_question(message):
            return MessageType.COMPARISON
        # ...
        return MessageType.GENERAL
```

#### 4.3 Add Comprehensive Tests

```python
# test_coach_routing.py
class TestMessageRouting:
    def test_judgment_question_detected(self):
        """Timeline/judgment questions should route to AI, not shortcuts."""
        router = MessageRouter()
        
        # These should all be detected as judgment questions
        judgment_questions = [
            "Would it be reasonable to think I'll hit 3:08 by March?",
            "Do you think I can get back to my old pace?",
            "Am I on track for my goal?",
            "Is it realistic to run a marathon in 8 weeks?",
            "Since I was in 3:08 shape, will I be there in time?",
        ]
        
        for q in judgment_questions:
            result = router.classify(q, {})
            assert result == MessageType.JUDGMENT, f"Failed: {q}"
    
    def test_prescription_not_triggered_by_timeline(self):
        """'This week' in a timeline question should NOT trigger prescription."""
        router = MessageRouter()
        
        msg = "This week I move up to 55 miles. Would it be reasonable to think I'll be ready?"
        result = router.classify(msg, {})
        assert result != MessageType.PRESCRIPTION
```

---

### Phase 5: Conversation Quality Improvements (2-3 hours) ✅ COMPLETE

**Goal**: Make the Coach feel like a real coach, not a deflection machine.

**Status:** ✅ Complete (Commit: `4c6aac6`, Integration: `a2b302c`)

**Phase 5 completed:** Conversation quality with confidence gating, question tracking (already_answered_in_thread, already_asked_clarification), progressive detail levels (FULL → MODERATE → BRIEF), and 28 new tests (total 89 passing in 1.21s).

**Final Integration (Commit `a2b302c`):** All features integrated into `ai_coach.py`. Judgment routing via MessageRouter.classify(), confidence gating for JUDGMENT questions, progressive detail levels active, question tracking connected. Tests green (89 passing).

#### 5.1 Confidence-Gated Responses

Require the AI to state confidence levels:

```python
# In system instructions
"""
For ALL judgment/opinion questions, you MUST:
1. State your answer directly (yes/no/maybe)
2. State your confidence level (High/Medium/Low)
3. Explain your reasoning with evidence
4. List key risks or caveats

Example:
"**Yes, I think you can get back to 3:08 shape by March 15th** (Medium confidence).

Your current efficiency is at 85% of December levels, and your planned progression 
(55→65→70 mpw) aligns with what got you to 3:08 before. 

Key factors:
- Your 15-mile progression run on Jan 25 showed strong aerobic base (132 bpm avg)
- CTL is currently 22.6 vs peak of 45 in December — you need ~8 weeks to rebuild
- You have exactly 7 weeks + taper, which is tight

Risks:
1. Any injury setback loses critical build time
2. Speed work window is short (only 4 weeks before taper)
3. 10-mile tune-up will be the real test

Recommendation: Target 3:08-3:12 range. Let the tune-up calibrate your final goal."
"""
```

#### 5.2 Don't Repeat Clarification Asks

Track what's been answered in the thread:

```python
def _already_answered_in_thread(self, thread_id: str, question_type: str) -> bool:
    """Check if a clarification question was already answered."""
    history = self.get_thread_history_raw(thread_id, limit=20)
    
    # Look for patterns like "I'm returning from a break that started on..."
    answer_patterns = {
        "return_date": r"(returned|came back|started again).*(january|february|march|april|may|june|july|august|september|october|november|december|\d{1,2}/\d{1,2})",
        "pain_level": r"(no pain|no niggles|feeling (good|great|fine)|pain free)",
        "weekly_mileage": r"(\d{2,3})\s*(miles?|mpw|mi)",
    }
    
    if question_type in answer_patterns:
        for msg in history:
            if msg["role"] == "user" and re.search(answer_patterns[question_type], msg["content"], re.I):
                return True
    return False
```

#### 5.3 Progressive Detail Levels

Adjust response depth based on conversation:

```python
# First response: Full context
"Based on your December 3:08 shape and current return-from-injury data..."

# Follow-up: Briefer, assumes context
"Given what we discussed, your Jan 25 long run confirms you're on track..."

# Third question in same thread: Very brief
"Yes, the 10-mile tune-up will tell us if 3:08 is realistic."
```

---

## Implementation Priority

### Must-Have for Beta (Do First)

| Item | Effort | Impact |
|------|--------|--------|
| Phase 1.1-1.3: Routing fix | 1-2h | Critical - stops deflections |
| Phase 2.1-2.2: `additional_instructions` | 2h | High - proper context delivery |
| Phase 5.1: Confidence-gated responses | 1h | High - trust building |

### Should-Have for Beta

| Item | Effort | Impact |
|------|--------|--------|
| Phase 3.1: Missing activity data | 1h | Medium - better evidence |
| Phase 5.2: Don't repeat clarifications | 1h | Medium - UX improvement |
| Phase 4.3: Comprehensive tests | 2h | Medium - prevents regressions |

### Nice-to-Have (Post-Beta)

| Item | Effort | Impact |
|------|--------|--------|
| Phase 4.1-4.2: Code refactor | 3-4h | Low immediate, high long-term |
| Phase 3.2-3.4: New tools | 2-3h | Medium - expanded capabilities |
| Phase 5.3: Progressive detail | 2h | Low - polish |

---

## Success Criteria

### Functional Tests

1. **Judgment Question Routing**
   - "Would it be reasonable to think I'll hit 3:08 by March?" → AI gives direct answer
   - No hardcoded "self-guided" response
   - Response includes confidence level and evidence

2. **Benchmark Comparison**
   - "I was in 3:08 shape in December" → AI compares current metrics to December
   - Response includes: current vs benchmark %, estimated timeline, risks

3. **No Repeated Clarifications**
   - If user answers "I returned from injury on Jan 1" → Coach remembers this
   - Follow-up questions don't ask for return date again

4. **Evidence-Based Responses**
   - All numeric claims cite tool outputs
   - Citation enforcement never fails silently

### Quality Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Deflection rate (asks for more info instead of answering) | ~40% | <10% |
| Direct answer rate (yes/no/maybe + reasoning) | ~30% | >80% |
| Repeated clarification asks | ~25% | <5% |
| Citation coverage (% of numeric claims with evidence) | ~70% | >95% |

---

## Comprehensive Tools & Data Gap Analysis

Based on full reading of `coach_tools.py` (2,333 lines) and the data models.

### Current Tool Inventory (18 Tools)

| Tool | Purpose | Lines |
|------|---------|-------|
| `get_recent_runs` | Last N days of run activities | 91-189 |
| `get_calendar_day_context` | Specific day plan + actual | 192-327 |
| `get_efficiency_trend` | EF time series with fallback | 330-471 |
| `get_plan_week` | Current week's planned workouts | 474-553 |
| `get_training_load` | CTL/ATL/TSB summary | 556-598 |
| `get_correlations` | Wellness-performance correlations | 601-637 |
| `get_race_predictions` | Race time predictions (with PB-VDOT fallback) | 640-822 |
| `get_recovery_status` | Recovery half-life, durability, fatigue signals | 825-869 |
| `get_active_insights` | Prioritized actionable insights | 872-948 |
| `get_pb_patterns` | Training patterns before PBs | 951-1074 |
| `get_efficiency_by_zone` | Zone-specific efficiency (easy/threshold/race) | 1077-1199 |
| `get_nutrition_correlations` | Activity-linked nutrition correlations | 1202-1279 |
| `get_weekly_volume` | Weekly rollups (distance/time/count) | 1282-1389 |
| `get_best_runs` | Best runs by metric (efficiency/pace/distance) | 1392-1536 |
| `compare_training_periods` | Last N days vs previous N days | 1539-1666 |
| `get_coach_intent_snapshot` | Self-guided coaching state | 1722-1768 |
| `set_coach_intent_snapshot` | Update self-guided coaching state | 1771-1836 |
| `get_training_prescription_window` | Deterministic 1-7 day prescriptions | 1839-2314 |

### Data Exposed by Tools vs Data in Models

#### Activity Model Fields

| Field | In Model | Exposed in Tools | Gap |
|-------|----------|------------------|-----|
| `distance_m` | Yes | Yes | - |
| `duration_s` | Yes | Yes | - |
| `avg_hr` | Yes | Yes | - |
| `max_hr` | Yes | **NO** | Missing - needed for HR zone accuracy |
| `total_elevation_gain` | Yes | **NO** | Missing - critical for "why was this hard?" |
| `average_speed` | Yes | Derived as pace | - |
| `workout_type` | Yes | Yes | - |
| `workout_zone` | Yes | **NO** | Missing - could improve zone filtering |
| `intensity_score` | Yes | Yes | - |
| `temperature_f` | Yes | **NO** | Missing - environmental context |
| `humidity_pct` | Yes | **NO** | Missing - environmental context |
| `weather_condition` | Yes | **NO** | Missing - "it was rainy" context |
| `performance_percentage` | Yes | **NO** | Missing - age-graded performance |
| `is_race_candidate` | Yes | **NO** | Could help identify race efforts |
| **ActivitySplit** | | | |
| `split_number` | Yes | **NO** | Missing - pacing strategy analysis |
| `average_heartrate` (per split) | Yes | **NO** | Missing - effort distribution |
| `average_cadence` | Yes | **NO** | Missing - cadence analysis |
| `gap_seconds_per_mile` | Yes | **NO** | Missing - Grade Adjusted Pace |

#### DailyCheckin Model Fields

| Field | In Model | Exposed in Tools | Gap |
|-------|----------|------------------|-----|
| `sleep_h` | Yes | **NO** | Missing - sleep correlation |
| `stress_1_5` | Yes | **NO** | Missing - stress correlation |
| `soreness_1_5` | Yes | **NO** | Missing - soreness correlation |
| `rpe_1_10` | Yes | **NO** | Missing - perceived effort |
| `hrv_rmssd` | Yes | **NO** | Missing - HRV recovery |
| `resting_hr` | Yes | **NO** | Missing - resting HR trends |
| `overnight_avg_hr` | Yes | **NO** | Missing - recovery indicator |
| `enjoyment_1_5` | Yes | **NO** | Missing - enjoyment correlation |
| `confidence_1_5` | Yes | **NO** | Missing - mindset data |
| `motivation_1_5` | Yes | **NO** | Missing - motivation tracking |

#### Athlete Profile Fields

| Field | In Model | Exposed in Tools | Gap |
|-------|----------|------------------|-----|
| `max_hr` | Yes | Used internally, not exposed | Partially available |
| `resting_hr` | Yes | **NO** | Missing for recovery context |
| `threshold_pace_per_km` | Yes | **NO** | Missing - threshold reference |
| `threshold_hr` | Yes | **NO** | Missing - threshold reference |
| `vdot` | Yes | Used in race predictions | Partially available |
| `runner_type` | Yes | **NO** | Missing - speedster/endurance context |
| `durability_index` | Yes | Via `get_recovery_status` | Available |
| `consistency_index` | Yes | **NO** | Missing - consistency context |
| `current_streak_weeks` | Yes | **NO** | Missing - motivation data |
| `longest_streak_weeks` | Yes | **NO** | Missing - motivation data |
| `height_cm` | Yes | **NO** | Missing for BMI context |

### Critical Tool Gaps

#### 1. No Wellness Trends Tool

The `DailyCheckin` model has rich wellness data (sleep, stress, soreness, HRV, enjoyment) but NO tool exposes it. The AI cannot answer:
- "How's my sleep affecting my running?"
- "Am I overtraining?" (beyond TSB)
- "Is my stress impacting performance?"

**Proposed Tool**: `get_wellness_trends(days=30)`

```python
def get_wellness_trends(db, athlete_id, days=30):
    return {
        "data": {
            "avg_sleep_h": 7.2,
            "avg_stress": 2.1,
            "avg_soreness": 1.8,
            "sleep_trend": "declining",
            "recent_hrv_avg": 45.2,
            "correlation_sleep_efficiency": -0.34,  # negative = better sleep → better efficiency
        }
    }
```

#### 2. No Athlete Profile Tool

The AI cannot answer questions about the athlete's baseline characteristics:
- "What's my threshold pace?"
- "Am I a speedster or endurance runner?"
- "How consistent have I been?"

**Proposed Tool**: `get_athlete_profile()`

```python
def get_athlete_profile(db, athlete_id):
    return {
        "data": {
            "runner_type": "endurance_monster",
            "threshold_pace_per_km": 285.0,  # 4:45/km
            "threshold_hr": 168,
            "vdot": 52.3,
            "consistency_index": 78.5,
            "current_streak_weeks": 6,
            "max_hr": 185,
            "resting_hr": 52,
        }
    }
```

#### 3. No Historical Training Load Tool

`get_training_load` only returns current values. The AI cannot answer:
- "What was my CTL at my peak in December?"
- "How does my current fitness compare to 3 months ago?"

**Proposed Tool**: `get_training_load_history(days=90)`

```python
def get_training_load_history(db, athlete_id, days=90):
    return {
        "data": {
            "time_series": [...],
            "peak_ctl_date": "2025-12-15",
            "peak_ctl_value": 45.2,
            "current_vs_peak_pct": 50.0,
        }
    }
```

#### 4. Missing Environmental Context in Activity Tools

`get_recent_runs` and `get_best_runs` don't include elevation, temperature, or weather. The AI cannot explain:
- "Why was that run so hard?" (1000ft elevation gain)
- "Your pace was slower but it was 95°F"

**Fix**: Add to existing tools:
```python
"total_elevation_gain_m": int(a.total_elevation_gain) if a.total_elevation_gain else None,
"temperature_f": float(a.temperature_f) if a.temperature_f else None,
"humidity_pct": float(a.humidity_pct) if a.humidity_pct else None,
"weather_condition": a.weather_condition,
"max_hr": int(a.max_hr) if a.max_hr else None,
```

#### 5. No Splits/Pacing Analysis Tool

The `ActivitySplit` model has per-split data (pace, HR, cadence, GAP) but no tool exposes it. The AI cannot answer:
- "Did I positive split or negative split?"
- "What was my cadence like?"
- "What's my Grade Adjusted Pace for that hilly run?"

**Proposed Tool**: `get_activity_splits(activity_id)`

### Tool Enhancement Priority

| Priority | Tool/Enhancement | Effort | Impact |
|----------|------------------|--------|--------|
| High | Add elevation/weather to `get_recent_runs` | 30 min | Explains "why hard" |
| High | Create `get_wellness_trends` | 1 hour | Sleep/stress answers |
| High | Create `get_athlete_profile` | 1 hour | Threshold/type answers |
| Medium | Create `get_training_load_history` | 1 hour | Historical comparisons |
| Medium | Add `max_hr` to activity tools | 15 min | HR zone accuracy |
| Low | Create `get_activity_splits` | 2 hours | Pacing analysis |

---

## Appendix: Files to Modify

### Primary Changes

| File | Lines Affected | Changes |
|------|----------------|---------|
| `apps/api/services/ai_coach.py` | 1054-1109, 1266-1321, 1672-1771 | Routing, context injection, detection |
| `apps/api/services/coach_tools.py` | New additions | New tools for wellness, profile, load history |

### Secondary Changes

| File | Changes |
|------|---------|
| `apps/api/tests/test_coach_routing.py` | New test file |
| `apps/api/tests/test_coach_integration.py` | New test file |

---

## Next Steps

1. **Approve this plan** or request modifications
2. **Prioritize**: Which items are must-have for immediate beta?
3. **Execute**: Implement in priority order, deploy, verify each item before next
4. **Test**: Run through the 10 judgment questions that previously failed
