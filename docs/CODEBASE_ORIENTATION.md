# Codebase Orientation for Builders

**Audience:** New builder agents starting a session.
**Read after:** `docs/FOUNDER_OPERATING_CONTRACT.md`
**Updated:** February 26, 2026

This document captures the friction points, conventions, and structural facts that every builder needs to know before touching code. It is not a tutorial — it is a survival guide.

---

## 1. Repo Structure

```
StrideIQ/                         ← workspace root
├── apps/
│   ├── api/                      ← FastAPI backend (Python)
│   ├── web/                      ← Next.js 13+ frontend (TypeScript)
│   └── worker/                   ← (Celery is run from apps/api, not a separate app)
├── docs/                         ← all specs, handoffs, ADRs
├── docker-compose.yml            ← LOCAL dev containers (named running_app_*)
├── docker-compose.prod.yml       ← PRODUCTION containers (named strideiq_*)
├── Caddyfile                     ← Caddy reverse proxy config (prod)
└── .env                          ← gitignored; real secrets; do NOT commit
```

---

## 2. Shell Environment — CRITICAL

The workspace is **Windows PowerShell**. Several common Unix patterns fail silently or loudly:

| Do NOT use | Use instead | Why |
|-----------|-------------|-----|
| `cmd1 && cmd2` | `cmd1; cmd2` | `&&` is not valid in PS |
| `tail -n 20 file` | `Get-Content file \| Select-Object -Last 20` | `tail` not available |
| `cat file` | `Get-Content file` or use the Read tool | — |
| `grep pattern file` | Use the Grep tool, or `Select-String` | — |
| Here-doc `<<'EOF'` | Write to file first, then reference | PS has no heredoc |
| `find . -name "*.py"` | Use the Glob tool | — |

**SSH commands to the droplet are fine** — the remote shell is bash. All `ssh root@strideiq.run "..."` commands execute in bash normally.

**Multi-line git commit messages on Windows:**
```powershell
git commit -m "short subject line`n`nBody paragraph here."
```
Backtick-n (`n`) is the PowerShell newline escape. Do NOT use `$(cat <<'EOF' ...)` — it breaks.

---

## 3. Backend — FastAPI (`apps/api/`)

### Entry point
`apps/api/main.py` — FastAPI app object, all middleware, all router registration.

Every new router must be imported and registered here. Pattern:
```python
from routers import my_new_router
app.include_router(my_new_router.router)
```

### Router convention
All production routes live under `/v1/`. Every router file uses:
```python
router = APIRouter(prefix="/v1/my-resource", tags=["my-resource"])
```

### Database import — DO NOT USE `from database import`
```python
# CORRECT
from core.database import get_db, SessionLocal, engine

# WRONG — deprecated shim, will emit warnings
from database import get_db
```
`database.py` is a backwards-compat shim only. All new code uses `core.database`.

### Models — all in one file
`apps/api/models.py` — monolithic SQLAlchemy ORM. Every table is here.
Key models: `Athlete`, `Activity`, `ActivitySplit`, `ActivityStream`, `GarminDay`, `DailyCheckin`, `Subscription`, `FeatureFlag`, `FeatureFlagAllowlist`.

### Auth / security
```python
from core.auth import get_current_user, require_admin
from core.security import create_access_token
```
`get_current_user` → returns current `Athlete` from JWT. Use as a FastAPI `Depends`.
`require_admin` → same but asserts `athlete.role == "admin"`.

### Feature flags
```python
from core.feature_flags import is_feature_enabled

enabled = is_feature_enabled("garmin_connect_enabled", str(athlete.id), db)
```
Flags are stored in the `feature_flags` table. On failure, defaults to `True` (fail open).

Active flags to know:
- `garmin_connect_enabled` — rollout 0%, allowlist: founder + father. Do not change without instruction.
- `lane_2a_cache_briefing` — home briefing Celery cache. Live for founder.

### Services directory
`apps/api/services/` — business logic. Never import from `routers/` inside services.

Notable services:
- `garmin_adapter.py` — all raw Garmin payload translation (source contract: no raw field names outside this file)
- `coach_tools.py` — coaching intelligence retrieval (`get_wellness_trends`, `build_athlete_brief`)
- `garmin_backfill.py` — multi-window historical backfill (30-day activity chunks, 90-day health chunks)

### Tasks (Celery)
`apps/api/tasks/` — all Celery task files.

| File | Owns |
|------|------|
| `home_briefing_tasks.py` | Async LLM briefing generation + cache |
| `garmin_webhook_tasks.py` | Garmin webhook processing + `ActivitySplit` creation |
| `strava_tasks.py` | Strava activity ingestion |
| `intelligence_tasks.py` | Morning intelligence pipeline |
| `digest_tasks.py` | Weekly digest emails |
| `import_tasks.py` | Garmin file import (ZIP upload) |

