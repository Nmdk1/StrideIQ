# Progress Page — Product & UX Spec v1

**Author:** Founder + advisors
**Date:** March 2, 2026
**Status:** Spec — not yet built
**Prereads:** `docs/PRODUCT_MANIFESTO.md`, `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md`, competitive analysis (Runalyze, Runna, TrainingPeaks, Athletica)

---

## Why This Page Matters

The progress page is where the moat becomes visible. Every other surface in the
product — the home briefing, the coach chat, the Runtoon — shows intelligence
in the moment. The progress page is where the athlete watches the system
learning them over time. It is the proof that N=1 is real and not a marketing
claim.

Every competitor either shows raw data (Runalyze), charts waiting for a human
coach to interpret (TrainingPeaks), traffic light readiness indicators
(Athletica), or plan adherence metrics (Runna). None of them combine visuals
that catch the eye with narrative that teaches the athlete to read those
visuals — for their own body. This page is immediately differentiating if
executed correctly.

This is also the page that converts a curious free user into a paying subscriber
who stays.

---

## The Design Principle (from `DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md`)

**Visual First, Narrative Bridge, Earned Fluency.**

Every section follows the same pattern:

1. **Visual catches the eye.** A chart, a sparkline, a gauge. Not text in a
   rectangle. Something the eye is drawn to before the brain engages.
2. **Wonder forms.** "What does this mean?" The visual creates the question.
3. **The narrative answers.** Below the visual — not beside it, not instead of
   it — the system speaks. Coach voice. Specific numbers. The narrative answers
   the question the visual just created.
4. **Understanding deepens.** The athlete returns to the visual with new eyes.
   The narrative reframed what they're looking at.

**Within the narrative:** interpretation leads, metrics follow. The coach voice
arrives first. Numbers arrive as evidence for what the coach already said. The
moment a narrative opens with a raw number instead of a sentence that means
something, it becomes TrainingPeaks.

**A section without a visual anchor is a text wall.** A visual without a
narrative bridge is a pretty chart nobody learns from. Both are required.

**What this page actually is:** Synthesis as an interface. Not better charts.
Not better text. Three layers of reasoning that no competitor has combined:

1. **Visuals are the first layer of reasoning** — they are not decoration.
   They show the shape of what happened so the eye can process it before the
   brain engages.
2. **Narrative is the second layer that resolves ambiguity** — it is not
   summary. It answers the question the visual created and teaches the athlete
   to read their own data.
3. **Action is the third layer** — every block ends in an athlete decision.
   Understanding without agency is a lecture. The athlete always decides.

**The rejection test:** If a section looks like something from 2018 analytics
SaaS, reject it. If a section makes a runner immediately understand and
decide, ship it.

---

## Page Structure — Five Acts

The page reads as one continuous scroll, one story arc. Not cards. Not a grid.
A flowing document with visual punctuation. Each act has a visual anchor and a
narrative bridge.

---

### Act 1: The Verdict

**Visual anchor:** A compact fitness arc — an 8-week sparkline of the athlete's
combined fitness trajectory (CTL-based or composite). One glanceable line that
answers "Am I getting better?" before the brain engages. The line rises, falls,
or plateaus. Color-coded: rising = emerald, plateau = amber, declining = red.
Current position marked with a dot. Simple. Immediate.

**Narrative bridge:** One or two sentences below the sparkline. Coach voice.
Specific to this athlete, this week, this moment. The narrative explains what
the arc means right now.

**Example:**

> [Sparkline: fitness arc trending up over 8 weeks, current dot at peak]
>
> You're carrying solid fitness into race week, but recovery lagged after
> Saturday's marathon-pace session. The taper is working — your body just
> needs you to trust it for 13 more days.

**Rules:**
- The sparkline renders from deterministic data (CTL history) — no LLM needed
- The narrative must reference at least one specific recent event
- Must NOT be generic ("You're doing well" / "Keep it up")
- Must include temporal context (race countdown, training phase, week number)
- Max 3 sentences
- Grounded in data — every claim traceable to a specific metric

**JSON contract:**

