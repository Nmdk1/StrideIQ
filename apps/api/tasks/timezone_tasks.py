"""
Timezone backfill task.

Infers and persists IANA timezone for athletes whose timezone is NULL
or invalid, using GPS coordinates from their most recent activity.

Safe to run repeatedly — skips athletes who already have a valid timezone.
Runs once as a startup backfill and is also triggered after Garmin sync
where no timezone is available from the provider.
"""

import logging
from uuid import UUID

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="tasks.backfill_athlete_timezones", bind=True, max_retries=0)
def backfill_athlete_timezones(self):
    """
    Backfill timezone for all athletes with NULL/invalid timezone.

    Runs as a one-off or periodic task. Safe to re-run — idempotent.
    """
    from core.database import SessionLocal
    from models import Athlete
    from services.timezone_utils import infer_and_persist_athlete_timezone, is_valid_iana_timezone

    db = SessionLocal()
    try:
        athletes = db.query(Athlete).filter(
            (Athlete.timezone == None) | (Athlete.timezone == "")  # noqa: E711
        ).all()

        total = len(athletes)
        resolved = 0
        failed = 0

        for athlete in athletes:
            try:
                tz = infer_and_persist_athlete_timezone(db, athlete.id)
                if tz:
                    resolved += 1
                    logger.info("Backfill: %s → %s", athlete.email, tz)
                else:
                    failed += 1
                    logger.debug("Backfill: %s — no GPS data available", athlete.email)
            except Exception as exc:
                failed += 1
                logger.warning("Backfill failed for %s: %s", athlete.email, exc, exc_info=True)

        logger.info(
            "Timezone backfill complete: %d/%d resolved, %d no GPS data",
            resolved, total, failed,
        )
        return {"total": total, "resolved": resolved, "no_gps": failed}
    finally:
        db.close()


@shared_task(name="tasks.infer_timezone_for_athlete", bind=True, max_retries=2)
def infer_timezone_for_athlete(self, athlete_id: str):
    """
    Infer and persist timezone for a single athlete.

    Called after Garmin sync where the provider does not supply timezone.
    """
    from core.database import SessionLocal
    from services.timezone_utils import infer_and_persist_athlete_timezone, is_valid_iana_timezone
    from models import Athlete

    db = SessionLocal()
    try:
        uid = UUID(athlete_id)

        # Check if already has valid timezone — skip
        athlete = db.query(Athlete).filter(Athlete.id == uid).first()
        if athlete and athlete.timezone and is_valid_iana_timezone(athlete.timezone):
            return {"status": "skipped", "timezone": athlete.timezone}

        tz = infer_and_persist_athlete_timezone(db, uid)
        if tz:
            return {"status": "resolved", "timezone": str(tz)}
        return {"status": "no_gps"}
    except Exception as exc:
        logger.warning("infer_timezone_for_athlete failed for %s: %s", athlete_id, exc)
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()
