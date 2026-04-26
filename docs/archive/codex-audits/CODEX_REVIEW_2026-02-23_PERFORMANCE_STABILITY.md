# Codex Review — Performance & Stability Fixes (v2 — post-review)

**Date:** February 23, 2026  
**Reviewer:** Advisor (Opus)  
**Status:** REVISED — incorporates all Codex review findings  
**Branch:** `feature/garmin-oauth` (will merge to `main` after verification)

---

## Read order before implementation

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `docs/ADVISOR_NOTE_2026-02-22_GARMIN_CLOSEOUT.md`
3. `apps/api/core/cache.py` (existing Redis pool + invalidation infrastructure)
4. `apps/api/core/database.py` (session factory — thread safety constraints)
5. This document

---

## Context

Last night (Feb 22), Garmin backfill delivered ~30 activity webhooks simultaneously. The Celery worker queued all 30 as `process_garmin_activity_task` jobs. While the worker ground through them, Postgres/Redis were under sustained load, and the API became unresponsive — login requests timed out with "Request cancelled or timed out". The founder had to manually `docker restart strideiq_api` to restore service.

Additionally, page load times are unacceptable:
- `/v1/progress` — **20+ seconds** (founder-measured)
- `/v1/home` — **10+ seconds** (founder-measured)
- Target: **every page under 4 seconds**

Root causes identified via code profiling:

1. **No stability guardrails** — no API healthcheck, no task rate limits, no prefetch control
2. **All endpoint computation is serial** — zero parallelization
3. **Redundant work** — `build_athlete_brief` called twice per progress load, training load calculated 3+ times per request
4. **Missing caching** — expensive computations recalculated on every request despite existing `core/cache.py` infrastructure

---

## Codex Review Findings — all addressed

### Round 1 (Feb 23)

| # | Severity | Finding | Resolution |
|---|----------|---------|------------|
| 1 | HIGH | `asyncio.to_thread()` unsafe with shared SQLAlchemy sessions | **Fixed:** DB-prefetch phase then parallel non-DB phase (see 2B, 3A) |
| 2 | HIGH | Per-call `redis.from_url()` creates connection churn | **Fixed:** Use existing `core/cache.py` singleton pool (`get_cache`/`set_cache`/`@cached`) |
| 3 | HIGH | Cache TTL without invalidation risks stale data | **Fixed:** Add invalidation hooks on activity ingest + sync events (see Cache Contract) |
| 4 | MED | Healthcheck may cause restart flapping on DB hiccups | **Fixed:** Liveness probe (`/ping`, process-only) for restart; readiness probe (`/health`, DB+Redis-backed) for monitoring |
| 5 | MED | Rate-limit values arbitrary without queue drain math | **Fixed:** Drain SLO documented (see 1C) |
| 6 | MED | `/health` rate-limit exclusion not verified | **Verified:** `core/rate_limit.py` line 47 already excludes `/health` |
| 7 | LOW | Duplicate SEV-1 guard block removal safety | **Verified:** Lines 71-99 are exact duplicate; no startup-order dependency |

### Round 2 (Feb 23)

| # | Severity | Finding | Resolution |
|---|----------|---------|------------|
| 8 | HIGH | `training_load` cache key too coarse — missing `target_date` param | **Fixed:** Key now `training_load:{athlete_id}:{target_date}` (see 2C) |
| 9 | HIGH | Queue drain SLO ignores `post_sync_processing` contention in solo pool | **Fixed:** Realistic worst-case adjusted to 7-10 min; SLO gate set at 10 min (see 1C) |
| 10 | MED | Invalidation only covers Garmin + Strava, misses manual activity creation | **Fixed:** Added `routers/v1.py` POST `/v1/activities` as third write path; audited all `Activity()` constructors in production code (see Cache Contract) |
| 11 | MED | Readiness probe `redis_ok` checks client existence, not reachability | **Fixed:** Now calls `redis_client.ping()` with exception handling (see 1B) |
| 12 | MED | p95 measurement from 3 curl runs is statistically insufficient | **Fixed:** 10 sequential requests per endpoint; p95 = worst of 10; limitations acknowledged (see Instrumentation) |

---

## Phase 1: Stability Guardrails (prevents outages)

Ship Phase 1 as an isolated commit before any endpoint optimization.

### 1A. API Docker healthcheck — liveness/readiness split

**File:** `docker-compose.prod.yml` (line 45-67, `api` service)

