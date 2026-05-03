"""
Calendar API Router

The calendar is the central UI hub for StrideIQ subscribers.
Everything flows through it: plans, activities, insights, notes, coach chat.

Endpoints:
- GET /calendar - Get merged plan + actual view for date range
- GET /calendar/{date} - Get full day detail
- POST /calendar/{date}/notes - Add note to a day
- GET /calendar/week/{week_number} - Get week view with summary
- POST /calendar/coach - Send message to GPT coach
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, datetime, timedelta
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, ConfigDict
import json
import re

from core.database import get_db
from core.auth import get_current_user
from core.feature_flags import is_feature_enabled
from models import (
    Athlete, Activity, PlannedWorkout,
    CalendarNote, CoachChat, CalendarInsight
)
from services.ai_coach import AICoach
from services import coach_tools
from services.plan_lifecycle import get_active_plan_for_athlete
from services.timezone_utils import (
    get_athlete_timezone,
    to_activity_local_date,
    athlete_local_today,
    local_day_bounds_utc,
)

router = APIRouter(prefix="/v1/calendar", tags=["Calendar"])


# =============================================================================
# SCHEMAS
# =============================================================================

class CalendarNoteCreate(BaseModel):
    note_type: str  # 'pre_workout', 'post_workout', 'free_text', 'voice_memo'
    structured_data: Optional[dict] = None
    text_content: Optional[str] = None
    activity_id: Optional[UUID] = None


class CalendarNoteResponse(BaseModel):
    id: UUID
    note_date: date
    note_type: str
    structured_data: Optional[dict] = None
    text_content: Optional[str] = None
    activity_id: Optional[UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlannedWorkoutResponse(BaseModel):
    id: UUID
    plan_id: UUID
    scheduled_date: date
    workout_type: str
    workout_subtype: Optional[str] = None
    title: str
    description: Optional[str] = None
    phase: str
    week_number: int  # Required for week summary grouping
    target_distance_km: Optional[float] = None
    target_duration_minutes: Optional[int] = None
    segments: Optional[list] = None  # List of workout segments
    workout_variant_id: Optional[str] = None
    completed: bool
    skipped: bool
    coach_notes: Optional[str] = None  # Pace description or guidance
    
    # Option A/B support
    has_option_b: bool = False
    option_b_title: Optional[str] = None
    option_b_description: Optional[str] = None
    option_b_segments: Optional[list] = None  # List of workout segments for option B
    selected_option: str = "A"  # Which option athlete has selected

    model_config = ConfigDict(from_attributes=True)


class ActivitySummary(BaseModel):
    id: UUID
    name: Optional[str] = None
    start_time: datetime
    distance_m: Optional[int] = None
    duration_s: Optional[int] = None
    avg_hr: Optional[int] = None
    workout_type: Optional[str] = None
    intensity_score: Optional[float] = None
    shape_sentence: Optional[str] = None
    athlete_title: Optional[str] = None
    resolved_title: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


def _activity_summary(a) -> ActivitySummary:
    """Build ActivitySummary with computed resolved_title."""
    from routers.activities import resolve_activity_title
    s = ActivitySummary.model_validate(a)
    s.resolved_title = resolve_activity_title(a)
    return s


class InsightResponse(BaseModel):
    id: UUID
    insight_type: str
    priority: int
    title: str
    content: str
    activity_id: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)


class InlineInsight(BaseModel):
    """Single inline insight for calendar display - one per day max."""
    metric: str  # 'efficiency', 'hr', 'pace', 'drift', 'consistency'
    value: str  # Human-readable value
    delta: Optional[float] = None  # % change vs baseline (if applicable)
    sentiment: str = 'neutral'  # 'positive', 'negative', 'neutral'


class CalendarDayResponse(BaseModel):
    date: date
    day_of_week: int  # 0=Monday, 6=Sunday
    day_name: str
    
    # Plan data
    planned_workout: Optional[PlannedWorkoutResponse] = None
    
    # Actual data
    activities: List[ActivitySummary] = []
    
    # Status: 'future', 'completed', 'modified', 'missed', 'rest'
    status: str
    
    # Notes and insights
    notes: List[CalendarNoteResponse] = []
    insights: List[InsightResponse] = []
    
    # Inline insight - single key metric for this day (for calendar cell display)
    inline_insight: Optional[InlineInsight] = None
    
    # Summary metrics for the day
    # ``total_*`` = all sports (cross-training inclusive). Do not use as
    # "running mileage" — use ``running_distance_m`` / ``running_duration_s``.
    total_distance_m: int = 0
    total_duration_s: int = 0
    running_distance_m: int = 0
    running_duration_s: int = 0
    other_distance_m: int = 0
    other_duration_s: int = 0


class WeekSummaryResponse(BaseModel):
    week_number: int
    phase: Optional[str] = None
    phase_week: Optional[int] = None
    
    planned_m: int = 0
    completed_m: int = 0
    
    quality_sessions_planned: int
    quality_sessions_completed: int
    long_run_planned_m: Optional[int] = None
    long_run_completed_m: Optional[int] = None
    
    # Focus text
    focus: Optional[str] = None
    
    # Days
    days: List[CalendarDayResponse]


class CalendarRangeResponse(BaseModel):
    start_date: date
    end_date: date
    
    # Active plan info
    active_plan: Optional[dict] = None
    current_week: Optional[int] = None
    current_phase: Optional[str] = None
    
    # Days in range
    days: List[CalendarDayResponse]
    
    # Week summaries
    week_summaries: List[WeekSummaryResponse] = []


class VariantOptionResponse(BaseModel):
    id: str
    display_name: str
    stem: str
    when_to_avoid: str
    pairs_poorly_with: str
    is_current: bool = False


class VariantSelectRequest(BaseModel):
    variant_id: str


class CoachMessageRequest(BaseModel):
    message: str
    context_type: str = "open"  # 'day', 'week', 'build', 'open'
    context_date: Optional[date] = None
    context_week: Optional[int] = None
    chat_id: Optional[UUID] = None  # Continue existing chat


class CoachMessageResponse(BaseModel):
    chat_id: UUID
    response: str
    context_type: str

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _looks_like_action(text: Optional[str]) -> bool:
    if not text:
        return False
    lower = text.lower()
    action_verbs = (
        "keep",
        "plan",
        "schedule",
        "run",
        "take",
        "prioritize",
        "reduce",
        "build",
        "skip",
        "focus",
        "recover",
        "hydrate",
        "fuel",
        "sleep",
    )
    return any(v in lower for v in action_verbs)


def _extract_json_object(text: str) -> Optional[dict]:
    if not text:
        return None
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```[a-zA-Z]*\s*", "", candidate)
        candidate = re.sub(r"\s*```$", "", candidate)
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _build_day_coach_contract_from_facts(day_data: dict) -> dict:
    weekday = day_data.get("weekday") or "today"
    planned = day_data.get("planned_workout") or {}
    acts = day_data.get("activities") or []
    marathon_pace = day_data.get("marathon_pace_per_mile") or day_data.get("marathon_pace_per_km")

    if not acts:
        planned_title = planned.get("title") or planned.get("workout_type") or "planned session"
        return {
            "assessment": f"{weekday} is set up as a controlled day with no logged run yet.",
            "implication": "This is a stable point in the week to protect recovery and keep quality sessions effective.",
            "action": [f"Execute {planned_title} as easy effort and reassess after the run."],
            "athlete_alignment_note": "No completed run found for this day.",
            "evidence": [f"{day_data.get('date')}: planned {planned_title}"],
            "safety_status": "ok",
        }

    first = acts[0]
    run_name = first.get("name") or "Run"
    pace = first.get("pace_per_mile") or first.get("pace_per_km") or "pace unavailable"
    distance = first.get("distance_mi") or first.get("distance_km")
    unit = "mi" if first.get("distance_mi") is not None else "km"
    rel = first.get("pace_vs_marathon_label")
    assessment = f"{weekday}'s {run_name} was a strong, controlled execution."
    if distance:
        assessment = f"{weekday}'s {run_name} ({distance:.1f} {unit} at {pace}) was a strong, controlled execution."

    implication = "That suggests your current aerobic base is supporting workload without obvious loss of control."
    if rel:
        implication = f"With pace tracking {rel}, your effort-to-speed relationship stays stable for this phase."
    elif marathon_pace:
        implication = f"Compared with your marathon reference pace ({marathon_pace}), this effort supports steady build progression."

    action = "Prioritize an easy recovery day next, then keep the next quality session controlled rather than stacking hard days."
    if planned.get("title"):
        action = f"Keep tomorrow easy to absorb this, then execute {planned.get('title')} with controlled effort."

    evidence = [f"{day_data.get('date')}: {run_name} @ {pace}"]
    if rel:
        evidence.append(f"{day_data.get('date')}: pace vs marathon reference = {rel}")

    return {
        "assessment": assessment,
        "implication": implication,
        "action": [action],
        "athlete_alignment_note": "Anchored to day facts and run execution context.",
        "evidence": evidence,
        "safety_status": "ok",
    }


def _valid_day_coach_contract(payload: dict) -> bool:
    if not isinstance(payload, dict):
        return False
    assessment = payload.get("assessment")
    implication = payload.get("implication")
    action = payload.get("action")
    if not assessment or not implication or not isinstance(action, list) or len(action) == 0:
        return False
    if not any(_looks_like_action(a) for a in action if isinstance(a, str)):
        return False
    return True


def _format_day_coach_contract(payload: dict) -> str:
    assessment = str(payload.get("assessment", "")).strip()
    implication = str(payload.get("implication", "")).strip()
    action_items = [str(a).strip() for a in payload.get("action", []) if str(a).strip()]
    evidence = [str(e).strip() for e in payload.get("evidence", []) if str(e).strip()]
    lines: List[str] = []
    if assessment:
        lines.append(assessment)
    if implication:
        lines.append(implication)
    if action_items:
        lines.append("")
        lines.append("Next step:")
        for item in action_items:
            lines.append(f"- {item}")
    if evidence:
        lines.append("")
        lines.append("## Evidence")
        for ev in evidence[:4]:
            lines.append(f"- {ev}")
    return "\n".join(lines).strip()


def _sanitize_day_coach_text(text: str) -> str:
    out = (text or "").strip()
    out = re.sub(r"(?im)^\s*\*{0,2}\s*date\s*:\s*.*$", "", out)
    out = re.sub(r"(?im)^\s*\*{0,2}\s*recorded pace vs marathon pace\s*:\s*.*$", "", out)
    out = re.sub(r"(?im)^\s*authoritative fact capsule.*$", "", out)
    out = re.sub(r"(?im)^\s*response contract.*$", "", out)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    return out

def split_day_distance_duration_by_sport(activities: List[Activity]) -> tuple[int, int, int, int, int, int]:
    """Split a day's activities into running vs other sports.

    Returns:
        (running_distance_m, running_duration_s,
         other_distance_m, other_duration_s,
         total_distance_m, total_duration_s)

    ``total_*`` is the cross-sport sum (legacy / training-load style).
    For *planned run* completion and *running mileage* UI, use the running
    components only — cross-training must not satisfy a running target
    (Dejan-class bug: walk + planned long run same day).
    """
    rd = rs = od = os_ = 0
    for a in activities:
        d = int(a.distance_m or 0)
        t = int(a.duration_s or 0)
        if (a.sport or "").lower() == "run":
            rd += d
            rs += t
        else:
            od += d
            os_ += t
    return rd, rs, od, os_, rd + od, rs + os_


def get_day_status(planned: Optional[PlannedWorkout], activities: List[Activity], day_date: date, today: Optional[date] = None) -> str:
    """Determine the status of a calendar day."""
    if today is None:
        today = date.today()
    
    if day_date > today:
        return "future"
    
    if not planned:
        if activities:
            return "completed"  # Unplanned activity
        return "rest"
    
    if planned.workout_type == "rest" or planned.workout_type == "gym":
        return "rest"
    
    if planned.completed or planned.completed_activity_id:
        return "completed"
    
    if planned.skipped:
        return "missed"
    
    if activities:
        # ``target_distance_km`` on planned rows is a *running* distance target.
        # Compare running mileage only — a walk or strength session must not
        # move a missed planned run to completed/modified (see split_day_*).
        running_activities = [a for a in activities if (a.sport or "").lower() == "run"]
        total_distance = sum(int(a.distance_m or 0) for a in running_activities)
        planned_distance = (planned.target_distance_km or 0) * 1000
        
        if planned_distance > 0:
            if total_distance == 0:
                # Cross-training only — does not satisfy the planned run.
                if day_date < today:
                    return "missed"
                return "future"
            ratio = total_distance / planned_distance
            if 0.8 <= ratio <= 1.2:
                return "completed"
            else:
                return "modified"
        return "completed"
    
    if day_date < today:
        return "missed"
    
    return "future"


def get_day_name(day_date: date) -> str:
    """Get day name from date."""
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return days[day_date.weekday()]


def meters_to_miles(meters: int) -> float:
    """Convert meters to miles."""
    return round(meters / 1609.344, 1)


def _provider_rank(provider: Optional[str]) -> int:
    """
    Higher is better (preferred for display when collapsing duplicates).

    We treat Strava as the canonical activity source when present, because it is the
    primary ingestion provider and often has richer metadata downstream.
    """
    p = (provider or "").lower()
    if p == "strava":
        return 3
    if p == "garmin":
        return 2
    if p:
        return 1
    return 0


def _activities_are_probable_duplicates(a: Activity, b: Activity) -> bool:
    """
    Heuristic: same workout recorded by multiple providers.

    Constraints are intentionally conservative to avoid collapsing true doubles.
    """
    try:
        dt_s = abs((a.start_time - b.start_time).total_seconds())
    except Exception:
        return False
    if dt_s > 10 * 60:  # 10 minutes
        return False

    da = a.distance_m or 0
    db = b.distance_m or 0
    if da > 0 and db > 0:
        # Allow either 2% relative tolerance or 150m absolute tolerance (GPS/provider drift).
        if abs(da - db) > max(150, int(0.02 * max(da, db))):
            return False

    ta = a.duration_s or 0
    tb = b.duration_s or 0
    if ta > 0 and tb > 0:
        # 10% or 5min tolerance.
        if abs(ta - tb) > max(300, int(0.10 * max(ta, tb))):
            return False

    return True


def dedupe_activities_for_calendar_display(activities: List[Activity]) -> List[Activity]:
    """
    Collapse probable cross-provider duplicates so the calendar doesn't show double entries.
    """
    if not activities:
        return []
    acts = sorted(activities, key=lambda x: x.start_time)
    kept: List[Activity] = []
    for a in acts:
        matched_idx: Optional[int] = None
        # Only check a few recent kept entries; duplicates will be close in time.
        for i in range(max(0, len(kept) - 5), len(kept)):
            if _activities_are_probable_duplicates(a, kept[i]):
                matched_idx = i
                break
        if matched_idx is None:
            kept.append(a)
            continue

        incumbent = kept[matched_idx]
        # Keep the preferred provider version.
        if _provider_rank(getattr(a, "provider", None)) > _provider_rank(getattr(incumbent, "provider", None)):
            kept[matched_idx] = a
    return kept


def get_primary_activity(activities: List[Activity]) -> Optional[Activity]:
    """
    Select the primary (most significant) activity from a list.
    
    Priority:
    1. Race-flagged activity (is_race_candidate=True)
    2. Longest activity by distance
    
    This ensures that when multiple activities occur on the same day
    (e.g., warmup + race), the main event is used for inline metrics.
    """
    if not activities:
        return None
    
    if len(activities) == 1:
        return activities[0]
    
    # Priority 1: Race-flagged activity
    races = [a for a in activities if getattr(a, 'is_race_candidate', False)]
    if races:
        # Return longest race if multiple
        return max(races, key=lambda a: a.distance_m or 0)
    
    # Priority 2: Longest activity
    return max(activities, key=lambda a: a.distance_m or 0)


def generate_inline_insight(activities: List[Activity], planned: Optional[PlannedWorkout], preferred_units: Optional[str] = None) -> Optional[InlineInsight]:
    """
    Generate a single inline insight for a calendar day.
    
    Priority:
    1. Efficiency delta (if available)
    2. HR zone indicator
    3. Pace consistency
    
    Tone: Data speaks. No praise.
    """
    if not activities:
        return None
    
    # Use primary activity (longest or race), not just first
    activity = get_primary_activity(activities)
    
    # Check for efficiency score (stored in activity or calculated)
    if hasattr(activity, 'efficiency_factor') and activity.efficiency_factor:
        # Would need baseline comparison - placeholder
        pass
    
    # HR-based insight - always show when available for consistency
    # Inconsistent display (only notable HR) creates user confusion
    if activity.avg_hr:
        if activity.avg_hr < 135:
            sentiment = 'positive'  # Low HR = good aerobic efficiency
        elif activity.avg_hr > 165:
            sentiment = 'negative'  # High HR = worth noting
        else:
            sentiment = 'neutral'   # Normal range
        
        return InlineInsight(
            metric='hr',
            value=f'HR {activity.avg_hr}',
            sentiment=sentiment
        )
    
    # Pace-based insight
    if activity.distance_m and activity.duration_s and activity.distance_m > 0:
        _is_met = (preferred_units or "imperial").lower() == "metric"
        _pu = "km" if _is_met else "mi"
        _div = 1000 if _is_met else 1609.344
        _pace_s = activity.duration_s / (activity.distance_m / _div)
        mins = int(_pace_s // 60)
        secs = int(_pace_s % 60)
        pace_str = f'{mins}:{secs:02d}'
        
        if planned and planned.workout_type:
            wt = planned.workout_type
            pace_s_per_km = activity.duration_s / (activity.distance_m / 1000)
            if 'easy' in wt or 'recovery' in wt:
                if pace_s_per_km > 298:  # ~4:58/km ≈ 8:00/mi
                    return InlineInsight(
                        metric='pace',
                        value=f'{pace_str}/{_pu}',
                        sentiment='positive'
                    )
            elif 'threshold' in wt or 'tempo' in wt:
                return InlineInsight(
                    metric='pace',
                    value=f'{pace_str}/{_pu}',
                    sentiment='neutral'
                )
    
    if activity.distance_m:
        _is_met = (preferred_units or "imperial").lower() == "metric"
        if _is_met:
            _val = round(activity.distance_m / 1000, 1)
            return InlineInsight(metric='distance', value=f'{_val}km', sentiment='neutral')
        else:
            _val = round(activity.distance_m / 1609.344, 1)
            return InlineInsight(metric='distance', value=f'{_val}mi', sentiment='neutral')
    
    return None


# =============================================================================
# ENDPOINTS
# =============================================================================

# IMPORTANT: /signals MUST be defined BEFORE /{calendar_date} to avoid route conflict
# FastAPI matches routes in order - /{calendar_date} would match "signals" as a date string

@router.get("/signals")
def get_calendar_signals_endpoint(
    start_date: date = Query(..., description="Start date for signals"),
    end_date: date = Query(..., description="End date for signals"),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get calendar signals for a date range.
    
    Returns day-level badges (efficiency spikes, decay risks, PR matches, etc.)
    and week-level trajectory summaries.
    
    ADR-016: Calendar Signals - Day Badges + Week Trajectory
    
    Requires feature flag: signals.calendar_badges
    """
    import logging
    from services.calendar_signals import get_calendar_signals, calendar_signals_to_dict
    
    logger = logging.getLogger(__name__)
    
    # Check feature flag
    flag_enabled = is_feature_enabled("signals.calendar_badges", str(current_user.id), db)
    
    if not flag_enabled:
        return {
            "day_signals": {},
            "week_trajectories": {},
            "message": "Calendar signals feature not enabled"
        }
    
    # Validate date range (max 90 days)
    if (end_date - start_date).days > 90:
        logger.warning(f"Calendar signals: date range too large for athlete {current_user.id}: {start_date} to {end_date}")
        return {
            "day_signals": {},
            "week_trajectories": {},
            "message": "Date range cannot exceed 90 days"
        }
    
    if end_date < start_date:
        logger.warning(f"Calendar signals: end_date before start_date for athlete {current_user.id}: {start_date} to {end_date}")
        return {
            "day_signals": {},
            "week_trajectories": {},
            "message": "End date must be after start date"
        }
    
    try:
        # Get signals
        result = get_calendar_signals(
            athlete_id=str(current_user.id),
            start_date=start_date,
            end_date=end_date,
            db=db
        )
        
        return calendar_signals_to_dict(result)
    except Exception as e:
        logger.error(f"Calendar signals error for athlete {current_user.id}: {e}")
        return {
            "day_signals": {},
            "week_trajectories": {},
            "message": "Error fetching calendar signals"
        }


