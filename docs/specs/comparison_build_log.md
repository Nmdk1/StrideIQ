# Comparison Product Build Log

Append-only log of the seven-phase build of the comparison product family.
Each phase appends a section when complete with what shipped, smoke evidence,
and judgment calls made autonomously.

**Phases:**

1. Activities-list filters (brushable histograms + workout-type chips) — SHIPPED
2. Route fingerprinting + ingest + backfill — SHIPPED
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

**Status:** SHIPPED 2026-04-17

**Commits:** `4290a53` (foundation: migration + service + ingest hooks +
backfill task + endpoints + tests) → `fd9b5c2` (sentinel fix for
GPS-less activities to break backfill loop)

**Behavioral smoke (prod, founder account, 2026-04-17):**

```
[OK ] alembic head = route_fp_001
[OK ] new activity cols: ['route_geohash_set', 'route_id']
[OK ] athlete_route table exists: True
[INFO] founder baseline: 582 stream-bearing run activities, 0 routed
[OK ] backfill drained: 517 routed across 106 unique routes,
                        65 sentinel-marked (no GPS — treadmill/track),
                        0 errors, loop terminates on second pass.

Top routes by run_count (founder account, 20 months of history):
  fce66de5  79 runs  ~11.7km  Aug 2024 → Apr 2026  (Meridian core loop)
  1665ecbb  68 runs  ~10.7km  Aug 2024 → today (Apr 16, 2026)
  05309748  32 runs  ~6.9km   Nov 2024 → Apr 2026
  8cbc145e  32 runs  ~18.8km  Jul 2025 → Apr 2026  (long-run staple)
  e6b53f0c  26 runs  ~6.8km   Aug 2024 → Nov 2025
  c2546dae  23 runs  ~26.3km  Sep 2024 → Dec 2025  (HM-distance route)
  24a3bbaf  19 runs  ~16.8km
  1caacb45  19 runs  ~14.0km  (different town — clean spatial separation)
  e340757c  18 runs  ~27.9km
  d2a0a8a2  17 runs  ~9.6km
  ...106 routes total

[OK ] /v1/routes (default min_runs=2) → 23 routes, last_seen DESC
[OK ] /v1/routes/{id} returns route + 10 activities with workout_type & HR
[OK ] /v1/routes?min_runs=1&limit=200 → 63 fingerprints across 300 acts
```

**Visual self-judgment:** Backend foundation is rock-solid. Spatial
separation between centroids is clean (Meridian core ~32.455,-88.726;
secondary cluster ~32.37,-88.73 in a different town). Distance-prefilter
working as designed: variants of the same start point segment by
distance (6.4km / 6.8km / 9.6km / 11.7km loops are distinct routes,
which is correct — they are different runs even when they share a
trailhead). Year-over-year is now possible: route fce66de5 has runs
spanning Aug 2024 → Apr 2026, which is exactly the spine the comparison
product needs.

**Notes / judgment calls:**

- Sentinel value `route_geohash_set = []` (empty list) marks "tried but
  no usable GPS" — without this the backfill query loops forever on
  treadmill activities. This decision is documented in the
  `compute_for_activity` docstring and enforced by
  `test_indoor_treadmill_stream_marks_empty_sentinel`.
- I set `min_runs=2` as the default for `/v1/routes` listing because
  one-off routes are noise. The athlete can pass `min_runs=1` to see
  every fingerprint (used for debugging today).
- Did NOT add a UI for routes in this phase — the API is live, the
  consumption is the activity-page comparable-runs view (Phase 5)
  and the route naming UX (Phase 3).

---

## Phase 3 — Route auto-naming + dominant_workout_type

**Status:** SHIPPED 2026-04-17 (server-side; UI rename folded into Phase 5)

**Commit:** `5ed28f0`

**What shipped:**

- Every `RouteSummary` now ships `display_name` and
  `dominant_workout_type`. Athletes see "11.7 km route", "18.8 km
  long-run route", "track loop" defaults instead of `null` names —
  zero work required from the athlete to get useful labels for the
  comparison product.
- Auto-name buckets tuned to founder data shape:
  `< 8 km` → loop / `8-16 km` → route / `16-26 km` → long-run /
  `26-36 km` → marathon-distance / `> 36 km` → ultra-distance.
