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
import asyncio
import logging

from core.database import get_db
from core.auth import get_current_user
from core.feature_flags import is_feature_enabled
from models import Athlete, Activity, ActivityStream, PlannedWorkout, TrainingPlan, CalendarInsight, DailyCheckin

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


class LastRunSegment(BaseModel):
    """Segment from stream analysis for mini-canvas overlay."""
    type: str
    start_time_s: float
    end_time_s: float
    duration_s: float
    avg_pace_s_km: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class LastRun(BaseModel):
    """RSI Layer 1: Most recent run (within 96h) for home page hero canvas.

    When stream_status == 'success', effort_intensity is populated so the
    home page can render an effort gradient canvas.  Otherwise, a clean
    metrics-only card is shown (silent upgrade path).
    """
    activity_id: str
    name: str
    start_time: str  # ISO datetime
    distance_m: Optional[float] = None
    moving_time_s: Optional[float] = None
    average_hr: Optional[float] = None
    stream_status: Optional[str] = None  # 'success' | 'pending' | 'fetching' | 'unavailable' | null
    effort_intensity: Optional[List[float]] = None  # Only when stream_status === 'success'
    pace_stream: Optional[List[float]] = None  # LTTB-downsampled pace (s/km) per point
    elevation_stream: Optional[List[float]] = None  # LTTB-downsampled altitude (m) per point
    tier_used: Optional[str] = None
    confidence: Optional[float] = None
    segments: Optional[List[LastRunSegment]] = None  # For segment band overlay
    pace_per_km: Optional[float] = None  # Derived from distance/time (s/km)

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
    briefing_state: Optional[str] = None  # ADR-065: fresh | stale | missing | refreshing
    # --- RSI Layer 1 ---
    last_run: Optional[LastRun] = None  # Most recent run within 96h for hero canvas

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


# ---------------------------------------------------------------------------
# Post-generation voice validator — fail-closed, no bypass
# ---------------------------------------------------------------------------

_VOICE_BAN_LIST = (
    "incredible", "amazing", "phenomenal", "extraordinary", "fantastic",
    "wonderful", "awesome", "brilliant", "magnificent", "outstanding",
    "superb", "stellar", "remarkable", "spectacular",
)

_VOICE_CAUSAL_PHRASES = (
    "because you", "caused by", "due to your", "as a result of your",
    "that's why", "which caused", "which led to",
)

# Internal metrics that must never reach the athlete-facing output.
# These values appear in the athlete brief for the model's reasoning only.
# Any field that surfaces one of these to the athlete is rejected.
_VOICE_INTERNAL_METRICS = (
    "chronic load",
    "acute load",
    " ctl",   # leading space avoids false-positive inside longer words
    " atl",
    " tsb",
    "form score",
    "durability index",
    "recovery half-life",
    "injury risk score",
)

_VOICE_FALLBACK = (
    "Your training data is ready. Check your workout below for today's plan."
)


def validate_voice_output(text: str, field: str = "morning_voice") -> dict:
    """
    Post-generation validator for LLM-produced morning_voice / workout_why.

    Fail-closed: if ANY check fails, returns valid=False with a deterministic
    fallback. There is no bypass flag, no warn-only mode.

    Checks:
      1. Ban-list — sycophantic/hyperbolic language
      2. Causal language — no pseudo-causal claims
      3. Numeric grounding — at least one number present
      4. Length — between 40 and 280 characters

    Returns:
        {"valid": True} or {"valid": False, "reason": str, "fallback": str}
    """
    if not text or not isinstance(text, str):
        return {"valid": False, "reason": "empty", "fallback": _VOICE_FALLBACK}

    lower = text.lower()

    # 1. Ban-list check
    for word in _VOICE_BAN_LIST:
        if word in lower:
            return {
                "valid": False,
                "reason": f"ban_list:{word}",
                "fallback": _VOICE_FALLBACK,
            }

    # 2. Causal language check
    for phrase in _VOICE_CAUSAL_PHRASES:
        if phrase in lower:
            return {
                "valid": False,
                "reason": f"causal:{phrase}",
                "fallback": _VOICE_FALLBACK,
            }

    # 2b. Internal metrics ban — these values are for model reasoning only and
    # must never surface in athlete-facing output. Fail-closed: any match rejects.
    padded = f" {lower} "  # pad so leading-space tokens match at string start/end
    for term in _VOICE_INTERNAL_METRICS:
        if term in padded:
            return {
                "valid": False,
                "reason": f"internal_metric:{term.strip()}",
                "fallback": _VOICE_FALLBACK,
            }

    # 3. Numeric grounding — at least one digit (morning_voice only)
    # workout_why may be conceptual ("Active recovery keeps blood flowing")
    import re
    if field == "morning_voice" and not re.search(r'\d', text):
        return {
            "valid": False,
            "reason": "numeric:no_numbers_found",
            "fallback": _VOICE_FALLBACK,
        }

    # 4. Length check — only enforced for fields with strict character limits.
    # coach_noticed is 1-2 sentences with no fixed character budget.
    if field in ("morning_voice", "workout_why"):
        if len(text) < 40:
            return {
                "valid": False,
                "reason": f"length:too_short({len(text)})",
                "fallback": _VOICE_FALLBACK,
            }
        if len(text) > 280:
            return {
                "valid": False,
                "reason": f"length:too_long({len(text)})",
                "fallback": _VOICE_FALLBACK,
            }

    return {"valid": True}


