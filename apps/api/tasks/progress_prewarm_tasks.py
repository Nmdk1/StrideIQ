"""Pre-warm progress page caches so first load is fast.

On login, `enqueue_progress_prewarm` fires a background Celery task that
pre-populates:
  - build_athlete_brief (15 min TTL, 2-5s compute)
  - calculate_training_load (5 min TTL, 500ms-2s compute)

Both are already cached after Phase 2 perf work — this task seeds the cache
BEFORE the user touches the progress page, eliminating the cold-start penalty.

LLM calls (headline/cards) are NOT pre-warmed here — their cache key depends on
the full ProgressSummary object which requires running the entire endpoint.
The irreducible first-load LLM time is 3-8s (parallelized); subsequent loads
hit cache and return in under 100ms.
"""
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
