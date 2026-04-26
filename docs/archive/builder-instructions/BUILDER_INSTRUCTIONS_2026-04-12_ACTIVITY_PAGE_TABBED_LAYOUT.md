# Builder Instructions — Activity Detail Page: Tabbed Layout Refactor

**Date:** April 12, 2026
**Priority:** HIGH — this is the most-used surface in the product
**Commissioned by:** Founder + advisor
**Replaces:** `docs/BUILDER_INSTRUCTIONS_2026-04-12_ACTIVITY_PAGE_POLISH.md` (strike that doc, this supersedes it)

---

## Context

The activity detail page has two problems, not one:

**Problem 1 (Layout):** The page stacks all content in a single vertical scroll. The run shape canvas, map, splits, feedback form, intelligence, and analysis are separated by 3-4 full viewports of scrolling. The `StreamHoverContext` — which links chart hover to map position — is already wired but useless because the chart and map are never visible simultaneously.

**Problem 2 (Intelligence):** The "WhyThisRun" and "RunContextAnalysis" components produce intelligence that is wrong, obvious, or both. On the founder's half marathon pacing run (13.2mi, 9:16/mi, 127bpm, 1.2% drift), our system said "Efficiency 7.2% worse than your recent recovery runs. Check for fatigue or illness." Strava's system said "Solid half marathon pacing effort — you stayed comfortable in endurance zones while maintaining your 12-day streak." We were wrong; they were right. And their intelligence was still shallow. See `docs/specs/INTELLIGENCE_VOICE_SPEC.md` for the full diagnosis and spec.

Problem 2 is more important than Problem 1. A polished layout amplifies whatever is inside it — if the intelligence is wrong, putting it above the fold makes the product worse. Fix intelligence quality first, then build the layout to deliver it.

**The visual goal:** Reorganize existing components into a tabbed layout so the athlete can learn from their data — visual catches the eye, narrative answers the wonder, understanding deepens. Strava uses a left sidebar tab navigation that keeps all content in a single viewport per tab, with chart/map/splits cross-linked via hover. We need the same navigational discipline.

**The intelligence goal:** Per-chart intelligence cards that are purpose-aware, longitudinally informed, and only speak when they have something genuinely useful to say. Empty card slots are acceptable and expected — silence over wrong confidence.

---

## Mandatory Read Order

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/specs/INTELLIGENCE_VOICE_SPEC.md` — **READ THIS FIRST.** The voice spec defines WHAT intelligence to show. This doc defines WHERE to put it. If you build the layout without understanding the voice spec, you will polish the presentation of bad content.
3. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` — Part 1 (the design principle)
4. This document

---

## Architecture Constraints

### DO NOT change any of these:
- The `RunShapeCanvas` internal rendering (gradient, LTTB, overlays, segment bands)
- The `StreamHoverContext` interface (`hoveredIndex` / `setHoveredIndex`)
- The `RouteContext` / `ActivityMapInner` map rendering logic
- The `SplitsTable` / `IntervalsView` column structure
- Non-run activity pages (cycling, strength, hiking, flexibility — leave untouched)

### WILL change (per Intelligence Voice Spec):
- `WhyThisRun` and `RunContextAnalysis` — these components produce wrong or unhelpful intelligence. They will be replaced with per-chart intelligence cards as specified in `docs/specs/INTELLIGENCE_VOICE_SPEC.md`. The layout work should leave placeholder slots for these cards; the intelligence content is a separate backend + frontend workstream.
- API endpoints for attribution and run-analysis — the backend intelligence needs to be purpose-aware, use appropriate metrics per run type, and return per-chart insights instead of one generic block. Layout builders should design card slots that can receive 0-3 insight cards per chart (0 is valid — suppression over hallucination).

### DO change:
- The render order and layout structure in `app/activities/[id]/page.tsx`
- Which components appear in which tab
- Component wrapper sizing (aspect ratios, heights, widths)
- The "Going In" and findings sections (currently inline — extract to components)

---

## Current File Map

