# Builder Instructions: Coach Phase 7 — Voice, Knowledge, and Guardrail Overhaul

**Created:** 2026-04-25  
**Priority:** CRITICAL — founder considers current coach unusable  
**Context:** `docs/COACH_IMPROVEMENT_PLAN.md` (Phase 7 shipped 2026-04-25)  
**Read first:** `docs/FOUNDER_OPERATING_CONTRACT.md`, then `docs/COACH_IMPROVEMENT_PLAN.md`

## Background

Phases 1-6 fixed the plumbing: activity search, athlete state injection, nutrition grounding, conversation contracts, race strategy packets, eval harness, and frontend trust UX. All shipped.

On 2026-04-25, the founder had a race-morning conversation with the coach. The coach had every mechanical advantage — activity history, stream data, training load, race predictions — and produced answers worse than an outside LLM that had zero athlete data. The root failures are both mechanical and behavioral:

1. The retrieval layer missed or buried decisive workouts before the coach formed a judgment.
2. The coach refuses to use knowledge the base model already has.
3. The coach hedges every recommendation instead of coaching.
4. The guardrails make it less useful than an unconstrained LLM.
5. The coach does not distinguish race-day execution from race-planning analysis.
6. The coach reads individual workouts in isolation instead of synthesizing training arcs.
7. The coach trusts its own zone model over recent workout evidence.

## Build Order

Execute in this order. Each section is independently testable.

**Retrieval-first slice (shipped in this session):**

1. **7K** — DB-backed retrieval eval scenarios (new test file)
2. **7G** — Search brittleness fix, including split-aware fallback for generic titles
3. **7J** — Training block structure-aware enhancement from `ActivitySplit`
4. **7H** — Race packet workout cap/ranking fix
5. **7I** — Thread-aware conversation classification for race-day follow-ups

**Behavior/voice slice (shipped in this session):**

6. **7A** — Knowledge Suppression Fix (system prompt + guardrail change)
7. **7B** — Voice and Confidence Directive (system prompt + hedge detection guardrail)
8. **7E** — Guardrail Audit (system prompt cleanup + forced-tool relaxation)
9. **7C** — Race-Day Execution Mode prompt/output shaping
10. **7D** — Training Block Narrative Synthesis prompt/tool consumption
11. **7F** — Zone Accuracy Questioning (system prompt instruction)
12. **Tests** — regression cases for all remaining behavioral/prompt changes

---

## 7A: Knowledge Suppression Fix

### Problem

The system prompt's ZERO-HALLUCINATION RULE makes no distinction between:
- Hallucinating athlete-specific data (bad)
- Refusing general sports science knowledge (also bad)

The coach says "I can't verify your past use from the tools" when asked about sodium bicarb timing — a question any competent coach can answer from general knowledge.

### File: `apps/api/services/coaching/_context.py`

**Location:** `_build_coach_system_prompt`, lines ~87-100 (the ZERO-HALLUCINATION RULE block)

**Current text (replace this exact block):**
```
ZERO-HALLUCINATION RULE (NON-NEGOTIABLE): Every number, distance, pace, date, and training fact you state MUST come from tool results. NEVER fabricate or estimate ANY training data. If you haven't called a tool yet, call one NOW. If no tool has the data, say "I don't have that data" -- NEVER make it up. This athlete relies on you exclusively. A wrong number could cause injury. All dates in tool results include pre-computed relative times like '(2 days ago)'. USE those labels verbatim -- do NOT compute your own relative time.
```

**Replace with:**
```
ZERO-HALLUCINATION RULE (NON-NEGOTIABLE): Every number, distance, pace, date, and training fact ABOUT THIS ATHLETE must come from tool results. NEVER fabricate or estimate athlete-specific training data. If you haven't called a tool yet, call one NOW. If no tool has the data, say "I don't have that in your history." All dates in tool results include pre-computed relative times like '(2 days ago)'. USE those labels verbatim -- do NOT compute your own relative time.

GENERAL KNOWLEDGE RULE (EQUALLY NON-NEGOTIABLE): You are an expert coach. When the athlete asks about sports science, nutrition timing, supplement protocols, warmup routines, race execution, recovery practices, or any domain where established knowledge exists — ANSWER FROM YOUR KNOWLEDGE. Do not say "I can't verify" or "I don't have data on that" for questions that any competent running coach could answer. Label general guidance as general: "Standard protocol is..." or "For most runners..." Then ask a follow-up to personalize if relevant athlete data exists. NEVER refuse an answerable question because the database is empty on that topic.
```

### Verification

After this change, grep the full system prompt string for "I don't have that data" — it should be gone, replaced by "I don't have that in your history."

---

## 7B: Voice and Confidence Directive

### Problem

The coach hedges reflexively. "Still aggressive," "it's worth noting," "that said." Every recommendation is wrapped in qualifiers.

### Part 1: System prompt directive

**File:** `apps/api/services/coaching/_context.py`  
**Location:** Inside `_build_coach_system_prompt`, after the existing `BAN CANNED OPENERS` block (around line ~175) and before `ANTI-LEAKAGE RULES`.

**Add this new block:**
```
VOICE DIRECTIVE (NON-NEGOTIABLE):
- Lead with your position. State the recommendation FIRST, then the reasoning.
- Do NOT wrap recommendations in hedge phrases. These are treated like banned words:
  - "still aggressive" / "that's aggressive"
  - "it's worth noting"
  - "that said"
  - "it's possible that"
  - "I would suggest considering"
  - "it may be worth"
  - "just something to keep in mind"
  - "I should mention"
  - "to be fair"
  - "I want to be careful"
  - "proceed with caution"
- Genuine uncertainty is allowed and encouraged: "Your threshold model says 6:31 but your recent 400s suggest faster — I'd reason from what you actually ran." That is direct uncertainty. "The 5:55 attempt is still aggressive" is a hedge. Know the difference.
- Match the athlete's energy. Excited and decisive athlete gets a decisive coach. Anxious athlete gets a steady coach. Do NOT default to caution regardless of context.
- If the athlete has made a decision ("I'm going out at 5:50"), help execute that decision. Risk context is ONE sentence max, then execution guidance. Do not lecture about whether the decision is wise.
```

### Part 2: Hedge detection guardrail

**File:** `apps/api/services/coaching/_constants.py`

**Add after the existing `_KB_VIOLATION_PATTERNS` list (around line 128):**

