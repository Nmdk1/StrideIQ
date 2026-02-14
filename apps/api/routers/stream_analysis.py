"""
RSI-Alpha — Stream Analysis API Router

Provides GET /v1/activities/{activity_id}/stream-analysis

Returns StreamAnalysisResult when stream data is available, or lifecycle
status responses (pending, unavailable) matching ADR-063 fetch states.

AC coverage: AC-1 (endpoint contract)
"""
from dataclasses import asdict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from core.database import get_db
from core.auth import get_current_user
from models import Activity, ActivityStream, Athlete, PlannedWorkout
from services.run_stream_analysis import (
    AthleteContext,
    analyze_stream,
)

router = APIRouter(prefix="/v1/activities", tags=["stream-analysis"])


@router.get("/{activity_id}/stream-analysis")
def get_stream_analysis(
    activity_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Analyze per-second stream data for a completed run.

    Returns:
        - Full StreamAnalysisResult when stream_fetch_status == 'success'
        - {"status": "pending"} when fetch is in progress
        - {"status": "unavailable"} for manual activities
        - 404 when activity not found or not owned by current user
        - 401 when not authenticated
    """
    # --- Activity lookup + ownership check ---
    activity = (
        db.query(Activity)
        .filter(Activity.id == activity_id)
        .first()
    )
    if activity is None or activity.athlete_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found",
        )

    # --- Lifecycle state handling (ADR-063) ---
    fetch_status = getattr(activity, "stream_fetch_status", None)

    if fetch_status == "unavailable":
        return {"status": "unavailable"}

    if fetch_status in ("pending", "fetching", "failed", None):
        return {"status": "pending"}

    # --- Load stream data ---
    stream_row = (
        db.query(ActivityStream)
        .filter(ActivityStream.activity_id == activity_id)
        .first()
    )
    if stream_row is None:
        return {"status": "pending"}

    stream_data = stream_row.stream_data
    channels_available = stream_row.channels_available or list(stream_data.keys())

    # --- Resolve N=1 athlete context ---
    athlete_ctx = AthleteContext(
        max_hr=getattr(current_user, "max_hr", None),
        resting_hr=getattr(current_user, "resting_hr", None),
        threshold_hr=getattr(current_user, "threshold_hr", None),
    )

    # --- Resolve linked planned workout (additive) ---
    planned_workout_dict = None
    linked_plan = (
        db.query(PlannedWorkout)
        .filter(PlannedWorkout.completed_activity_id == activity_id)
        .first()
    )
    if linked_plan is not None:
        planned_workout_dict = {
            "title": linked_plan.title,
            "workout_type": linked_plan.workout_type,
            "target_duration_minutes": linked_plan.target_duration_minutes,
            "target_distance_km": getattr(linked_plan, "target_distance_km", None),
            "segments": getattr(linked_plan, "segments", None),
        }

    # --- Run analysis ---
    result = analyze_stream(
        stream_data=stream_data,
        channels_available=channels_available,
        planned_workout=planned_workout_dict,
        athlete_context=athlete_ctx,
    )

    return asdict(result)
