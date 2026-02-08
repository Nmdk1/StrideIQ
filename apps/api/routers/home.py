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
from models import Athlete, Activity, PlannedWorkout, TrainingPlan, CalendarInsight, DailyCheckin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/home", tags=["home"])


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
    planned_distance_mi: Optional[float] = None  # Show both for comparison
    completed: bool
    is_today: bool
    activity_id: Optional[str] = None  # For linking to activity
    workout_id: Optional[str] = None  # For linking to planned workout


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


class CoachNoticed(BaseModel):
    """Top insight surfaced by the coach — one sentence."""
    text: str
    source: str  # "correlation" | "signal" | "insight_feed" | "narrative"
    ask_coach_query: str  # pre-filled query for /coach?q=...

    model_config = ConfigDict(from_attributes=True)


class RaceCountdown(BaseModel):
    """Race countdown derived from the active training plan."""
    race_name: Optional[str] = None
    race_date: str  # ISO date
    days_remaining: int
    goal_time: Optional[str] = None  # formatted e.g. "3:10:00"
    goal_pace: Optional[str] = None  # derived e.g. "7:15/mi"
    predicted_time: Optional[str] = None  # from race predictor
    coach_assessment: Optional[str] = None  # Coach's readiness assessment

    model_config = ConfigDict(from_attributes=True)


class StravaStatusDetail(BaseModel):
    """Strava connection health detail."""
    connected: bool
    last_sync: Optional[str] = None
    needs_reconnect: bool = False

    model_config = ConfigDict(from_attributes=True)


class TodayCheckin(BaseModel):
    """Today's check-in summary (shown after athlete checks in)."""
    motivation_label: Optional[str] = None
    sleep_label: Optional[str] = None
    soreness_label: Optional[str] = None
    coach_reaction: Optional[str] = None  # Coach's response to check-in state

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
    ingestion_state: Optional[dict] = None  # Phase 3: ingestion progress snapshot (durable)
    ingestion_paused: bool = False  # Phase 5: global ingestion pause banner
    # --- Phase 2 (ADR-17) ---
    coach_noticed: Optional[CoachNoticed] = None
    race_countdown: Optional[RaceCountdown] = None
    checkin_needed: bool = True
    today_checkin: Optional[TodayCheckin] = None  # Summary of today's check-in (if completed)
    strava_status: Optional[StravaStatusDetail] = None
    coach_briefing: Optional[dict] = None  # LLM-generated coaching narratives for all cards
    
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
    if 'threshold' in workout_type:
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