```python
_HEDGE_PHRASES = [
    "still aggressive",
    "that's aggressive",
    "it's worth noting",
    "that said",
    "it's possible that",
    "i would suggest considering",
    "it may be worth",
    "just something to keep in mind",
    "i should mention",
    "to be fair",
    "i want to be careful",
    "proceed with caution",
    "worth considering",
    "something to think about",
    "you might want to consider",
    "it's important to remember",
    "i'd recommend being cautious",
    "on the other hand",
]

def count_hedge_phrases(text: str) -> int:
    lower = text.lower()
    return sum(1 for phrase in _HEDGE_PHRASES if phrase in lower)
```

**File:** `apps/api/services/coaching/_constants.py`  
**Location:** Inside `_check_response_quality` (lines ~151-168)

**Add to the existing quality checks, after the emoji/word-count checks:**

```python
hedge_count = count_hedge_phrases(text)
if hedge_count >= 3:
    logger.warning(
        "coach_quality hedge_overload count=%d text_preview=%.100s",
        hedge_count,
        text[:100],
    )
```

This is a logging-first approach. It does not block the response. Once we observe the frequency, we can escalate to retry logic.

---

## 7E: Guardrail Audit (System Prompt Cleanup + Forced Tool Relaxation)

### Problem 1: System prompt over-constrains

The system prompt says "ALWAYS call get_weekly_volume first." This forces volume data into bicarb questions, warmup questions, and emotional support turns. The instruction is from before conversation contracts existed.

### Change 1: Replace forced tool mandate in system prompt

**File:** `apps/api/services/coaching/_context.py`  
**Location:** Lines ~98-113 of the system prompt (the `YOU HAVE TOOLS -- USE THEM PROACTIVELY` block)

**Current text:**
```
YOU HAVE TOOLS -- USE THEM PROACTIVELY:
- ALWAYS call get_weekly_volume first to understand the athlete's training history
- Call get_recent_runs to see individual workout details (up to 730 days back)
- Call get_training_load for current fitness/fatigue/form
- Call get_training_load_history for load progression over time
- Call get_recovery_status for injury risk assessment
- Call get_athlete_profile for age, experience, preferences
- Call get_efficiency_trend to track fitness changes over time
- Call get_best_runs for peak performance data
- Call compare_training_periods to compare recent vs previous training
- Call get_calendar_day_context for specific day plan + actual
- Call get_wellness_trends for sleep, stress, soreness patterns
- For race strategy, race plan, pacing, or execution questions, call get_race_strategy_packet first
- NEVER say "I don't have access" -- call the tools instead
```

**Replace with:**
```
YOU HAVE TOOLS -- USE THEM WHEN RELEVANT:
- For training questions: get_weekly_volume, get_recent_runs, get_training_load, compare_training_periods
- For race strategy/execution: get_race_strategy_packet, get_training_paces, search_activities
- For specific workouts: search_activities, get_calendar_day_context, get_mile_splits, analyze_run_streams
- For performance analysis: get_best_runs, get_efficiency_trend, get_race_predictions
- For recovery/wellness: get_recovery_status, get_wellness_trends
- For athlete context: get_athlete_profile, get_coach_intent_snapshot
- NEVER say "I don't have access" -- if you need data, call a tool
- But do NOT call tools for questions that don't need athlete data (general sports science, supplement timing, warmup protocols). Just answer those directly.
- When the athlete corrects you or says something exists, call search_activities to verify before responding.
```

### Change 2: Replace forced tool mandate in user message preamble

**File:** `apps/api/services/coaching/_llm.py`  
**Location:** Lines ~286-296 (the user message construction in `query_kimi_coach`)

**Current text:**
```python
"MANDATORY: Use the appropriate coach tools before making data claims. "
"For race strategy, race plan, pacing, or execution questions, call "
"get_race_strategy_packet first. "
"For specific older activities or athlete corrections that something exists, "
"call search_activities instead of relying on recent-run summaries. "
"Do NOT answer analytic/data questions without tool data.\n\n"
```

**Replace with:**
```python
"Use tools when you need athlete-specific data. "
"For race strategy or execution, call get_race_strategy_packet. "
"For athlete corrections ('that workout exists'), call search_activities. "
"For general sports science questions (supplements, warmup, nutrition timing), "
"answer directly from your knowledge — do not call tools first.\n\n"
```

### Change 3: Make tool_choice="auto" for non-data questions

**File:** `apps/api/services/coaching/_llm.py`  
**Location:** Lines ~306-310 (the `tool_choice` assignment in `query_kimi_coach`)

**Current logic:**
```python
tc = "required" if iteration == 0 else "auto"
```

**New logic — add an `is_data_question` check:**

Above the for loop (around line 303), add:
```python
needs_tools_first = self._is_data_question(message)
```

Then change the tool_choice line to:
```python
tc = "required" if (iteration == 0 and needs_tools_first) else "auto"
```

This means general knowledge questions (bicarb timing, warmup protocols) skip the forced first tool call. Data questions still force a tool call on iteration 0.

**Note:** `_is_data_question` is defined on `PrescriptionMixin` which `AICoach` inherits. Since `query_kimi_coach` is on `LLMMixin`, you need to call it via `self._is_data_question(message)` — verify the MRO allows this. If not, import and call it as a standalone function.

---

## 7C: Race-Day Execution Mode

### Problem

"I have a race in 3 hours" and "I'm thinking about racing a 5K next month" trigger the same conversation contract. The coach responds to race-morning questions with planning analysis instead of execution guidance.

### Change 1: Split race_strategy into race_day and race_planning

**File:** `apps/api/services/coaching/_conversation_contract.py`

**Add to `ConversationContractType` enum (line ~8-17):**
```python
RACE_DAY = "race_day"
```

**Update `classify_conversation_contract` (lines ~49-126):**

In the existing race detection branch (where `race_strategy` is assigned), add a temporal check BEFORE the generic race_strategy assignment:

```python
_RACE_DAY_RE = re.compile(
    r"race\s+(today|this morning|tonight|in\s+\d+\s+hours?|in\s+a\s+(few|couple)\s+hours?)"
    r"|racing\s+(today|this morning|tonight)"
    r"|5k\s+(today|this morning)"
    r"|marathon\s+(today|this morning)"
    r"|half\s+(today|this morning)"
    r"|start(s|ing)?\s+in\s+\d+\s+hours?"
    r"|going\s+out\s+at\s+\d+:\d+\s+pace"
    r"|my\s+race\s+is\s+(today|this morning|tonight|in\s+\d+\s+hours?)",
    re.IGNORECASE,
)
```

