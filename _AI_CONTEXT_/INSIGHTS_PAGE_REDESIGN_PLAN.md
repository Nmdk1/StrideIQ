# Insights Page Redesign Plan

**Created:** January 10, 2026  
**Updated:** January 10, 2026 (with founder feedback)  
**Status:** APPROVED WITH REVISIONS  
**Purpose:** Transform the Insights page from a generic query tool to the "brain" of the closed-loop coaching system

---

## Founder Decisions (January 10, 2026)

| Question | Decision |
|----------|----------|
| **Section priority** | Quality over order. Highest quality code, robustness, scalability, beautiful low-friction UX. |
| **Insight generation** | On sync (not daily batch). Generate when activity syncs. |
| **Where insights appear** | Dashboard or Insights page. **NOT calendar** — keep calendar uncluttered for plan/training/work/notes only. |
| **Premium gating** | Anything that runs up costs = premium. Protect profitability. |
| **Explore section** | Remove from Insights page. Query gateway should start from **Compare page or Activities page** instead. |

---

## The Problem

The current Insights page is:
- **Query-driven**: User must click "Run Insight" manually
- **Generic**: Same templates for everyone
- **Disconnected**: No awareness of training plan, phase, or goals
- **Surface-level**: Shows "what" but never "why"
- **Not learning**: No memory of what worked for this athlete

This is exactly what Strava/Garmin already do. It's not a moat.

---

## The Vision

> **The Insights page should be the "Brain View" of your training — proactive, personalized, and causally aware. It answers the questions you should be asking but haven't thought to ask yet.**

It should:
1. **Push insights to you** (not wait for queries)
2. **Be personalized** (based on YOUR data, YOUR patterns)
3. **Answer "WHY"** (causal attribution — the moat)
4. **Connect to your goals** (race-aware, phase-aware)
5. **Learn continuously** (compound over time)

---

