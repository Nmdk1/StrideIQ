# Builder Note — Strava Cross-Provider Dedup Fix

**Date:** February 23, 2026  
**Priority:** SEV-1 (data integrity — causes wrong coach advice)  
**Status:** Ready to implement  
**Branch:** `feature/garmin-oauth` → merge to `main`

---

## Read order

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `apps/api/services/activity_deduplication.py` (dedup thresholds)
3. `apps/api/tasks/garmin_webhook_tasks.py` lines 323-354 (working Garmin-side dedup)
4. `apps/api/tasks/strava_tasks.py` lines 508-516, 786-811 (broken Strava-side dedup)
5. This document

---

## Problem

When an athlete has both Garmin and Strava connected, the same physical run creates **two Activity rows** — one from each provider. This doubles the distance for that run in all analytics.

### Impact observed in production (Feb 22-23, 2026)

- Founder's weekly mileage inflated from **63 miles to 88 miles** (40% over-report)
- Coach briefing said: "88 miles last week... that's a massive ramp... 251 miles vs 125"
- Coach told the athlete to taper based on fabricated overtraining
- "What's Not Working" card said mileage swung 0→88 mi — completely false
- Injury risk detector said "no flags" despite the athlete having a real recent gap and injury
- **Two duplicate pairs found in production data (Feb 21, Feb 22)**
- Duplicates manually deleted from production database to restore correct analytics

### Root cause

The Strava sync path checks for existing activities using **provider-specific matching only**:

```
apps/api/tasks/strava_tasks.py lines 509-516:

existing = (
    db.query(Activity)
    .filter(
        Activity.provider == provider,        # "strava"
        Activity.external_activity_id == external_activity_id,
    )
    .first()
)
```

When Garmin has already ingested the same run with `provider='garmin'`, this query returns nothing because it filters on `provider='strava'`. Strava then creates a brand new Activity row at line 793.

### Why Garmin doesn't have this problem

The Garmin ingest path (`garmin_webhook_tasks.py` lines 323-354) performs **cross-provider time-window deduplication**:

```
apps/api/tasks/garmin_webhook_tasks.py lines 323-336:

# Time-window dedup: find any existing activity within ±1 hour
window_start = start_time - timedelta(seconds=TIME_WINDOW_S)
window_end = start_time + timedelta(seconds=TIME_WINDOW_S)
candidates = (
    db.query(Activity)
    .filter(
        Activity.athlete_id == athlete.id,
        Activity.start_time >= window_start,
        Activity.start_time <= window_end,
    )
    .all()
)
```

This query does NOT filter by provider, so it finds Strava activities and deduplicates correctly. Strava's sync path needs the same logic.

---

## Fix

**File:** `apps/api/tasks/strava_tasks.py`

**Location:** After the `continue` on line 784 (end of existing-activity update block), before the "Create new activity" comment on line 786.

Add a cross-provider dedup check before creating any new Strava activity:

```python
            # --- Cross-provider dedup: skip if Garmin already owns this run ---
            from datetime import timedelta as td
            window_start = start_time - td(seconds=3600)
            window_end = start_time + td(seconds=3600)
            garmin_match = (
                db.query(Activity)
                .filter(
                    Activity.athlete_id == athlete.id,
                    Activity.provider == 'garmin',
                    Activity.start_time >= window_start,
                    Activity.start_time <= window_end,
                )
                .first()
            )
            if garmin_match:
                dist_strava = a.get("distance") or 0
                dist_garmin = garmin_match.distance_m or 0
                if dist_garmin > 0 and dist_strava > 0:
                    diff_pct = abs(dist_strava - dist_garmin) / max(dist_strava, dist_garmin)
                    if diff_pct <= 0.05:
                        logger.info(
                            "Strava dedup: skipping %s — Garmin activity %s already exists (dist diff %.1f%%)",
                            external_activity_id, garmin_match.id, diff_pct * 100
                        )
                        continue
```

### Thresholds

These match the existing thresholds in `activity_deduplication.py`:
- **Time window:** ±3600 seconds (1 hour) — `TIME_WINDOW_S`
- **Distance tolerance:** 5% — `DISTANCE_TOLERANCE`

### Why inline instead of reusing `match_activities()`

`match_activities()` in `activity_deduplication.py` operates on dicts with internal field names (`distance_m`, `start_time`, `avg_hr`). The Strava sync loop has the raw Strava API dict (using `distance`, not `distance_m`). Converting to internal fields just for one check adds complexity and a risk of field-name drift. A simple inline check using the same numeric thresholds is clearer.

---

## What NOT to touch

- Do not modify `activity_deduplication.py`
- Do not modify `garmin_webhook_tasks.py` (Garmin dedup already works)
- Do not change provider precedence rules (Garmin wins when both exist)
- Do not change data models or add migrations
- Do not touch any frontend code
- Scoped commits only — never `git add -A`

---

## Testing

### 1. Existing tests must pass

```bash
cd apps/api && python -m pytest tests/ -x -q
```

### 2. Manual verification scenario

After deploying the fix, trigger a Strava sync for the founder account and verify:

```bash
# On droplet — check for duplicates after next Strava sync
docker exec strideiq_api python -c "
from core.database import SessionLocal
from models import Activity
from datetime import datetime
from collections import Counter
db = SessionLocal()
acts = db.query(Activity).filter(
    Activity.athlete_id=='4368ec7f-c30d-45ff-a6ee-58db7716be24',
    Activity.start_time >= datetime(2026,2,20)
).order_by(Activity.start_time).all()
times = [str(a.start_time) for a in acts]
dupes = {t: c for t, c in Counter(times).items() if c > 1}
if dupes:
    print(f'DUPLICATES FOUND: {dupes}')
else:
    print(f'CLEAN: {len(acts)} activities, no duplicates')
for a in acts:
    print(f'{a.start_time} | {a.provider:8s} | {a.distance_m or 0:>7} m | {a.name or \"\"}')
db.close()
"
```

Expected: no duplicate timestamps, all recent activities show `garmin` provider.

### 3. New test (optional but recommended)

Add a test in `apps/api/tests/` that:
1. Creates a Garmin activity at a specific time
2. Simulates a Strava sync with a matching activity (same time, similar distance)
3. Asserts only one Activity row exists after sync

---

## Evidence of production fix (Feb 23, 2026)

Two duplicate rows were manually deleted from production:

```
Deleted: 2026-02-21 17:09:49+00:00 | strava | 32193m | Loving the grind | id=9c46474c-047a-4b79-bfa7-fb56a3330afa
Deleted: 2026-02-22 19:01:16+00:00 | strava | 8054m  | Afternoon Run    | id=59a602e8-1421-4cad-970d-253b949af2e2
```

Dependent rows cleaned from: `best_effort`, `activity_split`, `activity_stream`.

Post-cleanup verification confirmed correct totals:
```
Feb 16-22 total: 101850m = 63.3 mi (was 88.3 mi with duplicates)
```

---

## Deployment

1. Commit the fix to `feature/garmin-oauth`
2. Merge to `main`
3. Deploy: `cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build`
4. Worker will restart and pick up the new dedup logic
5. Next Strava sync will exercise the fix — verify with the query above
