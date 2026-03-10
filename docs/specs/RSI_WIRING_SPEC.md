# RSI Wiring Spec — Layers 1-3

**Status:** Approved — founder reviewed 2026-02-14, all decisions locked
**Grounded in:** Real baseline data from 2026-02-14 Morning Run (Tier 1, 5253 points, 0.95 confidence)
**Design decisions from:** Builder + Advisor synthesis session 2026-02-14

---

## Guiding Principles

1. **The canvas is the product.** The effort gradient is the first thing the athlete sees after a run.
2. **Data doesn't hallucinate.** The canvas shows what the data says. No AI text in the hero.
3. **Silent upgrade.** Metrics card → canvas hero as streams become available. No loading spinners, no "pending" states.
4. **Suppression over noise.** If coachable moments don't have confidence, show nothing.
5. **The reflection prompt replaces the perception prompt.** One tap, three seconds, permanent.

---

## Layer 1: Post-Run Canvas on Home Page

### What changes

When the most recent activity has `stream_fetch_status === 'success'`, the home page hero becomes a compact Run Shape Canvas showing the effort gradient of that run.

### Backend: Extend `/v1/home` response

Add a `last_run` object to the `HomeData` response:

```
last_run: {
  activity_id: string
  name: string
  start_time: string          // ISO datetime
  distance_m: number
  moving_time_s: number
  average_hr: number | null
  stream_status: 'success' | 'pending' | 'fetching' | 'unavailable' | null
  effort_intensity: number[] | null   // Only when stream_status === 'success'
  tier_used: string | null
  confidence: number | null
  segments: Segment[] | null          // For segment band overlay
  pace_per_km: number | null          // Derived from distance/time
} | null
```

**Key decisions:**
- `effort_intensity` array is included directly (LTTB downsampled to ~500 points server-side to keep payload reasonable)
- Only the most recent activity within **24 hours** — if latest activity is >24h old, `last_run` is `null` (activity still accessible via Recent Runs strip)
- `null` when no activities exist at all
- Segments included for optional segment band coloring on the mini canvas

**Implementation:** Add to the existing `get_home_data()` function in `routers/home.py`. Query latest Activity by `start_time desc` within 24h window, join ActivityStream if `stream_fetch_status='success'`, serve from cached `StreamAnalysisResult`.

**Analysis caching (DECIDED):** Cache full `StreamAnalysisResult` in DB. Compute once at ingest time, serve on every Home + Activity page load. Recompute only on: new stream payload, analysis version bump, or manual reprocess. Include `analysis_version` field for deterministic invalidation.

### Frontend: `LastRunHero` component

New component rendered at the top of the home page when `last_run` exists and `stream_status === 'success'`:

```
┌─────────────────────────────────────────────┐
│  [Effort gradient canvas — full width]       │
│  ████████████████████████████████████████    │
│                                              │
│  Morning Run          8.2 mi   1:27:33      │
│  Today 9:48 AM        7:14/mi  Avg HR 115   │
│                                              │
│  [See Full Analysis →]                       │
└─────────────────────────────────────────────┘
```

**Behavior:**
- Effort gradient rendered via Canvas 2D (same `effortToColor` mapping from RSI-Alpha)
- Compact metrics ribbon below the gradient (single row, not card grid)
- Tap anywhere → navigates to `/activities/{id}` (the deep dive)
- "See Full Analysis →" link for explicit navigation

**Silent upgrade:**
- When `stream_status !== 'success'` (pending or null), render a clean metrics-only card instead:

```
┌─────────────────────────────────────────────┐
│  Morning Run          8.2 mi   1:27:33      │
│  Today 9:48 AM        7:14/mi  Avg HR 115   │
│                                              │
│  [View Run →]                                │
└─────────────────────────────────────────────┘
```

- No "loading streams" indicator. No skeleton. Just a clean card that upgrades to a canvas on the next page load when streams are ready.
- `useHomeData()` already has `refetchOnWindowFocus: true` with 5-min stale time — the upgrade will happen naturally when the athlete returns to the app.

### AC-L1: Acceptance Criteria

| ID | Criterion | Test approach |
|----|-----------|--------------|
| L1-1 | `/v1/home` returns `last_run` with effort_intensity when streams are available | Backend integration test |
| L1-2 | `/v1/home` returns `last_run` with `stream_status: 'pending'` and `effort_intensity: null` when streams not yet fetched | Backend integration test |
| L1-3 | `/v1/home` returns `last_run: null` when athlete has no activities | Backend integration test |
| L1-4 | Home page renders effort gradient canvas when `effort_intensity` is present | Frontend test with fixture |
| L1-5 | Home page renders metrics-only card when `stream_status !== 'success'` | Frontend test |
| L1-6 | Tapping the canvas navigates to `/activities/{id}` | Frontend test |
| L1-7 | Effort gradient uses `effortToColor` mapping from RSI-Alpha | Visual verification |
| L1-8 | No loading spinner, "pending" text, or skeleton shown for stream states | Frontend test (negative assertion) |

---