Use a **liveness probe** (process-alive check) for Docker restart policy. This avoids restart flapping during transient DB hiccups:

```yaml
  api:
    # ... existing config ...
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/ping')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 45s
```

The `/ping` endpoint (see 1B) does NOT hit the database. Docker only restarts on sustained API process failure, not transient DB blips.

### 1B. Health endpoints — split liveness and readiness

**File:** `apps/api/main.py`

Two endpoints:

```python
@app.get("/ping")
async def ping():
    """Liveness probe — confirms API process is alive. No DB, no auth, no rate limit."""
    return {"status": "alive"}

@app.get("/health")
async def health():
    """Readiness probe — confirms API can serve requests (DB + Redis reachable)."""
    try:
        from core.database import check_db_connection
        db_ok = check_db_connection()
        redis_client = get_redis_client()
        redis_ok = False
        if redis_client is not None:
            try:
                redis_ok = redis_client.ping()
            except Exception:
                redis_ok = False
        status = "ok" if (db_ok and redis_ok) else "degraded"
        return {"status": status, "db": db_ok, "redis": redis_ok}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unhealthy"})
```

Rate-limit exclusion is already handled — `core/rate_limit.py` line 47 skips `/health` and `/ping` can be added to that same list. No auth dependency.

### 1C. Celery task rate limits — with queue drain SLO

**File:** `apps/api/tasks/garmin_webhook_tasks.py`

**Queue drain math:**
- Worst-case burst: 30 activities from backfill (observed Feb 22)
- `rate_limit='6/m'` → 30 Garmin activity tasks drain in **5 minutes** (isolated)
- **Mixed workload adjustment:** Worker runs `--pool=solo`, so `post_sync_processing` jobs (Strava, 30-60s each) share the same queue. If 5 Strava sync jobs are queued, add ~2.5-5 minutes of contention. Realistic worst-case drain for 30 Garmin activities: **7-10 minutes**.
- Acceptable: athlete sees backfilled runs within 10-15 minutes, not hours. This is a background backfill — the athlete doesn't see a spinner.
- Health records are lighter; `10/m` → 30 health items drain in **3 minutes** (isolated), **5-7 minutes** with mixed contention.

```python
# Line 439 — process_garmin_activity_task
@celery_app.task(
    name="process_garmin_activity_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    rate_limit='6/m',
)

# Line 646 — process_garmin_health_task
@celery_app.task(
    name="process_garmin_health_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    rate_limit='10/m',
)
```

**Queue SLO:** 30-activity backfill burst drains within 10 minutes (mixed workload with `post_sync_processing` contention). No data loss — tasks queue in Redis and drain naturally. Worker `--pool=solo` means these rate limits effectively cap DB pressure from Garmin tasks.

### 1D. Celery prefetch control

**File:** `apps/api/tasks/__init__.py` (line 18-27, `celery_app.conf.update`)

Add to the existing `conf.update()` block:

```python
worker_prefetch_multiplier=1,
```

With `--pool=solo`, this ensures the worker only grabs one task at a time from Redis.

### 1E. Duplicate SEV-1 guardrail block

**File:** `apps/api/tasks/__init__.py` (lines 71-99)

**Verified safe to delete.** Lines 71-99 are an exact character-for-character duplicate of lines 37-65. The `garmin_webhook_tasks` import on line 69 does not depend on the second block. Both blocks import the same symbols from `routers.home` and perform the same `callable()` checks. There is no startup-order dependency — the first block executes before line 69 and is sufficient.

Delete lines 71-99.

---

## Cache Correctness Contract (applies to all Phase 2/3 caches)

**Existing infrastructure:** `apps/api/core/cache.py` provides:
- `get_redis_client()` — singleton connection pool (NOT per-call instantiation)
- `get_cache(key)` / `set_cache(key, value, ttl)` — with graceful degradation
- `cache_key(prefix, *args, **kwargs)` — consistent key generation
- `@cached(prefix, ttl)` — decorator for simple function caching
- `invalidate_athlete_cache(athlete_id)` — pattern-based invalidation
- `invalidate_activity_cache(athlete_id)` — activity-specific invalidation

**All new caches MUST use this existing infrastructure.** No per-call `redis.from_url()`.

### Cache key schemas

