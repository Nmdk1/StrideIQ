# Builder Note — Performance & Stability Fixes

**Date:** February 23, 2026  
**Priority:** SEV-1 (API outage prevention) + SEV-2 (page load times)  
**Status:** Codex-reviewed and approved (3 rounds, 12 findings resolved)  
**Full spec:** `docs/CODEX_REVIEW_2026-02-23_PERFORMANCE_STABILITY.md`

---

## Read order

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/CODEX_REVIEW_2026-02-23_PERFORMANCE_STABILITY.md` (the full spec — this note is a summary)
3. `apps/api/core/cache.py` (existing Redis pool + invalidation infrastructure — you MUST use this)
4. `apps/api/core/database.py` (session factory — thread safety constraints)

---

## Why this matters

Feb 22: Garmin backfill dumped 30 activity webhooks. Worker saturated DB/Redis. API became unresponsive — users couldn't log in. Founder had to manually restart containers.

Additionally:
- `/v1/progress` takes **20+ seconds**
- `/v1/home` takes **10+ seconds**
- Target: **every page under 4 seconds**

---

## Execution order — MUST follow this sequence

### Step 0: Baseline instrumentation (read-only)

On the droplet, capture current response times before any code changes. Script is in the full spec (section "Instrumentation"). Save the output — we compare after each phase.

### Step 1: Phase 1 — Stability guardrails (isolated commit)

**Files to modify:**

1. **`apps/api/main.py`** — Add `/ping` (liveness, no DB) and `/health` (readiness, DB+Redis ping) endpoints
2. **`apps/api/core/rate_limit.py`** — Add `/ping` to the skip list on line 47
3. **`docker-compose.prod.yml`** — Add healthcheck to `api` service using `/ping`
4. **`apps/api/tasks/garmin_webhook_tasks.py`** — Add `rate_limit='6/m'` to `process_garmin_activity_task` decorator, `rate_limit='10/m'` to `process_garmin_health_task` decorator
5. **`apps/api/tasks/__init__.py`** — Add `worker_prefetch_multiplier=1` to `celery_app.conf.update()`, delete duplicate SEV-1 guardrail block (lines 71-99, exact copy of lines 37-65)

**Commit message:** `fix: add API healthcheck, Celery rate limits, and prefetch control`

Deploy and verify:
- `/ping` returns 200
- `/health` returns `{"status": "ok", "db": true, "redis": true}`
- No container restart flapping

### Step 2: Phase 2 — Progress page optimization (isolated commit)

**Files to modify:**

1. **`apps/api/core/cache.py`** — Extend `invalidate_athlete_cache()` patterns to include `athlete_brief:{athlete_id}`, `training_load:{athlete_id}:*`, `fitness_bank:{athlete_id}`, `correlations:{athlete_id}`
2. **`apps/api/services/coach_tools.py`** — Add Redis caching to `build_athlete_brief()` using `get_cache`/`set_cache` (15 min TTL)
3. **`apps/api/services/training_load.py`** — Add Redis caching to `calculate_training_load()` using `get_cache`/`set_cache` (5 min TTL, key includes `target_date`)
4. **`apps/api/routers/progress.py`** — Parallelize `_generate_progress_headline` and `_generate_progress_cards` using `asyncio.gather` + `asyncio.to_thread`. CRITICAL: prefetch all DB data FIRST (athlete brief, checkin context), then pass pre-fetched data to the thread workers. Do NOT pass `db` session to thread workers.
5. **`apps/api/routers/progress.py`** — Batch the two period comparison queries into one
6. **`apps/api/tasks/garmin_webhook_tasks.py`** — Add `invalidate_athlete_cache(str(athlete_id))` after `db.commit()` in `process_garmin_activity_task` (after line 500)
7. **`apps/api/services/strava_ingest.py`** — Add `invalidate_athlete_cache(str(athlete.id))` after `db.commit()` on lines 90 and 103
8. **`apps/api/routers/v1.py`** — Add `invalidate_athlete_cache(str(current_user.id))` after `db.commit()` in POST `/v1/activities` (after line 343)

**Commit message:** `perf: cache athlete brief + training load, parallelize progress LLM calls`

Deploy and measure progress endpoint response time. Target: under 6s on current hardware.

### Step 3: Phase 3 — Home page optimization (isolated commit)

**Files to modify:**

1. **`apps/api/services/fitness_bank.py`** — Add Redis caching to `FitnessBankCalculator.calculate()` (15 min TTL)
2. **`apps/api/services/correlation_engine.py`** — Add Redis caching to `analyze_correlations()` (15 min TTL)
3. **`apps/api/routers/home.py`** — Batch week progress from 14 queries to 2 (lines 1652-1722)
4. **`apps/api/routers/home.py`** — If time permits: parallelize `_build_rich_intelligence_context` sources using the DB-prefetch + parallel-compute pattern (see full spec section 3A). If time-constrained, caching alone (items 1-2) may be sufficient.

**Commit message:** `perf: cache fitness bank + correlations, batch week progress queries`

Deploy and measure home endpoint response time. Target: under 5s on current hardware.

### Step 4: Re-instrument

Run the same baseline script from Step 0. Compare before/after. Both endpoints must hit p95 ≤ 4s.

---

## Critical constraints (from Codex review)

1. **DO NOT use `asyncio.to_thread()` with shared SQLAlchemy sessions.** Prefetch all DB data first, then parallelize only non-DB operations (LLM calls, computations on pre-fetched data).
2. **DO NOT create per-call Redis clients.** Use `get_cache()`/`set_cache()` from `core/cache.py` which uses the singleton connection pool.
3. **Every new cache MUST have an invalidation path.** See Cache Correctness Contract in the full spec.
4. **The `/ping` endpoint must NOT hit the database.** It's used for Docker liveness — DB failures must not trigger container restarts.
5. **Rate limit values are validated.** `6/m` for activities, `10/m` for health. Queue drain SLO: 30 tasks in ≤10 min with mixed workload.

---

## What NOT to touch

- No changes to Garmin webhook/ingestion code (D4-D8 is complete)
- No changes to AI coach, narrative, or insight generation logic (only caching wrappers)
- No changes to data models or migrations
- No changes to frontend
- No changes to feature flags or rollout configuration
- Scoped commits only — never `git add -A`

---

## Testing

1. All existing tests must pass (`pytest` green)
2. `/ping` returns 200
3. `/health` returns 200 with `{"db": true, "redis": true}`
4. Progress endpoint responds under 6s (manual timing on droplet)
5. Home endpoint responds under 5s (manual timing on droplet)
6. Cache invalidation fires on activity create/update (verify with `redis-cli KEYS 'athlete_brief:*'` before/after a sync)
7. Rate-limited Garmin tasks still drain (no data loss)

---

## Acceptance gates

- `/v1/progress` p95 (worst of 10) ≤ 4s
- `/v1/home` p95 (worst of 10) ≤ 4s
- No API restart needed during webhook/backfill bursts
- No restart flapping during transient DB hiccups
- Queue drain SLO met: 30-activity burst drains within 10 minutes
- No stale data after new activity sync
- All existing tests remain green
