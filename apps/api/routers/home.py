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
from statistics import mean, median, pstdev
from typing import Optional, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel, ConfigDict
import asyncio
import logging
import redis  # noqa: F401 — imported for test patching via 'routers.home.redis'

from core.database import get_db
from core.auth import get_current_user
from core.feature_flags import is_feature_enabled
from models import Athlete, Activity, ActivitySplit, ActivityStream, PlannedWorkout, TrainingPlan, CalendarInsight, DailyCheckin
from services.n1_insight_generator import friendly_signal_name
from services.plan_lifecycle import get_active_plan_for_athlete
from services.timezone_utils import (
    get_athlete_timezone,
    get_athlete_timezone_from_db,
    athlete_local_today,
    to_activity_local_date,
    local_day_bounds_utc,
)

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
    sport: Optional[str] = None
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
    finding_id: Optional[str] = None  # CorrelationFinding UUID for briefing→coach deep link

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
    readiness_label: Optional[str] = None
    sleep_label: Optional[str] = None
    sleep_h: Optional[float] = None  # Numeric sleep hours for LLM grounding
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
    provider: Optional[str] = None  # 'strava' | 'garmin' | 'manual'
    device_name: Optional[str] = None  # Garmin device name, e.g. 'forerunner965'
    shape_sentence: Optional[str] = None
    athlete_title: Optional[str] = None
    resolved_title: Optional[str] = None
    heat_adjustment_pct: Optional[float] = None
    workout_classification: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class HomeFinding(BaseModel):
    """A single confirmed correlation finding surfaced on Home."""
    text: str
    confidence_tier: str
    domain: str
    times_confirmed: int

    model_config = ConfigDict(from_attributes=True)


class RecentCrossTraining(BaseModel):
    """Most recent non-run activity in the last 24h for home page acknowledgment."""
    id: str
    sport: str
    name: Optional[str] = None
    distance_m: Optional[float] = None
    duration_s: Optional[int] = None
    avg_hr: Optional[int] = None
    steps: Optional[int] = None
    active_kcal: Optional[int] = None
    start_time: str
    additional_count: int = 0


class HomeResponse(BaseModel):
    """Complete home page data."""
    today: TodayWorkout
    yesterday: YesterdayInsight
    week: WeekProgress
    hero_narrative: Optional[str] = None  # Hero sentence for first-3-seconds impact (ADR-033)
    strava_connected: bool = False  # Whether user has connected Strava
    garmin_connected: bool = False  # Whether user has connected Garmin Connect
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
    briefing_is_interim: bool = False
    briefing_last_updated_at: Optional[str] = None
    briefing_source: Optional[str] = None  # llm | deterministic_fallback
    # --- RSI Layer 1 ---
    last_run: Optional[LastRun] = None  # Most recent run within 96h for hero canvas
    # --- Path A surfaces ---
    finding: Optional[HomeFinding] = None
    has_correlations: bool = False
    # --- Daily wellness ---
    garmin_wellness: Optional[dict] = None
    # --- Cross-training acknowledgment ---
    recent_cross_training: Optional[RecentCrossTraining] = None

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
    Get correlation-based context for today's workout from persisted findings.

    Looks up active, confirmed CorrelationFinding rows (is_active=True,
    times_confirmed >= 3). Produces a short coaching-language sentence
    using the finding's domain, direction, and time lag.

    Returns:
        (context_string, source) or (None, None) if no eligible finding
    """
    try:
        from models import CorrelationFinding as _CF

        finding = (
            db.query(_CF)
            .filter(
                _CF.athlete_id == athlete_id,
                _CF.is_active.is_(True),
                _CF.times_confirmed >= 3,
            )
            .order_by(_CF.times_confirmed.desc())
            .first()
        )

        if not finding:
            return None, None

        inp = friendly_signal_name(finding.input_name)
        direction = "better" if finding.direction == "positive" else "harder"
        lag = finding.time_lag_days

        sentence = f"Your data shows {inp} affects your {direction} runs"
        if lag and lag > 0:
            sentence += f" with a {lag}-day lag"
        sentence += "."

        if finding.threshold_value is not None:
            sentence += f" The cliff is around {finding.threshold_value:.1f}."

        return sentence, "correlation"

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
    tsb_context: Optional[str] = None,
    preferred_units: Optional[str] = None,
) -> Optional[str]:
    """
    Generate a sparse trajectory sentence.
    Tone: Data speaks. No praise, no prescription.

    Includes TSB context when available.

    remaining_mi: Only counts today + future planned miles (excludes missed past days)
    Units are formatted per the athlete's preferred_units ("metric" -> km, else miles).
    """
    is_metric = (preferred_units or "imperial").lower() == "metric"
    unit = "km" if is_metric else "mi"

    def _fmt(value_mi: float) -> str:
        v = value_mi * 1.60934 if is_metric else value_mi
        return f"{v:.0f} {unit}"

    remaining = remaining_mi if remaining_mi > 0 else max(0, planned_mi - completed_mi)

    if status == "no_plan":
        if completed_mi > 0:
            if activities_this_week == 1:
                return f"{_fmt(completed_mi)} logged this week. Consistency compounds."
            elif activities_this_week > 1:
                base = f"{_fmt(completed_mi)} across {activities_this_week} runs this week."
                if tsb_context:
                    return f"{base} {tsb_context}"
                return base
        return None

    if status == "ahead":
        base = f"Ahead of schedule. {_fmt(completed_mi)} done of {_fmt(planned_mi)} planned."
    elif status == "on_track":
        base = f"On track. {_fmt(remaining)} remaining this week."
    elif status == "behind":
        base = f"Behind schedule. {_fmt(remaining)} to go."
    else:
        return None

    if tsb_context and len(base) < 60:
        return f"{base}"

    return base


def generate_yesterday_insight(activity: Activity) -> str:
    """
    Generate one sparse insight from yesterday's activity.
    Tone: Data speaks. No praise, no prescription.
    """
    if activity.shape_sentence:
        result = activity.shape_sentence
        if activity.avg_hr and activity.avg_hr > 165:
            result += f" (HR ran high — {activity.avg_hr} avg)"
        return result

    insights = []

    if hasattr(activity, 'efficiency_score') and activity.efficiency_score:
        if activity.efficiency_score > 0:
            insights.append(f"Efficiency {activity.efficiency_score:+.1f}% vs baseline.")
        elif activity.efficiency_score < 0:
            insights.append(f"Efficiency {activity.efficiency_score:.1f}% vs baseline.")

    if activity.avg_hr:
        if activity.avg_hr < 140:
            insights.append(f"HR stayed low ({activity.avg_hr} avg).")
        elif activity.avg_hr > 165:
            insights.append(f"HR ran high ({activity.avg_hr} avg).")

    if hasattr(activity, 'pace_variability') and activity.pace_variability:
        if activity.pace_variability < 5:
            insights.append("Consistent pacing.")
        elif activity.pace_variability > 15:
            insights.append("Variable pacing.")

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
    "home briefing", "synced activity", "refreshed from", "briefing is",
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

# 2026-04-18 — content-quality gates added after the founder showed a
# specific bad briefing. The skeleton is good in ~80% of generations;
# these gates catch the remaining ~20% where the LLM:
#   - asks the athlete a literal question instead of coaching,
#   - stitches two unrelated findings together with "Separately, ...",
#   - prefaces with "Your data shows a pattern worth discussing" filler,
#   - exceeds the 2-3 sentence morning_voice contract.
# All gates support strip-and-recover via _strip_disallowed_sentences:
# remove only the offending sentence and re-validate the remainder.
# Blanket fallback is the last resort, never the first.

# Multi-topic transitions — the LLM's tell that it is smuggling a second
# finding past the ONE-NEW-THING rule. Match at sentence start (after
# capital-letter normalisation) to avoid catching "see also" in valid
# coaching prose.
_VOICE_MULTI_TOPIC_TRANSITIONS = (
    "separately,",
    "additionally,",
    "also,",
    "meanwhile,",
    "on another note,",
    "beyond that,",
)

# Meta-preamble phrases — talking *about* having an observation rather
# than stating it. These are the LLM's hedge when the underlying signal
# is weak; better to say nothing than to preface emptiness.
_VOICE_META_PREAMBLE = (
    "your data shows",
    "worth discussing",
    "worth noting",
    "i've noticed a pattern",
    "looking at your data",
    "the data suggests",
    "there's a pattern worth",
)

# Hard cap on morning_voice sentences. The prompt asks for 2-3; we allow
# 3 and truncate above that. The cap is enforced after strip-and-recover
# so we don't punish a clean three-sentence rewrite of a bad five-line
# original.
_VOICE_SENTENCE_CAP = 3

# ---------------------------------------------------------------------------
# Sleep source contract helpers
# ---------------------------------------------------------------------------

# "hour" and "rest" are intentionally excluded: too broad (triggers on workout durations,
# rest days, 3-hour marathon goals). "sleep"/"slept"/"overnight"/"last night" are
# sleep-specific enough to scope the validator correctly.
_SLEEP_CONTEXT_KEYWORDS = {"sleep", "slept", "overnight", "last night"}
_SLEEP_MAX_H = 14.0   # upper bound for a plausible sleep value (vs workout minutes)
_SLEEP_TOLERANCE_H = 0.5  # slider rounding + sync lag allowance

_FINDING_COOLDOWN_TTL = 72 * 3600  # 72 hours


def _is_finding_in_cooldown(
    athlete_id: str,
    input_name: str,
    output_metric: str,
) -> bool:
    """Check if a correlation finding is in cooldown (surfaced within 72h)."""
    try:
        import redis as _r
        import os
        client = _r.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)
        key = f"finding_surfaced:{athlete_id}:{input_name}:{output_metric}"
        return client.get(key) is not None
    except Exception:
        return False  # Fail open


def _set_finding_cooldowns(
    athlete_id: str,
    briefing_text: str,
    injected_findings: list,
):
    """After briefing generation, set cooldown keys for surfaced findings."""
    try:
        import redis as _r
        import os
        client = _r.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)
        combined = briefing_text.lower()
        for finding in injected_findings:
            input_name = finding.get("input_name", "")
            output_metric = finding.get("output_metric", "")
            readable = friendly_signal_name(input_name)
            if readable and readable in combined:
                key = f"finding_surfaced:{athlete_id}:{input_name}:{output_metric}"
                client.setex(key, _FINDING_COOLDOWN_TTL, "1")
    except Exception:
        pass  # Fail open


def _build_checkin_data_dict(checkin) -> dict:
    """
    Build the checkin_data dict from a DailyCheckin ORM row.
    Centralised so request path and worker path stay in sync.
    Includes numeric sleep_h for LLM grounding (not just the label).
    """
    readiness_map = {5: "High", 4: "Good", 3: "Neutral", 2: "Low", 1: "Poor"}
    sleep_quality_map = {5: "Great", 4: "Good", 3: "OK", 2: "Poor", 1: "Awful"}
    sleep_legacy_map = {8: "Great", 7: "OK", 5: "Poor"}
    soreness_map = {1: "None", 2: "Mild", 4: "Yes"}

    sleep_quality_val = getattr(checkin, "sleep_quality_1_5", None)
    if sleep_quality_val is not None:
        sleep_label = sleep_quality_map.get(int(sleep_quality_val))
    elif checkin.sleep_h is not None:
        sleep_label = sleep_legacy_map.get(int(checkin.sleep_h))
    else:
        sleep_label = None

    sleep_h_val = float(checkin.sleep_h) if checkin.sleep_h is not None else None

    return {
        "readiness_label": readiness_map.get(
            int(checkin.readiness_1_5) if checkin.readiness_1_5 is not None else -1
        ),
        "sleep_label": sleep_label,
        "sleep_h": sleep_h_val,
        "soreness_label": soreness_map.get(
            int(checkin.soreness_1_5) if checkin.soreness_1_5 is not None else -1
        ),
    }


def _get_garmin_sleep_h_for_last_night(
    athlete_id: str, db
) -> tuple:
    """
    Query GarminDay for last night's sleep using athlete-local date.

    Returns (sleep_h_float, local_date_str, is_today).
    is_today=True means value is from athlete-local today (last-night semantics).
    is_today=False means fallback/stale date and must not be labeled "last night".

    Date resolution (wakeup-day semantics per L1 CalendarDate Rule):
      1. local_today   — sync usually arrives within minutes of wakeup
      2. local_today - 1 day — fallback for delayed sync

    Timezone fallback policy (explicit, no silent default):
      If athlete.timezone is None or invalid → use UTC date.
    """
    from datetime import datetime, timedelta, timezone as _tz
    from models import Athlete, GarminDay

    try:
        try:
            import zoneinfo
        except ImportError:
            import backports.zoneinfo as zoneinfo  # type: ignore

        athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
        tz_name = getattr(athlete, "timezone", None) if athlete else None

        if tz_name:
            try:
                tz = zoneinfo.ZoneInfo(tz_name)
                local_today = datetime.now(_tz.utc).astimezone(tz).date()
            except Exception:
                local_today = datetime.now(_tz.utc).date()
        else:
            # Explicit fallback: UTC when athlete has no timezone configured
            local_today = datetime.now(_tz.utc).date()

        for candidate_date in [local_today, local_today - timedelta(days=1)]:
            row = (
                db.query(GarminDay)
                .filter(
                    GarminDay.athlete_id == athlete_id,
                    GarminDay.calendar_date == candidate_date,
                    GarminDay.sleep_total_s.isnot(None),
                )
                .first()
            )
            if row and row.sleep_total_s:
                sleep_h = round(row.sleep_total_s / 3600, 2)
                is_today = candidate_date == local_today
                logger.debug(
                    "Garmin sleep grounding: athlete=%s date=%s sleep_h=%.2f is_today=%s",
                    athlete_id, candidate_date, sleep_h, is_today,
                )
                return sleep_h, str(candidate_date), is_today

        return None, str(local_today), False
    except Exception as e:
        logger.warning("_get_garmin_sleep_h_for_last_night failed (non-blocking): %s", e)
        return None, "unknown", False


def _build_garmin_wellness(athlete_id: str, db) -> Optional[dict]:
    """Build today's Garmin wellness snapshot with personal baseline ranges."""
    from datetime import datetime, timedelta, timezone as _tz
    from models import Athlete, GarminDay
    from sqlalchemy import func

    try:
        try:
            import zoneinfo
        except ImportError:
            import backports.zoneinfo as zoneinfo  # type: ignore

        athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete or not getattr(athlete, "garmin_connected", False):
            return None

        tz_name = getattr(athlete, "timezone", None)
        if tz_name:
            try:
                tz = zoneinfo.ZoneInfo(tz_name)
                local_today = datetime.now(_tz.utc).astimezone(tz).date()
            except Exception:
                local_today = datetime.now(_tz.utc).date()
        else:
            local_today = datetime.now(_tz.utc).date()

        today_row = None
        for candidate in [local_today, local_today - timedelta(days=1)]:
            row = (
                db.query(GarminDay)
                .filter(GarminDay.athlete_id == athlete_id, GarminDay.calendar_date == candidate)
                .first()
            )
            if row and (row.sleep_total_s or row.hrv_5min_high or row.resting_hr):
                today_row = row
                break

        if not today_row:
            return None

        range_start = local_today - timedelta(days=30)
        history = (
            db.query(GarminDay)
            .filter(
                GarminDay.athlete_id == athlete_id,
                GarminDay.calendar_date >= range_start,
                GarminDay.calendar_date <= local_today,
            )
            .all()
        )

        def _range_for(values):
            if len(values) < 7:
                return None
            return {"low": round(min(values)), "high": round(max(values))}

        def _status(val, range_dict):
            if not range_dict or val is None:
                return None
            spread = range_dict["high"] - range_dict["low"]
            if spread == 0:
                return "normal"
            low_third = range_dict["low"] + spread * 0.25
            high_third = range_dict["high"] - spread * 0.25
            if val <= low_third:
                return "low"
            if val >= high_third:
                return "high"
            return "normal"

        hrv_peak_vals = [r.hrv_5min_high for r in history if r.hrv_5min_high]
        hrv_avg_vals = [r.hrv_overnight_avg for r in history if r.hrv_overnight_avg]
        rhr_vals = [r.resting_hr for r in history if r.resting_hr]

        hrv_peak_range = _range_for(hrv_peak_vals)
        rhr_range = _range_for(rhr_vals)

        result: dict = {"date": str(today_row.calendar_date)}

        if today_row.sleep_total_s:
            result["sleep_h"] = round(today_row.sleep_total_s / 3600, 1)
        if today_row.sleep_score:
            result["sleep_score"] = today_row.sleep_score
            result["sleep_score_qualifier"] = today_row.sleep_score_qualifier

        if today_row.hrv_5min_high:
            result["recovery_hrv"] = today_row.hrv_5min_high
            result["recovery_hrv_status"] = _status(today_row.hrv_5min_high, hrv_peak_range)
            if hrv_peak_range:
                result["recovery_hrv_range"] = hrv_peak_range
        if today_row.hrv_overnight_avg:
            result["overnight_hrv"] = today_row.hrv_overnight_avg

        if today_row.resting_hr:
            result["resting_hr"] = today_row.resting_hr
            result["resting_hr_status"] = _status(today_row.resting_hr, rhr_range)
            if rhr_range:
                result["resting_hr_range"] = rhr_range

        if today_row.avg_stress and today_row.avg_stress >= 0:
            result["avg_stress"] = today_row.avg_stress

        return result

    except Exception as e:
        logger.warning("_build_garmin_wellness failed (non-blocking): %s", e)
        return None


