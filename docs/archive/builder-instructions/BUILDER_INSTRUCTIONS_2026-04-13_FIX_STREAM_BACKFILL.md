# Builder Instructions: Fix Stream Backfill to Actually Complete

**Date:** April 13, 2026
**Priority:** P0 — historical activities show empty pages, athletes can't review past races
**Symptom:** Activities from months/years ago have no stream data, RunShapeCanvas shows "Analyzing your run..." forever
**Root cause:** Backfill task exists but is never scheduled, and when run manually it competes with live sync for a shared API budget that's too small

---

## Problem

Athletes cannot use StrideIQ to review historical activities (e.g., last year's race on the same course). They have to go to Strava. This is trust-breaking for the core use case of race prep and historical comparison.

## Current state

### Strava streams

- `backfill_strava_streams_task` exists in `tasks/strava_tasks.py` — processes eligible activities in batches
- **It is NOT scheduled in celerybeat.** No code calls `.delay()` or `apply_async()` on it anywhere in the repo.
- It shares the global Strava read budget: **100 reads per 15-minute window** (Redis key `strava:rate:global:window:{window_id}`)
- It yields when remaining budget < 20 to favor live sync
- State is per-activity on `stream_fetch_status`, `stream_fetch_retry_count`, `stream_fetch_deferred_until` — so it can resume where it left off
- `cleanup_stale_stream_fetches_task` runs every 5 min (resets stuck `fetching` rows)

### Garmin streams

- Garmin streams arrive via webhook push after backfill requests
- `request_deep_garmin_backfill` walks time windows backward but has **no persisted cursor** — restarts the full walk every run
- Garmin backfill requests BOTH activity endpoints AND health endpoints (`sleeps`, `hrv`, `stressDetails`, `dailies`, `userMetrics`) — they compete for the same Garmin rate limits
- After 429, the endpoint's window loop stops for that run

## Fix — Strava

### Step 1: Schedule `backfill_strava_streams_task` in celerybeat

File: `celerybeat_schedule.py`

Add an entry that runs the backfill task periodically. Suggested: every 30 minutes. The task already has internal budget management (yields when < 20 remaining) and Redis locking (20 min TTL), so concurrent runs are safe.

```python
'backfill-strava-streams': {
    'task': 'tasks.backfill_strava_streams',
    'schedule': crontab(minute='*/30'),
    'kwargs': {'batch_size': 10},
},
```

### Step 2: Increase the batch effectiveness

In `backfill_strava_streams_task`:
- Currently processes `batch_size` activities per invocation
- With 100 reads/15min budget and live sync taking some, realistic throughput is ~50-60 stream fetches per 15 min during quiet periods
- The task should loop through multiple batches within a single invocation until budget runs low, not just do one batch and exit
- Check: does the task already loop? If not, add a loop that continues fetching until `get_strava_read_budget_remaining() < 20` or all eligible activities are processed

### Step 3: Prioritize by recency and importance

In the query that selects eligible activities:
- Currently `ORDER BY start_time ASC` — starts from oldest
- Change to `ORDER BY start_time DESC` — start from most recent, which athletes are most likely to view
- Consider: flag race activities (from `is_race` column) as higher priority

## Fix — Garmin

### Step 4: Add checkpoint to deep backfill

File: `services/garmin_backfill.py`

In `request_deep_garmin_backfill`:
- After each successful window, persist the cursor (latest completed window start) to a DB record or Redis key per athlete
- On next invocation, read the cursor and skip already-completed windows
- This prevents the full walk from restarting every time

### Step 5: Prioritize activity streams over health data

In `request_deep_garmin_backfill` (or a new dedicated task):
- Currently requests activities AND health data in the same loop
- Option A: Split into two tasks — `backfill_garmin_activities_task` (activities + activityDetails only) and `backfill_garmin_health_task` (sleeps, hrv, stress, etc.). Schedule activities first/more frequently.
- Option B: In the existing task, process ALL activity windows first, THEN health windows. Don't interleave.

### Step 6: Schedule Garmin deep backfill for new users

- `request_deep_garmin_backfill_task` should be enqueued automatically for new Garmin connections (it may already be — verify in `routers/garmin.py` OAuth callback)
- For existing users who never got a complete backfill, add an admin endpoint or one-time migration to re-enqueue

## Verification

### For the founder account specifically:

1. After deploying, check how many activities have `stream_fetch_status != 'success'`:
```sql
SELECT stream_fetch_status, COUNT(*) 
FROM activities 
WHERE athlete_id = (SELECT id FROM athletes WHERE email = 'mbshaf@gmail.com')
GROUP BY stream_fetch_status;
```

2. Monitor progress over 24 hours:
```sql
SELECT stream_fetch_status, COUNT(*) 
FROM activities 
WHERE athlete_id = (SELECT id FROM athletes WHERE email = 'mbshaf@gmail.com')
  AND stream_fetch_status = 'success'
  AND updated_at > NOW() - INTERVAL '24 hours';
```

3. Spot-check a historical race activity to confirm RunShapeCanvas renders.

## Key files

| File | What to do |
|------|------------|
| `celerybeat_schedule.py` | ADD `backfill-strava-streams` schedule |
| `tasks/strava_tasks.py` | REVIEW `backfill_strava_streams_task` — ensure it loops, change sort order to DESC |
| `services/garmin_backfill.py` | ADD checkpoint persistence, SPLIT activity vs health |
| `services/strava_service.py` | READ — understand `acquire_strava_read_budget()` |
| `docs/adr/ADR-063-activity-stream-storage-and-fetch-lifecycle.md` | READ — design context |

## Evidence required

- [ ] `backfill_strava_streams_task` appears in celerybeat schedule
- [ ] Backfill loops until budget exhausted (not single-batch exit)
- [ ] Sort order changed to `start_time DESC`
- [ ] Garmin deep backfill has checkpoint (doesn't restart from scratch)
- [ ] `ruff check` and `black --check` clean
- [ ] CI green
- [ ] Deploy all: `docker compose -f docker-compose.prod.yml up -d --build`
- [ ] After 24h: show SQL count of newly backfilled streams
