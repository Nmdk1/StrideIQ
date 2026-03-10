# Security Hardening Execution Backlog

**Source:** Consolidated security audit (Feb 2026)  
**Purpose:** Actionable P0/P1/P2 tickets with acceptance criteria and test cases for agent execution

**Execution order:**
- P0: **P0-1 → P0-3 → P0-2** (close exposed surfaces before tightening throughput)
- Then P1, then P2

**Advisor notes:**
- **No batching:** Ship each P0 ticket in its own PR/commit. Test, deploy, verify logs, then move to the next.
- **Break-glass:** Every P0 ticket includes rollback + verification commands; run them before and after deploy.

---

## P0 — Immediate (today / 24h)

### P0-1: Lock down unauthenticated v1 endpoints

**Problem:** Several endpoints in `apps/api/routers/v1.py` are unauthenticated and expose data or accept user-controlled `athlete_id`, enabling IDOR.

**Endpoints to secure:**

| Endpoint | Current state | Required action |
|----------|---------------|-----------------|
| `GET /v1/athletes` | Unauthenticated, lists all athletes | Require admin OR remove |
| `GET /v1/athletes/{id}` | Unauthenticated, returns any athlete | Require auth + ownership (`id == current_user.id` or admin) |
| `POST /v1/activities` | Unauthenticated, accepts `athlete_id` in body | Require auth, ignore body `athlete_id`, use `current_user.id` |
| `POST /v1/checkins` | Unauthenticated, accepts `athlete_id` in body | Require auth, ignore body `athlete_id`, use `current_user.id` |
| `POST /v1/athletes/{id}/calculate-metrics` | Unauthenticated | Require auth + ownership OR admin |
| `GET /v1/athletes/{id}/personal-bests` | Unauthenticated | Require auth + ownership OR admin |
| `POST /v1/athletes/{id}/recalculate-pbs` | Unauthenticated | Require auth + ownership OR admin |
| `POST /v1/athletes/{id}/sync-best-efforts` | Unauthenticated | Require auth + ownership OR admin |

**Acceptance criteria:**
- [ ] All listed endpoints require `get_current_user` (or `require_admin` where appropriate)
- [ ] For write endpoints (`POST /activities`, `POST /checkins`): schemas or handler logic use `current_user.id` only; body `athlete_id` is ignored or rejected
- [ ] GET by ID: returns 403 if `id != current_user.id` and user is not admin

**Test cases:**
1. `GET /v1/athletes` without token → 401
2. `GET /v1/athletes/{other_user_id}` with valid token (non-admin) → 403
3. `POST /v1/activities` with body `athlete_id: <other_user_uuid>` without token → 401
4. `POST /v1/activities` with valid token; body `athlete_id: <other_user_uuid>` → activity created with `current_user.id`, not body value
5. `POST /v1/checkins` same as above
6. `POST /v1/athletes/{other_user_id}/calculate-metrics` without token → 401
7. `POST /v1/athletes/{other_user_id}/calculate-metrics` with valid token (non-admin) → 403

**Files:** `apps/api/routers/v1.py`, `apps/api/schemas.py` (if schema changes needed)

**Post-merge follow-up (non-blocking):** Refactor `create_activity` to use canonical `ActivityResponse` serialization instead of manual dict build—reduces drift risk from `routers/activities.py` mapping logic.

**Pre-merge review checklist** (strict security review evaluates in this order):
1. Auth added on all 8 endpoints
2. Ownership checks correct (athlete vs admin paths)
3. Write endpoints ignore body `athlete_id`
4. No route behavior regressions for legit clients
5. Tests prove unauthenticated + cross-user access are blocked

**Break-glass:**
- **Rollback:** `git revert <P0-1-commit-hash> --no-edit` then redeploy.
- **Verification (post-deploy):**
  ```bash
  # Unauthenticated requests must return 401
  curl -s -o /dev/null -w "%{http_code}" -X GET "$API_URL/v1/athletes"
  curl -s -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: application/json" -d '{"athlete_id":"'"$OTHER_UUID"'","start_time":"2026-01-01T00:00:00Z"}' "$API_URL/v1/activities"
  # Expect 401 for both
  ```