## Layer 2: Activity Detail Page — Canvas as Centerpiece

### What changes

`/activities/[id]/page.tsx` restructured to lead with the Run Shape Canvas, with existing components reorganized beneath it.

### Page structure (top to bottom)

1. **Run Shape Canvas** (full width)
   - Story mode default (effort gradient + pace line + HR line)
   - Crosshair interaction, story toggles (cadence, grade)
   - Terrain fill
   - Tier badge
   - This is the existing `RunShapeCanvas.tsx` component from RSI-Alpha, wired in

2. **Coachable Moments** (below canvas)
   - Rendered from `moments` array in stream analysis
   - Each moment: type icon + timestamp + value
   - Expandable for future coach commentary (not in Layer 2)
   - **Gated:** Only shown when `confidence >= 0.8` AND `moments.length > 0`. Below that threshold or with no moments, section hidden entirely (no placeholders).

3. **Reflection Prompt** (permanent, below moments)
   - Three buttons: `Harder than expected` | `As expected` | `Easier than expected`
   - Single tap submits. Shows checkmark after submission.
   - Stores: `{ activity_id, athlete_id, response: 'harder' | 'expected' | 'easier', timestamp }` — no free text in v1
   - New lightweight endpoint: `POST /v1/activities/{id}/reflection`
   - Replaces current `PerceptionPrompt` component on this page

4. **Metrics Ribbon** (compact horizontal strip)
   - Distance | Duration | Pace | Avg HR | Elevation | Cadence
   - Single row, not 2x4 grid of cards
   - Secondary metrics (Max HR, temp) available via expand/tap

5. **Plan Comparison** (conditional)
   - Only rendered when `plan_comparison` is non-null in stream analysis
   - Shows planned vs actual duration, distance, pace, interval count

6. **"Why This Run?"** (existing component, stays)
   - `WhyThisRun` component already exists and is wired

7. **"Compare to Similar"** (existing button, stays)
   - Link to `/compare/context/{id}` already exists

8. **Splits Table** (secondary position)
   - Existing `SplitsChart` + `SplitsTable`, moved below canvas content

9. **Lab Mode** (toggle from canvas)
   - Zone overlays, segment table, drift metrics
   - Accessed via toggle button on the canvas

### Lifecycle States

The canvas section handles these states (matching ADR-063).
**Note:** This is page-specific UX, intentionally different from Home's silent-upgrade rule. On the Activity Detail page, the athlete has explicitly navigated to see this run — showing "Analyzing..." is appropriate because they're waiting for a specific result. On Home, silent upgrade avoids visual noise for ambient browsing.

- `stream_status === 'success'` → Full canvas
- `stream_status === 'pending' | 'fetching'` → "Analyzing your run..." with subtle pulse (NOT a spinner). Page-specific: athlete navigated here intentionally, so an in-progress state is expected and informative.
- `stream_status === 'unavailable'` → Section hidden entirely (manual activities without GPS)
- `stream_status === null` → Section hidden (pre-stream-era activities)

### AC-L2: Acceptance Criteria

| ID | Criterion | Test approach |
|----|-----------|--------------|
| L2-1 | Activity detail page renders RunShapeCanvas as the first content element | Frontend test |
| L2-2 | `useStreamAnalysis` hook fetches from `/v1/activities/{id}/stream-analysis` | Frontend test with mock |
| L2-3 | Moments section renders when confidence >= 0.8 AND moments.length > 0 | Frontend test |
| L2-4 | Moments section hidden when confidence < 0.8 OR moments empty | Frontend test (negative) |
| L2-5 | Reflection prompt renders three options, submits on tap | Frontend test |
| L2-6 | Reflection prompt hits `POST /v1/activities/{id}/reflection` | Backend + frontend test |
| L2-7 | Metrics displayed as compact ribbon, not card grid | Frontend test / visual |
| L2-8 | Plan comparison shown only when data exists | Frontend test |
| L2-9 | WhyThisRun and Compare to Similar remain in page | Frontend test |
| L2-10 | Splits table appears below canvas content | Frontend test |
| L2-11 | Canvas shows "Analyzing..." for pending streams, nothing for unavailable | Frontend test |
| L2-12 | No coach/LLM surface introduced (AC-12 preserved from RSI-Alpha) | Negative assertion |

---

## Layer 3: Home Page State Machine + Recent Runs

### What changes

The home page hero becomes context-aware. Below the hero, a Recent Runs strip shows the last 3-5 runs with mini effort gradients.

### State Machine

```
if (last_run exists AND within 24h AND last_run.stream_status === 'success')
  → State A: Canvas Hero (Layer 1 component)
  
else if (last_run exists AND within 24h AND last_run.stream_status !== 'success')
  → State A-degraded: Metrics Card (silent upgrade path)
  
else if (today.has_workout)
  → State B: Today's Workout Hero (existing component, promoted)
  
else if (coach_noticed exists)
  → State C: Coach Noticed Hero (existing component, promoted)
  
else
  → State D: Rest Day / Empty (intelligence signal or weekly summary)
```

