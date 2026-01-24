## Agent Handoff: Phase 3 (Latency Bridge) — Invites + Strava OAuth Choreography

**Date:** 2026-01-24  
**Branch:** `stable-diagnostic-report-2026-01-14`  
**Owner intent:** Phase 3 with Option B: DB-backed invite allowlist, enforced at all account creation boundaries (including Strava OAuth), scalable for production.

---

## Executive Summary

Phase 3 is underway. The onboarding flow now avoids “dead air” by ensuring:

- Account creation is **invite-only** via a **DB-backed allowlist** (auditable).
- Strava OAuth callback is no longer a JSON dead-end and cannot bypass invites.
- Strava OAuth binds to the already-authenticated athlete via **signed state**, then redirects back to the web UI and queues an initial ingestion bootstrap.
- Onboarding and Home can show **deterministic ingestion progress** (latency bridge).

---

## What shipped (high signal)

### 1) Invite allowlist (DB-backed + auditable)

New tables:
- `invite_allowlist` (one row per invited email; can be revoked; marked used on registration)
- `invite_audit_event` (append-only audit events)

Enforcement:
- `POST /v1/auth/register` now requires an active invite; marks invite used on success.
- Strava OAuth callback cannot create new athletes and requires valid signed state.
- Legacy `POST /v1/athletes` is now **admin-only** (closes bypass).

Admin API (no UI added; Phase 4 not started):
- `GET /v1/admin/invites`
- `POST /v1/admin/invites`
- `POST /v1/admin/invites/revoke`

Key files:
- `apps/api/models.py`
- `apps/api/services/invite_service.py`
- `apps/api/routers/auth.py`
- `apps/api/routers/admin.py`
- `apps/api/routers/v1.py`
- Migration: `apps/api/alembic/versions/d3e4f5a6b7c8_add_invite_allowlist_and_audit.py`

### 2) Strava OAuth choreography (no bypass, returns to web)

- `GET /v1/strava/auth-url?return_to=/path` now returns an auth URL with a **signed `state`** binding to the current user.
- `GET /v1/strava/callback` now:
  - verifies signed state (TTL-based)
  - links tokens to that existing athlete
  - queues a cheap index backfill (`tasks.backfill_strava_activity_index`)
  - redirects back to `WEB_APP_BASE_URL + return_to` with `?strava=connected`

Key files:
- `apps/api/services/oauth_state.py`
- `apps/api/routers/strava.py`
- `apps/api/services/strava_service.py`
- `apps/api/core/config.py` (`WEB_APP_BASE_URL`, `OAUTH_STATE_TTL_S`)

### 3) Latency bridge endpoints + UI surfacing

API:
- `GET /v1/onboarding/status`
- `POST /v1/onboarding/bootstrap` (queues index backfill + full sync; best-effort idempotency)

Web:
- Onboarding Connect stage now uses `auth-url` and can start import + show “connected/importing” status.
- Settings Strava connect now uses `return_to=/settings` and refreshes status on `?strava=connected`.
- Home now includes an “Import in progress” card when connected but no activities yet.

Key files:
- `apps/api/routers/onboarding.py`
- `apps/web/app/onboarding/page.tsx`
- `apps/web/components/integrations/StravaConnection.tsx`
- `apps/web/app/home/page.tsx`
- `apps/web/lib/api/services/onboarding.ts`
- `apps/web/lib/hooks/queries/onboarding.ts`

---

## Tests added (anti-regression)

API:
- `tests/test_invite_allowlist_register.py`
- `tests/test_admin_invites.py`
- `tests/test_strava_oauth_state.py`

All API tests passed after changes (`pytest -q`).

Web:
- Existing Jest suite still passes (`npm test`).

---

## How to verify (manual golden path)

1) Admin creates invite:
- `POST /v1/admin/invites` with email

2) User registers:
- `/register` should succeed only if invited

3) Onboarding → Connect Strava:
- “Connect Strava” redirects to Strava OAuth
- After authorizing, you land back on `/onboarding?strava=connected`
- Click “Continue” after connection, or “Start Import” if needed

4) Home shows progress:
- `/home` should show “Import in progress” until activities appear

---

## Known remaining Phase 3 work

- Tighten the “bootstrap” strategy (when to queue full sync vs only index) for load spikes.
- Improve progress UI fidelity (e.g., show counts of activities created once index finishes).
- Decide if we want an invite “used by” surfacing in admin UI later (Phase 4).

