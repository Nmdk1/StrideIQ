# Build Spec: Home Page & Activity Detail Page
## February 15, 2026 (with shipped-state delta — April 19, 2026)

**Read first:** `docs/PRODUCT_MANIFESTO.md`, `docs/RUN_SHAPE_VISION.md`, `docs/SITE_AUDIT_LIVING.md`, `docs/wiki/activity-processing.md`, `docs/wiki/frontend.md`

> **Status (April 19, 2026):** the Activity Detail half of this spec has been
> **superseded by the Phase 1-4 rebuild** (CanvasV2 hero + 3-tab restructure +
> unskippable FeedbackModal + ShareDrawer). Changes A1, A4, A6 below are
> historical context only — the canvas they targeted is no longer rendered
> on run activities. See the **"Shipped After Original Spec — Activity-Page
> Rebuild Phases 1-4"** section near the bottom of this file for the
> current shipped state. The Home Page half (H1-H4) is still partially in
> force; see the same section for the home delta.

---

## The Design Principle (applies to every intelligence surface)

Every page follows the same loop:

1. **Visual catches the eye** — chart, gradient, shape. The runner's eye goes there first.
2. **Interact** — hover, drag, explore. The visual is tactile, not static.
3. **Wonder** — "what does this mean?" The visual creates the question.
4. **Read** — the narrative answers the question they just formed. Not before. Not instead. After the visual plants the seed.
5. **Explore deeper** — back to the visual with new understanding. The narrative reframes what they're looking at.
6. **Judge** — "is this real? does this match what I felt?" Trust builds or breaks here.
7. **Habit** — over time, the visual alone is enough. The runner reads the shape of their effort like reading a sentence. But they only got there because the narrative built the bridge from "what am I looking at" to "I know what this means."

The narrative isn't decoration on top of the chart. The narrative is what teaches the athlete to read the chart. Without it, the visual is pretty but opaque. Without the visual, the narrative is useful but forgettable. Together, they build fluency.

This is why the current site doesn't work:
- Training Load has visual but no narrative (PMC chart, no interpretation)
- Progress has narrative but no visual (good data in text cards, nothing for the eye)
- Activity Detail has both but they're disconnected (canvas up top, metric labels below, no bridge)

---

## Scope: Two Screens Only

The home page and the activity detail page. These are the daily touchpoints.
Everything else (progress, insights, analytics, training load, calendar) is
Layer 2 — addressed after these two screens feel right.

---

## HOME PAGE

### What it should feel like

The athlete finishes a run, opens the app. They immediately see the shape of
what they just did — the pace curve colored by effort. Below it, one paragraph
that synthesizes everything the system knows into the single thing that matters
today. Below that, today's workout (if any) in plain text. That's the above-
the-fold experience.

### Change H1: Gradient Pace Chart as Hero

**Replaces:** The current `MiniEffortCanvas` gradient ribbon (the colored strip
nobody understands).

**What it is:** A compact (~100-120px tall) pace line chart where the line
itself is colored by effort intensity. Cool blues for easy effort, warm ambers
for moderate, deep crimson at the limit. Pace only — no HR overlay on the mini.
Subtle elevation fill behind the line (optional, low priority).

The shape IS the identity of the run. A sawtooth interval session, a flat easy
run, a descending progressive long run — you see the shape and know which run
it was instantly.

**Backend work required:**
- File: `apps/api/routers/home.py` (the `/v1/home` endpoint)
- Currently returns `effort_intensity: number[]` (~500 LTTB-downsampled points)
- Must also return `pace_stream: number[]` (~500 LTTB-downsampled points)
- Source: `velocity_smooth` from `StreamAnalysisResult` → convert to pace (s/km or s/mi)
- Same LTTB downsampling approach already used for effort_intensity
- Add to `LastRun` response model

**Frontend work required:**
- File: `apps/web/components/home/LastRunHero.tsx`
- Replace `MiniEffortCanvas` (canvas-based colored rectangles) with a
  `MiniPaceChart` — either SVG path or Recharts Line with `<linearGradient>`
- Each point on the pace curve gets its color from the corresponding
  `effort_intensity[i]` value via the existing `effortToColor()` utility
  in `apps/web/components/activities/rsi/utils/effortColor.ts`
- Full-bleed (edge to edge within the card/link container)
- Height: ~100-120px
- Y-axis: pace (inverted — faster pace at top, like the full canvas)
- No axis labels, no gridlines. Clean.
- Below the chart: single line of metrics (run name, distance, duration, pace, HR)
  separated by middots. Already partially implemented.
