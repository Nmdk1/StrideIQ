# ADR-051: Invite-Only Access and Auditable Invites (Private Beta Gate)

## Status
**Accepted (Implemented)**

## Date
2026-01-24

## Context
StrideIQ is in private beta where:
- Access must be controlled (product quality + support capacity + infra safety).
- “Invite-only” must be enforceable at **every account-creation boundary** (not just UI), otherwise it is bypassable.
- Operator actions must be **auditable** (who invited whom, who revoked, who used).

Environment-flag gating (e.g. `ALLOW_SIGNUPS=true`) is not acceptable because it is:
- not auditable
- easy to drift across environments
- not extensible into future entitlements

## Decision
Use a **DB-backed invite allowlist** as the authoritative access gate.

### Enforcement points (must be server-side)
- `POST /v1/auth/register`: reject if email is not invited/active.
- Strava OAuth callback(s): reject account creation/binding if email is not invited/active.

### Invites as first-class domain objects
Invites are append-audited domain objects:
- who created
- who revoked
- who consumed
- timestamps + reasons/notes

## Consequences
### Positive
- Access control is centralized, testable, and auditable.
- Supports later evolution into “trial/grants/tiers” without rework.
- Enables operational workflows (“revoke invite”, “see invite usage”).

### Negative
- Requires keeping invite state consistent across tests/environments.
- Adds admin surface area (must be guarded and audited).

## Audit Logging Requirements
Minimum audit events:
- invite created (email, note, inviter id)
- invite revoked (email, revoker id, reason)
- invite used (email, user id)

## Test Strategy
- Integration tests must prove:
  - invite state flips active → used in the DB (not mocked)
  - enforcement at registration rejects non-invited users
  - enforcement at OAuth callback rejects non-invited users

## Security / Privacy Considerations
- Treat invite emails as sensitive (avoid logging raw email in generic logs).
- All invite endpoints must require admin/owner access.

## Related
- Phase ledger: `docs/PHASED_WORK_PLAN.md`
- Onboarding handoff: `docs/AGENT_HANDOFF_2026-01-24_PHASE_3_LATENCY_BRIDGE_INVITES_AND_STRAVA_CHOREOGRAPHY.md`