## Proposed Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           INSIGHTS PAGE                                      │
│                    "What's Your Training Telling You?"                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  🔥 ACTIVE INSIGHTS (Auto-generated, ranked by importance)              │ │
│  │  ─────────────────────────────────────────────────────────────────────  │ │
│  │  These insights were generated TODAY based on your recent training      │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  📊 BUILD STATUS (Phase-aware dashboard)                                │ │
│  │  ─────────────────────────────────────────────────────────────────────  │ │
│  │  KPIs, trajectory, readiness — all contextualized to your goal         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  🧠 ATHLETE INTELLIGENCE (What we've learned about YOU)                 │ │
│  │  ─────────────────────────────────────────────────────────────────────  │ │
│  │  What works, what doesn't, patterns, injury signals                    │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

NOTE: Explore/Query section REMOVED from Insights page.
Query functionality moves to Compare page and Activities page as natural entry points.
```
```

---

## Section 1: Active Insights (THE MOAT)

**Concept:** Auto-generated insights ranked by importance, refreshed daily.

**Key Principle:** "Here's what your training is telling you TODAY."

### Critical Definition: Efficiency Factor (EF)

**EF must be clear, meaningful, and actionable.**

#### Current Implementation:
```
EF = Normalized Grade Pace (seconds/mi) / Heart Rate (as % of max HR)
```

- **Lower EF = More Efficient** (faster pace at same HR, or lower HR at same pace)
- **Filters out first 6 minutes** (cardio lag — O₂ debt skews early data)
- **Uses Grade-Adjusted Pace (GAP)** when elevation data available
- **Calculates decoupling** (first half vs second half EF drift)

#### What EF Actually Tells You:

| EF Change | Meaning | Actionable Insight |
|-----------|---------|-------------------|
| EF drops over weeks | Same pace feels easier (lower HR) OR same HR produces faster pace | "Your aerobic system is adapting. Base building is working." |
| EF rises during a run (decoupling >8%) | Cardiac drift — less efficient in second half | "Durability issue. Consider longer easy runs or better fueling." |
| EF stable during a run (<5% decoupling) | Excellent aerobic durability | "Strong endurance. Ready for longer efforts." |
| EF higher than usual for same workout type | Fatigue, poor recovery, or external stress | "Recovery compromised. Check sleep, stress, or illness." |

#### How We'll Display It:
- **Never show raw EF numbers to athletes** (meaningless without context)
- **Always show DELTA or COMPARISON**: "6 bpm lower HR at same pace" or "Top 15% of your easy runs"
- **Trend arrows**: ↑ improving, ↓ declining, → stable
- **Decoupling traffic light**: 🟢 <5%, 🟡 5-8%, 🔴 >8%

---

### Insight Types (Clarified)

| Type | Trigger | Example | Clarification |
|------|---------|---------|---------------|
| **Causal Attribution** | EF change detected | "Your easy pace efficiency improved 8% this month. Data suggests: sleep improved (+45 min avg), threshold volume up (+3 mi/week)." | **EF = lower HR at same pace.** Attribution shows correlation bars, not causation claims. |
| **Pattern Detection** | Recurring behavior | "You've run easy days faster than prescribed 4/5 weeks. Average: 8:05/mi vs target 8:30-9:00. HR stayed elevated (avg 142 vs expected 125-135)." | **"Too fast" = pace AND HR context.** If HR adapted (stayed low), it's not a problem. If HR stayed elevated, recovery is compromised. |
| **Trend Alert** | Significant trend identified | "Your HR at 7:30 pace has dropped 4 bpm over 6 weeks (148 → 144 avg). Your aerobic base is building." | Always shows actual HR numbers, not just "improved." |
| **Fatigue Warning** | Cumulative fatigue high | "Your last 3 workouts show declining EF at same effort. Pace was consistent but HR 6-8 bpm higher than usual." | Specific numbers, not vague warnings. |
| **Breakthrough Detected** | Performance inflection | "Thursday's T-session was your best in 8 weeks. You held 6:38/mi (vs 6:45 target) at same HR (162)." | ✅ Clear — founder approved. |
| **Comparison Insight** | vs-similar analysis | "Yesterday's 10-miler was in your top 10% for EF at that distance. Sleep was 8.2 hrs (vs 6.8 avg). Weather was 52°F (vs 68°F avg)." | Shows what was different. |
| **Phase-Specific** | Build phase context | "You're in Build 2, Week 10. T-block progression on track. Ready for Sunday's first MP long run." | Contextual to plan. |
| **Injury Risk Signal** | **N=1 pattern match** | "Your current pattern (volume 62 mpw + intervals introduced Week 9) matches your November 2025 injury pattern. That was a one-off, but worth noting." | **Always N=1 first.** Only reference population patterns if no individual history. Clearly states if it's a recurring pattern vs one-off. |

### Visual Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  🔥 ACTIVE INSIGHTS                                          Updated today  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  ⚡ BREAKTHROUGH                                             Priority: 1 │  │
│  │  ──────────────────────────────────────────────────────────────────── │  │
│  │  Your easy pace efficiency is at an all-time high.                    │  │
│  │                                                                        │  │
│  │  📊 The data:                                                          │  │
│  │  • EF at 8:30/mi: 1.62 (was 1.48 six weeks ago)                       │  │
│  │  • Same pace, 6 bpm lower HR                                          │  │
│  │                                                                        │  │
│  │  🔍 What contributed (causal analysis):                                │  │
│  │  ┌────────────────────────────────────────────────────────────────┐   │  │
│  │  │ ████████████████████  Sleep quality (+45 min avg)      HIGH    │   │  │
│  │  │ ████████████████      Threshold volume (+3 mi/wk)      MOD     │   │  │
│  │  │ ████████████          Consistency (no missed days)     MOD     │   │  │
│  │  │ ████████              Body weight (-2 lbs)             LOW     │   │  │
│  │  └────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                        │  │
│  │  💡 Bottom line: Your base building is working. Keep sleeping well.   │  │
│  │                                                                        │  │
│  │  [View Details]  [Dismiss]  [Save to Profile]                         │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  ⚠️ PATTERN ALERT                                            Priority: 2 │  │
│  │  ──────────────────────────────────────────────────────────────────── │  │
│  │  You ran easy days too fast again this week.                          │  │
│  │                                                                        │  │
│  │  • Target: 8:30-9:00/mi  |  Actual: 8:05/mi average                   │  │
│  │  • This pattern appeared in 4 of the last 5 weeks                     │  │
│  │                                                                        │  │
│  │  🧠 From your history: When easy days are too fast, your T-sessions   │  │
│  │     are less effective (avg 3% lower EF). Let easy be easy.           │  │
│  │                                                                        │  │
│  │  [Acknowledge]  [Dismiss]                                             │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  📈 TREND                                                     Priority: 3 │  │
│  │  ──────────────────────────────────────────────────────────────────── │  │
│  │  Your threshold pace is improving.                                    │  │
│  │                                                                        │  │
│  │  T pace 6 weeks ago: 6:52/mi @ 165 bpm                                │  │
│  │  T pace now: 6:38/mi @ 163 bpm                                        │  │
│  │                                                                        │  │
│  │  Trajectory: On pace for 6:30/mi T by race week.                      │  │
│  │                                                                        │  │
│  │  [View T-block Progression]                                           │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Generation Logic

Insights are generated by:

1. **Attribution Engine** (`services/attribution_engine.py`) — Already exists, calculates input correlations
2. **Pattern Recognition** (`services/pattern_recognition.py`) — Already exists, detects trends
3. **Contextual Comparison** (`services/contextual_comparison.py`) — Already exists, compares similar runs
4. **Run Analysis Engine** (`services/run_analysis_engine.py`) — Already exists, contextualizes workouts
5. **NEW: Insight Aggregator** — Collects all signals, ranks by importance, de-duplicates, and surfaces top 5-10

---

## Section 2: Build Status Dashboard

**Concept:** If athlete has an active training plan, show phase-aware KPIs and trajectory.

**Key Principle:** "Where are you in your journey, and are you on track?"

### Visual Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  📊 BUILD STATUS                                                            │
│  Tobacco Road Marathon  •  March 14, 2026  •  63 days                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Week 10 of 18  •  Phase: Build 2 (MP Introduction)                         │
│  ████████████████░░░░░░░░  56%                                              │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  KEY PERFORMANCE INDICATORS                                             │ │
│  │  ─────────────────────────────────────────────────────────────────────  │ │
│  │                                                                          │ │
│  │   Threshold Pace           Easy Efficiency         Long Run Max         │ │
│  │   ┌─────────────┐          ┌─────────────┐         ┌─────────────┐      │ │
│  │   │   6:38/mi   │          │    1.62     │         │   18 mi     │      │ │
│  │   │   ↑ 14s     │          │    ↑ 9%     │         │   ↑ 4 mi    │      │ │
│  │   │ from build  │          │ from build  │         │ from build  │      │ │
│  │   │    start    │          │    start    │         │    start    │      │ │
│  │   └─────────────┘          └─────────────┘         └─────────────┘      │ │
│  │                                                                          │ │
│  │   MP Capability            Volume Trend            Fatigue State        │ │
│  │   ┌─────────────┐          ┌─────────────┐         ┌─────────────┐      │ │
│  │   │    8 mi     │          │   52 mpw    │         │  MODERATE   │      │ │
│  │   │ continuous  │          │   avg last  │         │  (normal    │      │ │
│  │   │  @ MP       │          │   4 weeks   │         │  for phase) │      │ │
│  │   └─────────────┘          └─────────────┘         └─────────────┘      │ │
│  │                                                                          │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  🎯 RACE PROJECTION                                                      │ │
│  │  ─────────────────────────────────────────────────────────────────────  │ │
│  │                                                                          │ │
│  │   Goal: 3:15:00                                                          │ │
│  │   Current trajectory: 3:12 - 3:18  ✓ ON TRACK                           │ │
│  │   Confidence: HIGH (based on T-pace progression + long run performance) │ │
│  │                                                                          │ │
│  │   ┌─────────────────────────────────────────────────────────────────┐   │ │
│  │   │ Week 1 ─────── Week 10 ────────────────────────── Race Day     │   │ │
│  │   │   •             ★ (you)                              🏁        │   │ │
│  │   │   ───────────────●────────────────────────────────────         │   │ │
│  │   │                  ↓                                             │   │ │
│  │   │            Current fitness                                     │   │ │
│  │   └─────────────────────────────────────────────────────────────────┘   │ │
│  │                                                                          │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  📅 THIS WEEK'S FOCUS                                                    │ │
│  │  ─────────────────────────────────────────────────────────────────────  │ │
│  │                                                                          │ │
│  │  "First MP introduction in the long run. Sunday is the key session —   │ │
│  │   20 miles with 8 at MP. The T-work this week sets you up. Nail        │ │
│  │   Thursday, then let the legs recover for Sunday."                     │ │
│  │                                                                          │ │
│  │  Key Session: Sunday Long Run (20mi w/ 8 @ MP)                          │ │
│  │                                                                          │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Section 3: Athlete Intelligence (The Moat Visualized)

**Concept:** Show what the system has learned about THIS athlete over time.

**Key Principle:** "We're not guessing. This is what YOUR data tells us about YOU."

### Visual Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  🧠 ATHLETE INTELLIGENCE                                                     │
│  Continuously learning from your training                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────┐  ┌──────────────────────────────────┐ │
│  │  ✅ WHAT WORKS FOR YOU           │  │  ❌ WHAT DOESN'T WORK            │ │
│  │  ─────────────────────────────── │  │  ─────────────────────────────── │ │
│  │                                  │  │                                  │ │
│  │  • High volume (55+ mpw)         │  │  • Intervals in mid-build        │ │
│  │    → Correlates with your PRs    │  │    → 100% injury correlation     │ │
│  │                                  │  │                                  │ │
│  │  • T-block progression           │  │  • Back-to-back hard days        │ │
│  │    → 14s T-pace improvement      │  │    → EF drops 8% following week  │ │
│  │                                  │  │                                  │ │
│  │  • 8+ hours sleep                │  │  • Volume + intensity spikes     │ │
│  │    → +12% next-day efficiency    │  │    → Fatigue cascades            │ │
│  │                                  │  │                                  │ │
│  │  • Hill strides in base          │  │                                  │ │
│  │    → Safe speed, no injury       │  │                                  │ │
│  │                                  │  │                                  │ │
│  └──────────────────────────────────┘  └──────────────────────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  📊 YOUR PATTERNS                                                        │ │
│  │  ─────────────────────────────────────────────────────────────────────  │ │
│  │                                                                          │ │
│  │  Sleep Impact on Next-Day Performance:                                  │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │ │
│  │  │  < 6 hrs     ████                        -8% EF                 │    │ │
│  │  │  6-7 hrs     ████████                    baseline               │    │ │
│  │  │  7-8 hrs     ████████████                +5% EF                 │    │ │
│  │  │  8+ hrs      ████████████████            +12% EF                │    │ │
│  │  └─────────────────────────────────────────────────────────────────┘    │ │
│  │                                                                          │ │
│  │  Best Workout Day: Thursday (78% of quality sessions succeed)           │ │
│  │  Best Long Run Conditions: 45-55°F, overcast                            │ │
│  │  Optimal Weekly Pattern: Hard Tue/Thu, Long Sun, Rest Mon               │ │
│  │                                                                          │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  ⚠️ INJURY RISK PATTERNS                                                 │ │
│  │  ─────────────────────────────────────────────────────────────────────  │ │
│  │                                                                          │ │
│  │  Your injury history shows:                                             │ │
│  │  • Intervals introduced mid-build (high cumulative fatigue) → injury   │ │
│  │  • Summer intervals (low fatigue, base phase) → no injury              │ │
│  │                                                                          │ │
│  │  Current risk: LOW                                                      │ │
│  │  You're in Build 2, no intervals planned. Staying safe.                 │ │
│  │                                                                          │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  🏆 CAREER PROGRESSION                                                   │ │
│  │  ─────────────────────────────────────────────────────────────────────  │ │
│  │                                                                          │ │
│  │  Half Marathon:  1:34:40 (2024) → 1:27:40 (2025)  •  7 min improvement  │ │
│  │  10K:            42:18 (2024) → 38:45 (2025)      •  3.5 min improve    │ │
│  │  Marathon:       —                                 •  First attempt!     │ │
│  │                                                                          │ │
│  │  Trend: Getting faster every build. Age is not limiting you.           │ │
│  │                                                                          │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Section 4: Query Functionality (MOVED)

**Decision:** Remove Explore section from Insights page entirely.

**Where queries live instead:**
- **Compare Page** — Natural place to ask "How does this run compare to..."
- **Activities Page** — Natural place to filter, search, and analyze activity history

The Insights page becomes **purely proactive** — we tell you what matters, you don't have to ask.

---

## Premium Gating Strategy

**Principle:** Anything that runs up costs = premium. Profitability is non-negotiable.

| Feature | Tier | Cost Driver |
|---------|------|-------------|
| **Basic EF trend** | Free | Low compute |
| **Workout distribution** | Free | Low compute |
| **Personal records** | Free | Low compute |
| **Causal Attribution** | Premium | GPT for language generation |
| **Pattern Detection (advanced)** | Premium | Historical analysis compute |
| **Injury Risk Signals** | Premium | Complex N=1 analysis |
| **Build Status Dashboard** | Premium | Requires active plan |
| **Athlete Intelligence Bank** | Premium | Continuous learning storage |
| **GPT Coach** | Premium | OpenAI API costs |

**Cost Control:**
- Cache insights aggressively (don't recalculate unless new data)
- Generate insights on-sync (batch, not real-time)
- Limit GPT calls to insight language generation, not every interaction
- Store generated insight text, don't regenerate on each page load

---

## Implementation Plan

### Phase 1: Backend Infrastructure (Days 1-2)

```python
# New service: InsightAggregator
class InsightAggregator:
    """
    Collects signals from all analysis engines and produces ranked insights.
    """
    
    def generate_daily_insights(self, athlete_id: UUID, db: Session) -> List[Insight]:
        """
        Called daily (or on-demand) to generate fresh insights.
        
        Gathers from:
        - AttributionEngine.get_recent_attributions()
        - PatternRecognition.get_active_patterns()
        - ContextualComparison.get_notable_comparisons()
        - RunAnalysisEngine.get_pending_insights()
        
        Then:
        - Ranks by importance
        - De-duplicates similar insights
        - Limits to top 10
        - Stores in CalendarInsight table (or new Insight table)
        """
        pass
    
    def get_build_status(self, athlete_id: UUID, db: Session) -> BuildStatus:
        """
        Returns KPIs, trajectory, and phase context for active build.
        """
        pass
    
    def get_athlete_intelligence(self, athlete_id: UUID, db: Session) -> AthleteIntelligence:
        """
        Returns banked learnings: what works, what doesn't, patterns, injury history.
        """
        pass
```

### Phase 2: API Endpoints (Day 2)

```python
# New endpoints
GET /v1/insights/active
    # Returns ranked active insights for current user
    
GET /v1/insights/build-status
    # Returns build KPIs, trajectory, phase focus (if active plan)
    
GET /v1/insights/intelligence
    # Returns athlete intelligence bank summary
    
POST /v1/insights/{id}/dismiss
    # Dismiss an insight
    
POST /v1/insights/{id}/save
    # Save insight to athlete profile (bank it)
```

### Phase 3: Frontend Redesign (Days 3-4)

1. **Replace** current query-first layout with section-based layout
2. **Active Insights section** — Cards with causal attribution visualizations
3. **Build Status section** — KPI cards + trajectory chart (only if active plan)
4. **Intelligence section** — What works / what doesn't + patterns
5. **Explore section** — Existing templates (collapsed by default)

### Phase 4: Insight Generation Pipeline (Day 5)

1. **Trigger:** Daily job + on-activity-sync
2. **Process:** Run all engines, aggregate, rank, store
3. **Display:** Insights appear on both Insights page AND Calendar day cells

---

## What Makes This The Moat

| Competitor | Their Insights | Our Insights |
|------------|----------------|--------------|
| Strava | "You ran 10 miles" | "Your 10-miler was your best EF in 6 weeks. Sleep was up, consistency was perfect. This is working." |
| Garmin | "Training status: Productive" | "Your threshold pace improved 14s since build start. Data suggests T-block progression + volume consistency are the drivers." |
| TrainingPeaks | "TSB: -15, Fatigued" | "Cumulative fatigue is moderate (expected for Build 2). Your pattern shows intervals under this fatigue cause injury — we're keeping them out." |
| Generic Coach | "Good week, keep it up" | "You ran easy days too fast 4/5 weeks. Your data shows this correlates with weaker T-sessions. Here's the pattern." |

**The difference:** We answer "WHY" with data-backed causal attribution and personalized pattern recognition. We learn what works for YOU, not what works for "runners."

---

## Success Metrics

1. **Engagement:** Time on Insights page > 2 minutes (vs current ~30s)
2. **Action Rate:** >30% of insights are "Saved" or acted upon
3. **Retention Signal:** Users with active insights have higher weekly return rate
4. **Differentiation:** In user interviews, "This told me something I didn't know" score >4/5

---

## Dependencies

This redesign requires these systems to be working:

| System | Status | Notes |
|--------|--------|-------|
| Attribution Engine | ✅ Exists | Needs to expose ranked attributions |
| Pattern Recognition | ✅ Exists | Needs to expose active patterns |
| Contextual Comparison | ✅ Exists | Needs to flag notable comparisons |
| Build Tracker | ⚠️ Partial | Need KPI calculation logic |
| Athlete Intelligence Bank | ⚠️ Partial | Need persistence + query layer |
| CalendarInsight model | ✅ Exists | Use for storage |

---

## Timeline

| Day | Deliverable |
|-----|-------------|
| 1 | InsightAggregator service + ranking logic |
| 2 | API endpoints + build status calculation |
| 3 | Frontend: Active Insights section with causal viz |
| 4 | Frontend: Build Status + Intelligence sections |
| 5 | Integration: Daily generation job + on-sync trigger |
| 6 | Polish + testing |

**Total: ~1 week of focused development**

---

## Confirmed Decisions

| Question | Decision |
|----------|----------|
| **Section priority** | Quality over order. Implement with highest quality code, robustness, scalability, beautiful low-friction UX. |
| **Generation frequency** | ✅ On sync. Generate when activity syncs. |
| **Persistence** | Insights stay active until dismissed or superseded by newer insight of same type. |
| **Where insights appear** | ✅ Dashboard or Insights page. **NOT calendar** — calendar stays clean. |
| **Premium gating** | ✅ Anything that runs up costs = premium. See Premium Gating Strategy section. |
| **Explore section** | ✅ Removed. Query gateway moves to Compare and Activities pages. |

---

## Summary

**Current state:** Generic query tool that shows "what" happened.

**Proposed state:** Proactive intelligence dashboard that:
- Automatically surfaces personalized insights
- Answers "WHY" with causal attribution (the moat)
- Shows build progress and trajectory
- Displays banked learnings (what works for YOU)
- Learns continuously from every workout

This transforms the Insights page from "nice to have" to "the reason I pay for StrideIQ."

---

*Proposal ready for review*  
*Performance Focused Coaching*
