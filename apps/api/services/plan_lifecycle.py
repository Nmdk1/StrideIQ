"""
Plan lifecycle helpers used by API read paths and background tasks.
"""

from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from models import TrainingPlan


def complete_expired_active_plans_for_athlete(
    db: Session,
    athlete_id: UUID,
    *,
    today: date | None = None,
) -> int:
    """
    Transition stale active plans to completed for one athlete.
    """
    effective_today = today or date.today()
    stale_active = (
        db.query(TrainingPlan)
        .filter(
            TrainingPlan.athlete_id == athlete_id,
            TrainingPlan.status == "active",
            TrainingPlan.goal_race_date < effective_today,
        )
        .all()
    )
    if not stale_active:
        return 0

    for plan in stale_active:
        plan.status = "completed"

    db.commit()
    return len(stale_active)


def get_active_plan_for_athlete(
    db: Session,
    athlete_id: UUID,
    *,
    today: date | None = None,
) -> TrainingPlan | None:
    """
    Return active plan after enforcing read-time expiry completion.
    """
    complete_expired_active_plans_for_athlete(db, athlete_id, today=today)
    return (
        db.query(TrainingPlan)
        .filter(
            TrainingPlan.athlete_id == athlete_id,
            TrainingPlan.status == "active",
        )
        .order_by(TrainingPlan.goal_race_date.desc(), TrainingPlan.created_at.desc())
        .first()
    )
