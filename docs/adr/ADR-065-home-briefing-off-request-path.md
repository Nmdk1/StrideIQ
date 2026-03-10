# ADR-065: Home Briefing Off Request Path

**Status:** Accepted  
**Date:** 2026-02-18  
**Context:** SEV-1 incidents (Feb 17-18) caused by LLM calls blocking `/v1/home`. Pages take 10-25s when cache misses. Lane 2A of the performance plan.

---

## Decision

The home coach briefing is served **cache-first, never inline LLM**. The `/v1/home` endpoint reads from Redis and returns immediately. LLM generation happens asynchronously via Celery.

## Options Considered

### Option A: Keep inline LLM with tighter timeouts
- Pro: No new infrastructure.
- Con: Even with 15s timeout, tail latency is 15s. With 3 workers, 3 concurrent cache misses saturate the API. Doesn't solve the fundamental problem.

### Option B: Celery precompute + Redis cache (chosen)
- Pro: Home endpoint never blocks on LLM. Predictable latency. Workers freed for auth/data requests. Extensible to other heavy computes (Lane 2B).
- Con: Adds staleness window. First visit after cold start returns no briefing.

### Option C: Edge-side caching (CDN)
- Pro: Zero origin latency for cached responses.
- Con: Briefings are per-athlete and auth-gated. CDN caching is inappropriate for personalized, authenticated content.

## Staleness Model

| State | Age | Behavior |
|-------|-----|----------|
| `fresh` | < 15 min | Return cached payload |
| `stale` | 15-60 min | Return cached payload + enqueue refresh |
| `missing` | > 60 min or no cache | Return `coach_briefing: null` + enqueue refresh |
| `refreshing` | Task in-flight | Return whatever cache exists (fresh/stale/null) |

- No stale served beyond 60 min, even if Redis entry still exists.
- Redis key TTL set to 3600s (hard expiry).
- Application logic enforces the 15/60 boundaries using `generated_at`.

## Redis Cache Contract

**Key:** `home_briefing:{athlete_id}`

**Value (JSON):**
```json
{
  "payload": { ... briefing fields ... },
  "generated_at": "2026-02-18T19:30:00Z",
  "expires_at": "2026-02-18T20:30:00Z",
  "source_model": "gemini-2.5-flash",
  "version": 1,
  "data_fingerprint": "sha256:abc123..."
}
```

**TTL:** 3600s (Redis-enforced hard expiry)

## Regeneration Triggers

1. Check-in saved
2. New activity ingested (Strava/Garmin sync)
3. Training plan created, updated, or deleted
4. Race goal updated
5. Daily intelligence write completion (new insights/narration landed)
6. Manual refresh: `POST /v1/home/admin/briefing-refresh/{athlete_id}` (admin/owner only, audit-logged; founder == owner by convention)
7. Celery beat: every 15 min for athletes active in last 24 hours

## Stampede Protection

- **Enqueue cooldown:** 60s per athlete. Multiple triggers within the cooldown window are coalesced into one task.
- **In-flight dedupe:** Redis lock (`home_briefing_lock:{athlete_id}`, 120s TTL). If lock exists, enqueue is skipped.
- **Repeated failure circuit:** After 3 consecutive provider failures for an athlete, stop requeueing for 15 min. Serve stale (if within 60 min) or null.

## Task Behavior

- **Runtime timeout:** 15s hard limit on Celery task.
- **Provider timeout:** 12s on LLM SDK call.
- **Retry:** Up to 3 attempts with exponential backoff (10s, 30s, 60s).
- **Idempotent:** Same athlete + data fingerprint produces same result. No duplicate work.
- **DB session:** Task creates its own `SessionLocal()`. Never receives a request-scoped session.

## Model Policy

- **Default:** Gemini 2.5 Flash. Home briefing is summarization/synthesis, not high-stakes advisory.
- **Feature flag:** `home_briefing_use_opus` — when enabled, task uses Opus with Gemini fallback. Off by default.
- **Rationale:** Removes the "fallback tax" where Opus fails (credits/timeout) and then Gemini runs, doubling latency.

## Observability

Mandatory logging/metrics:
- Cache hit state per request (`fresh/stale/missing/refreshing`)
- Celery task duration (p50, p95)
- Task failures and retries (count, reason)
- Enqueue rate and dedupe/cooldown skips
- Provider-level latency and error rates

These are required to prove Lane 2A achieved its goal.

## `/v1/home` Endpoint Changes

**Invariant: `/v1/home` never waits on a Celery task or LLM provider. It always returns immediately with cache or null.**

- Remove `asyncio.to_thread` + `asyncio.wait_for` LLM call block entirely.
- Replace with Redis cache read (< 1ms).
- If cache is stale or missing, enqueue a Celery task via `task.delay()` (fire-and-forget). The endpoint does not `await` the task result, does not poll for completion, and does not block on the task in any way.
- Add `briefing_state` field to response (`fresh | stale | missing | refreshing`).
- `briefing_state` is always present and enum-valid, even when `coach_briefing` is null.
- All deterministic payload (workout, insight, week, signals, etc.) unchanged.

**SLO contract:**
- `/v1/home` p95 < 2s when provider is healthy.
- `/v1/home` p95 < 2s when provider is down/slow (cache miss returns null + enqueue).

## Extensibility (Lane 2B)

The cache/job contract is designed so that `hero_narrative`, `coach_noticed`, and other expensive computes can be added as additional cached fields or separate cache keys using the same:
- Staleness model (configurable per field)
- Trigger mechanism
- Stampede protection
- Observability pattern

No architectural changes needed for Lane 2B.

## Rollout Plan

1. Deploy with feature flag `lane_2a_cache_briefing` (off by default).
2. Enable for founder account first. Verify latency, cache behavior, briefing quality.
3. Enable for all athletes. Monitor cache hit rates and p95 latency.
4. Remove inline LLM code path after 1 week of stable operation.

## Rollback Plan

- Disable feature flag → reverts to inline LLM behavior (old code path preserved until removal).
- No data migration needed. Redis cache is ephemeral.

## Consequences

- First-time visitors see no coach briefing until Celery generates one (typically < 30s).
- Briefings may be up to 15 minutes stale under normal operation.
- Celery worker must be healthy for briefings to regenerate. Worker health becomes a production dependency (already exists for other tasks).
