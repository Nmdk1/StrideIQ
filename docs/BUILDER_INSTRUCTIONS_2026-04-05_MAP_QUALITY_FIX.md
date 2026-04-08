# Builder Instructions: Map Quality Fix

**Date:** April 5, 2026
**From:** Advisor
**Priority:** Urgent — the founder saw the map and called it "useless"
**Scope:** Frontend only — no backend changes needed

---

## What happened

The map shipped as a bare Leaflet demo. Zoom controls were explicitly
disabled. Scroll-wheel zoom was explicitly disabled. There are no
start/end markers, no mile markers, no pace coloring, no fullscreen,
no elevation context. The route is a thin 3-pixel line on tiles so
dark the streets are invisible.

The founder compared it to Strava, Garmin Connect, and Nike Run Club
and said: "the map is useless. just a neon line on a dark background."

This is not a feature request. This is a quality correction. The bar
for shipping a map in a running app is what every other running app
ships. We fell below that bar.

---

## Quality Principle (apply to all future UI work)

**Before shipping any visual component, open Strava or Garmin Connect
and look at their equivalent. If ours is missing controls, markers,
or interactions that theirs provides as baseline, we are not done.**

This is not about copying. It's about meeting the minimum expectation
an athlete has when they see a map of their activity. They've seen
hundreds of activity maps. If ours is missing the basics, it signals
"this app doesn't care about my data."

---

## Files to modify

All changes are in:
- `apps/web/components/activities/map/ActivityMapInner.tsx` (main map)
- `apps/web/components/activities/map/RouteContext.tsx` (context wrapper)
- Possibly a new `MileMarkers.tsx` or `ElevationProfile.tsx` if extracted

No backend changes. The GPS data, elevation data, pace data, and split
data are all already available on the activity detail response.

---

## Fix 1: Enable Map Controls

Current code explicitly disables controls:

```tsx
// WRONG — currently shipped
<MapContainer
  scrollWheelZoom={false}
  zoomControl={false}
  attributionControl={false}
/>
```

Fix:

```tsx
<MapContainer
  scrollWheelZoom={true}
  zoomControl={true}
  attributionControl={true}
  dragging={true}
/>
```

Leaflet gives you zoom buttons and touch zoom for free. Disabling them
was an active decision to make the map worse. Re-enable them.

Keep `attributionControl` — CartoDB requires attribution, and hiding it
is a terms-of-service violation.

---

## Fix 2: Better Tile Layer

CartoDB Dark Matter (`dark_all`) renders streets as nearly invisible
dark-gray-on-black lines. On most screens, you cannot see where you ran
relative to actual geography.

Switch to **CartoDB Voyager** with a CSS brightness/contrast filter to
maintain dark aesthetic while keeping streets and labels readable:

```tsx
const CARTO_VOYAGER = 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png';

// In the MapContainer's parent div, apply:
<div style={{ filter: 'brightness(0.75) contrast(1.1) saturate(0.5)' }}>
  <MapContainer ...>
    <TileLayer url={CARTO_VOYAGER} ... />
  </MapContainer>
</div>
```

This gives you a dark map where you can actually **see the streets and
landmarks**. The route line remains the brightest element. Adjust
brightness value (0.65–0.80) to taste.

If this doesn't look right, an alternative is Stadia Alidade Smooth
Dark (needs free API key) or keeping Dark Matter but increasing
`brightness` to 1.3 and `contrast` to 1.2 to lift the labels.

Test both approaches and pick whichever makes street names readable
on a phone screen in daylight.

---

## Fix 3: Start and End Markers

Every running app marks where you started and finished. We show nothing.

Add two `CircleMarker` components:

```tsx
import { CircleMarker } from 'react-leaflet';

// Start marker — green
{track.length > 0 && (
  <CircleMarker
    center={track[0]}
    radius={7}
    pathOptions={{
      color: '#fff',
      weight: 2,
      fillColor: '#22c55e',
      fillOpacity: 1,
    }}
  />
)}

// End marker — red/checkered
{track.length > 1 && (
  <CircleMarker
    center={track[track.length - 1]}
    radius={7}
    pathOptions={{
      color: '#fff',
      weight: 2,
      fillColor: '#ef4444',
      fillOpacity: 1,
    }}
  />
)}
```

