# Builder Instructions: Map Polish — Corrections

**Date:** April 5, 2026
**From:** Advisor
**Priority:** Fix in order listed. These are quality corrections, not new features.
**Scope:** Frontend only. No backend changes.

---

## What happened

Phase 2 shipped 7 features. Several have errors or fail the quality
bar when compared to what every other running app shows. This document
corrects them.

---

## Fix 1: Flip the Pace Gradient (WRONG DIRECTION)

The pace coloring is backwards. We render green = fast, red = slow.
Every running app, every heart rate zone chart, and every athlete's
mental model associates:

- **Red / orange = fast, intense, hard effort, "red-lining"**
- **Blue / green = slow, easy, recovery**

This is not a style preference. It's a convention that every runner
has internalized from years of HR zone charts, Strava, Garmin, and
training plans. We violated it. Fix it.

```tsx
// CORRECT color scale: blue (slow) → yellow (mid) → red (fast)
function paceColor(t: number): string {
  // t: 0 = fastest, 1 = slowest
  if (t < 0.5) {
    // Red (fastest) → Yellow (mid)
    const g = Math.round(180 * (t * 2));
    return `rgb(235, ${g}, 50)`;
  } else {
    // Yellow (mid) → Blue (slowest)
    const r = Math.round(235 * (1 - (t - 0.5) * 2));
    const b = Math.round(180 * ((t - 0.5) * 2));
    return `rgb(${r}, ${180 - b / 2}, ${50 + b})`;
  }
}
```

Update the legend to match:

```tsx
<div className="flex items-center gap-2 mt-1 px-1">
  <span className="text-[10px] text-slate-500">Slower</span>
  <div className="flex-1 h-1 rounded-full"
    style={{ background: 'linear-gradient(to right, #3b82f6, #eab308, #ef4444)' }}
  />
  <span className="text-[10px] text-slate-500">Faster</span>
</div>
```

Blue on the left (slow), red on the right (fast).

Also: **shrink the legend bar.** It's too prominent. Reduce height
from whatever it is now to `h-1` (4px). It's a reference, not a
feature. It should be barely there — athletes will understand the
colors after seeing them once.

### Color scale calibration

The current min/max normalization makes most of a hilly run look
red (slow) because a few fast downhill strides pull the scale.
Switch to **percentile-based scaling**:

```tsx
function buildPaceSegments(stream: StreamPoint[]): PaceSegment[] {
  const withGps = stream.filter(p => p.lat != null && p.pace != null);
  if (withGps.length < 2) return [];

  const paces = withGps.map(p => p.pace!).sort((a, b) => a - b);
  // Use 5th and 95th percentile to avoid outlier distortion
  const p5 = paces[Math.floor(paces.length * 0.05)];
  const p95 = paces[Math.floor(paces.length * 0.95)];
  const range = p95 - p5 || 1;

  const segments: PaceSegment[] = [];
  for (let i = 0; i < withGps.length - 1; i++) {
    const p = withGps[i];
    const next = withGps[i + 1];
    // Clamp to [0, 1] — outliers get full red or full blue
    const t = Math.max(0, Math.min(1, (p.pace! - p5) / range));
    segments.push({
      positions: [[p.lat!, p.lng!], [next.lat!, next.lng!]],
      color: paceColor(t),
    });
  }
  return segments;
}
```

This distributes color across the actual pace range the athlete
experienced, not the extremes.

---

## Fix 2: Make the Elevation Profile Interactive

The static elevation profile breaks trust. It looks like something
you should be able to hover on, and when you can't, it signals
"this app is half-built."

Every running app with an elevation profile makes it interactive:
hover to see gradient, pace, HR, elevation at that point, AND a
dot moves on the map.

### Architecture

The `StreamHoverContext` already exists (canvas→map linking). The
elevation profile is another surface that reads from and writes to
the same context. When the athlete hovers on the elevation profile:

1. Calculate which stream point is under the cursor (based on X
   position relative to the SVG width)
2. Call `setHoveredIndex(index)` on the shared context
3. The map reads `hoveredIndex` and shows the amber dot
4. A tooltip appears over the elevation profile showing data at
   that point

When the athlete hovers on the RunShapeCanvas or the map, the
elevation profile reads `hoveredIndex` and shows a vertical cursor
line at that position.

### Implementation

Replace the static SVG with an interactive component:

