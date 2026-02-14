# Run Shape Intelligence — Canvas Proposal (RSI Phase 3)

**Status:** SPEC HARDENING — advisor review complete, pre-build gates in progress
**Date:** February 14, 2026
**Context:** RSI Phase 1 (stream storage, ADR-063) and RSI Phase 2 (analyze_run_streams coach tool with N=1 tiered classification) are complete. CI is 8/8 green on `main`. This proposal covers the frontend visualization and interaction layer.

**Scope labels (no collision with build-plan Phase 3A/3B/3C):**
- **RSI-Alpha** = Canvas + Story + Lab (no coach narration surface)
- **RSI-Beta** = Coach moments + tap-to-explain layer (deferred, gated)

---

## What This Is

Run Shape Intelligence Phase 3 puts the Phase 2 analysis engine on screen. The athlete opens a completed run and sees their effort come alive — not as a flat line chart, but as a narrative canvas that tells the story of the run, with an AI coach ready to discuss any part of it.

This is not a chart upgrade. This is the visual identity of the product.

---

## Design Philosophy

### The Problem with Every Running App

Every app on the market — Strava, Garmin Connect, TrainingPeaks, Coros — shows the same thing: line charts with time on the X axis, some squiggly traces, maybe a colored zone band. You finish a run that nearly broke you, where you hit a moment at 8K where you had to dig deep and find a mantra to make it to the next kilometer, and the app shows you... a flat line with a bump.

The data is there. The story isn't.

### What We're Building Instead

The run tells its own story when you look at it. Color is the primary language — not decoration. The intensity of color IS the effort. You should be able to glance at your run and immediately know where it got real, where you recovered, where you pushed through. Without reading a single number.

Then the coach (Opus 4.5) is sitting right there, looking at the same canvas, ready to discuss any moment you're curious about.

And for the data geeks — the subscribers who are also their own analysts — there's a full data layer where they can let their inner data analyst run wild.

---

## Three-Layer Canvas Architecture

### Layer 1: The Story (All Paid Tiers — RSI-Alpha)

**What the athlete sees first.** Intuitive, emotional, immediate. Anyone can understand it.

- **Effort gradient as primary visual language.** Not discrete colored bands (warmup = amber, work = red). The color is continuous — mapped from actual effort intensity at every second. Easy effort is cool (blues/teals), moderate is warm (amber), hard is hot (orange/red), max is deep crimson. The segment classification still exists underneath for structure, but what you *see* is the continuous story of effort. Effort intensity computation is tier-dependent — see ADR-064.

- **Terrain as the foundation.** Elevation profile as a filled shape at the bottom — the literal ground you ran on. This grounds the visualization in the physical experience.

- **Multi-trace on unified axis.** HR and pace as traces that visually interact on a shared time axis. When pace holds steady but HR climbs, you can *see* the gap opening between them. That gap IS cardiac drift. No label needed — the visual language communicates it. **One crosshair moves across all visible layers simultaneously** — hover at any timestamp and see every active channel at that exact moment.

- **Story-layer toggles.** Cadence, grade, and other secondary traces are togglable in the Story layer — not hidden behind a Lab switch. The athlete controls the information density. Some runners want everything. Some want just pace and HR. Both are right.

- **Run type shapes the canvas.** An easy run's canvas feels calm — mostly cool colors, gentle undulation. An interval session looks like a heartbeat — sharp alternating bands of intensity. A progressive run visually builds. A hill session shows terrain dominating the effort story. The canvas adapts to the type of run.

- **Plan comparison card.** If the run is linked to a planned workout, a summary card shows planned vs actual (duration, distance, pace, interval count match). Clean, at-a-glance.

- **Confidence + tier badge.** Small provenance indicator showing which N=1 tier classified this run and the confidence level. When `cross_run_comparable == false` (Tier 4), a visible caveat label communicates that colors are relative to this run only. Transparency for the athlete who cares; trust protection for every athlete.

**Cost:** Zero marginal token cost. Everything is deterministic engine output from Phase 2.

### Layer 2: The Coach ($25/mo Premium Tier — RSI-Beta, Deferred)

**The interactive intelligence layer.** This is the product's identity — not an afterthought on a chart.

