# Builder Instructions: Map & Activity Page — Final Corrections

**Date:** April 6, 2026
**From:** Advisor
**Priority:** These are the founder's direct feedback. Fix all of them.
**Scope:** Frontend only. No backend changes.

---

## Context

The founder reviewed the map on their 9.8-mile run and compared it
directly to Strava. Several things are wrong. These corrections
are based on specific observations from the founder:

1. "the scale is completely off — you can't make out anything on the map"
2. "when you zoom in, the moment you hover elevation it resets back
   to zoomed out automatically"
3. "Our key moments are useless, remove them and move the map into
   that spot"
4. "why can't we have this elevation ON the run shape chart instead
   of separate — and instead of just a line let it be solid below
   the line — making real shape — this way one hover works for
   everything and it's all tied together"
5. "it needs grade on the hover — strava provides this — it is FAR
   more useful than elevation"

---

## Fix 1: Remove "Key Moments" (Coachable Moments)

The `CoachableMoments` component renders a list like:
```
16:15  Pace Fade  12.5
16:31  Pace Fade  12.0
16:47  Pace Fade  11.7
...
```

The founder called these "useless." They are — it's the same event
("Pace Fade") repeated 7 times with numbers that mean nothing to
the athlete without context.

**Remove the `CoachableMoments` component entirely from the activity
page.** Don't delete the component file (it might be useful later
with better content), but remove it from the page layout.

In `apps/web/app/activities/[id]/page.tsx`, delete this block:

```tsx
// DELETE THIS ENTIRE BLOCK:
{analysisData && (
  <CoachableMoments
    moments={analysisData.moments}
    confidence={analysisData.confidence}
    className="mb-6"
  />
)}
```

Also delete the Garmin AI attribution that followed it (only needed
when Coachable Moments rendered derived AI analysis):

```tsx
// DELETE THIS:
{analysisData && activity.provider === 'garmin' && (
  <p className="text-xs text-slate-500 mb-4">
    Insights derived in part from Garmin device-sourced data.
  </p>
)}
```

---

## Fix 2: Move Map Up — Right After RunShapeCanvas

After removing Key Moments, the map should move up to be directly
below the RunShapeCanvas. The new page order for runs:

1. Header (back + name + date)
2. **RunShapeCanvas** (hero)
3. **Route Map** (directly below — connected via StreamHoverContext)
4. Reflection Prompt
5. Perception Prompt
6. Workout Type Selector
7. Metrics Ribbon
8. Pre-activity wellness ("Going In")
9. Runtoon

Move the `<RouteContext>` block from its current position (between
"Going In" and Runtoon) to immediately after the RunShapeCanvas
`<div className="mb-6">` block. This puts the chart and the map
next to each other visually, which makes the hover cross-linking
natural — the athlete's eye doesn't have to jump past 4 unrelated
sections to see the map dot when they hover on the chart.

---

## Fix 3: Remove Separate Elevation Profile Below Map

The RunShapeCanvas already renders elevation/terrain as an `Area`
fill behind the traces (AC-5). Having a SECOND elevation profile
below the map is redundant.

**Remove the `ElevationProfile` component from `RouteContext.tsx`.**
Don't render it. The terrain shape belongs in the RunShapeCanvas
where the hover is already connected.

---

## Fix 4: Make Terrain Fill More Prominent in RunShapeCanvas

The current terrain fill in RunShapeCanvas is nearly invisible:

```tsx
fill="rgba(16,185,129,0.2)"    // 20% opacity — can barely see it
stroke="rgba(16,185,129,0.4)"  // 40% opacity stroke
```

The founder wants "solid below the line — making real shape." The
terrain fill should be the visual foundation of the chart — a solid
mass that the traces sit on top of. This is how Strava renders
their elevation on activity charts.

Change to:

```tsx
<Area
  yAxisId="altitude"
  type="monotone"
  dataKey="altitude"
  baseValue="dataMin"
  fill="rgba(16,185,129,0.35)"     // Increase from 0.2 → 0.35
  stroke="rgba(16,185,129,0.6)"    // Increase from 0.4 → 0.6
  strokeWidth={1.5}
  isAnimationActive={false}
/>
```

This makes the terrain fill visible as a real shape — hills and
valleys that the athlete can read at a glance. The effort gradient
canvas behind it will still show through, and the traces (pace, HR)
will render on top.

If 0.35 is still too subtle, go to 0.45. The terrain should be
the second most prominent element after the pace line.

---

## Fix 5: Show Grade on Hover by Default