| Component | File | Props |
|-----------|------|-------|
| Activity page | `app/activities/[id]/page.tsx` | — |
| Run Shape Canvas | `components/activities/rsi/RunShapeCanvas.tsx` | `activityId`, `splits`, `intervalSummary`, `provider`, `deviceName`, `heatAdjustmentPct`, `temperatureF` |
| Route map | `components/activities/map/RouteContext.tsx` | `activityId`, `track`, `startCoords`, `sportType`, `startTime`, `streamPoints`, `weather`, `distanceM`, `durationS`, `heatAdjustmentPct` |
| Map inner | `components/activities/map/ActivityMapInner.tsx` | `track`, `startCoords`, `accentColor`, `streamPoints`, `weather`, `hoveredIndex` |
| Elevation profile | `components/activities/map/ElevationProfile.tsx` | Exists, wired to StreamHoverContext, **currently unused** |
| Splits table | `components/activities/SplitsTable.tsx` | `splits`, `provider`, `deviceName`, `onRowHover`, `rowRefs` |
| Intervals view | `components/activities/IntervalsView.tsx` | `splits`, `intervalSummary`, `provider`, `deviceName` |
| Why This Run? | `components/activities/WhyThisRun.tsx` | `activityId`, `className`, `defaultExpanded` |
| Run Context Analysis | `components/activities/RunContextAnalysis.tsx` | `activityId` |
| Reflection prompt | `components/activities/ReflectionPrompt.tsx` | `activityId`, `className` |
| Perception prompt | `components/activities/PerceptionPrompt.tsx` | `activityId`, `className`, `workoutType`, `expectedRpeRange` |
| Workout type selector | `components/activities/WorkoutTypeSelector.tsx` | `activityId`, `compact` |
| Runtoon card | `components/activities/RuntoonCard.tsx` | `activityId` |
| Stream hover context | `lib/context/StreamHoverContext.tsx` | `hoveredIndex`, `setHoveredIndex` |
| Stream analysis hook | `components/activities/rsi/hooks/useStreamAnalysis.ts` | `activityId` → `StreamAnalysisData` |
| "Going In" | **Inline** in `page.tsx` | Uses `activity.pre_recovery_hrv`, `pre_resting_hr`, `pre_sleep_h` |
| Findings | **Inline** in `page.tsx` | Maps `findings` array to cards |

---

## Target Layout

### Desktop (>= 768px)

```
┌──────────────────────────────────────────────────────┐
│  Header: Title, date, device, stats strip            │
│  Going In strip: HRV 48ms | RHR 57 | Sleep 5.2h     │
├────────┬─────────────────────────────────────────────┤
│        │                                             │
│  Tab   │  Tab Content Area                           │
│  Nav   │  (changes per tab, fits in one viewport)    │
│        │                                             │
│ Overview│                                            │
│ Splits │                                             │
│ Analysis│                                            │
│ Context│                                             │
│ Feedback│                                            │
│        │                                             │
├────────┴─────────────────────────────────────────────┤
```

### Mobile (< 768px)

```
┌──────────────────────────┐
│ Header + stats strip     │
│ Going In strip           │
├──────────────────────────┤
│ [Overview][Splits][Analysis][Context][⋯]  ← horizontal tabs │
├──────────────────────────┤
│                          │
│  Tab Content Area        │
│  (scrollable within tab) │
│                          │
└──────────────────────────┘
```

---

## Tab Definitions

### Tab 1: Overview (default)

This is the "learn from your run" tab. Everything the athlete needs to understand what happened and why.

**Render order:**

1. **RunShapeCanvas** (hero) — full width, exactly as today. Keep HR/Cadence/Grade toggles. Keep drift metrics cards below the chart. **Remove** the `SplitsModePanel` from inside RunShapeCanvas — splits move to their own tab. The canvas itself gets taller on this tab because splits aren't below it.

2. **Intelligence card slot** — positioned directly below the RunShapeCanvas. This is where per-chart insights will appear once the Intelligence Voice Spec backend work is complete. For now, render a placeholder area that can accept 0-3 insight cards. Each card: ~2 sentences, contextual to the chart above, specific to this run. **Do NOT render the current WhyThisRun or RunContextAnalysis here** — their output is wrong (see Voice Spec for diagnosis). Leave the slot empty until the backend produces insights worth showing. Empty is better than wrong.

