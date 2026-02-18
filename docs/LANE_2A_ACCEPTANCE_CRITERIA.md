# Lane 2A: Home Briefing Off Request Path — Acceptance Criteria + Test Plan

**ADR:** `docs/adr/ADR-065-home-briefing-off-request-path.md`  
**Status:** Awaiting founder sign-off  
**Date:** 2026-02-18

---

## Acceptance Criteria

### AC-1: `/v1/home` never blocks on LLM or Celery task
- The home endpoint returns a complete deterministic payload without waiting for any LLM call or Celery task result.
- `coach_briefing` is served from Redis cache or returned as `null`.
- No `asyncio.to_thread`, no `asyncio.wait_for`, no `task.get()`, no `await` on task result in the request path.
- When cache is stale or missing, the endpoint calls `task.delay()` (fire-and-forget) and returns immediately. It does not wait for the task to complete.
- **SLO:** `/v1/home` p95 < 2s when provider is healthy. `/v1/home` p95 < 2s when provider is down/slow.

### AC-2: Stale-while-revalidate semantics
- Fresh cache (< 15 min): return payload, `briefing_state: "fresh"`.
- Stale cache (15-60 min): return payload + enqueue refresh, `briefing_state: "stale"`.
- Expired cache (> 60 min): return `null` + enqueue refresh, `briefing_state: "missing"`. No stale served beyond 60 min even if Redis entry still present.
- No cache: return `null` + enqueue refresh, `briefing_state: "missing"`.
- Task in-flight: return whatever cache exists, `briefing_state: "refreshing"`.

### AC-3: Response includes `briefing_state`
- New field on HomeResponse: `briefing_state` enum (`fresh | stale | missing | refreshing`).
- Always present and enum-valid, even when `coach_briefing` is `null`.

### AC-4: Celery task `generate_home_briefing`
- Idempotent by athlete ID + data fingerprint.
- Deduplicates in-flight refreshes via Redis lock (`home_briefing_lock:{athlete_id}`, 120s TTL).
- Uses Gemini 2.5 Flash as default model.
- Opus path feature-flagged via `home_briefing_use_opus` (off by default).
- Provider timeout: 12s on LLM SDK call.
- Task runtime timeout: 15s hard limit.
- Retry: up to 3 attempts with exponential backoff (10s, 30s, 60s).
- On success: writes to Redis with `payload`, `generated_at`, `expires_at`, `source_model`, `version`, `data_fingerprint`.
- Task creates its own `SessionLocal()`. Never receives a request-scoped session.

### AC-5: Stampede protection
- Enqueue cooldown: 60s per athlete. Multiple triggers within the window are coalesced.
- In-flight dedupe: Redis lock prevents concurrent tasks for same athlete.
- Circuit breaker: after 3 consecutive provider failures for an athlete, stop requeueing for 15 min. Serve stale (if within 60 min) or null.

### AC-6: Regeneration triggers
- Check-in saved
- New activity ingested (Strava/Garmin sync)
- Training plan created, updated, or deleted
- Race goal update
- Daily intelligence write completion
- Manual refresh: `POST /v1/admin/home-briefing/refresh/{athlete_id}`
- Celery beat: every 15 min for athletes active in last 24 hours

### AC-7: Admin refresh endpoint security
- `POST /v1/admin/home-briefing/refresh/{athlete_id}` requires admin or founder role.
- Returns 403 for non-admin athletes.
- Returns 202 Accepted on success.
- Writes audit log entry recording who triggered the refresh and for which athlete.

### AC-8: Redis cache contract
- Key: `home_briefing:{athlete_id}`
- Value: JSON with `payload`, `generated_at`, `expires_at`, `source_model`, `version`, `data_fingerprint`
- TTL: 3600s (Redis-enforced hard expiry)

### AC-9: No regression in deterministic home payload
- All existing fields (today, yesterday, week, hero_narrative, coach_noticed, race_countdown, checkin, strava_status, last_run, ingestion_state) continue to work identically.
- Only behavioral change: `coach_briefing` comes from cache instead of inline LLM.

### AC-10: Extensible for Lane 2B
- Cache/job contract is generic enough that `hero_narrative`, `coach_noticed`, and other heavy computes can be added as additional cached fields without architectural changes.

### AC-11: Observability
- Structured logging for:
  - Cache hit state per request (`fresh/stale/missing/refreshing`)
  - Task duration
  - Task failures and retries (count, reason)
  - Enqueue rate and dedupe/cooldown skips
  - Provider-level latency and error rates
- Required to prove Lane 2A achieved its goal.

### AC-12: Feature-flagged rollout
- Feature flag `lane_2a_cache_briefing` controls whether home reads from cache (new) or calls LLM inline (old).
- Flag off = old behavior preserved.
- Flag on = new cache-first behavior.
- Old code path preserved until 1 week of stable operation.

---

## Test Plan

### Category 1: Unit Tests

