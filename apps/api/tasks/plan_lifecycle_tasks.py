"""
Plan lifecycle background tasks.

Auto-completes active plans whose goal race date has passed.
"""

from datetime import date

from celery import shared_task

from core.database import get_db_sync
from models import TrainingPlan
from services.plan_lifecycle import complete_expired_active_plans_for_athlete


def _complete_expired_plans_in_db(db, *, today: date | None = None) -> int:
    """
    Internal implementation that operates on a caller-provided DB session.
    """
    effective_today = today or date.today()
    athlete_ids = (
        db.query(TrainingPlan.athlete_id)
        .filter(
            TrainingPlan.status == "active",
            TrainingPlan.goal_race_date < effective_today,
        )
        .distinct()
        .all()
    )
    if not athlete_ids:
        return 0

    updated_total = 0
    for (athlete_id,) in athlete_ids:
        updated_total += complete_expired_active_plans_for_athlete(
            db, athlete_id, today=effective_today
        )
    return updated_total


@shared_task(name="tasks.complete_expired_plans")
def complete_expired_plans() -> int:
    """
    Mark active plans as completed when goal_race_date is before today.

    Returns:
        Number of plans transitioned to completed.
    """
    db = get_db_sync()
    try:
        result = _complete_expired_plans_in_db(db)

        from tasks.beat_startup_dispatch import record_task_run
        record_task_run("beat:last_run:complete_expired_plans")

        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