```json
"verdict": {
  "sparkline_data": [38.2, 39.1, 41.0, 42.8, 44.5, 46.1, 47.3, 48.0],
  "sparkline_direction": "rising",
  "current_value": 48.0,
  "text": "string (required)",
  "grounding": ["CTL 48.0", "TSB +0.7", "Saturday MP run 13.1mi @ 7:12/mi"],
  "confidence": "high"
}
```

---

### Act 2: Progress Chapters

2-4 chapters. Each chapter is **one visual + one coached interpretation**.
The visual catches the eye. The narrative below it teaches the athlete what
they're looking at.

**Visual anchors by chapter topic:**

| Topic | Visual |
|-------|--------|
| Volume trajectory | Mini bar chart — 6-8 weeks of weekly mileage, current week highlighted |
| Efficiency trend | Sparkline with trend arrow — efficiency over last 90 days |
| Recovery signals | Compact health strip — sleep hours, HRV, resting HR as small indicators with directional arrows |
| Training load | Mini form gauge — TSB position on a scale from "fatigued" to "fresh" |
| Consistency | Completion ring — % of planned workouts completed, filled arc |
| Wellness trend | Small dot plot — motivation/soreness over last 14 days |
| Personal best | Highlighted stat — the PB distance + time with a "NEW" badge |
| Injury risk | Amber/green indicator — simple status dot with label |

**Narrative structure per chapter:**

1. **Observation** — what the visual is showing (coach voice, 1-2 sentences)
2. **Evidence** — 2-3 compact metrics, styled as supporting data (smaller, muted)
3. **Interpretation** — why it matters for this specific athlete (1-2 sentences)
4. **Action** — what to do about it (1 sentence, athlete-controlled)

Chapters are ordered by relevance to the athlete's current situation. A runner
in taper sees readiness chapters first. A runner in base building sees volume
chapters first. The ordering is dynamic, not hardcoded.

**Example chapter:**

> [Mini bar chart: 8 weeks of volume — 45, 48, 52, 56, 63, 55, 42, 35]
>
> **Your taper is on track**
>
> Volume dropped from 63 miles to 35 miles over two weeks — a 44% reduction.
> Your body is absorbing the work: form has risen from -17 to +0.7.
>
> *63mi → 35mi (−44%) | Form: −17 → +0.7 | Injury risk: low*
>
> This is exactly the pattern your body has shown before a good race block.
> The fitness is banked. The fatigue is clearing.
>
> **Keep the remaining runs genuinely easy.** No tempo touches. Let the form
> number keep climbing toward +10 by race morning.

**Rules:**
- Every chapter has a visual anchor — no text-only chapters
- The visual is deterministic (from real data), not LLM-generated
- The narrative below it is LLM-generated, grounded in the data the visual shows
- Observation must be specific to this athlete's recent data (last 7-14 days)
- Evidence is compact — one line, not a table
- Interpretation must include causal reasoning or pattern recognition
- Action must be athlete-controllable
- A chapter with no interpretation is not a chapter — suppress it

**JSON contract:**

```json
"chapters": [
  {
    "title": "string (required)",
    "topic": "volume_trajectory",
    "visual_type": "bar_chart",
    "visual_data": {
      "labels": ["Jan 6", "Jan 13", "Jan 20", "Jan 27", "Feb 3", "Feb 10", "Feb 17", "Feb 24"],
      "values": [45, 48, 52, 56, 63, 55, 42, 35],
      "highlight_index": 7,
      "unit": "mi"
    },
    "observation": "string (required)",
    "evidence": "string (required)",
    "interpretation": "string (required)",
    "action": "string (required)",
    "relevance_score": 0.92
  }
]
```

**Supported `visual_type` values:**
- `bar_chart` — weekly volume, run counts
- `sparkline` — efficiency, CTL, any time series trend
- `health_strip` — sleep/HRV/RHR compact indicators
- `gauge` — TSB form position, readiness
- `completion_ring` — consistency percentage
- `dot_plot` — wellness trends (motivation, soreness over time)
- `stat_highlight` — PB or single metric callout

---

### Act 3: What Your Data Has Learned About You

**Visual anchor:** Correlation indicator — a simple visual showing two metrics
and the relationship between them. When X rises, Y improves. A paired
sparkline, a directional arrow diagram, or a compact scatter showing the
pattern. This visual communicates "your body has a pattern" before the
narrative explains what it is.

