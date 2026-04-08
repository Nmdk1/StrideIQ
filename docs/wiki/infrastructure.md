# Infrastructure

## Current State

Single Hostinger KVM 8 droplet (8 vCPU, 32GB RAM) running all services. Production IP: `187.124.67.153`. Domain: `strideiq.run`. Repo: `github.com/Nmdk1/StrideIQ`.

## Architecture

### Production Containers (`docker-compose.prod.yml`)

| Container | Role | Notes |
|-----------|------|-------|
| `strideiq_caddy` | TLS reverse proxy | Terminates HTTPS, routes to api/web |
| `strideiq_postgres` | PostgreSQL 16 (TimescaleDB) | Primary database |
| `strideiq_redis` | Redis | Cache + Celery broker |
| `strideiq_minio` | MinIO | S3-compatible object storage (Runtoons, exports) |
| `strideiq_api` | FastAPI | 4 Uvicorn workers, healthcheck `/ping` |
| `strideiq_worker` | Celery worker | Queues: `briefing_high`, `briefing` |
| `strideiq_worker_default` | Celery worker | Queue: `default` |
| `strideiq_beat` | Celery Beat | Task scheduler |
| `strideiq_web` | Next.js | Frontend behind Caddy |

### Hard Infrastructure Rules

- **Uvicorn workers: 1** (in dev; 4 in prod) — small droplet constraint
- **LLM hard timeouts** — never block indefinitely
- **`/v1/home` must not block on LLM** — Lane 2A architecture
- **No passing request-scoped SQLAlchemy `db` to `asyncio.to_thread`** — thread safety violation

### Database

- PostgreSQL 16 with TimescaleDB extension
- 95 Alembic migrations (as of Apr 2026)
- ~53 models in `models.py`
- Migration integrity: `.github/scripts/ci_alembic_heads_check.py` verifies single head + single root
- Expected migration heads: `EXPECTED_HEADS = {"wellness_stamp_001", "athlete_override_001"}`

### Celery & Task Scheduling

**Beat schedule:** Defined in `celerybeat_schedule.py`.

**Critical daily tasks:**
| Task | Schedule | Purpose |
|------|----------|---------|
| Auto-discovery nightly | 4 AM UTC | Correlation discovery |
| Morning intelligence | ~5 AM local | Readiness, intelligence rules, adaptation proposals |
| Fingerprint refresh | Nightly | Re-confirm findings |
| Correlation sweep | 8 AM UTC | Re-run correlations |

**Beat startup dispatch** (`tasks/beat_startup_dispatch.py`): On container start, checks if each daily task has run in the last 20 hours. If not, dispatches immediately. This is critical — the beat container is recreated on every deploy, and deploys happen before 4 AM, so without this pattern, daily tasks would never fire on their natural schedule.

**Short-interval tasks** (5min, 10min, 15min) work reliably because they fire within minutes of startup.

### Deployment

```bash
cd /opt/strideiq/repo && git pull origin main && docker compose -f docker-compose.prod.yml up -d --build
```

This single command pulls, rebuilds ALL containers (api, worker, beat, web), and restarts them with the new image. **Do not** use `docker restart` — it restarts containers with the old image, silently leaving worker/beat running stale code.

**CI must be green before deploy** — this is non-negotiable from the Operating Contract.

### CI Pipeline

Single workflow in `.github/workflows/ci.yml`:
- Backend: smoke tests + scheduled full suite, migration head check, lint
- Frontend: Jest + build + tsc + ESLint
- Security scan
- P0 plan registry gate (`ci_p0_registry_gate.py`)
- Docker build smoke
- Nightly: full test suite, issue reporting

### Caching

- **Redis:** Briefing cache (`home_briefing:{athlete_id}`), stream analysis cache, general cache
- **Model cache:** `services/model_cache.py` for LLM response caching

### Storage

- **MinIO** (`strideiq_minio`): S3-compatible object storage
- **`services/storage_service.py`**: Abstraction layer for R2/MinIO uploads (Runtoons, plan PDFs, exports)

### Environment Variables

Key env vars (from `.env.example`):
- `SECRET_KEY`, `TOKEN_ENCRYPTION_KEY`
- `DATABASE_URL`, `REDIS_URL`
- `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`
- `GARMIN_CONSUMER_KEY`, `GARMIN_CONSUMER_SECRET`
- `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_SUBSCRIBER_MONTHLY`, `STRIPE_PRICE_SUBSCRIBER_ANNUAL`
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_AI_API_KEY`, `MOONSHOT_API_KEY`
- `OWNER_ATHLETE_ID` — founder, bypasses all caps
- `COACH_VIP_ATHLETE_IDS` — comma-separated VIP UUIDs
- `SENTRY_DSN`

## Known Issues

- **Single server:** All services on one droplet. No horizontal scaling yet.
- **Beat container recreation:** Every deploy recreates beat. The startup dispatch pattern is the fix, but if it's removed, daily tasks break again.
- **Container name changes:** `docker compose up -d` can rename containers (e.g., `running_app_api` vs `strideiq_api`) depending on which compose file was used last. Workers may reference stale container names.

## Sources

- `docker-compose.yml` — dev stack
- `docker-compose.prod.yml` — production stack
- `docker-compose.test.yml` — test stack
- `.github/workflows/ci.yml` — CI pipeline
- `.env.example` — env var documentation
- `docs/SITE_AUDIT_LIVING.md` §9 — infrastructure rules
- `docs/OPS_PLAYBOOK.md` — operational procedures
