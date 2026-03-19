"""
Plan lifecycle background tasks.

Auto-completes active plans whose goal race date has passed.
"""

from datetime import date

from celery import shared_task

from core.database import get_db_sync
from models import TrainingPlan


def _complete_expired_plans_in_db(db, *, today: date | None = None) -> int:
    """
    Internal implementation that operates on a caller-provided DB session.
    """
    effective_today = today or date.today()
    stale_active_plans = (
        db.query(TrainingPlan)
        .filter(
            TrainingPlan.status == "active",
            TrainingPlan.goal_race_date < effective_today,
        )
        .all()
    )

    if not stale_active_plans:
        return 0

    for plan in stale_active_plans:
        plan.status = "completed"

    db.commit()
    return len(stale_active_plans)


@shared_task(name="tasks.complete_expired_plans")
def complete_expired_plans() -> int:
    """
    Mark active plans as completed when goal_race_date is before today.

    Returns:
        Number of plans transitioned to completed.
    """
    db = get_db_sync()
    try:
        return _complete_expired_plans_in_db(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
