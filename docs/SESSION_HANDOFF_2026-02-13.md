# Session Handoff — February 13, 2026

## Session Summary

This session delivered Phase 3B/3C code, discovered and resolved a critical
efficiency interpretation ambiguity, and established the Athlete Trust Safety
Contract.  The session ended with scoping two new features: Run Shape
Intelligence and Strava Write-Back.

---

## What Was Shipped (commit `f55059b`)

### Phase 3B/3C Corrective Patch Set
- **Synced-history sufficiency:** `phase3_eligibility._history_stats()` now
  counts only provider-backed activities (source != "manual" OR provider set).
  Manual-only history does not unlock 3B/3C.  Founder rule preserved: synced
  historical data unlocks immediately.
- **Tier alignment:** `TIERS_3C` expanded to `{guided, premium, elite, pro}`
  to match router tier checks.
- **3B audit records:** Workout narrative endpoint now persists `NarrationLog`
  for founder QA of first 50 narratives.

### Athlete Trust Safety Contract (the big deliverable)
- **Problem discovered:** Efficiency is `pace(sec/km) / avg_hr`.  This ratio
  is **directionally ambiguous** — it rises when HR drops at fixed pace (good)
  but falls when pace improves at fixed HR (also good).  15+ services had
  "lower = better" comments baked in, which is only correct when pace moves
  and HR is stable.  Raw correlation sign was being used to determine
  "what works / what doesn't" — a trust-killing error waiting to happen.
- **Solution:** Formal 8-clause Athlete Trust Safety Contract embedded in
  `n1_insight_generator.py` module docstring + enforced in runtime code.
- **Key mechanisms:**
  - `OutputMetricMeta` registry: 10 metrics with `metric_definition`,
    `higher_is_better`, `polarity_ambiguous`, `direction_interpretation`
  - `DIRECTIONAL_SAFE_METRICS` whitelist: `pace_easy`, `pace_threshold`,
    `race_pace`, `completion_rate`, `completion`, `pb_events`
  - Two-tier fail-closed: ambiguous → neutral text + `pattern` category;
    invalid metadata → full suppression
  - `_validate_metric_meta()` catches conflicting metadata
  - `_is_beneficial()` three-gate pipeline: validate → ambiguity → whitelist
- **65 contract tests** covering all 8 clauses
- **11 legacy services** updated with "directionally ambiguous — see
  OutputMetricMeta" comments (migration debt tracked, not hidden)
- **Cursor rules:** `athlete-trust-efficiency-contract.mdc` (file-scoped)
  and `build-plan-awareness.mdc` (always-on)

### Files Changed (17 files, +918 / -60)
- `services/n1_insight_generator.py` — contract, registry, guardrails
- `services/correlation_engine.py` — metric metadata in output, comment fixes
- `services/phase3_eligibility.py` — synced-history filter, tier alignment
- `routers/daily_intelligence.py` — audit log persistence
- `services/anchor_finder.py` — renamed speed/HR to "cardiac_speed"
- `services/ai_coach.py` — comment fixes
- `services/coach_tools.py` — comment fixes, legacy debt note
- `services/causal_attribution.py` — comment fixes
- `services/load_response_explain.py` — comment fixes
- `services/pattern_recognition.py` — comment fix
- `services/calendar_signals.py` — comment fix
- `services/home_signals.py` — comment fix
- `services/run_analysis_engine.py` — comment fix
- `services/activity_analysis.py` — comment fix
- `tests/test_n1_insight_generator.py` — 65 tests (full rewrite)
- `tests/test_phase3_eligibility.py` — synced-history + tier tests
- `docs/TRAINING_PLAN_REBUILD_PLAN.md` — contract baseline entry

### Test Results
- Full suite: **1986 passed**, 7 skipped, 119 xfail, 0 failures

---

## New Features Scoped (not yet built)

### Feature: Run Shape Intelligence (HIGH PRIORITY)