- **Earned moments on the canvas.** Specific points on the timeline where something genuinely interesting happened — but ONLY when they earn their place. A moment is a promise to the athlete: "look here, this matters." If they tap it and get something obvious or generic, trust is lost. If they tap it and learn something they didn't know about their own running, they'll be eager to find the next one.

- **Moment filtering is deterministic, not LLM.** The Phase 2 analysis engine produces candidate moments. A deterministic interest scoring model evaluates each one on:
  - **Surprise:** Does this deviate from the athlete's baseline or expectations?
  - **Novelty:** Has this pattern appeared before in this athlete's history?
  - **Actionability:** Can the athlete do something with this (pacing strategy, cadence adjustment, mental approach)?
  - **Rarity:** Moment density scales with run richness. Easy run: 0-2 moments. Intervals: 3-5. Race: every significant moment. Silence over noise.

- **Coach narration on tap.** When the athlete taps a moment, the LLM generates a contextual narrative grounded in their personal data and training history. Gemini Flash handles simple observations; Opus 4.5 handles deep analysis, cross-run patterns, and strategy suggestions. Tokens scale with engagement, not run count.

- **"Tell me about that red section."** The athlete can tap any region of the canvas (not just pre-identified moments) and ask the coach about it. The coach sees the same analysis data and speaks about what happened there — physiologically, tactically, in the context of their training. Trust contract constraints apply — see Canvas Trust Contract section below.

