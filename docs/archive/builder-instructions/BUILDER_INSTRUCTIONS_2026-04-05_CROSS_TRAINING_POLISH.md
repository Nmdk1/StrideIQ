# Builder Instructions: Cross-Training Polish (3 Workstreams)

**Date:** April 5, 2026
**From:** Advisor
**Priority:** In order listed
**Approval required:** Write a brief spec for each workstream before building. The advisor will review.

---

## Context

Cross-training activity storage and display shipped (Phases 1-5, Apr 1-4).
Activities are captured and shown, but three gaps were identified from
the founder's own walking activity today:

1. Weather data comes from the Garmin wrist sensor (always wrong — reads body heat). We have a GPS-based weather API service that gives actual conditions, but it's not wired into the live ingestion pipeline.
2. No maps on any activity despite full GPS tracks being available.
3. Walking/hiking/cycling activities aren't acknowledged on the home page — you have to navigate to the activity list to see they happened.

Additionally, the walking detail page has specific issues:
- Labels "Hiking" instead of "Walking" (same component used for both)
- Missing metrics that exist in the database (steps, cadence, calories)
- Temperature from Garmin sensor is wildly inaccurate

---

## Workstream 1: Weather API Wiring (data quality — highest priority)

### What exists
- `services/weather_backfill.py` — complete Open-Meteo Historical Weather API integration
  - `fetch_weather_for_date(lat, lng, date)` — fetches hourly weather
  - `extract_weather_at_hour(data, hour)` — extracts temp, humidity, dew point, wind, condition
  - `backfill_weather_for_athlete()` — batch backfill for all activities
  - Uses GPS coordinates (activity's own lat/lng, or athlete's home location)
  - Free API, no key needed, historical data available

### What's broken
- This service is ONLY called as a manual backfill script
- It is NOT wired into the live ingestion pipeline
- Garmin webhook tasks don't extract or set `temperature_f` at all
- Strava sync uses Strava's device sensor temperature (also often wrong)
- The founder's walk today: Garmin sensor said 26°C (79°F), actual weather was 69°F

### What to build
After any activity is ingested with GPS coordinates, call the weather
API to populate `temperature_f`, `humidity_pct`, `dew_point_f`,
`weather_condition` from actual conditions at that location and time.

**Applies to ALL sports** — runs, walking, cycling, hiking. Not strength/flexibility (indoor).

**Integration points:**
- Garmin webhook: after activity is created/updated in `process_garmin_activity_task`
- Strava sync: in `post_sync_processing_task` (replace device sensor temp with API temp)
- Should be fire-and-forget (weather enrichment failure must not break activity ingestion)

**The `compute_activity_heat_fields()` call** should run AFTER the API weather
is set, not before, so dew_point and heat_adjustment use real data.

**Backfill:** Run `backfill_weather_for_athlete()` with `force=True` for the
founder to correct all historical activities that have wrong device sensor temps.

### Spec before building
Write a brief spec showing:
1. Where in the Garmin webhook task the weather call gets wired
2. Where in the Strava post-sync task it gets wired
3. How you handle the Open-Meteo API being a historical API (today's data
   may not be available for a few hours — strategy for retry or deferred enrichment)
4. Error handling (API down, no GPS, indoor activities)

---

## Workstream 2: Activity Maps

### What exists
- `start_lat` / `start_lng` on the Activity model (set for all outdoor activities)
- Full GPS tracks in `session_detail` samples for Garmin activities (lat/lng per sample)
- For Strava activities: `ActivityStream` may contain lat/lng streams
- No map component exists in the frontend

### What to build
A map component on the activity detail page for outdoor activities.

**Shows for:** running, walking, hiking, cycling (any activity with GPS data)
**Does NOT show for:** strength, flexibility (indoor, no GPS)

**Data source priority:**
1. `session_detail.detail_webhook_raw.samples[].latitudeInDegree/longitudeInDegree` (Garmin)
2. `ActivityStream` lat/lng data (Strava)
3. If neither exists, show a static pin at `start_lat/start_lng`

