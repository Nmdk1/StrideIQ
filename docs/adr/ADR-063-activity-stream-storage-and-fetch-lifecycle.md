# ADR-063: ActivityStream Storage, Fetch Lifecycle, and Rate-Limit Coordination

**Status:** Accepted
**Date:** 2026-02-14
**Owner:** StrideIQ

---

## Context

Run Shape Intelligence requires per-second resolution stream data from Strava
(and eventually Garmin). The system must ingest, store, and serve ~3,600 data
points per channel per activity across 8-9 channels. The founder has ~700
historical Strava activities requiring backfill.

Key constraints:
- Strava rate limits: 100 reads/15min (app-wide), 1,000 reads/day
- Multiple Celery workers can run concurrently
- Normal sync (webhook/manual) and backfill compete for the same rate budget
- Transient failures (429, timeout, malformed data) must not permanently block
  activities from retry
- Manual activities have no streams — detect cheaply, don't waste API calls

---

## Decision 1: Storage Model — Single Row, JSONB Blob

### Options Considered

| Option | Description | Rejected Because |
|--------|-------------|------------------|
| A. Column per channel | `time_data JSONB`, `heartrate_data JSONB`, etc. | Rigid schema — adding channels requires migrations. Can't query "what channels exist?" without checking each column. |
| B. One row per channel | Multiple rows per activity (`stream_type`, `data JSONB`) | Multi-row reads for chart rendering. Partial-ingestion complexity. More rows in queries. |
| **C. Single JSONB blob** | **One row per activity. `stream_data JSONB` containing all channels as dict of arrays.** | **Selected.** |

### Rationale

- Frontend always needs multiple channels simultaneously — one fetch, one row,
  one response.
- Schema flexibility: new channels are just new keys, no migration needed.
- At current scale (~1,000 activities, ~50KB each = ~50MB total), Postgres
  handles this trivially.
- `channels_available` array column enables cheap "what's available?" queries
  without parsing JSONB.
- Trade-off accepted: can't SQL-query into individual data points. Not needed —
  we read whole blobs for chart rendering and coach analysis.

### Schema: `ActivityStream`

```python
class ActivityStream(Base):
    __tablename__ = "activity_stream"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    activity_id = Column(UUID(as_uuid=True), ForeignKey("activity.id"), nullable=False)

    # Dict of channel_name → array of values
    # {"time": [0,1,2,...], "heartrate": [140,141,...], "altitude": [100.5,...]}
    stream_data = Column(JSONB, nullable=False)

    # Which channels are present (cheap filtering without parsing JSONB)
    # ["time", "distance", "heartrate", "altitude", "velocity_smooth", "grade_smooth"]
    channels_available = Column(JSONB, nullable=False, default=list)

    # Number of data points (length of time array)
    point_count = Column(Integer, nullable=False)

    # Provenance
    source = Column(Text, nullable=False, default="strava")
    fetched_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("activity_id", name="uq_activity_stream_activity_id"),
        Index("ix_activity_stream_activity_id", "activity_id"),
    )

    activity = relationship("Activity", back_populates="streams")
```

Reverse on Activity: `streams = relationship("ActivityStream", back_populates="activity", uselist=False)`

---

## Decision 2: Fetch Lifecycle State Machine

### Problem

A single timestamp marker can't distinguish "never tried" from "tried and
failed" from "rate-limited." Failed activities become permanently invisible
to retry queries.

### Solution: Six-State Lifecycle on Activity

Fields added to `Activity`:

| Field | Type | Purpose |
|-------|------|---------|
| `stream_fetch_status` | Text, default `'pending'`, CHECK constraint | Current lifecycle state |
| `stream_fetch_attempted_at` | DateTime(tz), nullable | When last attempt occurred |
| `stream_fetch_error` | Text, nullable | Error detail for failed/deferred |
| `stream_fetch_retry_count` | Integer, default 0 | Attempt counter for backoff |
| `stream_fetch_deferred_until` | DateTime(tz), nullable | Earliest retry time for deferred |

Check constraint:
```sql
stream_fetch_status IN ('pending', 'fetching', 'success', 'failed', 'deferred', 'unavailable')
```

### State Transitions (Only Allowed)

```
  ┌─────────┐    claim     ┌──────────┐    success    ┌─────────┐
  │ PENDING ├─────────────►│ FETCHING ├──────────────►│ SUCCESS │
  └─────────┘              └────┬─────┘               └─────────┘
                                │
                    ┌───────────┼────────────┐
                    ▼           ▼            ▼
              ┌─────────┐ ┌──────────┐ ┌─────────────┐
              │ FAILED  │ │ DEFERRED │ │ UNAVAILABLE │
              └────┬────┘ └────┬─────┘ └─────────────┘
                   │           │
            claim  │    claim  │  (after cooldown)
                   ▼           ▼
              ┌──────────────────┐
              │     FETCHING     │ (retry path)
              └──────────────────┘
```

