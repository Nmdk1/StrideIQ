"""
Plan Generation API Router (v2)

New plan generation system using the modular framework.

Endpoints for:
- Standard plans (free, fixed templates)
- Semi-custom plans ($5, personalized)
- Custom plans (subscription)
- Plan previews (for review before purchase)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import date, datetime, timedelta

from core.database import get_db
from core.auth import get_current_athlete, get_current_athlete_optional
from models import Athlete, TrainingPlan, PlannedWorkout

from services.plan_framework import (
    PlanGenerator,
    GeneratedPlan,
    VolumeTierClassifier,
    PaceEngine,
    PlanTier,
    VolumeTier,
    Distance,
)
from services.plan_framework.feature_flags import FeatureFlagService
from services.plan_framework.entitlements import EntitlementsService
from services.plan_audit import (
    log_workout_move,
    log_workout_edit,
    log_workout_delete,
    log_workout_add,
    log_workout_swap,
    log_load_adjust,
    _serialize_workout,
)

router = APIRouter(prefix="/v2/plans", tags=["Plan Generation"])


# ============ Request Models ============

class StandardPlanRequest(BaseModel):
    """Request for a standard (free) plan."""
    distance: str = Field(..., description="Goal distance: 5k, 10k, half_marathon, marathon")
    duration_weeks: int = Field(..., ge=4, le=24, description="Plan duration in weeks")
    days_per_week: int = Field(6, ge=4, le=7, description="Running days per week")
    volume_tier: str = Field("mid", description="Volume tier: builder, low, mid, high")
    start_date: Optional[date] = Field(None, description="Plan start date (optional)")
    race_name: Optional[str] = Field(None, description="Goal race name (e.g., 'Boston Marathon')")


class SemiCustomPlanRequest(BaseModel):
    """Request for a semi-custom plan with personalization."""
    distance: str = Field(..., description="Goal distance: 5k, 10k, half_marathon, marathon")
    race_date: date = Field(..., description="Goal race date")
    days_per_week: int = Field(6, ge=4, le=7, description="Running days per week")
    
    # Race info
    race_name: Optional[str] = Field(None, description="Goal race name (e.g., 'Boston Marathon')")
    
    # Current fitness
    current_weekly_miles: float = Field(..., ge=10, le=150, description="Current weekly mileage")
    
    # For pace calculation
    recent_race_distance: Optional[str] = Field(None, description="Recent race distance")
    recent_race_time_seconds: Optional[int] = Field(None, ge=600, description="Recent race time in seconds")
    
    # Optional target
    goal_time_seconds: Optional[int] = Field(None, description="Goal race time in seconds")
    
    # Environment
    race_profile: Optional[str] = Field(None, description="Race profile: flat, hilly, mixed, trail")


class CustomPlanRequest(BaseModel):
    """Request for a fully custom plan (subscription required)."""
    distance: str
    race_date: date
    days_per_week: int = Field(6, ge=4, le=7)

    # Race info
    race_name: Optional[str] = Field(None, description="Goal race name (e.g., 'Boston Marathon')")

    # Fitness
    current_weekly_miles: Optional[float] = Field(None, ge=10, le=150)
    current_long_run_miles: Optional[float] = None

    # Paces
    recent_race_distance: Optional[str] = None
    recent_race_time_seconds: Optional[int] = None

    # Goal
    goal_time_seconds: Optional[int] = None

    # Preferences
    preferred_quality_day: Optional[int] = Field(None, ge=0, le=6, description="0=Mon, 6=Sun")
    preferred_long_run_day: Optional[int] = Field(None, ge=0, le=6)

    # Environment
    race_profile: Optional[str] = None

    # Training history
    injury_history: Optional[Dict[str, Any]] = None


class VolumeTierRequest(BaseModel):
    """Request for volume tier classification."""
    current_weekly_miles: float = Field(..., ge=0, le=200)
    goal_distance: str


# ============ Response Models ============

class PlanPreview(BaseModel):
    """Preview of a generated plan (before saving)."""
    plan_tier: str
    distance: str
    duration_weeks: int
    volume_tier: str
    days_per_week: int
    
    vdot: Optional[float]
    
    start_date: Optional[date]
    end_date: Optional[date]
    race_date: Optional[date]
    
    phases: List[Dict[str, Any]]
    workouts: List[Dict[str, Any]]
    
    weekly_volumes: List[float]
    peak_volume: float
    total_miles: float
    total_quality_sessions: int


class VolumeTierResult(BaseModel):
    """Result of volume tier classification."""
    tier: str
    tier_description: str
    min_weekly_miles: float
    max_weekly_miles: float
    peak_weekly_miles: float
    long_run_peak_miles: float
    cutback_frequency: int


class EntitlementsResponse(BaseModel):
    """Plan entitlements for an athlete."""
    can_generate_standard: bool
    available_distances: List[str]
    
    can_generate_semi_custom: bool
    semi_custom_price: Optional[float]
    
    can_generate_custom: bool
    custom_upgrade_path: Optional[str]
    
    can_use_pace_integration: bool
    can_use_option_ab: bool
    can_use_gpt_coach: bool


# ============ Endpoints ============

@router.get("/entitlements", response_model=EntitlementsResponse)
async def get_entitlements(
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """Get plan generation entitlements for current athlete."""
    flags = FeatureFlagService(db)
    entitlements = EntitlementsService(db, flags)
    
    perms = entitlements.get_plan_entitlements(athlete)
    
    return EntitlementsResponse(
        can_generate_standard=perms.can_generate_standard,
        available_distances=perms.available_distances,
        can_generate_semi_custom=perms.can_generate_semi_custom,
        semi_custom_price=perms.semi_custom_price,
        can_generate_custom=perms.can_generate_custom,
        custom_upgrade_path=perms.custom_upgrade_path,
        can_use_pace_integration=perms.can_use_pace_integration,
        can_use_option_ab=perms.can_use_option_ab,
        can_use_gpt_coach=perms.can_use_gpt_coach,
    )


@router.post("/classify-tier", response_model=VolumeTierResult)
async def classify_volume_tier(
    request: VolumeTierRequest,
    db: Session = Depends(get_db),
):
    """
    Classify an athlete into a volume tier.
    
    This is a public endpoint for the questionnaire.
    """
    classifier = VolumeTierClassifier(db)
    
    tier = classifier.classify(
        current_weekly_miles=request.current_weekly_miles,
        goal_distance=request.goal_distance,
    )
    
    params = classifier.get_tier_params(tier, request.goal_distance)
    description = classifier.get_tier_description(tier)
    
    return VolumeTierResult(
        tier=tier.value,
        tier_description=description,
        min_weekly_miles=params["min_weekly_miles"],
        max_weekly_miles=params["max_weekly_miles"],
        peak_weekly_miles=params["peak_weekly_miles"],
        long_run_peak_miles=params["long_run_peak_miles"],
        cutback_frequency=params["cutback_frequency"],
    )


@router.post("/standard/preview", response_model=PlanPreview)
async def preview_standard_plan(
    request: StandardPlanRequest,
    db: Session = Depends(get_db),
):
    """
    Generate a preview of a standard plan.
    
    This is a public endpoint - no auth required.
    Returns full plan structure for review.
    """
    # Validate inputs
    try:
        Distance(request.distance)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid distance: {request.distance}. Must be one of: 5k, 10k, half_marathon, marathon"
        )
    
    try:
        VolumeTier(request.volume_tier)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid volume_tier: {request.volume_tier}. Must be one of: builder, low, mid, high"
        )
    
    # Generate plan
    generator = PlanGenerator(db)
    plan = generator.generate_standard(
        distance=request.distance,
        duration_weeks=request.duration_weeks,
        tier=request.volume_tier,
        days_per_week=request.days_per_week,
        start_date=request.start_date,
    )
    
    return _plan_to_preview(plan)


@router.post("/standard", response_model=Dict[str, Any])
async def create_standard_plan(
    request: StandardPlanRequest,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Create and save a standard plan for the authenticated athlete.
    """
    # Generate plan
    generator = PlanGenerator(db)
    plan = generator.generate_standard(
        distance=request.distance,
        duration_weeks=request.duration_weeks,
        tier=request.volume_tier,
        days_per_week=request.days_per_week,
        start_date=request.start_date or date.today(),
    )
    
    # Save to database
    saved_plan = _save_plan(db, athlete.id, plan, race_name=request.race_name)
    
    return {
        "success": True,
        "plan_id": str(saved_plan.id),
        "message": f"Created {request.duration_weeks}-week {request.distance} plan",
    }