def generate_coach_home_briefing(
    athlete_id: str,
    checkin_data: Optional[dict],
    workout_data: dict,
    week_data: dict,
    race_data: Optional[dict],
    coach_noticed_text: Optional[str],
    tsb_context: Optional[str],
) -> Optional[dict]:
    """
    Generate real coaching narratives for every home page card using Gemini.
    
    One LLM call, structured output. Cached in Redis keyed by data hash.
    Returns dict with keys: coach_noticed, checkin_reaction, today_context,
    week_assessment, race_assessment.
    """
    import hashlib
    import json as _json
    
    # Build data fingerprint for cache key
    cache_input = _json.dumps({
        "checkin": checkin_data,
        "workout": workout_data,
        "week": week_data,
        "race": race_data,
        "noticed": coach_noticed_text,
        "tsb": tsb_context,
    }, sort_keys=True, default=str)
    data_hash = hashlib.md5(cache_input.encode()).hexdigest()[:12]
    cache_key = f"coach_home_briefing:{athlete_id}:{data_hash}"
    
    # Check Redis cache
    try:
        import redis
        import os
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        r = redis.from_url(redis_url, decode_responses=True)
        cached = r.get(cache_key)
        if cached:
            return _json.loads(cached)
    except Exception:
        r = None
    
    # Build the prompt with all context
    sections = []
    sections.append("You are an elite running coach speaking directly to your athlete about TODAY.")
    sections.append("Be specific, direct, insightful. Reference their actual data. 1-2 sentences per section max.")
    sections.append("Sound like a real coach who knows this athlete — not a dashboard, not a chatbot.")
    sections.append("")
    
    if coach_noticed_text:
        sections.append(f"## Key Insight Data\n{coach_noticed_text}")
    
    if checkin_data:
        sections.append(f"## Today's Check-in\nFeeling: {checkin_data.get('motivation_label', 'unknown')}, Sleep: {checkin_data.get('sleep_label', 'unknown')}, Soreness: {checkin_data.get('soreness_label', 'unknown')}")
    
    if workout_data.get("has_workout"):
        w = workout_data
        workout_desc = f"{w.get('distance_mi', '?')}mi {w.get('workout_type', 'run')}"
        if w.get("title"):
            workout_desc = w["title"]
        sections.append(f"## Today's Workout\nType: {w.get('workout_type')}, Distance: {w.get('distance_mi')}mi, Pace guidance: {w.get('pace_guidance', 'none')}")
        if w.get("why_context"):
            sections.append(f"Context: {w['why_context']}")
        if w.get("phase"):
            sections.append(f"Phase: {w['phase']}, Week {w.get('week_number', '?')}")
    else:
        sections.append("## Today's Workout\nNo workout scheduled (rest day or no plan).")
    
    week = week_data
    sections.append(f"## This Week\nCompleted: {week.get('completed_mi', 0)}mi of {week.get('planned_mi', 0)}mi planned. Status: {week.get('status', 'unknown')}. Activities: {week.get('activities_count', 0)}.")
    if tsb_context:
        sections.append(f"Training state: {tsb_context}")
    if week.get("trajectory_sentence"):
        sections.append(f"Trajectory: {week['trajectory_sentence']}")
    
    if race_data:
        sections.append(f"## Race\n{race_data.get('race_name', 'Race')} in {race_data.get('days_remaining')} days. Goal: {race_data.get('goal_time', 'not set')} ({race_data.get('goal_pace', '?')}/mi). Prediction: {race_data.get('predicted_time', 'insufficient data')}.")
    
    sections.append("")
    sections.append("Respond in this exact JSON format (no markdown, just raw JSON):")
    sections.append('{')
    sections.append('  "coach_noticed": "Your enriched coaching take on the key insight — make it sound like a coach, not a stat line. 1-2 sentences.",')
    if checkin_data:
        sections.append('  "checkin_reaction": "React to their state in context of today\'s workout and where they are in training. 1-2 sentences.",')
    sections.append('  "today_context": "Why this workout matters today, what to focus on, what to watch for. 1-2 sentences.",')
    sections.append('  "week_assessment": "Assessment of the week so far — trajectory, what to prioritize. 1 sentence.",')
    if race_data:
        sections.append('  "race_assessment": "Honest readiness assessment. Where they stand. 1-2 sentences."')
    sections.append('}')
    
    prompt = "\n".join(sections)
    
    try:
        from google import genai
        import os
        
        api_key = os.getenv("GOOGLE_AI_API_KEY")
        if not api_key:
            logger.warning("GOOGLE_AI_API_KEY not set — skipping coach home briefing")
            return None
        
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                max_output_tokens=500,
                temperature=0.3,
            ),
        )
        
        raw = response.text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3].strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()
        
        result = _json.loads(raw)
        
        # Cache for 30 minutes
        if r:
            try:
                r.setex(cache_key, 1800, _json.dumps(result))
            except Exception:
                pass
        
        return result
        
    except Exception as e:
        logger.warning(f"Coach home briefing generation failed: {type(e).__name__}: {e}")
        return None


def compute_coach_noticed(
    athlete_id: str,
    db: Session,
    hero_narrative: Optional[str] = None,
) -> Optional[CoachNoticed]:
    """
    ADR-17 Phase 2: Build the single most important coaching insight.

    Priority waterfall:
    1. Strong correlation (|r| >= 0.5, n >= 15)
    2. Top signal from home_signals
    3. Top insight feed card summary
    4. Hero narrative fallback
    """
    # 1. Strong correlation
    try:
        from services.correlation_engine import analyze_correlations
        result = analyze_correlations(athlete_id, days=60, db=db)
        for corr in result.get("correlations", []):
            if not corr.get("is_significant"):
                continue
            r = corr.get("correlation_coefficient", 0)
            n = corr.get("sample_size", 0)
            if abs(r) >= 0.5 and n >= 15:
                input_name = corr.get("input_name", "factor")
                direction = "positively" if r > 0 else "negatively"
                text = (
                    f"{input_name.replace('_', ' ').title()} {direction} correlates "
                    f"with your efficiency (r={r:.2f}, {n} observations)."
                )
                return CoachNoticed(
                    text=text,
                    source="correlation",
                    ask_coach_query=f"Tell me more about how {input_name.replace('_', ' ')} affects my running",
                )
    except Exception as e:
        logger.debug(f"Coach noticed correlation lookup failed: {e}")

    # 2. Top signal from home_signals
    try:
        from services.home_signals import aggregate_signals
        sig_resp = aggregate_signals(athlete_id, db)
        if sig_resp.signals:
            top = sig_resp.signals[0]
            text = f"{top.title}. {top.subtitle}" if top.subtitle else top.title
            return CoachNoticed(
                text=text,
                source="signal",
                ask_coach_query=f"Coach, explain this: {top.title}",
            )
    except Exception as e:
        logger.debug(f"Coach noticed signals lookup failed: {e}")

    # 3. Top insight feed card
    try:
        from services.insight_feed import build_insight_feed_cards
        athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if athlete:
            feed = build_insight_feed_cards(db, athlete, max_cards=1)
            cards = feed.get("cards", [])
            if cards:
                card = cards[0]
                text = card.get("summary") or card.get("title", "")
                return CoachNoticed(
                    text=text,
                    source="insight_feed",
                    ask_coach_query=f"Tell me about: {card.get('title', 'my latest insight')}",
                )
    except Exception as e:
        logger.debug(f"Coach noticed feed lookup failed: {e}")

    # 4. Hero narrative fallback
    if hero_narrative:
        return CoachNoticed(
            text=hero_narrative,
            source="narrative",
            ask_coach_query="What should I focus on today?",
        )

    return None