| Cache | Key pattern | TTL | Invalidation trigger |
|-------|-------------|-----|---------------------|
| `athlete_brief` | `athlete_brief:{athlete_id}` | 15 min | Activity create/update, sync completion |
| `training_load` | `training_load:{athlete_id}:{target_date}` | 5 min | Activity create/update |
| `fitness_bank` | `fitness_bank:{athlete_id}` | 15 min | Activity create/update |
| `correlations` | `correlations:{athlete_id}` | 15 min | Activity create/update |

### Invalidation hooks

**File:** `apps/api/core/cache.py`

Extend `invalidate_athlete_cache()` to include the new cache key patterns:

```python
def invalidate_athlete_cache(athlete_id: str):
    patterns = [
        # ... existing patterns ...
        f"athlete_brief:{athlete_id}",
        f"training_load:{athlete_id}:*",
        f"fitness_bank:{athlete_id}",
        f"correlations:{athlete_id}",
    ]
```

**Call sites for invalidation (ALL activity-write paths):**

1. `apps/api/tasks/garmin_webhook_tasks.py` — after `db.commit()` in `process_garmin_activity_task` (line 500)
2. `apps/api/services/strava_ingest.py` — after `db.commit()` following activity create/update (line 90, 103)
3. `apps/api/routers/v1.py` — after `db.commit()` in `POST /v1/activities` manual creation endpoint (line 343)

```python
from core.cache import invalidate_athlete_cache
# After db.commit() for new/updated activity:
invalidate_athlete_cache(str(athlete_id))
```

**Audit notes:**
- `strava_ingest.py` is the primary Strava activity write path (called by `strava_tasks.py`)
- `v1.py` POST `/v1/activities` handles manual activity creation
- `garmin_webhook_tasks.py` handles Garmin activity ingestion
- No other production code paths create `Activity()` rows (remaining `Activity()` references are in test files and `provision_demo_athlete.py` script)
- Nutrition/body composition mutations already call `invalidate_athlete_cache` (see `routers/nutrition.py`, `routers/body_composition.py`)

**Stale fallback behavior:** All caches use `get_cache()` which returns `None` on miss. If cache is stale, next request after invalidation simply recomputes. No stale data served after an activity ingest because invalidation fires on commit.

---

## Phase 2: Progress Page (20s → under 4s)

**File:** `apps/api/routers/progress.py`  
**Endpoint:** `GET /v1/progress` (line 180, `get_progress_summary`)

### 2A. Cache `build_athlete_brief` — biggest single win

**File:** `apps/api/services/coach_tools.py` (function `build_athlete_brief`, ~line 3315)

`build_athlete_brief` is called **twice** per progress page load. Each call takes 2-5s.

**Fix:** Use existing `core/cache.py` infrastructure:

```python
from core.cache import get_cache, set_cache

def build_athlete_brief(athlete_id, db, ...):
    cache_key = f"athlete_brief:{athlete_id}"
    cached = get_cache(cache_key)
    if cached is not None:
        return cached

    # ... existing brief building logic ...

    set_cache(cache_key, brief, ttl=900)  # 15 min
    return brief
```

**Expected savings:** 2-5s per request (eliminates duplicate call; on cache hit eliminates both).

### 2B. Parallelize headline and cards LLM calls — SAFE PATTERN

**File:** `apps/api/routers/progress.py`

**Codex finding:** `asyncio.to_thread()` is unsafe with shared SQLAlchemy sessions.

**Safe pattern:** DB-prefetch phase (single thread, shared session) → parallel non-DB phase (LLM calls only, no DB access).

```python
# Phase 1: Prefetch all DB data in the request thread (thread-safe)
athlete_brief = build_athlete_brief(athlete_id, db, ...)  # cached, see 2A
checkin_context = _latest_checkin_context(db, athlete_id)  # fast DB query

# Phase 2: Parallel LLM calls — NO DB ACCESS in these functions
# Both _generate_progress_headline and _generate_progress_cards
# receive pre-fetched data and only make external HTTP calls to Gemini.
headline_result, cards_result = await asyncio.gather(
    asyncio.to_thread(_generate_progress_headline, athlete_brief, checkin_context),
    asyncio.to_thread(_generate_progress_cards, athlete_brief, checkin_context),
)
```

**Requirement:** Verify that `_generate_progress_headline` and `_generate_progress_cards` do NOT accept or use a `db` session parameter. If they do, refactor to accept pre-fetched data only. The LLM call functions should receive the brief dict and make Gemini API calls — no DB access.

**Expected savings:** 3-8s (LLM calls run in parallel).

