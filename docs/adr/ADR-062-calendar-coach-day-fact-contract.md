# ADR-062: Calendar Coach Day-Fact Trust Contract

**Status:** Accepted  
**Date:** 2026-02-09  
**Owner:** StrideIQ

## Context

Calendar day coaching produced trust-breaking factual errors:
- Wrong weekday for the requested ISO date.
- Incorrect pace relation claims (for example claiming a run pace was faster than marathon pace when it was slower).

Root causes were narrow and concrete:
1. Day context did not expose canonical weekday and deterministic pace-vs-marathon comparisons.
2. `compute_running_math` existed but was not registered in coach tool declarations.
3. Calendar day responses were not fail-closed when day context verification failed.

## Decision

Adopt a strict day-fact contract for `context_type=day` requests:

1. `get_calendar_day_context` must return canonical day facts:
   - `date`
   - `weekday`
   - `weekday_index`
   - deterministic pace-vs-marathon fields for activities

2. Register `compute_running_math` across AI Coach tool declarations and dispatch paths.

3. Enforce fail-closed behavior in `POST /v1/calendar/coach`:
   - If day context preflight is unavailable or incomplete, do not call the model.
   - Return a safe "cannot answer this safely" response instead of speculative coaching text.

## Consequences

### Positive
- Prevents weekday/date drift in calendar day answers.
- Prevents pace-relation direction errors from free-form model arithmetic.
- Protects trust by refusing speculative outputs when required facts are unavailable.

### Trade-offs
- Slightly stricter behavior when data retrieval fails (more explicit safe failures).
- Day-context request path now depends on preflight context completeness.

## Acceptance Criteria

1. Day context for `2026-02-10` returns `weekday = Tuesday`.
2. Pace relation fields are mathematically consistent with activity pace and marathon pace reference.
3. Calendar day endpoint fails closed if day context preflight does not return required facts.
4. `compute_running_math` appears in assistant and opus tool registries.

## Notes

This ADR intentionally scopes to the minimal corrective set needed for trust restoration in calendar day coaching, without broader coach pipeline redesign.
