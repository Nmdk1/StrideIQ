"""
Training Plans API Router

Endpoints for:
- Creating training plans
- Viewing plans and workouts
- Calendar view (planned + actual)
- Workout completion tracking
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from uuid import UUID
from datetime import date, datetime, timedelta

from core.database import get_db
from core.auth import get_current_athlete
from models import Athlete, Activity, TrainingPlan, PlannedWorkout
from services.plan_generator import PlanGenerator

router = APIRouter(prefix="/v1/training-plans", tags=["Training Plans"])


# ============ Request/Response Models ============

class CreatePlanRequest(BaseModel):
    """Request to create a new training plan."""
    goal_race_name: str
    goal_race_date: date
    goal_race_distance_m: int
    goal_time_seconds: Optional[int] = None
    plan_start_date: Optional[date] = None


class PlanSummary(BaseModel):
    """Summary view of a training plan."""
    id: str
    name: str
    status: str
    goal_race_name: Optional[str]
    goal_race_date: date
    goal_race_distance_m: int
    goal_time_seconds: Optional[int]
    plan_start_date: date
    plan_end_date: date
    total_weeks: int
    current_week: Optional[int]
    progress_percent: float

    model_config = ConfigDict(from_attributes=True)


class WorkoutSummary(BaseModel):
    """Summary of a planned workout."""
    id: str
    scheduled_date: date
    week_number: int
    workout_type: str
    title: str
    description: Optional[str]
    phase: str
    target_duration_minutes: Optional[int]
    target_distance_km: Optional[float]
    target_pace_per_km_seconds: Optional[int]
    completed: bool
    skipped: bool
    completed_activity_id: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class CalendarDay(BaseModel):
    """A single day in the calendar view."""
    date: date
    planned_workout: Optional[WorkoutSummary]
    actual_activities: List[dict]
    day_of_week: int
    is_today: bool
    is_race_day: bool


class CalendarWeek(BaseModel):
    """A week in the calendar view."""
    week_number: int
    phase: Optional[str]
    days: List[CalendarDay]
    planned_volume_km: float
    actual_volume_km: float


class CalendarResponse(BaseModel):
    """Full calendar response."""
    plan: Optional[PlanSummary]
    weeks: List[CalendarWeek]
    start_date: date
    end_date: date


class WeeklyPlanResponse(BaseModel):
    """Weekly plan view - what to do this week."""
    week_number: int
    phase: str
    phase_week: int
    workouts: List[WorkoutSummary]
    total_planned_duration: int
    total_planned_distance: float
    completed_workouts: int
    skipped_workouts: int


# ============ Endpoints ============

@router.post("", response_model=PlanSummary, status_code=status.HTTP_201_CREATED)
async def create_plan(
    request: CreatePlanRequest,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Create a new training plan.
    
    Generates a full periodized training plan based on:
    - Goal race (distance, date, target time)
    - Athlete's current fitness
    - Training availability preferences
    """
    # Check for existing active plan
    existing = db.query(TrainingPlan).filter(
        TrainingPlan.athlete_id == athlete.id,
        TrainingPlan.status == "active"
    ).first()
    
    if existing:
        # Archive the old plan
        existing.status = "archived"
        db.commit()
    
    # Generate new plan
    generator = PlanGenerator(db)
    plan = generator.generate_plan(
        athlete_id=athlete.id,
        goal_race_name=request.goal_race_name,
        goal_race_date=request.goal_race_date,
        goal_race_distance_m=request.goal_race_distance_m,
        goal_time_seconds=request.goal_time_seconds,
        plan_start_date=request.plan_start_date,
    )
    
    # Calculate current week and progress
    current_week = _calculate_current_week(plan)
    progress = _calculate_progress(plan)
    
    # ADR-065: trigger home briefing refresh on plan creation
    try:
        from tasks.home_briefing_tasks import enqueue_briefing_refresh
        enqueue_briefing_refresh(str(athlete.id))
    except Exception:
        pass

    return PlanSummary(
        id=str(plan.id),
        name=plan.name,
        status=plan.status,
        goal_race_name=plan.goal_race_name,
        goal_race_date=plan.goal_race_date,
        goal_race_distance_m=plan.goal_race_distance_m,
        goal_time_seconds=plan.goal_time_seconds,
        plan_start_date=plan.plan_start_date,
        plan_end_date=plan.plan_end_date,
        total_weeks=plan.total_weeks,
        current_week=current_week,
        progress_percent=progress,
    )