**Placement:** On the activity detail page. For walking/hiking/cycling, the map
IS the hero (it's the answer to "where did you go?"). For running, it's
secondary to the Run Shape Canvas — place below the pace chart.

**Map library:** Choose one (Mapbox GL, Leaflet/react-leaflet, or Google Maps).
Leaflet is free and open source. Mapbox has the best dark-mode aesthetic.
Spec your recommendation.

### 2B. Route Clustering & Ghost Map (run activities)

**This is the most important map feature. Do not treat the map as decoration.**

#### Route Clustering (no new infrastructure — it's a query)

Most runners run the same 3-5 routes year-round. Route matching for
real athletes is NOT a geospatial service — it's a WHERE clause:

```sql
SELECT * FROM activity
WHERE athlete_id = :athlete_id
  AND sport = 'run'
  AND ABS(start_lat - :this_lat) < 0.005   -- ~500m radius
  AND ABS(start_lng - :this_lng) < 0.005
  AND ABS(distance_m - :this_distance) < distance_m * 0.15
ORDER BY start_time DESC
```

This gives "all runs from the same starting area at the same approximate
distance." For a runner who does weekday home runs and weekend trail runs,
this produces route clusters instantly. No polyline comparison. No new
tables. No geospatial indexes. Columns already exist on every Activity.

When viewing any outdoor activity, query for siblings and show the count:
"You've run from here 47 times."

#### Ghost Map

Once you have route siblings, render them. Load the GPS tracks from
sibling activities and draw them as translucent traces behind the
current run.

- **Weighting:** More recent = more opaque. Similar conditions (temperature,
  workout type) = more opaque. Oldest/different conditions = most transparent.
- **Value:** The athlete sees exactly where they are gaining on their history
  and where they are losing it. Not a summary number — a specific location
  on a specific section where they are consistently faster or slower.
- **Data threshold:** 6-8 runs of the same route gives meaningful ghosts.
  Most serious runners accumulate this in 2-3 months for their primary
  route. The founder has 30-50+ runs from each regular location already.

#### Effort-Normalized Overlay (Phase 2 — after basic map ships)

Grade-adjusted pace at every GPS point. The math is identical to
heat adjustment: take raw pace, adjust for elevation gradient at that
point, render the flat-equivalent pace.

- A 7:30/mi uphill at 5% grade → ~6:45 equivalent (strong effort)
- A 7:30/mi downhill at -3% grade → ~8:10 equivalent (coasting)

This turns hilly routes into truthful pictures. No competitor renders
this on a map. StrideIQ already computes `heat_adjustment_pct`. The
gradient adjustment is the same principle applied to elevation instead
of temperature.

Requires per-second elevation data from ActivityStream or session_detail.

#### Body State Narrative Segments (Phase 2 — after basic map ships)

`shape_extractor.py` already decomposes every run into phases: warmup,
work intervals, recovery, steady state, progression. Those segments
exist as structured data in `run_shape` JSONB.

Render the segments as labeled chapters on the map route:
- "Miles 1-2: warmup, HR normalizing"
- "Miles 3-5: optimal zone, efficiency at seasonal best"
- "Mile 6: fatigue accumulation detected"

Each segment gets a different color/label on the map trace. This is
what a coach watching your run would narrate — placed on geography.

### Also fix: Walking vs Hiking distinction
The `HikingDetail` component is used for both hiking and walking but hardcodes:
- "Hiking" label → should say "Walking" when `sport_type === 'walking'`
- Mountain icon → should use Footprints icon for walking (already used in ActivityCard)

### Also fix: Missing walking/hiking metrics
The API endpoint (`GET /v1/activities/{id}`) and the detail components should
include these fields that exist in the database but aren't passed through:

| Field | DB column | Where it goes |
|-------|-----------|---------------|
| Steps | `Activity.steps` | Walking/hiking detail — arguably the headline metric |
| Active calories | `Activity.active_kcal` | All cross-training detail pages |
| Cadence | `Activity.cadence_avg` | API should return this directly, not only derive from splits (splits don't exist for cross-training) |
| Avg/Max cadence | `Activity.avg_cadence` / `Activity.max_cadence` | Walking detail |

### Spec before building
1. Map library recommendation with rationale
2. API changes needed to return GPS track data (new endpoint or extend existing?)
3. Route clustering query — confirm the approach, propose how to return
   sibling count and sibling GPS tracks to the frontend
4. Ghost map rendering approach (opacity weighting, performance with 30+ traces)
5. Component placement per sport type (map as hero for walk/hike/cycle,
   secondary for runs where Run Shape Canvas is hero)
6. Walking vs hiking label/icon fix (trivial but confirm approach)
7. Which missing metrics to add to API response and where they render
8. For Phase 2 (effort-normalized + body state segments): brief design
   sketch only, not full spec — we'll spec these after the basic map ships

---

## Workstream 3: Home Page Cross-Training Acknowledgment

### What exists
- Home page shows `LastRunHero` (most recent run)
- Weekly chips show cross-training activities with sport icons
- Morning voice briefing can mention cross-training (Phase 4 already shipped)

### What's missing
When you do a walk, bike ride, or strength session, the home page acts
like nothing happened. You have to navigate to the activity list to see it.

### What to build
A compact secondary card below the LastRunHero that appears when a
non-run activity exists in the last 24 hours.

Something like:
```
┌──────────────────────────────────────────────┐
│ 🚶 Walking · 1.1 mi · 28 min · 92 bpm avg  │
│ Lauderdale County · 2:08 PM                  │
└──────────────────────────────────────────────┘
```

- Tappable → navigates to `/activities/{id}`
- Sport icon matches the activity list (Footprints, Dumbbell, Bike, etc.)
- Shows for ALL non-run sports
- Multiple non-run activities in 24h? Show the most recent one, with
  a "+2 more" indicator linking to the activity list
- Disappears naturally when no non-run activity in last 24h
- Does NOT replace or compete with the LastRunHero — it's a secondary acknowledgment

### API change
The `/v1/home` endpoint needs to include a `recent_cross_training` field:
```json
{
  "recent_cross_training": {
    "id": "uuid",
    "sport": "walking",
    "name": "Lauderdale County Walking",
    "distance_m": 1790,
    "duration_s": 1656,
    "avg_hr": 92,
    "steps": 2694,
    "start_time": "2026-04-05T19:08:03Z",
    "additional_count": 0
  }
}
```

### Spec before building
1. API response shape for `recent_cross_training`
2. Component design (placement, content, interaction)
3. What happens when there's no recent run but there IS a recent walk? Does
   the walk get promoted to the hero position, or does the hero stay empty/stale?

---

## Read order for this work

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` (especially Part 5 question 6: "Are the raw numbers visible?")
3. `docs/SITE_AUDIT_LIVING.md` — Section 0 deltas for cross-training phases 1-5
4. `apps/api/services/weather_backfill.py` — the weather service that needs wiring
5. `apps/api/tasks/garmin_webhook_tasks.py` — where Garmin activities are ingested
6. `apps/api/tasks/strava_tasks.py` — `post_sync_processing_task`
7. `apps/api/routers/activities.py` — `get_activity` endpoint (lines 309-540)
8. `apps/web/components/activities/cross-training/HikingDetail.tsx`
9. `apps/web/components/activities/cross-training/shared.tsx`
10. `apps/api/routers/home.py` — home endpoint

---

## Non-negotiable constraints

- Weather API failure must NEVER break activity ingestion (fire-and-forget)
- Never hide numbers (design philosophy)
- The home page is a running command center — cross-training is acknowledged, not promoted
- Maps must work on mobile (responsive)
- Suppression over hallucination applies to weather data too — if the API can't
  return data, show nothing rather than the wrong device sensor temperature
- Update `docs/SITE_AUDIT_LIVING.md` when each workstream ships