**Narrative bridge:** The full N=1 callout. This is the section no competitor
can replicate. It surfaces confirmed personal correlations from the correlation
engine and connects them to the athlete's current situation.

**Example:**

> [Paired sparkline: motivation (top) and efficiency (bottom), peaks aligned]
>
> **In your data:** When your motivation is higher, your running efficiency
> tends to improve within 3 days. This pattern has been confirmed 4 times —
> it's becoming a reliable signal. Right now your motivation is high. That's
> working in your favor heading into Tobacco Road.

**Rules:**
- Must be athlete-specific. The acceptance test: could this exact callout
  appear on a different athlete's progress page? If yes, reject it and
  regenerate.
- Must cite confirmation count (`times_confirmed` from `CorrelationFinding`)
- Must connect the pattern to the athlete's current situation
- If no confirmed correlations exist (new athlete), show a progress indicator
  with a visual (partially filled ring or progress bar):
  "Your personal patterns are forming. X/Y check-ins collected. Daily check-ins
  accelerate discovery." Do NOT show generic population insights as a
  placeholder.
- Max 2 patterns per page load
- The visual is deterministic (from stored correlation data), the narrative
  is LLM-generated

**JSON contract:**

```json
"personal_patterns": [
  {
    "narrative": "string (required)",
    "input_metric": "motivation_1_5",
    "output_metric": "efficiency",
    "visual_type": "paired_sparkline",
    "visual_data": {
      "input_series": [3, 4, 5, 4, 3, 5, 4, 5],
      "output_series": [0.82, 0.84, 0.88, 0.86, 0.83, 0.89, 0.85, 0.87],
      "input_label": "Motivation",
      "output_label": "Efficiency"
    },
    "times_confirmed": 4,
    "current_relevance": "string (required)",
    "confidence": "confirmed"
  }
],
"patterns_forming": {
  "checkin_count": 8,
  "checkins_needed": 14,
  "progress_pct": 57,
  "message": "string"
}
```

---

### Act 4: Looking Ahead

This section adapts based on whether the athlete has a race on the calendar.
Both variants need a visual anchor.

#### Variant A: Race on the calendar

**Visual anchor:** Race readiness gauge — a semicircular gauge or radial
indicator showing current readiness (composite of form, fitness, recovery,
sleep). Positioned from "building" through "ready" to "peaked." The athlete
sees where they stand at a glance. Countdown number beside it.

**Narrative bridge:** Scenario framing. Not predictions — scenarios. "If X then
Y." Honest, demonstrates system knowledge, gives athlete agency.

**Example:**

> [Readiness gauge: needle at 72%, label "Building → Ready", "13 days" counter]
>
> **Tobacco Road Marathon — 13 days**
>
> *If the current trend holds:* Your efficiency has been climbing for two
> weeks. If you sleep above your 6.8h average and keep runs easy through
> next week, your form should reach +10 to +15 by race morning. Estimated
> finish: 3:00-3:03.
>
> *If recovery slips:* Your Garmin sleep has averaged 5.6h device-measured.
> If that continues into race week, you're running a sleep deficit into
> taper. Prioritizing 7+ hours this week is the single highest-leverage
> action.

**Rules:**
- Readiness gauge is deterministic (composite score from existing services)
- Always present at least two scenarios (positive trend + risk scenario)
- Scenarios grounded in the athlete's own data and patterns
- Include estimated finish range if race predictions are available
- Frame as "if X then Y" — the athlete has agency
- No guarantees, no definitive predictions

#### Variant B: No race on the calendar

**Visual anchor:** Capability trajectory — a compact line chart showing what
the athlete's current fitness projects them capable of at standard race
distances. Not a prediction — a snapshot of "where your fitness is right now"
expressed as race equivalents. This answers "Am I getting better?" for runners
who run for fitness, not for races.

**Narrative bridge:** Trend framing. Where the trajectory is pointing, what's
improving, what the next milestone might be if they keep going.

**Example:**

