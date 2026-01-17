"""
Home API Router

Provides the "Glance" layer data:
- Today's workout with context (correlation-based when available)
- Yesterday's insight (from InsightAggregator when available)
- Week progress with training load context

Tone: Sparse, direct, data-driven. No prescriptiveness.

ADR-020: Home Experience Phase 1 Enhancement
"""

from datetime import date, timedelta, datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel, ConfigDict
import logging

from core.database import get_db
from core.auth import get_current_user
from core.feature_flags import is_feature_enabled
from models import Athlete, Activity, PlannedWorkout, TrainingPlan, CalendarInsight

logger = logging.getLogger(__name__)

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
    why_source: Optional[str] = None  # "correlation" | "load" | "plan"
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
    tsb_context: Optional[str] = None  # "Fresh" | "Building" | "Fatigued"
    load_trend: Optional[str] = None  # "up" | "stable" | "down"
    
    model_config = ConfigDict(from_attributes=True)


class HomeResponse(BaseModel):
    """Complete home page data."""
    today: TodayWorkout
    yesterday: YesterdayInsight
    week: WeekProgress
    hero_narrative: Optional[str] = None  # Hero sentence for first-3-seconds impact (ADR-033)
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


def get_correlation_context(
    athlete_id: str,
    workout_type: str,
    db: Session
) -> Optional[tuple[str, str]]:
    """
    Get correlation-based context for today's workout.
    
    Checks athlete's stored correlations and returns relevant context
    if a correlation applies to today's workout type.
    
    Only returns context when it's ACTIONABLE and clear.
    Plain language — no percentages or stats jargon.
    
    Returns:
        (context_string, source) or (None, None) if no relevant correlation
    
    Tone: Sparse, plain language. Self-explanatory.
    """
    try:
        from services.correlation_engine import analyze_correlations
        
        # Get recent correlations (cached in production)
        result = analyze_correlations(athlete_id, days=60, db=db)
        
        if 'error' in result or not result.get('correlations'):
            return None, None
        
        correlations = result.get('correlations', [])
        
        # Find the strongest significant correlation with strong effect
        for corr in correlations:
            if not corr.get('is_significant'):
                continue
            
            input_name = corr.get('input_name', '')
            r = corr.get('correlation_coefficient', 0)
            
            # Only show if effect is strong (|r| > 0.5)
            if abs(r) < 0.5:
                continue
            
            # Generate plain-language context
            if 'sleep' in input_name and r > 0:
                return "Your runs tend to be better after good sleep.", "correlation"
            elif 'hrv' in input_name and r > 0:
                return "You perform better when your morning HRV is higher.", "correlation"
            elif 'stress' in input_name and r < 0:
                return "High work stress days correlate with harder runs for you.", "correlation"
            elif 'protein' in input_name and r > 0:
                return "Higher protein days tend to precede your better runs.", "correlation"
            elif 'resting_hr' in input_name and r < 0:
                return "Lower resting HR days correlate with your better performances.", "correlation"
        
        return None, None
        
    except Exception as e:
        logger.warning(f"Correlation context lookup failed: {type(e).__name__}: {e}")
        return None, None


def get_tsb_context(athlete_id: str, db: Session) -> Optional[tuple[str, str, str]]:
    """
    Get Training Stress Balance context for the athlete.
    
    Only returns context when it's ACTIONABLE and meaningful.
    Uses plain language — no jargon like "TSB" or "CTL".
    
    Returns:
        (tsb_label, load_trend, context_sentence) or (None, None, None)
    """
    try:
        from services.training_load import TrainingLoadCalculator, TSBZone
        from uuid import UUID
        
        calculator = TrainingLoadCalculator(db)
        athlete_uuid = UUID(athlete_id)
        load = calculator.calculate_training_load(athlete_uuid)
        
        if load is None:
            return None, None, None
        
        tsb = load.current_tsb
        ctl = load.current_ctl
        
        # Only provide context if we have meaningful fitness data
        if ctl < 20:
            return None, None, None
        
        # Use personalized TSB zones for this athlete (N=1)
        zone_info = calculator.get_tsb_zone(tsb, athlete_id=athlete_uuid)
        
        # ONLY show context when it's actionable
        # "Building" or "normal" states don't need to be called out
        
        if zone_info.zone == TSBZone.RACE_READY and tsb > 15:
            # This is actionable - athlete should know they're fresh
            return None, None, "Fresh and fit. Good window for a hard effort or race."
        
        elif zone_info.zone == TSBZone.OVERTRAINING_RISK and tsb < -25:
            # This is actionable - athlete should consider recovery
            return None, None, "High fatigue accumulated. Recovery day would help."
        
        # For normal training states, don't add noise
        # Let the trajectory sentence speak for itself
        return None, None, None
        
    except Exception as e:
        logger.warning(f"TSB context lookup failed: {type(e).__name__}: {e}")
        return None, None, None