### 2C. Cache training load calculation

**File:** `apps/api/services/training_load.py` (function `calculate_training_load`, ~line 461)

Training load is calculated 3+ times per progress request.

**Fix:** Use `core/cache.py`:

```python
from core.cache import get_cache, set_cache

def calculate_training_load(self, athlete_id, target_date=None, ...):
    if target_date is None:
        target_date = date.today()
    cache_key = f"training_load:{athlete_id}:{target_date.isoformat()}"
    cached = get_cache(cache_key)
    if cached is not None:
        return TrainingLoad(**cached)

    # ... existing calculation ...

    set_cache(cache_key, asdict(result), ttl=300)  # 5 min
    return result
```

`target_date` is included in the key because the function accepts it as a parameter (defaults to `date.today()`). Most callers omit it, so in practice the key is date-scoped to today and cache hits are frequent. Different date ranges produce different keys — no cross-range pollution.

**Expected savings:** 1-2s per request.

### 2D. Batch period comparison queries

**File:** `apps/api/routers/progress.py` (~lines 238-285)

Two sequential DB queries (current period + previous period) → one query with date-range filter.

**Expected savings:** 200-500ms.

---

## Phase 3: Home Page (10s → under 4s)

**File:** `apps/api/routers/home.py`  
**Endpoint:** `GET /v1/home`

### 3A. Parallelize independent intelligence context sources — SAFE PATTERN

**File:** `apps/api/routers/home.py` (~lines 1186-1274, `_build_rich_intelligence_context`)

**Codex finding:** Do not pass shared `db` session to thread workers.

**Safe pattern:** Prefetch DB data, then parallelize only compute/aggregation functions that operate on pre-fetched data:

```python
# Phase 1: Prefetch all raw data needed by the 5 sources (single thread, shared session)
activities_90d = db.query(Activity).filter(...).all()
checkins_28d = db.query(DailyCheckin).filter(...).all()
personal_bests = db.query(PersonalBest).filter(...).all()
# ... etc.

# Phase 2: Parallel compute on pre-fetched data (no DB access)
n1, daily_intel, wellness, pb, period = await asyncio.gather(
    asyncio.to_thread(compute_n1_insights, activities_90d, checkins_28d),
    asyncio.to_thread(evaluate_daily_rules, activities_90d, checkins_28d),
    asyncio.to_thread(aggregate_wellness_trends, checkins_28d),
    asyncio.to_thread(analyze_pb_patterns, personal_bests, activities_90d),
    asyncio.to_thread(compare_training_periods, activities_90d),
)
```

**Implementation note:** The 5 source functions currently accept `db` and query internally. They need to be refactored into two layers:
1. Data-fetch layer (uses `db`, runs in request thread)
2. Compute layer (operates on dicts/lists, safe to parallelize)

This refactoring is the largest single change in Phase 3. If time-constrained, caching alone (3C) may be sufficient for the first pass.

**Expected savings:** 3-6s.

### 3B. Batch week progress queries

**File:** `apps/api/routers/home.py` (~lines 1652-1722)

Replace 14 sequential queries with 2 batch queries + Python-side partitioning.

**Expected savings:** 200-400ms.

### 3C. Cache fitness bank and correlation engine

**Files:**
- `apps/api/services/fitness_bank.py` (~line 244, `FitnessBankCalculator.calculate`)
- `apps/api/services/correlation_engine.py` (~line 1084, `analyze_correlations`)

**Fix:** Use `core/cache.py` `get_cache`/`set_cache` with 15-minute TTL. Same pattern as 2A/2C.

Invalidation handled by `invalidate_athlete_cache()` (see Cache Contract above).

**Expected savings:** 2-4s per request after first load.

---

## Instrumentation (before/after baseline)

Before any code changes, capture baseline metrics on the current droplet.

**Method:** 10 sequential requests per endpoint, cold start (first) + warm (remaining 9). Record all 10 response times. p50 = median of 10, p95 = worst of 10. Not a load test, but sufficient for single-user latency gating on a 2-user product.

