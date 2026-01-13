"""
Home API Router

Provides the "Glance" layer data:
- Today's workout with context
- Yesterday's insight
- Week progress

Tone: Sparse, direct, data-driven. No prescriptiveness.
"""

from datetime import date, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from core.database import get_db
from core.auth import get_current_user
from models import Athlete, Activity, PlannedWorkout, TrainingPlan


router = APIRouter(prefix="/home", tags=["home"])


# --- Response Models ---

class TodayWorkout(BaseModel):
    """Today's planned workout with context."""
    has_workout: bool
    workout_type: Optional[str] = None
    title: Optional[str] = None
    distance_mi: Optional[float] = None
    pace_guidance: Optional[str] = None
    why_context: Optional[str] = None  # "Why this workout" explanation
    week_number: Optional[int] = None
    phase: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class YesterdayInsight(BaseModel):
    """Yesterday's activity with one key insight."""
    has_activity: bool
    activity_name: Optional[str] = None
    activity_id: Optional[str] = None
    distance_mi: Optional[float] = None
    pace_per_mi: Optional[str] = None
    insight: Optional[str] = None  # One sparse insight
    # Fallback: most recent activity if no yesterday activity
    last_activity_date: Optional[str] = None  # ISO date of most recent activity
    last_activity_name: Optional[str] = None
    last_activity_id: Optional[str] = None
    days_since_last: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)


class WeekDay(BaseModel):
    """Single day in week view."""
    date: str
    day_abbrev: str  # M, T, W, etc.
    workout_type: Optional[str] = None
    distance_mi: Optional[float] = None
    completed: bool
    is_today: bool


class WeekProgress(BaseModel):
    """This week's progress."""
    week_number: Optional[int] = None
    total_weeks: Optional[int] = None
    phase: Optional[str] = None
    completed_mi: float
    planned_mi: float
    progress_pct: float
    days: List[WeekDay]
    status: str  # "on_track", "ahead", "behind", "no_plan"
    trajectory_sentence: Optional[str] = None  # One sparse sentence about trajectory
    
    model_config = ConfigDict(from_attributes=True)


class HomeResponse(BaseModel):
    """Complete home page data."""
    today: TodayWorkout
    yesterday: YesterdayInsight
    week: WeekProgress
    strava_connected: bool = False  # Whether user has connected Strava
    has_any_activities: bool = False  # Whether user has any synced activities
    total_activities: int = 0  # Total number of activities
    last_sync: Optional[str] = None  # When Strava was last synced
    
    model_config = ConfigDict(from_attributes=True)


# --- Phase Display Names ---

PHASE_NAMES = {
    'base': 'Base',
    'base_speed': 'Base + Speed',
    'volume_build': 'Volume Build',
    'threshold': 'Threshold',
    'marathon_specific': 'Marathon Specific',
    'race_specific': 'Race Specific',
    'hold': 'Maintenance',
    'taper': 'Taper',
    'race': 'Race Week',
    'recovery': 'Recovery',
}


def format_phase(phase: Optional[str]) -> Optional[str]:
    """Convert internal phase key to display name."""
    if not phase:
        return None
    return PHASE_NAMES.get(phase, phase.replace('_', ' ').title())