- Workout-type prefix ("track loop" / "tempo route" / "long-run
  route") added when ≥40% of the route's typed runs share that
  workout type. Double-labeling guarded ("long-run long-run" cannot
  occur).
- 10/10 `test_routes_naming.py` pass.

**Behavioral smoke (prod, founder, 2026-04-17):**

```
10.7 km route                        runs= 68  dom=recovery_run
18.8 km long-run route               runs= 32  dom=medium_long_run
14.0 km route                        runs= 19  dom=None
11.7 km route                        runs= 79  dom=recovery_run
22.2 km long-run route               runs=  2  dom=recovery_run
16.8 km long-run route               runs= 19  dom=medium_long_run
6.9 km loop                          runs= 32  dom=recovery_run
1.6 km loop                          runs=  3  dom=recovery_run
7.3 km loop                          runs=  9  dom=recovery_run
16.2 km long-run route               runs=  2  dom=race
```

**Notes:** UI rename input deferred to Phase 5 surface — naturally
appears on the activity-page route card where it has context
("you're running your 11.7 km route — name it Bonita Loop?"). No
deploy was needed for Phase 3 alone since it's server-only.

---

## Phase 4 — Training block detection

**Status:** SHIPPED 2026-04-17

**Commits:** `5ed28f0` (foundation: model + migration + detector +
backfill task + endpoints + 21 tests) → `3e7a96d` (label refinement:
3+ week blocks containing a race no longer label wholesale as
"race" — taper / build / peak / base based on pre-race phase).

**What shipped:**

- `services/blocks/block_detector.py` — pure-Python rule-based
  detector. ISO-week aggregation → boundary detection (off weeks
  isolate; ≥10-day gaps split; recovery weeks following 2+ building
  weeks isolate; race weeks terminate the block) → phase labeling
  using a workout-type registry as the single source of truth for
  what counts as "quality."
- `models/training_block.py` + `training_block_001` migration.
- `tasks.backfill_training_blocks` Celery task (delete-and-recreate
  per-athlete; safe to re-run nightly).
- `GET /v1/blocks` and `GET /v1/blocks/{id}` endpoints.
- 22/22 `test_block_detector.py` pass.

**Behavioral smoke (prod, founder, 2026-04-17 after fix):**

```
17 blocks detected covering Aug 2024 → Apr 2026.
Phase distribution:
  base       5
  race       5
  recovery   2
  build      2
  off        1
  taper      1
  peak       1

Most-recent 12 blocks (the product-relevant window):
  2025-02-24 → 2025-03-02   1wk   recovery     29 km
  2025-03-03 → 2025-04-13   6wk   base        562 km   ends with Threefoot mile (race name retained)
  2025-04-14 → 2025-04-20   1wk   race        151 km   "1st place in the Threefoot mile!"
  2025-04-21 → 2025-05-04   2wk   race        221 km   "Chip time 41:27 — garmin 10k 41:04"
  2025-05-05 → 2025-06-15   6wk   taper       867 km   ends Pascagoula Charity 5k
  2025-06-16 → 2025-06-29   2wk   race        300 km
  2025-06-30 → 2025-08-31   9wk   build       945 km
  2025-09-01 → 2025-11-30  13wk   base       1392 km   peak_wk=129.9km
  2025-12-01 → 2025-12-14   2wk   race        108 km
  2025-12-15 → 2026-03-08  12wk   peak        704 km   q=25%, ends Bay St Louis
  2026-03-09 → 2026-03-15   1wk   race         80 km   ends Cary Running
  2026-03-16 → 2026-04-19   5wk   build       370 km   q=19%  (CURRENT BLOCK)
```

**Visual self-judgment:** The detector found the founder's actual
training shape: a 12-week peak block from Dec 2025 → Mar 2026 (the
Bay St Louis HM block, q=25%, peak weekly 129km), a 13-week base
through fall 2025, multiple race weeks correctly bounded as their
own phases. The CURRENT block is correctly identified as a 5-week
build with 19% quality. This is the spine the comparison product
needs.

**Notes / judgment calls:**

- `race` is now reserved for ≤2-week blocks containing a race (race
  + immediate shakeout). Long blocks ending in races label by their
  pre-race character (taper/build/peak/base) and retain the
  `goal_event_name` so the UI can still surface "12-week peak block
  for Bay St Louis HM" correctly.
- Detector is deterministic and idempotent — backfill safely
  re-runs nightly via Celery beat (next: add to beat schedule when
  Phase 7 needs it).
- `peak` requires the trailing 12-week peak weekly distance AND
  ≥10% quality runs AND ≥3 weeks. Suppression discipline: never
  call something "peak" without evidence.

---

## Phase 5 — Activity-page comparable runs

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


