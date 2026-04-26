# Garmin → Strava structural fallback — scoped design

**Date:** 2026-04-16
**Status:** discuss-before-build. No code. No migrations. Open questions listed at the bottom for the founder.

---

## 1. Problem statement

Garmin running activities are created from summary webhooks; per-second detail is push-driven via the activity-details webhook. If that detail payload never arrives, `stream_fetch_status` remains non-terminal until the stale-cleanup beat task runs. `cleanup_stale_garmin_pending_streams` fail-closes Garmin rows that still have no `activity_stream` row after `start_time` is older than **30 minutes**, setting `stream_fetch_status = 'unavailable'` and, when `stream_fetch_error` was empty, `stream_fetch_error` to `garmin_detail_missing_timeout_30m` (constant `GARMIN_STREAM_STALE_MINUTES = 30`):

```87:110:apps/api/tasks/garmin_health_monitor_task.py
UPDATE activity a
SET stream_fetch_status = 'unavailable',
    stream_fetch_error = COALESCE(
        NULLIF(a.stream_fetch_error, ''),
        :error_marker
    )
WHERE a.provider = 'garmin'
  AND a.stream_fetch_status IN ('pending', 'fetching', 'failed')
  AND a.start_time < (NOW() - (:stale_minutes || ' minutes')::interval)
  AND NOT EXISTS (
      SELECT 1 FROM activity_stream s
      WHERE s.activity_id = a.id
  )
...
"error_marker": f"garmin_detail_missing_timeout_{GARMIN_STREAM_STALE_MINUTES}m",
```

The 30-minute threshold is defined in `apps/api/tasks/garmin_health_monitor_task.py:21–22` and enforced by that `UPDATE` at `97–98`. Beat scheduled every 10 minutes (`apps/api/celerybeat_schedule.py:47–52`).

`stream_fetch_status = 'unavailable'` is also set in other paths (Strava stream fetch `apps/api/tasks/strava_tasks.py:300–309, 394–405`; manual unrecoverable cases; and Garmin detail webhook with no samples and no laps `apps/api/tasks/garmin_webhook_tasks.py:684–690`).

**Activity-model state after stall + cleanup:** row stays `provider='garmin'` with whatever summary fields the summary path wrote (`distance_m`, `duration_s`, `avg_hr`, Garmin-specific columns per `apps/api/models/activity.py`). **No** `activity_stream` row. `stream_fetch_status='unavailable'`, `stream_fetch_error` typically `garmin_detail_missing_timeout_30m`, `run_shape` / `shape_sentence` null.

**API + web behavior:**
- `GET /v1/activities/{id}/stream-analysis`: if `stream_fetch_status == 'unavailable'`, returns `{"status":"unavailable"}` (`apps/api/routers/stream_analysis.py:254–257`).
- `GET /v1/activities/{id}/streams` with no `activity_stream` row returns `status` from `activity.stream_fetch_status` (`apps/api/routers/v1.py:465–476`).
- Web: `useStreamAnalysis` treats lifecycle `unavailable` like manual/no GPS (`apps/web/components/activities/rsi/hooks/useStreamAnalysis.ts:11–17, 132–135`). `RunShapeCanvas` returns `null` for `unavailable` — the main RSI canvas is hidden (`RunShapeCanvas.tsx:1020–1031`). `GET /v1/activities/{id}` does not expose `stream_fetch_status`; without stream latlng, `gps_track` is typically null (`apps/api/routers/activities.py:553–592`).

**Net symptom:** page loads summary metadata but no chart, no map polyline, no stream-backed analysis — a broken activity experience even when the run exists in Strava.

---

## 2. Strava adapter surface that already exists

Canonical implementation: `apps/api/services/sync/strava_service.py` (shim: `apps/api/services/strava_service.py` re-exports it).