@router.get("", response_model=CalendarRangeResponse)
def get_calendar(
    start_date: date = Query(default=None, description="Start date (defaults to start of current month)"),
    end_date: date = Query(default=None, description="End date (defaults to end of current month)"),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get calendar data for a date range.
    
    Returns merged view of:
    - Planned workouts (from active training plan)
    - Actual activities (synced from Strava/Garmin)
    - Notes
    - Insights
    """
    # Resolve athlete timezone for correct calendar-day bucketing
    tz = get_athlete_timezone(current_user)
    local_today = athlete_local_today(tz)

    # Default to current month in athlete's local timezone
    if not start_date:
        start_date = local_today.replace(day=1)
    if not end_date:
        next_month = start_date.replace(day=28) + timedelta(days=4)
        end_date = next_month.replace(day=1) - timedelta(days=1)
    
    # Get active training plan
    active_plan = get_active_plan_for_athlete(db, current_user.id)
    
    # Get planned workouts in range
    planned_workouts = {}
    current_week = None
    current_phase = None
    
    if active_plan:
        workouts = db.query(PlannedWorkout).filter(
            PlannedWorkout.plan_id == active_plan.id,
            PlannedWorkout.scheduled_date >= start_date,
            PlannedWorkout.scheduled_date <= end_date
        ).all()
        
        for w in workouts:
            planned_workouts[w.scheduled_date] = w
            
            if w.scheduled_date == local_today:
                current_week = w.week_number
                current_phase = w.phase
        
        if current_week is None and active_plan.plan_start_date:
            if local_today < active_plan.plan_start_date:
                current_week = 1
                first_workout = db.query(PlannedWorkout).filter(
                    PlannedWorkout.plan_id == active_plan.id
                ).order_by(PlannedWorkout.scheduled_date).first()
                if first_workout:
                    current_phase = first_workout.phase
            elif local_today <= (active_plan.plan_end_date or local_today):
                days_from_start = (local_today - active_plan.plan_start_date).days
                current_week = (days_from_start // 7) + 1
                nearest = db.query(PlannedWorkout).filter(
                    PlannedWorkout.plan_id == active_plan.id,
                    PlannedWorkout.week_number == current_week
                ).first()
                if nearest:
                    current_phase = nearest.phase
    
    # Query activities using UTC bounds for the athlete-local date range
    range_start_utc = local_day_bounds_utc(start_date, tz)[0]
    range_end_utc = local_day_bounds_utc(end_date, tz)[1]

    activities_by_date = {}
    activities = db.query(Activity).filter(
        Activity.athlete_id == current_user.id,
        Activity.is_duplicate == False,  # noqa: E712
        Activity.start_time >= range_start_utc,
        Activity.start_time < range_end_utc,
    ).order_by(Activity.start_time).all()
    
    for a in activities:
        activity_date = to_activity_local_date(a, tz)
        if activity_date not in activities_by_date:
            activities_by_date[activity_date] = []
        activities_by_date[activity_date].append(a)
    
    # Get notes in range
    notes_by_date = {}
    notes = db.query(CalendarNote).filter(
        CalendarNote.athlete_id == current_user.id,
        CalendarNote.note_date >= start_date,
        CalendarNote.note_date <= end_date
    ).all()
    
    for n in notes:
        if n.note_date not in notes_by_date:
            notes_by_date[n.note_date] = []
        notes_by_date[n.note_date].append(n)
    
    # Get insights in range
    insights_by_date = {}
    insights = db.query(CalendarInsight).filter(
        CalendarInsight.athlete_id == current_user.id,
        CalendarInsight.insight_date >= start_date,
        CalendarInsight.insight_date <= end_date,
        CalendarInsight.is_dismissed.is_(False)
    ).order_by(CalendarInsight.priority.desc()).all()
    
    for i in insights:
        if i.insight_date not in insights_by_date:
            insights_by_date[i.insight_date] = []
        insights_by_date[i.insight_date].append(i)
    
    # Build calendar days
    days = []
    current = start_date
    while current <= end_date:
        planned = planned_workouts.get(current)
        day_activities = dedupe_activities_for_calendar_display(activities_by_date.get(current, []))
        day_notes = notes_by_date.get(current, [])
        day_insights = insights_by_date.get(current, [])
        
        status = get_day_status(planned, day_activities, current, today=local_today)
        
        rd, rs, od, os_, td, ts = split_day_distance_duration_by_sport(day_activities)
        
        # Generate inline insight for completed days
        inline_insight = None
        if day_activities and status in ('completed', 'modified'):
            inline_insight = generate_inline_insight(day_activities, planned, getattr(current_user, "preferred_units", None))
        
        day_response = CalendarDayResponse(
            date=current,
            day_of_week=current.weekday(),
            day_name=get_day_name(current),
            planned_workout=PlannedWorkoutResponse.model_validate(planned) if planned else None,
            activities=[_activity_summary(a) for a in day_activities],
            status=status,
            notes=[CalendarNoteResponse.model_validate(n) for n in day_notes],
            insights=[InsightResponse.model_validate(i) for i in day_insights],
            inline_insight=inline_insight,
            total_distance_m=td,
            total_duration_s=ts,
            running_distance_m=rd,
            running_duration_s=rs,
            other_distance_m=od,
            other_duration_s=os_,
        )
        days.append(day_response)
        current += timedelta(days=1)
    
    # Build week summaries
    week_summaries = []
    if active_plan:
        # Group days by week number
        weeks = {}
        for day in days:
            if day.planned_workout:
                week_num = day.planned_workout.week_number if hasattr(day.planned_workout, 'week_number') else None
                if week_num:
                    if week_num not in weeks:
                        weeks[week_num] = {"days": [], "phase": day.planned_workout.phase}
                    weeks[week_num]["days"].append(day)
        
        for week_num, week_data in sorted(weeks.items()):
            week_days = week_data["days"]
            
            planned_m = sum(
                int((d.planned_workout.target_distance_km or 0) * 1000)
                for d in week_days if d.planned_workout
            )
            completed_m = sum(
                d.running_distance_m for d in week_days
            )
            
            quality_planned = sum(
                1 for d in week_days
                if d.planned_workout and d.planned_workout.workout_type in ['threshold', 'threshold_intervals', 'intervals', 'long_mp']
            )
            quality_completed = sum(
                1 for d in week_days
                if d.status == "completed" and d.planned_workout and d.planned_workout.workout_type in ['threshold', 'threshold_intervals', 'intervals', 'long_mp']
            )
            
            week_summaries.append(WeekSummaryResponse(
                week_number=week_num,
                phase=week_data["phase"],
                planned_m=planned_m,
                completed_m=completed_m,
                quality_sessions_planned=quality_planned,
                quality_sessions_completed=quality_completed,
                days=week_days
            ))
    
    return CalendarRangeResponse(
        start_date=start_date,
        end_date=end_date,
        active_plan={
            "id": str(active_plan.id),
            "name": active_plan.name,
            "goal_race_name": active_plan.goal_race_name,
            "goal_race_date": active_plan.goal_race_date.isoformat() if active_plan.goal_race_date else None,
            "total_weeks": active_plan.total_weeks
        } if active_plan else None,
        current_week=current_week,
        current_phase=current_phase,
        days=days,
        week_summaries=week_summaries
    )


@router.get("/{calendar_date}", response_model=CalendarDayResponse)
def get_calendar_day(
    calendar_date: date,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get full detail for a specific calendar day.
    
    Returns:
    - Planned workout with structure
    - Actual activities with analysis
    - All notes
    - All insights
    """
    tz = get_athlete_timezone(current_user)
    local_today = athlete_local_today(tz)

    # Get active plan and planned workout
    active_plan = get_active_plan_for_athlete(db, current_user.id)
    
    planned = None
    if active_plan:
        planned = db.query(PlannedWorkout).filter(
            PlannedWorkout.plan_id == active_plan.id,
            PlannedWorkout.scheduled_date == calendar_date
        ).first()
    
    # Query activities using athlete-local day bounds in UTC
    day_start_utc, day_end_utc = local_day_bounds_utc(calendar_date, tz)
    activities = db.query(Activity).filter(
        Activity.athlete_id == current_user.id,
        Activity.is_duplicate == False,  # noqa: E712
        Activity.start_time >= day_start_utc,
        Activity.start_time < day_end_utc,
    ).order_by(Activity.start_time).all()
    activities = dedupe_activities_for_calendar_display(activities)
    
    # Get notes
    notes = db.query(CalendarNote).filter(
        CalendarNote.athlete_id == current_user.id,
        CalendarNote.note_date == calendar_date
    ).order_by(CalendarNote.created_at).all()
    
    # Get insights
    insights = db.query(CalendarInsight).filter(
        CalendarInsight.athlete_id == current_user.id,
        CalendarInsight.insight_date == calendar_date,
        CalendarInsight.is_dismissed.is_(False)
    ).order_by(CalendarInsight.priority.desc()).all()
    
    status = get_day_status(planned, activities, calendar_date, today=local_today)
    rd, rs, od, os_, td, ts = split_day_distance_duration_by_sport(activities)
    
    return CalendarDayResponse(
        date=calendar_date,
        day_of_week=calendar_date.weekday(),
        day_name=get_day_name(calendar_date),
        planned_workout=PlannedWorkoutResponse.model_validate(planned) if planned else None,
        activities=[_activity_summary(a) for a in activities],
        status=status,
        notes=[CalendarNoteResponse.model_validate(n) for n in notes],
        insights=[InsightResponse.model_validate(i) for i in insights],
        total_distance_m=td,
        total_duration_s=ts,
        running_distance_m=rd,
        running_duration_s=rs,
        other_distance_m=od,
        other_duration_s=os_,
    )


@router.post("/{calendar_date}/notes", response_model=CalendarNoteResponse)
def add_calendar_note(
    calendar_date: date,
    note: CalendarNoteCreate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add a note to a calendar day.
    
    Note types:
    - pre_workout: Before the run (structured: sleep, energy, stress, weather)
    - post_workout: After the run (structured: feel, pain, fueling, mental)
    - free_text: General notes
    - voice_memo: Transcribed voice notes
    """
    db_note = CalendarNote(
        athlete_id=current_user.id,
        note_date=calendar_date,
        note_type=note.note_type,
        structured_data=note.structured_data,
        text_content=note.text_content,
        activity_id=note.activity_id
    )
    
    db.add(db_note)
    db.commit()
    db.refresh(db_note)
    
    return CalendarNoteResponse.model_validate(db_note)


@router.delete("/{calendar_date}/notes/{note_id}")
def delete_calendar_note(
    calendar_date: date,
    note_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a calendar note."""
    note = db.query(CalendarNote).filter(
        CalendarNote.id == note_id,
        CalendarNote.athlete_id == current_user.id
    ).first()
    
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    db.delete(note)
    db.commit()
    
    return {"status": "deleted"}


@router.get("/workouts/{workout_id}/variants", response_model=List[VariantOptionResponse])
def get_workout_variant_options(
    workout_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return the filtered list of valid variant alternatives for a planned workout.

    Filtering rules:
    1. Same stem as the workout's current type (threshold variants for threshold workouts, etc.)
    2. Must include the workout's build_context_tag (derived from phase)
    3. Contraindication text (when_to_avoid, pairs_poorly_with) surfaced to athlete for informed choice
    """
    workout = db.query(PlannedWorkout).filter(
        PlannedWorkout.id == workout_id,
        PlannedWorkout.athlete_id == current_user.id,
    ).first()
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    from services.plan_framework.variant_selector import _load_registry, _STEM_MAP

    stem = _STEM_MAP.get(workout.workout_type or "", "")
    if not stem:
        return []

    phase_to_tag = {
        "rebuild": "durability_rebuild",
        "base": "base_building",
        "build": "full_featured_healthy",
        "peak": "peak_fitness",
        "race": "race_specific",
        "taper": "minimal_sharpen",
        "recovery": "durability_rebuild",
    }
    build_tag = phase_to_tag.get(workout.phase or "", "full_featured_healthy")

    registry = _load_registry()
    options: List[VariantOptionResponse] = []
    for v in registry:
        if v.get("stem") != stem:
            continue
        if build_tag not in (v.get("build_context_tags") or []):
            continue
        options.append(VariantOptionResponse(
            id=v["id"],
            display_name=v.get("display_name", v["id"].replace("_", " ").title()),
            stem=v["stem"],
            when_to_avoid=v.get("when_to_avoid", ""),
            pairs_poorly_with=v.get("pairs_poorly_with", ""),
            is_current=(v["id"] == workout.workout_variant_id),
        ))

    return options


@router.patch("/workouts/{workout_id}/variant")
def select_workout_variant(
    workout_id: UUID,
    request: VariantSelectRequest,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Athlete selects a workout variant. Persists the choice and logs it.
    """
    workout = db.query(PlannedWorkout).filter(
        PlannedWorkout.id == workout_id,
        PlannedWorkout.athlete_id == current_user.id,
    ).first()
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    if workout.completed or workout.skipped:
        raise HTTPException(status_code=400, detail="Cannot change variant on a completed or skipped workout")

    from services.plan_framework.variant_selector import _load_registry, _STEM_MAP

    stem = _STEM_MAP.get(workout.workout_type or "", "")
    phase_to_tag = {
        "rebuild": "durability_rebuild",
        "base": "base_building",
        "build": "full_featured_healthy",
        "peak": "peak_fitness",
        "race": "race_specific",
        "taper": "minimal_sharpen",
        "recovery": "durability_rebuild",
    }
    build_tag = phase_to_tag.get(workout.phase or "", "full_featured_healthy")

    registry = _load_registry()
    valid_ids = {
        v["id"] for v in registry
        if v.get("stem") == stem and build_tag in (v.get("build_context_tags") or [])
    }
    if request.variant_id not in valid_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Variant '{request.variant_id}' is not eligible for workout type '{workout.workout_type}' in {workout.phase} phase",
        )

    old_variant = workout.workout_variant_id
    workout.workout_variant_id = request.variant_id
    db.commit()

    import logging
    logging.getLogger(__name__).info(
        "variant_selection: athlete=%s workout=%s old=%s new=%s",
        current_user.id, workout_id, old_variant, request.variant_id,
    )

    variant_entry = next((v for v in registry if v["id"] == request.variant_id), None)
    display_name = variant_entry.get("display_name", request.variant_id) if variant_entry else request.variant_id

    return {
        "status": "updated",
        "workout_id": str(workout_id),
        "variant_id": request.variant_id,
        "display_name": display_name,
    }


@router.post("/coach", response_model=CoachMessageResponse)
async def send_coach_message(
    request: CoachMessageRequest,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Send a message to the GPT coach.
    
    Context types:
    - day: Asking about a specific day's workout
    - week: Asking about the current/upcoming week
    - build: Asking about the overall training build
    - open: General question
    
    The coach receives full context injection based on context type.
    """
    # Get or create chat session
    if request.chat_id:
        chat = db.query(CoachChat).filter(
            CoachChat.id == request.chat_id,
            CoachChat.athlete_id == current_user.id
        ).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat session not found")
    else:
        chat = CoachChat(
            athlete_id=current_user.id,
            context_type=request.context_type,
            context_date=request.context_date,
            context_week=request.context_week,
            messages=[]
        )
        db.add(chat)
        db.commit()
        db.refresh(chat)
    
    # Add user message
    messages = chat.messages or []
    messages.append({
        "role": "user",
        "content": request.message,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # Snapshot context for audit/debug
    context_snapshot = _build_coach_context(
        db=db,
        athlete=current_user,
        context_type=request.context_type,
        context_date=request.context_date,
        context_week=request.context_week
    )

    # Route to the real AI Coach (same engine as /v1/coach)
    coach = AICoach(db)

    augmented_message = request.message
    day_context_tool = None
    if request.context_type == "day" and request.context_date:
        day_context_tool = coach_tools.get_calendar_day_context(
            db=db,
            athlete_id=current_user.id,
            day=request.context_date.isoformat(),
        )
        day_data = (day_context_tool.get("data") or {}) if isinstance(day_context_tool, dict) else {}
        if not day_context_tool or not day_context_tool.get("ok") or not day_data.get("date") or not day_data.get("weekday"):
            coach_response = (
                "I cannot answer this safely right now because the day context could not be verified. "
                "Please try again in a moment."
            )
            messages.append(
                {
                    "role": "coach",
                    "content": coach_response,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
            chat.messages = messages
            chat.context_snapshot = context_snapshot
            chat.updated_at = datetime.utcnow()
            db.commit()
            return CoachMessageResponse(
                chat_id=chat.id,
                response=coach_response,
                context_type=request.context_type,
            )

        first_activity = (day_data.get("activities") or [{}])[0]
        pace_vs_marathon = first_activity.get("pace_vs_marathon_label")
        marathon_pace = day_data.get("marathon_pace_per_mile") or day_data.get("marathon_pace_per_km")
        canonical_facts = [
            f"- Date: {day_data.get('date')}",
            f"- Weekday: {day_data.get('weekday')}",
        ]
        if marathon_pace:
            canonical_facts.append(f"- Marathon pace reference: {marathon_pace}")
        if pace_vs_marathon:
            canonical_facts.append(f"- Recorded pace vs marathon pace: {pace_vs_marathon}")

        augmented_message = (
            f"{request.message}\n\n"
            f"Context: calendar day {request.context_date.isoformat()}.\n"
            f"Before answering, call get_calendar_day_context(day='{request.context_date.isoformat()}') "
            f"and cite planned workout + activity IDs and values.\n\n"
            "AUTHORITATIVE FACT CAPSULE:\n"
            + "\n".join(canonical_facts)
            + "\n\nGround your answer in these facts. "
            + "Answer in natural coaching prose — no JSON, no capsule label reprinting, no markdown headers. "
            + "If the pace relation is present, use it directly in your response. "
            + "If evidence is partial or uncertain, name what is missing rather than refusing to answer."
        )
    elif request.context_type == "week" and request.context_week:
        augmented_message = (
            f"{request.message}\n\n"
            f"Context: plan week {request.context_week}.\n"
            f"Before answering, call get_plan_week and cite specific planned workout dates/titles."
        )

    result = await coach.chat(
        athlete_id=current_user.id,
        message=augmented_message,
        include_context=True,
        suppress_thread_storage=True,
    )

    coach_response = (result.get("response", "") or "").strip()
    if request.context_type == "day" and day_context_tool and day_context_tool.get("ok"):
        day_data = (day_context_tool.get("data") or {})
        if result.get("error") or not coach_response or coach_response.lower().startswith("coach is temporarily unavailable"):
            payload = _build_day_coach_contract_from_facts(day_data)
            coach_response = _format_day_coach_contract(payload)
        else:
            # Try the legacy JSON path first (V1 responses may still return JSON).
            payload = _extract_json_object(coach_response)
            if payload and _valid_day_coach_contract(payload):
                coach_response = _format_day_coach_contract(payload)
            else:
                # V2 returns natural prose — sanitize labels and use directly.
                sanitized = _sanitize_day_coach_text(coach_response)
                if sanitized and len(sanitized) > 80:
                    coach_response = sanitized
                else:
                    payload = _build_day_coach_contract_from_facts(day_data)
                    coach_response = _format_day_coach_contract(payload)
    else:
        if result.get("error") or not coach_response or coach_response.lower().startswith("coach is temporarily unavailable"):
            coach_response = (
                "I cannot answer this safely right now because coach context verification failed. "
                "Please retry in a moment."
            )
    
    # Add coach response
    messages.append({
        "role": "coach",
        "content": coach_response,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # Update chat
    chat.messages = messages
    chat.context_snapshot = context_snapshot
    chat.updated_at = datetime.utcnow()
    db.commit()
    
    return CoachMessageResponse(
        chat_id=chat.id,
        response=coach_response,
        context_type=request.context_type
    )


def _build_coach_context(
    db: Session,
    athlete: Athlete,
    context_type: str,
    context_date: Optional[date] = None,
    context_week: Optional[int] = None
) -> dict:
    """Build context for GPT coach based on context type."""
    context = {
        "athlete": {
            "display_name": athlete.display_name,
            "subscription_tier": athlete.subscription_tier,
            "rpi": athlete.rpi,
            "max_hr": athlete.max_hr,
            "threshold_pace_per_km": athlete.threshold_pace_per_km
        }
    }
    
    # Get active plan
    active_plan = get_active_plan_for_athlete(db, athlete.id)
    
    if active_plan:
        context["active_plan"] = {
            "name": active_plan.name,
            "goal_race_name": active_plan.goal_race_name,
            "goal_race_date": active_plan.goal_race_date.isoformat() if active_plan.goal_race_date else None,
            "goal_time_seconds": active_plan.goal_time_seconds,
            "total_weeks": active_plan.total_weeks
        }
    
    tz = get_athlete_timezone(athlete)

    if context_type == "day" and context_date:
        planned = None
        if active_plan:
            planned = db.query(PlannedWorkout).filter(
                PlannedWorkout.plan_id == active_plan.id,
                PlannedWorkout.scheduled_date == context_date
            ).first()
        
        day_start_utc, day_end_utc = local_day_bounds_utc(context_date, tz)
        activities = db.query(Activity).filter(
            Activity.athlete_id == athlete.id,
            Activity.is_duplicate == False,  # noqa: E712
            Activity.start_time >= day_start_utc,
            Activity.start_time < day_end_utc,
        ).all()
        
        context["day"] = {
            "date": context_date.isoformat(),
            "planned_workout": {
                "type": planned.workout_type,
                "title": planned.title,
                "description": planned.description,
                "target_distance_km": planned.target_distance_km,
                "segments": planned.segments,
                "workout_variant_id": planned.workout_variant_id,
            } if planned else None,
            "activities": [
                {
                    "distance_m": a.distance_m,
                    "duration_s": a.duration_s,
                    "avg_hr": a.avg_hr,
                    "workout_type": a.workout_type
                } for a in activities
            ]
        }
    
    # Get recent workouts for context
    recent = db.query(Activity).filter(
        Activity.athlete_id == athlete.id,
        Activity.is_duplicate == False,  # noqa: E712
    ).order_by(Activity.start_time.desc()).limit(7).all()
    
    context["recent_workouts"] = [
        {
            "date": to_activity_local_date(a, tz).isoformat(),
            "distance_m": a.distance_m,
            "workout_type": a.workout_type,
            "avg_hr": a.avg_hr
        } for a in recent
    ]
    
    return context


def _generate_coach_response(message: str, context: dict, history: list) -> str:
    """
    Generate coach response.
    
    TODO: Integrate with actual GPT API with proper prompt engineering.
    For now, returns a placeholder response.
    """
    # Placeholder - will be replaced with actual GPT integration
    if "ready" in message.lower():
        return "Based on your recent training, you're tracking well. Your consistency is building the foundation for a strong performance. Trust the work you've put in."
    
    if "pace" in message.lower():
        return "For your current fitness level, focus on effort over pace. Easy runs should feel conversational - if you can't talk, you're too fast. Save the speed for the quality sessions."
    
    if "tired" in message.lower() or "fatigue" in message.lower():
        return "Fatigue is expected during a build phase. The key question: is it productive fatigue (from training) or accumulated fatigue (needs attention)? How's your sleep been? Any unusual soreness?"
    
    return "I see your question about your training. Based on your recent workouts and current phase, let me help you think through this. What specific aspect would you like to explore further?"


@router.get("/week/{week_number}", response_model=WeekSummaryResponse)
def get_calendar_week(
    week_number: int,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed view of a specific training week."""
    # Get active plan
    active_plan = get_active_plan_for_athlete(db, current_user.id)
    
    if not active_plan:
        raise HTTPException(status_code=404, detail="No active training plan")
    
    # Get planned workouts for this week
    planned_workouts = db.query(PlannedWorkout).filter(
        PlannedWorkout.plan_id == active_plan.id,
        PlannedWorkout.week_number == week_number
    ).order_by(PlannedWorkout.scheduled_date).all()
    
    if not planned_workouts:
        raise HTTPException(status_code=404, detail=f"Week {week_number} not found in plan")
    
    tz = get_athlete_timezone(current_user)
    local_today = athlete_local_today(tz)

    # Get date range for the week
    start_date = min(w.scheduled_date for w in planned_workouts)
    end_date = max(w.scheduled_date for w in planned_workouts)
    
    # Query activities using athlete-local UTC bounds
    range_start_utc = local_day_bounds_utc(start_date, tz)[0]
    range_end_utc = local_day_bounds_utc(end_date, tz)[1]

    activities = db.query(Activity).filter(
        Activity.athlete_id == current_user.id,
        Activity.is_duplicate == False,  # noqa: E712
        Activity.start_time >= range_start_utc,
        Activity.start_time < range_end_utc,
    ).all()
    
    activities_by_date = {}
    for a in activities:
        d = to_activity_local_date(a, tz)
        if d not in activities_by_date:
            activities_by_date[d] = []
        activities_by_date[d].append(a)
    
    # Build day responses
    days = []
    for planned in planned_workouts:
        day_activities = dedupe_activities_for_calendar_display(
            activities_by_date.get(planned.scheduled_date, [])
        )
        status = get_day_status(planned, day_activities, planned.scheduled_date, today=local_today)
        
        rd, rs, od, os_, td, ts = split_day_distance_duration_by_sport(day_activities)
        
        days.append(CalendarDayResponse(
            date=planned.scheduled_date,
            day_of_week=planned.scheduled_date.weekday(),
            day_name=get_day_name(planned.scheduled_date),
            planned_workout=PlannedWorkoutResponse.model_validate(planned),
            activities=[_activity_summary(a) for a in day_activities],
            status=status,
            notes=[],
            insights=[],
            total_distance_m=td,
            total_duration_s=ts,
            running_distance_m=rd,
            running_duration_s=rs,
            other_distance_m=od,
            other_duration_s=os_,
        ))
    
    planned_m = sum(
        int((w.target_distance_km or 0) * 1000)
        for w in planned_workouts
    )
    completed_m = sum(
        d.running_distance_m for d in days
    )
    
    quality_types = ['threshold', 'intervals', 'tempo', 'long_mp', 'progression']
    quality_planned = sum(1 for w in planned_workouts if w.workout_type in quality_types)
    quality_completed = sum(
        1 for d in days
        if d.status == "completed" and d.planned_workout and d.planned_workout.workout_type in quality_types
    )
    
    phase = planned_workouts[0].phase if planned_workouts else None
    
    return WeekSummaryResponse(
        week_number=week_number,
        phase=phase,
        planned_m=planned_m,
        completed_m=completed_m,
        quality_sessions_planned=quality_planned,
        quality_sessions_completed=quality_completed,
        days=days
    )