4. **Map** — compact (aspect ratio 16:9 instead of 4:3), full width below the analysis. The `StreamHoverContext` hover linkage works because chart and map are now in the same viewport. When you hover the chart, the dot moves on the map.

5. **Runtoon** — only if the image is ready. If `status !== 'ready'`, render nothing. Never show "Runtoon took longer than expected."

### Tab 2: Splits

This is the "mile-by-mile detail" tab. Inspired by Strava's Laps view.

**Desktop layout:** Two columns — splits/intervals table on the LEFT (60%), map on the RIGHT (40%). The map stays visible as a spatial reference while you read splits.

**Mobile layout:** Map on top (compact, 16:9), splits table below (scrollable).

**Render order:**

1. **Interval detection** — if `intervalSummary` exists, show the Intervals/Mile Splits toggle and IntervalsView. Otherwise, show SplitsTable directly.

2. **Map** — `RouteContext` with `streamPoints`. Persistent, always visible.

3. **Elevation profile** — `ElevationProfile.tsx` already exists and is wired to `StreamHoverContext`. Activate it here, below the map. When the athlete hovers on a split row, the chart, map, AND elevation profile all highlight the same position.

**Hover linkage enhancement:** When a split row is hovered (`onRowHover`), compute the corresponding stream index range for that mile and set `setHoveredIndex` to the midpoint. This makes splits → chart → map → elevation all cross-linked.

### Tab 3: Analysis

This is the "how did the effort distribute" tab.

**Render order:**

1. **Drift metrics** — Cardiac Drift, Pace Drift, Cadence Trend. Currently inside RunShapeCanvas. Extract and place here as the top section.

2. **Pace Distribution** (NEW) — zone breakdown bar chart. Calculate time-in-zone from stream analysis data. Zones defined by the athlete's training paces from `/v1/activities/{id}` response (or RPI-derived if available). Show Z1 through Z5/Z6 with horizontal bars and duration labels. This is a **new component** — `components/activities/PaceDistribution.tsx`.