def compute_race_countdown(
    plan: Optional[TrainingPlan],
    athlete_id: str,
    db: Session,
) -> Optional[RaceCountdown]:
    """
    ADR-17 Phase 2: Race countdown from active training plan.
    Uses getattr/try-except for all plan fields — resilient to model changes.
    """
    if plan is None:
        return None

    race_date = getattr(plan, "goal_race_date", None)
    if not race_date:
        return None

    days_remaining = (race_date - date.today()).days
    if days_remaining < 0:
        return None  # Race already happened

    race_name = getattr(plan, "goal_race_name", None)

    # Format goal_time
    goal_time_str = None
    goal_time_s = getattr(plan, "goal_time_seconds", None)
    if goal_time_s:
        hours = int(goal_time_s // 3600)
        mins = int((goal_time_s % 3600) // 60)
        secs = int(goal_time_s % 60)
        goal_time_str = f"{hours}:{mins:02d}:{secs:02d}"

    # Derive goal pace from goal_time and distance
    goal_pace_str = None
    distance_m = getattr(plan, "goal_race_distance_m", None)
    if goal_time_s and distance_m and distance_m > 0:
        pace_s_per_mile = goal_time_s / (distance_m / 1609.344)
        p_mins = int(pace_s_per_mile // 60)
        p_secs = int(pace_s_per_mile % 60)
        goal_pace_str = f"{p_mins}:{p_secs:02d}/mi"

    # Predicted time from race predictor
    predicted_str = None
    try:
        from services.race_predictor import predict_race_time
        from uuid import UUID
        if distance_m and distance_m > 0:
            prediction = predict_race_time(UUID(athlete_id), race_date, distance_m, db)
            if prediction:
                predicted_str = getattr(prediction, "predicted_time_formatted", None)
    except Exception as e:
        logger.debug(f"Race prediction failed: {e}")

    return RaceCountdown(
        race_name=race_name,
        race_date=race_date.isoformat(),
        days_remaining=days_remaining,
        goal_time=goal_time_str,
        goal_pace=goal_pace_str,
        predicted_time=predicted_str,
    )


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
        planned_distance_mi = None
        completed = False
        is_missed = False
        activity_id = None
        workout_id = None
        
        if planned_workout:
            workout_type = planned_workout.workout_type
            workout_id = str(planned_workout.id)
            planned_distance = planned_workout.target_distance_km * 0.621371 if planned_workout.target_distance_km else 0
            planned_mi += planned_distance
            planned_distance_mi = round(planned_distance, 1) if planned_distance else None
            
            # Only count future planned miles as "remaining"
            if is_today_or_future and not actual:
                remaining_mi += planned_distance
                
            if day_date == today:
                current_week_number = planned_workout.week_number
                current_phase = planned_workout.phase
        
        if actual:
            completed = True
            activity_id = str(actual.id)
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
            planned_distance_mi=planned_distance_mi,
            completed=completed,
            is_today=(day_date == today),
            activity_id=activity_id,
            workout_id=workout_id,
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

    # Phase 3: ingestion progress snapshot (latency bridge)
    ingestion_state = None
    if strava_connected:
        try:
            from services.ingestion_state import get_ingestion_state_snapshot

            snap = get_ingestion_state_snapshot(db, current_user.id, provider="strava")
            ingestion_state = snap.to_dict() if snap else None
        except Exception:
            ingestion_state = None

    # Phase 5: global ingestion pause (emergency brake).
    ingestion_paused = False
    try:
        from services.system_flags import is_ingestion_paused

        ingestion_paused = bool(is_ingestion_paused(db))
    except Exception:
        ingestion_paused = False
    
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
    
    # --- Phase 2 (ADR-17): Coach Noticed ---
    coach_noticed = None
    if has_any_activities:
        coach_noticed = compute_coach_noticed(
            str(current_user.id), db, hero_narrative=hero_narrative
        )

    # --- Phase 2 (ADR-17): Race Countdown ---
    race_countdown = compute_race_countdown(
        active_plan, str(current_user.id), db
    )

    # --- Phase 2 (ADR-17): Check-in Needed + Today's Check-in Summary ---
    # Rollback any prior failed transaction state (e.g. missing tables like
    # athlete_calibrated_model) so this query runs on a clean session.
    checkin_needed = True
    today_checkin = None
    try:
        db.rollback()
        existing_checkin = db.query(DailyCheckin).filter(
            DailyCheckin.athlete_id == current_user.id,
            DailyCheckin.date == today,
        ).first()
        checkin_needed = existing_checkin is None
        if existing_checkin is not None:
            # Build human-readable labels from stored values
            motivation_map = {5: 'Great', 4: 'Fine', 2: 'Tired', 1: 'Rough'}
            sleep_map = {8: 'Great', 7: 'OK', 5: 'Poor'}
            soreness_map = {1: 'None', 2: 'Mild', 4: 'Yes'}
            today_checkin = TodayCheckin(
                motivation_label=motivation_map.get(
                    int(existing_checkin.motivation_1_5) if existing_checkin.motivation_1_5 is not None else -1
                ),
                sleep_label=sleep_map.get(
                    int(existing_checkin.sleep_h) if existing_checkin.sleep_h is not None else -1
                ),
                soreness_label=soreness_map.get(
                    int(existing_checkin.soreness_1_5) if existing_checkin.soreness_1_5 is not None else -1
                ),
            )
    except Exception as e:
        logger.warning(f"Check-in query failed: {e}")
        checkin_needed = True

    # --- Phase 2 (ADR-17): Strava Status Detail ---
    strava_status_detail = StravaStatusDetail(
        connected=strava_connected,
        last_sync=last_sync,
        needs_reconnect=not strava_connected and bool(current_user.strava_athlete_id),
    )

    # --- Phase 2 (ADR-17): LLM Coach Briefing ---
    # One Gemini call with all context → coaching voice for every card.
    # Cached in Redis for 30 min; regenerates when data changes.
    coach_briefing = None
    if has_any_activities:
        try:
            # Build workout data dict for the briefing prompt
            workout_data = {
                "has_workout": today_workout.has_workout,
                "workout_type": today_workout.workout_type,
                "title": today_workout.title,
                "distance_mi": today_workout.distance_mi,
                "pace_guidance": today_workout.pace_guidance,
                "why_context": today_workout.why_context,
                "phase": today_workout.phase,
                "week_number": today_workout.week_number,
            }
            
            # Build week data dict
            week_data_dict = {
                "completed_mi": week_progress.completed_mi,
                "planned_mi": week_progress.planned_mi,
                "progress_pct": week_progress.progress_pct,
                "status": week_progress.status,
                "trajectory_sentence": week_progress.trajectory_sentence,
                "activities_count": sum(1 for d in week_progress.days if d.completed),
                "week_number": week_progress.week_number,
                "total_weeks": week_progress.total_weeks,
                "phase": week_progress.phase,
            }
            
            # Build race data dict
            race_data_dict = None
            if race_countdown:
                race_data_dict = {
                    "race_name": race_countdown.race_name,
                    "race_date": race_countdown.race_date,
                    "days_remaining": race_countdown.days_remaining,
                    "goal_time": race_countdown.goal_time,
                    "goal_pace": race_countdown.goal_pace,
                    "predicted_time": race_countdown.predicted_time,
                }
            
            # Build check-in data dict
            checkin_data_dict = None
            if today_checkin:
                checkin_data_dict = {
                    "motivation_label": today_checkin.motivation_label,
                    "sleep_label": today_checkin.sleep_label,
                    "soreness_label": today_checkin.soreness_label,
                }
            
            # Coach noticed text
            noticed_text = coach_noticed.text if coach_noticed else hero_narrative
            
            coach_briefing = generate_coach_home_briefing(
                athlete_id=str(current_user.id),
                checkin_data=checkin_data_dict,
                workout_data=workout_data,
                week_data=week_data_dict,
                race_data=race_data_dict,
                coach_noticed_text=noticed_text,
                tsb_context=week_progress.tsb_context,
            )
        except Exception as e:
            logger.warning(f"Coach briefing failed: {type(e).__name__}: {e}")

    return HomeResponse(
        today=today_workout,
        yesterday=yesterday_insight,
        week=week_progress,
        hero_narrative=hero_narrative,
        strava_connected=strava_connected,
        has_any_activities=has_any_activities,
        total_activities=total_activities,
        last_sync=last_sync,
        ingestion_state=ingestion_state,
        ingestion_paused=ingestion_paused,
        coach_noticed=coach_noticed,
        race_countdown=race_countdown,
        checkin_needed=checkin_needed,
        today_checkin=today_checkin,
        strava_status=strava_status_detail,
        coach_briefing=coach_briefing,
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
