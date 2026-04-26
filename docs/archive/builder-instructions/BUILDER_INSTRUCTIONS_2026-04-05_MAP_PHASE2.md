# Builder Instructions: Map Phase 2 — The Agreed Map

**Date:** April 5, 2026
**From:** Advisor
**Priority:** Build in the order listed. Each section ships independently.
**Backend changes:** Yes — one small addition to the stream response.

---

## Context

Phase 1 shipped: zoom controls, start/end markers, Voyager tiles,
mile markers, glow line, full-screen. The map went from broken to
functional.

Phase 2 makes it the map we agreed on. The features below were in
the original product strategy (Priority #12: Intelligent Maps) and
in the Workstream 2 spec. They are not new scope — they are
unfulfilled commitments.

The data for all of these already exists. The `useStreamAnalysis`
hook on the activity page fetches 500 LTTB-downsampled `StreamPoint`
records per run, each containing `time`, `pace`, `altitude`, `grade`,
`hr`, `cadence`, and `effort`. The raw stream has per-second `latlng`,
`altitude`, `velocity_smooth`, `heartrate`, `cadence` at 8,000+
points. No new data sources are needed.

---

## Quality Principle (from Phase 1, still applies)

Before shipping any visual, open Garmin Connect for the same activity
and compare. If ours is missing something theirs shows as default,
we are not done. If ours shows something theirs doesn't, we are
differentiating.

---

## 1. Pace-Colored Route (run activities)

### What it is

Instead of a single flat-color polyline, the route is colored by
pace: green for fast, yellow for moderate, red for slow. The athlete
can see at a glance where they pushed and where they cruised. Every
competitor shows this. We don't.

### Backend change required

The `StreamPoint` dataclass (in `run_stream_analysis.py` or the
router that builds the response) currently includes `time`, `hr`,
`pace`, `altitude`, `grade`, `cadence`, `effort`. It does NOT
include `lat`/`lng`.

**Add `lat` and `lng` fields to `StreamPoint`.**

When building the LTTB-downsampled stream array, look up the
corresponding GPS coordinate from the raw `latlng` channel at the
same index. The LTTB algorithm preserves indices into the original
array — each downsampled point has a known `original_index` that
maps to the same position in the `latlng` array.

```python
# In the StreamPoint dataclass / dict:
@dataclass
class StreamPoint:
    time: int
    hr: int | None
    pace: float | None         # seconds per km
    altitude: float | None
    grade: float | None
    cadence: int | None
    effort: float              # [0.0, 1.0]
    lat: float | None = None   # ADD THIS
    lng: float | None = None   # ADD THIS
```

When building the stream response, pull lat/lng from the raw stream:

```python
raw_latlng = stream_data.get("latlng", [])
for point in downsampled_points:
    idx = point["original_index"]  # or however LTTB preserves index
    if idx < len(raw_latlng) and raw_latlng[idx] is not None:
        point["lat"] = round(raw_latlng[idx][0], 6)
        point["lng"] = round(raw_latlng[idx][1], 6)
```

This gives the frontend ~500 points with pace + coordinates aligned.
No new endpoint. No new query. Just two new fields on an existing
response.

**Update the TypeScript `StreamPoint` interface** in
`useStreamAnalysis.ts` to match:

```typescript
export interface StreamPoint {
  time: number;
  hr: number | null;
  pace: number | null;
  altitude: number | null;
  grade: number | null;
  cadence: number | null;
  effort: number;
  lat: number | null;   // ADD
  lng: number | null;   // ADD
}
```

### Frontend rendering

Replace the single Polyline in `ActivityMapInner.tsx` (for runs)
with pace-colored segments. When stream data is available, use it
instead of the flat `gps_track`.

```tsx
interface PaceSegment {
  positions: [number, number][];
  color: string;
}

function buildPaceSegments(stream: StreamPoint[]): PaceSegment[] {
  const withGps = stream.filter(p => p.lat != null && p.lng != null && p.pace != null);
  if (withGps.length < 2) return [];

  // Calculate pace range for this specific activity
  const paces = withGps.map(p => p.pace!);
  const minPace = Math.min(...paces);  // fastest (lowest seconds/km)
  const maxPace = Math.max(...paces);  // slowest
  const range = maxPace - minPace || 1;

  const segments: PaceSegment[] = [];
  for (let i = 0; i < withGps.length - 1; i++) {
    const p = withGps[i];
    const next = withGps[i + 1];
    // Normalize: 0 = fastest, 1 = slowest
    const t = (p.pace! - minPace) / range;
    segments.push({
      positions: [[p.lat!, p.lng!], [next.lat!, next.lng!]],
      color: paceColor(t),
    });
  }
  return segments;
}

// Green (fast) → Yellow (mid) → Red (slow)
function paceColor(t: number): string {
  // t: 0 = fastest, 1 = slowest
  if (t < 0.5) {
    // Green to Yellow
    const r = Math.round(255 * (t * 2));
    return `rgb(${r}, 220, 60)`;
  } else {
    // Yellow to Red
    const g = Math.round(220 * (1 - (t - 0.5) * 2));
    return `rgb(255, ${g}, 60)`;
  }
}
```

Render as individual Polyline segments:

```tsx
{paceSegments.map((seg, i) => (
  <Polyline
    key={i}
    positions={seg.positions}
    pathOptions={{
      color: seg.color,
      weight: 4,
      opacity: 1,
      lineCap: 'round',
      lineJoin: 'round',
    }}
  />
))}
```

Keep the glow layer (8px, 25% opacity) underneath, using the accent
color. The glow provides depth; the pace segments provide information.

**Add a legend** below the map:

```tsx
<div className="flex items-center gap-2 mt-1 px-1">
  <span className="text-[10px] text-slate-500">Slower</span>
  <div className="flex-1 h-1.5 rounded-full"
    style={{ background: 'linear-gradient(to right, #ef4444, #eab308, #22c55e)' }}
  />
  <span className="text-[10px] text-slate-500">Faster</span>
</div>
```

**Fallback:** If stream data is not available (non-runs, pending
streams), fall back to the flat-color polyline from Phase 1.

### Props change

`ActivityMapInner` needs a new optional prop:

```tsx
interface Props {
  track: [number, number][];
  startCoords?: [number, number] | null;
  ghosts?: GhostTrace[];
  height?: number;
  accentColor?: string;
  streamPoints?: StreamPoint[];  // ADD — when provided, renders pace-colored
}
```

`RouteContext` receives `streamPoints` from the activity page and
passes it through to `ActivityMap` → `ActivityMapInner`.

The activity page (`[id]/page.tsx`) passes the stream data:

```tsx
<RouteContext
  activityId={activityId}
  track={activity.gps_track}
  startCoords={activity.start_coords}
  sportType={activity.sport_type || 'run'}
  startTime={activity.start_time}
  streamPoints={analysisData?.stream}  // ADD
  mapHeight={250}
/>
```

---

## 2. Elevation Profile Below Map

### What it is

A thin ribbon chart below the map showing the elevation profile of
the activity. Garmin shows this as a full interactive chart. For us,
start with a simple SVG area fill — it gives the athlete terrain
context without another full chart component.

### Data source

`StreamPoint.altitude` — already in the stream response. ~500 points
with altitude values.

For non-runs: the `gps_track` currently doesn't include altitude.
If you added `lat`/`lng` to StreamPoint above, the elevation profile
comes free for runs. For non-runs, defer — the altitude data is in
`session_detail.detail_webhook_raw.samples[].altitudeInMeters` but
would need extraction. Note this as a follow-up, don't block the
run path on it.

### Frontend rendering

Add to `RouteContext.tsx`, below the map:

```tsx
{streamPoints && streamPoints.some(p => p.altitude != null) && (
  <ElevationProfile
    points={streamPoints}
    accentColor={accentColor}
    height={48}
  />
)}
```

`ElevationProfile` component:

```tsx
function ElevationProfile({
  points,
  accentColor = '#3b82f6',
  height = 48,
}: {
  points: StreamPoint[];
  accentColor?: string;
  height?: number;
}) {
  const altitudes = points
    .map(p => p.altitude)
    .filter((a): a is number => a != null);
  if (altitudes.length < 2) return null;

  const min = Math.min(...altitudes);
  const max = Math.max(...altitudes);
  const range = max - min || 1;
  const width = 1000; // SVG viewBox width

  const xStep = width / (altitudes.length - 1);
  const toY = (alt: number) => height - ((alt - min) / range) * (height - 4) - 2;

  const linePath = altitudes
    .map((alt, i) => `${i === 0 ? 'M' : 'L'} ${i * xStep} ${toY(alt)}`)
    .join(' ');
  const areaPath = `${linePath} L ${(altitudes.length - 1) * xStep} ${height} L 0 ${height} Z`;

  // Format elevation display
  const gainFt = Math.round((max - min) * 3.281); // m to ft, approximate

  return (
    <div className="mt-1 px-1">
      <div className="flex items-center justify-between mb-0.5">
        <span className="text-[10px] text-slate-500">Elevation</span>
        <span className="text-[10px] text-slate-500">{gainFt} ft range</span>
      </div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        style={{ height }}
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id="elev-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={accentColor} stopOpacity="0.25" />
            <stop offset="100%" stopColor={accentColor} stopOpacity="0.03" />
          </linearGradient>
        </defs>
        <path d={areaPath} fill="url(#elev-fill)" />
        <path d={linePath} fill="none" stroke={accentColor} strokeWidth="2" opacity="0.5" />
      </svg>
    </div>
  );
}
```

This is a static visualization — no interaction. It gives terrain
context. Interactive elevation (hover to see point) comes with
chart-map linking (section 4).

---

## 3. Weather Badge on Map

### What it is

A small badge in the top-right area of the map showing the weather
conditions during the activity. Garmin shows temperature, weather
icon, and wind.

### Data source

Already on the activity response: `temperature_f`, `humidity_pct`,
`dew_point_f`, `weather_condition`, `heat_adjustment_pct`.

### Frontend rendering

Pass weather data to `RouteContext` → `ActivityMapInner`:

```tsx
interface WeatherData {
  temperature_f: number | null;
  weather_condition: string | null;
  humidity_pct: number | null;
  heat_adjustment_pct: number | null;
}
```

Render as an overlay in the map container (not a Leaflet control —
an absolutely positioned HTML element):

```tsx
{weather?.temperature_f != null && (
  <div className="absolute top-3 right-14 z-[1000] px-2 py-1
                  rounded-md bg-slate-900/80 border border-slate-600/40
                  text-[11px] text-slate-300 flex items-center gap-1.5">
    <span>{weatherIcon(weather.weather_condition)}</span>
    <span className="font-medium">{Math.round(weather.temperature_f)}°F</span>
    {weather.humidity_pct != null && (
      <span className="text-slate-500">{weather.humidity_pct}%</span>
    )}
  </div>
)}
```

Position `right-14` to avoid overlapping the fullscreen toggle
(which is at `right-3`).

`weatherIcon` maps condition strings to emoji or small icons:
- "clear" → ☀️
- "mostly_clear" → 🌤️
- "overcast" → ☁️
- "rain" / "light_rain" → 🌧️
- default → 🌡️

---

## 4. Chart-Map Linking (Interactive Cross-Reference)

### What it is

Hover on the RunShapeCanvas → a dot appears on the map at that GPS
position. Hover on the map → a vertical cursor appears on the
RunShapeCanvas at the corresponding time. This is the feature that
Garmin shows in their screenshots. It connects the "how did it feel"
chart with the "where was I" map into one instrument.

### Architecture

Create a shared context that both components read from and write to:

```tsx
// lib/context/StreamHoverContext.tsx
import { createContext, useContext, useState, ReactNode } from 'react';

interface StreamHoverState {
  hoveredIndex: number | null;
  setHoveredIndex: (index: number | null) => void;
}

const StreamHoverContext = createContext<StreamHoverState>({
  hoveredIndex: null,
  setHoveredIndex: () => {},
});

export function StreamHoverProvider({ children }: { children: ReactNode }) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  return (
    <StreamHoverContext.Provider value={{ hoveredIndex, setHoveredIndex }}>
      {children}
    </StreamHoverContext.Provider>
  );
}

export function useStreamHover() {
  return useContext(StreamHoverContext);
}
```

### Wiring

In the activity detail page (`[id]/page.tsx`), wrap the run section
in the provider:

```tsx
<StreamHoverProvider>
  {/* RunShapeCanvas */}
  {/* ... other components ... */}
  {/* RouteContext (map) */}
</StreamHoverProvider>
```

### RunShapeCanvas changes

The canvas already has mouse hover logic for its interaction overlay.
When the user hovers, it knows the stream index. Add:

```tsx
const { setHoveredIndex } = useStreamHover();

// In the existing hover handler:
onMouseMove={(e) => {
  // ... existing logic to calculate hovered stream index ...
  setHoveredIndex(index);
}}
onMouseLeave={() => setHoveredIndex(null)}
```

### Map changes

Read the hover state and render a position marker:

```tsx
const { hoveredIndex, setHoveredIndex } = useStreamHover();

// Inside the MapContainer, render a hover marker:
{hoveredIndex != null && streamPoints?.[hoveredIndex]?.lat != null && (
  <CircleMarker
    center={[streamPoints[hoveredIndex].lat!, streamPoints[hoveredIndex].lng!]}
    radius={6}
    pathOptions={{
      color: '#fff',
      weight: 2,
      fillColor: '#f59e0b',  // amber — distinct from start/end
      fillOpacity: 1,
    }}
  />
)}
```

For map-to-canvas linking (hover on map shows cursor on canvas):
add mouse event handlers to the Polyline segments. On hover over
segment `i`, call `setHoveredIndex(i)`. The RunShapeCanvas reads
`hoveredIndex` and renders a vertical cursor line at that position.

This is the most architecturally significant change. Take care to
debounce the hover updates (use `requestAnimationFrame` or throttle
to 60fps) to avoid janky rendering.

**Important:** The `StreamHoverProvider` must wrap BOTH the canvas
and the map. If the provider is too high in the tree and causes
unnecessary re-renders, use `React.memo` on child components that
don't need the hover state.

---

## 5. Ghost Maps for All Outdoor Sports

### What it is

Currently, route siblings are only queried for runs:

```tsx
// RouteContext.tsx, line 73
enabled: sportType === 'run' && track.length > 0,
```

Walking and cycling athletes repeat routes too. The same clustering
query works for any sport with GPS data.

### Change

```tsx
// Remove the run-only gate
enabled: track.length > 0,
```

Update the siblings API query to match on the same sport instead
of hardcoding 'run':

In `routers/activities.py`, the siblings query currently filters:
```python
Activity.sport == "run",
```

Change to:
```python
Activity.sport == activity.sport,
```

This gives "You've walked from here 12 times" for walking activities
and "You've cycled from here 8 times" for cycling.

Update the display text in `RouteContext.tsx`:

```tsx
// Instead of "You've run from here"
<span>
  You&apos;ve {sportVerb(sportType)} from here {siblingCount} time{siblingCount !== 1 ? 's' : ''}
</span>

// Helper
function sportVerb(sport: string): string {
  switch (sport) {
    case 'run': return 'run';
    case 'walking': return 'walked';
    case 'hiking': return 'hiked';
    case 'cycling': return 'cycled';
    default: return 'been';
  }
}
```

---

## 6. Effort-Normalized Map (the differentiator)

### What it is

Grade-adjusted pace at every GPS point. An 8:00/mi going uphill at
6% grade is much harder than an 8:00/mi on flat ground. This overlay
shows the TRUE effort at each point, removing terrain as a variable.

No competitor renders this on a map. This is the feature that makes
someone screenshot the map and post it in a running forum.

### Data available

`StreamPoint` already has `pace` (s/km) and `grade` (% gradient).
The adjustment formula is the same principle as heat adjustment:

```typescript
function gradeAdjustedPace(paceSkm: number, gradePct: number): number {
  // Minetti et al. cost of transport curve (simplified)
  // Each 1% uphill adds ~12 seconds per km of equivalent effort
  // Each 1% downhill subtracts ~7 seconds per km (asymmetric — downhill
  // is less beneficial than uphill is costly)
  const adjustment = gradePct > 0
    ? gradePct * 12   // uphill penalty
    : gradePct * 7;   // downhill benefit (less aggressive)
  return paceSkm - adjustment;  // lower = faster = more effort
}
```

### Rendering

This is a toggle on the map: "Show effort" button switches from
raw pace coloring to grade-adjusted pace coloring. Same color
scale (green→yellow→red), but the values are adjusted.

```tsx
const [showEffort, setShowEffort] = useState(false);

// Toggle button below the legend
<button
  onClick={() => setShowEffort(!showEffort)}
  className="text-[10px] text-slate-500 hover:text-slate-300 mt-0.5"
>
  {showEffort ? 'Show pace' : 'Show effort'}
</button>
```

When `showEffort` is true, use `gradeAdjustedPace(p.pace, p.grade)`
instead of `p.pace` when calculating segment colors.

The visual result: a hilly route where the athlete maintained effort
shows as uniformly green (same effort throughout), even though the
raw pace varied dramatically with terrain. This is the truth about
the run that raw pace hides.

---

## 7. Route Performance View (the route as an entity)

### What it is

When an athlete has run or walked the same route multiple times, show
the performance trajectory — not just a count. Strava calls this
"Matched Activities." We have the data. We show "You've walked from
here 9 times" and stop. That's a wasted opportunity.

This view turns "9 times" into a performance story: Am I getting
faster? How does today compare to my best? What were conditions like
on my fastest effort?

### Data source

The route siblings endpoint (`GET /v1/activities/{id}/route-siblings`)
already returns matching activities with `distance_m`, `duration_s`,
`start_time`, `temperature_f`, `dew_point_f`, `workout_type`. Add
`avg_hr` and `avg_speed_mps` (or compute speed from distance/duration)
to the sibling response if not already present.

**Backend change:** In `routers/activities.py`, ensure each sibling
in the response includes:

```python
entry = {
    "id": str(s.id),
    "start_time": s.start_time.isoformat(),
    "distance_m": s.distance_m,
    "duration_s": s.duration_s or s.moving_time_s,
    "temperature_f": s.temperature_f,
    "dew_point_f": s.dew_point_f,
    "workout_type": s.workout_type,
    "avg_hr": s.avg_hr,                        # ADD
    "name": s.name,                             # ADD
    "total_elevation_gain": s.total_elevation_gain,  # ADD
}
```

Speed is derived on the frontend: `distance_m / duration_s`.

### Frontend: Expand the route context panel

When the athlete clicks/taps the "You've run from here N times" text
(or a dedicated "Route history" button), expand an inline panel below
the map showing:

#### A. Summary stats (always visible when expanded)

```
This route: 9 efforts
Today: 2.7 mi/h · -0.1 vs average
Best: 3.5 mi/h (Oct 2, 2024) · Avg: 2.8 mi/h · Slowest: 2.3 mi/h
```

#### B. Trend chart (inline, compact)

A small line chart (same height as the elevation profile, ~60px)
showing speed (or pace for runs) over time, with:
- Dots for each effort
- Current effort highlighted (larger dot, accent color)
- Trending average line (use rolling 3-effort average)
- Fastest/slowest/average labels on the right edge

Use the same SVG approach as the elevation profile — no need for
a charting library.

```tsx
<RouteTrendChart
  siblings={siblings.siblings}
  currentActivityId={activityId}
  currentSpeed={currentDistanceM / currentDurationS}
  sportType={sportType}
/>
```

For runs, show pace (min/mi or min/km) — lower is better, so invert
the Y axis. For walks/cycling, show speed (mi/h or km/h) — higher
is better.

#### C. Comparison table (collapsible)

A clean table below the chart:

| Date | Name | Speed | +/- Avg | Duration | Conditions |
|------|------|-------|---------|----------|------------|

- Sort by date descending (most recent first)
- Current activity highlighted with accent color left-border
- "+/- Avg" shows delta from all-time average (green positive,
  red negative)
- "Conditions" shows temperature + weather icon
- Each row links to that activity's detail page

#### D. Route identity

If the athlete has 6+ efforts on this route, display a one-line
route identity:

```
"Your neighborhood loop — averaging 2.8 mi/h, trending flat"
```

- "trending up" / "trending flat" / "trending down" based on the
  slope of the last 5 efforts vs the first 5
- Keep this dead simple. One sentence. No LLM call needed.

### Interaction model

The route performance panel is **collapsed by default** — the map
shows the sibling count text as it does now. Tapping the count or
a "See route history" button expands the panel inline (not a new
page, not a modal). This keeps the athlete in context while adding
depth.

```tsx
const [showRouteHistory, setShowRouteHistory] = useState(false);

{siblingCount > 0 && (
  <button
    onClick={() => setShowRouteHistory(!showRouteHistory)}
    className="flex items-center gap-1.5 text-xs text-slate-400
               hover:text-slate-200 transition-colors"
  >
    <MapPin className="w-3 h-3" />
    <span>
      You've {sportVerb(sportType)} from here {siblingCount} times
      {conditionsMatch > 0 && ` · ${conditionsMatch} in similar conditions`}
    </span>
    <ChevronDown className={`w-3 h-3 transition-transform ${showRouteHistory ? 'rotate-180' : ''}`} />
  </button>
)}

{showRouteHistory && (
  <RoutePerformancePanel
    siblings={siblings}
    currentActivityId={activityId}
    currentDistanceM={...}
    currentDurationS={...}
    sportType={sportType}
    unitSystem={unitSystem}
  />
)}
```

---

## Build Order

1. Backend: add `lat`/`lng` to `StreamPoint` — deploy immediately
2. Pace-colored route — deploy
3. Elevation profile — deploy
4. Weather badge — deploy
5. Ghost maps for all sports — deploy
6. Route performance view — deploy
7. Chart-map linking — deploy
8. Effort-normalized toggle — deploy

Each deploys independently. Don't batch. Ship and verify each one.

---

## Acceptance Criteria

### Pace-colored route
- [ ] Route shows green/yellow/red segments matching pace variation
- [ ] Legend below map reads "Slower ◄ gradient ► Faster"
- [ ] Glow layer still visible beneath pace segments
- [ ] Start/end markers still visible above segments
- [ ] Falls back to flat color for non-run activities

### Elevation profile
- [ ] Thin SVG area chart appears below map for runs
- [ ] Shows elevation range label (e.g., "142 ft range")
- [ ] Profile shape matches the terrain of the route

### Weather badge
- [ ] Temperature, weather icon, and humidity shown on map
- [ ] Positioned to not overlap fullscreen button or zoom controls
- [ ] Only shows when weather data exists

### Chart-map linking
- [ ] Hover on RunShapeCanvas → amber dot on map at that position
- [ ] Hover on map route → vertical cursor on RunShapeCanvas
- [ ] Smooth (60fps), no jank
- [ ] Hover clears when mouse leaves either component

### Ghost maps for all sports
- [ ] Walking activity shows "You've walked from here N times"
- [ ] Ghost button appears when threshold (6) is met
- [ ] Ghosts render for walking/cycling, not just runs

### Route performance view
- [ ] Tapping sibling count expands inline panel (not a modal/page)
- [ ] Summary shows today's speed/pace, +/- average, best/worst/avg
- [ ] Trend chart renders with dots per effort, current highlighted
- [ ] Trending average line visible
- [ ] Comparison table shows all matched efforts with delta from avg
- [ ] Each table row links to that activity's detail page
- [ ] Current activity row highlighted
- [ ] Works for walks AND runs (speed for walks, pace for runs)
- [ ] Panel collapses cleanly back to the count text

### Effort-normalized
- [ ] Toggle button switches between "pace" and "effort" coloring
- [ ] Hilly route shows more uniform color in effort mode
- [ ] Flat route looks identical in both modes (as expected)

### Mobile test
- [ ] Pace colors visible and distinct on phone screen
- [ ] Weather badge readable, not overlapping controls
- [ ] Elevation profile visible, not cut off
- [ ] Ghost maps work on mobile

---

## Do NOT

- Do not create a new API endpoint for the map data — extend the
  existing stream-analysis response with lat/lng
- Do not re-implement LTTB downsampling — use existing code path
- Do not add Mapbox, Google Maps, or any paid tile service
- Do not change the RunShapeCanvas rendering logic beyond adding
  hover event emissions
- Do not change the route siblings SQL query logic beyond the sport
  filter change
- Do not ship all 7 items at once — deploy and verify each one
