# Comparison Product Build Log

Append-only log of the seven-phase build of the comparison product family.
Each phase appends a section when complete with what shipped, smoke evidence,
and judgment calls made autonomously.

**Phases:**

1. Activities-list filters (brushable histograms + workout-type chips) — SHIPPED
2. Route fingerprinting + ingest + backfill — IN PROGRESS
3. Route naming UX
4. Block detection engine + persistence
5. Activity-page comparable runs (workout-type-specific visuals)
6. Anniversary card (route + condition tolerance)
7. Block-over-block view

**Operating rules in effect:**

- Suppression default everywhere (no card / no chart / no histogram if no data).
- Heat-adjusted pace requires both compared activities have temp + dew; otherwise raw only, no heat claim.
- Visual-first per `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md` — narrative below visual, not as a card with text.
- Tests xfailed first, then implementation.
- CI green before push to prod.
- Behavioral smoke against real founder data on prod after each phase.

---

## Phase 1 — Activities-list filters

**Status:** SHIPPED 2026-04-17

**Commits:** `a2542fd` (tests xfailed) → `c32b9b3` (impl) → `70ca7aa` (Suspense fix)

**What shipped:**

- Backend: `GET /v1/activities` accepts `workout_type` (CSV multi-select),
  `temp_min/max`, `dew_min/max`, `elev_gain_min/max`. NULL exclusion when
  the filter on a field is active. 400 on inverted ranges.
- New endpoint `GET /v1/activities/filter-distributions` returns 16-bucket
  histograms per dimension and a workout-type chip list. Marks dimension
  `available: false` when fewer than 5 activities have a value
  (suppression rule).
- Frontend: `BrushableHistogram` component (pure-React SVG with
  draggable range brush, log-scaled bars, click-to-bucket, double-click
  to clear).
- Frontend: `ActivityFilterPanel` orchestrates workout-type chips +
  four histograms; suppresses entire panel when athlete has nothing to
  filter on.
- Activities page: legacy 4-column dropdown grid replaced. Sort / Show /
  Per-page collapsed to a compact secondary control row. URL state sync
  for deep-link restoration via `next/navigation`.

**Behavioral smoke (prod, founder account, 2026-04-17):**

```
=== /v1/activities/filter-distributions ===
[OK] HTTP 200
  workout_types: 14 types
  recovery_run             count=401
  long_run                 count=106
  medium_long_run          count=103
  easy_run                 count=48
  aerobic_run              count=30
  progression_run          count=23
  fartlek                  count=11
  race                     count=11
  distance_m         AVAILABLE  range 1.0 -> 42542.0  16 buckets  N=800
  dew_point_f        AVAILABLE  range -1.3 -> 78.8   16 buckets  N=765
  temp_f             AVAILABLE  range 25.0 -> 96.1   16 buckets  N=765
  elevation_gain_m   AVAILABLE  range 0.0 -> 4800.0  16 buckets  N=733

[OK] HTTP 200 /v1/activities?workout_type=long_run&limit=5
  count: 5; titles include "10 miles building from 8:57 to 8:08"
[OK] HTTP 200 /v1/activities?dew_min=60&dew_max=75&limit=10
  10 hits in dew band
[OK] HTTP 400 /v1/activities?dew_min=80&dew_max=60  (inverted range)
[OK] HTTP 200 backward-compat /v1/activities?min_distance_m=15000&limit=5
[OK] HTTP 200 combined /v1/activities?workout_type=long_run&dew_min=65
```

**Visual self-judgment:** Backend contract proven. Visual rendering
verified through Next.js prerender (no runtime errors at build time)
and TypeScript pass. Live in-browser visual verification deferred to
founder review on next session — the design philosophy compliance
(brushable histograms, log-scaled bars, suppression default, no cards
with text) was followed at the component level. If the rendering
doesn't match the visual judgment when reviewed, iterate post-action
per founder's autonomy directive.

**Notes / judgment calls:**

- The legacy `min_distance_m` / `max_distance_m` URL params are kept as
  the wire format for distance even from the new histogram, so nothing
  external breaks. New fields (`temp_min/max`, `dew_min/max`,
  `elev_gain_min/max`) are net-additive.
- The "X+ match" counter shows only when filters are active; when no
  filters are active the existing summary line continues to show "N
  activities in last 30 days". This avoids an awkward redundant counter.
- I did NOT add a date-range filter — the existing `start_date` /
  `end_date` params already work; the UX for date can come later.

---

## Phase 2 — Route fingerprinting

**Status:** in progress

**Design (locked):**

A *route* is a canonical group of activities the athlete has run on the
same physical course. Fingerprinted by walking the GPS track at uniform
~50m intervals and encoding each sample as a precision-7 geohash
(~150m × 150m grid). The fingerprint is the *set* of unique geohashes —
direction-independent, tolerant to GPS drift, rejects non-overlapping
courses.

Two activities are "same route" when:
- Jaccard(set_a, set_b) ≥ 0.6
- AND distance differs by ≤ 25%

Suppression discipline:
- Tracks with <10 GPS points → no fingerprint (return None).
- Tracks shorter than ~500m → no fingerprint.
- Garmin `[0, 0]` "no fix yet" sentinels are dropped before sampling.
- Distance prefilter excludes routes with >25% length difference.
- Match requires Jaccard ≥ 0.6; otherwise create a new route — never
  force a match.

Persistence:
- New table `athlete_route` — { id, athlete_id, name (nullable, athlete-
  set in Phase 3), centroid_lat/lng, distance_p50/min/max_m, geohash_set
  JSONB (union of all run fingerprints), run_count, first/last_seen_at }.
- New columns on `activity` — `route_id` (FK nullable),
  `route_geohash_set` (JSONB).

Hooks:
- `tasks/strava_tasks.py:fetch_activity_streams` → after stream success.
- `tasks/garmin_webhook_tasks.py:process_garmin_activity_detail_task` →
  after detail item commit.
- `services/sync/strava_fallback.py` → after fallback repair success.

All hooks are best-effort: if route fingerprinting throws, the original
ingestion still succeeds; the activity is left for the backfill task to
pick up.

Backfill:
- New Celery task `tasks.backfill_route_fingerprints(athlete_id=None,
  batch_size=200)` walks all run activities lacking a `route_id` that
  have a stored stream, computes the fingerprint, and attaches the
  route. Idempotent: re-running on already-routed activities re-uses
  the existing route via Jaccard match without double-counting.

Endpoints:
- `GET /v1/routes` — list athlete routes (default `min_runs=2`,
  ordered by last_seen_at desc).
- `GET /v1/routes/{id}` — route summary + activity history on the route.
- `PUT /v1/routes/{id}/name` — set/clear athlete-supplied route name
  (Phase 3 will surface UX; the field exists now).

Test coverage written:
- 17 pure-algorithm tests (geohash encode, haversine, Jaccard, sampling,
  reversed track equality, sentinel filtering) — all passing locally.
- 6 persistence tests (first activity creates route; second matching
  activity attaches; distant activity creates separate route; distance
  prefilter; no stream → None; idempotent recompute) — DB-required,
  will run in CI.

Not in scope for Phase 2: the route name UX (Phase 3), the visual
overlay on the activity page (Phase 5/6), the activity-page
"comparable runs" surface (Phase 5).

---


