# Builder Note — Garmin Activities Missing Splits

**Date:** February 25, 2026
**Priority:** High (athlete-facing data gap — splits missing for all Garmin-only activities)
**Status:** Ready to implement
**Owner:** Builder agent
**Scope:** Backend only — two files, one new adapter function, one integration point

---

## Read order (mandatory)

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `apps/api/services/garmin_adapter.py` — existing adapter functions (reference pattern)
3. `apps/api/tasks/garmin_webhook_tasks.py` — `_ingest_activity_detail_item()` (integration point)
4. `apps/api/tasks/strava_tasks.py` — working split creation path (reference implementation)
5. `apps/api/models.py` — `ActivitySplit` model (field names)
6. This document

---

## Root Cause

The Garmin webhook pipeline never implemented split creation. It is **not a regression** — it is a gap that was hidden because older activities had splits inherited from Strava.

### Why it was masked

Older Garmin activities that show splits were originally ingested via Strava first. Strava's pipeline creates `ActivitySplit` rows. When the Garmin webhook later pushed the same activity, the dedup logic updated the `Activity` row but the Strava-created splits stayed attached.

Now that the founder is Garmin-only (new activities are Garmin-sourced), new activities go through the Garmin pipeline exclusively — which has no split creation code. Splits are empty for all new Garmin-only activities.

---

## Current state vs required state

| Step | Status |
|---|---|
| Garmin webhook receives activity-details | Working |
| Adapter extracts GPS/HR/cadence samples | Working |
| Task creates `ActivityStream` | Working |
| Adapter extracts laps from payload | **Missing** — `laps` key never read |
| Task creates `ActivitySplit` rows | **Missing** — no code exists |

---

## Step 0 — Capture a live payload before implementing (mandatory)

The Garmin portal docs only show `startTimeInSeconds` per lap. The actual payload may be richer. Add a one-line log to `_ingest_activity_detail_item()` before building:

```python
logger.info(f"Garmin laps payload: {raw_item.get('laps')}")
```

Capture one real laps array from the worker logs:

```bash
docker logs strideiq_worker --tail=500 | grep -i "laps payload"
```

**Remove this log before the final commit.** Use the captured payload to confirm field names and structure before mapping.

---

## The fix

### File 1: `apps/api/services/garmin_adapter.py`

Add `adapt_activity_detail_laps(raw_detail: dict, samples: list) -> list[dict]`:

- Extract the `laps` array from `raw_detail` (key: `"laps"`)
- For each lap, use `startTimeInSeconds` as the boundary
- Compute per-lap metrics by filtering `samples` within the lap's time window:
  - `distance` (metres) — delta from samples
  - `elapsed_time` / `moving_time` (seconds) — from lap boundaries or samples
  - `average_heartrate` — mean of HR samples within lap window
  - `max_heartrate` — max of HR samples within lap window
  - `average_cadence` — mean of cadence samples within lap window
- Return a list of dicts, one per lap, in the same shape as `ActivitySplit` fields

**Source contract:** all raw Garmin field names must be contained to `garmin_adapter.py`. The task must receive only internal field names.

### File 2: `apps/api/tasks/garmin_webhook_tasks.py`

In `_ingest_activity_detail_item()`, after `activity.stream_fetch_status = "success"`:

1. Call `adapt_activity_detail_laps(raw_item, samples)` — where `samples` is the list already extracted for `ActivityStream`
2. If laps returned:
   a. Delete existing `ActivitySplit` rows for this `activity.id` (idempotency)
   b. Create one `ActivitySplit` row per lap

---

## Reference: working Strava implementation

Study `apps/api/tasks/strava_tasks.py` — it calls `get_activity_laps()` and creates `ActivitySplit` rows with:

```python
ActivitySplit(
    activity_id=activity.id,
    split_number=...,
    distance=...,
    elapsed_time=...,
    moving_time=...,
    average_heartrate=...,
    max_heartrate=...,
    average_cadence=...,
    gap_seconds_per_mile=...,
)
```

The Garmin implementation must produce the same shape. `gap_seconds_per_mile` can be `None` if not available in the payload.

---

## Tests required

1. `test_adapt_activity_detail_laps_returns_correct_split_count` — correct number of laps extracted
2. `test_adapt_activity_detail_laps_computes_avg_hr_from_samples` — HR averaged correctly within lap window
3. `test_adapt_activity_detail_laps_empty_when_no_laps_key` — no laps key → empty list, no error
4. `test_adapt_activity_detail_laps_empty_when_laps_is_empty_array` — empty laps array → empty list
5. `test_ingest_activity_detail_creates_splits` — integration: `ActivitySplit` rows created for activity with laps
6. `test_ingest_activity_detail_idempotent_splits` — re-ingestion deletes old splits and creates new ones (no duplicates)
7. `test_ingest_activity_detail_no_splits_when_no_laps` — no laps in payload → no `ActivitySplit` rows, no error
8. `test_garmin_field_names_not_in_task_module` — source contract: no raw Garmin field names in `garmin_webhook_tasks.py`

---

## Also open: Garmin backfill (separate issue, do not conflate)

The backfill service (`apps/api/services/garmin_backfill.py`) returns 400/429 because:
- It uses 90-day ranges for activity endpoints (Garmin allows max 30 days)
- It has no retry logic for rate limits

This is a separate fix. Even if fixed, backfill activities would not get splits without this split-creation fix being deployed first. Fix splits first, then backfill.

---

## Do not touch

- Frontend code
- `ActivityStream` creation (already working)
- Deduplication logic
- Strava pipeline
- Health/wellness ingestion (D6)

---

## Commit guidance

Suggested commit message:

`feat(garmin): create ActivitySplit rows from webhook activity detail laps`

Land on `main`. Push to `origin/main`. Include raw test output in handoff.