**Vision:** Reinvent how athletes interact with their run data.  Not a
dashboard of separate charts — a single unified canvas with composable layers,
interactive exploration, and AI-powered coachable moments.  The chart is
magic on its own; the coach makes it smarter.

#### Why This Matters
- Runners are data geeks.  They LOVE seeing their data.  A beautiful,
  interactive chart is what gets them to open the app.
- The AI coach layer is what makes them stay — intelligence no competitor can
  replicate because nobody else has the coaching stack behind it.
- Garmin and Strava charts are dated, fragmented (5 separate panels), and
  answer "what were the numbers?" but never "what happened and why?"

#### Data Layer: Stream Ingestion
- **What:** Ingest 1-second resolution time-series from Strava
  (`GET /activities/{id}/streams`) and Garmin (FIT file parsing).
  Channels: `time`, `distance`, `heartrate`, `cadence`, `altitude`,
  `velocity_smooth`, `grade_smooth`, `latlng`.
- **Storage:** New `ActivityStream` model.  Store per-activity in the
  database (a 60-min run ~ 30-50KB compressed; 1000 runs ~ 50MB/athlete).
  DB storage preferred over object storage for query simplicity.
- **Backfill:** Historical activities need stream backfill.  Same
  rate-limiting pattern as existing split backfill.  Founder has 2 years
  of Strava data — this is the first backfill target.
- **Gap vs. current:** `ActivitySplit` stores per-split summaries (10 fields).
  Streams give per-second resolution.  Split data stays for backward compat;
  streams are the new source of truth for visualization and coach tools.

#### Visualization: Unified Canvas
- **Single chart, composable layers** (not 5 separate panels):
  - **Pace curve** — always on by default.  THE shape of the run.
  - **Heart rate response** — secondary Y-axis, toggleable.
  - **Cadence** — toggleable overlay.
  - **Stride length** — derived from pace + cadence, toggleable.
  - **Elevation profile** — shaded fill underneath (context, not competing
    data).  Grade/incline color-coded: green flat, yellow moderate, red steep.
  - **Workout structure markers** — vertical bands for rep/recovery from
    PlannedWorkout or athlete-tagged structure.
- **X-axis:** distance or time, athlete's choice.  Auto-suggest time for
  intervals (prevents recovery compression on distance axis), distance for
  steady/progressive runs.
- **Smoothing:** 5-10 second rolling average by default for readable curves.
  Toggle to raw data.  Raw values always available on hover.

#### Interaction Model
1. **Land** — chart loads with pace + elevation.  Coach summary appears.
   Coachable moments marked.  Get the story in 5 seconds.
2. **Explore** — toggle layers.  Hover for crosshair (all active values at
   that point).  Zoom/brush into segments.  Responsive, touch-friendly.
3. **Ask** — see something interesting?  Ask the coach.  It has the stream
   data loaded via tool.  Answers with evidence, not guesses.
4. **Compare** — pull up a previous similar run.  Overlay traces (solid vs.
   dashed).  See adaptation over time.  Or select two segments within the
   same run (rep 1 vs rep 6) and overlay them.
5. **Share** — found something worth sharing?  Push to Strava (Feature B).

#### Interactive Behaviors
- **Hover crosshair:** vertical line shows all active layer values at that
  distance/time point.
- **Zoom/brush:** drag-select a segment, chart zooms.  See one interval rep
  in detail.
- **Segment comparison:** select two segments, overlay at same scale.
  See drift, fade, consistency.
- **Plan overlay:** if linked to PlannedWorkout, show target zones as shaded
  bands.  Actual traces overlay on top.  One glance — did you execute?
- **Tap coachable moments:** marker expands with coach's finding.  Chart
  auto-zooms to that moment.  Relevant layers toggle on.

#### Coachable Moments (AI-detected findings pinned to timestamps)
- **Cardiac drift onset** — HR climbing at steady pace, with comparison to
  previous similar runs.
