# Workstream 2 Spec: Activity Maps + Missing Metrics

**Date:** April 5, 2026
**Author:** Builder
**Status:** Awaiting advisor review

---

## 1. Map Library: react-leaflet + CartoDB Dark Tiles

**Recommendation: Leaflet/react-leaflet with free CartoDB dark tiles.**

Rationale:
- **Free, no API key** — consistent with Open-Meteo, the product's infrastructure philosophy. No usage-based billing surprises at scale.
- **react-leaflet v4** is the standard React wrapper, works with Next.js SSR (dynamic import with `ssr: false` since Leaflet requires `window`).
- **CartoDB Dark Matter tiles** (`https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png`) — free, dark-mode aesthetic that matches the slate/dark UI. No key, no signup.
- **Polyline rendering** is native Leaflet (`L.polyline`). No canvas overhead for basic traces.
- **Lightweight** — Leaflet CSS + JS is ~40KB gzipped. No heavy GL context like Mapbox.

Rejected alternatives:
- **Mapbox GL JS** — best dark-mode aesthetic, but requires API key and charges per map load after free tier. Wrong economic model for "every activity gets a map."
- **Google Maps** — API key + billing required. Overkill.
- **deck.gl** — powerful for 30+ overlapping traces (WebGL), but heavy dependency for V1. Can layer on top of Leaflet later if ghost maps need WebGL performance.

**Install:** `npm install react-leaflet leaflet` + `@types/leaflet` (dev)

---

## 2. API Changes

### 2A. Add GPS track to activity detail response

Extend `GET /v1/activities/{id}` — don't create a new endpoint. Add:

```python
# After the existing result dict build (line ~463 in activities.py)

# GPS track for map rendering
gps_track = None
start_coords = None

if activity.start_lat is not None and activity.start_lng is not None:
    start_coords = [activity.start_lat, activity.start_lng]

if activity.sport == "run":
    stream = db.query(ActivityStream).filter(
        ActivityStream.activity_id == activity.id
    ).first()
    if stream and "latlng" in (stream.channels_available or []):
        raw = stream.stream_data.get("latlng", [])
        # Filter nulls and downsample if >2000 points (perf)
        gps_track = [pt for pt in raw if pt is not None]
        if len(gps_track) > 2000:
            step = len(gps_track) // 2000
            gps_track = gps_track[::step]
else:
    # Non-run: extract from session_detail.detail_webhook_raw.samples
    sd = activity.session_detail or {}
    samples = (sd.get("detail_webhook_raw") or {}).get("samples") or []
    if samples:
        gps_track = [
            [s["latitudeInDegree"], s["longitudeInDegree"]]
            for s in samples
            if s.get("latitudeInDegree") is not None
            and s.get("longitudeInDegree") is not None
        ]
        if len(gps_track) > 2000:
            step = len(gps_track) // 2000
            gps_track = gps_track[::step]

result["gps_track"] = gps_track          # [[lat, lng], ...] or None
result["start_coords"] = start_coords    # [lat, lng] or None
```

Response shape addition:
```json
{
  "gps_track": [[34.7312, -86.5821], [34.7315, -86.5818], ...],
  "start_coords": [34.7312, -86.5821]
}
```

`gps_track` is `null` when no GPS data exists (strength, flexibility, manual activities).
`start_coords` is the fallback pin when no track but lat/lng exist.
Downsampled to max 2000 points — keeps JSON under ~50KB.

### 2B. Add missing metrics to activity detail response

Add these fields to the `result` dict in `get_activity`:

```python
# After the existing fields (around line 462)
"steps": activity.steps,
"active_kcal": activity.active_kcal,
"avg_cadence_device": activity.avg_cadence,
"max_cadence": activity.max_cadence,
```

`avg_cadence_device` is named distinctly from the existing `average_cadence` (which is derived from splits) to avoid confusion. The device-level value is what matters for walking/hiking/cycling where splits don't exist.

### 2C. Route siblings endpoint