- **Moments must pass a trust test every time:**
  - Is this surprising? (The athlete doesn't already know this)
  - Is this personal? (References their own history, not generic physiology)
  - Is this actionable? (Physical or mental strategy they can try)
  - Is this rare enough to be valued? (Not drowning in annotations)

**Cost:** Tokens on-demand only. No LLM calls until the athlete taps. Tiered model routing controls cost. See cost analysis below.

### Layer 3: The Lab (All Paid Tiers — RSI-Alpha)

**The data geek layer.** Respects the intelligence of subscribers who want full analytical access.

- **Raw traces with precision.** Toggle into the lab and every channel becomes a precise line — exact HR values on hover, pace per split, cadence, grade, power if available. Unified crosshair persists — same interaction model as Story layer.
- **Zone overlays.** HR zones, pace zones — the athlete's own zones (N=1), not population defaults.
- **Drill-down data.** Segment-by-segment metrics table. Per-interval comparison for workouts. Drift percentages.
- **Full analysis output.** Everything the Phase 2 engine produced — segments, drift analysis, all coachable moments (not just the filtered ones), plan comparison details.
- **Historical comparison (deferred).** Overlay today's traces against previous efforts (same route, same workout type). Requires route matching or workout-type matching infrastructure — not in RSI-Alpha scope. Tracked for RSI-Gamma or later.

**Cost:** Zero marginal token cost. Static data rendering.

---

## RSI-Alpha / RSI-Beta Scope Split

### RSI-Alpha — Ship Target (Canvas + Story + Lab)

| # | Feature | Notes |
|---|---|---|
| A1 | Dedicated analysis endpoint (`GET /v1/activities/{id}/stream-analysis`) | Returns `StreamAnalysisResult` serialized |
| A2 | Effort gradient canvas with tier-aware intensity computation | Per ADR-064; Tier 4 caveat label when `cross_run_comparable == false` |
| A3 | HR + pace traces on unified time axis | Shared crosshair across all visible channels |
| A4 | Elevation terrain fill (foundation layer) | Subtle fill, grade-aware color shift |
| A5 | Story-layer toggles for secondary traces | Cadence, grade, stride length — athlete controls density |
| A6 | Unified crosshair interaction | Hover shows all active channel values at exact timestamp |
| A7 | Segment overlay (discrete bands behind traces) | Warmup / work / recovery / cooldown / steady color coding |
| A8 | Plan comparison card | Planned vs actual: duration, distance, pace, interval count |
| A9 | Confidence + tier provenance badge | Tier label + confidence score; Tier 4 caveat when applicable |
| A10 | Lab toggle — raw data mode | Full-precision traces, zone overlays (athlete's own zones), segment table, drift metrics |
| A11 | Loading states per ADR-063 lifecycle | pending → spinner; fetching → spinner; failed → retry hint; unavailable → hide panel |
| A12 | Downsampling for display performance | LTTB or equivalent; rendering tech per ADR-064 |

### RSI-Beta — Deferred (Coach Moments + Tap-to-Explain)

| # | Feature | Gate |
|---|---|---|
| B1 | Deterministic moment interest scoring model | Formal spec + founder approval (Gate 4) |
| B2 | Earned moment markers on canvas | Scoring spec approved |
| B3 | Tap-to-discuss: moment narration (LLM) | Canvas trust contract (Gate 5) |
| B4 | Tap-to-discuss: free-form region questions | Canvas trust contract (Gate 5) |
| B5 | Cross-run coach pattern narration | Canvas trust contract + comparison infra |
| B6 | Tiered model routing (Flash vs Opus) | Cost model validated |
| B7 | $25 tier gating enforcement | Monetization tier mapping landed |
| B8 | Trust validation: founder review of first 50 narrations | Before general rollout |

### Deferred Beyond RSI-Beta

| Feature | Reason |
|---|---|
| Historical cross-run comparison overlay | Requires route matching / workout-type matching infrastructure |
| Push notifications for coachable moments | In-app first per Resolved Decision 3 |

---

## Hard Gates (Pass/Fail)

No implementation work begins until the blocking gate is cleared.

| # | Gate | Pass Condition | Blocks |
|---|---|---|---|
| **1** | **ADR-064: Effort intensity model + rendering technology** | ADR written, options compared with prototype evidence, effort computation defined per tier (1-4), rendering tech decided, Tier 4 UI caveat contract specified. **Founder-approved.** | All RSI-Alpha frontend work |
| **2** | **Naming resolved** | `RSI-Alpha` / `RSI-Beta` labels used in all specs, test files, and build plan references. No collision with build-plan Phase 3A/3B/3C. | Test/spec creation |
| **3** | **Build-plan priority reconciliation** | Explicit justification for why RSI-Alpha ships within the current priority stack. Documented in proposal or build plan update. | Implementation start |
| **4** | **Moment scoring formal specification** | Surprise/novelty/actionability/rarity formulas defined with concrete thresholds. Per-run-type density targets. Test scenarios covering easy, interval, hill, progressive, race. **Founder-approved.** | RSI-Beta |
| **5** | **Canvas trust contract extension** | Tier-aware suppression rules for free-form region questions. OutputMetricMeta compliance for ambiguous metrics. Cross-run claim suppression when `cross_run_comparable == false`. Suppression-over-hallucination policy for low-confidence responses. **Founder-approved.** | RSI-Beta |
| **6** | **RUN_SHAPE_VISION alignment checklist** | Unified crosshair ✓, Story-layer toggles ✓, comparison handling addressed ✓, F1 telemetry aesthetic validated against rendering prototype. | RSI-Alpha scope finalization |

---

## Canvas Trust Contract (New)

### Tier-Aware Suppression Rules

These rules apply to all athlete-facing output from the canvas, including both deterministic labels and LLM-generated narrations (RSI-Beta).

**1. Cross-run claims gated on provenance.**
When `cross_run_comparable == false` (Tier 4 — stream-relative classification), NO cross-run comparisons, NO "improved/declined" language, NO fitness trajectory claims. The canvas shows within-run story only. The Tier 4 caveat label is always visible.

**2. Ambiguous metrics produce neutral language only.**
The following Phase 2 metrics are registered as `polarity_ambiguous=True` in `OutputMetricMeta`:
- `cardiac_drift_pct`
- `pace_drift_pct`
- `cadence_trend_bpm_per_km`
- `plan_execution_variance`

Canvas output (labels, tooltips, coach narrations) MUST NOT use directional language ("improved," "worsened," "better," "concerning") for these metrics unless a future whitelist change explicitly approves it. Neutral observation only: "Cardiac drift of X% detected over the second half."

**3. Confidence/signal suppression.**
If the analysis confidence score is below 0.3, or if required channels are missing for a given output (e.g., drift requires HR), the corresponding visual element or narration is suppressed entirely. No forced output. Silence over hallucination.

**4. Coach narration trust alignment (RSI-Beta).**
All LLM-generated canvas narrations must comply with:
- Athlete Trust Safety Contract (8 clauses in `n1_insight_generator.py`)
- `OutputMetricMeta` polarity registry
- Tier-aware cross-run claim suppression (rule 1 above)
- Suppression over hallucination (FOC §5)
- System INFORMS, athlete DECIDES (FOC §6)

Coach canvas interactions will use a scoped system prompt that includes the tier provenance, cross_run_comparable flag, and applicable OutputMetricMeta entries for the metrics present in the tapped region.

---

## Tier Gating

| Feature | $15/mo Guided | $25/mo Premium |
|---------|:---:|:---:|
| Layer 1: Story Canvas (effort gradient, terrain, segments) | ✓ | ✓ |
| Layer 1: Unified crosshair + Story-layer toggles | ✓ | ✓ |
| Layer 1: Plan comparison card | ✓ | ✓ |
| Layer 1: Confidence + tier provenance (with Tier 4 caveat) | ✓ | ✓ |
| Layer 3: Lab (raw traces, zones, drill-down, segment table) | ✓ | ✓ |
| Layer 2: Coached moments on canvas | — | ✓ (RSI-Beta) |
| Layer 2: Tap-to-discuss with AI coach | — | ✓ (RSI-Beta) |
| Layer 2: Cross-run pattern insights | — | ✓ (RSI-Beta) |

**The $15 → $25 upgrade path:** The $15 athlete sees the story and the data. They notice the red section at 8K, dig into the lab, see the HR spike and grade change. But they're doing the analysis themselves. The $25 athlete taps that section and the coach says: "This is the third time you've hit this grade at this effort level. Each time you've held pace 30 seconds longer. Your hill strength is building. Next time, try dropping cadence 5 spm on the grade — your power data suggests you're overstriding on climbs."

The $15 athlete sees the gold mine. The $25 athlete has someone helping them dig.

---

## Cost Model & $10/Athlete/Month Profit Floor

### $15/mo Tier

| Cost Component | Early-Stage (100 athletes) | At-Scale (1,000+ athletes) |
|---|---|---|
| Stripe (2.9% + $0.30) | $0.74 | $0.74 |
| Infrastructure share | ~$3.00 | ~$0.50 |
| Analysis engine (CPU) | ~$0.01 | ~$0.01 |
| Daily adaptation narrations (Gemini Flash) | ~$0.30 | ~$0.30 |
| **Total cost** | **~$4.05** | **~$1.55** |
| **Profit** | **~$10.95** | **~$13.45** |

### $25/mo Tier (RSI-Beta active)

| Cost Component | Moderate User (early) | Moderate User (scale) | Power User (early) | Power User (scale) |
|---|---|---|---|---|
| Stripe (2.9% + $0.30) | $1.03 | $1.03 | $1.03 | $1.03 |
| Infrastructure share | ~$3.00 | ~$0.50 | ~$3.00 | ~$0.50 |
| Analysis engine (CPU) | ~$0.01 | ~$0.01 | ~$0.01 | ~$0.01 |
| Daily adaptation narrations (Flash) | ~$0.30 | ~$0.30 | ~$0.30 | ~$0.30 |
| Moment evaluation (deterministic) | $0.00 | $0.00 | $0.00 | $0.00 |
| Canvas coach narrations (Flash/Opus) | ~$3.00 | ~$3.00 | ~$6.00 | ~$6.00 |
| **Existing** coach chat (Flash/Opus) | ~$2.00 | ~$2.00 | ~$4.00 | ~$4.00 |
| **Total cost** | **~$9.34** | **~$6.84** | **~$14.34** | **~$11.84** |
| **Profit** | **~$14.66** | **~$17.16** | **~$9.66** | **~$12.16** |

**Moderate user:** 25 runs/month, engages canvas coach on ~10 runs (3 turns avg), 8 general coach chats/month.
**Power user:** 30 runs/month, engages canvas coach on every run (5 turns avg), 15 general coach chats/month.

### Token Sensitivity Analysis

| Scenario | Power User (early) Profit | Clears $10 Floor? |
|---|---|---|
| **Baseline** (current Gemini/Opus pricing) | $9.66 | No — needs model routing optimization |
| **2x Gemini Flash pricing** | ~$8.16 | No |
| **Aggressive Flash routing** (80% Flash / 20% Opus) | ~$11.50 | Yes |
| **Response caching** (repeat moment taps cached on `activity_id + moment_type + time_range`) | ~$10.80 | Yes |
| **Flash routing + caching combined** | ~$12.60 | Yes |

**Key finding:** Early-stage power users at baseline pricing are tight against the $10 floor. Two mitigation levers are required at launch:

1. **Aggressive model routing:** Route 80%+ of canvas interactions to Gemini Flash; reserve Opus for multi-turn deep analysis and cross-run pattern conversations only.
2. **Response caching for repeat views:** Cache coach narrations for deterministic moments (keyed on `activity_id + moment_type + time_range`, no custom question). Invalidate only if analysis result changes. Zero trust risk — underlying data is immutable for completed activities.

Both levers must be designed into RSI-Beta architecture, not bolted on later.

### Cost Architecture Decision

Moment gatekeeper is deterministic (zero tokens). LLM tokens only fire when the athlete actively engages. This means a $25 athlete who runs 30 times but only taps moments on 5 hard workouts costs ~$4/month in tokens. Costs scale with engagement, not activity count.

Future levers (available but not required at launch):
- Price adjustment (raise to $30 when traction justifies it)
- Usage-based routing thresholds (downshift to Flash-only after N Opus calls/month)
- Conversation depth limits (soft cap at N turns, "continue in full coach chat" redirect)

---

## Technical Architecture

### API Layer

**Dedicated analysis endpoint (Option A — selected):**
`GET /v1/activities/{activity_id}/stream-analysis`

Returns the full `StreamAnalysisResult` (segments, drift, moments, plan comparison, confidence, tier provenance). Separate from the existing raw streams endpoint. Clean separation of concerns.

The raw streams endpoint (`GET /v1/activities/{activity_id}/streams`) continues to serve the raw channel data for the Lab layer.

Two fetches for a full view, but they're independent and can be parallelized by React Query.

### Frontend Stack

- **Framework:** Next.js 14 (existing)
- **Rendering:** Per ADR-064 — Recharts, Canvas 2D, or hybrid. Decision based on prototype evidence.
- **State management:** React Query (existing patterns)
- **New service:** `activitiesService.getStreamAnalysis(activityId)`
- **New hooks:** `useStreamAnalysis(activityId)`, `useActivityStreams(activityId)`
- **New components:**
  - `RunShapeCanvas.tsx` — orchestrator for the three-layer view
  - `EffortGradientChart.tsx` — the story layer (effort color mapping, terrain, traces)
  - `StreamLab.tsx` — raw data layer with full traces and zone overlays
  - `PlanComparisonCard.tsx` — planned vs actual summary
  - `CoachMoments.tsx` — moment markers + tap-to-discuss (RSI-Beta, $25 only)

### Computation Strategy

Analysis computed on-demand per request (not cached). Phase 2 perf tests confirm <100ms for typical runs, <500ms for ultra-length. No caching needed for v1.

### Coach Interaction Flow (RSI-Beta)

1. Athlete taps a moment (or any region) on the canvas
2. Frontend sends: `{ activity_id, time_range: [start_s, end_s], question?: string }`
3. Backend assembles context: analysis result for that region + athlete history + training context + tier provenance + applicable OutputMetricMeta entries
4. Routes to Gemini Flash (simple observation) or Opus 4.5 (deep analysis)
5. Trust contract rules applied: cross-run suppression if Tier 4, ambiguous metric neutral language, confidence gate
6. Response renders as a coach card overlaying the canvas
7. Athlete can follow up (conversation mode) or dismiss
8. If no custom question and same moment type: check response cache before LLM call

---

## RSI-Alpha Acceptance Criteria (Pass/Fail)

Every criterion below is a testable assertion. RSI-Alpha is not complete until all pass.

### AC-1: Analysis Endpoint
- `GET /v1/activities/{id}/stream-analysis` returns 200 with `StreamAnalysisResult` JSON when stream data exists and user owns the activity.
- Returns 404 when activity not found or not owned by current user.
- Returns 200 with `{"status": "pending"}` (no analysis) when `stream_fetch_status` is not `success`.
- Returns 200 with `{"status": "unavailable"}` when `stream_fetch_status == "unavailable"`.
- Response includes all fields: `segments`, `drift`, `moments`, `plan_comparison`, `channels_present`, `channels_missing`, `point_count`, `confidence`, `tier_used`, `estimated_flags`, `cross_run_comparable`.

### AC-2: Effort Gradient
- Per-second effort intensity is computed using the tier-appropriate formula (ADR-064).
- Effort maps to a continuous color gradient: HSL blue (low) → amber (moderate) → red (high) → deep crimson (max). Exact color stops defined in ADR-064.
- When `cross_run_comparable == false` (Tier 4), a visible caveat label reads: "Effort colors are relative to this run" (or approved equivalent).
- Gradient renders as smooth visual (not discrete block steps visible to the eye).

### AC-3: Unified Crosshair
- One crosshair spans all visible trace layers (HR, pace, elevation, cadence, grade — whichever are active).
- Hover/tap on any point shows exact values for every visible channel at that timestamp.
- Crosshair position syncs between Story view and Lab view.

### AC-4: Story-Layer Toggles
- Cadence and grade are toggleable ON/OFF in the Story layer (not only in Lab).
- Default state: HR + pace + elevation visible. Cadence and grade OFF.
- Toggle state persists within the session (does not reset on scroll/resize).

### AC-5: Terrain Fill
- Elevation profile renders as a filled area at the bottom of the canvas.
- Grade severity is indicated by fill color variation (flat = neutral, moderate grade = amber, steep = red). Exact thresholds defined in ADR-064.

### AC-6: Segment Overlay
- Detected segments render as colored background bands behind the trace lines.
- Colors: warmup (amber), work (red), recovery (green), cooldown (blue), steady (gray). Exact hex values in component theme constants.
- Bands align with segment `start_time_s` / `end_time_s` from analysis result.

### AC-7: Plan Comparison Card
- Card renders when `plan_comparison` is non-null in analysis result.
- Shows: planned vs actual duration, distance, pace. Interval count match when available.
- Card is hidden when no linked plan exists.

### AC-8: Confidence + Tier Badge
- Badge renders on every canvas view.
- Shows tier label (e.g., "Tier 1: Threshold HR", "Tier 4: Stream-Relative") and confidence as percentage.
- When `cross_run_comparable == false`, Tier 4 caveat is visible (per AC-2).

### AC-9: Lab Mode
- Lab toggle switches the canvas to full-precision data mode.
- All `channels_available` render as individual labeled traces.
- Zone overlays use the athlete's own physiological data (from `AthleteContext`: `threshold_hr`, `max_hr`, `resting_hr`) — NOT population defaults.
- When no physiological data exists, zone overlay is hidden (not shown with population defaults).
- Segment table shows: type, start time, end time, duration, avg pace, avg HR, avg cadence, avg grade.
- Drift metrics displayed: cardiac drift %, pace drift %, cadence trend.

### AC-10: Loading States
- `pending` / `fetching` → loading spinner with "Stream data loading..." text.
- `failed` → retry hint ("Stream data unavailable. Tap to retry.").
- `unavailable` → stream panel hidden entirely (manual activity).
- `success` → canvas renders.

### AC-11: Rendering Performance
- Initial canvas render completes in < 2 seconds for a 3,600-point (1-hour) stream on mobile viewport (375px width).
- Scroll/pan interaction maintains ≥ 30fps on mobile.
- Downsampling reduces display points to ≤ 500 via LTTB (or equivalent per ADR-064).

### AC-12: No Coach Surface in RSI-Alpha
- No LLM calls are made from the canvas in RSI-Alpha.
- No moment markers are rendered on the canvas.
- No "tap to discuss" interaction exists.
- Coach functionality is entirely absent — not hidden behind a paywall, not grayed out.

---

## Build Plan Priority Reconciliation

The build plan priority order is:
1. Monetization tier mapping (revenue unlock)
2. Phase 4 (50K Ultra)
3. Phase 3B (when narration quality gate clears)
4. Phase 3C (when data/stat gates clear)

**RSI-Alpha fits the current priority stack for two reasons:**

1. **RSI-Alpha creates the feature differentiation that monetization tiers are built on.** The $15 tier gets Story + Lab. The $25 tier gets Coach (RSI-Beta). Without the canvas, there is no visible $15-vs-$25 distinction for stream analysis. Shipping RSI-Alpha is prerequisite infrastructure for the monetization tier mapping.

2. **RSI-Alpha is zero-token, zero-gate.** Unlike Phase 3B (gated on narration accuracy accrual) and Phase 3C (gated on 3+ months data), RSI-Alpha has no external dependency. It can ship immediately on the stable Phase 2 base while gates accrue for other priorities.

**Explicit ordering:**
- RSI-Alpha ships next (creates tier differentiation)
- Monetization tier mapping ships after or in parallel (consumes the differentiation RSI-Alpha creates)
- RSI-Beta ships when Gates 4 + 5 clear (moment scoring spec + trust contract extension)
- Phase 4, 3B, 3C follow their existing gate conditions

---

## RUN_SHAPE_VISION Alignment Checklist

| Vision Requirement | Proposal Coverage | Status |
|---|---|---|
| One canvas, not a dashboard | Three-layer progressive disclosure on single canvas | ✓ Aligned |
| Unified crosshair across all layers | AC-3 | ✓ Specified |
| Story-layer toggles for secondary traces | AC-4 (cadence, grade toggleable in Story, not hidden in Lab) | ✓ Specified |
| Elevation as subtle fill, not competing line | AC-5 (terrain fill with grade-aware color) | ✓ Specified |
| F1 telemetry aesthetic | ADR-064 rendering tech decision required | ⏳ Gate 1 |
| Chart must be excellent with no AI | AC-12 (no coach surface in RSI-Alpha) — canvas quality stands alone | ✓ Specified |
| Comparison overlay ("addictive") | Deferred — requires route/workout matching infra. Tracked for RSI-Gamma. | ⏳ Deferred |
| Coach moments sparse and meaningful | Gate 4 (moment scoring spec) | ⏳ Gate 4 |
| "Something they couldn't have known" trust bar | Trust contract §3 confidence suppression + Gate 4 scoring spec | ⏳ Gate 4+5 |

---

## Alignment with Build Plan Principles

| Principle | How This Proposal Honors It |
|---|---|
| N=1 over population norms | Tier provenance visible. Zone overlays use athlete's own zones. Effort gradient is tier-aware. Tier 4 caveat prevents false precision. |
| No template narratives | RSI-Beta moments filtered by deterministic interest scoring. Coach narration generated fresh, never cached (except repeat-view optimization for identical deterministic moments). Silence over noise. |
| Daily adaptation is the monetization moat | The story layer ($15) is better than any competitor's visualization. The coach layer ($25) is the retention moat. |
| The system INFORMS, the athlete DECIDES | The canvas presents the story. The coach discusses it. Neither prescribes action — the athlete interprets. |
| Coach trust is earned, not assumed | Moments must pass surprise/novelty/actionability test. Trust validation via founder review of first 50 narratives. Kill switch if quality degrades. No coach surface ships until trust gates clear. |
| No metric is assumed directional | Canvas trust contract §2: ambiguous metrics (`cardiac_drift_pct`, `pace_drift_pct`, `cadence_trend_bpm_per_km`, `plan_execution_variance`) produce neutral language only. |
| Paid tier = N=1 intelligence | $15 gets the deterministic story. $25 gets the personalized, LLM-powered coaching. Clear boundary. |
| Suppression over hallucination | Trust contract §3: confidence < 0.3 or missing channels → suppress. FOC §5 applied to all canvas surfaces. |

---

*This proposal represents the shared vision from founder-builder discussion on February 14, 2026.*
*Advisor review completed February 14, 2026 — all findings addressed in this revision.*
*No code should be written until Hard Gates 1-3 and 6 are cleared and the founder has approved the final scope.*
