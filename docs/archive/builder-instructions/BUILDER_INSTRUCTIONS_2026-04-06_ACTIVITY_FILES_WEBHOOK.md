# Builder Instructions: Garmin Activity Files Webhook (FIT File Pipeline)

**Priority:** High — unlocks exercise set data for all strength training activities
**Status:** SHIPPED (Apr 6, 2026). Webhook endpoint live, FIT parser deployed, dead code removed. CI green. Awaiting first live Activity Files notification from Garmin (next strength workout by any connected athlete).

## Context

The strength training display pipeline is 90% built but has never worked. The entire backend (parser, model, taxonomy, classifier, DB writer) and frontend (StrengthDetail.tsx with exercise grouping, muscle labels, weight/rep display) are complete. The pipeline was never wired to actual data because:

1. The Garmin developer portal had "Activity Files" pointed at `https://example.com/path` (placeholder)
2. The existing `fetch_garmin_exercise_sets_task` calls a REST endpoint (`wellness-api/rest/activities/{id}/exerciseSets`) that **does not exist** on the Garmin Wellness API

The founder updated the portal. Garmin will now send Activity File PING notifications to our server. We need a handler to receive them, download the FIT files, parse exercise data, and feed it into the existing pipeline.

## What Already Exists (DO NOT rebuild)

| Component | File | Status |
|-----------|------|--------|
| `StrengthExerciseSet` model | `models.py:567` | Working |
| `parse_exercise_sets()` | `services/strength_parser.py` | Working |
| `write_exercise_sets()` | `services/strength_parser.py` | Working |
| `process_strength_activity()` | `services/strength_parser.py` | Working |
| `strength_taxonomy.py` | Movement pattern + 1RM | Working |
| Exercise sets on API response | `routers/activities.py:522-544` | Working |
| `StrengthDetail.tsx` | Frontend display | Working |
| 14 parser tests | `tests/test_strength_parser.py` | Passing |

## Workstream 1: Activity Files Webhook Handler

### 1A. New webhook endpoint

Add to `routers/garmin_webhooks.py`:

```
POST /v1/garmin/webhook/activity-files
```

This is a **PING-mode** webhook. Garmin sends a JSON notification containing callback URLs — NOT inline activity data. Expected payload format:

```json
{
  "activityFiles": [
    {
      "userId": "garmin-user-id",
      "userAccessToken": "...",
      "summaryId": "...",
      "fileType": "FIT",
      "callbackURL": "https://apis.garmin.com/wellness-api/rest/activityFile?id=12345&token=DOWNLOAD_TOKEN"
    }
  ]
}
```

