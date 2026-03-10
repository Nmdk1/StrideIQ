# Builder Note — Progress Page Pre-Warm on Login

**Date:** February 23, 2026  
**Priority:** SEV-2 (14-second cold-start on progress page)  
**Status:** Ready to implement  
**Advisor review:** Passed with corrections (applied below)

---

## Read order

1. `docs/FOUNDER_OPERATING_CONTRACT.md`
2. `apps/api/routers/auth.py` lines 234-312 (login endpoint)
3. `apps/api/tasks/home_briefing_tasks.py` lines 508-524 (`enqueue_briefing_refresh` — existing pre-warm pattern to replicate)
4. `apps/api/services/home_briefing_cache.py` lines 172-204 (`should_enqueue_refresh` / `set_enqueue_cooldown` — cooldown pattern to replicate)
5. `apps/api/services/coach_tools.py` (`build_athlete_brief` — already cached with 15 min TTL)
6. `apps/api/routers/progress.py` lines 572-680 (`_generate_progress_headline` — already has content-hash Redis cache)
7. This document

---

## Problem

After the performance/stability fixes, the progress page loads in under 100ms when caches are warm. But on **first load** (cold cache — e.g., after login, after cache expiry), it takes **14 seconds** because:

1. `build_athlete_brief` must compute from scratch (2-5s)
2. Two LLM calls (headline + cards) run via Gemini Flash (3-8s each, parallelized = 3-8s total)

Total cold-start: 5-13s + network overhead = 14s observed.

The home page already solves this with `enqueue_briefing_refresh` — a Celery task with cooldown + circuit-breaker that pre-generates the coach briefing so it's cached before the user sees the page. Progress needs the same pattern.

---

## Fix

### 1. Create a pre-warm Celery task with cooldown

**File:** `apps/api/tasks/progress_prewarm_tasks.py` (new file)

```python
"""Pre-warm progress page caches so first load is fast."""
import logging
from core.cache import get_redis_client
from tasks import celery_app
from core.database import get_db_sync

logger = logging.getLogger(__name__)

PREWARM_COOLDOWN_S = 120  # At most one prewarm per athlete per 2 minutes


def _cooldown_key(athlete_id: str) -> str:
    return f"progress_prewarm_cooldown:{athlete_id}"


def should_enqueue_prewarm(athlete_id: str) -> bool:
    """Check cooldown before enqueueing. Returns True if allowed."""
    r = get_redis_client()
    if not r:
        return False
    try:
        if r.exists(_cooldown_key(athlete_id)):
            logger.debug("progress_prewarm skipped (cooldown): %s", athlete_id)
            return False
        return True
    except Exception as e:
        logger.warning("progress_prewarm cooldown check error for %s: %s", athlete_id, e)
        return False


def set_prewarm_cooldown(athlete_id: str) -> None:
    """Mark that a prewarm was enqueued. Prevents rapid re-enqueue."""
    r = get_redis_client()
    if not r:
        return
    try:
        r.setex(_cooldown_key(athlete_id), PREWARM_COOLDOWN_S, "1")
    except Exception as e:
        logger.warning("progress_prewarm cooldown set error for %s: %s", athlete_id, e)


def enqueue_progress_prewarm(athlete_id: str) -> bool:
    """
    Fire-and-forget enqueue for progress pre-warm.
    Respects cooldown. Returns True if enqueued, False if skipped.
    """
    if not should_enqueue_prewarm(athlete_id):
        return False
    set_prewarm_cooldown(athlete_id)
    prewarm_progress_cache_task.delay(athlete_id)
    logger.info("progress_prewarm enqueued for %s", athlete_id)
    return True


@celery_app.task(name="tasks.prewarm_progress_cache", bind=True, max_retries=0)
def prewarm_progress_cache_task(self, athlete_id: str):
    """
    Pre-compute and cache the expensive parts of the progress page:
    1. build_athlete_brief (15 min TTL)
    2. calculate_training_load (5 min TTL)

    Fire-and-forget from login endpoint via enqueue_progress_prewarm().
    """
    db = get_db_sync()
    try:
        from uuid import UUID
        from models import Athlete
        from services.coach_tools import build_athlete_brief
        from services.training_load import TrainingLoadCalculator

        athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            logger.info("progress_prewarm skipped (athlete not found): %s", athlete_id)
            return {"status": "skipped", "reason": "athlete_not_found"}

        brief_ok, load_ok = False, False

        try:
            build_athlete_brief(db, UUID(athlete_id))
            brief_ok = True
        except Exception as e:
            logger.warning("progress_prewarm athlete_brief failed for %s: %s", athlete_id, e)

        try:
            calc = TrainingLoadCalculator(db)
            calc.calculate_training_load(UUID(athlete_id))
            load_ok = True
        except Exception as e:
            logger.warning("progress_prewarm training_load failed for %s: %s", athlete_id, e)

        logger.info(
            "progress_prewarm completed for %s: brief=%s load=%s",
            athlete_id, brief_ok, load_ok
        )
        return {"status": "ok", "brief": brief_ok, "load": load_ok}
    except Exception as e:
        logger.warning("progress_prewarm failed for %s: %s", athlete_id, e)
        return {"status": "error", "error": str(e)}
    finally:
        db.close()
```

