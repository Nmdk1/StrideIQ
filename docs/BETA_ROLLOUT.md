# Beta rollout (production-beta ready)

This checklist is meant to be followed for the first production beta cohort.

## Invite gating (must be enforced)

### Enable “invites required”

- Set feature flag `system.invites_required` to enabled.
  - Admin UI path depends on deployment; API is always available.
- OAuth flows (e.g. Strava) must never create new athletes; they only link to an existing authenticated athlete.

### Generate invites (invite allowlist)

Invites are email-based allowlist entries (audited), created by an admin:

- `POST /v1/admin/invites` with body `{ "email": "someone@example.com", "note": "beta cohort 1" }`
- `GET /v1/admin/invites?active_only=true` to see remaining active/unused invites
- `POST /v1/admin/invites/revoke` with body `{ "email": "someone@example.com", "reason": "removed from cohort" }`

Once the invited user registers via `POST /v1/auth/register`, the invite is marked used (audited) and can’t be reused.

## Monitoring (minimal, beta-safe)

### Coach Action Automation lifecycle

- **Admin Ops Pulse**: `GET /v1/admin/ops/coach-actions?hours=24`
  - Returns counts by status (proposed/confirmed/applied/failed/rejected) plus top failure reasons.
- **Structured logs + Sentry breadcrumbs**: API emits `coach_action_event` logs for:
  - `coach.action.proposed` (+ idempotent hits)
  - `coach.action.applied`
  - `coach.action.apply_failed` (includes error reason)
  - `coach.action.rejected`

### What to watch

- **Spikes in `failed`**: check top failure reasons and correlate to action types.
- **High propose → low confirm**: indicates UX confusion or overly aggressive proposals.
- **Repeated idempotent hits**: can indicate client retries or double-submits.

## First-user onboarding flow (quick)

- Register with invited email: `POST /v1/auth/register`
- Complete onboarding intake: `GET/POST /v1/onboarding/intake` stages
- Connect Strava (optional for beta): `GET /v1/strava/auth-url` then `/v1/strava/callback`
- Confirm the calendar is seeded (starter plan) and visible

## Local dogfood (end-to-end)

Goal: exercise **propose → confirm → apply**, verify:

- calendar/workout state changed as expected
- apply receipt returned
- audit log (`plan_modification_log`) entries exist with `source="coach"`

Recommended local run:

- Start stack: `docker compose up -d`
- Run the dogfood script: `apps/api/scripts/beta_dogfood_phase10.py`
- Inspect:
  - API output (script prints IDs + before/after)
  - Ops snapshot: `GET /v1/admin/ops/coach-actions?hours=1`
  - DB audit: `plan_modification_log` recent rows for the test athlete

## Rollback / safety levers

- **Stop new signups**: disable all invites by revoking pending invites, and/or keep `system.invites_required` enabled with an empty allowlist.
- **Disable risky automation paths**: keep Coach Action Automation UI off (no proposal payloads emitted) while retaining backend endpoints for admins/dogfood.
- **Pause ingestion** (if needed): `POST /v1/admin/ops/ingestion/pause`