| Area | Location | Notes |
|------|----------|------|
| OAuth | `get_auth_url:148–163`, `exchange_code_for_token:166–184`, `STRAVA_SCOPES:132–145` | Authorization code flow. |
| Token refresh | `refresh_access_token:187–204`, `ensure_fresh_token(athlete, db):207–253` | Proactive refresh if expiry within 5 minutes; commits on success. |
| Rate limits | `acquire_strava_read_budget`, `get_strava_read_budget_remaining:411–481`, `_acquire_strava_detail_slot:52–129` | Global read budget + concurrent detail slot. |
| Activity details | `get_activity_details(athlete, activity_id, ...):484–585` | `GET /activities/{id}` with `include_all_efforts=true`. |
| Laps | `get_activity_laps(athlete, activity_id, ...):587–673` | `GET /activities/{id}/laps`. |
| Streams | `get_activity_streams(athlete, activity_id, ...):683–860` | Returns `StreamFetchResult` with `success` / `unavailable` / `failed` / `skipped_no_redis`. |
| Activity list | `poll_activities_page` / `poll_activities:277–408` | `GET /athlete/activities` with optional `after` / `before` epoch filters. |

**Garmin ↔ Strava matching (existing):**
- HR backfill (Garmin → Strava row): `apps/api/services/sync/hr_backfill.py` — same athlete, ±30 minutes start, ±10% distance (`backfill_hr_from_garmin:15–62`).
- Strava index / ingest dedup: `apps/api/services/sync/strava_index.py` — `_find_cross_provider_match` loads non-Strava activities within ±8 hours, then `match_activities` from `apps/api/services/sync/activity_deduplication.py` (window 28800 s, distance 5%, optional HR 5 bpm, `27–35`).
- Surgical Strava ingest by ID: `ingest_strava_activity_by_id` in `apps/api/services/sync/strava_ingest.py` uses `_find_cross_provider_match` before creating a duplicate Strava `Activity` (`81–91`).

**Representative signatures:**

```484:489:apps/api/services/sync/strava_service.py
def get_activity_details(
    athlete,
    activity_id: int,
    max_retries: int = 3,
    allow_rate_limit_sleep: bool = True,
) -> Optional[Dict]:
```

```683:689:apps/api/services/sync/strava_service.py
def get_activity_streams(
    athlete,
    activity_id: int,
    stream_types: Optional[List[str]] = None,
    max_retries: int = 3,
    allow_rate_limit_sleep: bool = True,
) -> StreamFetchResult:
```

---

## 3. Trigger condition

Launch the fallback **only when all** hold:

1. **Garmin activity in terminal "missing detail" state:** `provider='garmin'`, `stream_fetch_status='unavailable'`, `stream_fetch_error` = `garmin_detail_missing_timeout_30m` (exact match; widen later if needed), and no `activity_stream` row.
2. **Strava account usable:** `athlete.strava_access_token` / `strava_refresh_token` present; `ensure_fresh_token` succeeds (or reactive 401 handling succeeds).
3. **Usable time window for matching:** `activity.start_time` (+ `distance_m` / `avg_hr` when present) passable to `match_activities` against Strava API candidates inside a bounded epoch window.
4. **Idempotency:** `strava_fallback_status` is null or `failed` with retries remaining — not `succeeded`, not any terminal `skipped_*`.
5. **Recency:** `activity.start_time` within N days of `NOW()` (founder picks N; default candidate 14–30 days).
6. **Sport:** `sport='run'` for first cut.

---

## 4. Boundary

**Does**
- Resolve the Strava activity id for the same workout (list + `match_activities`, or reuse existing helpers).
- Call `get_activity_streams`, `get_activity_laps`, optionally `get_activity_details` to fill laps/summary gaps.
- Upsert `activity_stream` on the **existing Garmin** `activity_id` with `stream_data` / `channels_available` / `point_count`.
- Populate splits from Strava laps (mirror the interval-detector path used in Garmin detail processing, `garmin_webhook_tasks.py:755–763`).
- Compute `run_shape` / `shape_sentence` when streams exist (mirror Garmin success path, `724–752`).
- Set `stream_fetch_status='success'`; clear or overwrite `stream_fetch_error` with an audit marker.
- Rely on `cached_stream_analysis` cache miss to recompute (`apps/api/services/stream_analysis_cache.py:63–66`).

