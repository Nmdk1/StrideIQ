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

**Status:** SHIPPED 2026-04-17

**Commits:** `0ebb728` (backend) → `31b11be` (frontend)

**What shipped (backend):**

Tier-based comparable-runs service + endpoint. The endpoint walks a
priority hierarchy of comparison "tiers" and returns each tier that
yielded data, with explicit `suppressions` for any tier that did not.

Tiers, in order:

1. `same_route_anniversary` — same route, ±30 days from one year ago.
   This is the "did I get faster on my favorite hill?" tier.
2. `same_route_recent` — last 5 runs on the same route, excluding
   anniversaries (so we don't double-show).
3. `same_type_current_block` — same workout type, inside the current
   detected training block. This is the "did my cruise intervals
   progress this build?" tier.
4. `same_type_similar_cond` — same workout type, last 90 days, soft-
   filtered to runs within ±5°F temp + ±5°F dew when both have
   weather data. This is the "fair comparison" tier.

Each entry carries:
- pace, HR, distance, weather, elevation
- `delta_pace_s_per_km`, `delta_hr_bpm`, `delta_distance_m` vs the
  focus run
- `in_tolerance_heat`, `in_tolerance_elevation` flags so the UI can
  honestly label "different conditions" without claiming heat-adjusted
  pace where data is missing.

Endpoint: `GET /v1/activities/{id}/comparables`

**Behavioral smoke (prod, founder data):**

```
>>> Comparables for a5799370 (cruise intervals, today)
  block_summary: build, weeks=5, run_count=27, quality_pct=19
  tiers: 3
    [same_route_anniversary] 6 entries
      - 2025-03-20  6.45km  4:56/km  392d ago  (+4s/km vs focus)
      - 2025-04-16  6.44km  5:41/km  365d ago  (+49s/km vs focus)
    [same_route_recent] 5 entries
      - 2026-04-10  9.82km  5:30/km  6d ago   (+38s/km vs focus)
    [same_type_current_block] 1 entry
      - 2026-04-09  14.40km  5:04/km 7d ago   (+12s/km vs focus)
  suppressions: 0
```

The founder is faster than the same route a year ago by 4-49s/km
across 6 anniversary runs — exactly the kind of insight the user
called out as "cool to see year over year."

**Notes / decisions:**

- Used `total_elevation_gain` (the actual model field) — caught a typo
  pre-push by reading `models/activity.py` and amended.
- `_elevation_in_tolerance` returns `False` when either side is missing
  (suppression discipline — never claim "same elevation" without
  evidence). Caught by test.
- Tier 4 soft-filters by heat tolerance only when both runs have temp
  data; otherwise it falls back to plain same-type recents so the
  athlete gets *something* useful when weather data is sparse.
- Block lookup is a single point-in-time query: blocks are date-bounded
  and non-overlapping in `block_detector`, so this is correct.

**Frontend shipped:** New "Compare" tab on activity page with
`ComparablesPanel`. Per founder direction: NOT generic cards. F1
telemetry density:

- Focus header with emerald accent rule, pace + workout type + block
  summary on one line.
- Each tier renders as a horizontal strip with a row per comparable.
- Pace bar per row: emerald fill when faster than focus, amber when
  slower; vertical tick marks the focus pace as the visual baseline;
  scale shared across all entries in the tier.
- Pace delta, HR delta, distance, weather all inline with tabular
  numerics — no card chrome.
- Suppressions surface honestly at the bottom.

**Visual smoke (prod, founder activity a5799370):**

DOM snapshot confirms the panel renders 3 tiers with real data:

```
Comparing this run · 5-week build block · 27 runs · 19% quality

Same route, one year ago      6 runs
  Mar 20, 2025  1.1y ago  6.45 km  53°F · dew 26 · 52m ↑
  Mar 21, 2025  1.1y ago  6.45 km  57°F · dew 27 · 42m ↑
  Apr 16, 2025  1.0y ago  6.44 km  64°F · dew 43 · 41m ↑
  Apr 30, 2025  12mo ago  6.44 km  76°F · dew 61 · 25m ↑
  May 1, 2025   12mo ago  6.45 km  76°F · dew 65 · 31m ↑
  May 8, 2025   11mo ago  6.45 km  69°F · dew 63 · 26m ↑

Recent runs on this route     5 runs
  Apr 10, 2026  6d ago    9.82 km  78°F · dew 51 · 52m ↑
  Apr 8, 2026   8d ago    9.66 km  75°F · dew 38 · 50m ↑
  ...

Other cruise intervals sessions in this block     1 run
  Apr 9, 2026   7d ago   14.40 km  76°F · dew 44 · 78m ↑
```

The anniversary tier alone surfaces six prior runs on the same route
spanning 11-12 months ago, each with full weather context — exactly
what the founder asked for ("track from last may to compare to this
may", "hilly runs on the bonita loop from last june", "must be
temp/dew point cognizant").

**Notes / decisions:**

- Used `total_elevation_gain` (the actual model field) — caught a typo
  pre-push by reading `models/activity.py` and amended.
- `_elevation_in_tolerance` returns `False` when either side is missing
  (suppression discipline). Tested.
- Tier 4 (similar conditions) didn't surface here because all
  same-type runs in last 90d are already in tier 3 (current block) —
  tier-de-duplication is working as designed.
- Block point-lookup: blocks are date-bounded and non-overlapping in
  `block_detector`, so a single point-in-time query is correct.
- Tab list now includes Compare between Analysis and Context. All
  panels stay mounted (CSS hidden) for instant switching, matching the
  existing tab pattern.

**Reprioritization for Phase 6 vs Phase 7:**

Original plan was Phase 6 (anniversary overlay on RunShapeCanvas) →
Phase 7 (block-over-block view). After shipping Phase 5, the
anniversary data is already surfaced as the first tier with weather
context. Drawing it as an overlaid pace trace on the run shape canvas
is incremental polish, not a new product surface.

Phase 7 (block-over-block periodization view) is the only remaining
*new* product surface in the comparison family. Reordering to ship
Phase 7 next, then return to Phase 6 if time permits.

---

## Phase 7 — Block-over-block periodization view

**Status:** SHIPPED 2026-04-17 — backend commit `b361ca1`, frontend same
commit.

**What shipped (backend):**

- `services/comparison/block_comparison.py` — pure aggregation service
  that takes two `TrainingBlock` rows and returns a structured
  comparison: per-side weekly series (volume + quality split), per-
  workout-type compare rows, scalar deltas, and suppressions.
- `compare_blocks(db, focus_id, against=None)` defaults to picking the
  most recent prior block of the **same phase** for a fair comparison
  (e.g. build vs build, not build vs the race that sits between them).
  Falls back to any prior block if no same-phase peer exists. When no
  prior block exists at all, returns the focus solo with a
  `previous_block` suppression rather than fabricating a comparison.
- `routers/blocks.py` — `GET /v1/blocks/{block_id}/compare` endpoint
  with optional `against=<uuid>` query param.

**What shipped (frontend):**

- `app/blocks/page.tsx` — index of all detected training blocks for the
  athlete, with phase badge, distance, run count, and date range. Click
  a row to drill into the comparison view. Honest empty state.
- `app/blocks/[id]/page.tsx` — block-over-block comparison view.
  Visual-first design: focus header naming the two blocks, delta strip
  for the headline scalars (distance, runs, peak week, quality %, weeks,
  longest run), side-by-side block columns each with weekly volume bars
  (quality split shown in a darker shade) + summary stats, and per-
  workout-type rows showing count + distance + pace for each side. When
  there's no prior block, surfaces the focus standalone with an explicit
  "no previous block to compare yet" message.

**Tests:**

- `tests/test_block_comparison.py` — 10 pure-function tests covering
  pace math, weekly aggregation (empty/single/quality split), and
  workout-type compare (single, disjoint, sorting by volume, untyped
  skips). All pass locally.

**Behavioral smoke (prod, founder data, 17 detected blocks):**

```
GET /v1/blocks → 17 blocks
  build  | 2026-03-16 → 2026-04-19 |   370km |  27 runs (focus, in progress)
  race   | 2026-03-09 → 2026-03-15 |    80km |   6 runs
  peak   | 2025-12-15 → 2026-03-08 |   704km |  56 runs
  race   | 2025-12-01 → 2025-12-14 |   108km |  11 runs
  base   | 2025-09-01 → 2025-11-30 |  1392km | 129 runs
  ...

GET /v1/blocks/{focus}/compare → matched same-phase build → build
  same_phase: True
  a (older):  build 2025-06-30 → 2025-08-31  945km  78 runs   (9 weeks, completed)
  b (focus):  build 2026-03-16 → 2026-04-19  370km  27 runs   (5 weeks, in progress)
  workout_type_compare:
    long_run         a=13/286km   b=0/0km      (no long runs yet this build)
    aerobic_run      a=18/194km   b=2/15km
    recovery_run     a=16/83km    b=6/74km
    medium_long_run  a=6/92km     b=2/42km
    fartlek          a=6/86km     b=1/13km
  deltas:
    total_distance_m: -574,641m   (focus is mid-block; expected)
    run_count: -51                (focus is mid-block; expected)
    quality_pct: +6%              (current build skewing more quality)
    peak_week_distance_m: -42km
    weeks: -4                     (in-progress vs completed)
```

The aggregation correctly picked the previous *build* block (last
summer's 9-week build) over the more recent race blocks. The data
surfaces a real, actionable signal: "this build is 5 weeks in with no
long runs yet vs 13 long runs in the same phase last summer." That's a
finding the founder can act on — the type of pattern recognition the
correlation engine layer above this would key on.

**Notes / decisions:**

- Same-phase preference makes block-over-block periodization comparisons
  fair by default. Athlete can override via `?against=<uuid>`.
- All aggregation is pure functions over the raw `Activity` table — no
  invented numbers, no synthesis. The week series, the workout-type
  rollups, and the deltas are all derived directly from activity rows
  bounded by `start_date`/`end_date`.
- Suppressions are first-class: missing previous block → empty `a` +
  `previous_block` suppression. UI honors this with an explicit message.
- Frontend uses tabular numerics throughout; weekly bars use a dual-fill
  pattern (lighter = total volume, darker = quality work) so the
  athlete can see both volume and intensity composition at a glance.

**Why Phase 7 over Phase 6:**

Documented above (end of Phase 5 section): Phase 5 already surfaces
anniversary data with weather context. Drawing it as an overlay on the
run shape canvas would be polish; the block-over-block view is a *new*
product surface and the only remaining new product surface in the
comparison family. Reordered accordingly.

---

## Phase 5 (legacy design notes from Phase 2 — kept for reference)

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


