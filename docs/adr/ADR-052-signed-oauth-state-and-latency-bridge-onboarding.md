# ADR-052: Signed OAuth State and “Latency Bridge” Onboarding Contract

## Status
**Accepted (Implemented)**

## Date
2026-01-24

## Context
OAuth callback flows are a common integrity failure point:
- `state` parameters are often treated as opaque, but if unsigned they can be forged/replayed.
- Onboarding “dead air” erodes trust (users don’t know if sync is working).
- Long-running ingestion cannot happen inside HTTP requests (timeouts, rate limits, bad UX).

StrideIQ’s onboarding contract must be:
- **tamper-resistant**
- **non-blocking**
- **deterministic** in what the user sees (progress/status)

## Decision
1) Use **signed OAuth state** to bind callbacks to the initiating user/session and prevent tampering.  
2) Implement onboarding as a **Latency Bridge**:
- HTTP endpoints queue work
- the UI shows deterministic ingestion progress/queued status while the user completes an intake “interview”

### Latency Bridge UX requirements
- User never sees an empty dashboard with no explanation.
- If Strava is connected but ingestion state is not yet populated, show “Import queued”.
- If ingestion is running, show “Importing…” state.

## Consequences
### Positive
- Prevents forged OAuth callback state from binding wrong users.
- Eliminates “is it working?” ambiguity during ingestion.
- Keeps ingestion and retry semantics in workers, not the API layer.

### Negative
- Requires durable ingestion-state tracking and careful UI states.
- Requires test isolation for global/system flags that affect ingestion.

## Test Strategy
Backend integration test requirements:
- Extract the `state` from the generated auth URL and pass it back to the callback.
- If the callback uses an altered/random `state`, it must fail.
- Only mock external Strava HTTP + Celery `.delay()`. DB + auth logic must be real.

Frontend test requirements:
- Force `ingestion_state` to “queued/running” and verify the correct card/banner appears.

## Security / Privacy Considerations
- State signatures must use server-held secrets and enforce TTL.
- Avoid returning tokens in callback responses; store server-side and redirect safely.

## Related
- Phase ledger: `docs/PHASED_WORK_PLAN.md`
- Worker resilience: `docs/adr/ADR-054-viral-safe-ingestion-resilience-and-emergency-brake.md`