> [Capability chart: four horizontal bars for 5K / 10K / Half / Marathon
> with projected times, colored by confidence]
>
> **Where your fitness is pointing**
>
> Your aerobic base has been building steadily for 6 weeks. Current fitness
> projects a 23:40 5K and a 1:44 half marathon — both improvements from
> where you were a month ago (24:15 and 1:48). The biggest driver has been
> consistency: you've completed 90% of planned runs over the last 4 weeks.
>
> If volume continues at 35-40 miles per week through March, your 5K
> equivalent should drop below 23:00 by early April.

**Rules:**
- Capability bars are deterministic (from existing race prediction service)
- The narrative frames trajectory and trend, not goals
- No pressure to race — this is for runners who run because they love it
- Include what's driving the improvement (consistency, volume, efficiency)
- If applicable, suggest what milestone is within reach without prescribing it

**JSON contract:**

```json
"looking_ahead": {
  "variant": "race" | "trajectory",
  "race": {
    "race_name": "Tobacco Road Marathon",
    "days_remaining": 13,
    "readiness_score": 72,
    "readiness_label": "Building",
    "gauge_zones": ["building", "ready", "peaked", "over-tapered"],
    "scenarios": [
      {
        "label": "If current trend holds",
        "narrative": "string (required)",
        "estimated_finish": "3:00-3:03",
        "key_action": "Keep runs easy, sleep 7+ hours"
      }
    ],
    "training_phase": "taper"
  },
  "trajectory": {
    "capabilities": [
      { "distance": "5K", "current": "23:40", "previous": "24:15", "confidence": "high" },
      { "distance": "10K", "current": "49:10", "previous": "50:30", "confidence": "high" },
      { "distance": "Half", "current": "1:44:00", "previous": "1:48:00", "confidence": "moderate" },
      { "distance": "Marathon", "current": "3:38:00", "previous": "3:46:00", "confidence": "low" }
    ],
    "narrative": "string (required)",
    "trend_driver": "string (required)",
    "milestone_hint": "string (nullable)"
  }
}
```

---

### Act 5: Athlete Controls

The athlete decides. The system informs. This footer gives the athlete agency
over the report they just read.

**Controls:**
- **"This feels right"** — positive signal. Logged for narrative quality
  tracking.
- **"Something's off"** — opens pre-set options: "I feel better than this
  says" / "I feel worse than this says" / "The data is wrong." Logged for
  calibration.
- **"Ask Coach about this"** — deep-links to coach chat with the progress
  context pre-loaded.

**Rules:**
- Never more than 3 controls
- Controls are feedback mechanisms, not navigation
- Responses logged to `NarrativeFeedback` for future calibration
- No "share" button — this is a private reflection surface

**JSON contract:**

```json
"athlete_controls": {
  "feedback_options": ["This feels right", "Something's off", "Ask Coach"],
  "coach_query": "Walk me through my progress report in detail"
}
```

---

## Build Contracts (non-negotiable)

### 1. Render independence

Visual blocks MUST NEVER depend on LLM completion. Every `visual_type` and
`visual_data` field is assembled from deterministic service calls. The
frontend renders visuals immediately upon receiving Phase 1 data. Narrative
fields arrive separately (Phase 2) and fill in below the already-visible
visuals. If the LLM is slow, the athlete sees charts. If the LLM fails,
the athlete still sees charts. The page is never blank.

### 2. Latency budget

| Phase | Target | Method |
|-------|--------|--------|
| Phase 1 (deterministic visual data) | < 500ms | Parallel service calls, no LLM |
| Phase 2 (LLM narrative) | < 5s | Async, streamed or polled |
| Cache hit | < 100ms | Redis, full response |

Architecture: single endpoint `GET /v1/progress/narrative`. Phase 1
assembles visual data (< 500ms). Phase 2 runs LLM synthesis (< 5s). The
endpoint returns the complete response. On cache hit, response returns in
< 100ms. There is no two-call split — one endpoint, one response, one cache
key. The frontend shows a visual-first skeleton while the call completes.

The render independence contract means: if the LLM times out or fails, the
endpoint still returns visual data with deterministic fallback text. The
response shape is identical — narrative fields contain fallback copy instead
of LLM output. The frontend never needs to know whether it got LLM or
fallback.

### 3. Per-act deterministic fallback copy

When the LLM fails or times out, each act renders its visual with a
deterministic text fallback. These are not coaching — they are factual labels
derived from the data. The page degrades to a visual dashboard, not a blank
screen.