def _build_sleep_baseline_guidance(
    athlete_id: str,
    db: Session,
    *,
    last_night_sleep_h: Optional[float],
) -> Optional[str]:
    """
    Build sleep-baseline prompt guidance from GarminDay history.

    Contract:
    - Use 90-day GarminDay.sleep_total_s history (Python stats, not DB percentile/stddev).
    - Require n >= 14 to inject any baseline guidance.
    - noteworthy threshold = max(1.0h, pstdev).
    """
    if last_night_sleep_h is None:
        return None

    try:
        from models import Athlete as _Athlete, GarminDay as _GarminDay
        from services.timezone_utils import get_athlete_timezone, athlete_local_today

        athlete = db.query(_Athlete).filter(_Athlete.id == athlete_id).first()
        athlete_tz = get_athlete_timezone(athlete)
        local_today = athlete_local_today(athlete_tz)
        start_date = local_today - timedelta(days=89)

        rows = (
            db.query(_GarminDay)
            .filter(
                _GarminDay.athlete_id == athlete_id,
                _GarminDay.calendar_date >= start_date,
                _GarminDay.calendar_date <= local_today,
                _GarminDay.sleep_total_s.isnot(None),
            )
            .order_by(_GarminDay.calendar_date.desc())
            .all()
        )
        sleep_hours = [
            round(float(r.sleep_total_s) / 3600.0, 2)
            for r in rows
            if r.sleep_total_s is not None
        ]
        n = len(sleep_hours)
        if n < 14:
            return None

        baseline_median = median(sleep_hours)
        baseline_avg = mean(sleep_hours)
        baseline_std = pstdev(sleep_hours) if n > 1 else 0.0
        threshold = max(1.0, baseline_std)
        deviation = abs(last_night_sleep_h - baseline_median)

        guidance_lines = [
            "=== SLEEP BASELINE CONTEXT (90 days) ===",
            (
                "SLEEP_BASELINE_STATS: "
                f"n={n}, median={baseline_median:.2f}h, avg={baseline_avg:.2f}h, std={baseline_std:.2f}h, "
                f"last_night={last_night_sleep_h:.2f}h, deviation={deviation:.2f}h, threshold={threshold:.2f}h"
            ),
        ]
        if deviation < threshold:
            guidance_lines.append("Sleep is NOT newsworthy today. Lead with something else.")
        else:
            guidance_lines.append("This IS noteworthy; frame as deviation from personal norm.")
        return "\n".join(guidance_lines)
    except Exception as e:
        logger.debug("Sleep baseline context skipped (non-blocking): %s", e)
        return None


def validate_sleep_claims(
    text: str,
    garmin_sleep_h: Optional[float],
    checkin_sleep_h: Optional[float],
) -> dict:
    """
    Validate that any numeric sleep claim in generated text is grounded
    to a known source within _SLEEP_TOLERANCE_H.

    Scope: only sentences containing sleep-context keywords are checked.
    Workout durations (e.g. "60-minute tempo", "3 hours 45 minutes marathon pace")
    are excluded because they either lack sleep keywords or exceed _SLEEP_MAX_H.

    Returns:
        {"valid": True}  — all claims are grounded (or no claims present)
        {"valid": False, "reason": str, "claim": float}  — ungrounded claim found
    """
    import re

    known_sources = [s for s in [garmin_sleep_h, checkin_sleep_h] if s is not None]
    # Match numeric values like 7, 7.5, 6.75 followed by h/hour/hours
    sleep_num_re = re.compile(r"(\d+(?:\.\d+)?)\s*(?:h\b|hours?)", re.IGNORECASE)

    # Split on sentence-ending punctuation only when NOT between digits (avoids
    # splitting "7.5 hours" into ["7", "5 hours"] at the decimal point).
    sentences = re.split(r"(?<!\d)[.!?](?!\d)", text)
    for sentence in sentences:
        lower = sentence.lower()
        if not any(k in lower for k in _SLEEP_CONTEXT_KEYWORDS):
            continue
        for m in sleep_num_re.finditer(sentence):
            val = float(m.group(1))
            if val > _SLEEP_MAX_H:
                continue  # Not a plausible sleep value (e.g. 90-minute run = 1.5h handled above)
            if not known_sources:
                return {
                    "valid": False,
                    "reason": f"sleep_claim_no_source:{val}h",
                    "claim": val,
                }
            if not any(abs(val - s) <= _SLEEP_TOLERANCE_H for s in known_sources):
                return {
                    "valid": False,
                    "reason": f"sleep_claim_ungrounded:{val}h (sources:{known_sources})",
                    "claim": val,
                }

    return {"valid": True}


def _strip_ungrounded_sleep_sentences(
    text: str,
    garmin_sleep_h: Optional[float],
    checkin_sleep_h: Optional[float],
) -> dict:
    """
    Remove sentence(s) containing ungrounded numeric sleep claims only.

    Preserves valid coaching content when a single sleep sentence is invalid.
    """
    import re

    if not text:
        return {"text": text, "removed": False}

    known_sources = [s for s in [garmin_sleep_h, checkin_sleep_h] if s is not None]
    sleep_num_re = re.compile(r"(\d+(?:\.\d+)?)\s*(?:h\b|hours?)", re.IGNORECASE)
    # Mirror sleep validator splitting semantics: do not split decimal numbers.
    chunks = [
        c.strip()
        for c in re.split(r"(?<!\d)[.!?](?!\d)", text)
        if c and c.strip()
    ]
    kept = []
    removed_any = False

    for chunk in chunks:
        sentence = chunk.strip()
        if not sentence:
            continue

        lower = sentence.lower()
        if not any(k in lower for k in _SLEEP_CONTEXT_KEYWORDS):
            kept.append(sentence)
            continue

        remove_sentence = False
        for m in sleep_num_re.finditer(sentence):
            val = float(m.group(1))
            if val > _SLEEP_MAX_H:
                continue
            if not known_sources:
                remove_sentence = True
                break
            if not any(abs(val - s) <= _SLEEP_TOLERANCE_H for s in known_sources):
                remove_sentence = True
                break

        if remove_sentence:
            removed_any = True
            continue
        kept.append(sentence)

    sanitized = " ".join(kept).strip()
    if sanitized and sanitized[-1] not in ".!?":
        sanitized += "."
    return {"text": sanitized, "removed": removed_any}


def _split_sentences(text: str) -> list:
    """Sentence-split that preserves terminators and does not break decimals.

    Returns list of sentences each ending with their original terminator
    (`.`, `!`, `?`). Terminator preservation is required for the
    interrogative gate to detect `?`-ending sentences after splitting.

    The pattern matches a run of non-terminator chars followed by an
    optional terminator. Decimal handling is enforced by a negative
    lookbehind+lookahead on the terminator (so 7.5 stays a single token).
    """
    import re

    if not text:
        return []
    # Each sentence is one-or-more body chars (anything that is NOT a
    # sentence terminator, OR a `.`/`!`/`?` that sits between digits and
    # therefore belongs to a number like 7.5), optionally followed by a
    # real terminator (one not between digits). The mid-number dot
    # accommodation is what makes "7.5 hours" stay a single token while
    # still allowing the trailing period of the sentence to be captured.
    pattern = re.compile(
        r"(?:[^.!?]|(?<=\d)[.!?](?=\d))+(?:(?<!\d)[.!?](?!\d))?"
    )
    return [m.group(0).strip() for m in pattern.finditer(text) if m.group(0).strip()]


def _sentence_has_disallowed_content(sentence: str) -> Optional[str]:
    """Return a reason string if the sentence trips a content gate.

    Gates checked (in order):
      1. interrogative — sentence contains a literal question mark.
      2. multi_topic   — starts with a banned transition phrase.
      3. meta_preamble — contains any banned meta-preamble phrase.

    Returns None if the sentence is clean.
    """
    if not sentence:
        return None
    lower = sentence.lower().lstrip()

    if "?" in sentence:
        return "interrogative"

    for transition in _VOICE_MULTI_TOPIC_TRANSITIONS:
        if lower.startswith(transition):
            return f"multi_topic:{transition.rstrip(',')}"

    for preamble in _VOICE_META_PREAMBLE:
        if preamble in lower:
            return f"meta_preamble:{preamble}"

    return None


def _strip_disallowed_sentences(text: str) -> dict:
    """Remove sentences that trip content gates; preserve the rest.

    Used by the morning_voice and coach_noticed validators as the
    strip-and-recover pass before falling back to the deterministic
    string. Keeps the 80% of good content intact when only a single
    sentence is bad.

    Returns:
        {"text": str, "removed": bool, "reasons": list[str]}
    """
    if not text:
        return {"text": text, "removed": False, "reasons": []}

    sentences = _split_sentences(text)
    kept: list = []
    reasons: list = []

    for s in sentences:
        reason = _sentence_has_disallowed_content(s)
        if reason is not None:
            reasons.append(reason)
            continue
        kept.append(s)

    if not reasons:
        return {"text": text, "removed": False, "reasons": []}

    sanitized = " ".join(kept).strip()
    if sanitized and sanitized[-1] not in ".!?":
        sanitized += "."
    return {"text": sanitized, "removed": True, "reasons": reasons}