def _looks_like_action(text: Optional[str]) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(
        v in lower
        for v in (
            "keep",
            "plan",
            "schedule",
            "run",
            "take",
            "prioritize",
            "reduce",
            "recover",
            "focus",
            "sleep",
            "fuel",
            "hydrate",
            "easy day",
        )
    )


def _valid_home_briefing_contract(result: dict, checkin_data: Optional[dict], race_data: Optional[dict]) -> bool:
    if not isinstance(result, dict):
        return False
    coach_noticed = result.get("coach_noticed")
    week_assessment = result.get("week_assessment")
    today_context = result.get("today_context")
    if not coach_noticed or not week_assessment or not today_context:
        return False
    action_sources = [today_context, result.get("checkin_reaction"), result.get("race_assessment")]
    if not any(_looks_like_action(s) for s in action_sources if isinstance(s, str)):
        return False
    if checkin_data and not result.get("checkin_reaction"):
        return False
    if race_data and not result.get("race_assessment"):
        return False
    return True


HOME_BRIEFING_TIMEOUT_S = 10  # hard ceiling on request path — page must never block on LLM; Celery warms cache in background


def _call_opus_briefing_sync(
    prompt: str,
    schema_fields: dict,
    required_fields: list,
    api_key: str,
    llm_timeout: Optional[int] = None,
) -> Optional[dict]:
    """
    Synchronous Opus call — meant to be run via asyncio.to_thread() or
    ThreadPoolExecutor in Celery workers.

    llm_timeout: SDK-level timeout in seconds. Defaults to HOME_BRIEFING_TIMEOUT_S
    (10s) for the request path. Workers pass PROVIDER_TIMEOUT_S (45s) so the
    richer prompt has enough generation time without blocking page loads.
    """
    import json as _json

    timeout_s = llm_timeout if llm_timeout is not None else HOME_BRIEFING_TIMEOUT_S

    try:
        from anthropic import Anthropic
    except ImportError:
        logger.warning("anthropic package not installed — cannot use Opus for home briefing")
        return None

    field_descriptions = "\n".join(
        f'  - "{k}" ({"REQUIRED" if k in required_fields else "optional"}): {v}'
        for k, v in schema_fields.items()
    )

    system_prompt = (
        "You are an elite running coach generating a structured home page briefing. "
        "Respond with ONLY a valid JSON object — no markdown, no code fences, no explanation. "
        "The JSON must contain these fields:\n"
        f"{field_descriptions}\n\n"
        "Rules:\n"
        "- Every required field MUST be present.\n"
        "- Optional fields should be included only when relevant data exists.\n"
        "- Keep each field concise: 1-2 sentences max.\n"
        "- Respond with the raw JSON object only."
    )

    try:
        client = Anthropic(api_key=api_key, timeout=timeout_s)
        response = client.messages.create(
            model="claude-opus-4-6",
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.3,
        )

        raw_text = response.content[0].text if response.content else ""
        if not raw_text.strip():
            logger.warning("Opus returned empty response for home briefing")
            return None

        text = raw_text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        result = _json.loads(text)
        logger.info(
            f"Home briefing generated via Opus "
            f"(input={response.usage.input_tokens}, output={response.usage.output_tokens})"
        )
        return result

    except _json.JSONDecodeError as je:
        logger.warning(f"Opus JSON parse failed: {je}")
        return None
    except Exception as e:
        logger.warning(f"Opus home briefing call failed: {type(e).__name__}: {e}")
        return None


def _call_gemini_briefing_sync(
    prompt: str,
    schema_fields: dict,
    required_fields: list,
    api_key: str,
    llm_timeout: Optional[int] = None,
) -> Optional[dict]:
    """
    Synchronous Gemini call with SDK-level timeout.
    Called directly or via ThreadPoolExecutor in Celery tasks.

    llm_timeout: SDK-level timeout in seconds. Defaults to HOME_BRIEFING_TIMEOUT_S
    (10s) for the request path. Workers pass PROVIDER_TIMEOUT_S (45s).
    """
    import json as _json

    timeout_s = llm_timeout if llm_timeout is not None else HOME_BRIEFING_TIMEOUT_S

    try:
        from google import genai
    except ImportError:
        logger.warning("google-genai package not installed — cannot use Gemini for home briefing")
        return None

    schema_properties = {
        k: {"type": "STRING", "description": v}
        for k, v in schema_fields.items()
    }

    client = genai.Client(
        api_key=api_key,
        http_options={"timeout": timeout_s * 1000},
    )

    for attempt in (1, 2):
        try:
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    max_output_tokens=4000,
                    temperature=0.3,
                    response_mime_type="application/json",
                    response_schema={
                        "type": "OBJECT",
                        "properties": schema_properties,
                        "required": required_fields,
                    },
                ),
            )
            raw_text = resp.text
            if not raw_text or not raw_text.strip():
                logger.warning(f"Gemini returned empty response (attempt {attempt})")
                raise ValueError("empty_response")
            result = _json.loads(raw_text)
            logger.info(f"Home briefing generated via Gemini Flash (attempt {attempt})")
            return result
        except (ValueError, _json.JSONDecodeError) as e:
            logger.warning(f"Gemini JSON parse failed (attempt {attempt}): {e}")
            if attempt == 2:
                return None
            import time
            time.sleep(1)
        except Exception as e:
            logger.warning(f"Gemini home briefing call failed: {type(e).__name__}: {e}")
            return None

    return None