@router.post("/semi-custom/preview", response_model=PlanPreview)
async def preview_semi_custom_plan(
    request: SemiCustomPlanRequest,
    athlete: Athlete = Depends(get_current_athlete_optional),
    db: Session = Depends(get_db),
):
    """
    Generate a preview of a semi-custom plan.
    
    Includes personalized paces if race time provided.
    Authentication optional for preview.
    """
    # Calculate duration from race date
    today = date.today()
    if request.race_date <= today:
        raise HTTPException(status_code=400, detail="Race date must be in the future")
    
    days_to_race = (request.race_date - today).days
    duration_weeks = min(24, max(4, days_to_race // 7))
    
    # Generate plan
    generator = PlanGenerator(db)
    plan = generator.generate_semi_custom(
        distance=request.distance,
        duration_weeks=duration_weeks,
        current_weekly_miles=request.current_weekly_miles,
        days_per_week=request.days_per_week,
        race_date=request.race_date,
        recent_race_distance=request.recent_race_distance,
        recent_race_time_seconds=request.recent_race_time_seconds,
        athlete_id=athlete.id if athlete else None,
    )
    
    return _plan_to_preview(plan)


@router.post("/semi-custom", response_model=Dict[str, Any])
async def create_semi_custom_plan(
    request: SemiCustomPlanRequest,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Create and save a semi-custom plan.
    
    Requires payment ($5).
    """
    # Check entitlements
    flags = FeatureFlagService(db)
    entitlements = EntitlementsService(db, flags)
    access = entitlements.check_plan_access(athlete, "semi_custom", request.distance, 18)
    
    if not access.allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "reason": access.reason,
                "price": access.price,
                "upgrade_path": access.upgrade_path,
            }
        )
    
    # Calculate duration
    today = date.today()
    days_to_race = (request.race_date - today).days
    duration_weeks = min(24, max(4, days_to_race // 7))
    
    # Generate plan
    generator = PlanGenerator(db)
    plan = generator.generate_semi_custom(
        distance=request.distance,
        duration_weeks=duration_weeks,
        current_weekly_miles=request.current_weekly_miles,
        days_per_week=request.days_per_week,
        race_date=request.race_date,
        recent_race_distance=request.recent_race_distance,
        recent_race_time_seconds=request.recent_race_time_seconds,
        athlete_id=athlete.id,
    )
    
    # Save to database
    saved_plan = _save_plan(db, athlete.id, plan, race_name=request.race_name)
    
    return {
        "success": True,
        "plan_id": str(saved_plan.id),
        "message": f"Created personalized {duration_weeks}-week {request.distance} plan",
        "vdot": plan.vdot,
    }


@router.post("/custom", response_model=Dict[str, Any])
async def create_custom_plan(
    request: CustomPlanRequest,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Create a fully custom plan using all athlete data.
    
    Requires subscription.
    Uses:
    - Auto-detected volume from Strava history
    - Calculated paces from best recent efforts
    - Training history patterns
    """
    # Check entitlements
    flags = FeatureFlagService(db)
    entitlements = EntitlementsService(db, flags)
    access = entitlements.check_plan_access(athlete, "custom", request.distance, 18)
    
    if not access.allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "reason": access.reason,
                "upgrade_path": access.upgrade_path,
            }
        )
    
    # Collect athlete preferences
    preferences = {
        "preferred_quality_day": request.preferred_quality_day,
        "preferred_long_run_day": request.preferred_long_run_day,
        "injury_history": request.injury_history,
        "goal_time_seconds": request.goal_time_seconds,
    }
    
    # Generate plan
    generator = PlanGenerator(db)
    plan = generator.generate_custom(
        distance=request.distance,
        race_date=request.race_date,
        days_per_week=request.days_per_week,
        athlete_id=athlete.id,
        athlete_preferences=preferences,
        recent_race_distance=request.recent_race_distance,
        recent_race_time_seconds=request.recent_race_time_seconds,
    )
    
    # Save to database
    saved_plan = _save_plan(db, athlete.id, plan, race_name=request.race_name)
    
    return {
        "success": True,
        "plan_id": str(saved_plan.id),
        "message": f"Created fully custom {plan.duration_weeks}-week {request.distance} plan",
        "vdot": plan.vdot,
        "detected_weekly_miles": plan.weekly_volumes[0] if plan.weekly_volumes else None,
        "peak_miles": plan.peak_volume,
    }


@router.get("/options")
async def get_plan_options():
    """
    Get available plan options.
    
    Public endpoint showing what plans are available.
    """
    return {
        "distances": [
            {"value": "5k", "label": "5K", "durations": [8, 12]},
            {"value": "10k", "label": "10K", "durations": [8, 12]},
            {"value": "half_marathon", "label": "Half Marathon", "durations": [12, 16]},
            {"value": "marathon", "label": "Marathon", "durations": [12, 18]},
        ],
        "volume_tiers": [
            {"value": "builder", "label": "Building Up", "description": "Currently running 20-35 miles/week"},
            {"value": "low", "label": "Low Volume", "description": "Currently running 35-45 miles/week"},
            {"value": "mid", "label": "Mid Volume", "description": "Currently running 45-60 miles/week"},
            {"value": "high", "label": "High Volume", "description": "Currently running 60+ miles/week"},
        ],
        "days_per_week": [
            {"value": 5, "label": "5 days/week"},
            {"value": 6, "label": "6 days/week (recommended)"},
            {"value": 7, "label": "7 days/week"},
        ],
        "tiers": [
            {"value": "standard", "label": "Standard", "price": 0, "description": "Fixed template, effort descriptions"},
            {"value": "semi_custom", "label": "Semi-Custom", "price": 5, "description": "Personalized paces, fitted to race date"},
            {"value": "custom", "label": "Custom", "price": "subscription", "description": "Full personalization, dynamic adaptation"},
        ],
    }


# ============ Helper Functions ============

def _plan_to_preview(plan: GeneratedPlan) -> PlanPreview:
    """Convert GeneratedPlan to preview response."""
    return PlanPreview(
        plan_tier=plan.plan_tier.value,
        distance=plan.distance,
        duration_weeks=plan.duration_weeks,
        volume_tier=plan.volume_tier,
        days_per_week=plan.days_per_week,
        vdot=plan.vdot,
        start_date=plan.start_date,
        end_date=plan.end_date,
        race_date=plan.race_date,
        phases=[
            {
                "name": p.name,
                "phase_type": p.phase_type.value,
                "weeks": p.weeks,
                "focus": p.focus,
            }
            for p in plan.phases
        ],
        workouts=[
            {
                "week": w.week,
                "day": w.day,
                "day_name": w.day_name,
                "date": w.date.isoformat() if w.date else None,
                "workout_type": w.workout_type,
                "title": w.title,
                "description": w.description,
                "phase": w.phase,
                "phase_name": w.phase_name,
                "distance_miles": w.distance_miles,
                "duration_minutes": w.duration_minutes,
                "pace_description": w.pace_description,
                "segments": w.segments,
                "option": w.option,
                "has_option_b": w.option_b is not None,
            }
            for w in plan.workouts
        ],
        weekly_volumes=plan.weekly_volumes,
        peak_volume=plan.peak_volume,
        total_miles=plan.total_miles,
        total_quality_sessions=plan.total_quality_sessions,
    )


def _save_plan(
    db: Session,
    athlete_id: UUID,
    plan: GeneratedPlan,
    race_name: Optional[str] = None,
) -> TrainingPlan:
    """Save generated plan to database."""
    from models import TrainingPlan, PlannedWorkout
    from services.plan_framework.constants import DISTANCE_METERS

    # Archive any existing active plans
    existing = db.query(TrainingPlan).filter(
        TrainingPlan.athlete_id == athlete_id,
        TrainingPlan.status == "active"
    ).all()

    for p in existing:
        p.status = "archived"

    # Create training plan
    distance_m = DISTANCE_METERS.get(Distance(plan.distance), 42195)

    # Use provided race name, or generate a default
    plan_name = race_name if race_name else f"{plan.distance.replace('_', ' ').title()} - {plan.duration_weeks}w Plan"

    db_plan = TrainingPlan(
        athlete_id=athlete_id,
        name=plan_name,
        goal_race_name=race_name,
        status="active",
        goal_race_date=plan.race_date or plan.end_date,
        goal_race_distance_m=distance_m,
        plan_start_date=plan.start_date,
        plan_end_date=plan.end_date or plan.race_date,
        total_weeks=plan.duration_weeks,
        baseline_vdot=plan.vdot,
        baseline_weekly_volume_km=(plan.weekly_volumes[0] * 1.609) if plan.weekly_volumes else None,
        plan_type=plan.distance,
        generation_method="framework_v2",
    )
    
    db.add(db_plan)
    db.flush()  # Get the plan ID
    
    # Create planned workouts
    for workout in plan.workouts:
        if workout.workout_type == "rest":
            continue  # Don't store rest days
        
        db_workout = PlannedWorkout(
            plan_id=db_plan.id,
            athlete_id=athlete_id,
            scheduled_date=workout.date,
            week_number=workout.week,
            day_of_week=workout.day,
            workout_type=workout.workout_type,
            title=workout.title,
            description=workout.description,
            phase=workout.phase,
            target_duration_minutes=workout.duration_minutes,
            target_distance_km=round(workout.distance_miles * 1.609, 2) if workout.distance_miles else None,
            segments=workout.segments,
            coach_notes=workout.pace_description,
        )
        db.add(db_workout)
    
    db.commit()
    
    return db_plan


def _save_model_driven_plan(
    db: Session,
    athlete_id: UUID,
    plan,  # ModelDrivenPlan from model_driven_plan_generator
) -> TrainingPlan:
    """Save model-driven plan to database with all workouts."""
    from models import TrainingPlan, PlannedWorkout
    from datetime import datetime
    
    # Distance mapping
    DISTANCE_METERS = {
        "5k": 5000,
        "10k": 10000,
        "half_marathon": 21097,
        "marathon": 42195
    }
    
    # Archive any existing active plans
    existing = db.query(TrainingPlan).filter(
        TrainingPlan.athlete_id == athlete_id,
        TrainingPlan.status == "active"
    ).all()
    
    for p in existing:
        p.status = "archived"
    
    # Create training plan
    distance_m = DISTANCE_METERS.get(plan.race_distance, 42195)
    
    # Build plan name
    race_distance_name = plan.race_distance.replace("_", " ").title()
    plan_name = f"Model-Driven {race_distance_name} Plan"
    
    db_plan = TrainingPlan(
        athlete_id=athlete_id,
        name=plan_name,
        status="active",
        goal_race_date=plan.race_date,
        goal_race_distance_m=distance_m,
        plan_start_date=plan.weeks[0].start_date if plan.weeks else None,
        plan_end_date=plan.race_date,
        total_weeks=plan.total_weeks,
        baseline_vdot=plan.prediction.projected_vdot if plan.prediction else None,
        plan_type=plan.race_distance,
        generation_method="model_driven",
    )
    
    db.add(db_plan)
    db.flush()  # Get the plan ID
    
    # Create planned workouts from weeks
    for week in plan.weeks:
        for day in week.days:
            if day.workout_type == "rest":
                continue  # Don't store rest days
            
            # Parse date
            workout_date = datetime.strptime(day.date, "%Y-%m-%d").date() if isinstance(day.date, str) else day.date
            
            # Build personalization notes
            coach_notes_parts = []
            if day.target_pace:
                coach_notes_parts.append(f"Target pace: {day.target_pace}")
            if day.notes:
                coach_notes_parts.extend(day.notes)
            coach_notes = " | ".join(coach_notes_parts) if coach_notes_parts else None
            
            db_workout = PlannedWorkout(
                plan_id=db_plan.id,
                athlete_id=athlete_id,
                scheduled_date=workout_date,
                week_number=week.week_number,
                day_of_week=workout_date.weekday(),
                workout_type=day.workout_type,
                title=day.name,
                description=day.description,
                phase=week.phase,
                target_duration_minutes=int(day.target_tss / 0.8) if day.target_tss else None,  # Rough estimate
                target_distance_km=round(day.target_miles * 1.609, 2) if day.target_miles else None,
                coach_notes=coach_notes,
            )
            db.add(db_workout)
    
    db.commit()
    
    return db_plan


# ============ Plan Management Endpoints ============

class ChangeDateRequest(BaseModel):
    """Request to change the race date."""
    new_race_date: date


class SkipWeekRequest(BaseModel):
    """Request to skip a week."""
    week_number: int


class SwapDaysRequest(BaseModel):
    """Request to swap two workouts."""
    workout_id_1: UUID = Field(..., description="First workout ID")
    workout_id_2: UUID = Field(..., description="Second workout ID")
    reason: Optional[str] = Field(None, description="Optional reason for swap")


class AdjustLoadRequest(BaseModel):
    """Request to adjust training load for a week."""
    week_number: int = Field(..., ge=1, description="Week number to adjust")
    adjustment: str = Field(..., description="Adjustment type: reduce_light, reduce_moderate, increase_light")
    reason: Optional[str] = Field(None, description="Optional reason for adjustment")


class MoveWorkoutRequest(BaseModel):
    """Request to move a workout to a new date."""
    new_date: date = Field(..., description="New date for the workout")


class UpdateWorkoutRequest(BaseModel):
    """Request to update workout details."""
    workout_type: Optional[str] = Field(None, max_length=50, description="New workout type")
    workout_subtype: Optional[str] = Field(None, max_length=50, description="Optional workout subtype (e.g., easy_to_mp)")
    title: Optional[str] = Field(None, max_length=200, description="New title")
    description: Optional[str] = Field(None, max_length=2000, description="New description")
    target_distance_km: Optional[float] = Field(None, ge=0, le=200, description="Target distance in km")
    target_duration_minutes: Optional[int] = Field(None, ge=0, le=600, description="Target duration in minutes")
    coach_notes: Optional[str] = Field(None, max_length=2000, description="Coach notes/pace description")


class AddWorkoutRequest(BaseModel):
    """Request to add a new workout."""
    scheduled_date: date = Field(..., description="Date for the workout")
    workout_type: str = Field(..., max_length=50, description="Workout type")
    title: str = Field(..., max_length=200, description="Workout title")
    description: Optional[str] = Field(None, max_length=2000, description="Workout description")
    target_distance_km: Optional[float] = Field(None, ge=0, le=200, description="Target distance in km")
    target_duration_minutes: Optional[int] = Field(None, ge=0, le=600, description="Target duration in minutes")
    coach_notes: Optional[str] = Field(None, max_length=2000, description="Coach notes/pace description")


@router.post("/{plan_id}/withdraw")
async def withdraw_from_plan(
    plan_id: UUID,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Withdraw from a race / archive a plan.
    
    This archives the plan and removes planned workouts from the calendar.
    Training history is preserved.
    """
    plan = db.query(TrainingPlan).filter(
        TrainingPlan.id == plan_id,
        TrainingPlan.athlete_id == athlete.id,
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    if plan.status == "archived":
        raise HTTPException(status_code=400, detail="Plan is already archived")
    
    # Archive the plan
    plan.status = "archived"
    
    # Mark all future planned workouts as cancelled
    today = date.today()
    db.query(PlannedWorkout).filter(
        PlannedWorkout.plan_id == plan_id,
        PlannedWorkout.scheduled_date >= today,
        PlannedWorkout.completed == False,
    ).update({"skipped": True})
    
    db.commit()
    
    return {
        "success": True,
        "message": "Plan archived. Your training history has been preserved.",
        "plan_id": str(plan_id),
    }


@router.post("/{plan_id}/pause")
async def pause_plan(
    plan_id: UUID,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Pause a training plan.
    
    The plan status is set to 'paused'. When resumed, workouts will be
    recalculated based on the remaining time to the race date.
    """
    plan = db.query(TrainingPlan).filter(
        TrainingPlan.id == plan_id,
        TrainingPlan.athlete_id == athlete.id,
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    if plan.status != "active":
        raise HTTPException(status_code=400, detail=f"Cannot pause plan with status: {plan.status}")
    
    # Pause the plan
    plan.status = "paused"
    
    # Calculate current week for reference
    today = date.today()
    current_workout = db.query(PlannedWorkout).filter(
        PlannedWorkout.plan_id == plan_id,
        PlannedWorkout.scheduled_date <= today,
    ).order_by(PlannedWorkout.scheduled_date.desc()).first()
    
    paused_at_week = current_workout.week_number if current_workout else 1
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Plan paused at week {paused_at_week}. You can resume anytime.",
        "plan_id": str(plan_id),
        "paused_at_week": paused_at_week,
    }


@router.post("/{plan_id}/resume")
async def resume_plan(
    plan_id: UUID,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Resume a paused training plan.
    
    Recalculates remaining workouts based on time to race date.
    """
    plan = db.query(TrainingPlan).filter(
        TrainingPlan.id == plan_id,
        TrainingPlan.athlete_id == athlete.id,
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    if plan.status != "paused":
        raise HTTPException(status_code=400, detail=f"Cannot resume plan with status: {plan.status}")
    
    # Resume the plan
    plan.status = "active"
    
    # TODO: Recalculate future workouts based on remaining time
    # For now, just resume with existing schedule
    
    db.commit()
    
    return {
        "success": True,
        "message": "Plan resumed. Continue where you left off.",
        "plan_id": str(plan_id),
    }


@router.post("/{plan_id}/change-date")
async def change_race_date(
    plan_id: UUID,
    request: ChangeDateRequest,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Change the race date for a plan.
    
    Recalculates all future workouts to peak on the new date.
    """
    plan = db.query(TrainingPlan).filter(
        TrainingPlan.id == plan_id,
        TrainingPlan.athlete_id == athlete.id,
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    if plan.status not in ("active", "paused"):
        raise HTTPException(status_code=400, detail=f"Cannot modify plan with status: {plan.status}")
    
    today = date.today()
    if request.new_race_date <= today:
        raise HTTPException(status_code=400, detail="New race date must be in the future")
    
    old_race_date = plan.goal_race_date
    
    # Update the race date
    plan.goal_race_date = request.new_race_date
    plan.plan_end_date = request.new_race_date
    
    # Calculate date difference
    if old_race_date:
        days_diff = (request.new_race_date - old_race_date).days
        
        # Shift all future workouts by the difference
        future_workouts = db.query(PlannedWorkout).filter(
            PlannedWorkout.plan_id == plan_id,
            PlannedWorkout.scheduled_date >= today,
        ).all()
        
        from datetime import timedelta
        for workout in future_workouts:
            workout.scheduled_date = workout.scheduled_date + timedelta(days=days_diff)
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Race date changed to {request.new_race_date}. Workouts have been adjusted.",
        "plan_id": str(plan_id),
        "new_race_date": request.new_race_date.isoformat(),
    }


@router.post("/{plan_id}/skip-week")
async def skip_week(
    plan_id: UUID,
    request: SkipWeekRequest,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Skip a week in the training plan.
    
    Marks all workouts in the specified week as skipped.
    """
    plan = db.query(TrainingPlan).filter(
        TrainingPlan.id == plan_id,
        TrainingPlan.athlete_id == athlete.id,
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    if plan.status != "active":
        raise HTTPException(status_code=400, detail=f"Cannot modify plan with status: {plan.status}")
    
    # Find workouts for this week
    week_workouts = db.query(PlannedWorkout).filter(
        PlannedWorkout.plan_id == plan_id,
        PlannedWorkout.week_number == request.week_number,
    ).all()
    
    if not week_workouts:
        raise HTTPException(status_code=404, detail=f"Week {request.week_number} not found")
    
    # Mark all as skipped
    skipped_count = 0
    for workout in week_workouts:
        if not workout.completed:
            workout.skipped = True
            skipped_count += 1
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Week {request.week_number} skipped. {skipped_count} workouts marked as skipped.",
        "plan_id": str(plan_id),
        "week_number": request.week_number,
        "workouts_skipped": skipped_count,
    }


@router.get("/{plan_id}")
async def get_plan(
    plan_id: UUID,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Get full plan details.
    
    Returns the plan with all weeks and workouts.
    """
    plan = db.query(TrainingPlan).filter(
        TrainingPlan.id == plan_id,
        TrainingPlan.athlete_id == athlete.id,
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    # Get all workouts grouped by week
    workouts = db.query(PlannedWorkout).filter(
        PlannedWorkout.plan_id == plan_id,
    ).order_by(
        PlannedWorkout.week_number,
        PlannedWorkout.day_of_week,
    ).all()
    
    # Group by week
    weeks: Dict[int, List[Dict[str, Any]]] = {}
    for w in workouts:
        if w.week_number not in weeks:
            weeks[w.week_number] = []
        weeks[w.week_number].append({
            "id": str(w.id),
            "date": w.scheduled_date.isoformat() if w.scheduled_date else None,
            "day_of_week": w.day_of_week,
            "workout_type": w.workout_type,
            "title": w.title,
            "description": w.description,
            "phase": w.phase,
            "target_distance_km": w.target_distance_km,
            "target_duration_minutes": w.target_duration_minutes,
            "coach_notes": w.coach_notes,
            "completed": w.completed,
            "skipped": w.skipped,
        })
    
    return {
        "id": str(plan.id),
        "name": plan.name,
        "status": plan.status,
        "goal_race_name": plan.goal_race_name,
        "goal_race_date": plan.goal_race_date.isoformat() if plan.goal_race_date else None,
        "total_weeks": plan.total_weeks,
        "start_date": plan.plan_start_date.isoformat() if plan.plan_start_date else None,
        "end_date": plan.plan_end_date.isoformat() if plan.plan_end_date else None,
        "baseline_vdot": plan.baseline_vdot,
        "weeks": weeks,
    }


@router.post("/{plan_id}/swap-days")
async def swap_workout_days(
    plan_id: UUID,
    request: SwapDaysRequest,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Swap two workouts between days.
    
    Allows athletes to rearrange their week to accommodate life demands.
    Both workouts must be in the same plan and belong to the athlete.
    """
    plan = db.query(TrainingPlan).filter(
        TrainingPlan.id == plan_id,
        TrainingPlan.athlete_id == athlete.id,
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    if plan.status != "active":
        raise HTTPException(status_code=400, detail=f"Cannot modify plan with status: {plan.status}")
    
    # Get both workouts
    workout1 = db.query(PlannedWorkout).filter(
        PlannedWorkout.id == request.workout_id_1,
        PlannedWorkout.plan_id == plan_id,
        PlannedWorkout.athlete_id == athlete.id,
    ).first()
    
    workout2 = db.query(PlannedWorkout).filter(
        PlannedWorkout.id == request.workout_id_2,
        PlannedWorkout.plan_id == plan_id,
        PlannedWorkout.athlete_id == athlete.id,
    ).first()
    
    if not workout1:
        raise HTTPException(status_code=404, detail="First workout not found")
    if not workout2:
        raise HTTPException(status_code=404, detail="Second workout not found")
    
    # Don't allow swapping completed workouts
    if workout1.completed:
        raise HTTPException(status_code=400, detail="Cannot swap a completed workout")
    if workout2.completed:
        raise HTTPException(status_code=400, detail="Cannot swap a completed workout")
    
    # Swap the scheduled dates and day_of_week.
    #
    # IMPORTANT: planned_workout has a unique constraint on (plan_id, scheduled_date).
    # A naive swap can violate the constraint during flush (row-by-row UPDATE).
    # Use a temporary date to keep the constraint satisfied throughout the transaction.
    if not workout1.scheduled_date or not workout2.scheduled_date:
        raise HTTPException(status_code=400, detail="Cannot swap workouts without scheduled dates")

    original_date_1 = workout1.scheduled_date
    original_date_2 = workout2.scheduled_date
    original_dow_1 = workout1.day_of_week
    original_dow_2 = workout2.day_of_week

    temp_date = date(1900, 1, 1)
    workout1.scheduled_date = temp_date
    workout1.day_of_week = 0
    db.flush()

    workout2.scheduled_date = original_date_1
    workout2.day_of_week = original_dow_1
    db.flush()
    workout1.scheduled_date = original_date_2
    workout1.day_of_week = original_dow_2
    db.flush()

    # Audit log
    log_workout_swap(
        db=db,
        athlete_id=athlete.id,
        plan_id=plan_id,
        workout1=workout1,
        workout2=workout2,
        reason=request.reason,
    )

    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        # Keep user-facing message clean; log details for diagnosis.
        print(f"ERROR: swap-days IntegrityError: {e}")
        raise HTTPException(status_code=400, detail="Swap failed due to a schedule conflict. Try a different swap.")

    return {
        "success": True,
        "message": f"Swapped {workout1.title} and {workout2.title}",
        "plan_id": str(plan_id),
        "workout_1": {
            "id": str(workout1.id),
            "title": workout1.title,
            "new_date": workout1.scheduled_date.isoformat() if workout1.scheduled_date else None,
        },
        "workout_2": {
            "id": str(workout2.id),
            "title": workout2.title,
            "new_date": workout2.scheduled_date.isoformat() if workout2.scheduled_date else None,
        },
    }


@router.post("/{plan_id}/adjust-load")
async def adjust_week_load(
    plan_id: UUID,
    request: AdjustLoadRequest,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Adjust training load for a specific week.
    
    Options:
    - reduce_light: Convert one quality session to easy, reduce distances by ~10%
    - reduce_moderate: Make it a recovery week (all easy runs, 70% volume)
    - increase_light: Add 1 mile to easy runs (careful progression)
    
    This is for accommodating life demands without abandoning the plan.
    """
    plan = db.query(TrainingPlan).filter(
        TrainingPlan.id == plan_id,
        TrainingPlan.athlete_id == athlete.id,
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    if plan.status != "active":
        raise HTTPException(status_code=400, detail=f"Cannot modify plan with status: {plan.status}")
    
    # Get this week's workouts
    week_workouts = db.query(PlannedWorkout).filter(
        PlannedWorkout.plan_id == plan_id,
        PlannedWorkout.week_number == request.week_number,
        PlannedWorkout.completed == False,
        PlannedWorkout.skipped == False,
    ).all()
    
    if not week_workouts:
        raise HTTPException(status_code=404, detail=f"No modifiable workouts found in week {request.week_number}")
    
    adjustments_made = []
    
    if request.adjustment == "reduce_light":
        # Find one quality session and convert to easy
        quality_types = ["threshold", "tempo", "intervals", "vo2max", "speed", "long_mp", "progression"]
        converted = False
        
        for workout in week_workouts:
            if workout.workout_type in quality_types and not converted:
                old_type = workout.workout_type
                workout.workout_type = "easy"
                workout.title = "Easy Run (adjusted)"
                workout.coach_notes = f"Originally {old_type.replace('_', ' ')}. Adjusted to easy run for recovery."
                converted = True
                adjustments_made.append(f"Converted {old_type} to easy run")
            
            # Reduce all distances by 10%
            if workout.target_distance_km:
                original = workout.target_distance_km
                workout.target_distance_km = round(original * 0.9, 1)
                adjustments_made.append(f"Reduced {workout.workout_type} from {original}km to {workout.target_distance_km}km")
    
    elif request.adjustment == "reduce_moderate":
        # Recovery week: all easy runs at 70% volume
        for workout in week_workouts:
            # Convert quality to easy
            if workout.workout_type not in ["easy", "recovery", "rest"]:
                workout.workout_type = "easy"
                workout.title = "Easy Recovery Run"
                workout.coach_notes = "Recovery week adjustment. Keep it easy and relaxed."
            
            # Reduce volume to 70%
            if workout.target_distance_km:
                original = workout.target_distance_km
                workout.target_distance_km = round(original * 0.7, 1)
            
            adjustments_made.append(f"Adjusted {workout.title} for recovery week")
    
    elif request.adjustment == "increase_light":
        # Add 1 mile to easy runs (careful)
        for workout in week_workouts:
            if workout.workout_type in ["easy", "easy_strides", "easy_hills"]:
                if workout.target_distance_km:
                    original = workout.target_distance_km
                    # Add approximately 1 mile (1.6km)
                    workout.target_distance_km = round(original + 1.6, 1)
                    adjustments_made.append(f"Increased {workout.title} from {original}km to {workout.target_distance_km}km")
    
    else:
        raise HTTPException(status_code=400, detail=f"Invalid adjustment type: {request.adjustment}")
    
    # Audit log
    log_load_adjust(
        db=db,
        athlete_id=athlete.id,
        plan_id=plan_id,
        week_number=request.week_number,
        adjustment=request.adjustment,
        affected_workouts=[{"id": str(w.id), "title": w.title} for w in week_workouts],
        reason=request.reason,
    )
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Week {request.week_number} adjusted with {request.adjustment}",
        "plan_id": str(plan_id),
        "week_number": request.week_number,
        "adjustments": adjustments_made,
    }


@router.get("/{plan_id}/week/{week_number}")
async def get_week_workouts(
    plan_id: UUID,
    week_number: int,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Get all workouts for a specific week.
    
    Useful for the adjust plan UI to show what can be swapped/modified.
    """
    plan = db.query(TrainingPlan).filter(
        TrainingPlan.id == plan_id,
        TrainingPlan.athlete_id == athlete.id,
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    workouts = db.query(PlannedWorkout).filter(
        PlannedWorkout.plan_id == plan_id,
        PlannedWorkout.week_number == week_number,
    ).order_by(PlannedWorkout.day_of_week).all()
    
    if not workouts:
        raise HTTPException(status_code=404, detail=f"Week {week_number} not found")
    
    return {
        "plan_id": str(plan_id),
        "week_number": week_number,
        "phase": workouts[0].phase if workouts else None,
        "workouts": [
            {
                "id": str(w.id),
                "date": w.scheduled_date.isoformat() if w.scheduled_date else None,
                "day_of_week": w.day_of_week,
                "day_name": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][w.day_of_week],
                "workout_type": w.workout_type,
                "title": w.title,
                "description": w.description,
                "target_distance_km": w.target_distance_km,
                "target_duration_minutes": w.target_duration_minutes,
                "coach_notes": w.coach_notes,
                "completed": w.completed,
                "skipped": w.skipped,
            }
            for w in workouts
        ],
    }


# ============ Full Workout Control (Paid Tier) ============

def _check_paid_tier(athlete: Athlete, db: Session) -> bool:
    """Check if athlete has paid tier access for plan modifications."""
    # Check subscription tier
    if athlete.subscription_tier in ("pro", "elite", "premium", "guided", "subscription"):
        return True
    
    # Check if they have any paid plans (semi-custom or custom)
    from models import TrainingPlan
    paid_plan = db.query(TrainingPlan).filter(
        TrainingPlan.athlete_id == athlete.id,
        TrainingPlan.generation_method.in_(["semi_custom", "custom", "framework_v2"]),
    ).first()
    
    return paid_plan is not None


@router.post("/{plan_id}/workouts/{workout_id}/move")
async def move_workout(
    plan_id: UUID,
    workout_id: UUID,
    request: MoveWorkoutRequest,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Move a workout to a new date.
    
    PAID TIER ONLY.
    
    Allows athletes to reschedule workouts to accommodate life demands.
    The original date becomes available (rest day).
    """
    if not _check_paid_tier(athlete, db):
        raise HTTPException(
            status_code=403,
            detail="Plan modification requires a paid subscription. Upgrade to unlock full control."
        )
    
    plan = db.query(TrainingPlan).filter(
        TrainingPlan.id == plan_id,
        TrainingPlan.athlete_id == athlete.id,
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    if plan.status != "active":
        raise HTTPException(status_code=400, detail=f"Cannot modify plan with status: {plan.status}")
    
    workout = db.query(PlannedWorkout).filter(
        PlannedWorkout.id == workout_id,
        PlannedWorkout.plan_id == plan_id,
        PlannedWorkout.athlete_id == athlete.id,
    ).first()
    
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    
    if workout.completed:
        raise HTTPException(status_code=400, detail="Cannot move a completed workout")
    
    # Check if new date is within plan bounds
    if plan.plan_start_date and request.new_date < plan.plan_start_date:
        raise HTTPException(status_code=400, detail="New date is before plan start")
    if plan.plan_end_date and request.new_date > plan.plan_end_date:
        raise HTTPException(status_code=400, detail="New date is after plan end")
    
    old_date = workout.scheduled_date
    
    # Update the workout
    workout.scheduled_date = request.new_date
    workout.day_of_week = request.new_date.weekday()
    
    # Recalculate week number based on plan start
    if plan.plan_start_date:
        days_from_start = (request.new_date - plan.plan_start_date).days
        workout.week_number = (days_from_start // 7) + 1
    
    # Audit log
    log_workout_move(
        db=db,
        athlete_id=athlete.id,
        plan_id=plan_id,
        workout=workout,
        old_date=old_date,
        new_date=request.new_date,
    )
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Moved '{workout.title}' to {request.new_date.isoformat()}",
        "workout": {
            "id": str(workout.id),
            "title": workout.title,
            "old_date": old_date.isoformat() if old_date else None,
            "new_date": request.new_date.isoformat(),
            "new_day": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][workout.day_of_week],
        },
    }


@router.put("/{plan_id}/workouts/{workout_id}")
async def update_workout(
    plan_id: UUID,
    workout_id: UUID,
    request: UpdateWorkoutRequest,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Update workout details.
    
    PAID TIER ONLY.
    
    Allows athletes to change workout type, distance, duration, and notes.
    """
    if not _check_paid_tier(athlete, db):
        raise HTTPException(
            status_code=403,
            detail="Plan modification requires a paid subscription. Upgrade to unlock full control."
        )
    
    plan = db.query(TrainingPlan).filter(
        TrainingPlan.id == plan_id,
        TrainingPlan.athlete_id == athlete.id,
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    if plan.status != "active":
        raise HTTPException(status_code=400, detail=f"Cannot modify plan with status: {plan.status}")
    
    workout = db.query(PlannedWorkout).filter(
        PlannedWorkout.id == workout_id,
        PlannedWorkout.plan_id == plan_id,
        PlannedWorkout.athlete_id == athlete.id,
    ).first()
    
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    
    if workout.completed:
        raise HTTPException(status_code=400, detail="Cannot modify a completed workout")
    
    # Capture before state for audit
    before_snapshot = _serialize_workout(workout)
    
    changes = []
    
    def _normalize_text(v: Optional[str]) -> Optional[str]:
        """
        Fix common mojibake sequences seen when UTF-8 is mis-decoded.

        Example: 'easyâ†’MP' should be 'easy→MP'
        """
        if v is None:
            return None
        return (
            v.replace("â†’", "→")
            .replace("â†’", "→")
        )

    if request.workout_type is not None:
        old_type = workout.workout_type
        workout.workout_type = request.workout_type
        changes.append(f"type: {old_type} → {request.workout_type}")
    
    if request.workout_subtype is not None:
        old_sub = workout.workout_subtype
        workout.workout_subtype = request.workout_subtype
        changes.append(f"subtype: {old_sub} → {request.workout_subtype}")

    if request.title is not None:
        workout.title = _normalize_text(request.title)
        changes.append(f"title updated")
    
    if request.description is not None:
        workout.description = _normalize_text(request.description)
        changes.append(f"description updated")
    
    if request.target_distance_km is not None:
        old_dist = workout.target_distance_km
        workout.target_distance_km = request.target_distance_km
        changes.append(f"distance: {old_dist}km → {request.target_distance_km}km")
    
    if request.target_duration_minutes is not None:
        workout.target_duration_minutes = request.target_duration_minutes
        changes.append(f"duration updated")
    
    if request.coach_notes is not None:
        workout.coach_notes = _normalize_text(request.coach_notes)
        changes.append(f"notes updated")
    
    # Audit log
    log_workout_edit(
        db=db,
        athlete_id=athlete.id,
        plan_id=plan_id,
        workout=workout,
        before_snapshot=before_snapshot,
        changes=changes,
    )
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Updated '{workout.title}'",
        "changes": changes,
        "workout": {
            "id": str(workout.id),
            "title": workout.title,
            "workout_type": workout.workout_type,
            "target_distance_km": workout.target_distance_km,
            "target_duration_minutes": workout.target_duration_minutes,
            "coach_notes": workout.coach_notes,
        },
    }


@router.delete("/{plan_id}/workouts/{workout_id}")
async def delete_workout(
    plan_id: UUID,
    workout_id: UUID,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Delete (skip) a workout.
    
    PAID TIER ONLY.
    
    Marks the workout as skipped. It will still appear in history but
    won't show on the calendar as pending.
    """
    if not _check_paid_tier(athlete, db):
        raise HTTPException(
            status_code=403,
            detail="Plan modification requires a paid subscription. Upgrade to unlock full control."
        )
    
    plan = db.query(TrainingPlan).filter(
        TrainingPlan.id == plan_id,
        TrainingPlan.athlete_id == athlete.id,
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    if plan.status != "active":
        raise HTTPException(status_code=400, detail=f"Cannot modify plan with status: {plan.status}")
    
    workout = db.query(PlannedWorkout).filter(
        PlannedWorkout.id == workout_id,
        PlannedWorkout.plan_id == plan_id,
        PlannedWorkout.athlete_id == athlete.id,
    ).first()
    
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    
    if workout.completed:
        raise HTTPException(status_code=400, detail="Cannot delete a completed workout")
    
    # Audit log (before marking skipped)
    log_workout_delete(
        db=db,
        athlete_id=athlete.id,
        plan_id=plan_id,
        workout=workout,
    )
    
    workout.skipped = True
    db.commit()
    
    return {
        "success": True,
        "message": f"Removed '{workout.title}' from plan",
        "workout_id": str(workout_id),
    }


@router.post("/{plan_id}/workouts")
async def add_workout(
    plan_id: UUID,
    request: AddWorkoutRequest,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Add a new workout to the plan.
    
    PAID TIER ONLY.
    
    Allows athletes to add custom workouts on rest days or any date.
    """
    if not _check_paid_tier(athlete, db):
        raise HTTPException(
            status_code=403,
            detail="Plan modification requires a paid subscription. Upgrade to unlock full control."
        )
    
    plan = db.query(TrainingPlan).filter(
        TrainingPlan.id == plan_id,
        TrainingPlan.athlete_id == athlete.id,
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    if plan.status != "active":
        raise HTTPException(status_code=400, detail=f"Cannot modify plan with status: {plan.status}")
    
    # Check if date is within plan bounds
    if plan.plan_start_date and request.scheduled_date < plan.plan_start_date:
        raise HTTPException(status_code=400, detail="Date is before plan start")
    if plan.plan_end_date and request.scheduled_date > plan.plan_end_date:
        raise HTTPException(status_code=400, detail="Date is after plan end")
    
    # Calculate week number
    week_number = 1
    if plan.plan_start_date:
        days_from_start = (request.scheduled_date - plan.plan_start_date).days
        week_number = (days_from_start // 7) + 1
    
    # Determine phase from nearby workouts
    nearby = db.query(PlannedWorkout).filter(
        PlannedWorkout.plan_id == plan_id,
        PlannedWorkout.week_number == week_number,
    ).first()
    phase = nearby.phase if nearby else "custom"
    
    # Create the workout
    new_workout = PlannedWorkout(
        plan_id=plan_id,
        athlete_id=athlete.id,
        scheduled_date=request.scheduled_date,
        week_number=week_number,
        day_of_week=request.scheduled_date.weekday(),
        workout_type=request.workout_type,
        title=request.title,
        description=request.description,
        phase=phase,
        target_distance_km=request.target_distance_km,
        target_duration_minutes=request.target_duration_minutes,
        coach_notes=request.coach_notes,
    )
    
    db.add(new_workout)
    db.flush()  # Get the ID before commit
    
    # Audit log
    log_workout_add(
        db=db,
        athlete_id=athlete.id,
        plan_id=plan_id,
        workout=new_workout,
    )
    
    db.commit()
    db.refresh(new_workout)
    
    return {
        "success": True,
        "message": f"Added '{request.title}' on {request.scheduled_date.isoformat()}",
        "workout": {
            "id": str(new_workout.id),
            "date": request.scheduled_date.isoformat(),
            "day": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][new_workout.day_of_week],
            "week_number": week_number,
            "title": request.title,
            "workout_type": request.workout_type,
        },
    }


@router.get("/{plan_id}/workout-types")
async def get_workout_types(
    plan_id: UUID,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Get available workout types for plan modification.
    
    Returns a list of workout types the athlete can use when modifying their plan.
    """
    # Verify plan ownership
    plan = db.query(TrainingPlan).filter(
        TrainingPlan.id == plan_id,
        TrainingPlan.athlete_id == athlete.id,
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    return {
        "workout_types": [
            {"value": "easy", "label": "Easy Run", "description": "Conversational pace, recovery"},
            {"value": "easy_strides", "label": "Easy + Strides", "description": "Easy run with strides at end"},
            {"value": "recovery", "label": "Recovery Run", "description": "Very easy, short duration"},
            {"value": "long", "label": "Long Run", "description": "Extended aerobic run"},
            {"value": "long_mp", "label": "Long Run w/ MP", "description": "Long run with marathon pace segments"},
            {"value": "medium_long", "label": "Medium-Long Run", "description": "70-75% of long run distance"},
            {"value": "progression", "label": "Progression Run", "description": "Starts easy and builds (e.g., easy → MP)"},
            {"value": "threshold", "label": "Threshold/Tempo", "description": "Comfortably hard, lactate threshold"},
            {"value": "tempo", "label": "Tempo Run", "description": "Sustained threshold effort"},
            {"value": "intervals", "label": "Intervals", "description": "High intensity repeats"},
            {"value": "hills", "label": "Hill Workout", "description": "Hill repeats or hilly route"},
            {"value": "speed", "label": "Speed Work", "description": "Fast repeats, short recovery"},
            {"value": "cross_train", "label": "Cross Training", "description": "Bike, swim, elliptical, etc."},
            {"value": "strength", "label": "Strength/Gym", "description": "Weight training, core work"},
            {"value": "rest", "label": "Rest Day", "description": "Full rest, no running"},
        ],
        "can_modify": _check_paid_tier(athlete, db),
    }


# ============ Model-Driven Plan Generation (ADR-025) ============

class TuneUpRace(BaseModel):
    """A tune-up race before the goal race."""
    race_date: date = Field(..., description="Tune-up race date", alias="date")
    distance: str = Field(..., description="Distance: 5k, 10k, 10_mile, half_marathon")
    name: Optional[str] = Field(None, description="Race name")
    purpose: str = Field("tune_up", description="Purpose: tune_up, threshold, sharpening, fitness_check")
    
    class Config:
        populate_by_name = True


class ModelDrivenPlanRequest(BaseModel):
    """Request for model-driven personalized plan (ADR-022, ADR-025)."""
    race_date: date = Field(..., description="Target race date")
    race_distance: str = Field(..., description="Race distance: 5k, 10k, half_marathon, marathon")
    goal_time_seconds: Optional[int] = Field(None, ge=600, description="Goal race time in seconds")
    force_recalibrate: bool = Field(False, description="Force model recalibration")
    tune_up_races: Optional[List[TuneUpRace]] = Field(None, description="Tune-up races before goal race")


class ModelDrivenPlanResponse(BaseModel):
    """Response for model-driven plan generation."""
    plan_id: str
    race: Dict[str, Any]
    prediction: Dict[str, Any]
    model: Dict[str, Any]
    personalization: Dict[str, Any]
    weeks: List[Dict[str, Any]]
    generated_at: str


# Rate limiting storage (in-memory, replace with Redis in production)
_model_plan_rate_limit: Dict[str, List[datetime]] = {}
MODEL_PLAN_RATE_LIMIT = 5  # 5 requests per day


def _check_rate_limit(athlete_id: str) -> bool:
    """Check if athlete has exceeded rate limit."""
    from datetime import datetime, timedelta
    
    now = datetime.now()
    cutoff = now - timedelta(hours=24)
    
    if athlete_id not in _model_plan_rate_limit:
        _model_plan_rate_limit[athlete_id] = []
    
    # Clean old entries
    _model_plan_rate_limit[athlete_id] = [
        t for t in _model_plan_rate_limit[athlete_id] if t > cutoff
    ]
    
    return len(_model_plan_rate_limit[athlete_id]) < MODEL_PLAN_RATE_LIMIT


def _record_rate_limit(athlete_id: str) -> None:
    """Record a rate limit hit."""
    from datetime import datetime
    
    if athlete_id not in _model_plan_rate_limit:
        _model_plan_rate_limit[athlete_id] = []
    
    _model_plan_rate_limit[athlete_id].append(datetime.now())


@router.post("/model-driven", response_model=Dict[str, Any])
async def create_model_driven_plan(
    request: ModelDrivenPlanRequest,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Generate a model-driven personalized plan (ADR-022, ADR-025).
    
    Uses the Individual Performance Model to:
    1. Calibrate τ1/τ2 from your training history
    2. Calculate optimal load trajectory
    3. Personalize taper based on pre-race fingerprint
    4. Predict race time from fitness trajectory
    
    ELITE TIER ONLY. Rate limited to 5 requests/day.
    """
    import logging
    from datetime import datetime
    
    logger = logging.getLogger(__name__)
    start_time = datetime.now()
    
    # Check feature flag
    flags = FeatureFlagService(db)
    if not flags.is_enabled("plan.model_driven_generation", athlete):
        raise HTTPException(
            status_code=403,
            detail={
                "reason": "Model-driven plans require Elite subscription",
                "upgrade_path": "/pricing"
            }
        )
    
    # Check tier
    if athlete.subscription_tier not in ("elite", "premium", "guided"):
        raise HTTPException(
            status_code=403,
            detail={
                "reason": "Model-driven plans require Elite subscription",
                "upgrade_path": "/pricing"
            }
        )
    
    # Check rate limit
    if not _check_rate_limit(str(athlete.id)):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Maximum 5 model-driven plans per day."
        )
    
    # Validate inputs
    valid_distances = ["5k", "10k", "half_marathon", "marathon"]
    if request.race_distance.lower() not in valid_distances:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid race_distance. Must be one of: {', '.join(valid_distances)}"
        )
    
    today = date.today()
    if request.race_date <= today:
        raise HTTPException(
            status_code=400,
            detail="Race date must be in the future"
        )
    
    max_weeks = 52
    weeks_to_race = (request.race_date - today).days // 7
    if weeks_to_race > max_weeks:
        raise HTTPException(
            status_code=400,
            detail=f"Race date too far in future (max {max_weeks} weeks)"
        )
    
    if weeks_to_race < 4:
        raise HTTPException(
            status_code=400,
            detail="Race date too close (minimum 4 weeks)"
        )
    
    # Validate tune-up races if provided
    tune_ups = None
    if request.tune_up_races:
        tune_ups = []
        for tr in request.tune_up_races:
            if tr.race_date >= request.race_date:
                raise HTTPException(
                    status_code=400,
                    detail=f"Tune-up race on {tr.race_date} must be before goal race on {request.race_date}"
                )
            if tr.race_date <= today:
                raise HTTPException(
                    status_code=400,
                    detail=f"Tune-up race on {tr.race_date} must be in the future"
                )
            tune_ups.append({
                "date": tr.race_date,
                "distance": tr.distance,
                "name": tr.name,
                "purpose": tr.purpose
            })
    
    # Generate plan
    try:
        from services.model_driven_plan_generator import generate_model_driven_plan
        
        plan = generate_model_driven_plan(
            athlete_id=athlete.id,
            race_date=request.race_date,
            race_distance=request.race_distance.lower(),
            db=db,
            goal_time_seconds=request.goal_time_seconds,
            tune_up_races=tune_ups
        )
        
        # Save plan to database
        saved_plan = _save_model_driven_plan(db, athlete.id, plan)
        
        # Record rate limit
        _record_rate_limit(str(athlete.id))
        
        # Log success
        gen_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Model-driven plan generated for {athlete.id} in {gen_time:.2f}s, saved as {saved_plan.id}")
        
        # Convert to response
        return {
            "plan_id": str(saved_plan.id),
            "race": {
                "date": plan.race_date.isoformat(),
                "distance": plan.race_distance,
                "distance_m": plan.race_distance_m
            },
            "prediction": plan.prediction.to_dict(),
            "model": {
                "confidence": plan.model_confidence,
                "tau1": round(plan.tau1, 1),
                "tau2": round(plan.tau2, 1),
                "insights": _generate_model_insights(plan.tau1, plan.tau2)
            },
            "personalization": {
                "taper_start_week": plan.taper_start_week,
                "notes": plan.counter_conventional_notes,
                "summary": plan.personalization_summary
            },
            "weeks": [w.to_dict() for w in plan.weeks],
            "summary": {
                "total_weeks": plan.total_weeks,
                "total_miles": round(plan.total_miles, 1),
                "total_tss": round(plan.total_tss, 0)
            },
            "generated_at": plan.created_at.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Model-driven plan generation failed for {athlete.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Plan generation failed: {str(e)}"
        )


def _generate_model_insights(tau1: float, tau2: float) -> List[str]:
    """Generate human-readable insights from model parameters."""
    insights = []
    
    if tau1 < 38:
        insights.append(f"You adapt faster than average (τ1={tau1:.0f} vs typical 42 days)")
    elif tau1 > 46:
        insights.append(f"You benefit from longer training blocks (τ1={tau1:.0f} vs typical 42 days)")
    
    if tau2 < 6:
        insights.append(f"You recover quickly from fatigue (τ2={tau2:.0f} vs typical 7 days)")
    elif tau2 > 9:
        insights.append(f"You need extra recovery time (τ2={tau2:.0f} vs typical 7 days)")
    
    # Optimal taper insight
    optimal_taper = int(2.0 * tau2)
    optimal_taper = max(7, min(21, optimal_taper))
    insights.append(f"Your optimal taper length: {optimal_taper} days")
    
    return insights


@router.get("/model-driven/preview")
async def preview_model_driven_plan(
    race_date: date,
    race_distance: str,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Preview model insights without generating full plan.
    
    Returns model parameters and prediction without consuming rate limit.
    Useful for UI to show "what you'll get" before generating.
    """
    from services.model_cache import get_or_calibrate_model_cached
    from services.race_predictor import predict_race_time
    
    # Get cached model (don't force recalibrate for preview)
    model = get_or_calibrate_model_cached(athlete.id, db, force_recalibrate=False)
    
    # Get race prediction
    distance_m = {"5k": 5000, "10k": 10000, "half_marathon": 21097, "marathon": 42195}
    prediction = predict_race_time(athlete.id, race_date, distance_m.get(race_distance.lower(), 42195), db)
    
    return {
        "model": {
            "confidence": model.confidence.value,
            "tau1": round(model.tau1, 1),
            "tau2": round(model.tau2, 1),
            "insights": _generate_model_insights(model.tau1, model.tau2),
            "can_calibrate": model.n_performance_markers >= 3
        },
        "prediction": prediction.to_dict() if prediction else None,
        "race_date": race_date.isoformat(),
        "race_distance": race_distance
    }


# ============ Constraint-Aware Plan Generation (ADR-030, ADR-031) ============

class ConstraintAwarePlanRequest(BaseModel):
    """Request for constraint-aware personalized plan (ADR-030, ADR-031).
    
    The Fitness Bank Framework analyzes your full training history to build
    plans that respect your constraints while targeting your proven peak.
    """
    race_date: date = Field(..., description="Target race date")
    race_distance: str = Field(..., description="Race distance: 5k, 10k, 10_mile, half_marathon, marathon")
    goal_time_seconds: Optional[int] = Field(None, ge=600, description="Goal race time in seconds")
    tune_up_races: Optional[List[TuneUpRace]] = Field(None, description="Tune-up races before goal race")
    race_name: Optional[str] = Field(None, description="Goal race name")


def _save_constraint_aware_plan(
    db: Session,
    athlete_id: UUID,
    plan,  # ConstraintAwarePlan from constraint_aware_planner
    race_name: Optional[str] = None,
) -> TrainingPlan:
    """Save constraint-aware plan to database with all workouts."""
    from models import TrainingPlan, PlannedWorkout
    from datetime import datetime
    
    # Distance mapping
    DISTANCE_METERS = {
        "5k": 5000,
        "10k": 10000,
        "10_mile": 16093,
        "half_marathon": 21097,
        "half": 21097,
        "marathon": 42195
    }
    
    # Archive any existing active plans
    existing = db.query(TrainingPlan).filter(
        TrainingPlan.athlete_id == athlete_id,
        TrainingPlan.status == "active"
    ).all()
    
    for p in existing:
        p.status = "archived"
    
    # Create training plan
    distance_m = DISTANCE_METERS.get(plan.race_distance, 42195)
    
    # Build plan name
    race_distance_name = plan.race_distance.replace("_", " ").title()
    plan_name = race_name if race_name else f"Constraint-Aware {race_distance_name} Plan"
    
    # Get fitness bank summary
    fb = plan.fitness_bank
    
    db_plan = TrainingPlan(
        athlete_id=athlete_id,
        name=plan_name,
        goal_race_name=race_name,
        status="active",
        goal_race_date=plan.race_date,
        goal_race_distance_m=distance_m,
        plan_start_date=plan.weeks[0].start_date if plan.weeks else None,
        plan_end_date=plan.race_date,
        total_weeks=plan.total_weeks,
        baseline_vdot=fb.get("best_vdot") if isinstance(fb, dict) else None,
        baseline_weekly_volume_km=round(fb.get("peak", {}).get("weekly_miles", 0) * 1.609, 1) if isinstance(fb, dict) else None,
        plan_type=plan.race_distance,
        generation_method="constraint_aware",
    )
    
    db.add(db_plan)
    db.flush()  # Get the plan ID
    
    # Create planned workouts from weeks
    for week in plan.weeks:
        for day in week.days:
            if day.workout_type == "rest":
                continue  # Don't store rest days
            
            # Calculate date for this day
            workout_date = week.start_date + timedelta(days=day.day_of_week)
            
            # Build coach notes from paces and notes
            coach_notes_parts = []
            if day.paces:
                pace_str = ", ".join(f"{k}: {v}/mi" for k, v in day.paces.items())
                coach_notes_parts.append(f"Paces: {pace_str}")
            if day.notes:
                coach_notes_parts.extend(day.notes)
            coach_notes = " | ".join(coach_notes_parts) if coach_notes_parts else None
            
            # Map intensity to phase for display
            phase_map = {
                "rebuild_easy": "rebuild",
                "rebuild_strides": "rebuild", 
                "build_t": "build",
                "build_mp": "build",
                "build_mixed": "build",
                "recovery": "recovery",
                "peak": "peak",
                "sharpen": "peak",
                "taper_1": "taper",
                "taper_2": "taper",
                "tune_up": "race",
                "race": "race"
            }
            theme_val = week.theme.value if hasattr(week.theme, 'value') else str(week.theme)
            phase = phase_map.get(theme_val, "build")
            
            db_workout = PlannedWorkout(
                plan_id=db_plan.id,
                athlete_id=athlete_id,
                scheduled_date=workout_date,
                week_number=week.week_number,
                day_of_week=day.day_of_week,
                workout_type=day.workout_type,
                title=day.name,
                description=day.description,
                phase=phase,
                target_duration_minutes=int(day.tss_estimate / 0.8) if day.tss_estimate else None,
                target_distance_km=round(day.target_miles * 1.609, 2) if day.target_miles else None,
                coach_notes=coach_notes,
            )
            db.add(db_workout)
    
    db.commit()
    
    return db_plan


@router.post("/constraint-aware", response_model=Dict[str, Any])
async def create_constraint_aware_plan(
    request: ConstraintAwarePlanRequest,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Generate a constraint-aware personalized plan (ADR-030, ADR-031).
    
    Uses the Fitness Bank Framework to:
    1. Analyze your FULL training history (peak capabilities, race performances)
    2. Detect current constraints (injury, reduced volume, time gaps)
    3. Calculate individual τ1/τ2 response characteristics
    4. Generate week themes with proper alternation (T/MP/Recovery)
    5. Prescribe specific workouts ("2x3mi @ 6:25" not "threshold work")
    6. Handle tune-up races with proper coordination
    
    ELITE TIER ONLY. Rate limited to 5 requests/day.
    
    Key Features:
    - Respects your detected training patterns (Sunday long runs, Thursday quality)
    - Injury-aware: protects first 2-3 weeks if returning from break
    - Personal paces from YOUR race performances (VDOT)
    - Counter-conventional insights based on individual τ values
    """
    import logging
    from datetime import datetime
    
    logger = logging.getLogger(__name__)
    start_time = datetime.now()
    
    # Check feature flag
    flags = FeatureFlagService(db)
    if not flags.is_enabled("plan.model_driven_generation", athlete):
        raise HTTPException(
            status_code=403,
            detail={
                "reason": "Constraint-aware plans require Elite subscription",
                "upgrade_path": "/pricing"
            }
        )
    
    # Check tier
    if athlete.subscription_tier not in ("elite", "premium", "guided"):
        raise HTTPException(
            status_code=403,
            detail={
                "reason": "Constraint-aware plans require Elite subscription",
                "upgrade_path": "/pricing"
            }
        )
    
    # Check rate limit
    if not _check_rate_limit(str(athlete.id)):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Maximum 5 plans per day."
        )
    
    # Validate inputs
    valid_distances = ["5k", "10k", "10_mile", "half_marathon", "half", "marathon"]
    if request.race_distance.lower() not in valid_distances:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid race_distance. Must be one of: {', '.join(valid_distances)}"
        )
    
    today = date.today()
    if request.race_date <= today:
        raise HTTPException(
            status_code=400,
            detail="Race date must be in the future"
        )
    
    max_weeks = 52
    weeks_to_race = (request.race_date - today).days // 7
    if weeks_to_race > max_weeks:
        raise HTTPException(
            status_code=400,
            detail=f"Race date too far in future (max {max_weeks} weeks)"
        )
    
    if weeks_to_race < 4:
        raise HTTPException(
            status_code=400,
            detail="Race date too close (minimum 4 weeks)"
        )
    
    # Validate tune-up races if provided
    tune_ups = None
    if request.tune_up_races:
        tune_ups = []
        for tr in request.tune_up_races:
            if tr.race_date >= request.race_date:
                raise HTTPException(
                    status_code=400,
                    detail=f"Tune-up race on {tr.race_date} must be before goal race on {request.race_date}"
                )
            if tr.race_date <= today:
                raise HTTPException(
                    status_code=400,
                    detail=f"Tune-up race on {tr.race_date} must be in the future"
                )
            tune_ups.append({
                "date": tr.race_date,
                "distance": tr.distance,
                "name": tr.name,
                "purpose": tr.purpose
            })
    
    # Generate plan using Constraint-Aware Planner
    try:
        from services.constraint_aware_planner import generate_constraint_aware_plan
        
        plan = generate_constraint_aware_plan(
            athlete_id=athlete.id,
            race_date=request.race_date,
            race_distance=request.race_distance.lower(),
            db=db,
            goal_time=str(request.goal_time_seconds) if request.goal_time_seconds else None,
            tune_up_races=tune_ups
        )
        
        # Save plan to database
        saved_plan = _save_constraint_aware_plan(db, athlete.id, plan, race_name=request.race_name)
        
        # Record rate limit
        _record_rate_limit(str(athlete.id))
        
        # Log success
        gen_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Constraint-aware plan generated for {athlete.id} in {gen_time:.2f}s, saved as {saved_plan.id}")
        
        # Convert to response
        return {
            "success": True,
            "plan_id": str(saved_plan.id),
            "race": {
                "date": plan.race_date.isoformat(),
                "distance": plan.race_distance,
                "name": request.race_name
            },
            "fitness_bank": plan.fitness_bank,
            "model": {
                "confidence": plan.model_confidence,
                "tau1": round(plan.tau1, 1),
                "tau2": round(plan.tau2, 1),
                "insights": _generate_model_insights(plan.tau1, plan.tau2)
            },
            "prediction": {
                "time": plan.predicted_time,
                "confidence_interval": plan.prediction_ci
            },
            "personalization": {
                "notes": plan.counter_conventional_notes,
                "tune_up_races": plan.tune_up_races
            },
            "summary": {
                "total_weeks": plan.total_weeks,
                "total_miles": round(plan.total_miles, 1),
                "peak_miles": round(max(w.total_miles for w in plan.weeks), 1) if plan.weeks else 0
            },
            "weeks": [w.to_dict() for w in plan.weeks],
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Constraint-aware plan generation failed for {athlete.id}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Plan generation failed: {str(e)}"
        )


@router.get("/constraint-aware/preview")
async def preview_constraint_aware_plan(
    race_date: date,
    race_distance: str,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Preview Fitness Bank insights without generating full plan.
    
    Shows what we know about the athlete's capabilities and constraints
    before generating a plan. Does not consume rate limit.
    
    Includes personalized narratives (ADR-033) for key insights.
    """
    from services.fitness_bank import get_fitness_bank
    from core.feature_flags import is_feature_enabled
    
    # Get fitness bank
    bank = get_fitness_bank(athlete.id, db)
    
    # Calculate weeks to race
    today = date.today()
    weeks_to_race = (race_date - today).days // 7
    
    # Generate narratives (ADR-033)
    narratives = []
    if is_feature_enabled("narrative.translation_enabled", str(athlete.id), db):
        try:
            from services.narrative_translator import NarrativeTranslator
            from services.narrative_memory import NarrativeMemory
            from services.training_load import TrainingLoadCalculator
            
            translator = NarrativeTranslator(db, athlete.id)
            memory = NarrativeMemory(db, athlete.id, use_redis=False)
            load_calc = TrainingLoadCalculator(db)
            load = load_calc.calculate_training_load(athlete.id)
            
            if load:
                # Get all applicable narratives
                all_narratives = translator.get_all_narratives(
                    bank,
                    tsb=load.current_tsb,
                    ctl=load.current_ctl,
                    atl=load.current_atl,
                    max_count=4
                )
                
                # Filter to fresh ones and take top 3
                fresh = memory.pick_freshest(all_narratives, count=3)
                
                for n in fresh:
                    narratives.append({"text": n.text, "type": n.signal_type})
                    memory.record_shown(n.hash, n.signal_type, "plan_preview")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Plan preview narrative generation failed for {athlete.id}: {type(e).__name__}: {e}")
            try:
                from services.audit_logger import log_narrative_error
                log_narrative_error(athlete.id, "plan_preview", str(e))
            except Exception:
                pass
    
    return {
        "fitness_bank": bank.to_dict(),
        "narratives": narratives,  # ADR-033
        "race": {
            "date": race_date.isoformat(),
            "distance": race_distance,
            "weeks_out": weeks_to_race
        },
        "model": {
            "tau1": round(bank.tau1, 1),
            "tau2": round(bank.tau2, 1),
            "experience": bank.experience_level.value,
            "insights": _generate_model_insights(bank.tau1, bank.tau2)
        },
        "constraint": {
            "type": bank.constraint_type.value,
            "details": bank.constraint_details,
            "returning": bank.is_returning_from_break
        },
        "projections": {
            "weeks_to_race_ready": bank.weeks_to_race_ready,
            "sustainable_peak": round(bank.sustainable_peak_weekly, 0)
        },
        "patterns": {
            "long_run_day": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][bank.typical_long_run_day] if bank.typical_long_run_day is not None else None,
            "quality_day": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][bank.typical_quality_day] if bank.typical_quality_day is not None else None
        }
    }