In the classification function, check `_RACE_DAY_RE` before the existing race check. If it matches, return `RACE_DAY` with:
```python
ConversationContract(
    contract_type=ConversationContractType.RACE_DAY,
    outcome_target="execution_plan",
    required_behavior="timeline, warmup prescription, mile-by-mile effort guidance, mental cues",
    max_words=300,
)
```

### Change 2: Add race_day validation

**In the same file, update `validate_conversation_contract_response`:**

Add a case for `RACE_DAY`:
```python
if contract.contract_type == ConversationContractType.RACE_DAY:
    lower = response_text.lower()
    has_execution = any(w in lower for w in ["mile 1", "mile 2", "first mile", "second mile", "warmup", "warm up", "warm-up", "stride", "jog"])
    if not has_execution:
        return False, "race_day response lacks execution guidance (warmup, mile-by-mile)"
    has_timeline = any(w in lower for w in ["minutes before", "min before", "hour before", "arrive", "leave"])
    # Timeline is nice-to-have, not required
    return True, ""
```

### Change 3: Add race-day system prompt supplement

**File:** `apps/api/services/coaching/_context.py`

Inside `_build_coach_system_prompt`, after the conversation contract is classified (or as a static block in the prompt since race_day detection happens per-turn):

Add to the system prompt, in the `REASONING APPROACH` section or as a new block after it:

```
RACE-DAY MODE:
When the athlete has a race TODAY (within the next 12 hours), you are in execution mode. Your job is to help them race well, not to assess whether their goal is realistic.
Required output elements for race-day conversations:
1. Timeline: when to leave, arrive, warmup start relative to gun time
2. Warmup prescription: specific drills, strides, duration (e.g., "10 min easy jog, 4-6 strides at 5K effort, 60-80m, full walk-back recovery")
3. Mile-by-mile effort guidance with effort scale, not just pace numbers (e.g., "Mile 1: 7/10, controlled and patient. Mile 2: 8-9/10, this is where you earn it. Mile 3.1: everything, empty the tank from 800m out")
4. Mental cues for adjustment (e.g., "If mile 1 feels like a 9/10, pull back to 6:00. If it feels like a 7/10, you are exactly on plan")
5. Supplement/fueling timing if discussed, slotted into the timeline
Do NOT: debate whether the goal pace is realistic, give extended risk analysis, or lead with "still aggressive." The athlete decided. Help them execute.
```

---

## 7D: Training Block Narrative Synthesis

### New tool: `get_training_block_narrative`

**File:** `apps/api/services/coach_tools/activity.py`

Add a new function after `get_best_runs`. This tool looks at the last N weeks of workouts and produces a structured training arc summary.

```python
def get_training_block_narrative(
    db: Session,
    athlete_id: UUID,
    weeks: int = 4,
) -> Dict[str, Any]:
    """
    Synthesize the recent training block into a narrative arc.
    
    Instead of listing individual workouts, this identifies:
    - What energy systems were trained (speed, speed endurance, threshold, aerobic)
    - The progression sequence
    - What's missing from the block
    - How recent the sharpest/hardest work is
    - Recovery pattern between key sessions
    """
    from services.timezone_utils import get_athlete_timezone_from_db, to_activity_local_date, athlete_local_today

    now = datetime.utcnow()
    weeks = max(1, min(int(weeks or 4), 12))
    cutoff = now - timedelta(weeks=weeks)
    units = _preferred_units(db, athlete_id)
    ath_tz = get_athlete_timezone_from_db(db, athlete_id)
    ref_date = athlete_local_today(ath_tz)

    activities = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.sport == "run",
            Activity.start_time >= cutoff,
        )
        .order_by(Activity.start_time.asc())
        .limit(100)
        .all()
    )

    if not activities:
        return {
            "ok": True,
            "tool": "get_training_block_narrative",
            "narrative": f"No running activities in the last {weeks} weeks.",
            "data": {"weeks": weeks, "sessions": []},
            "evidence": [],
        }

    sessions = []
    workout_types_seen = set()
    intensity_sequence = []
    total_distance_m = 0
    total_duration_s = 0
    key_sessions = []

    for a in activities:
        local_date = to_activity_local_date(a, ath_tz)
        rel = _relative_date(local_date, ref_date) if local_date else ""
        dist_m = float(a.distance_m or 0)
        dur_s = float(a.duration_s or 0)
        total_distance_m += dist_m
        total_duration_s += dur_s

        pace_mi = _pace_str_mi(
            int(a.duration_s) if a.duration_s else None,
            int(a.distance_m) if a.distance_m else None,
        )

        wtype = (a.workout_type or "").lower().strip()
        name_lower = (a.name or "").lower()
        intensity = float(a.intensity_score) if a.intensity_score is not None else None

        energy_system = "aerobic"
        if wtype in ("interval", "speed", "track") or any(
            kw in name_lower for kw in ["x 400", "x 800", "x 1000", "x 1200", "x 1600", "x mile", "repeat", "rep"]
        ):
            energy_system = "speed"
        elif wtype in ("tempo", "threshold") or any(
            kw in name_lower for kw in ["tempo", "threshold", "cruise"]
        ):
            energy_system = "threshold"
        elif wtype == "long_run" or (dist_m > 20000):
            energy_system = "endurance"
        elif any(kw in name_lower for kw in ["race", "5k", "10k", "half", "marathon"]):
            energy_system = "race"
        elif any(kw in name_lower for kw in ["stride", "strides", "shakeout"]):
            energy_system = "neuromuscular"
        elif any(kw in name_lower for kw in ["easy", "recovery"]):
            energy_system = "recovery"

        is_key = energy_system in ("speed", "threshold", "race", "endurance")
        if is_key:
            workout_types_seen.add(energy_system)

        session = {
            "date": local_date.isoformat() if local_date else None,
            "relative_date": rel,
            "name": a.name,
            "distance_mi": round(dist_m / _M_PER_MI, 2) if dist_m else None,
            "pace_per_mile": pace_mi,
            "avg_hr": int(a.avg_hr) if a.avg_hr is not None else None,
            "workout_type": a.workout_type,
            "energy_system": energy_system,
            "intensity_score": intensity,
            "is_key_session": is_key,
        }
        sessions.append(session)

        if is_key:
            key_sessions.append(session)
            intensity_sequence.append(energy_system)

    energy_systems_trained = sorted(workout_types_seen)
    common_missing = []
    if "threshold" not in workout_types_seen:
        common_missing.append("sustained threshold/tempo work")
    if "speed" not in workout_types_seen:
        common_missing.append("interval/speed work")
    if "endurance" not in workout_types_seen:
        common_missing.append("long run")

    days_since_hardest = None
    if key_sessions:
        last_key = key_sessions[-1]
        try:
            last_key_date = date.fromisoformat(last_key["date"])
            days_since_hardest = (ref_date - last_key_date).days
        except (ValueError, TypeError):
            pass

    total_mi = round(total_distance_m / _M_PER_MI, 1)
    total_hrs = round(total_duration_s / 3600, 1)

    narrative_parts = [
        f"Training block ({weeks} weeks): {len(activities)} sessions, {total_mi} mi, {total_hrs} hrs.",
        f"Energy systems trained: {', '.join(energy_systems_trained) if energy_systems_trained else 'aerobic only'}.",
        f"Progression sequence: {' → '.join(intensity_sequence) if intensity_sequence else 'no key sessions'}.",
    ]
    if common_missing:
        narrative_parts.append(f"Missing from block: {', '.join(common_missing)}.")
    if days_since_hardest is not None:
        narrative_parts.append(f"Last key session: {days_since_hardest} day(s) ago.")

    evidence = []
    for ks in key_sessions[-5:]:
        dist = ks.get("distance_mi") or 0
        evidence.append({
            "type": "activity",
            "date": f"{ks['date']} {ks.get('relative_date', '')}".strip(),
            "value": f"{ks['name']} | {dist:.1f} mi @ {ks.get('pace_per_mile', 'N/A')} [{ks['energy_system']}]",
        })

    return {
        "ok": True,
        "tool": "get_training_block_narrative",
        "generated_at": _iso(now),
        "narrative": " ".join(narrative_parts),
        "data": {
            "weeks": weeks,
            "session_count": len(activities),
            "total_distance_mi": total_mi,
            "total_hours": total_hrs,
            "energy_systems_trained": energy_systems_trained,
            "intensity_sequence": intensity_sequence,
            "missing_from_block": common_missing,
            "days_since_last_key_session": days_since_hardest,
            "key_sessions": key_sessions,
            "sessions": sessions,
        },
        "evidence": evidence,
    }
```

