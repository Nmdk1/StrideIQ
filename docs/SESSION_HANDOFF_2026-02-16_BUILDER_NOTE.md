# Builder Note - 2026-02-16

## Read First (in this order)

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/TRAINING_PLAN_REBUILD_PLAN.md`
3. `docs/AGENT_WORKFLOW.md`
4. `docs/SESSION_HANDOFF_2026-02-16.md`
5. `docs/SESSION_HANDOFF_2026-02-14.md`

---

## Current State

- **Branch:** `main`
- **HEAD:** `f26a989`
- **Tree:** clean
- **Production:** deployed and healthy on `strideiq.run`
- **Recent shipping commits:**
  - `2915476` frontend lint/CI fix
  - `f26a989` correlation specificity alignment

---

## What Just Shipped

### 1) CI blocker removed (frontend)

- File: `apps/web/lib/hooks/queries/home.ts`
- Replaced `any` cache updater with typed `HomeData | undefined` updater.
- Removed brittle eslint suppression line.
- CI frontend lint/build now passes for that change set.

### 2) Correlation messaging specificity aligned

- Files:
  - `apps/api/services/daily_intelligence.py`
  - `apps/api/routers/home.py`
  - `apps/api/tests/test_daily_intelligence_correlation_confirmed.py`
  - `apps/api/tests/test_home_api.py`
- Added explicit lag phrasing + confirmation count + `r=` evidence anchors in
  surfaced language.

### 3) Production deploy stabilized

- Build + container recreation succeeded.
- Migration hiccup (`corr_persist_001` duplicate object) resolved by stamping
  migration revision and re-running upgrade.
- Final production checks returned healthy API + valid domain routing.

---

## Known Operational Caveat

`docker-compose.prod.yml` defaults Postgres user to `postgres` unless `.env`
overrides it. Do not assume `strideiq` as DB role during manual psql checks.

---

## If You Need To Deploy Again

```bash
cd /opt/strideiq/repo
git fetch origin
git checkout main
git pull --ff-only origin main
docker compose -f docker-compose.prod.yml build api web
docker compose -f docker-compose.prod.yml up -d api web --remove-orphans
```

If migration fails on `corr_persist_001` with duplicate table/type:

```bash
docker compose -f docker-compose.prod.yml exec api alembic current
docker compose -f docker-compose.prod.yml exec api alembic heads
docker compose -f docker-compose.prod.yml exec api alembic stamp corr_persist_001
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
```

---

## Next Priority (Do Not Reorder)

From `docs/TRAINING_PLAN_REBUILD_PLAN.md`:

1. Monetization tier mapping
2. Phase 4 (50K Ultra)
3. Phase 3B rollout only when narration-quality gate clears
4. Phase 3C rollout by data/stat gate

Gate monitoring:

- `/v1/intelligence/narration/quality` (3B)
- Synced history + significant correlations (3C)

---

## Note To The Next Agent

Start with trust and precision, not speed:

1. Read the docs above before touching code.
2. Confirm whether the founder wants discussion/planning or immediate build.
3. If building, define acceptance criteria and tests first.
4. Keep commits tightly scoped and CI-green.
5. For production support, give exact copy/paste commands and verify with logs.

Do not reopen completed debates from this session:

- CI lint root cause has been fixed and shipped.
- Correlation specificity wording alignment is shipped in API surfaces.
- Production is healthy after migration bookkeeping alignment.