```tsx
function ElevationProfile({
  points,
  accentColor = '#3b82f6',
  height = 56,
}: {
  points: StreamPoint[];
  accentColor?: string;
  height?: number;
}) {
  const { hoveredIndex, setHoveredIndex } = useStreamHover();
  const containerRef = useRef<HTMLDivElement>(null);
  const [tooltip, setTooltip] = useState<{
    x: number;
    index: number;
  } | null>(null);

  const altitudes = useMemo(() =>
    points.map(p => p.altitude).filter((a): a is number => a != null),
    [points]
  );

  if (altitudes.length < 2) return null;

  const min = Math.min(...altitudes);
  const max = Math.max(...altitudes);
  const range = max - min || 1;
  const svgWidth = 1000;

  const xStep = svgWidth / (altitudes.length - 1);
  const toY = (alt: number) =>
    height - ((alt - min) / range) * (height - 6) - 3;

  const linePath = altitudes
    .map((alt, i) => `${i === 0 ? 'M' : 'L'} ${i * xStep} ${toY(alt)}`)
    .join(' ');
  const areaPath = `${linePath} L ${(altitudes.length - 1) * xStep} ${height} L 0 ${height} Z`;

  const handleMouseMove = (e: React.MouseEvent) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const x = e.clientX - rect.left;
    const pct = x / rect.width;
    const index = Math.round(pct * (points.length - 1));
    const clamped = Math.max(0, Math.min(points.length - 1, index));
    setHoveredIndex(clamped);
    setTooltip({ x, index: clamped });
  };

  const handleMouseLeave = () => {
    setHoveredIndex(null);
    setTooltip(null);
  };

  // External hover (from canvas or map) — show cursor line
  const cursorX = hoveredIndex != null
    ? (hoveredIndex / (points.length - 1)) * 100
    : null;

  const hovered = tooltip != null ? points[tooltip.index] : null;

  return (
    <div className="mt-1 px-1" ref={containerRef}>
      <div className="flex items-center justify-between mb-0.5">
        <span className="text-[10px] text-slate-500">Elevation</span>
        <span className="text-[10px] text-slate-500">
          {Math.round((max - min) * 3.281)} ft range
        </span>
      </div>

      <div
        className="relative cursor-crosshair"
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      >
        <svg
          viewBox={`0 0 ${svgWidth} ${height}`}
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
          <path d={linePath} fill="none" stroke={accentColor}
                strokeWidth="2" opacity="0.5" />
        </svg>

        {/* Cursor line from any hover source */}
        {cursorX != null && (
          <div
            className="absolute top-0 bottom-0 w-px bg-slate-400/50"
            style={{ left: `${cursorX}%` }}
          />
        )}

        {/* Tooltip on direct hover */}
        {tooltip != null && hovered && (
          <div
            className="absolute -top-16 px-2 py-1.5 rounded bg-slate-800/95
                        border border-slate-600/40 text-[10px] leading-tight
                        pointer-events-none z-10 whitespace-nowrap"
            style={{
              left: tooltip.x,
              transform: 'translateX(-50%)',
            }}
          >
            {hovered.altitude != null && (
              <div className="text-slate-300">
                {Math.round(hovered.altitude * 3.281)} ft
              </div>
            )}
            {hovered.grade != null && (
              <div className="text-slate-400">
                {hovered.grade > 0 ? '+' : ''}{hovered.grade.toFixed(1)}%
              </div>
            )}
            {hovered.pace != null && (
              <div className="text-slate-400">
                {formatPaceFromSKm(hovered.pace)}
              </div>
            )}
            {hovered.hr != null && (
              <div className="text-red-400/80">
                {hovered.hr} bpm
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// Helper — seconds/km to min:ss/mi display
function formatPaceFromSKm(sPerKm: number): string {
  const sPerMi = sPerKm * 1.60934;
  const min = Math.floor(sPerMi / 60);
  const sec = Math.round(sPerMi % 60);
  return `${min}:${sec.toString().padStart(2, '0')}/mi`;
}
```

**Key behaviors:**
- Hover on elevation profile → tooltip with elevation, grade, pace,
  HR appears AND amber dot moves on map
- Hover on RunShapeCanvas → cursor line appears on elevation profile
  at corresponding position
- Hover on map → cursor line appears on elevation profile
- All three surfaces are connected through `StreamHoverContext`
- `cursor-crosshair` CSS signals interactivity