### Register the tool

**File:** `apps/api/services/coaching/_tools.py`

Add to `_opus_tools()` list (after `get_best_runs` or at end):
```python
{
    "name": "get_training_block_narrative",
    "description": "Synthesize the recent training block into a narrative arc: what energy systems were trained, the progression sequence, what's missing, and how recent the sharpest work is. Use this for race readiness assessment, training block review, or when the athlete asks about their recent training arc.",
    "input_schema": {
        "type": "object",
        "properties": {
            "weeks": {
                "type": "integer",
                "description": "Number of weeks to analyze (1-12, default 4)",
            },
        },
    },
},
```

**File:** `apps/api/services/coaching/_tools.py`

In the `_execute_opus_tool` method, add the dispatch case:
```python
elif name == "get_training_block_narrative":
    result = coach_tools.get_training_block_narrative(self.db, athlete_id, **tool_input)
```

**File:** `apps/api/services/coach_tools/__init__.py`

Add to imports:
```python
from .activity import get_training_block_narrative
```

### Also add to race strategy packet

**File:** `apps/api/services/coach_tools/race_strategy.py`

In `get_race_strategy_packet`, after the `workouts` line (~line 452), add:
```python
from services.coach_tools.activity import get_training_block_narrative
training_block = get_training_block_narrative(db, athlete_id, weeks=4)
```

Add `training_block` to the `data` dict and `availability` dict:
```python
"training_block_narrative": training_block if training_block.get("ok") else None,
```
```python
"training_block": bool(training_block.get("ok")),
```

---

## 7F: Zone Accuracy Questioning

### Problem

The coach stated threshold is 6:31/mi and built risk analysis on it. The athlete's recent 400s at 5:41-5:50 suggest the zone is stale. The coach never questioned its own zones.

### Change: System prompt instruction

**File:** `apps/api/services/coaching/_context.py`  
**Location:** Add to the system prompt, after the `DATA-VERIFICATION DISCIPLINE` block

```
ZONE CROSS-REFERENCE (NON-NEGOTIABLE):
When using training paces or pace zones for analysis (from get_training_paces), ALWAYS cross-reference with recent workout evidence (from get_recent_runs or search_activities). If recent interval, repetition, or race paces are materially faster than the zone model predicts:
- Acknowledge the discrepancy explicitly: "Your RPI-based threshold is 6:31/mi, but your recent 400s at 5:45 and mile repeats near 6:00 suggest you're fitter than the model reflects."
- Reason from the evidence, not the model. Build your pace guidance and risk assessment from what the athlete actually ran.
- Do NOT build a risk assessment ("that's aggressive relative to your threshold") based solely on zone numbers when recent evidence contradicts them.
This is especially important for race-day conversations where stale zones can produce overly conservative guidance.
```

---

## Tests

### File: `apps/api/tests/test_coach_phase7_regression.py`

Create this test file covering the Phase 7 regression cases. These should be deterministic contract tests (no live LLM calls), testing the system prompt, conversation contract classification, hedge detection, and tool registration.