| # | Test | What it proves |
|---|------|---------------|
| 1 | `test_cache_fresh_returns_payload` | Cached entry < 15 min returns payload + state `fresh` |
| 2 | `test_cache_stale_returns_payload_and_enqueues` | Cached entry 15-60 min returns payload + state `stale` + task enqueued |
| 3 | `test_cache_expired_returns_null_and_enqueues` | Cached entry > 60 min returns `null` + state `missing` + task enqueued |
| 4 | `test_cache_miss_returns_null_and_enqueues` | No cache entry returns `null` + state `missing` + task enqueued |
| 5 | `test_no_stale_served_beyond_60_min` | Entry at 61 min treated as missing, not stale |
| 6 | `test_cache_write_shape` | Task writes correct JSON structure with all required fields |
| 7 | `test_data_fingerprint_changes_on_new_activity` | Fingerprint differs when activity data changes |
| 8 | `test_data_fingerprint_stable_when_no_change` | Fingerprint identical when data unchanged |
| 9 | `test_dedupe_prevents_concurrent_refreshes` | Second enqueue for same athlete while lock held is a no-op |
| 10 | `test_cooldown_coalesces_rapid_triggers` | Multiple triggers within 60s produce only one task |
| 11 | `test_circuit_breaker_stops_requeue_after_3_failures` | After 3 failures, no new tasks for 15 min |
| 12 | `test_celery_task_retries_on_provider_failure` | Task retries up to 3 times with backoff |
| 13 | `test_celery_task_idempotent` | Same athlete + fingerprint = same result, no duplicate work |
| 14 | `test_task_runtime_timeout` | Task killed after 15s hard limit |
| 15 | `test_task_uses_own_db_session` | Task creates SessionLocal, never uses a passed-in session |
| 16 | `test_briefing_state_always_valid_enum` | `briefing_state` is always one of `fresh/stale/missing/refreshing` |

### Category 2: Integration Tests

| # | Test | What it proves |
|---|------|---------------|
| 17 | `test_home_endpoint_no_llm_call` | `GET /v1/home` completes without any LLM SDK call (mock LLM, assert never called) |
| 18 | `test_home_endpoint_returns_briefing_state_field` | Response JSON includes `briefing_state` with valid enum value |
| 19 | `test_home_endpoint_deterministic_payload_intact` | All non-briefing fields populated correctly |
| 20 | `test_home_endpoint_with_cached_briefing` | Pre-seed Redis → `coach_briefing` returned, `briefing_state: "fresh"` |
| 21 | `test_home_endpoint_without_cache` | Empty Redis → `coach_briefing: null`, `briefing_state: "missing"` |
| 22 | `test_home_p95_unaffected_when_llm_down` | Mock provider timeout/error → `/v1/home` still returns fast with deterministic payload |
| 22b | `test_home_does_not_await_task_result` | Mock slow Celery task (10s sleep) + cache miss → `/v1/home` returns in < 500ms with `null` briefing. Proves no `await` on task. |
| 23 | `test_trigger_checkin_enqueues_refresh` | Saving check-in fires Celery task |
| 24 | `test_trigger_activity_ingest_enqueues_refresh` | New activity sync fires Celery task |
| 25 | `test_trigger_plan_change_enqueues_refresh` | Plan create/update fires Celery task |
| 26 | `test_admin_refresh_endpoint_202` | `POST /v1/admin/home-briefing/refresh/{id}` returns 202 for admin |
| 27 | `test_admin_refresh_endpoint_403_non_admin` | Same endpoint returns 403 for non-admin athlete |
| 28 | `test_admin_refresh_audit_logged` | Admin refresh writes audit log entry |

### Category 3: Celery Task Tests

| # | Test | What it proves |
|---|------|---------------|
| 29 | `test_celery_task_writes_to_redis` | Task runs → Redis entry exists with correct structure |
| 30 | `test_celery_task_uses_gemini_by_default` | Task calls Gemini, not Opus |
| 31 | `test_celery_task_respects_feature_flag_for_opus` | Flag on → task uses Opus; flag off → Gemini |
| 32 | `test_celery_task_handles_provider_failure` | On failure: no cache written, task marked for retry |
| 33 | `test_celery_task_lock_prevents_parallel` | Concurrent task for same athlete is skipped |

### Category 4: Schema Contract Tests

| # | Test | What it proves |
|---|------|---------------|
| 34 | `test_briefing_state_present_when_briefing_null` | `briefing_state` always present even when `coach_briefing` is null |
| 35 | `test_briefing_state_enum_values_exhaustive` | Only valid enum values accepted by response model |

### Category 6: Production Smoke Tests (post-deploy)

| # | Test | What it proves |
|---|------|---------------|
| 36 | `test_home_latency_under_2s` | `GET /v1/home` responds in < 2s (no LLM blocking) |
| 37 | `test_briefing_appears_after_delay` | Initial load returns null → subsequent load within 60s returns briefing |
| 38 | `test_briefing_refreshes_after_checkin` | Do check-in → wait → verify briefing updated |

---

## Implementation Sequence

1. Redis cache reader/writer utility (the contract)
2. Celery task with dedupe + cooldown + circuit breaker + retry
3. Modify `/v1/home` to read from cache, remove inline LLM call (behind feature flag)
4. Wire triggers (check-in, activity, plan, beat schedule, intelligence write)
5. Admin refresh endpoint with auth + audit
6. Observability logging
7. Tests green, deploy, smoke test latency

---

## Success Criteria

Lane 2A is complete when:
- `/v1/home` p95 latency < 2s (currently 10-25s)
- Zero LLM calls on the request path
- Cache hit rate > 80% for active athletes within 24h of deploy
- All 39 tests passing
- Observability confirms cache behavior matches the staleness model
