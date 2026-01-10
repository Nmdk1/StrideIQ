"""
Activity Comparison API Router

Enables powerful workout comparisons that Garmin/Strava don't offer:
- Compare all tempo runs
- Compare hot vs cool days
- Compare this month vs last month
- See trends within workout types
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timedelta
from uuid import UUID
from pydantic import BaseModel, Field

from core.database import get_db
from core.auth import get_current_athlete
from models import Athlete, Activity
from services.activity_comparison import ActivityComparisonService
from services.workout_classifier import WorkoutClassifierService

router = APIRouter(prefix="/v1/compare", tags=["Comparison"])


class IndividualCompareRequest(BaseModel):
    """Request body for individual activity comparison"""
    activity_ids: List[UUID] = Field(
        ..., 
        min_length=2, 
        max_length=10,
        description="List of 2-10 activity IDs to compare"
    )


@router.post("/individual")
async def compare_individual_activities(
    request: IndividualCompareRequest,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Compare 2-10 specific activities side-by-side.
    
    This is the marquee feature - select specific runs and see them
    compared with metrics table, best/worst highlighting, and insights.
    
    Returns:
    - All activity details in a comparison table
    - Best performer for each metric
    - Plain-language insights
    """
    service = ActivityComparisonService(db)
    
    try:
        result = service.compare_individual(
            athlete_id=athlete.id,
            activity_ids=request.activity_ids,
        )
        return result.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/workout-types")
async def get_workout_type_summary(
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Get a summary of activities by workout type.
    Shows how many of each type you have for comparison.
    """
    service = ActivityComparisonService(db)
    summary = service.get_workout_type_summary(athlete.id)
    
    return {
        "workout_types": summary,
        "total": sum(summary.values()),
    }


@router.get("/by-type/{workout_type}")
async def compare_by_workout_type(
    workout_type: str,
    days: int = Query(default=180, ge=7, le=730),
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Compare all activities of a specific workout type.
    
    Returns:
    - Trend analysis (improving/declining/stable)
    - Best and worst performances
    - All activities for detailed view
    """
    service = ActivityComparisonService(db)
    result = service.compare_by_workout_type(
        athlete_id=athlete.id,
        workout_type=workout_type,
        days=days,
    )
    
    return result.to_dict()


@router.get("/by-conditions")
async def compare_by_conditions(
    workout_type: Optional[str] = None,
    temp_min: Optional[float] = Query(default=None, description="Min temperature in °F"),
    temp_max: Optional[float] = Query(default=None, description="Max temperature in °F"),
    days: int = Query(default=365, ge=30, le=730),
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Compare activities filtered by conditions.
    
    Example: Compare tempo runs in hot weather (>80°F) vs cool (<60°F)
    """
    service = ActivityComparisonService(db)
    result = service.compare_by_conditions(
        athlete_id=athlete.id,
        workout_type=workout_type,
        temp_min=temp_min,
        temp_max=temp_max,
        days=days,
    )
    
    return result.to_dict()


@router.get("/activity/{activity_id}")
async def get_activity_with_comparison(
    activity_id: UUID,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Get an activity with comparison to similar workouts.
    
    Returns:
    - Activity details with splits
    - Comparison to similar workout types
    - Percentile ranking
    """
    service = ActivityComparisonService(db)
    result = service.get_activity_with_comparison(
        activity_id=activity_id,
        athlete_id=athlete.id,
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    return result


@router.post("/classify-all")
async def classify_all_activities(
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Classify all activities that don't have a workout type yet.
    This is a one-time operation to backfill existing activities.
    """
    classifier = WorkoutClassifierService(db)
    
    # Get unclassified activities
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete.id,
        Activity.workout_type.is_(None),
        Activity.distance_m >= 1000,  # Only classify meaningful runs
    ).all()
    
    classified_count = 0
    for activity in activities:
        try:
            classification = classifier.classify_activity(activity)
            activity.workout_type = classification.workout_type.value
            activity.workout_zone = classification.workout_zone.value
            activity.workout_confidence = classification.confidence
            activity.intensity_score = classification.intensity_score
            classified_count += 1
        except Exception as e:
            # Skip activities that fail classification
            continue
    
    db.commit()
    
    return {
        "classified": classified_count,
        "total_unclassified_before": len(activities),
        "message": f"Classified {classified_count} activities"
    }