```python
"""
Phase 7 regression tests — Voice, Knowledge, and Guardrail Overhaul.

These test the deterministic components: prompt text, contract classification,
hedge detection, tool registration. Live coach behavior tests belong in
test_coach_value_contract.py.
"""
import pytest
from datetime import datetime, timedelta


class TestKnowledgeSuppressionFix:
    """7A: The system prompt no longer tells the coach to say 'I don't have that data'
    as a terminal answer for general knowledge questions."""

    def test_system_prompt_has_general_knowledge_rule(self, db_session, test_athlete):
        from services.coaching.core import AICoach
        coach = AICoach(db=db_session)
        prompt = coach._build_coach_system_prompt(test_athlete.id)
        assert "GENERAL KNOWLEDGE RULE" in prompt
        assert "answer from your knowledge" in prompt.lower() or "ANSWER FROM YOUR KNOWLEDGE" in prompt

    def test_system_prompt_no_terminal_refusal(self, db_session, test_athlete):
        from services.coaching.core import AICoach
        coach = AICoach(db=db_session)
        prompt = coach._build_coach_system_prompt(test_athlete.id)
        assert "say \"I don't have that data\"" not in prompt


class TestVoiceDirective:
    """7B: Hedge detection exists and the system prompt bans hedge phrases."""

    def test_system_prompt_has_voice_directive(self, db_session, test_athlete):
        from services.coaching.core import AICoach
        coach = AICoach(db=db_session)
        prompt = coach._build_coach_system_prompt(test_athlete.id)
        assert "VOICE DIRECTIVE" in prompt
        assert "still aggressive" in prompt.lower()

    def test_hedge_count_zero_for_clean_text(self):
        from services.coaching._constants import count_hedge_phrases
        text = "Go out at 5:50 for mile 1. Hold 5:45 for mile 2. Empty the tank mile 3."
        assert count_hedge_phrases(text) == 0

    def test_hedge_count_detects_hedges(self):
        from services.coaching._constants import count_hedge_phrases
        text = (
            "The 5:50 attempt is still aggressive. That said, it's worth noting "
            "that you might want to consider a more conservative approach. "
            "I would suggest considering a warmup."
        )
        assert count_hedge_phrases(text) >= 3

    def test_hedge_count_allows_genuine_uncertainty(self):
        from services.coaching._constants import count_hedge_phrases
        text = (
            "I'm not confident your threshold is still 6:31 given your recent 400s. "
            "Your speed work suggests you're fitter than the model reflects."
        )
        assert count_hedge_phrases(text) <= 1


class TestGuardrailAudit:
    """7E: Forced tool mandate is relaxed for non-data questions."""

    def test_system_prompt_no_always_call_weekly_volume(self, db_session, test_athlete):
        from services.coaching.core import AICoach
        coach = AICoach(db=db_session)
        prompt = coach._build_coach_system_prompt(test_athlete.id)
        assert "ALWAYS call get_weekly_volume first" not in prompt

    def test_system_prompt_has_intent_based_tool_guidance(self, db_session, test_athlete):
        from services.coaching.core import AICoach
        coach = AICoach(db=db_session)
        prompt = coach._build_coach_system_prompt(test_athlete.id)
        assert "USE THEM WHEN RELEVANT" in prompt

    def test_non_data_question_not_forced_tool(self):
        """_is_data_question should return False for general knowledge."""
        from services.coaching._prescriptions import PrescriptionMixin
        mixin = PrescriptionMixin()
        assert not mixin._is_data_question("Should I take sodium bicarb before a race?")
        assert not mixin._is_data_question("How should I warm up for a 5K?")
        assert not mixin._is_data_question("What is carb loading?")

    def test_data_question_still_detected(self):
        from services.coaching._prescriptions import PrescriptionMixin
        mixin = PrescriptionMixin()
        assert mixin._is_data_question("How far did I run last week?")
        assert mixin._is_data_question("What was my pace on yesterday's tempo?")


class TestRaceDayContract:
    """7C: Race-day conversations get classified as race_day, not race_strategy."""

    def test_race_today_classified_as_race_day(self):
        from services.coaching._conversation_contract import classify_conversation_contract
        contract = classify_conversation_contract("I have a 5K race today, how should I warm up?")
        assert contract.contract_type.value == "race_day"

    def test_race_this_morning_classified_as_race_day(self):
        from services.coaching._conversation_contract import classify_conversation_contract
        contract = classify_conversation_contract("My race is this morning. Going out at 5:50 pace.")
        assert contract.contract_type.value == "race_day"

    def test_race_in_3_hours_classified_as_race_day(self):
        from services.coaching._conversation_contract import classify_conversation_contract
        contract = classify_conversation_contract("Race starts in 3 hours, what should I eat?")
        assert contract.contract_type.value == "race_day"

    def test_race_next_month_classified_as_race_strategy(self):
        from services.coaching._conversation_contract import classify_conversation_contract
        contract = classify_conversation_contract("I'm thinking about racing a 5K next month. What pace should I target?")
        assert contract.contract_type.value == "race_strategy"


class TestTrainingBlockNarrative:
    """7D: Training block narrative tool exists and returns structured data."""

    def test_tool_registered(self):
        from services.coaching._tools import ToolsMixin
        mixin = ToolsMixin()
        tool_names = [t["name"] for t in mixin._opus_tools()]
        assert "get_training_block_narrative" in tool_names

    def test_empty_history_returns_ok(self, db_session, test_athlete):
        from services.coach_tools.activity import get_training_block_narrative
        result = get_training_block_narrative(db_session, test_athlete.id, weeks=4)
        assert result["ok"] is True
        assert "no running activities" in result["narrative"].lower() or result["data"]["session_count"] == 0

    def test_returns_energy_systems(self, db_session, test_athlete):
        """With activities present, the tool identifies energy systems."""
        from models import Activity
        now = datetime.utcnow()
        for i, (name, wtype) in enumerate([
            ("16 x 400", "interval"),
            ("Easy run", "easy"),
            ("Tempo 5 mi", "tempo"),
        ]):
            db_session.add(Activity(
                athlete_id=test_athlete.id,
                sport="run",
                name=name,
                workout_type=wtype,
                start_time=now - timedelta(days=i * 3),
                distance_m=8000,
                duration_s=2400,
            ))
        db_session.flush()

        from services.coach_tools.activity import get_training_block_narrative
        result = get_training_block_narrative(db_session, test_athlete.id, weeks=4)
        assert result["ok"] is True
        assert result["data"]["session_count"] == 3
        assert len(result["data"]["energy_systems_trained"]) > 0


class TestZoneCrossReference:
    """7F: System prompt instructs zone cross-referencing."""

    def test_system_prompt_has_zone_cross_reference(self, db_session, test_athlete):
        from services.coaching.core import AICoach
        coach = AICoach(db=db_session)
        prompt = coach._build_coach_system_prompt(test_athlete.id)
        assert "ZONE CROSS-REFERENCE" in prompt
        assert "cross-reference" in prompt.lower()
```

### Update `_is_data_question` to exclude general knowledge

**File:** `apps/api/services/coaching/_prescriptions.py`  
**Location:** `_is_data_question` method, lines ~213-243

The current `definition_patterns` exclusion list doesn't cover general sports science questions. Add exclusions:

```python
general_knowledge_patterns = [
    "should i take", "how should i warm up", "warmup for",
    "warm up for", "carb load", "sodium bicarb", "bicarb",
    "caffeine before", "what should i eat before",
    "how to fuel", "supplement", "electrolyte",
    "stretching before", "foam roll",
    "ice bath", "cold plunge", "compression",
]
if any(p in ml for p in general_knowledge_patterns):
    return False
```

Add this block after the existing `definition_patterns` check and before the `data_keywords` return.

---

## Validation Checklist

After all changes, verify:

- [ ] `pytest apps/api/tests/test_coach_phase7_regression.py -v` — all green
- [ ] `pytest apps/api/tests/test_coach_phase7_retrieval.py -v` — all green
- [ ] `pytest apps/api/tests/ -k "coach" --tb=short` — no regressions
- [ ] System prompt does NOT contain "ALWAYS call get_weekly_volume first"
- [ ] System prompt DOES contain "GENERAL KNOWLEDGE RULE"
- [ ] System prompt DOES contain "VOICE DIRECTIVE"
- [ ] System prompt DOES contain "ZONE CROSS-REFERENCE"
- [ ] System prompt DOES contain "RACE-DAY MODE"
- [ ] `count_hedge_phrases` is importable from `_constants`
- [ ] `get_training_block_narrative` is in the tool list
- [ ] `classify_conversation_contract("I have a race today")` returns `race_day`
- [ ] `classify_conversation_contract("5:50 pace", context=[race thread])` returns `race_day`
- [ ] `_is_data_question("Should I take bicarb?")` returns `False`
- [ ] `_is_data_question("How far did I run last week?")` returns `True`
- [ ] `search_activities(name_contains="16x400")` finds "16 x 400 Workout"
- [ ] `_recent_relevant_workouts` returns interval sessions even with 8 recent easy runs
- [ ] `get_training_block_narrative` classifies "Morning Run" with 16x400m splits as `speed`

## Files Modified (Summary)

| File | Change |
|------|--------|
| `apps/api/services/coaching/_context.py` | System prompt: knowledge rule, voice directive, tool guidance, race-day mode, zone cross-reference |
| `apps/api/services/coaching/_constants.py` | Add `_HEDGE_PHRASES`, `count_hedge_phrases()`, hedge logging in `_check_response_quality` |
| `apps/api/services/coaching/_llm.py` | Relax user-message tool preamble; conditional `tool_choice` based on `_is_data_question` |
| `apps/api/services/coaching/_conversation_contract.py` | Add `RACE_DAY` contract type, detection regex, validation |
| `apps/api/services/coaching/_prescriptions.py` | Add general knowledge exclusions to `_is_data_question` |
| `apps/api/services/coaching/_tools.py` | Register `get_training_block_narrative` tool |
| `apps/api/services/coach_tools/activity.py` | Add `get_training_block_narrative` function |
| `apps/api/services/coach_tools/__init__.py` | Export `get_training_block_narrative` |
| `apps/api/services/coach_tools/race_strategy.py` | Add training block to race strategy packet |
| `apps/api/tests/test_coach_phase7_regression.py` | New test file for Phase 7 regression cases |

---

## 7G: Search Brittleness Fix (from agent diagnosis)

### Problem

`search_activities(name_contains="16x400")` returns 0. `search_activities(name_contains="16 x 400")` works. The `name_contains` filter in `activity_search.py` does a raw `ILIKE %needle%` match. Athletes and the coach both use natural variants — "16x400", "16 x 400", "400s", "16x400m" — and the search fails on spacing/plurals.

### File: `apps/api/services/activity_search.py`

**Location:** Lines 85-93 (the `name_contains` filter)

**Current code:**
```python
if params.name_contains:
    needle = f"%{params.name_contains.strip()}%"
    query = query.filter(
        or_(
            Activity.name.ilike(needle),
            Activity.athlete_title.ilike(needle),
            Activity.shape_sentence.ilike(needle),
        )
    )
```

**Replace with fuzzy-tolerant search:**
```python
if params.name_contains:
    raw = params.name_contains.strip()
    # Normalize common workout description variants:
    # "16x400" -> "16 x 400", "400s" -> "400", "16X400m" -> "16 x 400"
    import re as _re
    normalized = _re.sub(r'(\d+)\s*[xX]\s*(\d+)\s*m?\b', r'\1 x \2', raw)
    normalized = _re.sub(r'(\d+)s\b', r'\1', normalized)
    needle = f"%{normalized}%"
    # Also try the raw input in case it matches literally
    raw_needle = f"%{raw}%"
    query = query.filter(
        or_(
            Activity.name.ilike(needle),
            Activity.name.ilike(raw_needle),
            Activity.athlete_title.ilike(needle),
            Activity.athlete_title.ilike(raw_needle),
            Activity.shape_sentence.ilike(needle),
            Activity.shape_sentence.ilike(raw_needle),
        )
    )
```

This means "16x400", "16 x 400", "16X400m", and "400s" all normalize to patterns that match activity names like "16 x 400 Workout" or "Morning Run" (via shape_sentence which may contain rep descriptions).

### Test addition for `test_coach_phase7_regression.py`:

```python
class TestSearchNormalization:
    """7G: Search should find workouts with spacing/plural variants."""

    def test_normalize_16x400(self):
        import re
        raw = "16x400"
        normalized = re.sub(r'(\d+)\s*[xX]\s*(\d+)\s*m?\b', r'\1 x \2', raw)
        assert normalized == "16 x 400"

    def test_normalize_400s(self):
        import re
        raw = "400s"
        normalized = re.sub(r'(\d+)s\b', r'\1', raw)
        assert normalized == "400"

    def test_normalize_16X400m(self):
        import re
        raw = "16X400m"
        normalized = re.sub(r'(\d+)\s*[xX]\s*(\d+)\s*m?\b', r'\1 x \2', raw)
        assert normalized == "16 x 400"

    def test_search_finds_variant(self, db_session, test_athlete):
        from models import Activity
        from datetime import datetime
        db_session.add(Activity(
            athlete_id=test_athlete.id,
            sport="run",
            name="16 x 400 Workout",
            start_time=datetime.utcnow(),
            distance_m=8000,
            duration_s=2400,
        ))
        db_session.flush()

        from services.coach_tools.activity import search_activities
        result = search_activities(db_session, test_athlete.id, name_contains="16x400")
        assert result["ok"] is True
        assert result["data"]["match_count"] >= 1
```

---

## 7H: Race Packet Workout Cap Fix (from agent diagnosis)

### Problem

`_recent_relevant_workouts` in `race_strategy.py` has a hard `if len(rows) >= 6: break` at line 299. For a 5K race, distance matching is broad (0.8x to 4x the distance = 4km-25km), so the 6 slots fill with recent easy/moderate runs and the decisive interval session from 4 weeks ago gets crowded out.

### File: `apps/api/services/coach_tools/race_strategy.py`

**Location:** Lines 267-301 (`_recent_relevant_workouts`)

**Changes:**

1. Raise the cap from 6 to 15.
2. Prioritize quality sessions (intervals, tempo, races) over easy-distance matches.
3. Sort so key sessions appear first even if older.

