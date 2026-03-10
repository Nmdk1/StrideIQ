# Builder Instructions: Worker Architecture + Strava Dedup Fix

**Date:** 2026-03-08
**From:** Top Advisor (Opus)
**Priority:** P0 dedup fix → P1 worker architecture → P2 prompt cleanup
**Context:** Session diagnosed home page slowness, duplicate activities, and missing Garmin attributions. Root causes are interconnected.

---

## Read Order

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. This document
3. Files referenced in each section below

---

## Issue 1 (P0): Strava Cross-Provider Dedup Bug

### Problem

When an athlete has multiple Garmin activities within a ±1 hour time window (e.g., a 1-mile warmup at 14:39 and a 10-mile race at 15:05), the Strava dedup logic in `strava_tasks.py` uses `.first()` to find a Garmin match. If `.first()` returns the warmup (1 mile) instead of the race (10 miles), the distance check fails (90% difference vs 5% threshold) and a duplicate Strava activity is created.

**Consequence:** The founder's 10-mile race exists twice — once as Garmin (`Bay St Louis Running`) and once as Strava (`Father son, state age records 10 mile!`). The Strava copy has no Garmin attribution badge. The home briefing prompt sees 3 activities totaling 21 miles instead of 2 activities totaling 11 miles.

### Root Cause

`apps/api/tasks/strava_tasks.py` lines 798-818. The Strava dedup uses `.first()`:

```python
garmin_match = (
    db.query(Activity)
    .filter(
        Activity.athlete_id == athlete.id,
        Activity.provider == 'garmin',
        Activity.start_time >= window_start,
        Activity.start_time <= window_end,
    )
    .first()  # BUG: returns only one candidate
)
```

The Garmin webhook code (`garmin_webhook_tasks.py` lines 329-350) does this correctly — it uses `.all()` and iterates all candidates with `match_activities()`.

### Fix

Replace the `.first()` + manual distance check with `.all()` + `match_activities()` loop, mirroring the Garmin webhook pattern:

```python
# --- Cross-provider dedup: skip if Garmin already owns this run ---
from datetime import timedelta as td
from services.activity_deduplication import match_activities

window_start = start_time - td(seconds=3600)
window_end = start_time + td(seconds=3600)
garmin_candidates = (
    db.query(Activity)
    .filter(
        Activity.athlete_id == athlete.id,
        Activity.provider == 'garmin',
        Activity.start_time >= window_start,
        Activity.start_time <= window_end,
    )
    .all()
)

strava_dict = {
    "start_time": start_time,
    "distance_m": a.get("distance"),
    "avg_hr": a.get("average_heartrate"),
}

skip_strava = False
for garmin_candidate in garmin_candidates:
    candidate_dict = {
        "start_time": garmin_candidate.start_time,
        "distance_m": float(garmin_candidate.distance_m) if garmin_candidate.distance_m else None,
        "avg_hr": garmin_candidate.avg_hr,
    }
    if match_activities(strava_dict, candidate_dict):
        logger.info(
            "Strava dedup: skipping %s — Garmin activity %s already exists",
            external_activity_id, garmin_candidate.id,
        )
        skip_strava = True
        break

if skip_strava:
    continue
```

### Data Cleanup

After deploying the fix, run a one-time cleanup to remove the existing duplicate:

```sql
-- Find duplicates: same athlete, same start_time, different providers
SELECT a1.id AS strava_id, a2.id AS garmin_id, a1.name AS strava_name, a2.name AS garmin_name,
       a1.start_time, a1.distance_m AS strava_dist, a2.distance_m AS garmin_dist
FROM activity a1
JOIN activity a2 ON a1.athlete_id = a2.athlete_id
    AND a1.provider = 'strava'
    AND a2.provider = 'garmin'
    AND ABS(EXTRACT(EPOCH FROM (a1.start_time - a2.start_time))) < 3600
    AND ABS(a1.distance_m - a2.distance_m) / GREATEST(a1.distance_m, a2.distance_m, 1) < 0.05;
```

For each duplicate pair: delete the Strava copy (the Garmin one has richer data and proper attribution). Preserve any `strava_activity_id` or athlete-authored name from the Strava copy by updating the Garmin row before deleting.

### Tests

