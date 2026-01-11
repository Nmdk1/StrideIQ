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
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import date

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

router = APIRouter(prefix="/v2/plans", tags=["Plan Generation"])


# ============ Request Models ============

class StandardPlanRequest(BaseModel):
    """Request for a standard (free) plan."""
    distance: str = Field(..., description="Goal distance: 5k, 10k, half_marathon, marathon")
    duration_weeks: int = Field(..., ge=4, le=24, description="Plan duration in weeks")
    days_per_week: int = Field(6, ge=4, le=7, description="Running days per week")
    volume_tier: str = Field("mid", description="Volume tier: builder, low, mid, high")
    start_date: Optional[date] = Field(None, description="Plan start date (optional)")


class SemiCustomPlanRequest(BaseModel):
    """Request for a semi-custom plan with personalization."""
    distance: str = Field(..., description="Goal distance: 5k, 10k, half_marathon, marathon")
    race_date: date = Field(..., description="Goal race date")
    days_per_week: int = Field(6, ge=4, le=7, description="Running days per week")
    
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
    
    # Fitness
    current_weekly_miles: float = Field(..., ge=10, le=150)
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
    saved_plan = _save_plan(db, athlete.id, plan)
    
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
    saved_plan = _save_plan(db, athlete.id, plan)
    
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
    )
    
    # Save to database
    saved_plan = _save_plan(db, athlete.id, plan)
    
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


def _save_plan(db: Session, athlete_id: UUID, plan: GeneratedPlan) -> TrainingPlan:
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
    
    db_plan = TrainingPlan(
        athlete_id=athlete_id,
        name=f"{plan.distance.replace('_', ' ').title()} - {plan.duration_weeks}w Plan",
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