**Replace the function:**
```python
def _recent_relevant_workouts(
    db: Session,
    athlete_id: UUID,
    *,
    distance_m: Optional[int],
    lookback_days: int,
) -> List[Dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    activities = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.sport == "run",
            Activity.start_time >= cutoff,
        )
        .order_by(Activity.start_time.desc().nullslast())
        .limit(120)
        .all()
    )
    quality_keywords = ("race", "tempo", "threshold", "interval", "repeat", "workout", "progression", "x 400", "x 800", "x 1000", "x 1200", "x 1600", "x mile")
    distance_keywords = ("5k", "10k", "mile")

    quality_rows: List[Dict[str, Any]] = []
    distance_rows: List[Dict[str, Any]] = []
    for activity in activities:
        label = f"{activity.name or ''} {activity.workout_type or ''}".lower()
        distance_ok = bool(
            distance_m
            and activity.distance_m
            and 0.8 * distance_m <= activity.distance_m <= max(distance_m * 4.0, distance_m + 5000)
        )
        keyword_ok = any(token in label for token in quality_keywords)
        dist_keyword_ok = any(token in label for token in distance_keywords)

        if keyword_ok:
            quality_rows.append(_activity_row(activity))
        elif distance_ok or dist_keyword_ok:
            distance_rows.append(_activity_row(activity))

    # Quality sessions first, then distance matches, cap at 15
    return (quality_rows + distance_rows)[:15]
```

This ensures the 16x400 from 4 weeks ago appears before a generic 6-mile easy run from yesterday.

---

## 7I: Thread-Aware Conversation Classification (from agent diagnosis)

### Problem

"I did 16 x 400" classified as `general`. "5:50 pace" classified as `general`. The conversation classifier looks at one message in isolation. When the thread is about a race, pace-target and workout-evidence messages should inherit the race context.

### File: `apps/api/services/coaching/_conversation_contract.py`

**Location:** `classify_conversation_contract` (lines ~49-126)

**Current signature takes only the message:**
```python
def classify_conversation_contract(message: str) -> ConversationContract:
```

**Change to accept optional conversation context:**
```python
def classify_conversation_contract(
    message: str,
    conversation_context: Optional[List[Dict[str, str]]] = None,
) -> ConversationContract:
```

**Add thread-context awareness at the top of the function body, before the existing regex checks:**

```python
# Check if the recent conversation thread is about a race
_thread_is_race = False
if conversation_context:
    recent_text = " ".join(
        (m.get("content") or "")[:200]
        for m in (conversation_context or [])[-6:]
    ).lower()
    _thread_is_race = bool(
        re.search(r"\b(race|racing|5k|10k|half|marathon)\b", recent_text)
        and re.search(r"\b(today|this morning|tonight|tomorrow|saturday|sunday)\b", recent_text)
    )
```

Then, in the fall-through logic (before returning `GENERAL`), add:

```python
# If thread is about a same-day race, promote race-context messages
if _thread_is_race:
    ml = message.lower()
    if re.search(r"\d+:\d+\s*pace|\d+\s*x\s*\d+|workout|interval|warmup|warm.?up|bicarb|supplement|fuel", ml):
        return ConversationContract(
            contract_type=ConversationContractType.RACE_DAY,
            outcome_target="execution_plan",
            required_behavior="answer in race-day execution context",
            max_words=300,
        )
```

**Also update the call site** in `apps/api/services/coaching/core.py` where `classify_conversation_contract` is called — pass `conversation_context` to it:

Find:
```python
classify_conversation_contract(message)
```
Replace with:
```python
classify_conversation_contract(message, conversation_context=conversation_context)
```

### Test:

```python
class TestThreadAwareClassification:
    """7I: Race-thread context promotes workout/pace messages from general."""

    def test_workout_in_race_thread_is_race_day(self):
        from services.coaching._conversation_contract import classify_conversation_contract
        context = [
            {"role": "user", "content": "I have a 5K race this morning"},
            {"role": "assistant", "content": "Let's get you ready for race day."},
        ]
        contract = classify_conversation_contract(
            "I did 16 x 400 faster than that",
            conversation_context=context,
        )
        assert contract.contract_type.value == "race_day"

    def test_pace_in_race_thread_is_race_day(self):
        from services.coaching._conversation_contract import classify_conversation_contract
        context = [
            {"role": "user", "content": "I have a 5K race this morning"},
            {"role": "assistant", "content": "What's your target pace?"},
        ]
        contract = classify_conversation_contract(
            "I'm going out at 5:50 pace",
            conversation_context=context,
        )
        assert contract.contract_type.value == "race_day"

    def test_workout_without_race_thread_is_general(self):
        from services.coaching._conversation_contract import classify_conversation_contract
        contract = classify_conversation_contract(
            "I did 16 x 400 yesterday",
            conversation_context=None,
        )
        assert contract.contract_type.value != "race_day"
```

---

## 7J: Training Block Tool — Structure-Aware (from agent diagnosis)

### Problem

The `get_training_block_narrative` in section 7D classifies energy systems from activity names and `workout_type`. But a workout named "Morning Run" that has 16 x 400m work splits gets classified as "aerobic." The tool should inspect `ActivitySplit` data when available.

### Enhancement to `get_training_block_narrative` in `apps/api/services/coach_tools/activity.py`

**Inside the for-loop over activities, after the name-based `energy_system` classification, add split-based override:**

```python
        # Override with split-based classification when available
        work_splits = (
            db.query(ActivitySplit)
            .filter(
                ActivitySplit.activity_id == a.id,
                ActivitySplit.lap_type == "work",
            )
            .all()
        )
        if work_splits:
            rep_count = len(work_splits)
            avg_rep_distance = (
                sum(float(s.distance or 0) for s in work_splits) / rep_count
                if rep_count > 0 else 0
            )
            if rep_count >= 8 and avg_rep_distance < 600:
                energy_system = "speed"
            elif rep_count >= 4 and avg_rep_distance < 1200:
                energy_system = "speed"
            elif rep_count >= 2 and 1200 <= avg_rep_distance <= 2500:
                energy_system = "speed_endurance"
            elif rep_count >= 2 and avg_rep_distance > 2500:
                energy_system = "threshold"
```

**Also add the `ActivitySplit` import at the top of the function:**
```python
from models import ActivitySplit
```

**Update the `workout_types_seen` set and `common_missing` to include `speed_endurance`.**

---

## 7K: DB-Backed Retrieval Eval Scenarios (from agent diagnosis)

### Problem

The Phase 7 contract tests check prompt text, classification, and hedge detection. They don't test whether the retrieval pipeline actually surfaces the correct workout and produces the right data for the coach.

### File: `apps/api/tests/test_coach_phase7_retrieval.py` (new file)