| From | To | Trigger | Guard |
|------|----|---------|-------|
| `pending` | `fetching` | Worker claims for fetch | Atomic UPDATE |
| `failed` | `fetching` | Worker claims for retry | `retry_count < 3` in WHERE |
| `deferred` | `fetching` | Cooldown expired | `deferred_until < NOW()` in WHERE |
| `fetching` | `success` | Streams fetched and stored | ActivityStream row created |
| `fetching` | `failed` | Transient error | retry_count incremented |
| `fetching` | `deferred` | 429 rate limit | deferred_until set |
| `fetching` | `unavailable` | No streams exist | Terminal |

Terminal states: `success`, `unavailable`. Never re-attempted.

### Atomic Claim-Before-Fetch

Before calling Strava, a worker atomically claims the activity:

```sql
UPDATE activity
SET stream_fetch_status = 'fetching',
    stream_fetch_attempted_at = NOW()
WHERE id = :activity_id
  AND (
    stream_fetch_status = 'pending'
    OR (stream_fetch_status = 'failed' AND stream_fetch_retry_count < 3)
    OR (stream_fetch_status = 'deferred' AND stream_fetch_deferred_until < NOW())
  )
RETURNING id
```

All guards in the WHERE clause — race-safe, no TOCTOU gap. If `rowcount = 0`,
another worker already claimed it; skip.

### Stale Fetch Cleanup

Celery beat job (every 5 minutes): if a row has been `fetching` for >10 minutes,
the worker died. Reset to `failed`:

```sql
UPDATE activity
SET stream_fetch_status = 'failed',
    stream_fetch_error = 'fetching_timeout_cleanup',
    stream_fetch_retry_count = stream_fetch_retry_count + 1
WHERE stream_fetch_status = 'fetching'
  AND stream_fetch_attempted_at < NOW() - INTERVAL '10 minutes'
```

### Retry Policy

- `failed`: up to 3 attempts, exponential backoff (1min, 5min, 30min)
- `deferred`: retry after `deferred_until` (from Retry-After header, default 15min)
- After 3 failures: stays `failed` with `retry_count = 3`, requires manual reset

### Manual Reset

Admin endpoint: `POST /admin/activities/{id}/reset-stream-fetch` sets
`stream_fetch_status = 'pending'`, `retry_count = 0`, clears error.

---

## Decision 3: Source-of-Truth for `unavailable` Classification

`external_activity_id IS NULL` is the canonical test for "cannot fetch streams."

Rationale: this field is the Strava/Garmin activity ID required to call the
streams API. If null, there's nothing to fetch — regardless of `source` or
`provider` values.

Migration sets `stream_fetch_status = 'unavailable'` for all existing activities
where `external_activity_id IS NULL`.

---

## Decision 4: Shared Rate-Limit Coordination

### Global Limiter

Single function used by ALL Strava read paths (poll, details, laps, streams):

```python
def acquire_strava_read_budget(window_budget: int = 100) -> Optional[bool]:
    """
    Returns:
        True  — read allowed, budget decremented
        False — budget exhausted for current window
        None  — Redis unavailable, caller applies degraded-mode policy
    """
```

Redis key: `strava:rate:global:window:{window_id}`
Window ID: `floor(unix_timestamp / 900)` — aligns to Strava's 15-min boundaries.

Lua script: atomic check-and-increment with TTL.