- Entire component is a link to `/activities/{activity_id}`

**Frontend types update:**
- File: `apps/web/lib/api/services/home.ts`
- Add `pace_stream?: number[] | null` to `LastRun` interface

**Acceptance criteria:**
1. Home page shows a pace curve (not a colored ribbon) when `stream_status === 'success'`
2. The pace line is colored by effort intensity (not flat blue, not a single color)
3. The chart is full-width within its container
4. Tapping anywhere on the hero navigates to the activity detail page
5. Fallback: when `stream_status !== 'success'`, show the metrics-only card (existing behavior)
6. Units respect the `useUnits()` hook (pace in min/mi or min/km per user setting)

---

### Change H2: Merge Intelligence Into One Voice — ✅ SHIPPED (Mar 9)

**Status:** Per-field lane injection shipped. `morning_voice` draws from fingerprint findings; `coach_noticed` draws from daily rules/wellness/signals. Overlap eliminated.

**Original spec (for reference):**
**Replaced:** The separate `CoachNoticedCard` and `morning_voice` text on the
home page. Were two parallel systems with weak data sharing.

**The problem:**
- `compute_coach_noticed` (file: `apps/api/routers/home.py`, lines ~993-1072)
  is a deterministic pipeline that queries correlations, home signals, insight
  feed cards, and hero narrative. Returns a single text string.
- `coach_briefing` (same file, lines ~670-915) is an Opus LLM call that
  receives the athlete brief + InsightLog entries and generates 7 fields
  including `morning_voice` and `coach_noticed`.
- These two systems do NOT share data. The Opus call does NOT receive the
  output of `compute_coach_noticed`.

**The fix:**
1. Run `compute_coach_noticed` FIRST
2. Feed its output into the Opus prompt as additional context:
   `=== DETERMINISTIC INTELLIGENCE (from your analytical tools) ===\n{coach_noticed_output}`
3. Update the `morning_voice` field description to:
   "Synthesize ALL available intelligence — the deterministic analysis above,
   the athlete brief, recent insights, today's context — into one paragraph.
   This is the voice of the athlete's data. It must reflect the most important
   signal from any source. 40-280 characters."
