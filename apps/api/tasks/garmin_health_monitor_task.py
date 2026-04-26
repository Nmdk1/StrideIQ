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
                RETURNING a.id, a.athlete_id
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

        # --- Strava-fallback enqueue (Garmin -> Strava structural repair) ---
        # Every row we just fail-closed gets one shot at repair via the
        # athlete's Strava account.  The task itself enforces the eligibility
        # gates (Strava tokens present, sport=run, age <= 14d, idempotent
        # claim) so a duplicate enqueue is harmless.
        # Enqueue is best-effort: a Celery broker hiccup must not roll back
        # the cleanup commit above.
        fallback_enqueued = 0
        try:
            from tasks.strava_fallback_tasks import (
                repair_garmin_activity_from_strava_task,
            )

            for row in updated_rows:
                try:
                    repair_garmin_activity_from_strava_task.delay(str(row.id))
                    fallback_enqueued += 1
                except Exception as enqueue_exc:
                    logger.warning(
                        "strava_fallback_enqueue_failed activity_id=%s error=%s",
                        row.id,
                        enqueue_exc,
                    )
        except Exception as import_exc:
            logger.warning(
                "strava_fallback_module_unavailable: %s", import_exc
            )

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
            "fallback_enqueued": fallback_enqueued,
        }
    except Exception as exc:
        db.rollback()
        logger.exception("cleanup_stale_garmin_pending_streams failed: %s", exc)
        raise self.retry(exc=exc)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Self-healing sweep — defense in depth for the Garmin -> Strava fallback.
#
# Background: a Garmin activity row can be transitioned to
# `stream_fetch_status='unavailable'` from at least two paths today:
#   1. The cleanup beat above (after 30m stale)
#   2. The webhook handler when activity_detail arrives with no samples/laps
# Both paths *should* enqueue the Strava fallback so the UI gets a chart, a
# map and splits.  When one of them forgets — or a future code path adds a
# third transition without remembering — affected athletes silently accumulate
# blank activity pages forever.  That is exactly the regression that broke
# Larry / Adam / Brian.
#
# This sweep removes the requirement that every transition path remember to
# enqueue.  Instead, every N minutes we scan ALL eligible unavailable rows
# and enqueue the repair.  The repair task itself owns the atomic claim
# (`UPDATE...WHERE strava_fallback_status IS NULL OR 'failed' RETURNING`) so
# duplicate enqueues are harmless and concurrency-safe.
# ---------------------------------------------------------------------------

GARMIN_FALLBACK_SWEEP_BATCH_LIMIT = 200
GARMIN_FALLBACK_MAX_AGE_DAYS = 14
GARMIN_FALLBACK_MAX_ATTEMPTS = 3


@celery_app.task(
    name="tasks.sweep_unavailable_garmin_streams",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def sweep_unavailable_garmin_streams(self) -> dict:
    """Catch every Garmin row marked 'unavailable' that has not yet been
    repaired (or whose previous attempt soft-failed and is retryable) and
    enqueue the Strava fallback.

    Idempotent: the repair task's atomic claim makes duplicate enqueues
    harmless.  Bounded: cap at GARMIN_FALLBACK_SWEEP_BATCH_LIMIT per run so
    a one-time backfill of thousands of rows still spreads across cycles
    instead of flooding the queue.
    """
    db = get_db_sync()
    try:
        rows = db.execute(
            text(
                """
                SELECT a.id::text AS id
                FROM activity a
                WHERE a.provider = 'garmin'
                  AND a.sport = 'run'
                  AND a.stream_fetch_status = 'unavailable'
                  AND a.start_time > NOW() - (:max_age_days || ' days')::interval
                  AND (
                        a.strava_fallback_status IS NULL
                        OR (
                            a.strava_fallback_status IN ('failed', 'skipped_no_match', 'skipped_rate_limited')
                            AND COALESCE(a.strava_fallback_attempt_count, 0) < :max_attempts
                        )
                      )
                ORDER BY a.start_time DESC
                LIMIT :limit
                """
            ),
            {
                "max_age_days": str(GARMIN_FALLBACK_MAX_AGE_DAYS),
                "max_attempts": GARMIN_FALLBACK_MAX_ATTEMPTS,
                "limit": GARMIN_FALLBACK_SWEEP_BATCH_LIMIT,
            },
        ).fetchall()

        candidates = [r.id for r in rows]
        if not candidates:
            return {"status": "ok", "candidates": 0, "enqueued": 0}

        from tasks.strava_fallback_tasks import (
            repair_garmin_activity_from_strava_task,
        )

        enqueued = 0
        for activity_id in candidates:
            try:
                repair_garmin_activity_from_strava_task.delay(activity_id)
                enqueued += 1
            except Exception as enqueue_exc:
                logger.warning(
                    "garmin_fallback_sweep_enqueue_failed activity_id=%s error=%s",
                    activity_id,
                    enqueue_exc,
                )

        if enqueued > 0:
            logger.info(
                "[garmin-fallback-sweep] candidates=%d enqueued=%d max_age_days=%d",
                len(candidates),
                enqueued,
                GARMIN_FALLBACK_MAX_AGE_DAYS,
            )

        return {
            "status": "ok",
            "candidates": len(candidates),
            "enqueued": enqueued,
            "max_age_days": GARMIN_FALLBACK_MAX_AGE_DAYS,
        }
    except Exception as exc:
        logger.exception("sweep_unavailable_garmin_streams failed: %s", exc)
        raise self.retry(exc=exc)
    finally:
        db.close()