This seeds DB fixtures mimicking the real Mar 28 scenario and tests that the tools return the correct data.

```python
"""
Phase 7 retrieval tests — verify that coach tools surface key workouts
when asked about them in the ways athletes actually ask.

DB-backed using db_session + test_athlete fixtures.
"""
import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from models import Activity, ActivitySplit


@pytest.fixture
def interval_workout(db_session, test_athlete):
    """Create a 16x400 interval session from ~4 weeks ago."""
    activity = Activity(
        athlete_id=test_athlete.id,
        sport="run",
        name="Morning Run",  # deliberately generic name
        workout_type="interval",
        start_time=datetime.utcnow() - timedelta(days=28),
        distance_m=12700,
        duration_s=3600,
        avg_hr=162,
        max_hr=178,
    )
    db_session.add(activity)
    db_session.flush()

    # Add 16 work splits (~400m each) + rest splits
    for i in range(16):
        db_session.add(ActivitySplit(
            activity_id=activity.id,
            split_number=i * 2,
            distance=400,
            elapsed_time=92,  # ~5:45/mi pace
            lap_type="work",
            interval_number=i + 1,
            average_heartrate=170,
        ))
        db_session.add(ActivitySplit(
            activity_id=activity.id,
            split_number=i * 2 + 1,
            distance=100,
            elapsed_time=90,  # 90s rest
            lap_type="rest",
        ))
    db_session.flush()
    return activity


@pytest.fixture
def recent_easy_runs(db_session, test_athlete):
    """Create 8 easy runs in the last 2 weeks to crowd the race packet."""
    runs = []
    for i in range(8):
        a = Activity(
            athlete_id=test_athlete.id,
            sport="run",
            name=f"Easy Run {i+1}",
            workout_type="easy",
            start_time=datetime.utcnow() - timedelta(days=i + 1),
            distance_m=8000 + i * 500,
            duration_s=2700 + i * 200,
        )
        db_session.add(a)
        runs.append(a)
    db_session.flush()
    return runs


class TestRacePacketSurfacesKeyWorkouts:
    """The race packet must not drop a 16x400 session just because
    8 recent easy runs fill the cap first."""

    def test_interval_session_in_race_packet(
        self, db_session, test_athlete, interval_workout, recent_easy_runs
    ):
        from services.coach_tools.race_strategy import _recent_relevant_workouts
        workouts = _recent_relevant_workouts(
            db_session,
            test_athlete.id,
            distance_m=5000,
            lookback_days=60,
        )
        workout_ids = [w["activity_id"] for w in workouts]
        assert str(interval_workout.id) in workout_ids, (
            "The 16x400 interval session was crowded out of the race packet"
        )


class TestSearchFindsVariants:
    """search_activities must find workouts regardless of spacing variants."""

    def test_no_space_variant(self, db_session, test_athlete):
        db_session.add(Activity(
            athlete_id=test_athlete.id,
            sport="run",
            name="16 x 400 Intervals",
            start_time=datetime.utcnow() - timedelta(days=5),
            distance_m=8000,
            duration_s=2400,
        ))
        db_session.flush()

        from services.coach_tools.activity import search_activities
        result = search_activities(db_session, test_athlete.id, name_contains="16x400")
        assert result["data"]["match_count"] >= 1

    def test_plural_variant(self, db_session, test_athlete):
        db_session.add(Activity(
            athlete_id=test_athlete.id,
            sport="run",
            name="400 repeats",
            start_time=datetime.utcnow() - timedelta(days=5),
            distance_m=8000,
            duration_s=2400,
        ))
        db_session.flush()

        from services.coach_tools.activity import search_activities
        result = search_activities(db_session, test_athlete.id, name_contains="400s")
        assert result["data"]["match_count"] >= 1


class TestTrainingBlockUseSplits:
    """get_training_block_narrative should classify from splits, not just name."""

    def test_generic_name_with_interval_splits(
        self, db_session, test_athlete, interval_workout
    ):
        from services.coach_tools.activity import get_training_block_narrative
        result = get_training_block_narrative(db_session, test_athlete.id, weeks=6)
        assert result["ok"] is True
        assert "speed" in result["data"]["energy_systems_trained"], (
            "A workout with 16 x 400m work splits should be classified as speed, "
            "even if named 'Morning Run'"
        )
```

---

## Updated Files Modified (Full Summary)

| File | Change |
|------|--------|
| `apps/api/services/coaching/_context.py` | System prompt: knowledge rule, voice directive, tool guidance, race-day mode, zone cross-reference |
| `apps/api/services/coaching/_constants.py` | Add `_HEDGE_PHRASES`, `count_hedge_phrases()`, hedge logging in `_check_response_quality` |
| `apps/api/services/coaching/_llm.py` | Relax user-message tool preamble; conditional `tool_choice` based on `_is_data_question` |
| `apps/api/services/coaching/_conversation_contract.py` | Add `RACE_DAY` contract type, detection regex, validation, **thread-aware classification** |
| `apps/api/services/coaching/_prescriptions.py` | Add general knowledge exclusions to `_is_data_question` |
| `apps/api/services/coaching/_tools.py` | Register `get_training_block_narrative` tool |
| `apps/api/services/coaching/core.py` | Pass `conversation_context` to `classify_conversation_contract` |
| `apps/api/services/coach_tools/activity.py` | Add `get_training_block_narrative` function (**with split-based classification**) |
| `apps/api/services/coach_tools/__init__.py` | Export `get_training_block_narrative` |
| `apps/api/services/coach_tools/race_strategy.py` | Add training block to race strategy packet; **fix workout cap from 6→15, prioritize quality sessions** |
| `apps/api/services/activity_search.py` | **Fuzzy-normalize workout name variants** (16x400 → 16 x 400, 400s → 400) |
| `apps/api/tests/test_coach_phase7_regression.py` | Contract tests for 7A-7F + **search normalization tests** |
| `apps/api/tests/test_coach_phase7_retrieval.py` | **NEW — DB-backed retrieval tests** for race packet, search variants, split-based classification |

## Do NOT Change

- `_execute_opus_tool` dispatch order (only add the new case)
- `query_opus` fallback path (Sonnet keeps its current behavior)
- `AthleteFact` extraction pipeline (async, untouched)
- Frontend coach page (backend-only changes)
- Any existing passing test assertions

## After Build

- Run full coach test suite
- Update `docs/wiki/coach-architecture.md` with Phase 7 changes
- Update `docs/COACH_IMPROVEMENT_PLAN.md` Phase 7 status
