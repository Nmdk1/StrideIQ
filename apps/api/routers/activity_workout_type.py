"""
Activity Workout Type API

Allows athletes to:
- View the classified workout type for an activity
- Override/set the workout type themselves
- This improves data quality and builds training data for better classification
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID

from core.database import get_db
from core.auth import get_current_athlete
from models import Athlete, Activity
from services.workout_classifier import WorkoutType, WorkoutZone

router = APIRouter(prefix="/v1/activities", tags=["Activity Workout Type"])


# All available workout types for the dropdown
WORKOUT_TYPE_OPTIONS = [
    {"value": "recovery_run", "label": "Recovery Run", "zone": "recovery", "description": "Very easy, promoting blood flow"},
    {"value": "easy_run", "label": "Easy Run", "zone": "endurance", "description": "Comfortable aerobic pace"},
    {"value": "aerobic_run", "label": "Aerobic Run", "zone": "endurance", "description": "Moderate steady effort"},
    {"value": "long_run", "label": "Long Run", "zone": "endurance", "description": "Extended endurance builder"},
    {"value": "medium_long_run", "label": "Medium Long Run", "zone": "endurance", "description": "Mid-week volume run"},
    {"value": "tempo_run", "label": "Tempo Run", "zone": "stamina", "description": "Sustained threshold effort"},
    {"value": "tempo_intervals", "label": "Tempo Intervals", "zone": "stamina", "description": "Threshold intervals with recovery"},
    {"value": "threshold_run", "label": "Threshold Run", "zone": "stamina", "description": "Hard lactate threshold effort"},
    {"value": "cruise_intervals", "label": "Cruise Intervals", "zone": "stamina", "description": "Broken tempo with short rest"},
    {"value": "vo2max_intervals", "label": "VO2max Intervals", "zone": "speed", "description": "High intensity for aerobic power"},
    {"value": "track_workout", "label": "Track Workout", "zone": "speed", "description": "Speed work on the track"},
    {"value": "fartlek", "label": "Fartlek", "zone": "mixed", "description": "Flexible speed play"},
    {"value": "hill_repetitions", "label": "Hill Repetitions", "zone": "speed", "description": "Uphill repeats for strength"},
    {"value": "strides", "label": "Strides", "zone": "sprint", "description": "Short fast accelerations"},
    {"value": "marathon_pace", "label": "Marathon Pace", "zone": "race_specific", "description": "Goal marathon race pace"},
    {"value": "half_marathon_pace", "label": "Half Marathon Pace", "zone": "race_specific", "description": "Goal half marathon pace"},
    {"value": "progression_run", "label": "Progression Run", "zone": "mixed", "description": "Gradual pace increase"},
    {"value": "fast_finish_long_run", "label": "Fast Finish Long Run", "zone": "mixed", "description": "Long run with race-pace finish"},
    {"value": "race", "label": "Race", "zone": "race_specific", "description": "Competition or time trial"},
    {"value": "tune_up_race", "label": "Tune-up Race", "zone": "race_specific", "description": "Training race"},
    {"value": "shakeout", "label": "Shakeout", "zone": "recovery", "description": "Pre-race easy jog"},
]

# Map value to zone
WORKOUT_ZONE_MAP = {opt["value"]: opt["zone"] for opt in WORKOUT_TYPE_OPTIONS}


class WorkoutTypeUpdate(BaseModel):
    """Request to update workout type"""
    workout_type: str
    notes: Optional[str] = None  # Optional notes about why they classified it this way


class WorkoutTypeResponse(BaseModel):
    """Response with workout type info"""
    activity_id: str
    workout_type: Optional[str]
    workout_zone: Optional[str]
    workout_confidence: Optional[float]
    is_user_override: bool  # True if athlete set this, False if auto-classified


class WorkoutTypeOptionsResponse(BaseModel):
    """Available workout type options"""
    options: List[dict]


@router.get("/workout-types/options", response_model=WorkoutTypeOptionsResponse)
async def get_workout_type_options():
    """
    Get all available workout type options for the dropdown.
    """
    return WorkoutTypeOptionsResponse(options=WORKOUT_TYPE_OPTIONS)


@router.get("/{activity_id}/workout-type", response_model=WorkoutTypeResponse)
async def get_activity_workout_type(
    activity_id: UUID,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Get the workout type for a specific activity.
    """
    activity = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.athlete_id == athlete.id,
    ).first()
    
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    # Confidence of 1.0 means user-set, <1.0 means auto-classified
    is_user_override = activity.workout_confidence == 1.0
    
    return WorkoutTypeResponse(
        activity_id=str(activity.id),
        workout_type=activity.workout_type,
        workout_zone=activity.workout_zone,
        workout_confidence=activity.workout_confidence,
        is_user_override=is_user_override,
    )


@router.put("/{activity_id}/workout-type", response_model=WorkoutTypeResponse)
async def update_activity_workout_type(
    activity_id: UUID,
    request: WorkoutTypeUpdate,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Update the workout type for an activity.
    
    This allows athletes to correct auto-classification or set it for the first time.
    User-set types have confidence of 1.0 (100%).
    """
    activity = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.athlete_id == athlete.id,
    ).first()
    
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    # Validate workout type
    valid_types = [opt["value"] for opt in WORKOUT_TYPE_OPTIONS]
    if request.workout_type not in valid_types:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid workout type. Must be one of: {', '.join(valid_types)}"
        )
    
    # Update the activity
    activity.workout_type = request.workout_type
    activity.workout_zone = WORKOUT_ZONE_MAP.get(request.workout_type)
    activity.workout_confidence = 1.0  # User-set = 100% confidence
    
    db.commit()
    db.refresh(activity)
    
    return WorkoutTypeResponse(
        activity_id=str(activity.id),
        workout_type=activity.workout_type,
        workout_zone=activity.workout_zone,
        workout_confidence=activity.workout_confidence,
        is_user_override=True,
    )


@router.delete("/{activity_id}/workout-type")
async def clear_activity_workout_type(
    activity_id: UUID,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Clear the workout type for an activity (revert to unclassified).
    Useful if athlete wants to let the system re-classify.
    """
    activity = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.athlete_id == athlete.id,
    ).first()
    
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    activity.workout_type = None
    activity.workout_zone = None
    activity.workout_confidence = None
    
    db.commit()
    
    return {"message": "Workout type cleared", "activity_id": str(activity_id)}
