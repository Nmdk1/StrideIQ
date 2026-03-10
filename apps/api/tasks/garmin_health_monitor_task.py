"""
Garmin Ingestion Health Monitor — Celery Beat Task

Runs once daily (configured in celerybeat_schedule.py).
Computes GarminDay coverage for all Garmin-connected athletes and emits
structured warning logs for any athlete below the 50% threshold for
sleep or HRV data.

No writes.  No Garmin API calls.  Read-only monitoring only.
"""

import logging

from tasks import celery_app
from core.database import get_db_sync

logger = logging.getLogger(__name__)


@celery_app.task(
    name="tasks.check_garmin_ingestion_health",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def check_garmin_ingestion_health(self) -> dict:
    """
    Daily health check: compute GarminDay coverage for all connected Garmin
    athletes and log underfed cases.

    Returns:
        {"status": "ok", "total": int, "underfed": int}
    """
    db = get_db_sync()
    try:
        from services.garmin_ingestion_health import (
            compute_garmin_coverage,
            emit_health_log_lines,
        )

        coverage = compute_garmin_coverage(db)
        emit_health_log_lines(coverage)

        total = coverage["total_connected_garmin_athletes"]
        underfed = coverage["athletes_below_threshold_count"]

        logger.info(
            "[garmin-health] daily check complete — total=%d underfed=%d",
            total,
            underfed,
        )
        return {"status": "ok", "total": total, "underfed": underfed}

    except Exception as exc:
        logger.exception(
            "check_garmin_ingestion_health failed: %s", exc
        )
        raise self.retry(exc=exc)
    finally:
        db.close()
