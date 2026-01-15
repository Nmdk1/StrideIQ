"""
Activities API Router

Provides endpoints for activity management with proper filtering, pagination, and authentication.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
from typing import Optional, List
from datetime import datetime, timedelta
from uuid import UUID
from core.database import get_db
from core.auth import get_current_user
from core.feature_flags import is_feature_enabled
from models import Activity, Athlete
from schemas import ActivityResponse

router = APIRouter(prefix="/v1/activities", tags=["activities"])


@router.get("", response_model=List[ActivityResponse])
def list_activities(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=100, description="Number of activities to return"),
    offset: int = Query(0, ge=0, description="Number of activities to skip"),
    start_date: Optional[str] = Query(None, description="Filter activities from this date (ISO format)"),
    end_date: Optional[str] = Query(None, description="Filter activities until this date (ISO format)"),
    min_distance_m: Optional[int] = Query(None, ge=0, description="Minimum distance in meters"),
    max_distance_m: Optional[int] = Query(None, ge=0, description="Maximum distance in meters"),
    sport: Optional[str] = Query(None, description="Filter by sport type"),
    is_race: Optional[bool] = Query(None, description="Filter by race status"),
    sort_by: str = Query("start_time", description="Sort field: start_time, distance_m, duration_s"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
):
    """
    List activities for current user with filtering and pagination.
    
    Returns only activities belonging to the authenticated user.
    Supports filtering by date range, distance, sport type, and race status.
    """
    # Build query - always filter by athlete_id
    query = db.query(Activity).filter(Activity.athlete_id == current_user.id)
    
    # Date filtering
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query = query.filter(Activity.start_time >= start_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"
            )
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.filter(Activity.start_time <= end_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"
            )
    
    # Distance filtering
    if min_distance_m is not None:
        query = query.filter(Activity.distance_m >= min_distance_m)
    
    if max_distance_m is not None:
        query = query.filter(Activity.distance_m <= max_distance_m)
    
    # Sport filtering
    if sport:
        query = query.filter(Activity.sport == sport)
    
    # Race filtering
    # When filtering for races (is_race=True): include if EITHER flag is True
    # When filtering for training (is_race=False): exclude if EITHER flag is True
    if is_race is not None:
        if is_race:
            # Show races: either user verified OR candidate
            query = query.filter(
                or_(
                    Activity.user_verified_race == True,
                    Activity.is_race_candidate == True
                )
            )
        else:
            # Show training only: NOT a race (both flags must be False/None)
            query = query.filter(
                and_(
                    or_(Activity.user_verified_race == False, Activity.user_verified_race.is_(None)),
                    or_(Activity.is_race_candidate == False, Activity.is_race_candidate.is_(None))
                )
            )
    
    # Sorting
    sort_field_map = {
        "start_time": Activity.start_time,
        "distance_m": Activity.distance_m,
        "duration_s": Activity.duration_s,
    }
    
    sort_field = sort_field_map.get(sort_by, Activity.start_time)
    if sort_order.lower() == "asc":
        query = query.order_by(asc(sort_field))
    else:
        query = query.order_by(desc(sort_field))
    
    # Pagination
    total = query.count()
    activities = query.offset(offset).limit(limit).all()
    
    # Convert to response format
    result = []
    for activity in activities:
        # Use actual activity name if available, otherwise generate default
        activity_name = activity.name or f"{activity.sport.title()} Activity"
        
        activity_dict = {
            "id": str(activity.id),
            "strava_id": None,  # Add if needed
            "name": activity_name,
            "distance": float(activity.distance_m) if activity.distance_m else 0.0,
            "moving_time": activity.duration_s or 0,
            "start_date": activity.start_time.isoformat(),
            "average_speed": float(activity.average_speed) if activity.average_speed else 0.0,
            "max_hr": activity.max_hr,
            "average_heartrate": activity.avg_hr,
            "average_cadence": None,  # Calculate from splits if needed
            "total_elevation_gain": float(activity.total_elevation_gain) if activity.total_elevation_gain else None,
            "pace_per_mile": None,  # Calculate if needed
            "duration_formatted": None,  # Format if needed
            "splits": None,  # Load splits if needed
            "performance_percentage": activity.performance_percentage,
            "performance_percentage_national": activity.performance_percentage_national,
            "is_race_candidate": activity.is_race_candidate,
            "race_confidence": activity.race_confidence,
        }
        
        # Calculate pace if we have speed
        if activity.average_speed and float(activity.average_speed) > 0:
            pace_per_mile = 26.8224 / float(activity.average_speed)
            minutes = int(pace_per_mile)
            seconds = int(round((pace_per_mile - minutes) * 60))
            activity_dict["pace_per_mile"] = f"{minutes}:{seconds:02d}/mi"
        
        # Format duration
        if activity.duration_s:
            hours = activity.duration_s // 3600
            minutes = (activity.duration_s % 3600) // 60
            secs = activity.duration_s % 60
            if hours > 0:
                activity_dict["duration_formatted"] = f"{hours}:{minutes:02d}:{secs:02d}"
            else:
                activity_dict["duration_formatted"] = f"{minutes}:{secs:02d}"
        
        result.append(ActivityResponse(**activity_dict))
    
    return result


@router.get("/summary", response_model=dict)
def get_activities_summary(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
):
    """
    Get summary statistics for user's activities.
    
    Optimized to use SQL aggregation instead of loading all activities into memory.
    
    Returns:
        - Total activities
        - Total distance
        - Total time
        - Average pace
        - Activities by sport type
        - Activities by run type (if classified)
    """
    from sqlalchemy import func, case
    
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Use SQL aggregation instead of loading all activities
    summary = db.query(
        func.count(Activity.id).label('total_activities'),
        func.sum(Activity.distance_m).label('total_distance_m'),
        func.sum(Activity.duration_s).label('total_duration_s'),
        func.avg(
            case(
                (Activity.average_speed > 0, 26.8224 / Activity.average_speed),
                else_=None
            )
        ).label('avg_pace_per_mile'),
        func.sum(
            case(
                ((Activity.user_verified_race == True) | (Activity.is_race_candidate == True), 1),
                else_=0
            )
        ).label('race_count')
    ).filter(
        Activity.athlete_id == current_user.id,
        Activity.start_time >= cutoff_date
    ).first()
    
    # Get activities by sport (still need to load for grouping)
    activities_by_sport_query = db.query(
        Activity.sport,
        func.count(Activity.id).label('count')
    ).filter(
        Activity.athlete_id == current_user.id,
        Activity.start_time >= cutoff_date
    ).group_by(Activity.sport).all()
    
    sports = {sport or "unknown": count for sport, count in activities_by_sport_query}
    
    total_distance_m = summary.total_distance_m or 0
    total_duration_s = summary.total_duration_s or 0
    
    return {
        "total_activities": summary.total_activities or 0,
        "total_distance_km": round(total_distance_m / 1000, 2),
        "total_distance_miles": round(total_distance_m / 1609.34, 2),
        "total_duration_hours": round(total_duration_s / 3600, 2),
        "average_pace_per_mile": round(float(summary.avg_pace_per_mile), 2) if summary.avg_pace_per_mile else None,
        "activities_by_sport": sports,
        "race_count": summary.race_count or 0,
        "period_days": days,
    }


@router.get("/{activity_id}", response_model=dict)
def get_activity(
    activity_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a single activity by ID with full details.
    
    Includes workout classification, expected RPE, and narrative context.
    Only returns activity if it belongs to the current user.
    """
    from services.workout_classifier import WorkoutClassifierService
    
    activity = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.athlete_id == current_user.id
    ).first()
    
    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found"
        )
    
    # Calculate expected RPE if we have workout classification
    expected_rpe_range = None
    if activity.workout_type:
        try:
            classifier = WorkoutClassifierService(db)
            from services.workout_classifier import WorkoutType
            workout_type = WorkoutType(activity.workout_type)
            duration_min = (activity.duration_s or 0) / 60
            expected_rpe_range = classifier.get_expected_rpe(workout_type, duration_min)
        except (ValueError, Exception):
            pass
    
    # Generate narrative context (ADR-033)
    narrative = None
    if is_feature_enabled("narrative.translation_enabled", str(current_user.id), db):
        try:
            from services.narrative_translator import NarrativeTranslator
            from services.narrative_memory import NarrativeMemory
            
            translator = NarrativeTranslator(db, current_user.id)
            memory = NarrativeMemory(db, current_user.id, use_redis=False)
            
            # Generate workout context narrative
            if activity.workout_type:
                pace = None
                if activity.average_speed and float(activity.average_speed) > 0:
                    pace = 26.8224 / float(activity.average_speed)
                
                narrative_obj = translator.narrate_workout_context(
                    activity.workout_type,
                    activity.name or "Run",
                    pace
                )
                
                if narrative_obj and not memory.recently_shown(narrative_obj.hash, days=7):
                    narrative = narrative_obj.text
                    memory.record_shown(narrative_obj.hash, narrative_obj.signal_type, "activity_detail")
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug(f"Narrative generation failed: {e}")
    
    # Build response
    result = {
        "id": str(activity.id),
        "name": activity.name or "Run",
        "sport_type": activity.sport,
        "start_time": activity.start_time.isoformat() if activity.start_time else None,
        "distance_m": activity.distance_m,
        "elapsed_time_s": activity.duration_s,
        "moving_time_s": activity.duration_s,
        "average_hr": activity.avg_hr,
        "max_hr": activity.max_hr,
        "average_cadence": None,  # Not stored currently
        "total_elevation_gain_m": float(activity.total_elevation_gain) if activity.total_elevation_gain else None,
        "average_temp_c": float(activity.temperature_f - 32) * 5/9 if activity.temperature_f else None,
        "strava_activity_id": activity.external_activity_id if activity.provider == "strava" else None,
        
        # Workout classification
        "workout_type": activity.workout_type,
        "workout_zone": activity.workout_zone,
        "workout_confidence": activity.workout_confidence,
        "intensity_score": activity.intensity_score,
        
        # Expected RPE based on workout type
        "expected_rpe_range": expected_rpe_range,
        
        # Race info
        "is_race": activity.user_verified_race or activity.is_race_candidate,
        "race_confidence": activity.race_confidence,
        "performance_percentage": activity.performance_percentage,
        
        # Environmental context
        "temperature_f": activity.temperature_f,
        "humidity_pct": activity.humidity_pct,
        "weather_condition": activity.weather_condition,
        
        # Narrative context (ADR-033)
        "narrative": narrative,
    }
    
    return result


@router.get("/{activity_id}/attribution")
def get_activity_attribution(
    activity_id: str,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get attribution analysis for a specific activity - "Why This Run?"
    
    Aggregates signals from all analytics methods to explain the run's quality.
    Includes pace decay, TSB status, pre-run state, efficiency comparison, and CS analysis.
    
    ADR-015: Why This Run? Activity Attribution
    
    Requires feature flag: analytics.run_attribution
    """
    from services.run_attribution import get_run_attribution, run_attribution_to_dict
    
    # Check feature flag
    flag_enabled = is_feature_enabled("analytics.run_attribution", str(current_user.id), db)
    
    if not flag_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Run attribution feature is not enabled"
        )
    
    # Validate activity_id format
    try:
        UUID(activity_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid activity ID format"
        )
    
    # Get attribution
    result = get_run_attribution(activity_id, str(current_user.id), db)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found or no attribution available"
        )
    
    return run_attribution_to_dict(result)