New endpoint (not on the activity detail — it's a separate query):

```
GET /v1/activities/{activity_id}/route-siblings?limit=50
```

```python
@router.get("/{activity_id}/route-siblings")
def get_route_siblings(
    activity_id: UUID,
    limit: int = Query(default=50, le=100),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    activity = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.athlete_id == current_user.id,
    ).first()
    if not activity or activity.start_lat is None:
        return {"siblings": [], "count": 0}

    siblings = db.query(Activity).filter(
        Activity.athlete_id == current_user.id,
        Activity.sport == "run",
        Activity.id != activity_id,
        Activity.is_duplicate == False,
        Activity.start_lat.isnot(None),
        func.abs(Activity.start_lat - activity.start_lat) < 0.005,
        func.abs(Activity.start_lng - activity.start_lng) < 0.005,
        func.abs(Activity.distance_m - activity.distance_m) < Activity.distance_m * 0.15,
    ).order_by(Activity.start_time.desc()).limit(limit).all()

    return {
        "count": len(siblings),
        "siblings": [
            {
                "id": str(s.id),
                "start_time": s.start_time.isoformat(),
                "distance_m": s.distance_m,
                "duration_s": s.duration_s,
                "temperature_f": s.temperature_f,
                "workout_type": s.workout_type,
            }
            for s in siblings
        ],
    }
```

This returns the sibling metadata. GPS tracks for ghost rendering are fetched lazily per-sibling via the existing `/v1/activities/{id}/streams` endpoint — the frontend loads them on demand (user taps "Show ghost map"), not eagerly.

### 2D. Route siblings GPS batch endpoint

To avoid N+1 stream requests for ghost map, add a batch endpoint:

```
POST /v1/activities/route-siblings/tracks
Body: { "activity_ids": ["uuid1", "uuid2", ...] }
```

Returns `{ "tracks": { "uuid1": [[lat,lng],...], "uuid2": [...] } }`.

Fetches `ActivityStream.stream_data.latlng` for each, downsampled to 500 points per track. Caps at 30 sibling tracks per request.

---

## 3. Route Clustering

The query is exactly as described in the instructions — a WHERE clause on `start_lat`, `start_lng`, and `distance_m`. No geospatial indexes. No new tables. All columns already exist.

**Threshold values:**
- `0.005` degrees ≈ 500m radius (matches the ~500m instruction)
- `15%` distance tolerance (a 5-mile run matches 4.25–5.75 mile runs from the same start)

**Where it surfaces:**
- Activity detail page, below the map: "You've run from here 47 times"
- Tappable — expands to show ghost map toggle (if ≥ 6 siblings)

**Query cost:** Three indexed column filters on a per-athlete query. Sub-millisecond for any realistic activity count.

---

## 4. Ghost Map Rendering

**Trigger:** Only shown for run activities with ≥ 6 route siblings.

**Rendering approach:**
- Current run: solid colored line (blue, 3px weight)
- Ghost traces: translucent polylines rendered behind the current run

**Opacity weighting:**
- Base opacity: 0.08 (barely visible)
- Recency boost: +0.15 for runs in the last 30 days, +0.08 for 30-90 days
- Condition similarity: +0.05 if same `workout_type`, +0.05 if temperature within 10°F
- Max opacity per ghost: 0.35 (never overwhelms the current run)
- All ghosts use a neutral gray (`#94a3b8`, slate-400) — the current run is the colored one

**Performance with 30+ traces:**
- Each trace downsampled to 500 points server-side
- 30 traces × 500 points = 15,000 points total — Leaflet handles this natively without WebGL
- Traces loaded lazily (batch endpoint) only when user opts into ghost view
- If performance is an issue with 50+ traces, cap at 30 most recent and show "+20 more runs from here"

**UX flow:**
1. Activity loads → map shows current run trace
2. Below map: "You've run from here 47 times" (from route siblings query)
3. User taps → ghost traces fade in (batch GPS fetch)
4. Ghost traces render behind current run

---

## 5. Component Placement Per Sport

| Sport | Map position | Hero element |
|-------|-------------|-------------|
| Walking | **Map is hero** — full width, top of detail | Distance/duration summary below |
| Hiking | **Map is hero** — full width, elevation gain overlaid | Elevation profile below |
| Cycling | **Map is hero** — full width, top of detail | Distance/speed summary below |
| Run | **Secondary** — below the Run Shape Canvas | Run Shape Canvas remains hero |
| Strength | No map (indoor, no GPS) | Exercise sets |
| Flexibility | No map (indoor, no GPS) | Duration/HR |

For walking/hiking/cycling: the map answers "where did I go?" — the most natural first question. For runs, the Run Shape Canvas answers "how did it feel?" — the map is supplementary.

**Map sizing:**
- Mobile: full width, 250px height
- Tablet/Desktop: full width, 350px height
- Aspect ratio preserved with `aspect-[16/9]` container

**No map fallback:** When `gps_track` is null but `start_coords` exists, show a static pin on the map. When neither exists, show nothing (no map section at all).

---

## 6. Walking vs Hiking Label/Icon Fix

`HikingDetail.tsx` currently hardcodes `<Mountain>` icon and "Hiking" label.

**Fix:** Use the existing `SPORT_CONFIG` from `shared.tsx` which already has the correct mapping:
```typescript
// shared.tsx already defines:
hiking:  { icon: Mountain, label: 'Hiking', color: 'text-emerald-400' },
walking: { icon: Footprints, label: 'Walking', color: 'text-teal-400' },
```

Change `HikingDetail` to accept `sport_type` and read from `SPORT_CONFIG`:
```typescript
const config = SPORT_CONFIG[activity.sport_type] ?? SPORT_CONFIG.hiking;
// Then use config.icon, config.label, config.color
```

The component renders for both `walking` and `hiking` (already branched in `page.tsx`). The fix is ~5 lines.

---

## 7. Missing Metrics: Where They Render

| Metric | API field | Renders on | Display |
|--------|-----------|-----------|---------|
| Steps | `steps` | Walking/Hiking detail — headline metric | "2,694 steps" in elevation hero or as a MetricCard |
| Active calories | `active_kcal` | All cross-training detail pages | MetricCard: "285 kcal" |
| Avg cadence (device) | `avg_cadence_device` | Walking/Hiking (steps/min), Cycling (RPM) | MetricCard: "162 spm" or "85 rpm" |
| Max cadence | `max_cadence` | Walking/Hiking | MetricCard: "174 spm" |

For walking, **steps** is arguably the most important metric — promote it alongside distance and duration in the hero section, not buried in the grid.

**Frontend type update:** Add to `CrossTrainingActivity` interface:
```typescript
steps: number | null;
active_kcal: number | null;
avg_cadence_device: number | null;
max_cadence: number | null;
gps_track: [number, number][] | null;
start_coords: [number, number] | null;
```

---

## 8. Phase 2 Design Sketch (not for this build)

### Effort-Normalized Overlay
- Per-GPS-point grade-adjusted pace computed from elevation gradient between consecutive points
- Color the route trace: green (strong effort relative to grade), yellow (expected), red (under-performing for grade)
- Same principle as `heat_adjustment_pct` applied to elevation instead of temperature
- Requires per-second elevation data from `ActivityStream` (runs) or `session_detail.samples` (non-run)
- Math: Minetti gradient cost curve or Strava's GAP formula

### Body State Narrative Segments
- `run_shape` JSONB already contains phase segments (warmup, work, recovery, steady, progression)
- Map each segment to its GPS coordinates using the time/distance alignment
- Render as labeled colored sections on the route trace
- Each segment gets a tooltip: "Miles 3-5: steady state, HR 148 avg, 8:12/mi"
- Only for runs (run_shape only exists for runs)

Both require stable basic map + GPS rendering first. Spec fully after basic map ships and is tested with real data.

---

## Build Sequence

1. **API: add `gps_track`, `start_coords`, missing metrics** to `get_activity` response
2. **Install react-leaflet** + create `ActivityMap` component
3. **Walking/Hiking fix:** label, icon, steps/calories/cadence metrics
4. **Map placement:** hero for walk/hike/cycle, secondary for run
5. **Route siblings endpoint** + "You've run from here N times" display
6. **Ghost map:** batch tracks endpoint, opacity weighting, lazy load UX
7. Update `docs/SITE_AUDIT_LIVING.md`

Steps 1-4 can ship as one commit. Steps 5-6 as a second. Each CI green.

---

## What NOT to change
- Run Shape Canvas — untouched
- Correlation engine — untouched
- No new database tables or migrations
- No geospatial indexes
- No Mapbox/Google Maps API keys