| Act | Fallback text |
|-----|--------------|
| Verdict | "{direction} trend over {N} weeks. CTL {value}." (e.g., "Rising trend over 8 weeks. CTL 48.0.") |
| Chapter: volume | "Weekly volume: {current_week}mi this week. {trend_pct}% vs 4-week average." |
| Chapter: efficiency | "Efficiency {direction} over {days} days. Current: {value}." |
| Chapter: recovery | "Sleep {avg}h avg | HRV {avg}ms | RHR {avg}bpm" |
| Chapter: load | "Form (TSB): {value}. Zone: {zone_label}." |
| Chapter: consistency | "{pct}% of planned workouts completed." |
| Chapter: PB | "New {distance} PB: {time} on {date}." |
| N=1 pattern | "Pattern: {input_metric} → {output_metric}. Confirmed {N} times." |
| Looking Ahead (race) | "{race_name} in {days} days. Readiness: {score}%." |
| Looking Ahead (trajectory) | "Current projections — 5K: {time} | Half: {time} | Marathon: {time}" |

Fallback text uses only fields already present in `visual_data`. No LLM
call, no invented language.

### 4. No-race capability grounding

The "trajectory" variant of Looking Ahead MUST use race times from the
existing `get_race_predictions()` service. No invented projections. No
extrapolated times the prediction model did not produce. If the prediction
service returns no data for a distance, that bar does not render. The
"previous" ghost bar uses the prediction from 28 days ago (cached or
recomputed). If no prior prediction exists, no ghost bar.

### 5. N=1 confidence gating

Correlation patterns are presented with language that matches their
evidence weight. The confidence field controls the framing:

| Confidence | `times_confirmed` | Language rule |
|-----------|-------------------|---------------|
| `emerging` | 1-2 | "Early signal to watch: {pattern}. Seen {N} times so far." |
| `confirmed` | 3-5 | "In your data: {pattern}. Confirmed {N} times — becoming reliable." |
| `strong` | 6+ | "Your body consistently shows: {pattern}. Confirmed {N} times." |

An `emerging` pattern is NEVER presented as a causal claim. The language
must communicate "we're watching this" not "this is how your body works."
The LLM prompt must include this gating table. If the LLM ignores it and
produces causal language for an emerging pattern, validation rejects and
falls back to the deterministic template above.

---

## Backend: New Endpoint

### `GET /v1/progress/narrative`

Returns the full structure for the progress page. Two-phase assembly:

**Phase 1: Deterministic data (no LLM)** — assembles all visual data:
- `TrainingLoadCalculator` → CTL history (sparkline), TSB (gauge), form zone
- `get_efficiency_trends()` → efficiency sparkline data
- `correlation_persistence.get_confirmed_correlations()` → N=1 pattern data
  with time series
- `get_weekly_volume()` → volume bar chart data
- `get_wellness_trends()` → health strip data (sleep, HRV, RHR, stress)
- `get_recovery_status()` → readiness composite
- `get_race_predictions()` → capability bars
- `TrainingPlan` → race info, training phase
- `Activity` → recent run data for evidence
- `GarminDay` → device health metrics
- `DailyCheckin` → checkin count, wellness dot plot
- `calculate_consistency_index()` → completion ring data
- `PersonalBest` → recent PBs

**Phase 2: LLM synthesis** — generates narrative for each section:
- System prompt enforces the five-act structure
- Receives the full deterministic data snapshot as context
- Returns narrative fields only (the visuals are already assembled)
- Validation: all required narrative fields present, no empty chapters, N=1
  patterns pass uniqueness test

**Caching:**
- Redis key: `progress_narrative:{athlete_id}`
- TTL: 1800s (30 min)
- Visual data can be cached separately with longer TTL (deterministic)
- Invalidated on new activity sync or daily checkin

**Fallback:** If LLM fails, visual data still renders with deterministic
captions (trend direction labels, metric summaries). The page is still
meaningful because the visuals carry the story. The narrative enhances it
when available — but the visuals alone are not a blank page.

**Full response shape:**