Every HTTP request to Strava (including retries within a method's retry loop)
calls this function. A method that retries 3 times makes 3 budget acquisitions.

### Budget Allocation

- Total: 100 reads/15min (app-wide)
- No static split between sync and backfill — first-come, first-served
- Backfill yield threshold: when budget drops below 20 remaining in current
  window, backfill pauses until next window (live sync is higher priority)
- Within-window backfill pacing: `max(1.0, window_seconds_remaining / budget_remaining)`

### Relationship to Existing Concurrency Control

`_acquire_strava_detail_slot` controls concurrency (max N simultaneous
detail fetches). `acquire_strava_read_budget` controls rate (max N reads per
window). They are orthogonal — a request must pass both.

### Redis-Down Degraded-Mode Policy

| Path | Redis Up | Redis Down |
|------|----------|------------|
| Live sync — activity/splits | Budget-checked | Existing behavior (no rate guard) |
| Live sync — streams | Budget-checked | **Disabled.** Skip, leave `pending`. |
| Backfill — streams | Budget-checked + batch lock | **Disabled.** Task exits immediately. |

When Redis is down, no stream fetches happen. Activity and split ingestion
continue with existing degraded-mode behavior.

---

## Decision 5: Backfill Design

### Query

```sql
SELECT id, external_activity_id
FROM activity
WHERE stream_fetch_status IN ('pending', 'failed', 'deferred')
  AND external_activity_id IS NOT NULL
  AND provider = 'strava'
  AND (
    stream_fetch_status = 'pending'
    OR (stream_fetch_status = 'failed' AND stream_fetch_retry_count < 3)
    OR (stream_fetch_status = 'deferred' AND stream_fetch_deferred_until < NOW())
  )
ORDER BY start_time ASC
LIMIT :batch_size
FOR UPDATE SKIP LOCKED
```

### Partial Index

```sql
CREATE INDEX ix_activity_stream_backfill_eligible
ON activity (start_time ASC)
WHERE stream_fetch_status IN ('pending', 'failed', 'deferred')
  AND external_activity_id IS NOT NULL;
```

### Batch Locking

Per-batch Redis lock: `strava:stream_backfill:{athlete_id}` with 20min TTL.
Released before window-boundary sleeps, re-acquired after waking:

```
loop:
  acquire batch lock (20min TTL)
  if not acquired: exit
  select batch (FOR UPDATE SKIP LOCKED)
  for each activity:
    if budget exhausted:
      release lock
      sleep until next window
      continue to top of loop
    claim → fetch → transition
  release lock
  if more work: continue
  else: exit
```

### Expected Completion

Founder (~700 activities) at 50 reads/window: ~14 windows × 15min = ~3.5 hours.

---

## Decision 6: Observability (Required Acceptance Criteria)

| Metric | Query/Method |
|--------|--------------|
| Status distribution | `SELECT stream_fetch_status, COUNT(*) FROM activity GROUP BY 1` |
| Retry count distribution | `WHERE stream_fetch_status = 'failed' GROUP BY retry_count` |
| 429 rate (24h) | `WHERE stream_fetch_error LIKE '%429%' AND attempted_at > NOW() - 24h` |
| Window budget usage | Redis key for current window |
| Stuck failed count | `WHERE status = 'failed' AND retry_count >= 3` |
| Backfill progress | `{pending, success, failed, deferred, unavailable}` per athlete |

Structured logging on every stream fetch attempt:
```
activity_id, athlete_id, status, channels_fetched, point_count,
error, retry_count, duration_ms, rate_budget_remaining
```

---

## Consequences

### Positive
- Single-row JSONB: simple queries, one-read chart rendering, flexible schema
- Six-state lifecycle: no lost retries, full operational visibility
- Atomic claim: no duplicate Strava fetches, no wasted rate budget
- Global rate limiter: all read paths coordinated, no app-wide overshoot
- Partial index: backfill queries stay fast as table grows

### Negative (Accepted)
- JSONB blob opaque to SQL — can't query per-data-point. Not needed.
- Redis dependency for streams — graceful degradation to "disabled."
- 5 new columns on Activity — operational metadata, same pattern as existing.
- `FOR UPDATE SKIP LOCKED` may yield smaller batches under concurrency.

---

## API Endpoint Contract: `GET /v1/activities/{activity_id}/streams`

**Auth:** Bearer token; ownership enforced (`activity.athlete_id == current_user.id`).

| HTTP Status | Meaning |
|-------------|---------|
| 404 | Activity not found or not owned by current user |
| 200 | Activity exists — response always includes `status` field |

**200 response `status` values:**

| `status` | `stream_data` | Frontend hint |
|-----------|--------------|---------------|
| `"success"` | populated dict of channels | Render chart |
| `"pending"` | `null` | Show loading spinner |
| `"fetching"` | `null` | Show loading spinner |
| `"failed"` | `null` | Show retry hint |
| `"deferred"` | `null` | Show loading spinner (auto-retries) |
| `"unavailable"` | `null` | Hide stream panel (manual activity) |

**Rationale for 200-with-status instead of 404-when-absent:**
The activity *exists* — only the stream data may not be ready. 404 would be
misleading (the activity is found, just not yet fetched). The `status` field
gives the frontend enough context to render the right UI state without
additional round-trips.

---

## Migration Plan

Single migration:
1. Create `activity_stream` table
2. Add 5 `stream_fetch_*` columns to `activity`
3. Check constraint on `stream_fetch_status`
4. Partial index for backfill eligibility
5. Data migration: `SET unavailable WHERE external_activity_id IS NULL`
6. Add relationship on Activity model