---

### P0-2: Add strict auth endpoint rate limits

**Problem:** Auth endpoints (`/login`, `/register`, `/forgot-password`, `/reset-password`) have no stricter limits than global default; credential stuffing and reset spam are easier.

**Changes in `apps/api/core/rate_limit.py`:**

1. Add auth endpoint limits to `endpoint_limits`:
   - `/v1/auth/login`: 10 per minute (per IP when unauthenticated)
   - `/v1/auth/register`: 5 per minute
   - `/v1/auth/forgot-password`: 5 per minute
   - `/v1/auth/reset-password`: 10 per minute

2. Optional: For auth endpoints only, consider fail-closed when Redis is unavailable (reject instead of allow). Document this as a trade-off; if fail-closed is too aggressive for ops, keep fail-open but add a warning log.

**Acceptance criteria:**
- [ ] `RateLimitMiddleware.endpoint_limits` includes the four auth paths above
- [ ] Unauthenticated requests to `/v1/auth/login` exceeding 10/min return 429
- [ ] Same for register, forgot-password, reset-password

**Test cases:**
1. Send 11 requests to `POST /v1/auth/login` within 60s from same IP → 11th returns 429
2. Send 6 requests to `POST /v1/auth/register` within 60s → 6th returns 429
3. Verify non-auth endpoints still use default limit (60/min)

**Files:** `apps/api/core/rate_limit.py`

**Break-glass:**
- **Rollback:** `git revert <P0-2-commit-hash> --no-edit` then redeploy.
- **Verification (post-deploy):**
  ```bash
  # 11th login attempt within 60s from same IP → 429
  for i in $(seq 1 11); do
    curl -s -o /dev/null -w "%{http_code}\n" -X POST -H "Content-Type: application/json" -d '{"email":"test@example.com","password":"x"}' "$API_URL/v1/auth/login"
  done
  # Last response should be 429
  ```

---

### P0-3: Production startup hard-fail checks

**Problem:** Dangerous defaults (e.g. `POSTGRES_PASSWORD=postgres`) and misconfig (e.g. `DEBUG=true`, `CORS_ORIGINS` empty) can silently make production insecure.

**Changes:**

1. **`apps/api/core/config.py`**
   - Add `_validate_production()` (or use Pydantic `model_validator`) that runs when `ENVIRONMENT == "production"`:
     - `DEBUG` must be `False`
     - `CORS_ORIGINS` must be non-empty (comma-separated allowed origins)
     - `POSTGRES_PASSWORD` must not equal `"postgres"` (or a short allowlist of known-weak values)
   - On validation failure: raise `ValueError` with clear message (e.g. "Production config invalid: POSTGRES_PASSWORD must not be default")

2. **`apps/api/main.py`**
   - In `startup` (or before app serves): call validation when `ENVIRONMENT == "production"`
   - Ensure startup fails fast before accepting requests

**Acceptance criteria:**
- [ ] With `ENVIRONMENT=production`, `DEBUG=true` → app fails to start with clear error
- [ ] With `ENVIRONMENT=production`, `CORS_ORIGINS=` (empty) → app fails to start
- [ ] With `ENVIRONMENT=production`, `POSTGRES_PASSWORD=postgres` → app fails to start
- [ ] With `ENVIRONMENT=development`, `POSTGRES_PASSWORD=postgres` → app starts normally (no change for local dev)

**Test cases:**
1. Unit test: `Settings(ENVIRONMENT="production", DEBUG=True, ...)` → raises
2. Unit test: `Settings(ENVIRONMENT="production", CORS_ORIGINS="", ...)` → raises
3. Unit test: `Settings(ENVIRONMENT="production", POSTGRES_PASSWORD="postgres", ...)` → raises
4. Integration: start API with prod env + bad config → exit code non-zero, no listening port

**Files:** `apps/api/core/config.py`, `apps/api/main.py`, `apps/api/tests/test_config_validation.py` (new)