```json
{
  "verdict": {
    "sparkline_data": [38.2, 39.1, 41.0, 42.8, 44.5, 46.1, 47.3, 48.0],
    "sparkline_direction": "rising",
    "current_value": 48.0,
    "text": "string (required)",
    "grounding": ["CTL 48.0", "TSB +0.7"],
    "confidence": "high"
  },
  "chapters": [
    {
      "title": "string (required)",
      "topic": "volume_trajectory",
      "visual_type": "bar_chart",
      "visual_data": { "labels": [], "values": [], "highlight_index": 7, "unit": "mi" },
      "observation": "string (required)",
      "evidence": "string (required)",
      "interpretation": "string (required)",
      "action": "string (required)",
      "relevance_score": 0.92
    }
  ],
  "personal_patterns": [
    {
      "narrative": "string (required)",
      "input_metric": "motivation_1_5",
      "output_metric": "efficiency",
      "visual_type": "paired_sparkline",
      "visual_data": { "input_series": [], "output_series": [], "input_label": "", "output_label": "" },
      "times_confirmed": 4,
      "current_relevance": "string (required)",
      "confidence": "confirmed"
    }
  ],
  "patterns_forming": null,
  "looking_ahead": {
    "variant": "race",
    "race": { "race_name": "", "days_remaining": 0, "readiness_score": 0, "scenarios": [], "training_phase": "" },
    "trajectory": null
  },
  "athlete_controls": {
    "feedback_options": ["This feels right", "Something's off", "Ask Coach"],
    "coach_query": "Walk me through my progress report in detail"
  },
  "generated_at": "2026-03-02T12:00:00Z",
  "data_coverage": {
    "activity_days": 28,
    "checkin_days": 22,
    "garmin_days": 14,
    "correlation_findings": 3
  }
}
```

---

## Frontend: Rendering Rules

### The flow

The page is one continuous scroll. Not cards. Not a grid. Each act flows into
the next, separated by generous whitespace. The visual anchors create rhythm —
the eye lands on a chart, absorbs the shape, then reads the narrative below it
to understand what the shape means.

### Visual rendering

- **Sparklines:** Lightweight, inline. No axes, no labels beyond start/end
  values. Color-coded by direction (emerald rising, amber flat, red declining).
  Rendered with SVG or a lightweight chart library (recharts, visx, or raw SVG).
- **Bar charts:** Compact. 6-8 bars max. Current week highlighted with accent
  color. Muted slate for historical weeks. No grid lines. Values on hover/tap.
- **Health strips:** Horizontal row of 3-4 compact indicators (sleep, HRV,
  RHR, stress). Each shows a value + directional arrow. Colored by status
  (green normal, amber watch, red alert).
- **Gauges:** Semicircular or linear. Simple position indicator. Not a full
  dashboard gauge — a minimal arc with a needle or dot.
- **Paired sparklines:** Two sparklines stacked vertically, aligned on the
  time axis, showing the N=1 correlation visually.
- **Capability bars:** Horizontal bars for race distances with projected times.
  Colored by confidence. Previous time shown as a lighter ghost bar behind.
- **Completion rings:** Simple SVG arc, percentage in the center.

All visuals are interactive on hover/tap — show the exact value at that point.
This is step 2 of the design principle: the athlete interacts.

### Typography hierarchy

1. **Verdict text** — large, bold, white. The first thing you read after the
   sparkline.
2. **Chapter titles** — medium, semibold, white
3. **Observation + Interpretation** — normal, slate-200, readable line height
4. **Evidence** — smaller, monospace or condensed, slate-400 — supporting role
5. **Action** — medium, accent color (orange or emerald), stands out from body
6. **N=1 callout** — distinct visual treatment: subtle glow, thin accent
   border, or different background tone

### Mobile

- Visuals scale down but remain visible — they're the page's visual rhythm
- Sparklines and bars work at phone width
- Health strips stack vertically on narrow screens
- Touch targets on interactive visuals are minimum 44px
- Narrative text gets generous line height for readability

### Loading state

- Skeleton that mimics the layout: sparkline placeholder + text blocks
- "Building your progress report..." message
- Visual data loads first (fast, deterministic) — narrative fills in after
  (LLM, ~2-3s). This means the page has visual content almost immediately.

### Empty/new athlete state