```bash
# On droplet — generate token first
TOKEN=$(docker exec strideiq_api python -c "
from core.security import create_access_token
from database import SessionLocal
from models import Athlete
db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
print(create_access_token(data={'sub': str(user.id), 'email': user.email, 'role': user.role}))
db.close()
")

# Run 10 requests per endpoint, capture response times
for i in $(seq 1 10); do
  curl -s -o /dev/null -w "%{time_total}\n" -H "Authorization: Bearer $TOKEN" https://strideiq.run/v1/home
done > /tmp/home_baseline.txt

for i in $(seq 1 10); do
  curl -s -o /dev/null -w "%{time_total}\n" -H "Authorization: Bearer $TOKEN" https://strideiq.run/v1/progress
done > /tmp/progress_baseline.txt

# Sort and extract p50 (line 5) and p95 (line 10, worst)
echo "=== HOME ===" && sort -n /tmp/home_baseline.txt && echo "=== PROGRESS ===" && sort -n /tmp/progress_baseline.txt
```

After each phase deployment, repeat with the same script and compare. Acceptance: p95 (worst of 10) must be ≤ 4s for both endpoints.

**Limitations acknowledged:** 10 samples is not rigorous statistical profiling. For a 2-user product at this stage, it establishes a directional baseline. If the product scales to >50 users, invest in proper APM (Sentry performance, or Prometheus + response time histograms).

---

## Files to modify (complete list)

| File | Changes |
|------|---------|
| `docker-compose.prod.yml` | Add API liveness healthcheck (1A) |
| `apps/api/main.py` | Add `/ping` + `/health` endpoints (1B) |
| `apps/api/tasks/garmin_webhook_tasks.py` | Add `rate_limit` to activity + health tasks (1C) |
| `apps/api/tasks/__init__.py` | Add `worker_prefetch_multiplier=1` (1D), delete duplicate guardrail lines 71-99 (1E) |
| `apps/api/core/cache.py` | Extend `invalidate_athlete_cache` with new key patterns (Cache Contract) |
| `apps/api/services/coach_tools.py` | Cache `build_athlete_brief` via `core/cache` (2A) |
| `apps/api/routers/progress.py` | Parallelize LLM calls after DB prefetch (2B), batch period comparison (2D) |
| `apps/api/services/training_load.py` | Cache `calculate_training_load` via `core/cache` (2C) |
| `apps/api/routers/home.py` | Parallelize context sources after DB prefetch (3A), batch week progress (3B) |
| `apps/api/services/fitness_bank.py` | Cache `FitnessBankCalculator.calculate` via `core/cache` (3C) |
| `apps/api/services/correlation_engine.py` | Cache `analyze_correlations` via `core/cache` (3C) |
| `apps/api/core/rate_limit.py` | Add `/ping` to skip list (line 47) |

---

## What NOT to touch

- No changes to Garmin webhook/ingestion code (D4-D8 is complete)
- No changes to AI coach, narrative, or insight generation logic (only caching wrappers + parallelization of external calls)
- No changes to data models or migrations
- No changes to frontend
- No changes to feature flags or rollout configuration
- Scoped commits only — never `git add -A`

---

## Execution order

1. **Instrument baseline** (read-only, no code changes)
2. **Phase 1 commit** — stability guardrails, deploy, verify no flapping
3. **Phase 2 commit** — progress page caching + LLM parallelization, deploy, measure
4. **Phase 3 commit** — home page caching + batch queries, deploy, measure
5. **Re-instrument** — capture after metrics, compare to baseline

---

## Testing requirements

1. All existing tests must pass (`pytest` green)
2. Verify `/ping` returns 200 (liveness)
3. Verify `/health` returns 200 with `{"db": true, "redis": true}` (readiness)
4. Verify progress endpoint responds under 6s on current hardware (manual timing)
5. Verify home endpoint responds under 5s on current hardware (manual timing)
6. Verify cached values expire correctly (TTLs)
7. Verify cache invalidation fires on activity create/update (check Redis keys cleared)
8. Verify rate-limited Garmin tasks still drain within SLO (30 tasks in ≤10 min, mixed workload)

---

## Acceptance gates

- [ ] `/v1/progress` p95 (worst of 10) ≤ 4s
- [ ] `/v1/home` p95 (worst of 10) ≤ 4s
- [ ] No API restart needed during webhook/backfill bursts — liveness probe handles it
- [ ] No restart flapping during transient DB hiccups — liveness probe (`/ping`) is DB-independent
- [ ] Queue drain SLO met: 30-activity burst drains within 10 minutes (mixed workload)
- [ ] No stale-athlete-view after new activity sync — verify cache invalidation fires on all 3 write paths (Garmin ingest, Strava ingest, manual create)
- [ ] All existing tests remain green
