"""Celery wrapper around `services.sync.strava_fallback.repair_garmin_activity_from_strava`.

Lifecycle: `tasks.cleanup_stale_garmin_pending_streams` enqueues one of
these per fail-closed Garmin activity (see hook in `garmin_health_monitor_task.py`).

Kept as thin as possible -- this module exists so the Celery beat / queue
machinery never reaches into the service layer directly, and so the pure
service stays trivially unit-testable.
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from uuid import UUID

from tasks import celery_app
from core.database import get_db_sync

logger = logging.getLogger(__name__)


@celery_app.task(
    name="tasks.repair_garmin_activity_from_strava",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    autoretry_for=(),
)
def repair_garmin_activity_from_strava_task(
    self, activity_id: str
) -> Dict[str, Any]:
    """Run a single Garmin -> Strava repair attempt for `activity_id`.

    Returns the structured `RepairResult.to_dict()` so flower / logs
    show the outcome inline.  Does not raise on terminal soft-skips
    (no_match, no_strava, etc.) -- those are normal outcomes the worker
    records and walks away from.
    """
    from services.sync.strava_fallback import repair_garmin_activity_from_strava

    try:
        activity_uuid = UUID(activity_id)
    except (TypeError, ValueError):
        logger.error(
            "strava_fallback_invalid_activity_id activity_id=%s", activity_id
        )
        return {
            "status": "failed",
            "activity_id": str(activity_id),
            "error": "invalid_uuid",
        }

    db = get_db_sync()
    try:
        result = repair_garmin_activity_from_strava(activity_uuid, db)
        return result.to_dict()
    except Exception as exc:
        # Unexpected exception: let Celery retry (up to max_retries) and
        # the next cycle's claim will pick the row up if needed.
        logger.exception(
            "strava_fallback_task_unexpected_error activity_id=%s error=%s",
            activity_id,
            exc,
        )
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {
                "status": "failed",
                "activity_id": str(activity_id),
                "error": f"unhandled:{str(exc)[:200]}",
            }
    finally:
        db.close()