**Time decay (DECIDED):** 24-hour freshness window. Runs older than 24h do not appear as the hero — they remain accessible via the Recent Runs strip below. This prevents a stale canvas from dominating Home when the athlete hasn't run in days.

### Recent Runs Strip

Below the hero (in all states), a horizontal strip of the last **4** runs:

```
┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐
│██████│  │██████│  │██████│  │██████│
│▓▓▓▓▓▓│  │▒▒▒▒▒▒│  │██████│  │▒▒▒▒▒▒│
│      │  │      │  │██████│  │      │
│ 8.2mi│  │ 5.1mi│  │12.4mi│  │ 6.0mi│
│ Today│  │ Wed  │  │ Tue  │  │ Mon  │
└──────┘  └──────┘  └──────┘  └──────┘
```

Each card:
- Mini effort gradient (~80px tall) — compressed Canvas 2D render
- Distance
- Day label (Today, Yesterday, day name)
- Tap → `/activities/{id}`

**For runs without streams:** Show a flat colored bar (activity exists but no gradient data). Still tappable.

### Backend: Extend `/v1/home` for Recent Runs

Add `recent_runs` array to `HomeData`:

```
recent_runs: [{
  activity_id: string
  name: string
  start_time: string
  distance_m: number
  moving_time_s: number
  stream_status: 'success' | 'pending' | 'fetching' | 'unavailable' | null
  effort_intensity_summary: number[] | null  // Downsampled to ~50 points for thumbnail
}]
```

**50 points per thumbnail** is enough for the mini gradient visual. Keeps the payload small with 4 runs (~200 floats total).

### Home Page Layout (final structure, all states)

```
┌─────────────────────────────────┐
│  Header (date + coach link)     │
├─────────────────────────────────┤
│  HERO (state-driven)            │
│  A: Canvas  B: Workout  C: Coach│
├─────────────────────────────────┤
│  Recent Runs Strip              │
│  [mini] [mini] [mini] [mini]    │
├─────────────────────────────────┤
│  Coach Noticed (if present)     │
├─────────────────────────────────┤
│  Quick Check-in (if needed)     │
├─────────────────────────────────┤
│  This Week (day chips + progress│
├─────────────────────────────────┤
│  Race Countdown (if applicable) │
└─────────────────────────────────┘
```

### AC-L3: Acceptance Criteria

| ID | Criterion | Test approach |
|----|-----------|--------------|
| L3-1 | Home page shows canvas hero when latest activity has streams within 24h | Frontend test |
| L3-2 | Home page shows metrics card when latest activity has pending streams | Frontend test |
| L3-3 | Home page shows workout hero when no recent run but workout scheduled | Frontend test |
| L3-4 | Home page shows coach noticed when no recent run and no workout | Frontend test |
| L3-5 | Recent Runs strip renders below hero in all states | Frontend test |
| L3-6 | Each Recent Run card shows mini effort gradient when streams available | Frontend test |
| L3-7 | Each Recent Run card is tappable → navigates to activity detail | Frontend test |
| L3-8 | Runs without streams show flat colored bar, still tappable | Frontend test |
| L3-9 | Recent Runs strip shows max 4 runs | Frontend test |
| L3-10 | `/v1/home` returns `recent_runs` array with downsampled effort data | Backend test |

---

## Implementation Order

1. **Layer 2 first** — Activity detail page restructure
   - Wire `RunShapeCanvas` into `/activities/[id]/page.tsx`
   - Add reflection prompt endpoint + component
   - Reorganize existing components
   - This is the most self-contained change and validates the canvas in a real page

2. **Layer 1 second** — Home page canvas hero
   - Extend `/v1/home` with `last_run` data
   - Build `LastRunHero` component
   - Implement silent upgrade behavior

3. **Layer 3 third** — State machine + Recent Runs
   - Implement state priority logic
   - Extend `/v1/home` with `recent_runs` array
   - Build mini gradient cards
   - Restructure home page layout

---

## Decisions (locked 2026-02-14)

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 1 | Analysis caching | Cache full `StreamAnalysisResult` in DB | Compute once at ingest, serve on Home + Activity. Recompute on: new stream payload, `analysis_version` bump, manual reprocess. |
| 2 | Hero freshness | 24-hour window | >24h falls through to workout/coach/rest hero. Stale canvas doesn't dominate Home. |
| 3 | Recent Runs count | 4 | Best mobile density/scanability balance. 3 sparse, 5 cramped. |
| 4 | Reflection payload | Enum only: `harder \| expected \| easier` | No free text in v1. Store `activity_id + athlete_id + response + timestamp`. |
| 5 | Moments gate | `confidence >= 0.8` AND `moments.length > 0` | Suppress section entirely when either condition fails. No placeholders. |

---

## What This Does NOT Include

- Coachable moment prose/commentary (future — requires coach integration)
- Cross-run comparison on home page
- Intelligence consolidation (Layer 4 — separate spec)
- Webhook-driven sync (separate infrastructure task)
- Stream backfill for existing activities
- Monetization tier gating