3. **Efficiency Trend + Volume Trend** — currently in `RunContextAnalysis`. If these are separable, pull them here. If not, duplicate the display (they're small cards).

4. **Plan vs Actual** — if `plan_comparison` exists in stream analysis data. Currently appears in two places (RunShapeCanvas internal and page collapsible). Consolidate to this tab only.

### Tab 4: Context

This is the "what does this mean for my training" tab. **This is our differentiator** — nothing on this tab exists in Strava.

**Render order:**

1. **Going In (expanded)** — full pre-run state: Recovery HRV (with overnight avg), RHR, Sleep (with score). Currently a one-line strip. On this tab, expand to show the full pre-run detail including Stress, Soreness if available. Extract from inline page code into `components/activities/GoingInCard.tsx`.

2. **N=1 Findings** — the correlation insight cards. Currently inline in page.tsx. Extract to `components/activities/FindingsCards.tsx`. **Critical:** The current finding text ("YOUR running efficiency is noticeably associated with changes the following day when your leg freshness is higher") is algorithm-speak that no athlete reads. The display component should be built clean, but the text quality depends on Intelligence Voice Spec backend work. For now, filter to show only findings RELEVANT to this activity (not global top-3). If no findings are relevant, show nothing — don't fill the space with generic correlations.

3. **Narrative** — if `activity.narrative` exists, show the coaching narrative text.

4. **Pre-Run State Details** — full wellness detail if available.

### Tab 5: Feedback (or collapsed section)

This is the INPUT tab — where the athlete records their perception.

**Option A (tab):** A dedicated Feedback tab containing ReflectionPrompt + PerceptionPrompt + WorkoutTypeSelector. This keeps input separate from output.

**Option B (floating):** A floating action button (bottom-right) that opens a modal/sheet with the feedback form. This frees up a tab slot.

**Founder to decide.** If unsure, implement Option A (tab) — it's simpler and reversible.

---

## Specific Implementation Notes

### Extract "Going In" to a component

Currently inline in `page.tsx` (conditional block checking `pre_recovery_hrv`, `pre_resting_hr`, `pre_sleep_h`). Extract to:

```
components/activities/GoingInStrip.tsx  — compact 1-line version (for header area)
components/activities/GoingInCard.tsx   — expanded version (for Context tab)
```

Both receive the same props from the `activity` object.

### Extract Findings to a component

Currently inline in `page.tsx` (maps `findings` array to bordered cards). Extract to:

```
components/activities/FindingsCards.tsx
```

Props: `findings: Array<{ text, domain, confidence_tier, evidence_summary? }>`.

### Remove duplicate Plan Comparison

`PlanComparisonCard` inside `RunShapeCanvas` AND "Plan vs Actual" grid in page's collapsible section show the same data. Remove both. Place ONE instance in the Analysis tab.

### Tab component

Create a generic tab container:

```
components/activities/ActivityTabs.tsx
```

Desktop: left sidebar, 120px wide, vertical tab labels, content area fills remaining width.
Mobile: horizontal scrollable tab bar at the top, content area below.

Use a simple `useState<string>('overview')` for active tab. No routing — tabs are client-side state within the page.

### StreamHoverProvider scope

`StreamHoverProvider` currently wraps the entire run branch. Keep it there — it needs to wrap ALL tabs so hover state persists across tab switches. The chart on the Overview tab sets `hoveredIndex`; the map on the Splits tab reads it. This only works if the provider wraps everything.

**Important:** Components in non-active tabs should NOT unmount. Use CSS `display: none` or `visibility: hidden` on inactive tabs so React state (including hover subscriptions and Leaflet map instances) persists. Tab switching should feel instant — no re-renders, no re-fetching, no map tile reloads.

---

## What NOT to build

- No new API endpoints
- No new data fetching hooks (reuse existing queries — React Query dedupes)
- No changes to RunShapeCanvas internals (chart rendering, LTTB, gradient, segment overlays)
- No changes to ActivityMapInner (tile loading, fitBounds, CircleMarker)
- No changes to non-run activity pages
- No pace distribution backend — compute time-in-zone client-side from stream analysis data
- No Runtoon changes — just conditionally hide when not ready

---

## Evidence Required

1. **Desktop screenshot (1440px)** of each tab showing content fits in one viewport without scrolling
2. **Mobile screenshot (390px)** of Overview and Splits tabs
3. **Hover linkage proof:** Screenshot or screen recording showing chart hover → map dot movement while both are visible simultaneously
4. **`npx tsc --noEmit` exit 0**
5. **No regressions:** All existing activity page data still loads and displays correctly

---

## Priority Order

If this is too large for one session, build in this order:

1. **Tab container + Overview tab** — move WhyThisRun and RunContextAnalysis above the fold, add Going In strip to header. This alone is a major improvement.
2. **Splits tab** — side-by-side splits + map on desktop.
3. **Context tab** — extract Going In and Findings to components, move here.
4. **Analysis tab** — drift metrics, plan comparison consolidation.
5. **Pace Distribution** (new component) — last priority, most new code.
6. **Feedback** — collapse or move to tab.

---

## Files to modify

| File | Change |
|------|--------|
| `app/activities/[id]/page.tsx` | Major restructure — tab container wrapping existing components |
| `components/activities/rsi/RunShapeCanvas.tsx` | Remove `SplitsModePanel` from internal render (splits move to Splits tab) |
| NEW: `components/activities/ActivityTabs.tsx` | Tab container (desktop sidebar + mobile horizontal) |
| NEW: `components/activities/GoingInStrip.tsx` | Compact pre-run wellness strip |
| NEW: `components/activities/GoingInCard.tsx` | Expanded pre-run wellness card |
| NEW: `components/activities/FindingsCards.tsx` | N=1 correlation finding cards |
| NEW: `components/activities/PaceDistribution.tsx` | Zone time-in-zone bar chart (Phase 5) |