def validate_voice_output(text: str, field: str = "morning_voice") -> dict:
    """
    Post-generation validator for LLM-produced morning_voice / workout_why.

    Fail-closed: if ANY check fails, returns valid=False with a deterministic
    fallback. There is no bypass flag, no warn-only mode.

    Checks:
      1. Ban-list — sycophantic/hyperbolic language
      2. Causal language — no pseudo-causal claims
      3. Numeric grounding — at least one number present
      4. Length — minimum 40 characters (no upper cap; structure is controlled by prompt)

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

    # 3b. Specificity gate — morning_voice must reference athlete-specific
    # content, not generic template filler. Catches LLM outputs like
    # "Your training data is ready" that pass numeric grounding (if a
    # stray number exists) but contain zero personalization.
    if field == "morning_voice":
        _TEMPLATE_PHRASES = [
            "training data is ready",
            "check your workout below",
            "check below for today",
            "data is ready for review",
            "your data has been updated",
            "briefing is refreshed",
            "your plan is ready",
            "training is on track",
            "everything looks good",
            "keep up the good work",
            "stay consistent",
        ]
        if any(tp in lower for tp in _TEMPLATE_PHRASES):
            return {
                "valid": False,
                "reason": "specificity:template_phrase_detected",
                "fallback": _VOICE_FALLBACK,
            }

        _SPECIFICITY_MARKERS = [
            r"\d+\.?\d*\s*(mi|km|miles|k\b)",
            r"\d+:\d{2}",
            r"\d+\s*bpm",
            r"yesterday|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday",
            r"your (last|latest|recent) (run|workout|session|effort)",
            r"(easy|tempo|threshold|interval|long run|recovery|quality)",
            r"\d+x\d+",
        ]
        if not any(re.search(pat, lower) for pat in _SPECIFICITY_MARKERS):
            return {
                "valid": False,
                "reason": "specificity:no_athlete_specific_content",
                "fallback": _VOICE_FALLBACK,
            }

    # 4. Length check — minimum only; no upper cap.
    if field in ("morning_voice", "workout_why"):
        if len(text) < 40:
            return {
                "valid": False,
                "reason": f"length:too_short({len(text)})",
                "fallback": _VOICE_FALLBACK,
            }

    # 5. Paragraph enforcement for morning_voice.
    # Prompt-only constraints drift; this is the hard structural backstop.
    if field == "morning_voice":
        stripped = text.strip()
        if "\n" in stripped:
            paragraphs = [p.strip() for p in re.split(r"\n+", stripped) if p.strip()]
            if len(paragraphs) > 1:
                first_para = paragraphs[0]
                if len(first_para) >= 40 and re.search(r"\d", first_para):
                    logger.warning(
                        "morning_voice had %d paragraphs; truncated to first (%d chars)",
                        len(paragraphs),
                        len(first_para),
                    )
                    return {"valid": True, "truncated_text": first_para}
                return {
                    "valid": False,
                    "reason": "structure:multiple_paragraphs_short_first",
                    "fallback": _VOICE_FALLBACK,
                }

    # 6. Content quality gates (added 2026-04-18).
    # Scope: morning_voice and coach_noticed. workout_why is a conceptual
    # one-liner and exempt — see test_workout_why_may_contain_question_mark.
    if field in ("morning_voice", "coach_noticed"):
        for sentence in _split_sentences(text):
            reason = _sentence_has_disallowed_content(sentence)
            if reason is not None:
                logger.info(
                    "voice gate fired field=%s reason=%s sentence=%r",
                    field, reason, sentence[:120],
                )
                return {
                    "valid": False,
                    "reason": reason,
                    "fallback": _VOICE_FALLBACK,
                }

    # 7. Sentence cap for morning_voice (max 3 sentences, contract is 2-3).
    # If over the cap, truncate to the first three and signal via
    # truncated_text so the caller can substitute it. We only keep the
    # truncated text when it still satisfies the earlier gates (numeric
    # grounding + length + specificity) — otherwise we fall back so we
    # never publish a half-thought.
    if field == "morning_voice":
        sentences = _split_sentences(text)
        if len(sentences) > _VOICE_SENTENCE_CAP:
            truncated = ". ".join(sentences[:_VOICE_SENTENCE_CAP]).strip()
            if truncated and truncated[-1] not in ".!?":
                truncated += "."
            # Re-check the truncated text against the cheap gates that
            # could regress (numeric grounding, length, specificity, and
            # the same content gates). If anything fires, we surface the
            # cap reason so the caller chooses fallback over silently
            # publishing a degraded shorter version.
            recheck = validate_voice_output(truncated, field=field)
            if recheck.get("valid") and not recheck.get("truncated_text"):
                logger.warning(
                    "morning_voice exceeded sentence cap (%d > %d); truncated",
                    len(sentences), _VOICE_SENTENCE_CAP,
                )
                return {"valid": True, "truncated_text": truncated}
            return {
                "valid": False,
                "reason": (
                    f"sentence_cap:{len(sentences)}>"
                    f"{_VOICE_SENTENCE_CAP}"
                ),
                "fallback": _VOICE_FALLBACK,
            }

    return {"valid": True}


def _normalize_cached_briefing_payload(
    payload: Optional[dict],
    garmin_sleep_h: Optional[float],
    checkin_sleep_h: Optional[float],
) -> Optional[dict]:
    """
    Normalize/sanitize cached coach briefing payload on read.

    Why this exists:
    - Cache entries can outlive a deploy and contain pre-fix text.
    - We need read-time guardrails so old cached content cannot leak:
      - multi-paragraph morning_voice
      - ungrounded sleep claims
      - internal metrics in coach_noticed
    """
    if not payload or not isinstance(payload, dict):
        return None

    out = dict(payload)

    raw_voice = out.get("morning_voice")
    if raw_voice:
        voice_check = validate_voice_output(raw_voice, field="morning_voice")
        if not voice_check.get("valid"):
            # Strip-and-recover before falling back to the deterministic
            # string. Old cache entries from before the content gates
            # were added contain partially-bad text that is fully
            # recoverable by removing the offending sentence(s).
            stripped = _strip_disallowed_sentences(raw_voice)
            recovered = False
            if stripped["removed"] and stripped["text"]:
                recheck = validate_voice_output(
                    stripped["text"], field="morning_voice"
                )
                if recheck.get("valid"):
                    out["morning_voice"] = (
                        recheck.get("truncated_text") or stripped["text"]
                    )
                    recovered = True
            if not recovered:
                out["morning_voice"] = voice_check.get(
                    "fallback", _VOICE_FALLBACK
                )
        elif voice_check.get("truncated_text"):
            out["morning_voice"] = voice_check["truncated_text"]

        final_voice = out.get("morning_voice") or ""
        if final_voice and final_voice != _VOICE_FALLBACK:
            sleep_check = validate_sleep_claims(final_voice, garmin_sleep_h, checkin_sleep_h)
            if not sleep_check.get("valid"):
                stripped = _strip_ungrounded_sleep_sentences(
                    final_voice, garmin_sleep_h, checkin_sleep_h
                )
                candidate = stripped.get("text") or ""
                if candidate:
                    candidate_voice_check = validate_voice_output(candidate, field="morning_voice")
                    candidate_sleep_check = validate_sleep_claims(
                        candidate, garmin_sleep_h, checkin_sleep_h
                    )
                    if candidate_voice_check.get("valid") and candidate_sleep_check.get("valid"):
                        out["morning_voice"] = candidate
                    else:
                        out["morning_voice"] = _VOICE_FALLBACK
                else:
                    out["morning_voice"] = _VOICE_FALLBACK
    elif "morning_voice" in out:
        out["morning_voice"] = _VOICE_FALLBACK

    raw_noticed = out.get("coach_noticed")
    if raw_noticed:
        noticed_check = validate_voice_output(raw_noticed, field="coach_noticed")
        if not noticed_check.get("valid"):
            out["coach_noticed"] = None

    return out


def _sanitize_finding_text(text: str) -> str:
    """Normalize legacy/internal tokens in athlete-facing finding text."""
    if not text:
        return text
    out = text
    import re

    # Legacy all-caps pronoun appears in some persisted findings; normalize tone.
    out = re.sub(r"\bYOUR\b", "your", out)

    replacements = (
        ("your tsb", "your form"),
        ("your ctl", "your fitness"),
        ("your atl", "your fatigue"),
    )
    for raw, clean in replacements:
        out = out.replace(raw, clean)
        out = out.replace(raw.title(), clean.title())

    out = re.sub(r"\btsb\b", "form", out, flags=re.IGNORECASE)
    out = re.sub(r"\bctl\b", "fitness", out, flags=re.IGNORECASE)
    out = re.sub(r"\batl\b", "fatigue", out, flags=re.IGNORECASE)

    # Backward compatibility: persisted findings may still contain raw signal keys
    # (underscore/space/dotted variants). Normalize to friendly labels at read-time.
    try:
        from services.n1_insight_generator import FRIENDLY_NAMES
    except Exception:  # pragma: no cover - defensive fallback
        FRIENDLY_NAMES = {}

    for raw_key in sorted(FRIENDLY_NAMES.keys(), key=len, reverse=True):
        friendly = friendly_signal_name(raw_key)
        if not friendly:
            continue
        variants = {
            raw_key,
            raw_key.replace("_", " "),
            raw_key.replace("_", "."),
        }
        parts = raw_key.split("_")
        if len(parts) >= 3 and parts[-1].isdigit() and parts[-2].isdigit():
            stem = "_".join(parts[:-2])
            stem_space = stem.replace("_", " ")
            a, b = parts[-2], parts[-1]
            variants.update({
                f"{stem} {a}.{b}",
                f"{stem_space} {a}.{b}",
                f"{stem} {a}/{b}",
                f"{stem_space} {a}/{b}",
            })
        for variant in variants:
            if not variant or variant.lower() == friendly.lower():
                continue
            pattern = rf"(?<![A-Za-z0-9]){re.escape(variant)}(?![A-Za-z0-9])"
            out = re.sub(pattern, friendly, out, flags=re.IGNORECASE)
    return out


def validate_relative_time_claims(
    text: str,
    recent_run_dates: List[date],
    today: Optional[date] = None,
) -> dict:
    """
    Catch obviously wrong relative-time claims in LLM output.

    Scans text for phrases like "two weeks ago", "a month ago", etc.
    and cross-references against the most recent activity dates.
    If the most recent run was within 7 days but the text says
    "weeks ago" or "month ago", the claim is invalid.

    Returns {"valid": True} or {"valid": False, "reason": ...}.
    """
    import re

    if not text or not recent_run_dates:
        return {"valid": True}

    lower = text.lower()
    if today is None:
        today = date.today()

    most_recent = max(recent_run_dates)
    days_since_most_recent = (today - most_recent).days

    weeks_phrases = [
        r"\btwo weeks?\b", r"\bthree weeks?\b", r"\bfour weeks?\b",
        r"\bseveral weeks?\b", r"\ba few weeks?\b", r"\bweeks? ago\b",
    ]
    months_phrases = [
        r"\ba month ago\b", r"\bmonths? ago\b", r"\blast month\b",
    ]

    if days_since_most_recent <= 7:
        for pattern in weeks_phrases + months_phrases:
            if re.search(pattern, lower):
                return {
                    "valid": False,
                    "reason": (
                        f"relative_time:claimed_weeks_or_months_but_most_recent_run_was"
                        f"_{days_since_most_recent}_days_ago"
                    ),
                }

    if days_since_most_recent <= 3:
        if re.search(r"\blast week\b", lower):
            return {
                "valid": False,
                "reason": (
                    f"relative_time:claimed_last_week_but_most_recent_run_was"
                    f"_{days_since_most_recent}_days_ago"
                ),
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
    # Require checkin_reaction only when we have a real athlete check-in payload.
    # `checkin_data` may be populated with Garmin metadata only (e.g. garmin_sleep_h),
    # which should not force a hard A->I->A failure.
    checkin_requires_reaction = bool(
        checkin_data
        and isinstance(checkin_data, dict)
        and any(k != "garmin_sleep_h" for k in checkin_data.keys())
    )
    if checkin_requires_reaction and not result.get("checkin_reaction"):
        return False

    # Require race_assessment only when the race is meaningfully near.
    # Long-horizon plans often include race metadata months out; forcing this
    # field at all times caused avoidable deterministic fallbacks.
    race_requires_assessment = False
    if race_data and isinstance(race_data, dict):
        days_remaining = race_data.get("days_remaining")
        if isinstance(days_remaining, int) and days_remaining <= 21:
            race_requires_assessment = True
    if race_requires_assessment and not result.get("race_assessment"):
        return False
    return True


HOME_BRIEFING_TIMEOUT_S = 10  # hard ceiling on request path — page must never block on LLM; Celery warms cache in background


def _call_opus_briefing_sync(
    prompt: str,
    schema_fields: dict,
    required_fields: list,
    api_key: str,
    llm_timeout: Optional[int] = None,
    athlete_id: Optional[str] = None,
    local_today: Optional[date] = None,
    local_now: Optional[datetime] = None,
) -> Optional[dict]:
    """
    Synchronous LLM call for home briefing — routes through the centralized
    llm_client abstraction with canary support.

    The `api_key` parameter is retained for backward compatibility with the
    Celery task path (home_briefing_tasks.py calls this directly). Actual
    key resolution is handled inside call_llm_with_json_parse via
    core.config.settings and os.getenv().

    llm_timeout: SDK-level timeout in seconds. Defaults to HOME_BRIEFING_TIMEOUT_S
    for Sonnet. For Kimi (reasoning model), minimum 120s is enforced because
    kimi-k2.5 thinks before responding (60-180s typical for briefing prompts).
    athlete_id: when provided, enables Kimi canary routing for this athlete.
    """
    from core.llm_client import call_llm_with_json_parse, resolve_briefing_model

    model = resolve_briefing_model(athlete_id=athlete_id)

    # kimi-k2.5 is a reasoning model — enforce minimum timeout
    KIMI_MIN_TIMEOUT_S = 15  # kimi-k2-turbo-preview responds in ~800ms; 15s gives ample headroom
    if model.startswith("kimi"):
        timeout_s = max(llm_timeout or 0, KIMI_MIN_TIMEOUT_S)
    else:
        timeout_s = llm_timeout if llm_timeout is not None else HOME_BRIEFING_TIMEOUT_S

    field_descriptions = "\n".join(
        f'  - "{k}" ({"REQUIRED" if k in required_fields else "optional"}): {v}'
        for k, v in schema_fields.items()
    )

    _today = local_today or date.today()
    _now = local_now or datetime.now()
    try:
        _time_str = _now.strftime("%-I:%M %p")
    except ValueError:
        _time_str = _now.strftime("%I:%M %p").lstrip("0")
    _tod = "morning" if _now.hour < 12 else ("afternoon" if _now.hour < 17 else "evening")
    system_prompt = (
        f"You are an elite running coach generating a structured home page briefing. "
        f"Today is {_today.isoformat()} ({_today.strftime('%A')}). "
        f"The athlete's current local time is {_time_str} ({_tod}). "
        "Use time-appropriate language — say 'this afternoon' if it's afternoon, 'this evening' if evening, 'this morning' ONLY if it's actually morning. "
        "All dates include pre-computed relative times like '(2 days ago)'. USE those labels — do NOT compute your own. "
        "Respond with ONLY a valid JSON object — no markdown, no code fences, no explanation. "
        "The JSON must contain these fields:\n"
        f"{field_descriptions}\n\n"
        "Rules:\n"
        "- Every required field MUST be present.\n"
        "- Optional fields should be included only when relevant data exists.\n"
        "- Keep each field concise: 1-2 sentences max.\n"
        "- Respond with the raw JSON object only."
    )

    result = call_llm_with_json_parse(
        model=model,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
        temperature=0.3,
        timeout_s=timeout_s,
    )

    if result is not None:
        logger.info("Home briefing generated via %s", model)
    return result


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


# Fingerprint-related terms that should only appear in morning_voice
_FINGERPRINT_TERMS = [
    "sleep cliff", "asymmetry", "half-life", "decay", "threshold",
    "fingerprint", "pattern", "efficiency tends", "correlat",
]


def _validate_briefing_diversity(fields: dict, athlete_id: str = "") -> dict:
    """
    Monitor mode: detect when fingerprint-derived language leaks from
    morning_voice into 2+ other fields (cross-lane repetition).

    Logs a warning but returns payload unchanged.
    """
    if not fields:
        return fields

    morning = (fields.get("morning_voice") or "").lower()
    if not morning:
        return fields

    morning_terms = [t for t in _FINGERPRINT_TERMS if t in morning]
    if not morning_terms:
        return fields

    other_fields = ["coach_noticed", "week_assessment", "checkin_reaction",
                    "race_assessment", "today_context"]
    leaking = []
    for fname in other_fields:
        text = (fields.get(fname) or "").lower()
        if not text:
            continue
        for term in morning_terms:
            if term in text:
                leaking.append(fname)
                break

    if len(leaking) >= 2:
        logger.warning(
            "Briefing diversity violation for %s: fingerprint terms %s leaked "
            "from morning_voice into %s",
            athlete_id, morning_terms, leaking,
        )

    return fields


def _fetch_llm_briefing_sync(
    prompt: str,
    schema_fields: dict,
    required_fields: list,
    checkin_data: Optional[dict],
    race_data: Optional[dict],
    cache_key: str,
    athlete_id: str,
    local_today: Optional[date] = None,
    local_now: Optional[datetime] = None,
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
        result = _call_opus_briefing_sync(
            prompt, schema_fields, required_fields, anthropic_key,
            athlete_id=athlete_id, local_today=local_today, local_now=local_now,
        )
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
        elif voice_check.get("truncated_text"):
            result["morning_voice"] = voice_check["truncated_text"]
    else:
        result["morning_voice"] = _VOICE_FALLBACK

    # --- Post-generation validator: sleep claim grounding ---
    # Runs on the final morning_voice (after ban-list/causal pass above).
    _garmin_sleep_h = checkin_data.get("garmin_sleep_h") if checkin_data else None
    _checkin_sleep_h = checkin_data.get("sleep_h") if checkin_data else None
    final_voice = result.get("morning_voice", "")
    if final_voice and final_voice != _VOICE_FALLBACK:
        sleep_check = validate_sleep_claims(final_voice, _garmin_sleep_h, _checkin_sleep_h)
        if not sleep_check["valid"]:
            stripped = _strip_ungrounded_sleep_sentences(
                final_voice, _garmin_sleep_h, _checkin_sleep_h
            )
            candidate = stripped.get("text") or ""
            if candidate:
                candidate_voice_check = validate_voice_output(candidate, field="morning_voice")
                candidate_sleep_check = validate_sleep_claims(
                    candidate, _garmin_sleep_h, _checkin_sleep_h
                )
                if candidate_voice_check.get("valid") and candidate_sleep_check.get("valid"):
                    logger.warning(
                        "morning_voice sleep claim ungrounded (%s); removed offending sentence(s) and kept remaining content",
                        sleep_check.get("reason"),
                    )
                    result["morning_voice"] = candidate
                else:
                    logger.warning(
                        "morning_voice sleep claim ungrounded (%s); candidate still invalid (voice=%s sleep=%s), using fallback",
                        sleep_check.get("reason"),
                        candidate_voice_check.get("reason"),
                        candidate_sleep_check.get("reason"),
                    )
                    result["morning_voice"] = _VOICE_FALLBACK
            else:
                logger.warning(
                    "morning_voice sleep claim ungrounded (%s); no valid content remained, using fallback",
                    sleep_check.get("reason"),
                )
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

    # --- Post-generation validator: relative-time claims ---
    # Extract run dates from the prompt (athlete brief uses "YYYY-MM-DD:" format)
    # and validate all text fields for obviously wrong time references.
    import re as _re_time
    _run_date_matches = _re_time.findall(r"(\d{4}-\d{2}-\d{2}):", prompt)
    if _run_date_matches:
        try:
            _recent_dates = [date.fromisoformat(d) for d in _run_date_matches]
            _text_fields = ["morning_voice", "coach_noticed", "race_assessment",
                           "today_context", "week_assessment", "checkin_reaction"]
            for _field_name in _text_fields:
                _field_text = result.get(_field_name)
                if not _field_text:
                    continue
                _time_check = validate_relative_time_claims(_field_text, _recent_dates, today=local_today)
                if not _time_check["valid"]:
                    logger.warning(
                        "Briefing field '%s' has wrong relative-time claim (%s); clearing",
                        _field_name, _time_check.get("reason"),
                    )
                    if _field_name == "morning_voice":
                        result[_field_name] = _VOICE_FALLBACK
                    else:
                        result[_field_name] = None
        except Exception as _e:
            logger.debug("Relative-time validation failed (non-blocking): %s", _e)

    # --- Post-generation diversity monitor (monitor mode — log only) ---
    result = _validate_briefing_diversity(result, athlete_id)

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


# run_shape classifications that do NOT contradict a detected split-derived
# workout structure.  Used by _render_workout_structure_block to decide
# whether to lead with "WORKOUT STRUCTURE" (confirmed) vs "POSSIBLE
# WORKOUT STRUCTURE" (run_shape disagrees).
_STRUCTURE_AGREEING_SHAPE_CLASSIFICATIONS = frozenset({
    "track_intervals",
    "threshold_intervals",
    "hill_repeats",
    "fartlek",
    "tempo",
    "over_under",
    "progression",
    "strides",
    "anomaly",  # anomaly = "doesn't fit a clean bucket" -- usually intervals
    "",
})


def _render_workout_structure_block(c: dict) -> str:
    """Build the workout-structure prompt block for today's run.

    Three honest branches:

    1. workout_structure present
       -> render the structure with a confidence prefix based on whether
          the run_shape classification agrees with structured work

    2. splits_available=True, no workout_structure
       -> tell the LLM the splits were examined and showed no structured
          pattern.  Safe assertion -- splits really were inspected.

    3. splits_available=False (or missing)
       -> tell the LLM that split-level analysis is not yet available
          for this run.  Do NOT claim splits were inspected.  This was
          the founder's 2026-04-18 regression: brief fired before async
          split processing finished, the prompt asserted "examined the
          splits and determined CONTINUOUS", and the LLM faithfully
          described an interval workout as a continuous fade.
    """
    workout_structure = c.get("workout_structure")
    if workout_structure:
        shape_class = c.get("shape_classification", "")
        structure_agrees = shape_class in _STRUCTURE_AGREEING_SHAPE_CLASSIFICATIONS
        if structure_agrees:
            return (
                f"WORKOUT STRUCTURE (from split data — confirmed by stream analysis):\n  "
                f"{workout_structure}\n"
                "The average pace blends warmup, work intervals, and rest jogs. "
                "Coach from the split breakdown for this structured workout."
            )
        return (
            f"POSSIBLE WORKOUT STRUCTURE (from split data — stream analysis classified this as "
            f"'{shape_class}', which may indicate natural pace variation rather than structured "
            f"intervals):\n  {workout_structure}\n"
            "Use judgment: if the run_shape classification and this structure disagree, "
            "trust the run_shape and mention the structure only as secondary context."
        )

    splits_available = c.get("splits_available")
    if splits_available is True:
        return (
            "NO STRUCTURED WORKOUT PATTERN — split-level analysis ran on the splits "
            "for this run and found no interval/rep structure. "
            "Do NOT describe this run as intervals, reps, repeats, or any structured workout. "
            "Do NOT invent split-level data (fastest rep, slowest rep, rep count). "
            "Describe it from the overall distance, pace, HR, and elevation data only."
        )

    return (
        "SPLIT-LEVEL ANALYSIS NOT YET AVAILABLE for this run -- describe it using "
        "the overall metrics only (distance, pace, HR, elevation, conditions). "
        "Do NOT invent split-level data (fastest rep, slowest rep, rep count). "
        "Do NOT make claims about whether this was a structured workout or not -- "
        "the split data simply hasn't been processed yet."
    )


def _summarize_workout_structure(activity_id, db: Session) -> Optional[str]:
    """
    Detect structured workouts (intervals, tempo w/ warmup) from split data
    and return a coaching-useful summary instead of flat averages.

    Returns None if no splits, < 4 splits, or no interval pattern detected.

    Gating order (fastest rejections first):
    1. Shape-extractor gate — if run_shape already classified this as an
       easy/steady/long run, skip split analysis entirely
    2. Elevation gate — if pace variation correlates with terrain, not structure
    3. Alternating pattern gate — real intervals alternate work/rest
    4. Work rep consistency gate — real intervals have consistent rep lengths
    5. Pace gap gate — meaningful differential between work and rest
    """
    import statistics as _stats

    METERS_PER_MILE = 1609.344

    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        return None

    # ── Gate 1: Shape-extractor veto ──
    # The shape_extractor's classification uses full stream data (not just
    # mile splits) and is far more reliable for distinguishing steady runs
    # from structured workouts. If it says easy/long/gray, trust it.
    NON_INTERVAL_SHAPES = {
        'easy_run', 'long_run', 'medium_long_run', 'gray_zone_run',
    }
    run_shape_data = activity.run_shape
    if run_shape_data and isinstance(run_shape_data, dict):
        summary_data = run_shape_data.get('summary', {})
        shape_class = summary_data.get('workout_classification', '')
        if shape_class in NON_INTERVAL_SHAPES:
            return None

    splits = (
        db.query(ActivitySplit)
        .filter(ActivitySplit.activity_id == activity_id)
        .order_by(ActivitySplit.split_number)
        .all()
    )
    if not splits or len(splits) < 4:
        return None

    # ── Gate 2: Elevation gate ──
    elev_gain_m = float(activity.total_elevation_gain or 0)
    total_dist_m = sum(float(s.distance or 0) for s in splits)
    total_dist_mi = total_dist_m / METERS_PER_MILE if total_dist_m > 0 else 0
    elev_per_mile_m = elev_gain_m / total_dist_mi if total_dist_mi > 0 else 0
    is_hilly = elev_per_mile_m > 15

    if is_hilly:
        gap_values = [
            float(s.gap_seconds_per_mile)
            for s in splits
            if s.gap_seconds_per_mile is not None
            and float(s.distance or 0) / METERS_PER_MILE > 0.05
        ]
        if len(gap_values) >= 4:
            gap_mean = _stats.mean(gap_values)
            if gap_mean > 0:
                gap_cv = _stats.stdev(gap_values) / gap_mean
                if gap_cv < 0.08:
                    return None

    parsed = []
    for s in splits:
        dist_m = float(s.distance) if s.distance else 0
        elapsed = int(s.elapsed_time) if s.elapsed_time else 0
        dist_mi = dist_m / METERS_PER_MILE
        pace_per_mi = (elapsed / dist_mi) if dist_mi > 0.01 else 99999
        parsed.append({
            "num": s.split_number,
            "dist_m": dist_m,
            "dist_mi": round(dist_mi, 2),
            "elapsed_s": elapsed,
            "pace_s_per_mi": pace_per_mi,
            "hr": int(s.average_heartrate) if s.average_heartrate else None,
        })

    real_paces = sorted(
        p["pace_s_per_mi"] for p in parsed
        if p["dist_mi"] > 0.05 and p["pace_s_per_mi"] < 50000
    )
    if len(real_paces) < 4:
        return None

    # Threshold: median-based with a tighter cutoff than the old q25 * 1.15.
    # Using median avoids skew from a single fast mile on an otherwise easy run.
    median_pace = real_paces[len(real_paces) // 2]
    work_pace_cutoff = median_pace * 0.92  # Splits must be >=8% faster than median to be "work"

    warmup_splits = []
    i = 0
    while i < len(parsed):
        sp = parsed[i]
        if sp["dist_mi"] < 0.3:
            break
        if sp["pace_s_per_mi"] <= work_pace_cutoff:
            break
        warmup_splits.append(sp)
        i += 1

    j = len(parsed) - 1
    while j > i and parsed[j]["dist_mi"] < 0.1:
        j -= 1
    cooldown_splits = []
    k = j
    while k > i:
        sp = parsed[k]
        if sp["dist_mi"] < 0.3:
            break
        if sp["pace_s_per_mi"] <= work_pace_cutoff:
            break
        cooldown_splits.append(sp)
        k -= 1
    cooldown_splits.reverse()
    j = k

    middle = parsed[i:j + 1]
    if len(middle) < 2:
        return None

    work_candidates = []
    rest_candidates = []
    for sp in middle:
        if sp["dist_mi"] < 0.05:
            rest_candidates.append(sp)
        elif sp["pace_s_per_mi"] <= work_pace_cutoff:
            work_candidates.append(sp)
        else:
            rest_candidates.append(sp)

    if len(work_candidates) < 3:
        return None

    # ── Gate 3: Alternating work/rest pattern ──
    # Real intervals alternate work and rest. If there are no rest splits
    # between work splits, this is a steady or progressive run.
    if len(rest_candidates) == 0:
        return None

    # Work:rest ratio — real intervals need recovery between reps.
    # >=2 work per 1 rest is generous (e.g., 6x800 with 5 recovery jogs).
    # If the ratio is much higher, the "rest" splits are noise.
    if len(work_candidates) > len(rest_candidates) * 3:
        return None

    # Check actual alternation: label each middle split as W or R and
    # verify the sequence has at least 2 W→R or R→W transitions.
    labels = []
    for sp in middle:
        if sp in work_candidates:
            labels.append('W')
        else:
            labels.append('R')
    transitions = sum(1 for idx in range(len(labels) - 1) if labels[idx] != labels[idx + 1])
    if transitions < 2:
        return None

    # ── Gate 4: Work rep consistency ──
    # Real intervals have reasonably consistent rep lengths.
    work_dists_m_check = [w["dist_m"] for w in work_candidates]
    avg_work_dist_m = sum(work_dists_m_check) / len(work_dists_m_check)
    if avg_work_dist_m > 0:
        try:
            dist_cv = _stats.stdev(work_dists_m_check) / avg_work_dist_m
            if dist_cv > 0.50:
                return None
        except _stats.StatisticsError:
            pass

    # ── Gate 5: Pace gap ──
    # The pace gap between avg work and avg rest must be meaningful (>=45s/mi).
    rest_paces = [r["pace_s_per_mi"] for r in rest_candidates if r["pace_s_per_mi"] < 50000]
    if rest_paces:
        avg_work = sum(w["pace_s_per_mi"] for w in work_candidates) / len(work_candidates)
        avg_rest = sum(rest_paces) / len(rest_paces)
        if avg_rest - avg_work < 45:
            return None

    work_paces = [w["pace_s_per_mi"] for w in work_candidates]
    work_hrs = [w["hr"] for w in work_candidates if w["hr"]]
    work_dists = [w["dist_mi"] for w in work_candidates]
    work_times = [w["elapsed_s"] for w in work_candidates]

    avg_work_pace_s = sum(work_paces) / len(work_paces)
    min_work_pace_s = min(work_paces)
    max_work_pace_s = max(work_paces)
    avg_work_dist = sum(work_dists) / len(work_dists)
    avg_work_time_s = sum(work_times) / len(work_times)
    avg_work_hr = round(sum(work_hrs) / len(work_hrs)) if work_hrs else None

    def _fmt_pace(s_per_mi):
        m = int(s_per_mi // 60)
        sec = int(s_per_mi % 60)
        return f"{m}:{sec:02d}/mi"

    parts = []

    if warmup_splits:
        wu_dist = sum(w["dist_mi"] for w in warmup_splits)
        wu_time = sum(w["elapsed_s"] for w in warmup_splits)
        wu_pace = wu_time / wu_dist if wu_dist > 0 else 0
        parts.append(f"Warmup: {wu_dist:.1f}mi at {_fmt_pace(wu_pace)}")

    rep_label = None
    avg_work_m = avg_work_dist * METERS_PER_MILE
    if len(work_times) >= 3 and avg_work_time_s > 0:
        time_spread = (max(work_times) - min(work_times)) / avg_work_time_s
        work_dists_m = [w["dist_m"] for w in work_candidates]
        dist_spread = (
            (max(work_dists_m) - min(work_dists_m)) / avg_work_m
            if avg_work_m > 0 else 999
        )
        rounded_min = round(avg_work_time_s / 60)
        time_near_round = abs(avg_work_time_s - rounded_min * 60) < 15

        if time_spread <= dist_spread and time_near_round and rounded_min >= 1:
            rep_label = f"{rounded_min} min"

    if rep_label is None:
        if 350 < avg_work_m < 450:
            rep_label = "400m"
        elif 750 < avg_work_m < 900:
            rep_label = "800m"
        elif 900 < avg_work_m < 1100:
            rep_label = "1000m"
        elif 1500 < avg_work_m < 1700:
            rep_label = "1mi"
        elif 1100 < avg_work_m < 1400:
            rep_label = "1200m"
        elif 180 < avg_work_m < 250:
            rep_label = "200m"
        elif 250 < avg_work_m < 350:
            rep_label = "300m"
        else:
            rep_label = f"{avg_work_dist:.2f}mi"

    pace_range = f"{_fmt_pace(min_work_pace_s)}-{_fmt_pace(max_work_pace_s)}"
    if abs(min_work_pace_s - max_work_pace_s) < 10:
        pace_range = _fmt_pace(avg_work_pace_s)

    hr_str = f", avg HR {avg_work_hr}" if avg_work_hr else ""
    parts.append(
        f"Work: {len(work_candidates)} x {rep_label} at {_fmt_pace(avg_work_pace_s)} avg "
        f"(range {pace_range}){hr_str}"
    )

    if rest_candidates:
        rest_jogs = [r for r in rest_candidates if r["elapsed_s"] > 0 and r["dist_mi"] < 0.5]
        if rest_jogs:
            avg_rest_s = sum(r["elapsed_s"] for r in rest_jogs) / len(rest_jogs)
            parts.append(f"Recovery: ~{int(avg_rest_s)}s between reps")

    if cooldown_splits:
        cd_dist = sum(c["dist_mi"] for c in cooldown_splits)
        cd_time = sum(c["elapsed_s"] for c in cooldown_splits)
        cd_pace = cd_time / cd_dist if cd_dist > 0 else 0
        parts.append(f"Cooldown: {cd_dist:.1f}mi at {_fmt_pace(cd_pace)}")

    return "\n  ".join(parts)


def generate_coach_home_briefing(
    athlete_id: str,
    db: Session,
    today_completed: Optional[dict] = None,
    planned_workout: Optional[dict] = None,
    checkin_data: Optional[dict] = None,
    race_data: Optional[dict] = None,
    skip_cache: bool = False,
    upcoming_plan: Optional[list] = None,
    preferred_units: Optional[str] = None,
) -> tuple:
    """
    Prepare everything the LLM needs (DB work on request thread), then
    return the args for ``_fetch_llm_briefing_sync`` so the caller can
    run the LLM call in a worker thread via ``asyncio.to_thread``.

    Returns ``(cached_result,)`` if Redis hit (request path only), or
    ``(None, prompt, schema_fields, required_fields, cache_key, garmin_sleep_h, local_today, local_now)``
    if the LLM call is needed.

    skip_cache=True: the Lane 2A Celery worker always passes this to bypass
    the legacy ``coach_home_briefing:{athlete_id}:{hash}`` key. Without this,
    a stale legacy key causes the task to return already_cached and silently
    skip writing to ``home_briefing:{athlete_id}``.

    Primary model: Claude Opus 4.6 (highest reasoning quality).
    Fallback: Gemini 2.5 Flash (if Opus unavailable).
    Cached in Redis keyed by athlete + data hash (request path only).
    """
    import hashlib
    import json as _json
    from uuid import UUID as _tz_uuid

    from services.coach_units import coach_units

    tz = get_athlete_timezone_from_db(db, _tz_uuid(athlete_id))
    local_today = athlete_local_today(tz)
    local_now = datetime.now(timezone.utc).astimezone(tz)

    # Resolve units. Callers from the request path may not pass the value;
    # fall back to the athlete row so the prompt always speaks the athlete's
    # language regardless of which entry point invoked us.
    if preferred_units is None:
        try:
            from models import Athlete
            preferred_units = (
                db.query(Athlete.preferred_units)
                .filter(Athlete.id == athlete_id)
                .scalar()
            ) or "imperial"
        except Exception:
            preferred_units = "imperial"
    units = coach_units(preferred_units)

    cache_input = _json.dumps({
        "date": local_today.isoformat(),
        "completed": today_completed,
        "planned": planned_workout,
        "checkin": checkin_data,
        "race": race_data,
        "upcoming": upcoming_plan,
        "units": units.preferred_units,
    }, sort_keys=True, default=str)
    data_hash = hashlib.md5(cache_input.encode()).hexdigest()[:12]
    cache_key = f"coach_home_briefing:{athlete_id}:{data_hash}"

    # Check legacy Redis cache (request path only).
    # The Lane 2A worker passes skip_cache=True to always build fresh and
    # write to home_briefing:{athlete_id}. Without skip_cache, a stale
    # legacy key silently blocks the Lane 2A write.
    if not skip_cache:
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
                InsightLog.trigger_date >= local_today - timedelta(days=7),
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
    # --- Insight rotation: suppress recently-surfaced coach_noticed insight for 48h ---
    parts = [
        f"You are an elite running coach speaking directly to your athlete about TODAY ({local_today.isoformat()}, {local_today.strftime('%A')}).",
        "You have their full training profile below. Use it. Be specific, direct, insightful.",
        "CRITICAL: All dates below include pre-computed relative times like '(2 days ago)' or '(yesterday)'. USE those labels verbatim — do NOT compute your own relative time. NEVER say 'two weeks ago' unless the data says '(2 weeks ago)'.",
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
        "PERSONAL FINGERPRINT CONTRACT:",
        f"- Use threshold values to give specific advice WITH UNITS: 'your sleep cliff is at 6.2 hours — last night was 5.5 hours'. Pace as {units.pace_unit}, sleep in hours, time of day as AM/PM, distances in {units.distance_unit_long}, counts as numbers.",
        "- Use asymmetry ratios to convey magnitude ('bad sleep hurts you 3x more than good sleep helps').",
        "- Use decay timing for forward-looking advice ('the effect peaks tomorrow based on your 2-day half-life').",
        "- When describing a pattern, be SPECIFIC about what the data shows. 'I've noticed a pattern' is vague and useless. 'Your easy runs before 7 AM are consistently slower — that threshold has held across 18 observations' is specific and actionable.",
        "- If no confirmed patterns exist, do not mention the fingerprint — coach from the other data.",
        "- ABSOLUTE BAN on athlete-facing stats: never say 'confirmed N times', 'r=', 'p-value', 'times_confirmed', 'correlation coefficient', 'observations'. Use coaching language: 'I've seen this consistently' not 'confirmed 34 times'. 'Strong pattern' not 'r=0.62'.",
        "",
        "TRUST-SAFETY CONSTRAINTS (enforced by post-generation validator):",
        "- Do NOT use sycophantic words: incredible, amazing, phenomenal, extraordinary, fantastic, wonderful, awesome, brilliant, magnificent, outstanding, superb, stellar, remarkable, spectacular.",
        "- Do NOT make causal claims: avoid 'because you', 'caused by', 'due to your'.",
        "- morning_voice MUST contain at least one specific number from the data.",
        "- morning_voice must be ONE paragraph only. No sentence count limit — say what needs to be said.",
        "- workout_why must be a single sentence explaining why today's workout matters.",
        "- ABSOLUTE BAN on quoting these to the athlete: CTL, ATL, TSB, chronic load, acute load, form score, durability index, recovery half-life, injury risk score. These appear in the brief for YOUR reasoning only. If you quote them, the output will be rejected.",
        "",
        "SEASONAL COMPARISON DISCIPLINE:",
        "- NEVER compare runs across different seasons without acknowledging temperature/humidity differences. A July run and an April run are NOT comparable without heat context.",
        "- If you reference a past run from a different season, note the conditions: 'Your 8:15 pace in July heat (adjusted: ~7:50 in cool conditions) vs today's 7:55 in April.'",
        "- If heat_adjustment_pct data is available on the activities, USE IT for fair comparisons.",
        "- When no environmental data is available for a past run, do NOT compare paces across seasons. Compare within the same 4-week window or acknowledge the limitation.",
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
            "DEEP INTELLIGENCE is reasoning context for you, not a script to copy.",
            "Each output field below has its own YOUR DATA FOR THIS FIELD lane —",
            "draw from that lane first. Only morning_voice may reference fingerprint",
            "findings directly. Other fields must NOT repeat fingerprint themes.",
            "",
        ])
    elif coach_noticed_intel:
        parts.extend([
            "=== DETERMINISTIC INTELLIGENCE ===",
            f"Source: {coach_noticed_intel.source}",
            coach_noticed_intel.text,
            "",
        ])

    # --- Athlete fact injection (coach memory layer 1) ---
    try:
        from models import AthleteFact as _AF
        MAX_INJECTED_FACTS = 15
        BATCH_SIZE = 50
        MAX_SCAN_ROWS = 500
        _now = datetime.now(timezone.utc)

        active_facts = []
        offset = 0
        while len(active_facts) < MAX_INJECTED_FACTS and offset < MAX_SCAN_ROWS:
            batch = (
                db.query(_AF)
                .filter(
                    _AF.athlete_id == athlete_id,
                    _AF.is_active == True,  # noqa: E712
                )
                .order_by(
                    _AF.confirmed_by_athlete.desc(),
                    _AF.extracted_at.desc(),
                )
                .offset(offset)
                .limit(BATCH_SIZE)
                .all()
            )
            if not batch:
                break

            for f in batch:
                if f.temporal and f.ttl_days is not None:
                    if f.extracted_at < _now - timedelta(days=f.ttl_days):
                        continue
                active_facts.append(f)
                if len(active_facts) >= MAX_INJECTED_FACTS:
                    break
            offset += BATCH_SIZE
        if active_facts:
            facts_section = "=== ATHLETE-STATED FACTS (from coach conversations) ===\n"
            for f in active_facts:
                facts_section += f"- {f.fact_key}: {f.fact_value} (stated {f.extracted_at.strftime('%b %d')})\n"
            facts_section += (
                "\nRULES FOR USING THESE FACTS:\n"
                "- Use these facts to INFORM your reasoning, connections, and interpretations.\n"
                "- Do NOT recite facts back to the athlete. They already know their own weight, "
                "their own deadlift max, their own T-score. Telling them what they told you is not coaching.\n"
                "- DO use facts to CONNECT and CONTEXTUALIZE. Example: 'Your scale discrepancy is "
                "explained by your bone density' uses two facts together to produce an insight "
                "without parroting either number.\n"
                "- The athlete should feel the system THINKS with what they shared, not that it "
                "memorized and repeated it.\n"
            )
            parts.append(facts_section)
    except Exception as fe:
        logger.warning(f"Fact injection into morning voice skipped: {fe}")

    if units.is_metric:
        _hilly_example = "+300m gain"
        _heat_threshold = "16°C"
        _heat_hot = "29°C/80%rh"
        _heat_cool = "10°C/30%rh"
        _heat_pace_hot = f"5:35{units.pace_unit_short}"
        _heat_pace_cool = f"5:17{units.pace_unit_short}"
        _heat_diff_threshold = "8°C"
    else:
        _hilly_example = "+1000ft gain"
        _heat_threshold = "60°F"
        _heat_hot = "85°F/80%rh"
        _heat_cool = "50°F/30%rh"
        _heat_pace_hot = f"9:00{units.pace_unit_short}"
        _heat_pace_cool = f"8:30{units.pace_unit_short}"
        _heat_diff_threshold = "15°F"

    parts.append(
        "=== PACE COMPARISON CONTRACT ===\n"
        "NEVER compare paces between runs without accounting for these confounders:\n"
        f"1. ELEVATION: A hilly run ({_hilly_example}) is inherently slower than a flat run. "
        "If elevation data differs significantly between two runs, say so explicitly.\n"
        f"2. HEAT: Runs above {_heat_threshold} are physiologically slower. A {_heat_pace_hot} in {_heat_hot} is "
        f"FASTER effort than {_heat_pace_cool} in {_heat_cool}. Use the heat-adjustment percentage when "
        f"available. If temperature data differs by >{_heat_diff_threshold} between compared runs, you MUST note it.\n"
        "3. SEASON: Do NOT compare a March run to a July run and claim the athlete is 'getting faster' "
        "or 'slowing down' without noting the seasonal temperature difference.\n"
        "4. WORKOUT TYPE: Do NOT compare an interval/tempo workout average pace to an easy run pace. "
        "They measure different things.\n"
        "If confounders are present, either normalize the comparison or explicitly caveat it. "
        "Silence is better than a misleading pace comparison."
    )

    parts.append("=== TODAY ===")

    if today_completed:
        c = today_completed
        # Prefer pre-formatted *_text fields written by the briefing builder
        # (which respects the athlete's preferred units). Fall back to the
        # legacy imperial keys for any caller that hasn't been migrated yet.
        _dist_text = c.get("distance_text")
        if not _dist_text and c.get("distance_mi") is not None:
            _dist_text = f"{c['distance_mi']} mi"
        today_line = f"COMPLETED today: {c.get('name')}, {_dist_text or '?'}, pace {c.get('pace')}, HR {c.get('avg_hr', 'N/A')}, {c.get('duration_min')}min"
        _elev_text = c.get("elevation_text")
        if not _elev_text and c.get("elevation_gain_ft") is not None:
            _elev_text = f"+{c['elevation_gain_ft']} ft"
        if _elev_text:
            today_line += f", elevation {_elev_text}"
        _temp_text = c.get("temperature_text")
        if not _temp_text and c.get("temperature_f") is not None:
            _temp_text = f"{c['temperature_f']}°F"
        if _temp_text:
            today_line += f", {_temp_text}"
        if c.get("humidity_pct") is not None:
            today_line += f" / {int(c['humidity_pct'])}% humidity"
        if c.get("heat_adjustment_pct") is not None and c["heat_adjustment_pct"] > 0:
            today_line += f" (heat-adjusted pace ≈ {c['heat_adjustment_pct']}% slower)"
        parts.append(today_line)
        parts.append(_render_workout_structure_block(c))
        if planned_workout and planned_workout.get("has_workout"):
            plan_mi = planned_workout.get("distance_mi")
            plan_type = planned_workout.get("title") or planned_workout.get("workout_type")
            if plan_mi and c.get("distance_mi") and abs(c["distance_mi"] - plan_mi) > 1.0:
                # Compare in miles (the canonical stored field) but render
                # both numbers in the athlete's units.
                _plan_text = planned_workout.get("distance_text") or f"{plan_mi} mi"
                _ran_text = c.get("distance_text") or f"{c['distance_mi']} mi"
                parts.append(f"Note: plan had {_plan_text} {plan_type}, athlete ran {_ran_text} instead.")
    elif planned_workout and planned_workout.get("has_workout"):
        w = planned_workout
        _w_dist = w.get("distance_text") or (f"{w.get('distance_mi')} mi" if w.get("distance_mi") is not None else "?")
        parts.append(f"PLANNED (not yet completed): {w.get('title') or w.get('workout_type')}, {_w_dist}")
        parts.append("The athlete may or may not follow this plan. Coach based on their actual patterns, not the plan.")
    else:
        parts.append("No planned workout and nothing completed yet today.")

    if upcoming_plan:
        _up_lines = ["=== UPCOMING PLAN (next 1-3 days) ==="]
        for _up in upcoming_plan:
            _up_type = _up.get("title") or _up.get("workout_type") or "workout"
            if _up.get("distance_text"):
                _up_dist = f", {_up['distance_text']}"
            elif _up.get("distance_mi"):
                _up_dist = f", {_up['distance_mi']} mi"
            else:
                _up_dist = ""
            _up_desc = f" — {_up['description']}" if _up.get("description") else ""
            _up_lines.append(f"- {_up['day_name']}: {_up_type}{_up_dist}{_up_desc}")
        _up_lines.extend([
            "",
            "PLAN-AWARENESS RULES (non-negotiable):",
            "- NEVER suggest rest, easy days, or alternative sessions on days when a quality "
            "workout (threshold, intervals, tempo, long run) is scheduled.",
            "- Frame today's session in the context of what is COMING, not what you imagine "
            "should come. 'Good setup for tomorrow's threshold' not 'take it easy tomorrow.'",
            "- If the athlete ran easy today and has quality work tomorrow, frame the easy run "
            "as preparation: fueling, hydration, sleep priority.",
            "- If quality work is scheduled within 48 hours, forward-looking advice should "
            "reference that specific session by name and type.",
            "- You may note when the upcoming plan looks heavy relative to current fatigue, "
            "but do NOT override the plan. The athlete and plan generator decide the schedule.",
        ])
        parts.extend(_up_lines)

    if checkin_data:
        soreness_label = checkin_data.get("soreness_label")
        soreness_str = soreness_label if soreness_label else "not reported today — do NOT claim any soreness"
        parts.append(
            f"Check-in: Readiness {checkin_data.get('readiness_label', '?')}, "
            f"Sleep {checkin_data.get('sleep_label', '?')}, "
            f"Soreness {soreness_str}"
        )

    # --- Sleep source grounding (source contract — prevents hallucinated sleep values) ---
    # Query Garmin device sleep for last night using athlete-local date.
    garmin_sleep_h, garmin_date_used, garmin_is_today = _get_garmin_sleep_h_for_last_night(athlete_id, db)
    checkin_sleep_h = checkin_data.get("sleep_h") if checkin_data else None

    sleep_parts: list = ["=== SLEEP SOURCE CONTRACT ==="]
    if garmin_sleep_h is not None and garmin_is_today:
        sleep_parts.append(
            f"GARMIN_LAST_NIGHT_SLEEP_HOURS: {garmin_sleep_h:.2f}h "
            f"(device-measured, date={garmin_date_used}, source=garmin_device)"
        )
    elif garmin_sleep_h is not None and not garmin_is_today:
        sleep_parts.append(
            "GARMIN SLEEP NOT YET AVAILABLE for last night. "
            f"Do NOT cite a Garmin sleep number. The most recent Garmin sleep is from "
            f"{garmin_date_used} ({garmin_sleep_h:.2f}h) — that is NOT last night."
        )
        garmin_sleep_h = None
    if checkin_sleep_h is not None:
        sleep_parts.append(
            f"TODAY_CHECKIN_SLEEP_HOURS: {checkin_sleep_h:.1f}h "
            f"(athlete self-report, source=manual_checkin)"
        )
    if garmin_sleep_h is None and checkin_sleep_h is None:
        sleep_parts.append("NO_NUMERIC_SLEEP_SOURCE: Do NOT make any numeric sleep claim.")
    else:
        sleep_parts.extend([
            "SLEEP_SOURCE_PRIORITY: Garmin device > manual check-in > label only.",
            "CONFLICT_RULE: If both sources present and they differ, cite each source separately with its label.",
            "SYNTHESIS_BAN: Do NOT synthesize, average, or invent a third sleep value.",
            "GROUNDING_RULE: Any numeric sleep claim in your output MUST match one of the sources above within 30 minutes.",
        ])
    parts.extend(sleep_parts + [""])
    baseline_guidance = _build_sleep_baseline_guidance(
        athlete_id, db, last_night_sleep_h=garmin_sleep_h
    )
    if baseline_guidance:
        parts.extend([baseline_guidance, ""])

    logger.debug(
        "Sleep grounding: athlete=%s garmin_sleep_h=%s checkin_sleep_h=%s",
        athlete_id, garmin_sleep_h, checkin_sleep_h,
    )

    # Runs completed this week — ground the LLM so it never fabricates cut runs
    try:
        _today = local_today
        _week_start = _today - timedelta(days=_today.weekday())
        from models import Activity as _Activity
        from sqlalchemy import func as _func
        _runs_this_week = (
            db.query(_func.count(_Activity.id))
            .filter(
                _Activity.athlete_id == athlete_id,
                _Activity.sport == "run",
                _Activity.start_time >= _week_start,
                _Activity.start_time < _today + __import__("datetime").timedelta(days=1),
            )
            .scalar()
        ) or 0
        parts.append(
            f"Runs completed this week so far (Monday through now): {_runs_this_week}. "
            "CRITICAL: Do NOT claim the athlete cut runs short, reduced mileage, or missed runs "
            "unless this count is LESS than the number of workouts planned for days already past."
        )
    except Exception:
        pass  # Non-blocking

    # --- Recent cross-training context (last 48 hours) ---
    try:
        from models import Activity as _CTActivity
        from services.training_load import TrainingLoadCalculator as _CTCalc
        _ct_cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
        _ct_activities = (
            db.query(_CTActivity)
            .filter(
                _CTActivity.athlete_id == athlete_id,
                _CTActivity.sport.in_(["cycling", "walking", "hiking", "strength", "flexibility"]),
                _CTActivity.start_time >= _ct_cutoff,
                _CTActivity.is_duplicate == False,  # noqa: E712
            )
            .order_by(_CTActivity.start_time.desc())
            .limit(5)
            .all()
        )
        if _ct_activities:
            _ct_calc = _CTCalc(db)
            _athlete_obj = db.query(Athlete).filter(Athlete.id == athlete_id).first()
            _ct_lines = ["=== RECENT CROSS-TRAINING (last 48 hours) ==="]
            for _cta in _ct_activities:
                _hours_ago = (datetime.now(timezone.utc) - _cta.start_time).total_seconds() / 3600
                _dur_min = round((_cta.duration_s or 0) / 60)
                _ct_tss = None
                try:
                    _stress = _ct_calc.calculate_workout_tss(_cta, _athlete_obj)
                    _ct_tss = round(_stress.tss)
                except Exception:
                    pass
                _ct_line = f"- {_cta.sport}: {_dur_min}min"
                if _ct_tss:
                    _ct_line += f" ({_ct_tss} TSS)"
                if _cta.strength_session_type:
                    _ct_line += f", {_cta.strength_session_type} session"
                _ct_line += f", {round(_hours_ago)}h ago"
                _ct_lines.append(_ct_line)
            _ct_lines.extend([
                "",
                "CROSS-TRAINING MENTION RULES:",
                "- When cross-training occurred in the last 48 hours and is relevant to "
                "today's running context, acknowledge it briefly.",
                "- A heavy strength session before a quality run day is relevant. "
                "A yoga session before a rest day is not. Use judgment.",
                "- When you do mention it, connect it to the running context: "
                "'Yesterday's strength session adds to your total training load heading into today's threshold.'",
                "- Do NOT always mention cross-training. Only when it matters to today's run.",
                "- Do NOT make prescriptive claims about how the athlete will feel "
                "('your legs will be fatigued'). State the load contribution, not the prediction.",
            ])
            parts.extend(_ct_lines)
    except Exception as _ct_err:
        logger.debug(f"Cross-training context query failed (non-blocking): {_ct_err}")

    try:
        from models import PlanAdaptationProposal
        _pending_proposal = (
            db.query(PlanAdaptationProposal)
            .filter(
                PlanAdaptationProposal.athlete_id == athlete_id,
                PlanAdaptationProposal.status == "pending",
            )
            .first()
        )
        if _pending_proposal:
            _trigger_labels = {
                "missed_long_run": "a missed long run",
                "consecutive_missed": "multiple missed training days",
                "readiness_tank": "extended low readiness",
            }
            _trigger_desc = _trigger_labels.get(
                _pending_proposal.trigger_type, _pending_proposal.trigger_type
            )
            _changed_count = sum(
                1 for c in (_pending_proposal.proposed_changes or []) if c.get("changed")
            )
            parts.append(
                f"\n=== PENDING PLAN ADJUSTMENT ===\n"
                f"A plan adjustment has been proposed due to {_trigger_desc} "
                f"({_changed_count} day{'s' if _changed_count != 1 else ''} adjusted, "
                f"weeks {_pending_proposal.affected_week_start}-{_pending_proposal.affected_week_end}). "
                f"The athlete has not yet responded. "
                f"You may briefly acknowledge this: 'I've suggested a small adjustment to your "
                f"upcoming week — check the home screen when you're ready.' "
                f"Do NOT describe the specific changes. Do NOT pressure the athlete to accept."
            )
    except Exception:
        pass

    parts.append(
        "\nONE-NEW-THING RULE: Your briefing should contain exactly ONE observation "
        "the athlete didn't know yesterday — one genuinely new piece of "
        "information, finding, or pattern. Not four insights. Not three "
        "correlation findings. Not two ways of saying the same thing. One true, "
        "useful, new thing — then practical guidance for today. If you don't "
        "have anything new, just coach today's session. Don't fill space."
    )

    if race_data and race_data.get("days_remaining", 99) <= 7:
        forecast = _get_race_forecast(athlete_id)
        if forecast:
            weather_section = _build_race_weather_context(athlete_id, db, forecast, race_data)
            if weather_section:
                parts.extend([weather_section, ""])

    prompt = "\n".join(parts)

    # --- Build per-field lane snippets (structural separation) ---
    fingerprint_summary = ""
    try:
        from services.fingerprint_context import build_fingerprint_prompt_section
        from uuid import UUID as _lane_UUID
        fp = build_fingerprint_prompt_section(
            _lane_UUID(athlete_id),
            db,
            verbose=False,
            max_findings=3,
            include_emerging_question=False,
        )
        if fp:
            fingerprint_summary = fp
    except Exception:
        pass

    coach_noticed_source = ""
    if coach_noticed_intel:
        coach_noticed_source = coach_noticed_intel.text
    elif insight_context:
        coach_noticed_source = insight_context

    today_summary = ""
    if today_completed:
        c = today_completed
        _ts_dist = c.get("distance_text") or (
            f"{c.get('distance_mi')} mi" if c.get("distance_mi") is not None else "?"
        )
        if c.get("workout_structure"):
            today_summary = (
                f"Completed: {c.get('name')}, {_ts_dist} total\n"
                f"  {c.get('workout_structure')}"
            )
        else:
            today_summary = (
                f"Completed: {c.get('name')}, {_ts_dist}, "
                f"pace {c.get('pace')}, HR {c.get('avg_hr', 'N/A')}"
            )
    elif planned_workout and planned_workout.get("has_workout"):
        w = planned_workout
        _w_dist = w.get("distance_text") or (
            f"{w.get('distance_mi')} mi" if w.get("distance_mi") is not None else "?"
        )
        today_summary = (
            f"Planned: {w.get('title') or w.get('workout_type')}, {_w_dist}"
        )

    checkin_summary = ""
    if checkin_data:
        checkin_summary = (
            f"Readiness: {checkin_data.get('readiness_label', '?')}, "
            f"Sleep: {checkin_data.get('sleep_label', '?')}, "
            f"Soreness: {checkin_data.get('soreness_label') or 'not reported'}"
        )

    race_summary = ""
    if race_data:
        race_parts = [
            f"Race: {race_data.get('name', '?')} on {race_data.get('date', '?')}",
            f"distance: {race_data.get('distance', '?')}",
            f"{race_data.get('days_remaining', '?')} days away",
        ]
        if race_data.get("goal_time"):
            race_parts.append(f"goal: {race_data['goal_time']}")
        if race_data.get("goal_pace"):
            race_parts.append(f"goal pace: {race_data['goal_pace']}")
        race_summary = ", ".join(race_parts)

    def _lane(snippet: str) -> str:
        if snippet:
            return f" YOUR DATA FOR THIS FIELD: {snippet}"
        return " YOUR DATA FOR THIS FIELD: Use the athlete brief and today context above."

    schema_fields = {
        "coach_noticed": f"The single most important coaching observation the athlete doesn't already know. If a daily intelligence rule fired, lead with that. Otherwise draw from wellness trends, training load signals, or recent activity patterns. The athlete should read this and think 'I didn't know that.' 1-2 sentences. BE SPECIFIC: describe what you observed using the athlete's training units — pace in {units.pace_unit}, distances in {units.distance_unit_long}, sleep in hours, time as AM/PM, frequency as counts. Never be vague about the pattern. 'Your easy pace changes with time of day' is too vague. 'Your easy runs before 7 AM have been consistently slower across 18 observations — there's a threshold around 7 AM' is specific. BANNED: r-values, p-values, correlation coefficients, 'statistically significant', z-scores, any statistical language. Use coaching language, not statistics.{_lane(coach_noticed_source)}",
        "today_context": f"Action-focused context: if run completed, state the result then specify next steps referencing the UPCOMING PLAN if available; if not yet, describe what today should look like. Must include a concrete next action. If tomorrow has a quality session scheduled, next steps should prepare for it (fueling, sleep, hydration). 1-2 sentences.{_lane(today_summary)}",
        "week_assessment": f"Implication: explain what this week's trajectory means for near-term training direction, based on actual training not plan adherence. 1 sentence.{_lane('')}",
        "checkin_reaction": f"Acknowledge how they feel FIRST, then guide next steps. If they feel good despite high load, validate that and suggest recovery actions to maintain it. Never contradict their self-report. 1-2 sentences.{_lane(checkin_summary)}",
        "race_assessment": f"Honest readiness assessment for their race based on current fitness, not plan adherence. 1-2 sentences.{_lane(race_summary)}",
        "morning_voice": f"The first thing the athlete reads. ONE paragraph, 2-3 sentences. Follow this structure exactly: Sentence 1: State what they did today with one specific number (distance, pace, or HR). Use time-appropriate language: 'this afternoon' if the run was in the afternoon, 'this evening' if evening, 'this morning' ONLY if they actually ran before noon. Sentence 2: Connect it to their recent training pattern — volume trend this week, load block context, or a personal fingerprint pattern. Sentence 3 (optional): One concrete forward-looking action for TOMORROW only — if the UPCOMING PLAN section exists, reference the actual scheduled workout by name and type instead of guessing. CRITICAL RULES: If the athlete already ran today, NEVER tell them to rest TODAY or do zero running TODAY — their run is done; guidance is about tomorrow. If a quality session (threshold, intervals, tempo, long run) is scheduled tomorrow, NEVER suggest rest or easy movement — frame today as preparation for that session. NEVER reference the briefing itself, synced data, data refreshes, or system internals. NEVER say 'home briefing', 'synced activity', 'refreshed'. Must cite at least one specific number (pace, distance, HR — NOT internal metrics). ABSOLUTE BAN on CTL, ATL, TSB, chronic load, acute load, form score, durability index, recovery half-life, injury risk score, 'confirmed N times', 'r=', 'correlation'.{_lane(fingerprint_summary)}",
        "workout_why": f"One sentence explaining WHY today's workout matters in the context of their training. Example: 'Active recovery keeps blood flowing after yesterday's {'15 km' if units.is_metric else '10-mile'} effort.' No sycophantic language.{_lane(today_summary)}",
    }
    required_fields = ["coach_noticed", "today_context", "week_assessment", "morning_voice"]
    if checkin_data:
        required_fields.append("checkin_reaction")
    if race_data:
        required_fields.append("race_assessment")

    return (None, prompt, schema_fields, required_fields, cache_key, garmin_sleep_h, local_today, local_now)


def compute_coach_noticed(
    athlete_id: str,
    db: Session,
    hero_narrative: Optional[str] = None,
) -> Optional[CoachNoticed]:
    """
    ADR-17 Phase 2: Build the single most important coaching insight.

    Priority waterfall:
    1. Persisted fingerprint finding (times_confirmed >= 3, daily rotation)
    2. Top signal from home_signals
    3. Top insight feed card summary
    4. Hero narrative fallback

    No live analyze_correlations — all correlation data comes from persisted
    CorrelationFinding rows (populated by the daily fingerprint refresh).
    """
    tz = get_athlete_timezone_from_db(db, __import__("uuid").UUID(athlete_id))
    _local_today = athlete_local_today(tz)

    # 1. Persisted fingerprint finding (trust-gated, rotated daily)
    try:
        from uuid import UUID as _UUID
        from models import CorrelationFinding as _CF
        from services.fingerprint_context import (
            _format_value_with_unit,
            _SUPPRESSED_SIGNALS,
            _ENVIRONMENT_SIGNALS,
        )
        _suppressed = _SUPPRESSED_SIGNALS | _ENVIRONMENT_SIGNALS
        eligible = (
            db.query(_CF)
            .filter(
                _CF.athlete_id == _UUID(athlete_id),
                _CF.is_active == True,  # noqa: E712
                _CF.times_confirmed >= 3,
                ~_CF.input_name.in_(_suppressed),
            )
            .order_by(_CF.times_confirmed.desc(), _CF.last_confirmed_at.desc())
            .limit(5)
            .all()
        )
        if eligible:
            idx = _local_today.toordinal() % len(eligible)
            f = eligible[idx]
            if not _is_finding_in_cooldown(athlete_id, f.input_name, f.output_metric):
                inp_name = friendly_signal_name(f.input_name)
                out_name = friendly_signal_name(f.output_metric)
                direction_verb = "improves" if f.direction == "positive" else "worsens"

                finding_text = _sanitize_finding_text(
                    f.insight_text or (
                    f"{inp_name.title()} {f.direction}ly "
                    f"affects your {out_name}"
                    )
                )

                detail_parts = []
                if f.threshold_value is not None:
                    thresh_fmt = _format_value_with_unit(
                        f.threshold_value, f.input_name
                    )
                    above_below = f.threshold_direction or "below"
                    detail_parts.append(
                        f"your {inp_name} threshold is around {thresh_fmt}"
                    )
                if f.asymmetry_ratio is not None and f.asymmetry_ratio > 1.5:
                    detail_parts.append(
                        f"the downside is {f.asymmetry_ratio:.1f}x stronger "
                        f"than the upside"
                    )
                if f.decay_half_life_days is not None:
                    detail_parts.append(
                        f"the effect peaks within {f.decay_half_life_days:.0f} day(s)"
                    )
                if f.time_lag_days and f.time_lag_days > 0:
                    detail_parts.append(
                        f"shows up {f.time_lag_days} day(s) later"
                    )

                detail_parts.append(
                    f"consistent across {f.sample_size} of your runs"
                )

                text = finding_text
                if detail_parts:
                    text += " — " + ", ".join(detail_parts)
                text += "."
                return CoachNoticed(
                    text=text,
                    source="fingerprint",
                    ask_coach_query=(
                        f"Tell me more about how {inp_name} "
                        f"affects my {out_name}. "
                        f"What should I do about it?"
                    ),
                    finding_id=str(f.id),
                )
    except Exception as e:
        logger.debug("Fingerprint finding for coach_noticed failed: %s", e)

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
    Assemble deep intelligence from multiple sources into a single prompt section.

    Each source runs in its own try/except — any failure is logged and skipped.
    If all sources return nothing, returns "".

    Sources:
    1. Daily intelligence rules that fired today
    2. Wellness trends (28-day check-in aggregation)
    3. PB patterns
    4. This block vs previous block (28-day period comparison)
    5. Training Story (race attribution + adaptation)
    6. Activity shapes
    7. Personal Fingerprint (persisted CorrelationFinding)

    N=1 insights (generate_n1_insights) removed — redundant with persisted
    fingerprint (Source 7) which is already Bonferroni-corrected and persisted.
    """
    from uuid import UUID as _UUID
    athlete_uuid = _UUID(athlete_id)
    _tz = get_athlete_timezone_from_db(db, athlete_uuid)
    _local_today = athlete_local_today(_tz)

    sections: list[str] = []

    # 1. Daily intelligence rules that fired today
    try:
        from services.daily_intelligence import DailyIntelligenceEngine, InsightMode
        intel_result = DailyIntelligenceEngine().evaluate(athlete_uuid, _local_today, db)
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

    # 6. Training Story — race stories, progressions, campaign narrative
    #    Read from stored AthleteFinding (fast path) with fallback to recompute
    try:
        from services.finding_persistence import get_active_findings
        from services.training_story_engine import synthesize_training_story
        from services.race_input_analysis import RaceInputFinding
        from models import PerformanceEvent as _PE

        stored = get_active_findings(athlete_uuid, db)
        if stored:
            findings = [
                RaceInputFinding(
                    layer=getattr(f, 'layer', 'B'),
                    finding_type=f.finding_type,
                    sentence=f.sentence,
                    receipts=f.receipts or {},
                    confidence=f.confidence,
                )
                for f in stored
            ]
        else:
            from services.race_input_analysis import mine_race_inputs
            findings, _gaps = mine_race_inputs(athlete_uuid, db)

        if findings:
            events = db.query(_PE).filter(
                _PE.athlete_id == athlete_uuid,
                _PE.user_confirmed == True,  # noqa: E712
            ).order_by(_PE.event_date).all()

            story = synthesize_training_story(findings, events)
            ctx = story.to_coach_context()
            if ctx.strip():
                sections.append(
                    "--- Training Story (race attribution + adaptation progressions) ---\n"
                    + ctx
                )
    except Exception as e:
        logger.debug(f"Training story failed for home briefing ({athlete_id}): {e}")

    # 7. Recent activity shapes — last 10 days only
    try:
        ten_days_ago = datetime.now(timezone.utc) - timedelta(days=10)
        recent = db.query(Activity).filter(
            Activity.athlete_id == athlete_uuid,
            Activity.sport == "run",
            Activity.shape_sentence.isnot(None),
            Activity.start_time >= ten_days_ago,
        ).order_by(Activity.start_time.desc()).limit(5).all()
        if recent:
            from services.coach_tools import _relative_date as _rel
            lines = []
            for a in recent:
                day = a.start_time.strftime("%a %b %d") if a.start_time else "?"
                rel = _rel(to_activity_local_date(a, _tz), _local_today) if a.start_time else ""
                lines.append(f"- {day} {rel}: {a.shape_sentence}")
            if lines:
                sections.append(
                    "--- Recent Runs (auto-detected from stream data) ---\n"
                    + "\n".join(lines)
                )
    except Exception as e:
        logger.debug(f"Activity shapes failed for home briefing ({athlete_id}): {e}")

    # 8. Personal Fingerprint — confirmed, persisted correlation findings with layer data
    try:
        from services.fingerprint_context import build_fingerprint_prompt_section
        fp_section = build_fingerprint_prompt_section(
            athlete_uuid,
            db,
            verbose=True,
            max_findings=8,
            include_emerging_question=False,
        )
        if fp_section:
            sections.append(fp_section)
    except Exception as e:
        logger.debug("Personal fingerprint failed for home briefing (%s): %s", athlete_id, e)

    if not sections:
        return ""

    return (
        "=== DEEP INTELLIGENCE (what the athlete CANNOT know from looking at their data) ===\n\n"
        + "\n\n".join(sections)
    )