def _fetch_llm_briefing_sync(
    prompt: str,
    schema_fields: dict,
    required_fields: list,
    checkin_data: Optional[dict],
    race_data: Optional[dict],
    cache_key: str,
    athlete_id: str,
) -> Optional[dict]:
    """
    Pure LLM call + validation + Redis cache write.  No DB access.

    Designed to run in a worker thread via ``asyncio.to_thread`` so the
    event loop is never blocked by a slow LLM response.  The caller is
    responsible for building the prompt (which requires DB) on the
    request thread before handing off.
    """
    import json as _json
    import os

    # --- Primary: Claude Opus 4.6 ---
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        result = _call_opus_briefing_sync(prompt, schema_fields, required_fields, anthropic_key)
    else:
        logger.info("ANTHROPIC_API_KEY not set — falling back to Gemini for home briefing")
        result = None

    # --- Fallback: Gemini Flash ---
    if result is None:
        google_key = os.getenv("GOOGLE_AI_API_KEY")
        if google_key:
            result = _call_gemini_briefing_sync(prompt, schema_fields, required_fields, google_key)
        else:
            logger.warning("No LLM API keys available for home briefing")
            return None

    if result is None:
        return None

    if not _valid_home_briefing_contract(result, checkin_data=checkin_data, race_data=race_data):
        logger.warning("Coach home briefing failed A->I->A contract validation; returning None for deterministic fallback.")
        return None

    # --- Post-generation validator: morning_voice ---
    raw_voice = result.get("morning_voice")
    if raw_voice:
        voice_check = validate_voice_output(raw_voice, field="morning_voice")
        if not voice_check["valid"]:
            logger.warning(f"morning_voice failed validation ({voice_check.get('reason')}); using fallback")
            result["morning_voice"] = voice_check["fallback"]
    else:
        result["morning_voice"] = _VOICE_FALLBACK

    # --- Post-generation validator: coach_noticed ---
    # Uses the same ban lists (sycophancy, causal, internal metrics).
    # Numeric grounding and length checks are skipped (coach_noticed is a
    # different shape — 1-2 sentences, no strict number requirement).
    raw_noticed = result.get("coach_noticed")
    if raw_noticed:
        noticed_check = validate_voice_output(raw_noticed, field="coach_noticed")
        if not noticed_check["valid"]:
            logger.warning(f"coach_noticed failed validation ({noticed_check.get('reason')}); clearing field")
            result["coach_noticed"] = None

    # --- Post-generation validator: workout_why ---
    raw_why = result.get("workout_why")
    if raw_why:
        why_check = validate_voice_output(raw_why, field="workout_why")
        if not why_check["valid"]:
            logger.warning(f"workout_why failed validation ({why_check.get('reason')}); using fallback")
            result["workout_why"] = None

    # Cache for 30 minutes
    try:
        import redis as _redis
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        r = _redis.from_url(redis_url, decode_responses=True)
        r.setex(cache_key, 1800, _json.dumps(result))
    except Exception:
        pass

    logger.info(f"Coach home briefing generated successfully for {athlete_id}")
    return result