- **Cadence breakdown** — cadence drops while pace holds = compensating with
  stride length.  First sign of fatigue.
- **Pacing execution** — hit target zones within tolerance.  Positive
  reinforcement when deserved.
- **Recovery quality** — between-rep HR recovery degrading across the set.
- **Decoupling point** — pace:HR relationship breaks.
- **Form change** — cadence/stride ratio shifts.

#### Coach Tool: `analyze_run_streams`
- **Segment detection** — auto-identify intervals, recovery, warmup,
  cooldown, steady-state from stream patterns.
- **Drift analysis** — cardiac, pace, cadence drift within and across
  segments.
- **Coachable moments** — anomalies, breakdowns, achievements at specific
  timestamps.
- **Plan comparison** — PlannedWorkout prescription vs. actual execution.
- **Cross-run context** — how this run compares to recent similar efforts.

#### Workout Type Awareness
- **Plan-linked runs:** automatic structure from PlannedWorkout prescription.
  Overlay planned vs. actual.
- **Ad-hoc runs:** athlete tags workout type.  Shape detection suggests
  structure (intervals look like spikes, threshold looks sustained, progressive
  shows descending pace).
- **Ambiguous workouts:** 2x3min at threshold looks like intervals in the
  data but is a threshold variant.  Athlete-selected type resolves this.

#### Design Language
- **Modern, not 1990s.**  Garmin = engineering UI.  Strava = decade-old
  prototype.  StrideIQ = 2026.
- Dark background option (performance data pops).  Think F1 telemetry.
- Smooth curves (rolling average), subtle grid, strong data.
- Consistent color system: pace = brand primary, HR = warm red,
  cadence = cool blue, elevation = muted earth tones.
- Chart chrome (axes, gridlines) almost invisible.  Data is the loudest
  element.
- Responsive and touch-friendly.  Pinch to zoom on mobile.

#### Use Cases That Must Work Beautifully
1. **Interval session (12x400m):** twelve rep spikes, visible consistency,
   HR and cadence per rep, recovery quality between reps.
2. **Progressive run:** pace stepping down in stages, HR climbing in
   response, cadence/stride length showing HOW you got faster.
3. **Hill repeats:** elevation fill with grade coloring, pace dips on climbs
   (expected), HR maintaining effort band (good), different grades visible
   to explain different paces.
4. **Easy long run:** steady pace, cardiac drift detection, decoupling point
   identification.
5. **Race:** negative split execution, pacing vs. plan, HR ceiling approach.

#### Existing Foundation
- `ActivitySplit` model (10 fields) — keep for backward compat.
- Strava ingestion with lap/split merging — extend to streams.
- Garmin import for laps — extend to FIT stream data.
- `GET /v1/activities/{id}/splits` endpoint — add `/streams` endpoint.
- `SplitsChart.tsx` + `SplitsTable.tsx` (Recharts) — replace or extend
  for stream-level unified canvas.
- Coach already has tools — add `analyze_run_streams`.

#### Implementation Sequence (suggested)
1. **Stream ingestion + storage** — `ActivityStream` model, Strava stream
   fetch, Garmin stream parsing, backfill pipeline.
2. **Coach tool** — `analyze_run_streams` with segment detection, drift
   analysis, coachable moment identification.
3. **Unified canvas** — frontend component, composable layers, interactions.
4. **Coachable moment rendering** — markers on chart linked to coach findings.
5. **Comparison** — run-over-run overlay, segment-vs-segment, plan overlay.

---

### Feature: Strava Write-Back with Attribution (LOWER PRIORITY — spec now, build later)

**Vision:** Push StrideIQ coaching content to Strava activity descriptions.
Every training partner/follower who sees the activity also sees the insight
and the attribution.  Organic distribution through the athlete's social graph.

#### Key Requirements
1. **OAuth scope audit:** verify current flow requests `activity:write`.
   If not, existing users need re-authorization flow.