def format_pace(seconds_per_mile: float) -> str:
    """Format pace as M:SS/mi."""
    mins = int(seconds_per_mile // 60)
    secs = int(seconds_per_mile % 60)
    return f"{mins}:{secs:02d}/mi"


def generate_why_context(
    workout: PlannedWorkout,
    plan: TrainingPlan,
    week_number: int,
    phase: str,
    recent_similar: Optional[Activity] = None
) -> str:
    """
    Generate sparse, non-prescriptive context for today's workout.
    Tone: Direct, data-driven, no motivation.
    """
    workout_type = workout.workout_type or 'workout'
    phase_display = format_phase(phase)
    
    # Base context on phase and position in plan
    contexts = []
    
    if week_number and plan.total_weeks:
        if week_number <= 2:
            contexts.append(f"Week {week_number}. Building foundation.")
        elif week_number >= plan.total_weeks - 1:
            contexts.append(f"Week {week_number} of {plan.total_weeks}. Final push.")
        else:
            contexts.append(f"Week {week_number} of {plan.total_weeks}.")
    
    if phase_display:
        contexts.append(f"{phase_display} phase.")
    
    # Add workout-specific context
    if 'threshold' in workout_type or 'tempo' in workout_type:
        contexts.append("Builds lactate clearance.")
    elif 'long' in workout_type:
        contexts.append("Builds endurance and fat metabolism.")
    elif 'interval' in workout_type or 'vo2max' in workout_type:
        contexts.append("Builds VO2max capacity.")
    elif 'easy' in workout_type or 'recovery' in workout_type:
        contexts.append("Active recovery day.")
    elif 'strides' in workout_type:
        contexts.append("Neuromuscular activation. Short and quick.")
    
    return " ".join(contexts) if contexts else None


def generate_trajectory_sentence(
    status: str, 
    completed_mi: float, 
    planned_mi: float,
    quality_completed: int = 0,
    quality_planned: int = 0,
    activities_this_week: int = 0
) -> Optional[str]:
    """
    Generate a sparse trajectory sentence.
    Tone: Data speaks. No praise, no prescription.
    """
    remaining = planned_mi - completed_mi
    
    if status == "no_plan":
        # Still provide insight for users without a plan
        if completed_mi > 0:
            if activities_this_week == 1:
                return f"{completed_mi:.0f} mi logged this week. Consistency compounds."
            elif activities_this_week > 1:
                return f"{completed_mi:.0f} mi across {activities_this_week} runs this week."
        return None
    
    if status == "ahead":
        return f"Ahead of schedule. {completed_mi:.0f} mi done of {planned_mi:.0f} mi planned."
    elif status == "on_track":
        return f"On track. {remaining:.0f} mi remaining this week."
    elif status == "behind":
        return f"Behind schedule. {remaining:.0f} mi to go."
    
    return None


def generate_yesterday_insight(activity: Activity) -> str:
    """
    Generate one sparse insight from yesterday's activity.
    Tone: Data speaks. No praise, no prescription.
    """
    insights = []
    
    # Efficiency comparison (if available)
    if hasattr(activity, 'efficiency_score') and activity.efficiency_score:
        if activity.efficiency_score > 0:
            insights.append(f"Efficiency {activity.efficiency_score:+.1f}% vs baseline.")
        elif activity.efficiency_score < 0:
            insights.append(f"Efficiency {activity.efficiency_score:.1f}% vs baseline.")
    
    # Heart rate context
    if activity.avg_hr:
        if activity.avg_hr < 140:
            insights.append(f"HR stayed low ({activity.avg_hr} avg).")
        elif activity.avg_hr > 165:
            insights.append(f"HR ran high ({activity.avg_hr} avg).")
    
    # Pace consistency (if splits available)
    if hasattr(activity, 'pace_variability') and activity.pace_variability:
        if activity.pace_variability < 5:
            insights.append("Consistent pacing.")
        elif activity.pace_variability > 15:
            insights.append("Variable pacing.")
    
    # Default to distance/pace if no other insight
    if not insights:
        if activity.distance_m and activity.duration_s:
            pace_per_mile = (activity.duration_s / (activity.distance_m / 1609.344))
            pace_str = format_pace(pace_per_mile)
            distance_mi = activity.distance_m / 1609.344
            insights.append(f"{distance_mi:.1f} mi at {pace_str}.")
    
    return " ".join(insights[:2]) if insights else None


@router.get("", response_model=HomeResponse)
async def get_home_data(
    db: Session = Depends(get_db),
    current_user: Athlete = Depends(get_current_user)
):
    """
    Get home page data: today's workout, yesterday's insight, week progress.
    """
    today = date.today()
    yesterday = today - timedelta(days=1)
    
    # --- Today's Workout ---
    today_workout = TodayWorkout(has_workout=False)
    
    # Find active plan
    active_plan = db.query(TrainingPlan).filter(
        TrainingPlan.athlete_id == current_user.id,
        TrainingPlan.status == "active"
    ).first()
    
    if active_plan:
        # Find today's planned workout
        planned = db.query(PlannedWorkout).filter(
            PlannedWorkout.plan_id == active_plan.id,
            PlannedWorkout.scheduled_date == today
        ).first()
        
        if planned:
            distance_mi = None
            if planned.target_distance_km:
                distance_mi = planned.target_distance_km * 0.621371
            
            why_context = generate_why_context(
                planned, 
                active_plan,
                planned.week_number,
                planned.phase
            )
            
            today_workout = TodayWorkout(
                has_workout=True,
                workout_type=planned.workout_type,
                title=planned.title,
                distance_mi=round(distance_mi, 1) if distance_mi else None,
                pace_guidance=planned.coach_notes,
                why_context=why_context,
                week_number=planned.week_number,
                phase=format_phase(planned.phase)
            )
    
    # --- Yesterday's Insight ---
    yesterday_insight = YesterdayInsight(has_activity=False)
    
    yesterday_activity = db.query(Activity).filter(
        Activity.athlete_id == current_user.id,
        Activity.start_time >= yesterday,
        Activity.start_time < today
    ).order_by(Activity.start_time.desc()).first()
    
    if yesterday_activity:
        distance_mi = None
        pace_str = None
        
        if yesterday_activity.distance_m:
            distance_mi = yesterday_activity.distance_m / 1609.344
        
        if yesterday_activity.distance_m and yesterday_activity.duration_s:
            pace_per_mile = yesterday_activity.duration_s / (yesterday_activity.distance_m / 1609.344)
            pace_str = format_pace(pace_per_mile)
        
        insight = generate_yesterday_insight(yesterday_activity)
        
        yesterday_insight = YesterdayInsight(
            has_activity=True,
            activity_name=yesterday_activity.name or "Run",
            activity_id=str(yesterday_activity.id),
            distance_mi=round(distance_mi, 1) if distance_mi else None,
            pace_per_mi=pace_str,
            insight=insight
        )
    else:
        # No yesterday activity - find most recent activity for context
        last_activity = db.query(Activity).filter(
            Activity.athlete_id == current_user.id
        ).order_by(Activity.start_time.desc()).first()
        
        if last_activity:
            days_ago = (today - last_activity.start_time.date()).days
            yesterday_insight = YesterdayInsight(
                has_activity=False,
                last_activity_date=last_activity.start_time.date().isoformat(),
                last_activity_name=last_activity.name or "Run",
                last_activity_id=str(last_activity.id),
                days_since_last=days_ago
            )
    
    # --- Week Progress ---
    # Get Monday of current week
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    
    week_days = []
    completed_mi = 0.0
    planned_mi = 0.0
    current_week_number = None
    current_phase = None
    
    for i in range(7):
        day_date = monday + timedelta(days=i)
        day_abbrev = ['M', 'T', 'W', 'T', 'F', 'S', 'S'][i]
        
        # Get planned workout for this day
        planned_workout = None
        if active_plan:
            planned_workout = db.query(PlannedWorkout).filter(
                PlannedWorkout.plan_id == active_plan.id,
                PlannedWorkout.scheduled_date == day_date
            ).first()
        
        # Get actual activity for this day
        actual = db.query(Activity).filter(
            Activity.athlete_id == current_user.id,
            Activity.start_time >= day_date,
            Activity.start_time < day_date + timedelta(days=1)
        ).first()
        
        workout_type = None
        distance_mi = None
        completed = False
        
        if planned_workout:
            workout_type = planned_workout.workout_type
            if planned_workout.target_distance_km:
                planned_mi += planned_workout.target_distance_km * 0.621371
            if day_date == today:
                current_week_number = planned_workout.week_number
                current_phase = planned_workout.phase
        
        if actual:
            completed = True
            if actual.distance_m:
                actual_mi = actual.distance_m / 1609.344
                completed_mi += actual_mi
                distance_mi = round(actual_mi, 1)
        elif planned_workout and planned_workout.target_distance_km:
            distance_mi = round(planned_workout.target_distance_km * 0.621371, 0)
        
        week_days.append(WeekDay(
            date=day_date.isoformat(),
            day_abbrev=day_abbrev,
            workout_type=workout_type,
            distance_mi=distance_mi,
            completed=completed,
            is_today=(day_date == today)
        ))
    
    # Determine status
    if not active_plan:
        status = "no_plan"
    elif planned_mi == 0:
        status = "no_plan"
    else:
        progress_ratio = completed_mi / planned_mi if planned_mi > 0 else 0
        expected_ratio = (today.weekday() + 1) / 7  # How far into the week
        
        if progress_ratio >= expected_ratio * 1.1:
            status = "ahead"
        elif progress_ratio >= expected_ratio * 0.8:
            status = "on_track"
        else:
            status = "behind"
    
    # Count activities this week for trajectory
    activities_this_week = sum(1 for day in week_days if day.completed)
    
    trajectory_sentence = generate_trajectory_sentence(
        status=status,
        completed_mi=round(completed_mi, 1),
        planned_mi=round(planned_mi, 1),
        activities_this_week=activities_this_week
    )
    
    week_progress = WeekProgress(
        week_number=current_week_number,
        total_weeks=active_plan.total_weeks if active_plan else None,
        phase=format_phase(current_phase),
        completed_mi=round(completed_mi, 1),
        planned_mi=round(planned_mi, 1),
        progress_pct=round((completed_mi / planned_mi * 100) if planned_mi > 0 else 0, 0),
        days=week_days,
        status=status,
        trajectory_sentence=trajectory_sentence
    )
    
    # Check Strava connection and activity count
    strava_connected = bool(current_user.strava_access_token)
    
    # Get total activity count
    total_activities = db.query(Activity).filter(
        Activity.athlete_id == current_user.id
    ).count()
    has_any_activities = total_activities > 0
    
    # Last sync time
    last_sync = None
    if current_user.last_strava_sync:
        last_sync = current_user.last_strava_sync.isoformat()
    
    return HomeResponse(
        today=today_workout,
        yesterday=yesterday_insight,
        week=week_progress,
        strava_connected=strava_connected,
        has_any_activities=has_any_activities,
        total_activities=total_activities,
        last_sync=last_sync
    )