def _get_race_forecast(athlete_id: str) -> Optional[dict]:
    """Load admin-set race forecast from Redis. Returns None on miss or error."""
    from core.cache import get_redis_client
    import json as _json
    try:
        client = get_redis_client()
        if not client:
            return None
        raw = client.get(f"race_forecast:{athlete_id}")
        if not raw:
            return None
        return _json.loads(raw)
    except Exception:
        return None


def _get_personal_heat_multiplier(athlete_id: str, db: Session) -> float:
    """Derive personal heat multiplier from AthleteFinding heat_resilience data.

    Priority:
    1. Valid resilience_ratio from finding receipts -> bounded ratio-derived multiplier
    2. Classification label -> default multiplier
    3. Fallback -> 1.0 (no personalization)

    Bounded to [0.70, 1.30].
    """
    from uuid import UUID as _UUID
    from models import AthleteFinding

    try:
        finding = (
            db.query(AthleteFinding)
            .filter(
                AthleteFinding.athlete_id == _UUID(athlete_id),
                AthleteFinding.finding_type == "heat_resilience",
                AthleteFinding.is_active == True,  # noqa: E712
            )
            .order_by(AthleteFinding.last_confirmed_at.desc())
            .first()
        )
    except Exception:
        return 1.0

    if not finding:
        return 1.0

    receipts = finding.receipts or {}
    classification = receipts.get("classification", "average")

    resilience_ratio = receipts.get("resilience_ratio")
    if resilience_ratio is not None:
        try:
            ratio = float(resilience_ratio)
            multiplier = 1.0 / max(ratio, 0.5)
            return max(0.70, min(multiplier, 1.30))
        except (ValueError, TypeError):
            pass

    classification_map = {"resilient": 0.85, "average": 1.00, "sensitive": 1.15}
    return classification_map.get(classification, 1.0)