**IMPORTANT:** The exact payload format is not fully documented. The handler MUST:
1. Log the **full raw payload** on first receipt (we've never seen a live one)
2. Try `data_key="activityFiles"` first
3. Accept and log any unrecognized structure (return 200 to prevent Garmin retry storms)
4. Extract `callbackURL` from each record
5. Resolve athlete from `userId` using `_resolve_athlete()` (existing helper)
6. Dispatch `process_garmin_activity_file_task.delay(athlete_id, record)` for each record

### 1B. New Celery task: `process_garmin_activity_file_task`

Add to `tasks/garmin_webhook_tasks.py`:

```python
@celery_app.task(
    name="process_garmin_activity_file_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    rate_limit="5/m",
)
def process_garmin_activity_file_task(self, athlete_id: str, record: dict):
    """Download FIT file from Garmin callback URL and extract exercise sets."""
```

Steps:
1. Extract `callbackURL` from `record`
2. Download the FIT file from the callback URL (binary GET, no auth header needed — token is in the URL)
3. Parse the FIT file using `fitparse` (see below)
4. Match to existing Activity via `garmin_activity_id` or `summaryId` from the record
5. If the activity exists AND `sport == "strength"`: feed parsed exercise data into `process_strength_activity()` (existing function)
6. If the activity exists but is NOT strength: store the FIT file metadata but skip exercise parsing (FIT files come for ALL activities, not just strength)
7. If the activity doesn't exist yet (timing race): retry with countdown=30

### 1C. FIT File Parsing

Add `fitparse` to `requirements.txt`:
```
fitparse>=0.6.0,<1.0.0
```

Create `services/fit_parser.py`:

```python
def extract_exercise_sets_from_fit(fit_bytes: bytes) -> dict:
    """Parse a FIT file and extract exercise set data.
    
    Returns data in the same format as the existing strength_parser expects:
    {
        "exerciseSets": [
            {
                "setType": "ACTIVE" | "REST",
                "exerciseCategory": "DEADLIFT",
                "exerciseName": "BARBELL_DEADLIFT",
                "repetitionCount": 5,
                "weight": 133.8,
                "duration": 45.0,
                "setOrder": 1,
            }
        ]
    }
    """
```

The FIT file contains `set` message types with fields:
- `set_type` → maps to `setType` ("ACTIVE" / "REST")
- `category` → maps to `exerciseCategory`
- `exercise_name` → maps to `exerciseName`
- `repetitions` → maps to `repetitionCount`
- `weight` → maps to `weight` (may be in grams — divide by 1000 for kg)
- `duration` → maps to `duration` (may be in milliseconds — divide by 1000)
- `set_order` → maps to `setOrder`

**CRITICAL:** The FIT SDK field names may differ from the JSON API field names. Log the raw FIT `set` message fields on first parse to verify exact naming. The `fitparse` library provides `.get_values()` on each message to see all available fields.

Use `fitparse.FitFile(io.BytesIO(fit_bytes))` to parse from bytes in memory — do NOT write to disk.

### 1D. Remove dead code

The existing `fetch_garmin_exercise_sets_task` (line 1372-1510 in `garmin_webhook_tasks.py`) calls a non-existent REST endpoint. Either:
- **Remove it entirely** (preferred — it has never worked)
- Or keep it but mark it deprecated and remove the dispatch from `process_garmin_activity_task` (line 626-646)

Also remove `_GARMIN_ACTIVITY_API_BASE` and `_EXERCISE_SETS_TIMEOUT_S` constants (line 1368-1369) if removing the task.

## Workstream 2: Backfill Existing Strength Activities

After the webhook handler is working:

1. Create an admin endpoint or script to backfill exercise sets for existing strength activities
2. For each strength activity with `garmin_activity_id` and no `exercise_sets`:
   - Use the athlete's OAuth token to request a backfill of `activityFiles` from Garmin
   - OR: Use `https://apis.garmin.com/wellness-api/rest/backfill/activityFiles` with appropriate parameters (check Garmin docs for backfill format)
3. Process incoming FIT files through the same pipeline

This can be a follow-up — the webhook handler should work for NEW activities first.

## Workstream 3: Manually Updated Activities (Optional, low priority)

The Garmin portal also has "ACTIVITY - Manually Updated Activities" pointing at `example.com/path`. This fires when an athlete renames an activity, changes its type, or edits it in Garmin Connect.

If time permits, update the URL to `https://strideiq.run/v1/garmin/webhook/activity-updates` and add a simple handler that:
1. Receives the notification
2. Matches to existing Activity via `garmin_activity_id`
3. Updates `name`, `sport`, `garmin_activity_type` from the new data

This prevents stale activity names when athletes rename workouts after the fact.

## Verification

After deploying:

1. Have the founder or Brian do a strength workout on their Garmin watch
2. Check worker logs for:
   - `Garmin webhook envelope` log from the activity-files handler (verifies Garmin is sending)
   - `process_garmin_activity_file_task` execution logs
   - `Exercise sets processed` log from the parser
3. Check the activity detail page — `StrengthDetail.tsx` should render exercise groups, reps, weights
4. Compare to what Garmin Connect shows for the same activity — verify data completeness

## Files to Modify

| File | Change |
|------|--------|
| `routers/garmin_webhooks.py` | Add `webhook_activity_files` handler |
| `tasks/garmin_webhook_tasks.py` | Add `process_garmin_activity_file_task`, remove dead `fetch_garmin_exercise_sets_task` |
| `services/fit_parser.py` | **New file** — FIT binary parser |
| `requirements.txt` | Add `fitparse>=0.6.0,<1.0.0` |
| `Dockerfile` | No change needed (fitparse is pure Python) |

## Constraints

- Always return 200 from the webhook handler — non-200 triggers Garmin's 7-day exponential backoff
- Log the full raw payload on first receipt — we've never seen a live Activity Files notification
- FIT files can be large (5-20MB for long activities) — parse in memory, don't write to disk
- FIT files come for ALL activities, not just strength — the handler should gracefully skip non-strength activities after parsing
- The download token in the callback URL is temporary — download promptly (within minutes, not hours)