Render start/end markers ABOVE the route polyline (after it in JSX)
so they're always visible.

---

## Fix 4: Thicker Route Line with Glow

Current: `weight: 3, opacity: 0.9` — too thin, no depth.

Replace the single Polyline with a two-layer approach:

```tsx
{/* Shadow/glow layer */}
{track.length > 1 && (
  <Polyline
    positions={track}
    pathOptions={{
      color: accentColor,
      weight: 8,
      opacity: 0.25,
      lineCap: 'round',
      lineJoin: 'round',
    }}
  />
)}

{/* Main route layer */}
{track.length > 1 && (
  <Polyline
    positions={track}
    pathOptions={{
      color: accentColor,
      weight: 4,
      opacity: 1,
      lineCap: 'round',
      lineJoin: 'round',
    }}
  />
)}
```

This gives the route depth and makes it the visual hero of the map.

---

## Fix 5: Mile/Km Markers Along Route

Calculate cumulative distance along GPS points. At each mile (or km,
based on user's unit preference), place a small label marker.

Implementation approach:

```tsx
function computeMileMarkers(
  track: [number, number][],
  unitSystem: 'imperial' | 'metric'
): { position: [number, number]; label: string }[] {
  const markers: { position: [number, number]; label: string }[] = [];
  const interval = unitSystem === 'imperial' ? 1609.34 : 1000; // miles or km
  let cumulative = 0;
  let nextMark = interval;

  for (let i = 1; i < track.length; i++) {
    const d = haversine(track[i - 1], track[i]);
    cumulative += d;
    if (cumulative >= nextMark) {
      const n = Math.round(nextMark / interval);
      markers.push({
        position: track[i],
        label: String(n),
      });
      nextMark += interval;
    }
  }
  return markers;
}

// Haversine helper (meters)
function haversine([lat1, lon1]: [number, number], [lat2, lon2]: [number, number]): number {
  const R = 6371000;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}
```

Render each marker as a Leaflet `DivIcon` or `Marker` with a custom
HTML icon — a small dark circle with the mile number in white:

```tsx
import { Marker } from 'react-leaflet';
import L from 'leaflet';

{mileMarkers.map((m) => (
  <Marker
    key={m.label}
    position={m.position}
    icon={L.divIcon({
      className: '',
      html: `<div style="
        background: rgba(15, 23, 42, 0.85);
        border: 1.5px solid rgba(148, 163, 184, 0.5);
        color: #e2e8f0;
        font-size: 11px;
        font-weight: 600;
        width: 22px;
        height: 22px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
      ">${m.label}</div>`,
      iconSize: [22, 22],
      iconAnchor: [11, 11],
    })}
  />
))}
```

The unit system should come from the `useUnits()` hook (already
available in the activity page). Pass it through to `RouteContext`
as a new prop: `unitSystem: 'imperial' | 'metric'`.

---

## Fix 6: Full-Screen Toggle

Add a button in the top-right corner of the map to toggle full-screen.
On click, the map container expands to fill the viewport. On second
click (or Escape), it returns to normal.

```tsx
const [isFullscreen, setIsFullscreen] = useState(false);

// Wrap the map container in a div that handles fullscreen:
<div className={isFullscreen
  ? 'fixed inset-0 z-50 bg-slate-900'
  : 'relative rounded-lg overflow-hidden border border-slate-700/30'}
  style={isFullscreen ? undefined : { height }}