Beat schedule: `apps/api/celerybeat_schedule.py`
- Morning intelligence: every 15 min, 24/7 (checks 5 AM local per athlete)
- Weekly digest: Monday 9 AM UTC
- Stale stream cleanup: every 5 min
- Home briefing refresh: scheduled (ADR-065)

### Alembic (migrations)
Current head: **`garmin_004`**
Migration files: `apps/api/alembic/versions/`

To create a new migration (run inside the container or with venv active):
```bash
docker exec strideiq_api alembic revision --autogenerate -m "describe_change"
docker exec strideiq_api alembic upgrade head
```
Never hand-edit the database schema directly. Always go through Alembic.

Naming convention for migration files: `<feature>_<NNN>_<description>.py`
Examples: `garmin_001_oauth_fields.py`, `sleep_quality_001_add_sleep_quality_to_checkin.py`

---

## 4. Tests

### How to run
```bash
# All tests (on droplet or with local Docker running)
docker exec strideiq_api pytest apps/api/tests/ -x -q

# Locally (if venv active and Postgres running)
cd apps/api
pytest tests/ -x -q

# Specific file
pytest tests/test_garmin_splits.py -v
```

### Key facts
- `tests/conftest.py` auto-runs Alembic migrations at session start. If Postgres is unreachable, pure-unit tests still run.
- Tests use **transactional rollback** — nothing written during tests persists.
- **119 xfail tests** (Phase 3B, 3C, 4, Monetization) — these are contract tests waiting for gates to clear. Do NOT delete them, do NOT convert them to skip.
- Test count baseline (Feb 13): 1,878 passing + 119 xfail. Any new code should add tests; do not ship features without them.

### Test files for recent features
- `test_sleep_prompt_grounding.py` — 22 tests, sleep grounding (commit `494b9e9`)
- `test_garmin_splits.py` — 17 tests, Garmin splits + GAP computation (commits `a058c8d`→`b58a0b3`)

---

## 5. Frontend — Next.js (`apps/web/`)

### App Router (Next.js 13+)
Pages live in `apps/web/app/` using the file-system router. Each route is a directory with `page.tsx` (and optionally `layout.tsx`).

Key routes:
```
app/
├── home/           ← athlete home page (coach briefing + morning voice)
├── activities/[id] ← activity detail page (splits table, stream analysis)
├── coach/          ← AI coach chat
├── settings/       ← integrations (Garmin Connect, Strava), profile
├── onboarding/     ← onboarding flow
├── plans/          ← training plans
├── privacy/        ← privacy policy
└── terms/          ← terms of service
```

### API communication
All API calls go through `apps/web/lib/api/`:
- `client.ts` — base `ApiClient` class, handles auth headers + error wrapping
- `config.ts` — `API_CONFIG` with base URL
- `services/*.ts` — one file per domain (e.g., `garmin.ts`, `home.ts`, `activities.ts`)

To add a new API call: add a method to the relevant service file. Do not call `fetch()` directly from components.

### Hooks
`apps/web/lib/hooks/` — React Query hooks. Follow the pattern in existing hooks (e.g., `useGarminStatus`, `useHomeData`).

### Components structure
```
components/
├── integrations/   ← Garmin Connect, Strava connection panels
├── home/           ← home page components
├── activities/     ← activity cards, splits table, stream charts
├── coach/          ← coach chat UI
├── ui/             ← shadcn/ui primitives (Button, Badge, etc.)
└── ...
```

### Garmin Connect naming rule (partner requirement)
All user-facing text must say **"Garmin Connect"** not "Garmin" alone. Code identifiers (variable names, function names, imports) are exempt. See commit `a6228f1`.

---

## 6. Docker — Local vs Production

| | Local (`docker-compose.yml`) | Production (`docker-compose.prod.yml`) |
|---|---|---|
| API container | `running_app_api` | `strideiq_api` |
| Web container | `running_app_web` | `strideiq_web` |
| Postgres | `running_app_postgres` | `strideiq_postgres` |
| Redis | `running_app_redis` | `strideiq_redis` |
| Worker | `running_app_worker` | `strideiq_worker` |
| Proxy | (none) | `strideiq_caddy` |

**Never mix them up.** `docker exec running_app_api ...` will fail on the droplet.

### Running scripts inside production container
If you need to run a Python diagnostic on production:
```bash
# Copy script to droplet
scp script.py root@strideiq.run:/tmp/script.py

# Copy into container (working dir must be /app for imports to work)
ssh root@strideiq.run "docker cp /tmp/script.py strideiq_api:/app/script.py"

# Execute with /app as working directory
ssh root@strideiq.run "docker exec -w /app strideiq_api python script.py"

# Clean up
ssh root@strideiq.run "rm /tmp/script.py && docker exec strideiq_api rm /app/script.py"
```
This pattern was battle-tested in the Garmin splits smoke test. The `-w /app` flag is required — without it, module imports fail.

---

## 7. Git Conventions

- **Scoped commits only.** Stage only files you touched. Never `git add -A`.
- **Commit message format:** `type(scope): description`
  - `feat(garmin): ...`, `fix(home): ...`, `docs: ...`, `test(splits): ...`