**Why not pre-warm the LLM calls too?** The headline/cards use a content-hash cache key that depends on the full `ProgressSummary` object (CTL, TSB, efficiency trend, etc.). To pre-generate them, we'd need to run the entire progress endpoint logic in the worker. That's too complex for a pre-warm task. Instead, caching `athlete_brief` and `training_load` eliminates 3-7s of the cold-start. The remaining LLM time (3-8s parallelized) is the irreducible minimum for AI-generated content on first load.

### 2. Register the task module

**File:** `apps/api/tasks/__init__.py`

Add after the existing task imports:

```python
from . import progress_prewarm_tasks  # noqa: E402
```

### 3. Fire the pre-warm on login (single trigger point)

**File:** `apps/api/routers/auth.py` (after line 298, after `create_access_token`, before the return statement)

```python
    try:
        from tasks.progress_prewarm_tasks import enqueue_progress_prewarm
        enqueue_progress_prewarm(str(user.id))
    except Exception as e:
        logger.warning("progress prewarm enqueue failed (non-blocking): %s", e)
```

**Important:** Login-only for now. Do NOT add a second trigger on home page load until we verify the cooldown works correctly in production. The home briefing enqueue already fires on home load — adding another task enqueue without verified throttle risks queue churn on a 1-worker machine.

---

## Expected impact (target, requires measured verification)

- `build_athlete_brief` (2-5s) — target: already cached by the time user clicks Progress
- `calculate_training_load` (500ms-2s) — target: already cached
- Remaining cold-start: LLM headline + cards (~3-8s parallelized, then cached)
- **Progress first-load target: 14s → 3-8s** (LLM-bound, irreducible without faster model or pre-rendering the full summary)
- **Progress subsequent loads: under 100ms** (unchanged)
- Requires before/after measurement on production to confirm

---

## What NOT to touch

- Do not modify the progress endpoint itself
- Do not modify cache TTLs or invalidation
- Do not add any new dependencies
- Do not add a second trigger (home page) until login trigger is verified
- Scoped commits only

---

## Testing (required before merge)

### Unit tests — `apps/api/tests/test_progress_prewarm.py` (new file)

1. **Task is registered and callable** — import `prewarm_progress_cache_task`, assert it has a `.delay` method and `name == "tasks.prewarm_progress_cache"`
2. **Enqueue is fire-and-forget and non-blocking** — call `enqueue_progress_prewarm` with a mocked task `.delay`; assert it returns True and `.delay` was called with the athlete ID
3. **Cooldown prevents duplicate enqueue (deterministic)** — mock `get_redis_client()` with a fake Redis object (or `fakeredis`) so first call has no cooldown key and second call does; assert first enqueue returns True, second returns False
4. **Athlete-not-found returns skipped** — call `prewarm_progress_cache_task.run()` with a non-existent athlete ID; assert return value `status == "skipped"`
5. **Login response unchanged when enqueue throws** — patch `enqueue_progress_prewarm` to raise; POST to `/login` with valid creds; assert 200 with valid token

### Production verification

6. After deploy, login and check worker logs: `progress_prewarm enqueued for ...` then `progress_prewarm completed for ... brief=True load=True`
7. Navigate to progress page — first load should be noticeably faster than 14s baseline
8. Record actual cold-start timing and report

---

## Commit message

`perf: pre-warm progress page caches on login with cooldown throttle`
