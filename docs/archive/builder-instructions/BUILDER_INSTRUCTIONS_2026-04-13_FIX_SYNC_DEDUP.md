# Builder Instructions: Fix Activity Sync Dedup Regression

**Date:** April 13, 2026
**Priority:** P0 — trust-breaking bug visible to all users
**Symptom:** Calendar shows duplicate activities (every run appears twice for dual-sync users)
**Root cause:** Multiple code paths create activities without cross-provider dedup checks

---

## Problem

Despite existing cross-provider dedup logic in the main sync paths, duplicates keep reappearing after manual cleanup. The dedupe scripts fix the data, but the next sync run recreates the duplicates.

## Where the dedup works (don't touch these)

1. `tasks/garmin_webhook_tasks.py` → `_ingest_activity_item()` — checks `(athlete_id, provider, external_activity_id)` for same-provider idempotency, then runs `match_activities()` for cross-provider dedup. **This path is correct.**

2. `tasks/strava_tasks.py` → `sync_strava_activities_task` — checks existing Strava by `external_activity_id`, then loads Garmin candidates in ±1h window and runs `match_activities()`. **This path is correct.**

## Where the dedup is MISSING (fix these)

### Path A: `services/strava_index.py` → `upsert_strava_activity_summaries()`
- Creates Activity rows from Strava list API during index backfill
- Only checks `(provider, external_activity_id)` — **no cross-provider check**
- This means: if a Garmin activity exists and Strava index backfill runs, a duplicate Strava row is created
- **Fix:** Before inserting, query for existing activities within ±1h of `start_time` with similar distance. Use `match_activities()` from `activity_deduplication.py`. Skip insert if match found.

### Path B: `services/strava_ingest.py` → `ingest_strava_activity_by_id()`
- Surgical upsert by Strava activity ID
- Only checks `(provider, external_activity_id)` — **no cross-provider check**
- **Fix:** Same pattern as Path A — check cross-provider before insert.

### Path C: Garmin DI Connect import ID mismatch
- `services/provider_import/garmin_di_connect.py` uses `activityId` as `external_activity_id`
- Live Garmin webhook adapter uses `summaryId` as `external_activity_id`
- Same Garmin activity → different `external_activity_id` → unique constraint doesn't catch it
- **Fix:** In `import_garmin_di_connect_summaries()`, also check by `garmin_activity_id` column (which stores the `activityId` from both paths). If a row exists with matching `garmin_activity_id`, skip or update instead of insert.

## Implementation steps

1. Read `services/activity_deduplication.py` — understand `match_activities()` signature and `TIME_WINDOW_S` (8h).

2. Fix Path A (`strava_index.py`):
   - In `upsert_strava_activity_summaries()`, before each insert, load candidate activities for the same athlete within ±1h of the Strava activity's `start_time`.
   - Call `match_activities()` against each candidate.
   - If any match, log `"Strava index dedup: skipping {strava_id}, matches {existing_id}"` and skip insert.

3. Fix Path B (`strava_ingest.py`):
   - In `ingest_strava_activity_by_id()`, same pattern as Path A.

4. Fix Path C (`garmin_di_connect.py`):
   - Before insert, check if any existing Activity row has `garmin_activity_id` matching the current import's `activityId`. If yes, skip.
   - This is in addition to the existing `_matches_existing_time_distance()` check.

5. Run the existing `duplicate_scanner.scan_and_mark_duplicates()` once to clean up current duplicates.

6. Write a test that:
   - Creates a Garmin activity
   - Calls `upsert_strava_activity_summaries()` with the same run (same time, same distance, different provider)
   - Asserts no duplicate row was created

## Key files

| File | Function | Status |
|------|----------|--------|
| `services/activity_deduplication.py` | `match_activities()` | Read — use this |
| `services/strava_index.py` | `upsert_strava_activity_summaries()` | FIX — add cross-provider check |
| `services/strava_ingest.py` | `ingest_strava_activity_by_id()` | FIX — add cross-provider check |
| `services/provider_import/garmin_di_connect.py` | `import_garmin_di_connect_summaries()` | FIX — add garmin_activity_id check |
| `services/duplicate_scanner.py` | `scan_and_mark_duplicates()` | RUN — clean existing dupes |

## Evidence required

- [ ] `npx tsc --noEmit` clean (if any TS touched)
- [ ] `ruff check` and `black --check` clean
- [ ] New test proving cross-provider dedup in index path
- [ ] CI green
- [ ] Deploy API: `docker compose -f docker-compose.prod.yml up -d --build api`
- [ ] Run `scan_and_mark_duplicates()` once on prod to clean existing dupes
- [ ] Verify calendar no longer shows duplicates for founder account
