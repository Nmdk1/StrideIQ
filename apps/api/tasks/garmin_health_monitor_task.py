"""
Garmin Ingestion Health Monitor — Celery Beat Task

Runs once daily (configured in celerybeat_schedule.py).
Computes GarminDay coverage for all Garmin-connected athletes and emits
structured warning logs for any athlete below the 50% threshold for
sleep or HRV data.

No writes.  No Garmin API calls.  Read-only monitoring only.
"""

import logging

from sqlalchemy import text

from tasks import celery_app
from core.database import get_db_sync

logger = logging.getLogger(__name__)

GARMIN_STREAM_STALE_MINUTES = 30
GARMIN_STREAM_ALERT_THRESHOLD = 25


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
        from tasks.beat_startup_dispatch import record_task_run
        record_task_run("beat:last_run:garmin_ingestion_health")

        return {"status": "ok", "total": total, "underfed": underfed}

    except Exception as exc:
        logger.exception(
            "check_garmin_ingestion_health failed: %s", exc
        )
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    name="tasks.cleanup_stale_garmin_pending_streams",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def cleanup_stale_garmin_pending_streams(self) -> dict:
    """
    Auto-heal Garmin activities stuck in pending/fetching/failed with no stream row.

    These activities are push-driven (activity-details webhook). If that push never
    arrives, status can remain pending indefinitely and chart surfaces appear stuck.
    This task fail-closes stale rows to `unavailable` after a bounded window.
    """
    db = get_db_sync()
    try:
        updated_rows = db.execute(
            text(
                """
                UPDATE activity a
                SET stream_fetch_status = 'unavailable',
                    stream_fetch_error = COALESCE(
                        NULLIF(a.stream_fetch_error, ''),
                        :error_marker
                    )
                WHERE a.provider = 'garmin'
                  AND a.stream_fetch_status IN ('pending', 'fetching', 'failed')
                  AND a.start_time < (NOW() - (:stale_minutes || ' minutes')::interval)
                  AND NOT EXISTS (
                      SELECT 1
                      FROM activity_stream s
                      WHERE s.activity_id = a.id
                  )
                RETURNING a.athlete_id
                """
            ),
            {
                "stale_minutes": str(GARMIN_STREAM_STALE_MINUTES),
                "error_marker": f"garmin_detail_missing_timeout_{GARMIN_STREAM_STALE_MINUTES}m",
            },
        ).fetchall()
        db.commit()

        healed = len(updated_rows)
        athlete_ids = {str(r.athlete_id) for r in updated_rows}
        affected_athletes = len(athlete_ids)

        if healed >= GARMIN_STREAM_ALERT_THRESHOLD:
            logger.warning(
                "[garmin-stream-health] healed=%d affected_athletes=%d stale_window_min=%d",
                healed,
                affected_athletes,
                GARMIN_STREAM_STALE_MINUTES,
            )
        elif healed > 0:
            logger.info(
                "[garmin-stream-health] healed=%d affected_athletes=%d stale_window_min=%d",
                healed,
                affected_athletes,
                GARMIN_STREAM_STALE_MINUTES,
            )

        return {
            "status": "ok",
            "healed": healed,
            "affected_athletes": affected_athletes,
            "stale_window_min": GARMIN_STREAM_STALE_MINUTES,
        }
    except Exception as exc:
        db.rollback()
        logger.exception("cleanup_stale_garmin_pending_streams failed: %s", exc)
        raise self.retry(exc=exc)
    finally:
        db.close()