**Break-glass:**
- **Rollback:** `git revert <P0-3-commit-hash> --no-edit` then redeploy. If app won't start due to config, fix env vars (e.g. set `DEBUG=false`, `CORS_ORIGINS`, strong `POSTGRES_PASSWORD`) and redeploy.
- **Verification (post-deploy):**
  ```bash
  # Prod API must start; bad config must fail fast
  ENVIRONMENT=production POSTGRES_PASSWORD=postgres python -c "from apps.api.main import app" 2>&1 || true
  # Expect startup failure with clear validation error
  # With correct prod env, API health check succeeds
  curl -s -o /dev/null -w "%{http_code}" "$API_URL/health"
  # Expect 200
  ```

---

## P1 — Short-term (2–5 days)

### P1-1: Add CAPTCHA to auth flows (Turnstile or equivalent)

**Problem:** Login, register, forgot-password, reset-password are bot-abusable; no CAPTCHA exists.

**Implementation:**

1. **Frontend (`apps/web`):**
   - Add Cloudflare Turnstile (or reCAPTCHA/hCaptcha) script to auth pages: login, register, forgot-password, reset-password
   - On form submit, include the CAPTCHA response token in the request body

2. **Backend (`apps/api/routers/auth.py`):**
   - Add env vars: `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY` (or equivalent)
   - For each auth endpoint: validate CAPTCHA token server-side before processing
   - If validation fails: return 400 with message "Verification failed"

**Acceptance criteria:**
- [ ] Login form includes Turnstile widget and sends token
- [ ] Register, forgot-password, reset-password likewise
- [ ] Server rejects request if token missing or invalid
- [ ] Feature can be disabled via env (e.g. `CAPTCHA_ENABLED=false`) for local/dev

**Test cases:**
1. POST login without token → 400
2. POST login with invalid/expired token → 400
3. POST login with valid token → 200 (or 401 if wrong creds)
4. E2E: Human can complete auth flow with CAPTCHA

**Files:** `apps/web` (auth pages), `apps/api/routers/auth.py`, `apps/api/core/config.py`

---

### P1-2: ZIP magic-byte validation in imports

**Problem:** Import upload validation is extension-based only; a malicious file named `.zip` could bypass if not actually a ZIP.

**Changes in `apps/api/routers/imports.py`:**

1. After reading file chunks (or before processing), verify magic bytes:
   - ZIP: `PK` (0x50 0x4B) at start of file
2. If magic bytes don't match → raise 400 "Invalid file format"

**Acceptance criteria:**
- [ ] File with `.zip` extension but wrong magic bytes (e.g. PE executable) → 400
- [ ] Valid ZIP file → accepted and processed as before

**Test cases:**
1. Upload file with `.zip` extension, content starts with `MZ` (PE) → 400
2. Upload valid ZIP → 202 or success (existing behavior)

**Files:** `apps/api/routers/imports.py`, `apps/api/tests/test_imports_validation.py`

---

### P1-3: Add npm audit to CI

**Problem:** No `npm audit` gate in CI; frontend CVEs can go unnoticed.

**Changes in `.github/workflows/ci.yml`:**

1. Add step in `frontend-test` or `frontend-build` (or new job):
   ```yaml
   - name: npm audit
     working-directory: apps/web
     run: npm audit --production --audit-level=high
   ```
2. Configure to fail on high/critical. Use `--audit-level=moderate` if high is too noisy initially; document and tighten over time.

**Acceptance criteria:**
- [ ] CI runs `npm audit` for `apps/web`
- [ ] CI fails when high/critical vulnerabilities exist (or moderate, per policy)
- [ ] `npm audit fix` can be run to resolve where safe

**Files:** `.github/workflows/ci.yml`

---

## P2 — Next hardening phase (1–2 weeks)

### P2-1: Implement DB Row Level Security (RLS)

**Problem:** No RLS in Postgres; isolation is app-layer only. A single missed ownership check can lead to cross-user data exposure.

**Implementation:**