**Unit awareness:** Use the athlete's unit preference from `useUnits()`
for elevation (ft vs m) and pace (min/mi vs min/km). The example
above hardcodes imperial — make it respect the setting.

---

## Fix 3: Reduce Ghost Trace Visual Weight

The ghost traces compete with the pace-colored route for visual
attention. The current run must always be the visual hero.

Current: `weight: 2, opacity: 0.30` for recent ghosts.

Change to: `weight: 1.5, opacity: 0.15` for recent (≤30 days),
scaling down to `opacity: 0.06` for oldest. The ghosts should be
barely there — a whisper of history, not a competing signal.

```tsx
function computeGhostOpacity(siblingDate: string, currentDate: string): number {
  const daysAgo = /* ... same calculation ... */;
  if (daysAgo <= 30) return 0.15;
  if (daysAgo <= 60) return 0.10;
  if (daysAgo <= 90) return 0.07;
  return 0.05;
}

// In the Polyline for ghosts:
pathOptions={{
  color: '#94a3b8',
  weight: 1.5,      // was 2
  opacity: g.opacity,
}}
```

---

## Fix 4: Mile Marker Overlap on Loop Routes

On loop or out-and-back routes, mile markers from different parts
of the route stack on top of each other in the same area. Markers
1, 4, and 10 on top of each other is unreadable.

### Solution: Collision detection with suppression

After calculating all mile marker positions, check for overlaps.
If two markers are within 30px of each other at the current zoom
level, hide the less important one (keep the first and last, and
every Nth marker for round numbers).

Simpler approach: **only show markers at round intervals based on
distance.** For routes under 5 miles/km: show every mile. For
5-15: show every 2. For 15+: show every 5. This naturally reduces
density.

```tsx
function filterMileMarkers(
  markers: { position: [number, number]; label: string }[],
  totalCount: number,
): typeof markers {
  if (totalCount <= 5) return markers;
  const interval = totalCount <= 15 ? 2 : 5;
  return markers.filter((_, i) => {
    const mile = i + 1;
    return mile === 1 || mile === totalCount || mile % interval === 0;
  });
}
```

This gives clean results:
- 3-mile run: markers at 1, 2, 3
- 10-mile run: markers at 1, 2, 4, 6, 8, 10
- 22-mile long run: markers at 1, 5, 10, 15, 20, 22

---

## Fix 5: End Marker on Loop Routes

On a loop route, the start and end markers overlap because they're
at the same GPS position. The athlete can't tell if the run ended
where it started.

For out-and-back or loop routes where start and end are within 50m:
replace both markers with a single combined marker. Use a circle
that's half green (start) and half red (finish):

```tsx
// Check if start ≈ end (within ~50m)
const isLoop = track.length > 1 &&
  haversine(track[0], track[track.length - 1]) < 50;

{isLoop ? (
  // Single start/finish marker
  <CircleMarker
    center={track[0]}
    radius={8}
    pathOptions={{
      color: '#fff',
      weight: 2,
      fillColor: '#22c55e',  // green dominates — "you finished where you started"
      fillOpacity: 1,
    }}
  />
) : (
  <>
    {/* Separate start (green) and end (red) markers */}
    <CircleMarker center={track[0]} ... fillColor="#22c55e" />
    <CircleMarker center={track[track.length - 1]} ... fillColor="#ef4444" />
  </>
)}
```

---

## Acceptance Criteria

- [ ] Pace gradient: red = fast, blue = slow (matches every running app)
- [ ] Legend bar is thin (4px), not prominent
- [ ] Color distribution: a hilly run shows varied colors, not 80% one color
- [ ] Elevation profile: hovering shows tooltip with elevation, grade, pace, HR
- [ ] Elevation profile: hovering moves amber dot on map
- [ ] Elevation profile: cursor line appears when hovering RunShapeCanvas
- [ ] Ghost traces: barely visible, current run is clearly the hero
- [ ] Mile markers: no stacking on loop routes, clean intervals
- [ ] Loop routes: single start/finish marker, not overlapping circles
- [ ] Test on the founder's Meridian 14-mile run (hilly loop — the stress test)
- [ ] Test on the founder's walking activity (short out-and-back)
- [ ] Mobile: tooltip readable, not clipped off screen edge

---

## Do NOT

- Do not add any new features — this is polish on existing features
- Do not change the StreamHoverContext architecture
- Do not modify the backend
- Do not change map tiles or controls
- Do not ship without testing on the founder's actual activities