**Does not**
- Change `Activity.provider` (stays `garmin`), `external_activity_id` (Garmin summary id), or `garmin_activity_id`.
- Overwrite summary fields Garmin already populated (distance, duration, HR, device) — only fill nulls or explicit founder-listed gaps.
- Create a second Strava `Activity` row for the same workout (avoid breaking `uq_activity_provider_external_id`).
- Relabel source to Strava in the UI; optional neutral banner is product copy, not provider mutation.

**Provenance / audit**
- `ActivityStream.source` uses a dedicated value, e.g. `strava_fallback`, distinct from `garmin` / `strava` (`apps/api/models/activity.py:329–330`).
- New columns on `activity` (§5) record Strava activity id, attempt time, outcome.

---

## 5. Idempotency and safety

**Proposed columns on `activity`**

| Column | Type | Purpose |
|---|---|---|
| `strava_fallback_attempted_at` | `TIMESTAMPTZ` nullable | Last enqueue or worker start. |
| `strava_fallback_status` | `TEXT` nullable | `pending` / `succeeded` / `failed` / `skipped_no_strava` / `skipped_no_match` / `skipped_rate_limited` / … |
| `strava_fallback_strava_activity_id` | `BIGINT` nullable | Strava's activity id used for fetch. |
| `strava_fallback_error` | `TEXT` nullable | Truncated error / reason string. |

Optional: `strava_fallback_attempt_count` `INTEGER DEFAULT 0`.

**Concurrency guard**
- DB: `UPDATE activity SET strava_fallback_status='pending', strava_fallback_attempted_at=now() WHERE id=:id AND (strava_fallback_status IS NULL OR strava_fallback_status='failed') ... RETURNING id` — only one worker wins.
- Redis (optional): lock key `strava_fallback:{activity_id}` with short TTL for Strava API burst protection.

**Retry semantics**
- Transient (Strava 429, `StreamFetchResult.failed` network, post-refresh auth hiccup): retry with backoff; increment counter; max attempts, then `failed`.
- Terminal skip: no Strava tokens → `skipped_no_strava`, no retry until tokens appear (optional nightly sweep).
- Terminal no-match: `match_activities` returns nothing → `skipped_no_match`.
- Terminal Strava no-streams: `StreamFetchResult.outcome=='unavailable'` → `skipped_strava_no_streams` (or partial — founder question).

---

## 6. Trigger mechanism — recommendation

**Chosen: (b) Extend the existing Garmin timeout path.** When `cleanup_stale_garmin_pending_streams` performs the `UPDATE ... RETURNING`, enqueue a dedicated Celery task per returned `activity.id` (and `athlete_id`).

**Why this is simplest and structural**
- The only writer that sets `garmin_detail_missing_timeout_30m` today is this cleanup SQL (`garmin_health_monitor_task.py:87–110`). Hooking fallback there guarantees every fail-closed row gets a repair attempt without duplicating eligibility logic.
- **(a)** A new beat scanner duplicates predicates and can drift.
- **(c)** On-demand API ties repair to page loads — flaky for users who don't open the page; doesn't satisfy "structural, never again."

**Caveat:** cleanup runs every 10 minutes; pairing enqueue with the same transaction/commit keeps behavior aligned. A later safety-net beat is a small add-on, not required minimum.

---

## 7. Scope of DB migration (sketch, not code)