def generate_coach_home_briefing(
    athlete_id: str,
    db: Session,
    today_completed: Optional[dict] = None,
    planned_workout: Optional[dict] = None,
    checkin_data: Optional[dict] = None,
    race_data: Optional[dict] = None,
) -> tuple:
    """
    Prepare everything the LLM needs (DB work on request thread), then
    return the args for ``_fetch_llm_briefing_sync`` so the caller can
    run the LLM call in a worker thread via ``asyncio.to_thread``.

    Returns ``(cached_result,)`` if Redis hit, or
    ``(None, prompt, schema_fields, required_fields, cache_key)`` if
    the LLM call is needed.

    Primary model: Claude Opus 4.5 (highest reasoning quality).
    Fallback: Gemini 2.5 Flash (if Opus unavailable).
    Cached in Redis keyed by athlete + data hash.
    """
    import hashlib
    import json as _json

    # Build data fingerprint for cache key
    cache_input = _json.dumps({
        "completed": today_completed,
        "planned": planned_workout,
        "checkin": checkin_data,
        "race": race_data,
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
            return (_json.loads(cached),)
    except Exception:
        pass

    # ADR-16: Get the full athlete brief — same context the coach chat uses
    try:
        from services.coach_tools import build_athlete_brief
        from uuid import UUID
        athlete_brief = build_athlete_brief(db, UUID(athlete_id))
    except Exception as e:
        logger.warning(f"Failed to build athlete brief for home briefing: {e}")
        athlete_brief = "(Brief unavailable)"

    # Query InsightLog for recent non-LOG insights (top 3, last 7 days)
    insight_context = ""
    try:
        from models import InsightLog
        recent_insights = (
            db.query(InsightLog)
            .filter(
                InsightLog.athlete_id == athlete_id,
                InsightLog.mode != "log",
                InsightLog.trigger_date >= date.today() - timedelta(days=7),
            )
            .order_by(desc(InsightLog.trigger_date))
            .limit(3)
            .all()
        )
        if recent_insights:
            insight_lines = []
            for ins in recent_insights:
                msg = ins.message or ins.rule_id
                insight_lines.append(f"- [{ins.mode.upper()}] {msg}")
            insight_context = "\n".join(insight_lines)
    except Exception as e:
        logger.debug(f"InsightLog query failed (non-blocking): {e}")

    # H2: Run deterministic intelligence pipeline before LLM prompt assembly.
    # compute_coach_noticed queries correlations, home signals, and insight feed —
    # the richest intelligence the system produces. Feed it into the prompt so the
    # LLM synthesises it rather than generating generic observations.
    coach_noticed_intel = None
    try:
        coach_noticed_intel = compute_coach_noticed(athlete_id, db)
    except Exception as e:
        logger.warning(f"compute_coach_noticed failed (non-blocking): {e}")

    # Build the prompt
    parts = [
        "You are an elite running coach speaking directly to your athlete about TODAY.",
        "You have their full training profile below. Use it. Be specific, direct, insightful.",
        "Reference their actual numbers. Sound like a real coach, not a dashboard.",
        "CRITICAL: Only reference data explicitly provided. Do NOT invent or assume anything.",
        "1-2 sentences per field max.",
        "A->I->A contract: coach_noticed must be interpretive assessment, week_assessment must explain implication, and at least one field must provide a concrete next action.",
        "Do NOT emit internal labels or schema-like wording.",
        "",
        "COACHING TONE RULES (non-negotiable):",
        "- State facts first, then implication. Let the data speak — no cheerleading, no praise.",
        "- Frame load/fatigue concerns as FORWARD-LOOKING actions ('easy day tomorrow to absorb this') NOT as warnings or diagnoses.",
        "- NEVER contradict how the athlete says they feel. If they feel fine but load is high, say 'Glad you feel good — let's keep it that way with an easy day tomorrow.' Do NOT say 'but actually you are fatigued.'",
        "- NEVER quote raw metrics like TSB numbers, form scores, or load ratios to the athlete. Translate into plain coaching language.",
        "- Be direct and honest, not sycophantic. The athlete trusts data, not flattery.",
        "",
        "TRUST-SAFETY CONSTRAINTS (enforced by post-generation validator):",
        "- Do NOT use sycophantic words: incredible, amazing, phenomenal, extraordinary, fantastic, wonderful, awesome, brilliant, magnificent, outstanding, superb, stellar, remarkable, spectacular.",
        "- Do NOT make causal claims: avoid 'because you', 'caused by', 'due to your'.",
        "- morning_voice MUST contain at least one specific number from the data.",
        "- morning_voice must be 40-280 characters.",
        "- workout_why must be a single sentence explaining why today's workout matters.",
        "- ABSOLUTE BAN on quoting these to the athlete: CTL, ATL, TSB, chronic load, acute load, form score, durability index, recovery half-life, injury risk score. These appear in the brief for YOUR reasoning only. If you quote them, the output will be rejected.",
        "",
        "=== ATHLETE BRIEF ===",
        athlete_brief,
        "",
    ]

    if insight_context:
        parts.extend([
            "=== RECENT INTELLIGENCE INSIGHTS (last 7 days) ===",
            insight_context,
            "",
        ])

    # FIX 2: Build rich intelligence from five analytical sources and inject
    # into the prompt. Falls back to the single deterministic signal when all
    # sources are empty (e.g., athlete has no check-ins or N=1 data yet).
    rich_context = ""
    try:
        rich_context = _build_rich_intelligence_context(athlete_id, db)
    except Exception as e:
        logger.warning(f"Rich intelligence context failed (non-blocking): {e}")

    if rich_context:
        parts.extend([
            rich_context,
            "",
            "CRITICAL INSTRUCTION: The DEEP INTELLIGENCE section above contains findings",
            "the athlete CANNOT derive from looking at their own data. Your morning_voice",
            "and coach_noticed MUST draw from this section. If you ignore it and produce",
            "generic observations like weekly mileage totals, your output will be rejected.",
            "",
        ])
    elif coach_noticed_intel:
        parts.extend([
            "=== DETERMINISTIC INTELLIGENCE ===",
            f"Source: {coach_noticed_intel.source}",
            coach_noticed_intel.text,
            "",
        ])

    parts.append("=== TODAY ===")

    if today_completed:
        c = today_completed
        parts.append(f"COMPLETED today: {c.get('name')}, {c.get('distance_mi')}mi, pace {c.get('pace')}, HR {c.get('avg_hr', 'N/A')}, {c.get('duration_min')}min")
        if planned_workout and planned_workout.get("has_workout"):
            plan_mi = planned_workout.get("distance_mi")
            plan_type = planned_workout.get("title") or planned_workout.get("workout_type")
            if plan_mi and c.get("distance_mi") and abs(c["distance_mi"] - plan_mi) > 1.0:
                parts.append(f"Note: plan had {plan_mi}mi {plan_type}, athlete ran {c['distance_mi']}mi instead.")
    elif planned_workout and planned_workout.get("has_workout"):
        w = planned_workout
        parts.append(f"PLANNED (not yet completed): {w.get('title') or w.get('workout_type')}, {w.get('distance_mi', '?')}mi")
        parts.append("The athlete may or may not follow this plan. Coach based on their actual patterns, not the plan.")
    else:
        parts.append("No planned workout and nothing completed yet today.")

    if checkin_data:
        parts.append(f"Check-in: Feeling {checkin_data.get('motivation_label', '?')}, Sleep {checkin_data.get('sleep_label', '?')}, Soreness {checkin_data.get('soreness_label', '?')}")

    prompt = "\n".join(parts)

    schema_fields = {
        "coach_noticed": "The single most important coaching observation the athlete doesn't already know. Draw from the DEEP INTELLIGENCE personal patterns section. Surface the finding most relevant to TODAY. If a daily intelligence rule fired, lead with that. The athlete should read this and think 'I didn't know that.' Example of GOOD: 'Your efficiency tends to improve within 2 days of higher sleep — last night's 5.5 hours may blunt tomorrow's gains.' Example of BAD: 'You ran two 10-mile runs this week showing consistent volume.' 1-2 sentences. NEVER quote internal metrics.",
        "today_context": "Action-focused context: if run completed, state the result then specify next steps; if not yet, describe what today should look like. Must include a concrete next action. 1-2 sentences.",
        "week_assessment": "Implication: explain what this week's trajectory means for near-term training direction, based on actual training not plan adherence. 1 sentence.",
        "checkin_reaction": "Acknowledge how they feel FIRST, then guide next steps. If they feel good despite high load, validate that and suggest recovery actions to maintain it. Never contradict their self-report. 1-2 sentences.",
        "race_assessment": "Honest readiness assessment for their race based on current fitness, not plan adherence. 1-2 sentences.",
        "morning_voice": "One paragraph that gives your athlete's data a voice. 40-280 characters. PRIORITIZE insights from the DEEP INTELLIGENCE section — these are things the athlete cannot derive from their own runs. A good morning voice connects a personal pattern to today's context. Example of GOOD: '6.8 hours of sleep last night. Your body tends to run easier the day after 7+ hours — today might not get that boost, so keep the effort honest.' Example of BAD: '38.3 miles through 5 runs this week. Your pacing has been consistent.' Must cite at least one specific number (pace, distance, HR — NOT internal metrics). ABSOLUTE BAN on CTL, ATL, TSB, chronic load, acute load, form score, durability index, recovery half-life, injury risk score.",
        "workout_why": "One sentence explaining WHY today's workout matters in the context of their training. Example: 'Active recovery keeps blood flowing after yesterday's 10-mile effort.' No sycophantic language.",
    }
    required_fields = ["coach_noticed", "today_context", "week_assessment", "morning_voice"]
    if checkin_data:
        required_fields.append("checkin_reaction")
    if race_data:
        required_fields.append("race_assessment")

    return (None, prompt, schema_fields, required_fields, cache_key)


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
                lag_days = int(corr.get("time_lag_days", 0) or 0)
                if lag_days == 0:
                    lag_phrase = "same day"
                elif lag_days == 1:
                    lag_phrase = "the following day"
                else:
                    lag_phrase = f"within {lag_days} days"
                text = (
                    f"{input_name.replace('_', ' ').title()} {direction} correlates "
                    f"with your efficiency (r={r:.2f}, {n} observations). "
                    f"Timing signal: effect usually appears {lag_phrase}."
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


def _build_rich_intelligence_context(athlete_id: str, db: Session) -> str:
    """
    Assemble deep intelligence from five sources into a single prompt section.

    Each source runs in its own try/except — any failure is logged and skipped.
    If all sources return nothing, returns "".

    Sources (in order of insertion into prompt):
    1. N=1 insights (Bonferroni-corrected personal patterns)
    2. Daily intelligence rules that fired today
    3. Wellness trends (28-day check-in aggregation)
    4. PB patterns (training conditions preceding personal bests)
    5. This block vs previous block (28-day period comparison)
    """
    from uuid import UUID as _UUID
    athlete_uuid = _UUID(athlete_id)

    sections: list[str] = []

    # 1. N=1 personal patterns — crown jewels
    try:
        from services.n1_insight_generator import generate_n1_insights
        n1_insights = generate_n1_insights(athlete_uuid, db, max_insights=5)
        if n1_insights:
            lines = [
                f"- {ins.text} (confidence: {ins.confidence:.2f})"
                for ins in n1_insights
            ]
            sections.append(
                "--- Personal Patterns (N=1, statistically validated) ---\n"
                + "\n".join(lines)
            )
    except Exception as e:
        logger.warning(f"N=1 insights failed for home briefing ({athlete_id}): {e}")

    # 2. Daily intelligence rules that fired today
    try:
        from services.daily_intelligence import DailyIntelligenceEngine, InsightMode
        intel_result = DailyIntelligenceEngine().evaluate(athlete_uuid, date.today(), db)
        fired = [
            ins for ins in intel_result.insights
            if ins.mode != InsightMode.LOG
        ]
        if fired:
            lines = [f"- [{ins.rule_id}] {ins.message}" for ins in fired]
            sections.append(
                "--- Today's Intelligence Rules ---\n"
                + "\n".join(lines)
            )
    except Exception as e:
        logger.debug(f"Daily intelligence rules failed for home briefing ({athlete_id}): {e}")

    # 3. Wellness trends (28 days of check-in data)
    try:
        from services.coach_tools import get_wellness_trends
        wt = get_wellness_trends(db, athlete_uuid, days=28)
        narrative = wt.get("narrative", "")
        if narrative and "No wellness data" not in narrative:
            sections.append("--- Wellness Trends (28 days) ---\n" + narrative)
    except Exception as e:
        logger.debug(f"Wellness trends failed for home briefing ({athlete_id}): {e}")

    # 4. PB patterns
    try:
        from services.coach_tools import get_pb_patterns
        pb = get_pb_patterns(db, athlete_uuid)
        narrative = pb.get("narrative", "")
        if narrative:
            sections.append("--- PB Patterns ---\n" + narrative)
    except Exception as e:
        logger.debug(f"PB patterns failed for home briefing ({athlete_id}): {e}")

    # 5. This block vs previous block
    try:
        from services.coach_tools import compare_training_periods
        ctp = compare_training_periods(db, athlete_uuid, days=28)
        narrative = ctp.get("narrative", "")
        if narrative:
            sections.append("--- This Block vs Previous ---\n" + narrative)
    except Exception as e:
        logger.debug(f"Compare training periods failed for home briefing ({athlete_id}): {e}")

    if not sections:
        return ""

    return (
        "=== DEEP INTELLIGENCE (what the athlete CANNOT know from looking at their data) ===\n\n"
        + "\n\n".join(sections)
    )


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


def _lttb_1d(values: list, target: int) -> list:
    """Largest-Triangle-Three-Buckets downsampling for a 1D array.

    Treats index as x and value as y. Returns a list of length ``target``.
    This is the same LTTB algorithm used in the stream-analysis router for
    per-point data — applied here to the effort_intensity scalar array.
    """
    n = len(values)
    if n <= target:
        return values

    sampled = [values[0]]
    bucket_size = (n - 2) / (target - 2)

    a_idx = 0
    for i in range(1, target - 1):
        bucket_start = int((i - 1) * bucket_size) + 1
        bucket_end = min(int(i * bucket_size) + 1, n - 1)

        next_start = int(i * bucket_size) + 1
        next_end = min(int((i + 1) * bucket_size) + 1, n)

        # Average of next bucket
        avg_x = sum(range(next_start, next_end)) / max(1, next_end - next_start)
        avg_y = sum(values[j] for j in range(next_start, next_end)) / max(1, next_end - next_start)

        # Pick point with max triangle area
        max_area = -1
        best_idx = bucket_start
        a_x = a_idx
        a_y = values[a_idx]

        for j in range(bucket_start, bucket_end):
            area = abs(
                (a_x - avg_x) * (values[j] - a_y)
                - (a_x - j) * (avg_y - a_y)
            )
            if area > max_area:
                max_area = area
                best_idx = j

        sampled.append(values[best_idx])
        a_idx = best_idx

    sampled.append(values[-1])
    return sampled


def compute_last_run(
    athlete_id,
    db: Session,
) -> Optional[LastRun]:
    """RSI Layer 1: Build last_run for the home hero canvas.

    Rules (from RSI_WIRING_SPEC Layer 1):
    - Only the most recent activity within 96 hours (4 days)
    - If latest activity is >96h old, return None
    - When stream_fetch_status == 'success': serve from cached analysis
      (spec decision: "Cache full StreamAnalysisResult in DB")
    - effort_intensity is LTTB downsampled to ~500 points

    Note: 96h ensures there's always a run showing unless the athlete
    is injured or taking an extended break. Most training plans have
    at least one run every 3-4 days. Demo accounts skip the cutoff
    entirely so the demo always has a hero visible.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=96)

    # First try within the 96h window
    latest = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= cutoff,
        )
        .order_by(desc(Activity.start_time))
        .first()
    )

    # Demo accounts: if nothing in 96h, show most recent regardless of age
    if latest is None:
        latest = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete_id,
                Activity.source == "demo",
            )
            .order_by(desc(Activity.start_time))
            .first()
        )

    if latest is None:
        return None

    # Derive pace from distance/time
    pace_per_km = None
    if latest.distance_m and latest.duration_s and latest.distance_m > 0:
        pace_per_km = round(latest.duration_s / (latest.distance_m / 1000.0), 1)

    stream_status = getattr(latest, "stream_fetch_status", None)

    # Base last_run (metrics-only card when stream not ready)
    last_run = LastRun(
        activity_id=str(latest.id),
        name=latest.name or "Run",
        start_time=latest.start_time.isoformat(),
        distance_m=latest.distance_m,
        moving_time_s=latest.duration_s,
        average_hr=latest.avg_hr,
        stream_status=stream_status,
        pace_per_km=pace_per_km,
    )

    # Enrich with stream analysis data when available — serve from cache
    if stream_status == "success":
        try:
            stream_row = (
                db.query(ActivityStream)
                .filter(ActivityStream.activity_id == latest.id)
                .first()
            )
            if stream_row and stream_row.stream_data:
                from services.run_stream_analysis import AthleteContext
                from services.stream_analysis_cache import get_or_compute_analysis

                athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
                athlete_ctx = AthleteContext(
                    max_hr=getattr(athlete, "max_hr", None),
                    resting_hr=getattr(athlete, "resting_hr", None),
                    threshold_hr=getattr(athlete, "threshold_hr", None),
                )

                # Serve from cache (or compute + cache on first hit)
                result_dict = get_or_compute_analysis(
                    activity_id=latest.id,
                    stream_row=stream_row,
                    athlete_ctx=athlete_ctx,
                    db=db,
                    planned_workout_dict=None,  # Home doesn't need plan comparison
                )

                # LTTB downsample effort_intensity to ~500 points
                effort = result_dict.get("effort_intensity", [])
                if len(effort) > 500:
                    effort = _lttb_1d(effort, 500)

                last_run.effort_intensity = [round(e, 4) for e in effort]
                last_run.tier_used = result_dict.get("tier_used")
                last_run.confidence = result_dict.get("confidence")

                # Extract pace_stream from velocity_smooth (m/s → s/km)
                raw_velocity = stream_row.stream_data.get("velocity_smooth", [])
                if raw_velocity and len(raw_velocity) > 0:
                    # Convert m/s to pace (s/km); clamp zero/near-zero velocity
                    pace_raw = [
                        round(1000.0 / max(v, 0.3), 1) if v and v > 0.3 else 1200.0
                        for v in raw_velocity
                    ]
                    if len(pace_raw) > 500:
                        pace_raw = _lttb_1d(pace_raw, 500)
                    last_run.pace_stream = [round(p, 1) for p in pace_raw]

                # Extract elevation_stream from altitude
                raw_altitude = stream_row.stream_data.get("altitude", [])
                if raw_altitude and len(raw_altitude) > 0:
                    if len(raw_altitude) > 500:
                        raw_altitude = _lttb_1d(raw_altitude, 500)
                    last_run.elevation_stream = [round(a, 1) for a in raw_altitude]

                segments_raw = result_dict.get("segments", [])
                last_run.segments = [
                    LastRunSegment(
                        type=seg.get("type", "steady"),
                        start_time_s=seg.get("start_time_s", 0),
                        end_time_s=seg.get("end_time_s", 0),
                        duration_s=seg.get("duration_s", 0),
                        avg_pace_s_km=seg.get("avg_pace_s_km"),
                    )
                    for seg in segments_raw
                ]
        except Exception as e:
            logger.warning(f"Last run stream analysis failed: {type(e).__name__}: {e}")
            # Graceful degradation: keep last_run with metrics only

    return last_run


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
            sleep_quality_map = {5: 'Great', 4: 'Good', 3: 'OK', 2: 'Poor', 1: 'Awful'}
            # Legacy fallback: old rows stored quality as fake hours in sleep_h
            sleep_legacy_map = {8: 'Great', 7: 'OK', 5: 'Poor'}
            soreness_map = {1: 'None', 2: 'Mild', 4: 'Yes'}

            # Prefer sleep_quality_1_5; fall back to legacy sleep_h mapping for old rows
            sleep_quality_val = getattr(existing_checkin, 'sleep_quality_1_5', None)
            if sleep_quality_val is not None:
                sleep_label = sleep_quality_map.get(int(sleep_quality_val))
            elif existing_checkin.sleep_h is not None:
                sleep_label = sleep_legacy_map.get(int(existing_checkin.sleep_h))
            else:
                sleep_label = None

            today_checkin = TodayCheckin(
                motivation_label=motivation_map.get(
                    int(existing_checkin.motivation_1_5) if existing_checkin.motivation_1_5 is not None else -1
                ),
                sleep_label=sleep_label,
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

    # --- Phase 2 (ADR-17) / ADR-065: LLM Coach Briefing ---
    # Lane 2A: briefing is served from Redis cache, never inline LLM.
    # If cache is stale or missing, a Celery task is enqueued (fire-and-forget).
    coach_briefing = None
    briefing_state = "missing"

    # P1-D: Consent gate — no AI processing without explicit opt-in.
    from services.consent import has_ai_consent as _has_consent
    _ai_allowed = _has_consent(athlete_id=current_user.id, db=db)

    if not _ai_allowed:
        briefing_state = "consent_required"
    elif has_any_activities:
        try:
            _use_cache_briefing = is_feature_enabled(
                "lane_2a_cache_briefing", str(current_user.id), db
            )
            if _use_cache_briefing:
                from services.home_briefing_cache import read_briefing_cache, BriefingState
                from tasks.home_briefing_tasks import enqueue_briefing_refresh

                cached_payload, b_state = read_briefing_cache(str(current_user.id))
                briefing_state = b_state.value
                coach_briefing = cached_payload

                if b_state in (BriefingState.STALE, BriefingState.MISSING):
                    try:
                        enqueue_briefing_refresh(str(current_user.id))
                    except Exception as enq_err:
                        logger.warning(
                            "Home briefing enqueue failed (non-blocking): %s", enq_err
                        )

                logger.info(
                    f"Home briefing cache: state={briefing_state} "
                    f"athlete={current_user.id}"
                )
            else:
                # Legacy inline path (preserved until Lane 2A stable)
                briefing_state = None
                today_actual = db.query(Activity).filter(
                    Activity.athlete_id == current_user.id,
                    Activity.start_time >= today,
                    Activity.start_time < today + timedelta(days=1),
                ).order_by(Activity.start_time.desc()).first()

                today_completed = None
                if today_actual:
                    actual_mi = round(today_actual.distance_m / 1609.344, 1) if today_actual.distance_m else None
                    actual_pace = None
                    if today_actual.distance_m and today_actual.duration_s:
                        pace_s = today_actual.duration_s / (today_actual.distance_m / 1609.344)
                        mins = int(pace_s // 60)
                        secs = int(pace_s % 60)
                        actual_pace = f"{mins}:{secs:02d}/mi"
                    today_completed = {
                        "name": today_actual.name or "Run",
                        "distance_mi": actual_mi,
                        "pace": actual_pace,
                        "avg_hr": int(today_actual.avg_hr) if today_actual.avg_hr else None,
                        "duration_min": round(today_actual.duration_s / 60, 0) if today_actual.duration_s else None,
                    }

                planned_workout_dict = None
                if today_workout and today_workout.has_workout:
                    planned_workout_dict = {
                        "has_workout": True,
                        "workout_type": today_workout.workout_type,
                        "title": today_workout.title,
                        "distance_mi": today_workout.distance_mi,
                    }

                race_data_dict = None
                if race_countdown:
                    race_data_dict = {
                        "race_name": race_countdown.race_name,
                        "days_remaining": race_countdown.days_remaining,
                        "goal_time": race_countdown.goal_time,
                    }

                checkin_data_dict = None
                if today_checkin:
                    checkin_data_dict = {
                        "motivation_label": today_checkin.motivation_label,
                        "sleep_label": today_checkin.sleep_label,
                        "soreness_label": today_checkin.soreness_label,
                    }

                prep = generate_coach_home_briefing(
                    athlete_id=str(current_user.id),
                    db=db,
                    today_completed=today_completed,
                    planned_workout=planned_workout_dict,
                    checkin_data=checkin_data_dict,
                    race_data=race_data_dict,
                )

                if len(prep) == 1:
                    coach_briefing = prep[0]
                else:
                    _, prompt, schema_fields, required_fields, cache_key = prep
                    try:
                        coach_briefing = await asyncio.wait_for(
                            asyncio.to_thread(
                                _fetch_llm_briefing_sync,
                                prompt=prompt,
                                schema_fields=schema_fields,
                                required_fields=required_fields,
                                checkin_data=checkin_data_dict,
                                race_data=race_data_dict,
                                cache_key=cache_key,
                                athlete_id=str(current_user.id),
                            ),
                            timeout=HOME_BRIEFING_TIMEOUT_S,
                        )
                    except asyncio.TimeoutError:
                        logger.warning(
                            "Coach home briefing timed out at callsite (%ss)",
                            HOME_BRIEFING_TIMEOUT_S,
                        )
                        coach_briefing = None
        except Exception as e:
            logger.warning(f"Coach briefing failed: {type(e).__name__}: {e}")

    # --- RSI Layer 1: Last Run Hero ---
    last_run = None
    if has_any_activities:
        try:
            last_run = compute_last_run(current_user.id, db)
        except Exception as e:
            logger.warning(f"Last run computation failed: {type(e).__name__}: {e}")

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
        briefing_state=briefing_state,
        last_run=last_run,
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


# --- ADR-065: Admin Refresh Endpoint ---

@router.post("/admin/briefing-refresh/{athlete_id}", status_code=202)
async def admin_refresh_briefing(
    athlete_id: str,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manually trigger a home briefing refresh for an athlete.
    Requires admin or owner role. Audit-logged.
    """
    from core.auth import require_admin
    from services.audit_logger import log_audit
    from uuid import UUID

    if current_user.role not in ("admin", "owner"):
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Required roles: ['admin', 'owner']",
        )

    from tasks.home_briefing_tasks import enqueue_briefing_refresh

    enqueued = enqueue_briefing_refresh(athlete_id)

    log_audit(
        action="home_briefing.admin_refresh",
        athlete_id=UUID(athlete_id),
        success=enqueued,
        metadata={
            "triggered_by": str(current_user.id),
            "triggered_by_email": current_user.email,
            "enqueued": enqueued,
        },
    )

    return {"status": "enqueued" if enqueued else "skipped", "athlete_id": athlete_id}