- **Never push to `main` without tests passing.**
- **One concern per commit.** Don't bundle a feature with an unrelated fix.

Pushing to production automatically happens via `git pull` in the deploy command — there is no CI/CD pipeline. Push to `main` = code is deployable; deploy command = code is live.

---

## 8. Production Deployment

```bash
# SSH in, pull, rebuild
ssh root@strideiq.run "cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build 2>&1 | tail -20"
```

Build takes ~3-5 minutes (Next.js compile is the slow part).

**Smoke check after deploy:**
```bash
ssh root@strideiq.run "curl -s -o /dev/null -w '%{http_code}' https://strideiq.run"
# Expect: 200
```

**If SSH fails with "host key changed":**
```bash
ssh-keygen -R strideiq.run
# Then retry
```

**Logs:**
```bash
ssh root@strideiq.run "docker logs strideiq_api --tail=50"
ssh root@strideiq.run "docker logs strideiq_web --tail=50"
ssh root@strideiq.run "docker logs strideiq_worker --tail=50"
```

---

## 9. Environment Variables

Secrets live in `.env` at the workspace root (gitignored). `.env.example` shows all keys with safe defaults.

Variables the build frequently references:

| Variable | Used by |
|----------|---------|
| `SECRET_KEY` | JWT signing |
| `TOKEN_ENCRYPTION_KEY` | OAuth token encryption at rest |
| `POSTGRES_*` | DB connection |
| `REDIS_URL` | Celery broker + cache |
| `STRAVA_CLIENT_ID/SECRET` | Strava OAuth |
| `GARMIN_CLIENT_ID/SECRET` | Garmin Connect OAuth |
| `STRIPE_SECRET_KEY` | Stripe API calls |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signature verification |
| `STRIPE_PRICE_PRO_MONTHLY_ID` | `price_1T4SUtLRj4KBJxHa4sq8e35A` |
| `STRIPE_PRICE_PRO_ANNUAL_ID` | `price_1T4SUuLRj4KBJxHat0sHVdrw` |
| `ANTHROPIC_API_KEY` | Claude (Opus) for coaching |
| `GOOGLE_AI_API_KEY` | Gemini Flash for narrations |

Do not log or print these values. Do not commit `.env`.

---

## 10. Monetization (Stripe) — Current State

Stripe is live in production. Do not create new products, prices, or webhooks without founder sign-off.

| Item | Value |
|------|-------|
| Account | `acct_1T4SGOLRj4KBJxHa` |
| Product | `prod_U2XZC71b1B6nxX` (StrideIQ Pro) |
| Monthly price | `price_1T4SUtLRj4KBJxHa4sq8e35A` ($14.99/mo) |
| Annual price | `price_1T4SUuLRj4KBJxHat0sHVdrw` ($149.00/yr) |
| Webhook | `we_1T4StVLRj4KBJxHaMH3qURqm` → `/v1/billing/webhooks/stripe` |
| Customer portal | Configured in Stripe Dashboard |

The billing router is `apps/api/routers/billing.py`. Subscription state is mirrored in the `Subscription` table and `athlete.subscription_tier` (`"free"` or `"pro"`).

**Next build:** Monetization tier gating — 29 xfail contract tests are waiting. This is the revenue unlock. Start here.

---

## 11. The Things That Have Burned Builders Before

1. **`from database import get_db`** → deprecated, causes warnings. Use `from core.database import get_db`.

2. **`&&` in PowerShell** → silent parse error. Always use `;`.

3. **`docker exec strideiq_api python script.py` without `-w /app`** → `ModuleNotFoundError` because Python can't find the app modules. Always use `docker exec -w /app strideiq_api python script.py`.

4. **Staging a test file then using `git add -A`** → violates commit hygiene. Stage explicitly.

5. **Editing `alembic.ini` SQLAlchemy URL** → it's a dummy value intentionally; the real URL is injected via env at runtime. Do not "fix" it.

6. **`re.split(r"[.!?]")`** on text with decimal numbers → splits "7.5 hours" at the decimal. Use `re.split(r"(?<!\d)[.!?](?!\d)")` with the PCRE2 flag, or process sentence-by-sentence differently.

7. **Proposing anything already rejected in `docs/DESIGN_PHILOSOPHY_AND_SITE_ROADMAP.md`** → costs trust immediately. Read that doc before proposing UI changes.

8. **SSH host key mismatch** → if `ssh root@strideiq.run` fails with ECDSA warning, run `ssh-keygen -R strideiq.run` and retry.

9. **Patching the wrong module path in `unittest.mock.patch`** → patch where functions are *defined*, not where they're imported. E.g., patch `routers.home.generate_coach_home_briefing`, not `tasks.home_briefing_tasks.generate_coach_home_briefing`.

10. **Assuming `laps[]` field names from Garmin are stable** — the adapter is designed to degrade via samples. Do not hardcode field names without a live-capture verification.
