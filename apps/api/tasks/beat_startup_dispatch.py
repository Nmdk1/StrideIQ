"""
Beat Startup Dispatch — deployment-proof daily task execution.

On beat container startup, checks which daily tasks are overdue
(haven't run in the last 20 hours) and dispatches them immediately.
This solves the problem of crontab-only tasks missing their window
when the beat container is recreated by a deployment.

Each daily task records its last completion in a Redis key with a
25-hour TTL. On startup, any missing or expired key triggers
an immediate dispatch.

Hooks into Celery's beat_init signal — runs once when the beat
process starts, before the first scheduler tick.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from celery.signals import beat_init

logger = logging.getLogger(__name__)

DAILY_TASKS = [
    {
        "name": "tasks.complete_expired_plans",
        "redis_key": "beat:last_run:complete_expired_plans",
        "description": "Plan lifecycle cleanup",
    },
    {
        "name": "tasks.backfill_athlete_timezones",
        "redis_key": "beat:last_run:backfill_athlete_timezones",
        "description": "Timezone backfill",
    },
    {
        "name": "tasks.run_auto_discovery_nightly",
        "redis_key": "beat:last_run:auto_discovery_nightly",
        "description": "AutoDiscovery nightly",
    },
    {
        "name": "tasks.refresh_living_fingerprint",
        "redis_key": "beat:last_run:refresh_living_fingerprint",
        "description": "Living Fingerprint refresh",
    },
    {
        "name": "tasks.run_experience_guardrail",
        "redis_key": "beat:last_run:experience_guardrail",
        "description": "Experience guardrail",
    },
    {
        "name": "tasks.check_garmin_ingestion_health",
        "redis_key": "beat:last_run:garmin_ingestion_health",
        "description": "Garmin ingestion health check",
    },
    {
        "name": "tasks.run_daily_correlation_sweep",
        "redis_key": "beat:last_run:daily_correlation_sweep",
        "description": "Daily correlation sweep",
    },
]

REDIS_TTL_SECONDS = 25 * 60 * 60  # 25 hours


def record_task_run(redis_key: str) -> None:
    """Record that a daily task completed. Called at the end of each task."""
    try:
        from core.cache import get_redis_client

        rc = get_redis_client()
        if rc:
            rc.setex(redis_key, REDIS_TTL_SECONDS, datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        logger.warning("Failed to record task run for %s: %s", redis_key, exc)


@beat_init.connect
def dispatch_overdue_daily_tasks(sender, **kwargs):
    """
    On beat startup, dispatch any daily task that hasn't run recently.

    Uses Redis keys (set by record_task_run) to determine staleness.
    If a key is missing or expired, the task is considered overdue.
    Tasks are dispatched to the default Celery queue with low priority
    and a short countdown to stagger execution.
    """
    try:
        from core.cache import get_redis_client

        rc = get_redis_client()
        if not rc:
            logger.warning("Beat startup dispatch: Redis unavailable, skipping overdue checks")
            return

        dispatched = []
        skipped = []

        for i, task in enumerate(DAILY_TASKS):
            last_run = rc.get(task["redis_key"])

            if last_run:
                skipped.append(task["description"])
                continue

            try:
                from tasks import celery_app

                celery_app.send_task(
                    task["name"],
                    countdown=30 + (i * 15),
                )
                dispatched.append(task["description"])
                logger.info(
                    "Beat startup: dispatched overdue task %s (%s) with %ds countdown",
                    task["name"],
                    task["description"],
                    30 + (i * 15),
                )
            except Exception as exc:
                logger.error(
                    "Beat startup: failed to dispatch %s: %s",
                    task["name"],
                    exc,
                )

        logger.info(
            "Beat startup dispatch complete: %d dispatched, %d skipped (recent). "
            "Dispatched: [%s]. Skipped: [%s]",
            len(dispatched),
            len(skipped),
            ", ".join(dispatched) or "none",
            ", ".join(skipped) or "none",
        )

    except Exception as exc:
        logger.error("Beat startup dispatch failed: %s", exc, exc_info=True)