- If < 7 days of data: single sparkline with 3-4 points + "Your progress
  story is just beginning. Run a few more times, do your daily check-ins,
  and we'll start telling it."
- If 7-21 days: partial page with fewer chapters, confidence language visible
- If 21+ days: full page, all acts

---

## What This Page Does NOT Duplicate

1. **Full PMC chart.** The Training Load page owns that visualization. The
   progress page uses a compact fitness sparkline — same data, different
   presentation. The sparkline tells the direction; the full PMC page tells
   the detail.

2. **Full efficiency chart.** The Analytics page owns that. The progress page
   uses an efficiency sparkline in a chapter.

3. **Personal bests table.** If a recent PB is relevant, it appears as a
   chapter with a `stat_highlight` visual. The full PB list is secondary.

4. **Period comparison table.** If the comparison matters, it's a chapter with
   a bar chart and narrative. Not a table.

5. **Runner profile section.** Paces, RPI, runner type — reference data, not
   progress narrative. Belongs on settings/profile.

---

## Acceptance Criteria

- [ ] AC1: Page loads with a single `GET /v1/progress/narrative` call
- [ ] AC2: Every section has a visual anchor AND a narrative bridge — no
      text-only sections, no unexplained charts
- [ ] AC3: Visuals load first (deterministic), narrative fills in after (LLM)
      — the page is never a blank white screen waiting for AI
- [ ] AC4: Verdict sparkline renders from real CTL data, narrative below it
- [ ] AC5: Chapters each have a topic-appropriate visual (bar chart, sparkline,
      gauge, etc.) with narrative below
- [ ] AC6: N=1 pattern callout has a correlation visual and could NOT appear on
      a different athlete's page (uniqueness test)
- [ ] AC7: Looking Ahead renders race readiness gauge + scenarios when race
      exists, OR capability trajectory bars when no race exists
- [ ] AC8: Athlete controls render and log feedback
- [ ] AC9: Every narrative claim is grounded — no unsupported assertions
- [ ] AC10: If LLM fails, visual data still renders with deterministic labels
       — the page degrades gracefully, not to a blank screen
- [ ] AC11: Visuals are interactive (hover/tap shows values) — step 2 of the
       design principle
- [ ] AC12: Page feels like a visual story told by a coach, not a dashboard
       of charts OR a wall of text
- [ ] AC13: Mobile-first — visuals scale, touch targets work, narrative reads
       well on a phone
- [ ] AC14: Tree clean, tests green, production healthy

---

## Build Priority

1. **Backend:** `/v1/progress/narrative` endpoint — deterministic data assembly
   (Phase 1) + LLM narrative synthesis (Phase 2) + caching + validation
2. **Frontend: Visual components** — sparklines, bar charts, health strips,
   gauges, paired sparklines, capability bars, completion rings
3. **Frontend: Narrative layout** — flowing document with visual → narrative
   rhythm per section
4. **Feedback:** Athlete controls + NarrativeFeedback table + logging
5. **Polish:** Loading states (visual-first skeleton), empty states, confidence
   language, interaction (hover/tap)

---

## Decided

- **Visual first, narrative bridge.** Every section has a visual anchor that
  catches the eye, then a narrative below that teaches the athlete to read
  the visual. This is the product's foundational design principle. No
  exceptions.

- **Interpretation leads within narrative.** When the coach speaks, the
  observation comes first, not the raw number. Numbers are evidence for what
  the coach already said.

- **N=1 section cannot be generic.** If the pattern callout could apply to any
  runner, reject and regenerate.

- **Looking Ahead adapts.** Race on calendar = readiness gauge + scenario
  framing. No race = capability trajectory + trend narrative. The section
  never disappears — every runner deserves a forward-looking view.

- **Graceful degradation.** Visual data is deterministic and loads fast. If
  the LLM fails, the visuals still render with deterministic labels. The page
  is never blank.

- **Not a dashboard.** The visuals serve the narrative, not the other way
  around. Each chart exists because it creates a question the narrative
  answers. No chart exists just to display data.

---

*This spec is the builder's complete guide. The visuals are the eye. The
narrative is the voice. Together they build understanding that neither could
alone. Get the data assembly right, get the visual components right, then
let the narrative weave through them.*
