"""
Plan Modification Audit Service

Tracks all modifications to training plans and workouts.
Provides audit trail for security, analytics, and rollback capability.
"""

from uuid import UUID
from typing import Optional, Any
from sqlalchemy.orm import Session
from datetime import datetime

from models import PlanModificationLog, PlannedWorkout


def _serialize_workout(workout: PlannedWorkout) -> dict:
    """Serialize a workout to a JSON-compatible dict for audit logging."""
    return {
        "id": str(workout.id),
        "scheduled_date": workout.scheduled_date.isoformat() if workout.scheduled_date else None,
        "week_number": workout.week_number,
        "day_of_week": workout.day_of_week,
        "workout_type": workout.workout_type,
        "workout_subtype": workout.workout_subtype,
        "title": workout.title,
        "description": workout.description,
        "phase": workout.phase,
        "target_distance_km": workout.target_distance_km,
        "target_duration_minutes": workout.target_duration_minutes,
        "target_pace_per_km_seconds": workout.target_pace_per_km_seconds,
        "coach_notes": workout.coach_notes,
        "completed": workout.completed,
        "skipped": workout.skipped,
    }


def log_modification(
    db: Session,
    athlete_id: UUID,
    plan_id: UUID,
    action: str,
    workout_id: Optional[UUID] = None,
    before_state: Optional[dict] = None,
    after_state: Optional[dict] = None,
    reason: Optional[str] = None,
    source: str = "web",
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> PlanModificationLog:
    """
    Log a plan modification for audit trail.
    
    Args:
        db: Database session
        athlete_id: Athlete making the modification
        plan_id: Training plan being modified
        action: Action type (move_workout, edit_workout, delete_workout, add_workout, etc.)
        workout_id: Specific workout being modified (if applicable)
        before_state: JSON-serializable state before modification
        after_state: JSON-serializable state after modification
        reason: Optional athlete-provided reason
        source: Source of modification (web, mobile, api, coach)
        ip_address: Client IP for security audit
        user_agent: Client user agent string
        
    Returns:
        Created PlanModificationLog entry
    """
    log_entry = PlanModificationLog(
        athlete_id=athlete_id,
        plan_id=plan_id,
        workout_id=workout_id,
        action=action,
        before_state=before_state,
        after_state=after_state,
        reason=reason,
        source=source,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    
    db.add(log_entry)
    # Don't commit here - let the caller manage the transaction
    
    return log_entry


def log_workout_move(
    db: Session,
    athlete_id: UUID,
    plan_id: UUID,
    workout: PlannedWorkout,
    old_date: Any,
    new_date: Any,
    reason: Optional[str] = None,
) -> PlanModificationLog:
    """Log a workout move action."""
    before = _serialize_workout(workout)
    before["scheduled_date"] = old_date.isoformat() if old_date else None
    
    after = _serialize_workout(workout)
    after["scheduled_date"] = new_date.isoformat() if new_date else None
    
    return log_modification(
        db=db,
        athlete_id=athlete_id,
        plan_id=plan_id,
        action="move_workout",
        workout_id=workout.id,
        before_state=before,
        after_state=after,
        reason=reason,
    )


def log_workout_edit(
    db: Session,
    athlete_id: UUID,
    plan_id: UUID,
    workout: PlannedWorkout,
    before_snapshot: dict,
    changes: list[str],
    reason: Optional[str] = None,
) -> PlanModificationLog:
    """Log a workout edit action."""
    return log_modification(
        db=db,
        athlete_id=athlete_id,
        plan_id=plan_id,
        action="edit_workout",
        workout_id=workout.id,
        before_state=before_snapshot,
        after_state={**_serialize_workout(workout), "changes": changes},
        reason=reason,
    )


def log_workout_delete(
    db: Session,
    athlete_id: UUID,
    plan_id: UUID,
    workout: PlannedWorkout,
    reason: Optional[str] = None,
) -> PlanModificationLog:
    """Log a workout deletion (skip) action."""
    return log_modification(
        db=db,
        athlete_id=athlete_id,
        plan_id=plan_id,
        action="delete_workout",
        workout_id=workout.id,
        before_state=_serialize_workout(workout),
        after_state={"skipped": True},
        reason=reason,
    )


def log_workout_add(
    db: Session,
    athlete_id: UUID,
    plan_id: UUID,
    workout: PlannedWorkout,
    reason: Optional[str] = None,
) -> PlanModificationLog:
    """Log a new workout addition."""
    return log_modification(
        db=db,
        athlete_id=athlete_id,
        plan_id=plan_id,
        action="add_workout",
        workout_id=workout.id,
        before_state=None,
        after_state=_serialize_workout(workout),
        reason=reason,
    )


def log_workout_swap(
    db: Session,
    athlete_id: UUID,
    plan_id: UUID,
    workout1: PlannedWorkout,
    workout2: PlannedWorkout,
    reason: Optional[str] = None,
) -> PlanModificationLog:
    """Log a workout swap action."""
    return log_modification(
        db=db,
        athlete_id=athlete_id,
        plan_id=plan_id,
        action="swap_workouts",
        before_state={
            "workout1": _serialize_workout(workout1),
            "workout2": _serialize_workout(workout2),
        },
        after_state={
            "workout1_new_date": workout1.scheduled_date.isoformat() if workout1.scheduled_date else None,
            "workout2_new_date": workout2.scheduled_date.isoformat() if workout2.scheduled_date else None,
        },
        reason=reason,
    )


def log_load_adjust(
    db: Session,
    athlete_id: UUID,
    plan_id: UUID,
    week_number: int,
    adjustment: str,
    affected_workouts: list[dict],
    reason: Optional[str] = None,
) -> PlanModificationLog:
    """Log a weekly load adjustment."""
    return log_modification(
        db=db,
        athlete_id=athlete_id,
        plan_id=plan_id,
        action="adjust_load",
        before_state={"week_number": week_number, "workouts": affected_workouts},
        after_state={"adjustment": adjustment},
        reason=reason,
    )