>
  {/* Fullscreen toggle button */}
  <button
    onClick={() => setIsFullscreen(!isFullscreen)}
    className="absolute top-3 right-3 z-[1000] p-1.5 rounded-md
               bg-slate-900/80 border border-slate-600/50
               text-slate-300 hover:text-white hover:bg-slate-800
               transition-colors"
    aria-label={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
  >
    {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
  </button>

  {/* Close button visible only in fullscreen */}
  {isFullscreen && (
    <button
      onClick={() => setIsFullscreen(false)}
      className="absolute top-3 left-3 z-[1000] ..."
    >
      <X className="w-5 h-5" />
    </button>
  )}

  <MapContainer ... style={{ height: '100%', width: '100%' }}>
    ...
  </MapContainer>
</div>
```

When toggling fullscreen, call `map.invalidateSize()` after the
transition so Leaflet recomputes tile positions. Use the `useMap()`
hook inside a child component that watches the fullscreen state.

Import icons from lucide-react: `Maximize2`, `Minimize2`, `X`.

---

## Fix 7: Elevation Mini-Profile (if elevation data is available)

The activity detail response already includes `total_elevation_gain_m`.
The `ActivityStream` has `altitude` in `channels_available` for runs.

For this fix, pass the elevation profile data from the stream through
the activity response (or use the existing GPS points with altitude
if the backend `gps_track` includes elevation). If not, add elevation
to the backend response as a parallel array: `elevation_profile: number[]`
matching the downsampled GPS track.

Render a small SVG area chart below the map:

```tsx
<div className="h-12 mt-1 px-2">
  <svg viewBox={`0 0 ${width} 48`} className="w-full h-full">
    <defs>
      <linearGradient id="elev-fill" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor={accentColor} stopOpacity="0.3" />
        <stop offset="100%" stopColor={accentColor} stopOpacity="0.05" />
      </linearGradient>
    </defs>
    <path d={areaPath} fill="url(#elev-fill)" />
    <path d={linePath} fill="none" stroke={accentColor} strokeWidth="1.5" opacity="0.6" />
  </svg>
</div>
```

If the elevation data isn't available on the current response, this
can be deferred — but note it as a fast follow. The priority is
Fixes 1-6.

---

## Fix 8: Map Height

Current heights are too small:
- Walking/hiking hero: 280px
- Run secondary: 250px

Change to:
- Walking/hiking/cycling hero: **350px**
- Run secondary: **300px**
- Full-screen: **100vh**

These values give the map presence. On mobile, 350px is roughly half
the screen — enough to see the route in context.

---

## Acceptance Criteria

Before marking this complete, verify each of these on a real activity
page (not localhost — production, on the founder's account):

- [ ] Map has visible zoom controls (+ / - buttons)
- [ ] Map can be zoomed with scroll wheel (desktop) and pinch (mobile)
- [ ] Map can be dragged to pan
- [ ] Green circle marks the start of the route
- [ ] Red circle marks the end of the route
- [ ] Mile markers appear along the route at each mile boundary
- [ ] Route line is visibly thicker than current, with glow effect
- [ ] Street names and labels are readable on the map tiles
- [ ] Full-screen button exists and works (expand + collapse)
- [ ] Map attribution is visible (CartoDB + OSM)
- [ ] Map renders on runs (not just walking) — verify on the founder's
  most recent "Meridian Running" activity
- [ ] Map renders on walking activities with correct accent color

**Test on mobile.** Open the activity page on a phone. Can you:
- See where the run happened (street names visible)?
- See the start and end points?
- Zoom in and out with pinch?
- Tell which mile you're looking at?

If any answer is "no," the map is not done.

---

## Backend Note: Why runs should already have maps

The GPS data exists for all of the founder's runs. The most recent
"Meridian Running" has 8,260 latlng points in the ActivityStream.
The `gps_track` field on the API response should be populated.

If maps are not appearing for runs, check:
1. The `gps_track` extraction code in `routers/activities.py` (line
   that checks `activity.sport == "run"` and queries `ActivityStream`)
2. Whether the frontend is receiving `gps_track` in the API response
   (check browser DevTools Network tab)
3. Whether `activity.gps_track.length > 1` evaluates true in the page

The walking activity works because it extracts GPS from
`session_detail.detail_webhook_raw.samples`. Runs use a different
code path (`ActivityStream.stream_data.latlng`). Both paths were
implemented — verify both are returning data.

---

## Do NOT

- Do not change the backend API response structure
- Do not add new API endpoints
- Do not change the route siblings / ghost map logic
- Do not touch `RunShapeCanvas`, `RuntoonCard`, or any non-map component
- Do not use a map library that requires an API key (no Mapbox, no Google Maps)
- Do not ship without testing on both mobile and desktop
