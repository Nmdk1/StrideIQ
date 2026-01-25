# Security Secrets: Inventory + Rotation Policy

This document defines **what secrets exist**, **how often to rotate**, and **how to validate** a rotation.

Guiding rules:
- **Never commit real secrets** (local secrets belong in `.env`, which is gitignored).
- **Prefer least privilege** (scoped tokens, smallest perms).
- **Rotate on incident** immediately (suspected leak counts as incident).

---

## Critical secrets inventory (by system)

### Core application / auth
- **`SECRET_KEY`** (aka “JWT secret” / sometimes referred to as `JWT_SECRET_KEY`)
  - **Purpose**: signs/verifies JWT access tokens.
  - **Rotation impact**: rotating invalidates all existing tokens (expected).
- **`TOKEN_ENCRYPTION_KEY`**
  - **Purpose**: encrypts provider tokens at rest (e.g., Strava/Garmin tokens).
  - **Rotation impact**: requires a planned migration strategy if existing ciphertext must remain readable.

### Strava
- **`STRAVA_CLIENT_ID`** (not secret, but critical config)
- **`STRAVA_CLIENT_SECRET`** (secret)
- **`STRAVA_WEBHOOK_VERIFY_TOKEN`** (secret, if webhooks enabled)
- **`STRAVA_REDIRECT_URI`** (not secret, but must match Strava app settings)

### Garmin (future official API / integrations)
- **`GARMIN_CLIENT_ID`** (not secret, but critical config)
- **`GARMIN_CLIENT_SECRET`** (secret)

### Stripe / billing
- **`STRIPE_SECRET_KEY`** (secret; grants API access)
- **`STRIPE_WEBHOOK_SECRET`** (secret; validates webhook signatures)

### Observability / third party
- **`SENTRY_DSN`** (secret-ish; treat as sensitive because it can route data to a project)
- **`OPENAI_API_KEY`** (secret; if used in any runtime paths)

### Data / infrastructure
- **`POSTGRES_PASSWORD`** (secret)
- **`DATABASE_URL`** (secret; typically embeds password)
- **`REDIS_URL`** (may be secret depending on deployment; treat as sensitive in prod)

---

## Rotation cadence (baseline)

Rotate on this schedule unless there’s an incident:
- **Every 90 days**: `STRAVA_CLIENT_SECRET`, `GARMIN_CLIENT_SECRET`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `OPENAI_API_KEY`
- **Every 180 days**: `SENTRY_DSN`, `POSTGRES_PASSWORD` / `DATABASE_URL` (or sooner if access patterns change)
- **On demand (planned)**: `SECRET_KEY`, `TOKEN_ENCRYPTION_KEY` (these require care due to token invalidation / data readability)

Rotate immediately (outside cadence) if:
- A secret is exposed in logs, screenshots, CI output, or a public repo.
- A laptop/dev machine is compromised or lost.
- A vendor reports suspicious activity.

---

## Break-glass procedure (suspected leak)

1. **Contain**
   - Revoke/rotate the suspected secret(s) first (vendor dashboard / key management).
   - Disable affected integrations temporarily if needed (feature flag / config toggle).
2. **Invalidate sessions**
   - If `SECRET_KEY` is impacted: rotate it (forces re-auth).
3. **Audit**
   - Review recent `AdminAuditEvent` for suspicious admin actions.
   - Review provider dashboards (Strava/Stripe) for unusual traffic.
4. **Recover**
   - Deploy updated secrets to all environments.
   - Run smoke tests (see below).
5. **Document**
   - Record what was rotated, when, and why (internal incident notes).

---

## Validation checklist (post-rotation)

### Always (all rotations)
- Confirm services start and can connect to Postgres/Redis.
- Run backend smoke subset in Docker:
  - `pytest -q` on the repo’s `backend-smoke` list (see `.github/workflows/ci.yml`).
- Confirm the CI secret scan passes (no literal leaks).

### If rotating `SECRET_KEY` (JWT signing)
- Expect all existing tokens to fail (401) — this is correct.
- Validate:
  - `GET /v1/gdpr/export` succeeds after re-auth.
  - Admin endpoints require re-auth; token/JWT invariants tests pass.

### If rotating `TOKEN_ENCRYPTION_KEY`
- **Plan required**:
  - Either support dual-read (old+new keys) during a migration window, or re-encrypt stored ciphertext.
- Validate:
  - Provider token decryption still works (Strava sync / provider flows).

### If rotating Stripe secrets
- Validate:
  - Webhook signature verification succeeds in the target environment.
  - Admin billing actions remain auditable.

---

## CI guardrail (names only)

CI includes a lightweight check that **deployment/config templates mention required secret names**
to prevent “secret drift” (accidentally removing a required env var from templates). This check
does **not** validate values.