- Table: `activity` only (unless founder wants an immutable `strava_fallback_event` audit table — out of scope minimum).
- Columns: the four (or five) above; optional check on `strava_fallback_status` for strict values.
- Indexes: partial index on `(provider, strava_fallback_status, start_time)` for ops queries, optional.
- Data backfill: none mandatory. Hand-repaired rows (e.g. founder's run fixed manually today) can optionally be stamped with `succeeded` + known Strava id for analytics parity.
- Head revision: chain off the then-current Alembic head at implementation time (today: `n1_repair_001`).

---

## 8. Test design before build

**Unit (fallback worker)**
1. Happy path: mocked Strava → stream + laps stored, status `success`, `ActivityStream.source='strava_fallback'`, shape populated.
2. No Strava tokens → `skipped_no_strava`, no API calls.
3. `ensure_fresh_token` fails → failed terminal (or retry per policy).
4. Strava 401 after refresh → terminal `failed` / auth skip.
5. `poll_activities_page` returns no matching run → `skipped_no_match`.
6. Multiple Strava candidates → nearest `start_time` or first `match_activities` hit — deterministic choice asserted.
7. `get_activity_streams` returns `unavailable` (404) → terminal partial/skip per policy.
8. Partial streams (missing `time` channel) → `StreamFetchResult.failed` path, no silent store.
9. Already repaired (`status='succeeded'`) → no-op.
10. Do not overwrite: Garmin `distance_m` set, Strava summary differs → `distance_m` unchanged.

**Integration**
1. End-to-end with DB + Celery test harness: cleanup marks row → enqueue fires fallback (mock Strava) → success.
2. Idempotency: two workers / double enqueue → single successful patch.
3. Property: `provider` and `external_activity_id` unchanged after success.
4. API: after success, `GET /v1/activities/{id}/stream-analysis` returns full analysis (not `{status:"unavailable"}`).
5. Trigger does not run for Strava-native `unavailable` activities.

**Production smoke (post-deploy)**
1. Pick a test Garmin activity id (staging or founder account): verify fallback columns.
2. `curl` with bearer: `GET /v1/activities/{id}/stream-analysis` — expect full JSON.
3. `GET /v1/activities/{id}/streams` — `status:success`, `point_count>0`.
4. Tail worker logs for `strava_fallback` completion line.
5. Spot-check web: activity page shows RSI canvas.

---

## 9. Open questions for the founder

1. **Matching window:** reuse `match_activities` thresholds (8h / 5%) or a tighter window (±30 min) for fallback-only, to reduce wrong-run attachment?
2. If Strava returns **streams but no laps** (single-lap run), is the activity fully repaired or marked partial?
3. If Strava streams exist but **missing HR channel**, still mark success or degrade flag?
4. Retry `skipped_no_match` once Strava's index catches up (e.g. 2h later), or terminal after one pass?
5. Max age for fallback (`start_time` older than N days → do not call Strava)?
6. If athlete unlinked Strava after timeout but relinks later, nightly sweep retries old `failed` / `skipped_no_strava` rows?
7. Rate budget: fallback consumes Strava read budget — ok to defer via `stream_fetch_status='deferred'` + `deferred_until`, or dedicated small budget for repair?
8. Should `ActivityStream.source='strava_fallback'` drive a one-line UI ("Streams recovered from Strava") for trust?

---

## 10. Plain-language summary

Sometimes Garmin sends the "you finished a run" summary but the detailed file that powers the chart never shows up. After about half an hour, the system marks that run as having no usable stream data so the app doesn't spin forever — side effect is that your activity page looks empty or broken even though the run exists in Strava. This design adds an automatic repair: when that specific timeout happens, we look up the matching run in Strava, pull the streams and laps there, and attach them to your **existing Garmin activity** so the charts and analysis work. Your activity stays labeled as coming from Garmin; we only use Strava as a backup source for the missing pieces. We store a small audit trail so we know which runs were fixed this way. The repair is triggered at the exact place we currently give up on Garmin detail, so nothing falls through the cracks. A few product choices — how picky the matching is, what to do when Strava is incomplete — need your call before engineering starts. Tests are listed up front so behavior stays locked. After deploy, a short checklist confirms the fix on the live site.

---

**Files cited:** `apps/api/tasks/garmin_health_monitor_task.py`, `apps/api/celerybeat_schedule.py`, `apps/api/tasks/garmin_webhook_tasks.py`, `apps/api/tasks/strava_tasks.py`, `apps/api/routers/stream_analysis.py`, `apps/api/routers/v1.py`, `apps/api/routers/activities.py`, `apps/api/services/sync/strava_service.py`, `apps/api/services/sync/strava_index.py`, `apps/api/services/sync/activity_deduplication.py`, `apps/api/services/sync/hr_backfill.py`, `apps/api/services/sync/strava_ingest.py`, `apps/api/models/activity.py`, `apps/web/components/activities/rsi/hooks/useStreamAnalysis.ts`, `apps/web/components/activities/rsi/RunShapeCanvas.tsx`.