@router.get("/current", response_model=Optional[PlanSummary])
async def get_current_plan(
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """Get the athlete's current active training plan."""
    plan = db.query(TrainingPlan).filter(
        TrainingPlan.athlete_id == athlete.id,
        TrainingPlan.status == "active"
    ).first()
    
    if not plan:
        return None
    
    current_week = _calculate_current_week(plan)
    progress = _calculate_progress(plan)
    
    return PlanSummary(
        id=str(plan.id),
        name=plan.name,
        status=plan.status,
        goal_race_name=plan.goal_race_name,
        goal_race_date=plan.goal_race_date,
        goal_race_distance_m=plan.goal_race_distance_m,
        goal_time_seconds=plan.goal_time_seconds,
        plan_start_date=plan.plan_start_date,
        plan_end_date=plan.plan_end_date,
        total_weeks=plan.total_weeks,
        current_week=current_week,
        progress_percent=progress,
    )


@router.get("/current/week", response_model=Optional[WeeklyPlanResponse])
async def get_current_week(
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """Get this week's workouts from the current plan."""
    plan = db.query(TrainingPlan).filter(
        TrainingPlan.athlete_id == athlete.id,
        TrainingPlan.status == "active"
    ).first()
    
    if not plan:
        return None
    
    # Get current week bounds
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday
    week_end = week_start + timedelta(days=6)  # Sunday
    
    # Get workouts for this week
    workouts = db.query(PlannedWorkout).filter(
        PlannedWorkout.plan_id == plan.id,
        PlannedWorkout.scheduled_date >= week_start,
        PlannedWorkout.scheduled_date <= week_end
    ).order_by(PlannedWorkout.scheduled_date).all()
    
    if not workouts:
        return None
    
    # Get week info from first workout
    first_workout = workouts[0]
    
    workout_summaries = [
        WorkoutSummary(
            id=str(w.id),
            scheduled_date=w.scheduled_date,
            week_number=w.week_number,
            workout_type=w.workout_type,
            title=w.title,
            description=w.description,
            phase=w.phase,
            target_duration_minutes=w.target_duration_minutes,
            target_distance_km=w.target_distance_km,
            target_pace_per_km_seconds=w.target_pace_per_km_seconds,
            completed=w.completed,
            skipped=w.skipped,
            completed_activity_id=str(w.completed_activity_id) if w.completed_activity_id else None,
        )
        for w in workouts
    ]
    
    return WeeklyPlanResponse(
        week_number=first_workout.week_number,
        phase=first_workout.phase,
        phase_week=first_workout.phase_week or 1,
        workouts=workout_summaries,
        total_planned_duration=sum(w.target_duration_minutes or 0 for w in workouts),
        total_planned_distance=sum(w.target_distance_km or 0 for w in workouts),
        completed_workouts=len([w for w in workouts if w.completed]),
        skipped_workouts=len([w for w in workouts if w.skipped]),
    )


@router.get("/calendar")
async def get_calendar(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Get calendar view combining planned workouts and actual activities.
    
    If no dates provided, returns current month.
    """
    # Default to current month
    today = date.today()
    if start_date is None:
        start_date = today.replace(day=1)
    if end_date is None:
        # Last day of month
        if today.month == 12:
            end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    
    # Get current plan
    plan = db.query(TrainingPlan).filter(
        TrainingPlan.athlete_id == athlete.id,
        TrainingPlan.status == "active"
    ).first()
    
    # Get planned workouts in range
    planned = {}
    if plan:
        workouts = db.query(PlannedWorkout).filter(
            PlannedWorkout.plan_id == plan.id,
            PlannedWorkout.scheduled_date >= start_date,
            PlannedWorkout.scheduled_date <= end_date
        ).all()
        
        for w in workouts:
            planned[w.scheduled_date] = w
    
    # Get actual activities in range
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete.id,
        Activity.start_time >= datetime.combine(start_date, datetime.min.time()),
        Activity.start_time <= datetime.combine(end_date, datetime.max.time())
    ).all()
    
    # Group activities by date
    activities_by_date = {}
    for a in activities:
        d = a.start_time.date()
        if d not in activities_by_date:
            activities_by_date[d] = []
        activities_by_date[d].append({
            "id": str(a.id),
            "sport": a.sport,
            "distance_km": round(a.distance_m / 1000, 2) if a.distance_m else None,
            "duration_minutes": a.duration_s // 60 if a.duration_s else None,
            "pace_per_km": a.duration_s / (a.distance_m / 1000) if a.distance_m and a.duration_s else None,
        })
    
    # Build calendar days
    days = []
    current = start_date
    while current <= end_date:
        pw = planned.get(current)
        workout_summary = None
        if pw:
            workout_summary = WorkoutSummary(
                id=str(pw.id),
                scheduled_date=pw.scheduled_date,
                week_number=pw.week_number,
                workout_type=pw.workout_type,
                title=pw.title,
                description=pw.description,
                phase=pw.phase,
                target_duration_minutes=pw.target_duration_minutes,
                target_distance_km=pw.target_distance_km,
                target_pace_per_km_seconds=pw.target_pace_per_km_seconds,
                completed=pw.completed,
                skipped=pw.skipped,
                completed_activity_id=str(pw.completed_activity_id) if pw.completed_activity_id else None,
            )
        
        is_race_day = plan and current == plan.goal_race_date if plan else False
        
        days.append(CalendarDay(
            date=current,
            planned_workout=workout_summary,
            actual_activities=activities_by_date.get(current, []),
            day_of_week=current.weekday(),
            is_today=(current == today),
            is_race_day=is_race_day,
        ))
        
        current += timedelta(days=1)
    
    # Group into weeks
    weeks = []
    current_week_days = []
    current_week_num = 1 if not plan else None
    
    for day in days:
        if day.planned_workout:
            current_week_num = day.planned_workout.week_number
        
        current_week_days.append(day)
        
        # End of week (Sunday) or end of date range
        if day.day_of_week == 6 or day.date == end_date:
            phase = None
            if current_week_days and current_week_days[0].planned_workout:
                phase = current_week_days[0].planned_workout.phase
            
            planned_volume = sum(
                d.planned_workout.target_distance_km or 0
                for d in current_week_days
                if d.planned_workout
            )
            
            actual_volume = sum(
                sum(a.get('distance_km', 0) or 0 for a in d.actual_activities)
                for d in current_week_days
            )
            
            weeks.append(CalendarWeek(
                week_number=current_week_num or 0,
                phase=phase,
                days=current_week_days,
                planned_volume_km=round(planned_volume, 1),
                actual_volume_km=round(actual_volume, 1),
            ))
            
            current_week_days = []
            if current_week_num:
                current_week_num += 1
    
    # Build plan summary
    plan_summary = None
    if plan:
        current_week = _calculate_current_week(plan)
        progress = _calculate_progress(plan)
        plan_summary = PlanSummary(
            id=str(plan.id),
            name=plan.name,
            status=plan.status,
            goal_race_name=plan.goal_race_name,
            goal_race_date=plan.goal_race_date,
            goal_race_distance_m=plan.goal_race_distance_m,
            goal_time_seconds=plan.goal_time_seconds,
            plan_start_date=plan.plan_start_date,
            plan_end_date=plan.plan_end_date,
            total_weeks=plan.total_weeks,
            current_week=current_week,
            progress_percent=progress,
        )
    
    return CalendarResponse(
        plan=plan_summary,
        weeks=weeks,
        start_date=start_date,
        end_date=end_date,
    )


@router.post("/{plan_id}/workouts/{workout_id}/complete")
async def mark_workout_complete(
    plan_id: UUID,
    workout_id: UUID,
    activity_id: Optional[UUID] = None,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """Mark a planned workout as completed, optionally linking to an activity."""
    workout = db.query(PlannedWorkout).filter(
        PlannedWorkout.id == workout_id,
        PlannedWorkout.plan_id == plan_id,
        PlannedWorkout.athlete_id == athlete.id
    ).first()
    
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    
    workout.completed = True
    workout.skipped = False
    if activity_id:
        workout.completed_activity_id = activity_id
    
    db.commit()
    
    return {"status": "completed", "workout_id": str(workout_id)}


@router.post("/{plan_id}/workouts/{workout_id}/skip")
async def skip_workout(
    plan_id: UUID,
    workout_id: UUID,
    reason: Optional[str] = None,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """Mark a planned workout as skipped."""
    workout = db.query(PlannedWorkout).filter(
        PlannedWorkout.id == workout_id,
        PlannedWorkout.plan_id == plan_id,
        PlannedWorkout.athlete_id == athlete.id
    ).first()
    
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    
    workout.skipped = True
    workout.completed = False
    workout.skip_reason = reason
    
    db.commit()
    
    return {"status": "skipped", "workout_id": str(workout_id)}


# ============ Helper Functions ============

def _calculate_current_week(plan: TrainingPlan) -> Optional[int]:
    """Calculate which week of the plan we're currently in."""
    today = date.today()
    
    if today < plan.plan_start_date:
        return 0
    if today > plan.plan_end_date:
        return plan.total_weeks + 1
    
    days_in = (today - plan.plan_start_date).days
    return (days_in // 7) + 1


def _calculate_progress(plan: TrainingPlan) -> float:
    """Calculate plan progress as percentage."""
    today = date.today()
    
    if today < plan.plan_start_date:
        return 0.0
    if today >= plan.plan_end_date:
        return 100.0
    
    total_days = (plan.plan_end_date - plan.plan_start_date).days
    days_in = (today - plan.plan_start_date).days
    
    return round((days_in / total_days) * 100, 1)