2. **Opt-in with preview:** athlete enables globally, sees preview before
   each push, can disable per-activity or globally.  Founder is first
   opt-in for testing.
3. **Append model:** read existing description, preserve athlete's content,
   add StrideIQ block below a recognizable delimiter
   (e.g., `--- StrideIQ Analysis ---`).  Never overwrite athlete's notes.
4. **Content selection:** what gets pushed —
   - Post-run stream analysis summary (coachable moments)
   - Key insight if one exists
   - Workout narrative (3B output)
5. **Timing:** initially manual (athlete reviews in StrideIQ, then pushes).
   Automatic push is a later option once quality trust is established.
6. **Removal:** athlete can remove StrideIQ block without affecting their
   own notes.  The delimiter makes this possible.
7. **Attribution:** "Analysis by StrideIQ" with link.  Check Strava API
   terms for attribution format requirements.
8. **Rate limiting:** Strava API rate limits apply.  Queue writes, don't
   burst.

#### Existing Observation
The founder already uses a third-party weather service that writes to Strava
descriptions.  Same API pattern.  Founder sometimes erases third-party
content deliberately — confirms that athlete control and clean delimiters
are essential.

#### Technical Path
- Strava API: `PUT /api/v3/activities/{id}` with `description` field.
- Read current description → append below delimiter → write back.
- New service: `strava_writeback_service.py`
- New router endpoint: `POST /v1/activities/{id}/push-to-strava`
- Settings: per-athlete opt-in flag, content preferences.

---

## Current State of Build Plan

| Phase | Status |
|-------|--------|
| Phase 1 (Plans) | COMPLETE |
| Phase 2 (Adaptation) | COMPLETE |
| Phase 3A (Narration) | COMPLETE |
| Phase 3B (Workout Narratives) | CODE COMPLETE — gate accruing (4-week narration quality) |
| Phase 3C (N=1 Insights) | CODE COMPLETE — gate accruing (founders with synced history unlock immediately) |
| Trust Safety Contract | ENFORCED — 65 contract tests |
| Monetization | Not started — 1-2 weeks out |
| Phase 4 (50K Ultra) | Not started — not pressing |
| **Run Shape Intelligence** | **SCOPED — next priority** |
| Strava Write-Back | SCOPED — build after Run Shape |

## Build Priority (current)

1. **Run Shape Intelligence** — stream ingestion, unified canvas, coach tool
2. **Strava Write-Back** — after Run Shape produces content worth pushing
3. **Monetization** — in 1-2 weeks
4. **Phase 4 (50K Ultra)** — when ready

## Key Files for Next Session

- `docs/TRAINING_PLAN_REBUILD_PLAN.md` — north star build plan
- `services/n1_insight_generator.py` — trust safety contract + metric registry
- `models.py` — ActivitySplit (line 403), Activity (line 341)
- `tasks/strava_tasks.py` — current split/lap ingestion
- `apps/web/components/activities/SplitsChart.tsx` — current chart component
- `.cursor/rules/build-plan-awareness.mdc` — always-on build priority rule
- `.cursor/rules/athlete-trust-efficiency-contract.mdc` — trust contract rule

## Notes for Next Agent

- The founder has 2 years of Strava data.  Stream backfill for this account
  is the first test case.
- The founder will be the first Strava write-back opt-in for testing timing
  and content quality on real data.
- The Athlete Trust Safety Contract applies to ANY new coach output,
  including the `analyze_run_streams` tool.  Directional claims about
  efficiency still require the whitelist and polarity metadata.
- The `SplitsChart.tsx` component exists but is basic Recharts.  The unified
  canvas likely needs a different approach (D3, Visx, or heavily customized
  Recharts).  Evaluate before committing to a library.
- Workout type detection from stream shape is a stretch goal.  Start with
  plan-linked structure and athlete tagging.
- Stream storage: prefer database (`ActivityStream` table) over object
  storage.  Query simplicity matters more than storage optimization at
  current scale.
