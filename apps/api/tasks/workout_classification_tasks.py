"""Backfill / refresh task for `activity.workout_type`.

Why this task exists
--------------------
The Garmin webhook ingest path silently failed to classify workouts for
months because `WorkoutClassifierService.classify_activity` was called as
a class method without a `db` arg.  Every Garmin-primary athlete piled
up activities with `workout_type=NULL`, which then made the Compare tab
return "no similar runs" for everyone except the founder (the founder
had run the per-athlete reclassification ops script).

The webhook bug is fixed at the call site, but two things are still
needed:

1. A one-time backfill of the existing fleet so historical activities
   pick up a workout_type without anyone having to run an ops script
   per-athlete.
2. A periodic safety-net sweep so any future code path that creates an
   activity without classifying it (or where classification raises) is
   self-healing within one cycle.  Same defense-in-depth pattern as the
   Garmin -> Strava fallback sweep.

Idempotent: classifies any row where `workout_type IS NULL` for runs in
the trailing 365 days (older history is rarely surfaced and re-running
the classifier on it is pure cost).  Skips already-classified rows.

Bounded: classifies at most BATCH_LIMIT activities per athlete per
invocation to keep memory + db-time per task small even on a one-shot
backfill of years of activity.
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from celery import shared_task
from sqlalchemy import and_

from core.database import SessionLocal
from models import Activity, Athlete
from services.workout_classifier import WorkoutClassifierService

logger = logging.getLogger(__name__)


# Per-athlete safety bound: even a fresh full-history backfill processes
# at most this many activities before the task ends and yields the worker
# back to the queue.  Subsequent sweep cycles will pick up any remainder.
BATCH_LIMIT_PER_ATHLETE = 200

# How far back to consider.  Anything older than this is rarely surfaced
# in any product feature; we don't pay the classifier cost for it.
TRAILING_DAYS = 365


@shared_task(
    name="tasks.backfill_workout_classifications",
    bind=True,
    max_retries=0,
)
def backfill_workout_classifications(
    self,
    athlete_id: Optional[str] = None,
    limit_athletes: Optional[int] = None,
    batch_limit_per_athlete: int = BATCH_LIMIT_PER_ATHLETE,
    trailing_days: int = TRAILING_DAYS,
) -> dict:
    """Classify any run activity with `workout_type IS NULL`.

    Args:
        athlete_id: optional filter to a single athlete (UUID string).
        limit_athletes: optional cap on number of athletes processed.
        batch_limit_per_athlete: max activities classified per athlete per run.
        trailing_days: only consider runs whose start_time falls within this
            many days of now.

    Returns:
        Structured summary used by ops + the periodic safety-net sweep.
    """
    from datetime import datetime, timedelta, timezone

    db = SessionLocal()
    athletes_processed = 0
    classified = 0
    errors = 0
    try:
        q = db.query(Athlete.id)
        if athlete_id:
            q = q.filter(Athlete.id == UUID(str(athlete_id)))
        if limit_athletes:
            q = q.limit(int(limit_athletes))
        athlete_ids = [row[0] for row in q.all()]

        cutoff = datetime.now(timezone.utc) - timedelta(days=int(trailing_days))
        classifier = WorkoutClassifierService(db)

        for aid in athlete_ids:
            try:
                pending = (
                    db.query(Activity)
                    .filter(
                        and_(
                            Activity.athlete_id == aid,
                            Activity.sport == "run",
                            Activity.workout_type.is_(None),
                            Activity.start_time >= cutoff,
                        )
                    )
                    .order_by(Activity.start_time.desc())
                    .limit(int(batch_limit_per_athlete))
                    .all()
                )

                if not pending:
                    continue

                athletes_processed += 1
                athlete_classified = 0
                for activity in pending:
                    try:
                        result = classifier.classify_activity(activity)
                        activity.workout_type = result.workout_type.value
                        activity.workout_zone = result.workout_zone.value
                        activity.workout_confidence = result.confidence
                        activity.intensity_score = result.intensity_score
                        athlete_classified += 1
                    except Exception as exc:
                        errors += 1
                        logger.warning(
                            "workout_classify_row_failed athlete_id=%s activity_id=%s err=%s",
                            aid,
                            activity.id,
                            exc,
                        )

                if athlete_classified > 0:
                    db.commit()
                    classified += athlete_classified
                else:
                    db.rollback()
            except Exception as exc:
                errors += 1
                logger.warning(
                    "workout_classify_athlete_failed athlete_id=%s err=%s",
                    aid,
                    exc,
                )
                db.rollback()

        if classified > 0 or errors > 0:
            logger.info(
                "[workout-classify-backfill] athletes_processed=%d classified=%d errors=%d trailing_days=%d",
                athletes_processed,
                classified,
                errors,
                trailing_days,
            )

        return {
            "status": "ok",
            "athletes_processed": athletes_processed,
            "classified": classified,
            "errors": errors,
            "trailing_days": trailing_days,
        }
    finally:
        db.close()


@shared_task(
    name="tasks.sweep_unclassified_runs",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def sweep_unclassified_runs(self) -> dict:
    """Periodic safety-net: classify any run with workout_type=NULL.

    Same defense-in-depth philosophy as the Garmin fallback sweep.  Catches
    any run that slipped past the ingest-time classifier (e.g. classifier
    raised on a malformed row, a future code path forgot to wire it, etc.)
    so the Compare tab can rely on workout_type being populated.

    Smaller per-athlete batch on the periodic version so a one-time backfill
    of years of data still spreads across cycles instead of holding the
    worker for many seconds at a time.
    """
    return backfill_workout_classifications.run(
        athlete_id=None,
        limit_athletes=None,
        batch_limit_per_athlete=50,
        trailing_days=TRAILING_DAYS,
    )
