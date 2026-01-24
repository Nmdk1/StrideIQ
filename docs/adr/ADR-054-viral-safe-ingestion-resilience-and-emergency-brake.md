# ADR-054: Viral-Safe Ingestion Resilience and Emergency Brake

## Status
**Accepted (Implemented)**

## Date
2026-01-24

## Context
StrideIQ ingests Strava data asynchronously. Under traffic spikes (e.g., influencer mentions), the failure modes are predictable:
- Strava rate limits (429) can cause worker stalls if workers sleep.
- Excess retries can turn “expected backpressure” into “error storms”.
- Operators need a manual, immediate way to stop ingestion fan-out during incidents.

Policy constraints:
- **Deferral logic lives in workers**, not HTTP endpoints.
- HTTP endpoints should queue work or fail fast; they should not perform complex 429 handling.

## Decision
Implement a “Viral-Safe Shield” for ingestion:
1) **Rate Limit Armor**: on Strava 429 in workers, defer and retry later without marking errors.
2) **Emergency Brake**: a DB-backed `system.ingestion_paused` flag to stop enqueueing new ingestion work.
3) **Ops visibility**: show deferred/stuck/errors and pause status in admin UI.

### Rate Limit Armor semantics
- Workers call Strava with `allow_rate_limit_sleep=False`.
- On 429, raise a typed error (e.g., `StravaRateLimitError`) that includes `retry_after_s`.
- Task behavior:
  - mark ingestion state as `deferred` with `deferred_until` and `deferred_reason="rate_limit"`
  - clear `last_error` so deferrals don’t appear as failures
  - `self.retry(countdown=...)` with sane bounds

### Emergency Brake semantics
- `system.ingestion_paused = true`:
  - Strava callback stores tokens but **skips enqueuing** ingestion
  - admin “retry ingestion” returns **409** (blocked) so operators don’t accidentally fan out
- Home UI shows a calm banner (“Import delayed…”) when paused so users aren’t confused.

## Consequences
### Positive
- Prevents worker stalls; preserves throughput under rate limits.
- Converts rate limits into predictable backpressure (defer) instead of noisy errors.
- Operators can stop the bleeding quickly during incidents.

### Negative
- Requires careful state management so “deferred” is not treated as “failed”.
- Requires UI/ops tooling so the system remains debuggable.

## Test Strategy
- Unit/integration tests must prove:
  - 429 → `deferred_until` set, `deferred_reason="rate_limit"`, and task reschedules via `Retry`
  - 429 does not show up as an error state
  - `system.ingestion_paused` skips enqueue at callback
  - admin retry is blocked with 409 when paused

## Security / Privacy Considerations
- Pause control is a system-level lever; it must be explicitly permissioned (`system.*`).
- Avoid leaking token details or athlete-private identifiers in logs/UI.

## Related
- Ops playbook: `docs/OPS_PLAYBOOK.md`
- Phase ledger: `docs/PHASED_WORK_PLAN.md`