def generate_why_context(
    workout: PlannedWorkout,
    plan: TrainingPlan,
    week_number: int,
    phase: str,
    db: Session = None,
    athlete_id: str = None,
    recent_similar: Optional[Activity] = None
) -> tuple[str, str]:
    """
    Generate sparse, non-prescriptive context for today's workout.
    
    Priority order:
    1. Correlation-based context (if available and relevant)
    2. Training load context (TSB zone)
    3. Plan position (week/phase)
    
    Returns:
        (context_string, source) where source is "correlation" | "load" | "plan"
    
    Tone: Direct, data-driven, no motivation.
    """
    workout_type = workout.workout_type or 'workout'
    phase_display = format_phase(phase)
    
    # 1. Try correlation-based context first
    if db and athlete_id:
        corr_context, corr_source = get_correlation_context(str(athlete_id), workout_type, db)
        if corr_context:
            return corr_context, corr_source
    
    # 2. Try TSB-based context
    if db and athlete_id:
        tsb_label, load_trend, tsb_context = get_tsb_context(str(athlete_id), db)
        if tsb_context:
            return tsb_context, "load"
    
    # 3. Fallback to plan-based context
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
    
    return " ".join(contexts) if contexts else None, "plan"


def generate_trajectory_sentence(
    status: str,
    completed_mi: float,
    planned_mi: float,
    remaining_mi: float = 0.0,
    quality_completed: int = 0,
    quality_planned: int = 0,
    activities_this_week: int = 0,
    tsb_context: Optional[str] = None
) -> Optional[str]:
    """
    Generate a sparse trajectory sentence.
    Tone: Data speaks. No praise, no prescription.

    Includes TSB context when available.
    
    remaining_mi: Only counts today + future planned miles (excludes missed past days)
    """
    # Use remaining_mi (today + future) not (planned - completed) to avoid confusion
    remaining = remaining_mi if remaining_mi > 0 else max(0, planned_mi - completed_mi)
    
    if status == "no_plan":
        # Still provide insight for users without a plan
        if completed_mi > 0:
            if activities_this_week == 1:
                return f"{completed_mi:.0f} mi logged this week. Consistency compounds."
            elif activities_this_week > 1:
                base = f"{completed_mi:.0f} mi across {activities_this_week} runs this week."
                if tsb_context:
                    return f"{base} {tsb_context}"
                return base
        return None
    
    if status == "ahead":
        base = f"Ahead of schedule. {completed_mi:.0f} mi done of {planned_mi:.0f} mi planned."
    elif status == "on_track":
        base = f"On track. {remaining:.0f} mi remaining this week."
    elif status == "behind":
        base = f"Behind schedule. {remaining:.0f} mi to go."
    else:
        return None
    
    # Append TSB context if available (but keep it short)
    if tsb_context and len(base) < 60:
        return f"{base}"
    
    return base


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
            
            # Enhanced why_context with correlation/load priority
            why_context, why_source = generate_why_context(
                planned, 
                active_plan,
                planned.week_number,
                planned.phase,
                db=db,
                athlete_id=str(current_user.id)
            )
            
            today_workout = TodayWorkout(
                has_workout=True,
                workout_type=planned.workout_type,
                title=planned.title,
                distance_mi=round(distance_mi, 1) if distance_mi else None,
                pace_guidance=planned.coach_notes,
                why_context=why_context,
                why_source=why_source,
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
        
        # Try to get insight from InsightAggregator (CalendarInsight) first
        stored_insight = db.query(CalendarInsight).filter(
            CalendarInsight.athlete_id == current_user.id,
            CalendarInsight.insight_date == yesterday,
            CalendarInsight.is_dismissed == False
        ).order_by(desc(CalendarInsight.priority)).first()
        
        if stored_insight:
            insight = stored_insight.content or stored_insight.title
        else:
            # Fallback to inline generation
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
    remaining_mi = 0.0  # Only count today + future planned miles
    current_week_number = None
    current_phase = None
    
    for i in range(7):
        day_date = monday + timedelta(days=i)
        day_abbrev = ['M', 'T', 'W', 'T', 'F', 'S', 'S'][i]
        is_past = day_date < today
        is_today_or_future = day_date >= today
        
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
        is_missed = False
        
        if planned_workout:
            workout_type = planned_workout.workout_type
            planned_distance = planned_workout.target_distance_km * 0.621371 if planned_workout.target_distance_km else 0
            planned_mi += planned_distance
            
            # Only count future planned miles as "remaining"
            if is_today_or_future and not actual:
                remaining_mi += planned_distance
                
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
            # Past day with no activity = missed
            if is_past:
                is_missed = True
                distance_mi = None  # Don't show planned distance for missed days
            else:
                # Future day - show planned distance
                distance_mi = round(planned_workout.target_distance_km * 0.621371, 0)
        
        week_days.append(WeekDay(
            date=day_date.isoformat(),
            day_abbrev=day_abbrev,
            workout_type=workout_type if not is_missed else None,  # Don't show workout type for missed
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
    
    # Get TSB context for trajectory
    tsb_label, load_trend, tsb_short_context = get_tsb_context(str(current_user.id), db)
    
    trajectory_sentence = generate_trajectory_sentence(
        status=status,
        completed_mi=round(completed_mi, 1),
        planned_mi=round(planned_mi, 1),
        remaining_mi=round(remaining_mi, 1),
        activities_this_week=activities_this_week,
        tsb_context=tsb_short_context
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
        trajectory_sentence=trajectory_sentence,
        tsb_context=tsb_label,
        load_trend=load_trend
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
    
    # Generate hero narrative (ADR-033)
    hero_narrative = None
    if is_feature_enabled("narrative.translation_enabled", str(current_user.id), db) and has_any_activities:
        try:
            from services.narrative_translator import NarrativeTranslator
            from services.narrative_memory import NarrativeMemory
            from services.fitness_bank import FitnessBankCalculator
            from services.training_load import TrainingLoadCalculator
            
            # Get fitness bank and load data
            bank_calc = FitnessBankCalculator(db)
            bank = bank_calc.calculate(current_user.id)
            
            load_calc = TrainingLoadCalculator(db)
            load = load_calc.calculate_training_load(current_user.id)
            
            if bank and load:
                translator = NarrativeTranslator(db, current_user.id)
                memory = NarrativeMemory(db, current_user.id, use_redis=False)
                
                # Build upcoming workout context if available
                upcoming = None
                if today_workout.has_workout:
                    upcoming = {
                        "workout_type": today_workout.workout_type,
                        "name": today_workout.title
                    }
                
                # Get hero narrative
                narrative_obj = translator.get_hero_narrative(
                    bank,
                    tsb=load.current_tsb,
                    ctl=load.current_ctl,
                    atl=load.current_atl,
                    upcoming_workout=upcoming
                )
                
                if narrative_obj and not memory.recently_shown(narrative_obj.hash, days=1):
                    hero_narrative = narrative_obj.text
                    memory.record_shown(narrative_obj.hash, narrative_obj.signal_type, "home_hero")
        except Exception as e:
            # Log at WARNING level for production visibility
            logger.warning(f"Hero narrative generation failed for user {current_user.id}: {type(e).__name__}: {e}")
            # Audit log the failure
            try:
                from services.audit_logger import log_narrative_error
                log_narrative_error(current_user.id, "home_hero", str(e))
            except Exception:
                pass  # Don't fail the request due to audit logging
    
    return HomeResponse(
        today=today_workout,
        yesterday=yesterday_insight,
        week=week_progress,
        hero_narrative=hero_narrative,
        strava_connected=strava_connected,
        has_any_activities=has_any_activities,
        total_activities=total_activities,
        last_sync=last_sync
    )


# --- Signals Response Model ---

class SignalItem(BaseModel):
    """Single signal for home glance."""
    id: str
    type: str
    priority: int
    confidence: str
    icon: str
    color: str
    title: str
    subtitle: str
    detail: Optional[str] = None
    action_url: Optional[str] = None


class HomeSignalsResponse(BaseModel):
    """Aggregated signals for home glance layer."""
    signals: List[SignalItem]
    suppressed_count: int
    last_updated: str
    
    model_config = ConfigDict(from_attributes=True)


@router.get("/signals", response_model=HomeSignalsResponse)
async def get_home_signals(
    db: Session = Depends(get_db),
    current_user: Athlete = Depends(get_current_user)
):
    """
    Get aggregated signals from all analytics methods.
    
    Only returns high-confidence signals worth surfacing on the home page.
    Signals are prioritized and filtered by confidence level.
    
    Requires feature flag: signals.home_banner
    """
    from services.home_signals import aggregate_signals, signals_to_dict
    
    # Check feature flag
    flag_enabled = is_feature_enabled("signals.home_banner", str(current_user.id), db)
    
    if not flag_enabled:
        # Return empty response if feature disabled
        return HomeSignalsResponse(
            signals=[],
            suppressed_count=0,
            last_updated=date.today().isoformat()
        )
    
    # Aggregate signals from all analytics methods
    response = aggregate_signals(str(current_user.id), db)
    
    # Convert to response model
    result = signals_to_dict(response)
    
    return HomeSignalsResponse(
        signals=[SignalItem(**s) for s in result["signals"]],
        suppressed_count=result["suppressed_count"],
        last_updated=result["last_updated"]
    )