1. **Alembic migration:**
   - Enable RLS on athlete-scoped tables: `athlete`, `activity`, `daily_checkin`, `personal_best`, `best_effort`, etc.
   - Create policies: `athlete_id = current_setting('app.current_athlete_id')::uuid` (or equivalent)
   - Admin bypass: policy allows when `current_setting('app.is_admin')::bool = true`

2. **Request-scoped tenant context:**
   - Middleware or dependency: set `app.current_athlete_id` and `app.is_admin` at request start from JWT/session
   - For unauthenticated requests, set to NULL or deny

**Acceptance criteria:**
- [ ] RLS policies exist for core athlete-scoped tables
- [ ] App sets tenant context per request
- [ ] Direct SQL without context (e.g. from migration script) still works when context is set explicitly
- [ ] Regression test: attempt to query another user's data via raw SQL without setting context → no rows (or error)

**Test cases:**
1. Migration applies cleanly
2. Authenticated request for own data → success
3. Authenticated request attempting to access other user's data via app → 403 (existing)
4. Raw SQL with `SET app.current_athlete_id = ...` → returns only that user's rows

**Files:** `apps/api/alembic/versions/`, `apps/api/core/` (middleware or db session setup)

---

### P2-2: Tighten pip-audit CI policy

**Problem:** `pip-audit` runs with `continue-on-error: true`; high/critical Python CVEs don't block CI.

**Changes in `.github/workflows/ci.yml`:**

1. Remove `continue-on-error: true` from pip-audit step, OR
2. Add `--format cyclonedx` and a policy that fails on high/critical

**Acceptance criteria:**
- [ ] CI fails when pip-audit reports high/critical vulnerabilities
- [ ] Low/moderate can remain as warnings (configurable)

**Files:** `.github/workflows/ci.yml`

---

### P2-3: Security regression tests for IDOR

**Problem:** Ensure athlete-scoped endpoints consistently enforce ownership; prevent future regressions.

**Implementation:**

1. Create `apps/api/tests/test_security_idor_regression.py`:
   - For each athlete-scoped resource (activities, checkins, calendar, progress, etc.):
     - Obtain valid JWT for user A
     - Attempt to access/modify user B's resource (by ID)
     - Assert 403 or 404 (never 200 with B's data)

**Acceptance criteria:**
- [ ] Test suite covers all major athlete-scoped endpoints
- [ ] Tests run in CI
- [ ] New endpoints must pass analogous checks before merge

**Files:** `apps/api/tests/test_security_idor_regression.py`, `.github/workflows/ci.yml` (add to backend-test)

---

## Summary checklist

| ID | Title | Priority | Order | Est. effort |
|----|-------|----------|-------|-------------|
| P0-1 | Lock down unauthenticated v1 endpoints | P0 | 1 | 2–3h |
| P0-3 | Production startup hard-fail checks | P0 | 2 | 1–2h |
| P0-2 | Add strict auth endpoint rate limits | P0 | 3 | 1h |
| P1-1 | Add CAPTCHA to auth flows | P1 | 4–6h |
| P1-2 | ZIP magic-byte validation in imports | P1 | 1h |
| P1-3 | Add npm audit to CI | P1 | 0.5h |
| P2-1 | Implement DB RLS | P2 | 1–2 days |
| P2-2 | Tighten pip-audit CI policy | P2 | 0.5h |
| P2-3 | Security regression tests for IDOR | P2 | 2–4h |

---

## Agent execution notes

- **No interpretation drift:** Each ticket is self-contained; implement exactly as specified.
- **Tests first:** When possible, add test cases before or in parallel with implementation.
- **Do not skip P0:** P0 tickets address the highest-risk findings and should be completed before P1.
- **Schema changes:** For P0-1, if `ActivityCreate`/`DailyCheckinCreate` are shared, consider creating internal schemas that omit `athlete_id` for v1 write endpoints, or add a validator that rejects body `athlete_id` when it differs from `current_user.id`.
- **First PR review:** Paste the P0-1 diff for strict pre-merge security review (findings-first, severity-ranked).