4. Remove the separate `coach_noticed` field from the schema (or keep it
   internal but don't render it separately on the frontend)

**Frontend work:**
- File: `apps/web/app/home/page.tsx`
- Remove the `CoachNoticedCard` component rendering
- The `morning_voice` paragraph becomes the single text element below the
  hero chart. Style: `text-base text-slate-300 leading-relaxed`. No card
  wrapper. No header. Just the paragraph.

**Acceptance criteria:**
1. `morning_voice` output demonstrably incorporates intelligence from the
   deterministic pipeline (correlations, signals, insight feed) — not just
   the athlete brief
2. No separate Coach Noticed card on the home page
3. One paragraph, one voice, below the hero chart
4. The merged prompt still respects all existing trust-safety constraints
   (no sycophancy, no causal claims, specific numbers, 40-280 chars)

---

### Change H3: Strip Workout to Plain Text

**Current state:** Workout section has Card wrapper, CardHeader, CardContent,
icon box, badge, Sparkles icon, "Ask Coach" link.

**Target state:**
```
Today
Threshold — 6x800m at 6:32/mi
This threshold session follows two easy days — you should feel ready for quality work.
Week 4 of 8 · Build Phase
```

No card chrome. No icon box. No badge. No Sparkles.

- Small caps label ("Today")
- Workout title (bold, colored by effort category)
- `workout_why` sentence (slate-400, relaxed leading)
- Week/phase context (small, slate-500)

**File:** `apps/web/app/home/page.tsx` — the workout section

**Acceptance criteria:**
1. No Card, CardHeader, CardContent wrappers
2. No icon boxes or decorative elements
3. `workout_why` rendered as plain text
4. If no workout today, this section doesn't render at all (no "Rest Day" card)

---

### Change H4: Clean Up Below the Fold

After the hero chart, voice paragraph, and workout, the only things on the
home page should be:

1. Week strip (the compact day-chip row — keep as-is)
2. Check-in prompt (only if not done today — keep as-is)
3. Race countdown (if race is set — keep as-is)

**Remove from home page:**
- CoachNoticedCard (absorbed into morning_voice — see H2)
- Any duplicate intelligence cards

---

## ACTIVITY DETAIL PAGE

### What it should feel like

The athlete taps into a run. The canvas fills the top — gradient pace line,
HR overlay, elevation fill, segment bands. They hover and drag, inspecting
every second of their effort. Below the canvas, 2-4 coaching moments explain
what happened in plain language, anchored to timestamps. The athlete reads a
moment, then drags back to that timestamp to SEE it. The narrative teaches
them to read the visual. Below that: reflection (one tap), metrics ribbon,
and a collapsible details section for everything else.

### Change A1: Gradient Pace Line on the Canvas

**The single biggest visual differentiator from Strava.** Currently the pace
line is a flat `#60a5fa` blue stroke — visually identical to every other
running app.

**The fix:** Apply an effort-colored gradient to the pace `<Line>` in the
Recharts chart. The approach:

1. Define an SVG `<linearGradient>` in the chart's `<defs>`
2. Map each data point's effort_intensity value to a color stop using
   `effortToColor()` from `apps/web/components/activities/rsi/utils/effortColor.ts`
3. Apply the gradient as the stroke of the pace Line: `stroke="url(#effortGradient)"`

**File:** `apps/web/components/activities/rsi/RunShapeCanvas.tsx`

**Acceptance criteria:**
1. The pace line changes color along its length based on effort intensity
2. Cool blues for easy effort → warm ambers → deep crimson at the limit
3. The gradient is smooth (not stepped blocks)
4. HR line remains its current separate color (not gradient)
5. Elevation fill remains its current style
6. The gradient works in both Story and Lab modes

---

### Change A2: HR Sanity Check

**The problem:** When wrist-based HR glitches (inverted data, drops to 0,
spikes above max), the effort-based coloring and segment classification
become misleading. Yesterday's run had inverted HR — a 6:47/mi pace was
classified as "Recovery" because the HR sensor reported low values.

**The fix (backend):**
- File: `apps/api/services/run_stream_analysis.py`
- Add an HR sanity check during stream analysis, before effort calculation
- Detection heuristics:
  - HR inversely correlated with pace (r < -0.3 when it should be positive)
  - HR below resting for sustained periods during hard effort
  - HR above max_hr for sustained periods
  - Sudden drops to 0 or near-0
  - Standard deviation of HR unreasonably low or high
- When HR fails the sanity check:
  - Flag `hr_reliable: false` in the analysis result
  - Fall back to pace-based effort estimation (Tier 4 behavior)
  - Segment classification uses pace thresholds instead of HR zones
  - Add a note to the response: "Heart rate data appears unreliable for
    this activity. Effort estimation based on pace."

**Frontend:**
- When `hr_reliable === false`, show a small note below the canvas:
  "HR data appears unreliable — effort colors based on pace"
- The gradient still works (using pace-derived effort), it's just honest
  about the source

**Acceptance criteria:**
1. An activity with inverted HR (pace fast, HR low) is detected as unreliable
2. Effort intensity falls back to pace-based estimation
3. Segment classifications use pace thresholds, not HR zones
4. The frontend shows a brief note about HR reliability
5. Activities with normal HR are unaffected

---

### Change A3: Moment Narratives (LLM, Not Templates)

**Current state:** Moments are metric labels — "Grade Adjusted Anomaly: 4.7",
"Pace Surge: 15.3". The athlete doesn't know what these mean.

**Target state:** Each moment is a coaching sentence:
- "Your pace dropped here but the 4.7% grade explains it — your effort was
  steady through this climb."
- "Your cadence shifted from 168 to 174 at 42 minutes — your body found a
  more efficient gear as fatigue set in."
- "Heart rate drifted 8% over this steady segment while pace held — a sign
  of building fatigue. Your body was working harder to maintain the same
  output."

**The approach:** Batch LLM call. One call per activity, all moments together.

**Backend work:**
- File: `apps/api/services/run_stream_analysis.py` (or a new service)
- After moments are detected, make a single LLM call with:
  - All detected moments (type, timestamp, value, surrounding context)
  - The athlete's profile (zones, typical patterns)
  - The segment context (what type of segment the moment occurred in)
  - Instruction: "For each moment, write one sentence a runner would
    understand. Explain what happened and why it matters. No jargon. No
    metric labels. Be specific about the numbers."
- Cache the narrative alongside the moment data in `CachedStreamAnalysis`
- Use a fast/cheap model (Gemini Flash or Haiku) — the task is translation,
  not complex reasoning

**Moment data model update:**
```python
@dataclass
class Moment:
    type: str
    index: int
    time_s: int
    value: Optional[float] = None
    context: Optional[str] = None
    narrative: Optional[str] = None  # NEW — LLM-generated coaching sentence
```

**Frontend:**
- File: `apps/web/components/activities/rsi/CoachableMoments.tsx`
- Display `moment.narrative` instead of (or prominently above) the type + value
- If narrative is null (old cached data), fall back to current display

**Timing:** Generate during stream analysis (async, after sync). The moment
narratives should be ready by the time the athlete opens the activity page.
If the athlete opens the page before generation completes, show the metric
labels as fallback and refresh when ready.

**Acceptance criteria:**
1. Each moment displays a coaching sentence, not a metric label
2. Sentences are specific (cite numbers, timestamps, context)
3. Sentences are unique per moment — no repeated phrasing patterns
4. One LLM call per activity (batched), not one per moment
5. Narratives are cached — no LLM call on page load
6. Fallback to metric labels when narrative is not yet generated

---

### Change A4: Remove Old Splits Chart, Keep Splits Table

**Current state:** Section 10 of the activity detail page renders BOTH
`SplitsChart` and `SplitsTable` inside the same container.

**The fix:** Remove the `<SplitsChart>` component call. Keep `<SplitsTable>`.
The splits table shows accurate lap times, paces, and metrics — that data is
valuable. The chart is redundant with the Run Shape Canvas.

**File:** `apps/web/app/activities/[id]/page.tsx`, lines ~389-398

**Current code:**
```tsx
{splits && splits.length > 0 && (
  <div className="bg-slate-800/50 rounded-lg p-6 mb-6 border border-slate-700/50">
    <h2 className="text-lg font-bold text-white">Splits / Laps</h2>
    <div className="mt-4">
      <SplitsChart splits={splits} className="mb-4" />  ← REMOVE THIS
      <SplitsTable splits={splits} />                    ← KEEP THIS
    </div>
  </div>
)}
```

**Acceptance criteria:**
1. No `SplitsChart` rendered on the activity detail page
2. `SplitsTable` still renders with accurate lap data
3. The `SplitsChart` component file can remain (not deleted) — just not used here

---

### Change A5: Fix Cadence in Segment Table

**Current state:** The Lab Mode segment table (inside `RunShapeCanvas.tsx`,
`LabModePanel`) shows "--" for cadence in every segment row.

**The fix:** Wire cadence data from the stream analysis into the segment
table rows. The cadence data exists (it's a toggle on the canvas chart) but
isn't being passed to the segment table.

**File:** `apps/web/components/activities/rsi/RunShapeCanvas.tsx`

**Acceptance criteria:**
1. Segment table rows show average cadence (spm) when cadence data exists
2. Shows "--" only when cadence data is genuinely unavailable

---

### Change A6: Collapse Lower Sections

**Current activity page scroll order:**
1. Header (name, date)
2. Run Shape Canvas ← above the fold
3. Coachable Moments ← above the fold
4. Reflection Prompt ← above the fold
5. Metrics Ribbon ← above the fold
6. Plan Comparison
7. Workout Type Classification
8. Why This Run + Context Analysis
9. Compare to Similar
10. Splits Table

**Sections 6-10 should collapse into an expandable "Details" section.**
One tap to expand. The above-the-fold experience is:
Canvas → Moments → Reflection → Metrics. Clean. Focused. Visual → Narrative.

**Acceptance criteria:**
1. Sections 6-10 are hidden behind a "Show details" toggle
2. The toggle remembers state per session (or defaults to collapsed)
3. All content still accessible — nothing is removed

---

## HR Zone Card (Lab Mode)

The segment table in Lab Mode that classifies segments as Warmup/Recovery/
Steady/Cooldown is addressed by Change A2 (HR Sanity Check). When HR is
unreliable, classifications fall back to pace-based thresholds. This prevents
a 6:47/mi pace from being labeled "Recovery" due to sensor glitches.

---

## Build Order

### Layer 1 (core experience — ship together)
1. **A1** — Gradient pace line on the canvas (the visual differentiator)
2. **H1** — Gradient pace chart on home page (needs A1's approach + backend API change)
3. **A4** — Remove old splits chart (5 minutes, pure deletion)
4. **H3** — Strip workout chrome (10 minutes, straightforward)
5. **H4** — Clean up below the fold (remove CoachNoticedCard)

### Layer 2 (intelligence — ship together)
6. **H2** — Merge intelligence into one voice (backend wiring)
7. **A3** — Moment narratives (backend LLM call + frontend)
8. **A2** — HR sanity check (backend, protects gradient accuracy)
9. **A5** — Fix cadence in segment table (small frontend fix)

### Layer 3 (polish)
10. **A6** — Collapse lower sections on activity page

Each layer is committed and verified green before moving to the next.

---

## Shipped After Original Spec (Apr 4, 2026)

These surfaces were designed and built after the Feb 15 spec, extending
the home and activity pages beyond the original scope:

### Change H5: Wellness Row — ✅ SHIPPED (Apr 4)

**What it is:** A horizontal strip between coach briefing and workout
showing the athlete's Garmin wellness state: Recovery HRV (5-min peak),
Overnight Avg HRV, Resting HR, Sleep hours + Garmin sleep score. Each
metric shows value, status (low/normal/high), and personal 30-day range.

**Design principle:** Raw numbers always shown. Interpretation layered on
top ("low / normal / high"). An info tooltip explains the difference
between Recovery HRV and Overnight Avg HRV.

**Backend:** `_build_garmin_wellness()` in `routers/home.py`. Queries
today's `GarminDay` + 30-day history for personal ranges.

**Frontend:** `WellnessRow` and `HrvTooltip` components in `app/home/page.tsx`.

### Change H6: Mindset Check-in — ✅ SHIPPED (Apr 4)

`enjoyment_1_5` and `confidence_1_5` added to `QuickCheckin` as optional
collapsible section. Standalone `/checkin` page deprecated (redirects to
`/home`). All check-in now happens on the home page.

### Change A7: Pre-Activity Wellness Stamps — ✅ SHIPPED (Apr 4)

**What it is:** Every activity stamped with the athlete's wellness going
into it: `pre_sleep_h`, `pre_sleep_score`, `pre_resting_hr`,
`pre_recovery_hrv`, `pre_overnight_hrv`. Stamped at ingestion time from
`GarminDay`. Retro-stamped when health data arrives after activity.

**Backend:** `services/wellness_stamp.py`. Wired into all four ingestion
paths + admin backfill endpoint. Migration: `wellness_stamp_001`.

**Frontend:** "Going In" section on activity detail page showing
wellness context before each run.

**Purpose:** Enables wellness-vs-performance correlation research
alongside HR, cadence, and pace.

---

## Shipped After Original Spec — Activity-Page Rebuild Phases 1-4 (Apr 19, 2026)

**This section supersedes Changes A1, A4, A6 above for run activities.**
The original canvas those changes targeted (`RunShapeCanvas.tsx`) is no
longer rendered on run activities. It has been replaced by `CanvasV2`
running in `chromeless` mode as the page hero, with the rest of the page
restructured around it. Authoritative source files:
`apps/web/components/canvas-v2/`, `apps/web/components/activities/feedback/`,
`apps/web/components/activities/share/`, `apps/web/app/activities/[id]/page.tsx`,
`docs/wiki/activity-processing.md`, `docs/wiki/frontend.md`.

### Phase 1 — CanvasV2 as the Activity Hero — ✅ SHIPPED (Apr 19)

- `CanvasV2` gains a `chromeless` prop that suppresses internal title /
  subtitle / help block and moves `CanvasHelpButton` to a minimal
  right-aligned slot. Run activities render `CanvasV2` chromeless as
  the hero, replacing `RunShapeCanvas` (preserved on disk for reference).
- `TerrainMap3D.tsx` — Mapbox GL real 3D terrain with `pitch: 62`,
  `bearing: -20`, DEM exaggeration `3.0`. Three-layer route (white
  casing + emerald glow + deep emerald line) for contrast on light
  terrain. Built-in `hillshade` left untouched (earlier
  `setPaintProperty` attempts threw "cannot read properties of
  undefined (reading 'value')"; visibility comes from terrain
  exaggeration plus the route layers). `mapbox-gl/dist/mapbox-gl.css`
  imported statically at top of file (was the cause of the production
  "completely dark map" regression). `NavigationControl` mounted for
  rotate / tilt / zoom. Desktop-only fullscreen toggle. Initial render
  zoom tightened so the course fills the frame. Caddy CSP allows
  Mapbox tile/style/sprite domains in `connect-src` and `blob:` in
  `worker-src`/`child-src`; CSP changes require a Caddy container
  restart, not just `caddy reload` (Docker bind-mount caching
  artefact on Linux).
- `StreamsStack.tsx` — chart order locked to **HR top, pace middle,
  elevation bottom**. Pace `robustDomain` switched from percentile
  clipping to **Tukey's fence (IQR, k=3.0)** to preserve real pace
  variation while clipping spikes. Elevation uses the smoothed series
  the splits tab uses (less pointy).
- Distance moved from inline label to the **leftmost moment-readout
  hover card** with two-decimal miles and a secondary time line.

### Phase 2 — Activity Tabs 6 → 3 — ✅ SHIPPED (Apr 19)

- `Splits` (no map; the hero already has it).
- `Coach` (absorbs `RunIntelligence`, `FindingsCards`, `WhyThisRun`,
  `GoingInCard`, `AnalysisTabPanel`, and `activity.narrative`).
- `Compare` (placeholder; redesign sequenced behind the canvas — see
  `docs/specs/COMPARE_REDESIGN.md`).
- The `RuntoonCard` is no longer rendered at the bottom of the page
  (lives in the ShareDrawer now).

### Phase 3 — Unskippable FeedbackModal + ReflectPill — ✅ SHIPPED (Apr 19)

- `FeedbackModal` has three sections: reflection text, RPE,
  workout-type confirmation. **No escape hatch** — no X, Cancel, Skip,
  or backdrop-click dismissal. Save & Close stays disabled until all
  three are complete.
- Auto-classified workout types require explicit "Looks right"
  confirmation: `workoutTypeAcked` is only pre-true when
  `existingWorkoutType.is_user_override === true`.
- `useFeedbackTrigger` auto-opens the modal once per recent,
  incomplete run, gated on a `localStorage` flag so it doesn't keep
  popping up after save.
- Edits remain available later via the `ReflectPill` in the page
  chrome (which sources status from `useFeedbackCompletion`).

### Phase 4 — Share is a Pull Action — ✅ SHIPPED (Apr 19)

- `ShareButton` page-chrome pill (next to `ReflectPill`, run-only)
  opens a `ShareDrawer` that hosts the `RuntoonCard` and a roadmap
  placeholder for future share styles (photo overlays, customizable
  stats, modern backgrounds, flyovers). Drawer dismisses via close
  button, Escape, or backdrop click.
- `RuntoonSharePrompt` removed from `app/layout.tsx` — was polling
  `/v1/runtoon/pending` every 10s and sliding up on every recent run,
  explicitly rejected as push-style sharing. Component file preserved
  on disk for reference / rollback; intentionally not imported. Static
  regression test `apps/web/__tests__/layout-no-runtoon-prompt.test.ts`
  enforces this.

### Implications for the Original Spec

- **A1 (gradient pace line on the old canvas)** — superseded. The
  effort-colored gradient idea lives on inside `CanvasV2`'s
  `StreamsStack` and effort-colored route, but on a different
  rendering substrate.
- **A3 (moment narratives)** — still valuable for the Coach tab,
  carried forward.
- **A4 (remove old splits chart)** — superseded; `Splits` tab now
  shows the table only with no map.
- **A6 (collapse lower sections)** — superseded; the page has no
  "lower sections" anymore — everything is hero + 3 tabs.
- **A2 (HR sanity check)** and **A5 (cadence in segment table)** —
  still relevant inside `CanvasV2`'s effort and segment logic.

---

## What This Does NOT Cover (future sessions)

- ~~Intelligence page consolidation~~ — resolved: `/insights` and `/discovery` redirect to `/manual`
- Progress page chart additions
- ~~Navigation changes~~ — resolved: Manual in primary nav, three pages deprecated
- Recent Runs strip on home page
- Home page state machine (pre-workout / rest day states)
- Morning voice prompt refinements beyond the merge
- Coach page changes (it works — don't touch it)
- Calendar changes (it works — don't touch it)
- **Compare tab redesign** — placeholder; sequenced behind canvas
  vocabulary. See `docs/specs/COMPARE_REDESIGN.md`.

---

## Reference Documents

- `docs/PRODUCT_MANIFESTO.md` — the soul of the product
- `docs/RUN_SHAPE_VISION.md` — the visual vision
- `docs/SITE_AUDIT_LIVING.md` — current state of everything
- `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` — design decisions and HRV display standard
- `docs/FOUNDER_OPERATING_CONTRACT.md` — how to work with this founder
- `docs/wiki/activity-processing.md` — current shipped state of CanvasV2, terrain, charts, share/feedback
- `docs/wiki/frontend.md` — current shipped state of activity-page composition, components, contexts