1. Test: two Garmin activities in window (1mi warmup + 10mi race), Strava 10mi race → Strava skipped
2. Test: one Garmin activity in window, matching distance → Strava skipped (existing behavior, regression guard)
3. Test: one Garmin activity in window, non-matching distance → Strava created (existing behavior)
4. Test: no Garmin activities in window → Strava created (existing behavior)

---

## Issue 2 (P1): Worker Architecture — Sequential Processing Bottleneck

### Problem

The single worker container runs both the Celery Beat scheduler AND task execution in one process with `--pool=solo` (one task at a time). When beat fires `refresh_active_home_briefings` every 15 minutes, it enqueues one `generate_home_briefing` task per active athlete. Each task makes an LLM call (~14s for Opus). All tasks run sequentially.

**Current:** 5 athletes × 14s = 70 seconds. Every athlete waits behind everyone else.
**At 500 athletes:** 500 × 14s = 7,000 seconds = 116 minutes. Completely broken.
**While briefings run:** ALL other tasks (Strava sync, intelligence, runtoons) are blocked behind them.

### Current Config

`docker-compose.prod.yml` line 118:
```
command: celery -A tasks worker --loglevel=info -B --pool=solo
```

`-B` embeds the beat scheduler in the worker process. `--pool=solo` is required because `-B` doesn't support `prefork` reliably. This was fine when beat had nothing to schedule, but now it's scheduling LLM-heavy tasks for every active athlete.

### Fix: Three changes

#### 2A. Split beat into its own container

Add a new `beat` service in `docker-compose.prod.yml`:

```yaml
  beat:
    build:
      context: ./apps/api
    container_name: strideiq_beat
    restart: unless-stopped
    env_file:
      - .env
    environment:
      POSTGRES_HOST: postgres
      POSTGRES_PORT: 5432
      REDIS_URL: ${REDIS_URL:-redis://redis:6379/0}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: celery -A tasks beat --loglevel=info
    stop_signal: SIGTERM
    stop_grace_period: 10s
```

Update the `worker` service command to remove `-B` and use `gevent` pool:

```yaml
    command: celery -A tasks worker --loglevel=info --pool=gevent --concurrency=16
```

**Why gevent:** LLM calls are I/O-bound (waiting for HTTP response). Gevent handles hundreds of concurrent I/O operations with minimal memory. Prefork would spawn OS processes (heavy for I/O tasks).

**Dependency:** `gevent` must be in `requirements.txt`. Add `gevent>=24.2.1`.

#### 2B. Fingerprint-based skip

The data fingerprint is already computed inside `generate_home_briefing_task` (line 415) and stored in the cache entry. But the task NEVER checks it before calling the LLM. If the athlete's data hasn't changed, we're burning a 14-second LLM call for nothing.

In `apps/api/tasks/home_briefing_tasks.py`, after computing the fingerprint (line 415), add:

```python
fingerprint = _build_data_fingerprint(athlete_id, db)

# Skip if cached briefing already reflects current data
from services.home_briefing_cache import read_briefing_cache
from core.cache import get_redis_client
import json

cached_payload, cached_state = read_briefing_cache(athlete_id)
if cached_state == BriefingState.FRESH:
    r = get_redis_client()
    if r:
        raw = r.get(f"home_briefing:{athlete_id}")
        if raw:
            try:
                entry = json.loads(raw)
                if entry.get("data_fingerprint") == fingerprint:
                    logger.info(
                        "Home briefing fingerprint unchanged for %s — skipping LLM call",
                        athlete_id,
                    )
                    return {"status": "skipped", "reason": "fingerprint_unchanged"}
            except (json.JSONDecodeError, TypeError):
                pass
```