Grade is currently hidden behind a toggle button. The founder says
grade is "FAR more useful than elevation" and Strava shows GAP
(Grade Adjusted Pace) by default.

Change the default for `showGrade` from `false` to `true`:

```tsx
// In RunShapeCanvas.tsx:
const [showGrade, setShowGrade] = useState(true);  // was false
```

The grade line and grade value in the tooltip should always be
visible unless the athlete toggles it off. Grade tells you WHY your
pace changed. Elevation tells you WHERE you are. Grade is the
answer to the question the athlete is actually asking.

---

## Fix 6: Fix Map Scale — Tighter Bounds

The map is zoomed out too far. The route appears as a tiny shape
in the center of a mostly empty map. The athlete can't see the
route detail without zooming in manually.

### Problem: too much padding in `FitBounds`

The current padding in `ActivityMapInner.tsx`:

```tsx
map.fitBounds(bounds, { padding: [30, 30] });
```

30px padding on a 300px-tall map means 20% of the map is empty
border. Combined with the bounds calculation's own padding
(`const pad = 0.001`), the route is squeezed into the center.

**Increase padding to give the route more visual weight:**

```tsx
map.fitBounds(bounds, { padding: [40, 40], maxZoom: 16 });
```

But the real fix is in the bounds calculation. Remove the extra
padding in the bounds computation:

```tsx
// Remove this arbitrary padding:
const pad = 0.001;
return [[minLat - pad, minLng - pad], [maxLat + pad, maxLng + pad]];

// Replace with tight bounds — let Leaflet's padding handle the margin:
return [[minLat, minLng], [maxLat, maxLng]];
```

And set `maxZoom: 16` on `fitBounds` to prevent over-zooming on
short routes.

### Also increase map height

For runs, change from 300px to **350px**. The route needs room to
breathe. This matches the hero height for non-run activities and
gives the pace coloring and mile markers space to be legible.

---

## Fix 7: Fix Zoom Reset on Hover (CRITICAL BUG)

When the athlete zooms into the map and then hovers over the
elevation profile (or the RunShapeCanvas), the map snaps back
to the original zoom level. This makes the map unusable.

### Root cause

The `FitBounds` component re-runs `map.fitBounds()` every time
the `bounds` prop changes. If `bounds` is recalculated (even to
the same value) on any re-render, Leaflet resets the view.

The `bounds` useMemo depends on `[track, ghosts, startCoords]`.
If a parent re-render causes these to be new array references
(even with the same data), the bounds are recalculated and
fitBounds fires again.

### Fix

The `FitBounds` component should only fit bounds ONCE on initial
render, not on every update. Add a ref to track whether initial
fit has occurred:

```tsx
function FitBounds({ bounds }: { bounds: LatLngBoundsExpression }) {
  const map = useMap();
  const didFit = useRef(false);

  useEffect(() => {
    if (!didFit.current) {
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 16 });
      didFit.current = true;
    }
  }, [map, bounds]);

  return null;
}
```

This fits the bounds on first render and never resets after that.
The athlete's manual zoom and pan are preserved. If the athlete
wants to reset to the original view, they can use a "Reset view"
button (optional — not required for this fix).

**Also:** When the hover context updates (amber dot moves on map),
do NOT recalculate bounds or trigger any map view changes. The
amber dot should appear at the position without affecting zoom
or pan.

---

## Acceptance Criteria

- [ ] Key Moments / Coachable Moments no longer appear on the page
- [ ] Map is directly below RunShapeCanvas (no sections between them)
- [ ] No separate elevation profile below the map
- [ ] Terrain fill in RunShapeCanvas is clearly visible as a solid
      shape (hills and valleys readable at a glance)
- [ ] Grade is shown on hover by default (not behind a toggle)
- [ ] Grade line is visible on the chart by default
- [ ] Map route fills most of the map area (not tiny in the center)
- [ ] Zooming into the map stays zoomed when hovering chart or
      elevation — NO ZOOM RESET
- [ ] Hover on RunShapeCanvas still moves amber dot on map
- [ ] Map height is 350px for runs
- [ ] Test on the founder's 9.8-mile Meridian run
- [ ] Test on the founder's 14-mile hilly loop run

---

## Do NOT

- Do not delete the CoachableMoments component file — just remove
  it from the page
- Do not change the StreamHoverContext architecture
- Do not change the pace coloring logic (that was fixed in the
  previous round)
- Do not change the backend
- Do not add new features — this is strictly corrections