def _build_race_weather_context(
    athlete_id: str, db: Session, forecast: dict, race_data: dict,
) -> Optional[str]:
    """Build a RACE WEEK WEATHER context block for the LLM prompt.

    Returns None if forecast data is incomplete.
    """
    from uuid import UUID as _UUID
    from models import Activity
    from services.heat_adjustment import calculate_heat_adjustment_pct

    temp_f = forecast.get("temp_f")
    dew_point_f = forecast.get("dew_point_f")
    if temp_f is None or dew_point_f is None:
        return None

    generic_adj = calculate_heat_adjustment_pct(temp_f, dew_point_f)
    personal_multiplier = _get_personal_heat_multiplier(athlete_id, db)
    personal_adj_pct = generic_adj * personal_multiplier
    personal_adj_pct = max(0.0, min(personal_adj_pct, 0.15))

    similar_count = 0
    similar_avg_adj = None
    try:
        athlete_uuid = _UUID(athlete_id)
        temp_tol = 8.0
        dp_tol = 8.0
        similar_runs = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete_uuid,
                Activity.sport.ilike("run"),
                Activity.is_duplicate == False,  # noqa: E712
                Activity.temperature_f.isnot(None),
                Activity.dew_point_f.isnot(None),
                Activity.distance_m >= 5000,
                Activity.temperature_f.between(temp_f - temp_tol, temp_f + temp_tol),
                Activity.dew_point_f.between(dew_point_f - dp_tol, dew_point_f + dp_tol),
            )
            .all()
        )
        similar_count = len(similar_runs)
        adj_vals = [r.heat_adjustment_pct for r in similar_runs if r.heat_adjustment_pct]
        if adj_vals:
            similar_avg_adj = sum(adj_vals) / len(adj_vals)
    except Exception:
        pass

    description = forecast.get("description", "")
    race_name = race_data.get("name", "your race")
    days_remaining = race_data.get("days_remaining", "?")

    parts = [
        "=== RACE WEEK WEATHER ===",
        f"Race: {race_name} in {days_remaining} days.",
        f"Forecast: {temp_f:.0f}°F, humidity {forecast.get('humidity_pct', '?')}%.",
    ]
    if description:
        parts.append(f"Conditions: {description}.")

    if personal_adj_pct > 0.02:
        pct_display = personal_adj_pct * 100
        parts.append(
            f"Based on this athlete's heat history, expect roughly {pct_display:.0f}% "
            f"pace slowdown in these conditions."
        )

    if similar_count > 0:
        parts.append(
            f"This athlete has {similar_count} previous run(s) in similar conditions."
        )
        if similar_avg_adj is not None:
            avg_display = similar_avg_adj * 100
            parts.append(f"Their average heat impact in similar weather: {avg_display:.1f}%.")

    parts.extend([
        "",
        "COACHING RULE: Use this to set realistic pace expectations for race day. "
        "Speak in coaching language — do NOT expose numeric adjustment percentages, "
        "resilience ratios, or internal metric names to the athlete. "
        "Instead say things like 'the heat may slow you by a minute or two' or "
        "'conditions are favorable for a strong effort'.",
    ])

    return "\n".join(parts)


