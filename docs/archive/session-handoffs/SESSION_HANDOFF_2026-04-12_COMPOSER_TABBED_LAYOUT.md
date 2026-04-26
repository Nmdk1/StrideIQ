# Composer Task — Activity Page Tabbed Layout

**Date:** April 12, 2026
**Priority:** HIGH
**Scope:** Frontend only. No backend changes. No API changes.

---

## What You're Building

Refactor the activity detail page from a single vertical scroll into a tabbed layout. Currently the page stacks RunShapeCanvas, splits, map, feedback form, intelligence, and findings across 4+ viewports. After this work, each tab fits in one viewport with no scrolling.

**Read this spec for full details:** `docs/BUILDER_INSTRUCTIONS_2026-04-12_ACTIVITY_PAGE_TABBED_LAYOUT.md`

**Read this FIRST for operating rules:** `docs/FOUNDER_OPERATING_CONTRACT.md`

**Read the wiki for system context:** `docs/wiki/index.md` — then `docs/wiki/frontend.md` for component architecture, routes, and data layer.

---

## Critical Rules

1. **Do NOT start coding before reading the full spec** (`docs/BUILDER_INSTRUCTIONS_2026-04-12_ACTIVITY_PAGE_TABBED_LAYOUT.md`). It has file paths, component names, render order, and priority order.

2. **Do NOT change RunShapeCanvas internals** — chart rendering, LTTB, gradient, segment overlays, the canvas itself. You are moving it, not modifying it.

3. **Do NOT change ActivityMapInner** — tile loading, fitBounds, CircleMarker rendering. The map was just fixed. Don't touch it.

4. **Do NOT render WhyThisRun or RunContextAnalysis in the Overview tab.** These components produce wrong intelligence. Leave empty intelligence card slots where they would go. The spec explains why.

5. **Use CSS hiding for inactive tabs, NOT unmount.** Components in non-active tabs must persist (React state, Leaflet map instances, hover subscriptions). Tab switching must be instant — no re-renders, no re-fetches.

6. **StreamHoverProvider must wrap ALL tabs.** Keep it at the top level so hover state persists across tab switches.

---

## Build Order (do in this sequence)

### Step 1: Tab container + Overview tab
**Files:**
- NEW: `apps/web/components/activities/ActivityTabs.tsx` — tab container
  - Desktop (>=768px): left sidebar, ~120px wide, vertical tab labels
  - Mobile (<768px): horizontal scrollable tab bar at top
  - `useState<string>('overview')` for active tab, no routing
- MODIFY: `apps/web/app/activities/[id]/page.tsx` — wrap run branch in ActivityTabs

**Overview tab content (render order):**
1. RunShapeCanvas (hero, full width, exactly as today with HR/Cadence/Grade toggles)
2. Empty intelligence card slot (placeholder div, styled but empty)
3. Map (compact, 16:9 aspect ratio instead of current 4:3)
4. Runtoon (only if `status === 'ready'`, otherwise render nothing)

### Step 2: Splits tab
**Desktop:** Two columns — splits/intervals on LEFT (60%), map on RIGHT (40%)
**Mobile:** Map on top (compact 16:9), splits below (scrollable)

**Content:**
1. IntervalsView/SplitsTable (use intervalSummary existence to toggle)
2. Map (persistent, always visible)
3. ElevationProfile — `components/activities/map/ElevationProfile.tsx` already exists, wired to StreamHoverContext. Activate it below the map.

**Hover linkage:** When split row is hovered (`onRowHover`), compute stream index range for that mile, set `setHoveredIndex` to midpoint. This cross-links splits → chart → map → elevation.

### Step 3: Context tab
**Extract these from inline in page.tsx into new components:**
- NEW: `apps/web/components/activities/GoingInStrip.tsx` — compact 1-line (for header)
- NEW: `apps/web/components/activities/GoingInCard.tsx` — expanded (for this tab)
- NEW: `apps/web/components/activities/FindingsCards.tsx` — correlation findings

**Content:**
1. GoingInCard (expanded pre-run state: HRV, RHR, Sleep, Stress, Soreness)
2. FindingsCards (from `findings` array — display as cards, same data)
3. Narrative (if `activity.narrative` exists)

### Step 4: Analysis tab
**Content:**
1. Drift metrics (Cardiac Drift, Pace Drift, Cadence Trend) — extract from RunShapeCanvas area
2. Efficiency/Volume trends (from RunContextAnalysis if separable)
3. Plan vs Actual (consolidate from duplicated locations to here only)

### Step 5: PaceDistribution (new component)
- NEW: `apps/web/components/activities/PaceDistribution.tsx`
- Zone breakdown bar chart, time-in-zone from stream analysis data
- Compute client-side from stream data, no new API
- Place in Analysis tab

### Step 6: Feedback tab
- Move ReflectionPrompt, PerceptionPrompt, WorkoutTypeSelector here
- These are INPUT, not OUTPUT — separating them from learning tabs

---

## Header (persistent across all tabs)

```
┌──────────────────────────────────────────────────────┐
│  Title: "Hattiesburg - 9:30 pacer Hattiesburg Half"  │
│  Date: Saturday, April 11, 2026 at 7:00 AM           │
│  Device: Garmin Forerunner 165                        │
│  Stats: 13.3 mi | 2:03:51 | 9:20/mi | 127 bpm | ... │
│  Going In: HRV 48ms | RHR 57 | Sleep 5.2h            │
├──────────────────────────────────────────────────────┤
```

Going In strip uses the compact `GoingInStrip` component. Always visible.

---

## Files Summary

| File | Action |
|------|--------|
| `app/activities/[id]/page.tsx` | Major restructure — wrap in tabs |
| NEW: `components/activities/ActivityTabs.tsx` | Tab container |
| NEW: `components/activities/GoingInStrip.tsx` | Compact wellness strip |
| NEW: `components/activities/GoingInCard.tsx` | Expanded wellness card |
| NEW: `components/activities/FindingsCards.tsx` | Correlation finding cards |
| NEW: `components/activities/PaceDistribution.tsx` | Zone time bar chart (Step 5) |
| `components/activities/rsi/RunShapeCanvas.tsx` | May need SplitsModePanel removal from internal render |

---

## Evidence Required

1. Desktop screenshot (1440px) of Overview and Splits tabs — content fits one viewport
2. Mobile screenshot (390px) of Overview tab
3. Hover linkage proof: chart hover → map dot movement while both visible
4. `npx tsc --noEmit` exit 0
5. All existing activity data still loads and displays
6. Tab switching is instant (no flicker, no re-fetch, no map tile reload)

---

## What NOT to Build

- No new API endpoints
- No backend changes
- No changes to RunShapeCanvas chart rendering
- No changes to ActivityMapInner
- No WhyThisRun or RunContextAnalysis rendering (leave slots empty)
- No non-run activity page changes
- No Runtoon changes (just conditionally hide when not ready)