Import `BriefingState` at the top of the task function (it's already available from `services.home_briefing_cache`).

**Impact:** At 500 athletes, maybe 20 have data changes in a 15-minute window. The other 480 skip in milliseconds instead of making 14-second LLM calls.

#### 2C. Priority queue for live requests

Two Celery queues so live athletes aren't blocked by background pre-warming.

In `apps/api/tasks/__init__.py`, add queue routing:

```python
celery_app.conf.update(
    # ... existing config ...
    task_routes={
        'tasks.generate_home_briefing': {'queue': 'briefing'},
    },
    task_default_queue='default',
)
```

In `apps/api/tasks/home_briefing_tasks.py`, update `enqueue_briefing_refresh`:
- When called from `/v1/home` (live request): `generate_home_briefing_task.apply_async(args=[athlete_id], queue='briefing_high')`
- When called from beat (pre-warm): `generate_home_briefing_task.apply_async(args=[athlete_id], queue='briefing')`

Add a parameter to distinguish: `enqueue_briefing_refresh(athlete_id, priority="high"|"normal")`.

Update the worker command to consume both queues, high first:

```yaml
command: celery -A tasks worker --loglevel=info --pool=gevent --concurrency=16 -Q briefing_high,briefing,default
```

### Scale math with all three

500 athletes, ~20 with changed data per 15-minute window:
- Fingerprint skip: 480 skip instantly, 20 generate
- Gevent concurrency=16: 20 tasks at 14s each = ~2 batches = ~28 seconds total
- Live request: high-priority queue, served in <14 seconds regardless of queue depth

vs. current: 500 × 14s = 7,000 seconds sequential.

---

## Issue 3 (P2): Home Briefing Prompt — Same-Day Activity Aggregation

### Problem

The athlete brief (`services/coach_tools.py`, `build_athlete_brief()`) lists all activities individually in the "Recent Runs" section. When an athlete has a warmup, race, and cooldown as separate Garmin recordings on the same day, the LLM sees three activities and sums them (e.g., 1 + 10 + 10 = 21 miles). The athlete ran a 10-mile race, not 21 miles.

Note: Issue 1 (dedup fix) will eliminate the duplicate 10-mile entry. But the underlying problem remains — the warmup and race are still separate activities, and the LLM will say "11 miles yesterday" instead of "10-mile race + warmup."

### Suggested Approach

This is lower priority than Issues 1 and 2. Options to discuss with the founder:

**Option A:** Group same-day activities in the prompt with a daily summary line:
```
2026-03-07 (yesterday): 3 activities, 11.0mi total
  - Bay St Louis Running — 1.0mi @ 7:25/mi (warmup)
  - Father son, state age records 10 mile! — 10.0mi @ 6:58/mi (race)
```

**Option B:** Add a prompt instruction telling the LLM not to sum same-day activities when one is clearly a race.

**Option C:** No change — the dedup fix in Issue 1 eliminates the 21-mile case; the remaining 11-mile case is less misleading.

### Do not build this without founder discussion. It's product-level.

---

## Deployment Order

1. **Issue 1 (dedup fix):** Code change + tests + deploy + data cleanup script
2. **Issue 2A+2B (split beat + fingerprint skip):** Deploy together — these are safe and independent
3. **Issue 2C (priority queues):** Can follow separately
4. **Issue 3:** Discuss with founder first

## Verification

After each deploy:
- `docker logs strideiq_worker --tail=50` — confirm no 404 errors, confirm tasks succeeding
- `docker logs strideiq_beat --tail=20` — confirm beat scheduling tasks
- `docker exec strideiq_redis redis-cli KEYS 'home_briefing:*'` — confirm briefings being cached
- Check founder's home page loads in <5 seconds

## Files Referenced

| File | Issue |
|------|-------|
| `apps/api/tasks/strava_tasks.py` (lines 794-818) | Issue 1: `.first()` → `.all()` |
| `apps/api/services/activity_deduplication.py` | Issue 1: `match_activities()` reuse |
| `apps/api/tasks/garmin_webhook_tasks.py` (lines 324-355) | Issue 1: reference pattern |
| `docker-compose.prod.yml` (line 118) | Issue 2: worker/beat split |
| `apps/api/tasks/__init__.py` | Issue 2: queue routing |
| `apps/api/tasks/home_briefing_tasks.py` (lines 394-450) | Issue 2: fingerprint skip |
| `apps/api/services/home_briefing_cache.py` | Issue 2: `BriefingState`, cache read |
| `apps/api/services/coach_tools.py` (lines 3637-3656) | Issue 3: Recent Runs section |
| `requirements.txt` | Issue 2: add `gevent>=24.2.1` |

---

## What NOT to Change

- **Model strings:** `claude-opus-4-6` and `gemini-2.5-flash` are the working models. Do NOT change these without verifying the replacement model exists via a live API call first.
- **Coach chat page** (`apps/api/services/ai_coach.py`): stays on its current model. Do not touch.
- **Celerybeat schedule** (`celerybeat_schedule.py`): no changes needed. The schedule is correct.
- **Home briefing cache service** (`services/home_briefing_cache.py`): no changes needed. The cache logic is correct.