def _format_race_distance(plan) -> str:
    """Human-readable race distance from plan's goal_race_distance_m."""
    dist_m = getattr(plan, "goal_race_distance_m", None)
    if not dist_m:
        return "unknown distance"
    miles = dist_m / 1609.344
    if abs(miles - 26.2) < 0.5:
        return "marathon"
    if abs(miles - 13.1) < 0.3:
        return "half marathon"
    if abs(miles - 6.2) < 0.2:
        return "10K"
    if abs(miles - 3.1) < 0.2:
        return "5K"
    return f"{miles:.1f} miles"


def compute_race_countdown(
    plan: Optional[TrainingPlan],
    athlete_id: str,
    db: Session,
    local_today: Optional[date] = None,
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

    if local_today is None:
        _tz = get_athlete_timezone_from_db(db, __import__("uuid").UUID(athlete_id))
        local_today = athlete_local_today(_tz)
    days_remaining = (race_date - local_today).days
    if days_remaining < 0:
        return None

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
            Activity.sport == "run",
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
                Activity.sport == "run",
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
    from routers.activities import resolve_activity_title
    resolved = resolve_activity_title(latest)

    workout_classification = None
    run_shape = getattr(latest, "run_shape", None)
    if isinstance(run_shape, dict):
        summary = run_shape.get("summary")
        if isinstance(summary, dict):
            candidate = summary.get("workout_classification")
            if isinstance(candidate, str) and candidate.strip():
                workout_classification = candidate.strip()

    last_run = LastRun(
        activity_id=str(latest.id),
        name=latest.name or "Run",
        start_time=latest.start_time.isoformat(),
        distance_m=latest.distance_m,
        moving_time_s=latest.duration_s,
        average_hr=latest.avg_hr,
        stream_status=stream_status,
        pace_per_km=pace_per_km,
        provider=getattr(latest, "provider", None),
        device_name=getattr(latest, "device_name", None),
        shape_sentence=getattr(latest, "shape_sentence", None),
        athlete_title=getattr(latest, "athlete_title", None),
        resolved_title=resolved,
        heat_adjustment_pct=getattr(latest, "heat_adjustment_pct", None),
        workout_classification=workout_classification,
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
                    threshold_pace_per_km=getattr(athlete, "threshold_pace_per_km", None),
                    rpi=getattr(athlete, "rpi", None),
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
    _ath_tz = get_athlete_timezone(current_user)
    today = athlete_local_today(_ath_tz)
    yesterday = today - timedelta(days=1)
    # UTC bounds for yesterday's activity window
    _yest_start_utc, _yest_end_utc = local_day_bounds_utc(yesterday, _ath_tz)
    # UTC bounds for today (used in week progress and today's workout lookup)
    _today_start_utc, _today_end_utc = local_day_bounds_utc(today, _ath_tz)

    # --- Today's Workout ---
    today_workout = TodayWorkout(has_workout=False)

    # Find active plan
    active_plan = get_active_plan_for_athlete(db, current_user.id)

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
        Activity.sport == "run",
        Activity.start_time >= _yest_start_utc,
        Activity.start_time < _yest_end_utc
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
            CalendarInsight.is_dismissed.is_(False)
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
        # No yesterday activity - find most recent run for context
        last_activity = db.query(Activity).filter(
            Activity.athlete_id == current_user.id,
            Activity.sport == "run",
        ).order_by(Activity.start_time.desc()).first()

        if last_activity:
            from services.timezone_utils import to_activity_local_date as _to_act_local
            last_local_date = _to_act_local(last_activity, _ath_tz)
            days_ago = (today - last_local_date).days
            yesterday_insight = YesterdayInsight(
                has_activity=False,
                last_activity_date=last_local_date.isoformat(),
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

    # Batch fetch all planned workouts and activities for the week (2 queries instead of 14)
    _week_planned: dict = {}
    if active_plan:
        _week_workouts = db.query(PlannedWorkout).filter(
            PlannedWorkout.plan_id == active_plan.id,
            PlannedWorkout.scheduled_date >= monday,
            PlannedWorkout.scheduled_date <= sunday,
        ).all()
        _week_planned = {w.scheduled_date: w for w in _week_workouts}

    _week_actuals_raw = db.query(Activity).filter(
        Activity.athlete_id == current_user.id,
        Activity.start_time >= local_day_bounds_utc(monday, _ath_tz)[0],
        Activity.start_time < local_day_bounds_utc(sunday, _ath_tz)[1],
    ).all()
    _week_actuals: dict = {}
    for _a in _week_actuals_raw:
        from services.timezone_utils import to_activity_local_date as _to_act_local2
        _day = _to_act_local2(_a, _ath_tz)
        if _day not in _week_actuals:
            _week_actuals[_day] = _a  # keep first per day

    for i in range(7):
        day_date = monday + timedelta(days=i)
        day_abbrev = ['M', 'T', 'W', 'T', 'F', 'S', 'S'][i]
        is_past = day_date < today
        is_today_or_future = day_date >= today

        planned_workout = _week_planned.get(day_date)
        actual = _week_actuals.get(day_date)

        workout_type = None
        sport = None
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
            sport = actual.sport
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
            workout_type=workout_type if not is_missed else None,
            sport=sport,
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
        tsb_context=tsb_short_context,
        preferred_units=getattr(current_user, "preferred_units", None),
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

    # Check Strava and Garmin connection status
    strava_connected = bool(current_user.strava_access_token)
    garmin_connected = bool(current_user.garmin_connected and current_user.garmin_oauth_access_token)

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
        active_plan, str(current_user.id), db, local_today=today
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
            _cd = _build_checkin_data_dict(existing_checkin)
            today_checkin = TodayCheckin(
                readiness_label=_cd["readiness_label"],
                sleep_label=_cd["sleep_label"],
                sleep_h=_cd["sleep_h"],
                soreness_label=_cd["soreness_label"],
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
    briefing_is_interim = False
    briefing_last_updated_at = None
    briefing_source = None

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
                from services.home_briefing_cache import read_briefing_cache_with_meta, BriefingState
                from tasks.home_briefing_tasks import enqueue_briefing_refresh

                cached_payload, b_state, b_meta = read_briefing_cache_with_meta(str(current_user.id))
                briefing_state = b_state.value
                briefing_is_interim = bool(b_meta.get("briefing_is_interim", False))
                briefing_last_updated_at = b_meta.get("briefing_last_updated_at")
                briefing_source = b_meta.get("briefing_source")
                _garmin_sleep_h = None
                _checkin_sleep_h = today_checkin.sleep_h if today_checkin else None
                try:
                    _g_h, _g_date, _g_is_today = _get_garmin_sleep_h_for_last_night(str(current_user.id), db)
                    if _g_h is not None and _g_is_today:
                        _garmin_sleep_h = _g_h
                except Exception:
                    _garmin_sleep_h = None
                coach_briefing = _normalize_cached_briefing_payload(
                    cached_payload,
                    garmin_sleep_h=_garmin_sleep_h,
                    checkin_sleep_h=_checkin_sleep_h,
                )

                if b_state in (BriefingState.STALE, BriefingState.MISSING) or briefing_is_interim:
                    try:
                        enqueue_briefing_refresh(str(current_user.id), priority="high")
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
                    Activity.sport == "run",
                    Activity.start_time >= _today_start_utc,
                    Activity.start_time < _today_end_utc,
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
                    elev_m = float(today_actual.total_elevation_gain) if today_actual.total_elevation_gain is not None else None
                    today_completed = {
                        "name": today_actual.name or "Run",
                        "distance_mi": actual_mi,
                        "pace": actual_pace,
                        "avg_hr": int(today_actual.avg_hr) if today_actual.avg_hr else None,
                        "duration_min": round(today_actual.duration_s / 60, 0) if today_actual.duration_s else None,
                        "elevation_gain_ft": int(round(elev_m * 3.28084)) if elev_m is not None else None,
                        "temperature_f": round(float(today_actual.temperature_f), 1) if today_actual.temperature_f is not None else None,
                        "humidity_pct": round(float(today_actual.humidity_pct), 0) if today_actual.humidity_pct is not None else None,
                        "heat_adjustment_pct": round(float(today_actual.heat_adjustment_pct), 1) if today_actual.heat_adjustment_pct is not None else None,
                    }
                    try:
                        from models import ActivitySplit as _ActivitySplit
                        # See _render_workout_structure_block: this flag
                        # keeps the "no structure" prompt branch honest
                        # when splits haven't been processed yet.
                        today_completed["splits_available"] = (
                            db.query(_ActivitySplit.id)
                            .filter(_ActivitySplit.activity_id == today_actual.id)
                            .first()
                        ) is not None
                        ws = _summarize_workout_structure(today_actual.id, db)
                        if ws:
                            today_completed["workout_structure"] = ws
                        if today_actual.run_shape and isinstance(today_actual.run_shape, dict):
                            sc = today_actual.run_shape.get('summary', {}).get('workout_classification', '')
                            if sc:
                                today_completed["shape_classification"] = sc
                    except Exception as _ws_err:
                        logger.debug("Workout structure detection skipped: %s", _ws_err)

                planned_workout_dict = None
                if today_workout and today_workout.has_workout:
                    planned_workout_dict = {
                        "has_workout": True,
                        "workout_type": today_workout.workout_type,
                        "title": today_workout.title,
                        "distance_mi": today_workout.distance_mi,
                    }

                upcoming_plan_list = []
                if active_plan:
                    _upcoming_days = (
                        db.query(PlannedWorkout)
                        .filter(
                            PlannedWorkout.plan_id == active_plan.id,
                            PlannedWorkout.scheduled_date > today,
                            PlannedWorkout.scheduled_date <= today + timedelta(days=3),
                        )
                        .order_by(PlannedWorkout.scheduled_date)
                        .all()
                    )
                    for pw in _upcoming_days:
                        _pw_mi = round(pw.target_distance_km * 0.621371, 1) if pw.target_distance_km else None
                        upcoming_plan_list.append({
                            "date": pw.scheduled_date.isoformat(),
                            "day_name": pw.scheduled_date.strftime("%A"),
                            "workout_type": pw.workout_type,
                            "title": pw.title,
                            "distance_mi": _pw_mi,
                            "description": pw.description,
                        })

                race_data_dict = None
                if race_countdown:
                    race_data_dict = {
                        "name": race_countdown.race_name,
                        "date": race_countdown.race_date,
                        "days_remaining": race_countdown.days_remaining,
                        "distance": _format_race_distance(active_plan),
                        "goal_time": race_countdown.goal_time,
                        "goal_pace": race_countdown.goal_pace,
                        "predicted_time": race_countdown.predicted_time,
                    }

                checkin_data_dict = None
                if today_checkin:
                    checkin_data_dict = {
                        "readiness_label": today_checkin.readiness_label,
                        "sleep_label": today_checkin.sleep_label,
                        "sleep_h": today_checkin.sleep_h,
                        "soreness_label": today_checkin.soreness_label,
                    }

                prep = generate_coach_home_briefing(
                    athlete_id=str(current_user.id),
                    db=db,
                    today_completed=today_completed,
                    planned_workout=planned_workout_dict,
                    checkin_data=checkin_data_dict,
                    race_data=race_data_dict,
                    upcoming_plan=upcoming_plan_list if upcoming_plan_list else None,
                )

                if len(prep) == 1:
                    coach_briefing = prep[0]
                else:
                    _, prompt, schema_fields, required_fields, cache_key, garmin_sleep_h, _local_today, _local_now = prep
                    if garmin_sleep_h is not None:
                        if checkin_data_dict is None:
                            checkin_data_dict = {}
                        checkin_data_dict["garmin_sleep_h"] = garmin_sleep_h
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
                                local_today=_local_today,
                                local_now=_local_now,
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

    # --- Path A: Finding + correlations flag ---
    home_finding = None
    has_correlations = False
    try:
        from models import CorrelationFinding as _CF
        active_count = (
            db.query(_CF)
            .filter(
                _CF.athlete_id == current_user.id,
                _CF.is_active.is_(True),
                _CF.times_confirmed >= 3,
            )
            .count()
        )
        has_correlations = active_count > 0
        if active_count > 0:
            eligible = (
                db.query(_CF)
                .filter(
                    _CF.athlete_id == current_user.id,
                    _CF.is_active.is_(True),
                    _CF.times_confirmed >= 3,
                )
                .order_by(_CF.times_confirmed.desc())
                .limit(5)
                .all()
            )
            _home_tz = get_athlete_timezone(current_user)
            idx = athlete_local_today(_home_tz).toordinal() % len(eligible)
            f = eligible[idx]
            tier = "strong" if f.times_confirmed >= 8 else "confirmed"
            home_finding = HomeFinding(
                text=_sanitize_finding_text(
                    f.insight_text or f"{friendly_signal_name(f.input_name)} affects your {friendly_signal_name(f.output_metric)}"
                ),
                confidence_tier=tier,
                domain=f.output_metric,
                times_confirmed=f.times_confirmed,
            )
    except Exception as e:
        logger.warning(f"Home finding computation failed: {type(e).__name__}: {e}")

    garmin_wellness = _build_garmin_wellness(str(current_user.id), db)

    # Recent cross-training: most recent non-run activity in last 24h (athlete local)
    recent_cross_training = None
    try:
        _ct_cutoff_utc = _today_start_utc - timedelta(hours=24)
        _ct_activities = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == current_user.id,
                Activity.sport != "run",
                Activity.is_duplicate == False,  # noqa: E712
                Activity.start_time >= _ct_cutoff_utc,
            )
            .order_by(desc(Activity.start_time))
            .all()
        )
        if _ct_activities:
            _latest_ct = _ct_activities[0]
            recent_cross_training = RecentCrossTraining(
                id=str(_latest_ct.id),
                sport=_latest_ct.sport or "other",
                name=_latest_ct.name,
                distance_m=_latest_ct.distance_m,
                duration_s=_latest_ct.duration_s or _latest_ct.moving_time_s,
                avg_hr=_latest_ct.avg_hr,
                steps=_latest_ct.steps,
                active_kcal=_latest_ct.active_kcal,
                start_time=_latest_ct.start_time.isoformat(),
                additional_count=len(_ct_activities) - 1,
            )
    except Exception as e:
        logger.warning(f"Recent cross-training query failed: {type(e).__name__}: {e}")

    return HomeResponse(
        today=today_workout,
        yesterday=yesterday_insight,
        week=week_progress,
        hero_narrative=hero_narrative,
        strava_connected=strava_connected,
        garmin_connected=garmin_connected,
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
        briefing_is_interim=briefing_is_interim,
        briefing_last_updated_at=briefing_last_updated_at,
        briefing_source=briefing_source,
        last_run=last_run,
        finding=home_finding,
        has_correlations=has_correlations,
        garmin_wellness=garmin_wellness,
        recent_cross_training=recent_cross_training,
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
            last_updated=athlete_local_today(get_athlete_timezone(current_user)).isoformat()
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
