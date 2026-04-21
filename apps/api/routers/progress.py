"""
Progress API Router — ADR-17 Phase 3

Unified "Am I getting better?" endpoint.
Pulls from ALL coach tools: training load, recovery, efficiency, correlations,
race predictions, training paces, PB patterns, wellness trends, athlete profile,
consistency, pace decay, volume trajectory — the full system.

New: GET /v1/progress/narrative — visual-first progress story (spec v1).
"""

import logging
import os
import json
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
from models import Athlete, Activity, DailyCheckin, CorrelationFinding, TrainingPlan, PerformanceEvent
from services.intelligence.narration_tiers import (
    evidence_phrase as _pf_evidence_phrase,
    tier_for as _pf_tier_for,
)
from services.n1_insight_generator import friendly_signal_name
from services.timezone_utils import get_athlete_timezone, get_athlete_timezone_from_db, athlete_local_today
from routers.auth import get_current_user
from core.cache import get_cache, set_cache as _set_cache

# Module-level so tests can patch routers.progress.anthropic
try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment]

# Module-level Gemini client for narrative synthesis
try:
    from google import genai as _genai_module
    _gemini_api_key = os.getenv("GOOGLE_AI_API_KEY")
    gemini_client = _genai_module.Client(api_key=_gemini_api_key) if _gemini_api_key else None
except Exception:
    gemini_client = None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/progress", tags=["progress"])


# ═══════════════════════════════════════════════════════════════════
# Progress Narrative Response Models (Spec V1)
# ═══════════════════════════════════════════════════════════════════

class VerdictResponse(BaseModel):
    sparkline_data: List[float] = Field(default_factory=list)
    sparkline_direction: str = "stable"
    current_value: float = 0.0
    text: str = ""
    grounding: List[str] = Field(default_factory=list)
    confidence: str = "low"


class ChapterVisualData(BaseModel):
    labels: Optional[List[str]] = None
    values: Optional[List[float]] = None
    highlight_index: Optional[int] = None
    unit: Optional[str] = None
    current: Optional[float] = None
    average: Optional[float] = None
    direction: Optional[str] = None
    indicators: Optional[List[Dict[str, Any]]] = None
    value: Optional[float] = None
    zone_label: Optional[str] = None
    pct: Optional[float] = None
    distance: Optional[str] = None
    time: Optional[str] = None
    date_achieved: Optional[str] = None


class ChapterResponse(BaseModel):
    title: str
    topic: str
    visual_type: str
    visual_data: Dict[str, Any] = Field(default_factory=dict)
    observation: str = ""
    evidence: str = ""
    interpretation: str = ""
    action: str = ""
    relevance_score: float = 0.5


class PatternVisualData(BaseModel):
    input_series: List[float] = Field(default_factory=list)
    output_series: List[float] = Field(default_factory=list)
    input_label: str = ""
    output_label: str = ""


class PersonalPatternResponse(BaseModel):
    narrative: str = ""
    input_metric: str = ""
    output_metric: str = ""
    visual_type: str = "paired_sparkline"
    visual_data: Dict[str, Any] = Field(default_factory=dict)
    times_confirmed: int = 0
    current_relevance: str = ""
    confidence: str = "emerging"


class PatternsFormingResponse(BaseModel):
    checkin_count: int = 0
    checkins_needed: int = 14
    progress_pct: float = 0.0
    message: str = ""


class RaceScenario(BaseModel):
    label: str
    narrative: str = ""
    estimated_finish: Optional[str] = None
    key_action: Optional[str] = None


class RaceAhead(BaseModel):
    race_name: str = ""
    days_remaining: int = 0
    readiness_score: float = 0.0
    readiness_label: str = ""
    gauge_zones: List[str] = Field(default_factory=lambda: ["building", "ready", "peaked", "over-tapered"])
    scenarios: List[RaceScenario] = Field(default_factory=list)
    training_phase: str = ""


class TrajectoryCapability(BaseModel):
    distance: str
    current: Optional[str] = None
    previous: Optional[str] = None
    confidence: str = "low"


class TrajectoryAhead(BaseModel):
    capabilities: List[TrajectoryCapability] = Field(default_factory=list)
    narrative: str = ""
    trend_driver: str = ""
    milestone_hint: Optional[str] = None


class LookingAheadResponse(BaseModel):
    variant: str = "trajectory"
    race: Optional[RaceAhead] = None
    trajectory: Optional[TrajectoryAhead] = None


class AthleteControlsResponse(BaseModel):
    feedback_options: List[str] = Field(default_factory=lambda: ["This feels right", "Something's off", "Ask Coach"])
    coach_query: str = "Walk me through my progress report in detail"


class DataCoverageResponse(BaseModel):
    activity_days: int = 0
    checkin_days: int = 0
    garmin_days: int = 0
    correlation_findings: int = 0


class ProgressNarrativeResponse(BaseModel):
    verdict: VerdictResponse = Field(default_factory=VerdictResponse)
    chapters: List[ChapterResponse] = Field(default_factory=list)
    personal_patterns: List[PersonalPatternResponse] = Field(default_factory=list)
    patterns_forming: Optional[PatternsFormingResponse] = None
    looking_ahead: LookingAheadResponse = Field(default_factory=LookingAheadResponse)
    athlete_controls: AthleteControlsResponse = Field(default_factory=AthleteControlsResponse)
    generated_at: str = ""
    data_coverage: DataCoverageResponse = Field(default_factory=DataCoverageResponse)


class NarrativeFeedbackRequest(BaseModel):
    feedback_type: str
    feedback_detail: Optional[str] = None


# --- Response Models ---

class PeriodMetrics(BaseModel):
    run_count: int = 0
    total_distance_mi: float = 0
    total_duration_hr: float = 0
    avg_hr: Optional[float] = None


class PeriodComparison(BaseModel):
    current: PeriodMetrics
    previous: PeriodMetrics
    volume_change_pct: Optional[float] = None
    run_count_change: int = 0
    hr_change: Optional[float] = None


class ProgressHeadline(BaseModel):
    text: str
    subtext: Optional[str] = None


class ProgressCoachCard(BaseModel):
    id: str
    title: str
    summary: str
    trend_context: str
    drivers: str
    next_step: str
    ask_coach_query: str


def _looks_like_action(text: Optional[str]) -> bool:
    if not text:
        return False
    lower = text.lower()
    action_tokens = (
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
    return any(t in lower for t in action_tokens)


def _valid_progress_card_contract(card: ProgressCoachCard) -> bool:
    if not card.summary or not card.trend_context or not card.next_step:
        return False
    if not _looks_like_action(card.next_step):
        return False
    forbidden = ("recorded pace vs marathon pace", "authoritative fact capsule", "response contract")
    lower_blob = f"{card.summary} {card.trend_context} {card.drivers} {card.next_step}".lower()
    if any(f in lower_blob for f in forbidden):
        return False
    return True


class RecoveryData(BaseModel):
    durability_index: Optional[float] = None
    recovery_half_life_hours: Optional[float] = None
    injury_risk_score: Optional[float] = None
    false_fitness: bool = False
    masked_fatigue: bool = False
    status: Optional[str] = None


class RacePrediction(BaseModel):
    distance: str
    predicted_time: Optional[str] = None
    confidence: Optional[str] = None


class TrainingPaces(BaseModel):
    rpi: Optional[float] = None
    easy: Optional[str] = None
    marathon: Optional[str] = None
    threshold: Optional[str] = None
    interval: Optional[str] = None
    repetition: Optional[str] = None


class RunnerProfile(BaseModel):
    runner_type: Optional[str] = None
    max_hr: Optional[int] = None
    rpi: Optional[float] = None
    training_paces: Optional[TrainingPaces] = None
    age: Optional[int] = None
    sex: Optional[str] = None


class WellnessTrends(BaseModel):
    avg_sleep: Optional[float] = None
    avg_readiness: Optional[float] = None
    avg_soreness: Optional[float] = None
    avg_stress: Optional[float] = None
    checkin_count: int = 0
    trend_direction: Optional[str] = None


class VolumeTrajectory(BaseModel):
    recent_weeks: Optional[List[Dict[str, Any]]] = None
    current_week_mi: Optional[float] = None
    peak_week_mi: Optional[float] = None
    trend_pct: Optional[float] = None


class ProgressSummary(BaseModel):
    headline: Optional[ProgressHeadline] = None
    coach_cards: Optional[List[ProgressCoachCard]] = None
    period_comparison: Optional[PeriodComparison] = None
    ctl: Optional[float] = None
    atl: Optional[float] = None
    tsb: Optional[float] = None
    ctl_trend: Optional[str] = None
    tsb_zone: Optional[str] = None
    efficiency_trend: Optional[str] = None
    efficiency_current: Optional[float] = None
    efficiency_average: Optional[float] = None
    efficiency_best: Optional[float] = None
    # New: everything the system knows
    recovery: Optional[RecoveryData] = None
    race_predictions: Optional[List[RacePrediction]] = None
    runner_profile: Optional[RunnerProfile] = None
    wellness: Optional[WellnessTrends] = None
    volume_trajectory: Optional[VolumeTrajectory] = None
    consistency_index: Optional[float] = None
    pb_count_last_90d: int = 0
    pb_patterns: Optional[Dict[str, Any]] = None
    goal_race_name: Optional[str] = None
    goal_race_date: Optional[str] = None
    goal_race_days_remaining: Optional[int] = None
    goal_time: Optional[str] = None


# --- Endpoints ---

@router.get("/summary")
async def get_progress_summary(
    days: int = Query(default=28, ge=7, le=180),
    db: Session = Depends(get_db),
    current_user: Athlete = Depends(get_current_user),
):
    """
    Unified progress summary using ALL coach tools.
    One call powers the entire Progress page.
    """
    athlete_id = current_user.id
    result = ProgressSummary()

    # --- Training Load ---
    try:
        from services.training_load import TrainingLoadCalculator
        calc = TrainingLoadCalculator(db)
        load = calc.calculate_training_load(athlete_id)
        if load and load.current_ctl >= 10:
            result.ctl = round(load.current_ctl, 1)
            result.atl = round(load.current_atl, 1)
            result.tsb = round(load.current_tsb, 1)
            result.ctl_trend = load.ctl_trend

            try:
                zone = calc.get_tsb_zone(athlete_id, load.current_tsb)
                if zone:
                    result.tsb_zone = zone.zone.value if hasattr(zone.zone, 'value') else str(zone.zone)
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Progress load failed: {e}")

    # Clean session after training load (athlete_calibrated_model may poison it)
    try:
        db.rollback()
    except Exception:
        pass

    # --- Efficiency Trend ---
    try:
        from services.efficiency_analytics import get_efficiency_trends
        trends = get_efficiency_trends(
            athlete_id=str(athlete_id),
            db=db,
            days=days,
            include_stability=False,
            include_load_response=False,
            include_annotations=False,
        )
        if trends and trends.get("summary"):
            s = trends["summary"]
            result.efficiency_trend = s.get("trend_direction")
            result.efficiency_current = s.get("current_efficiency")
            result.efficiency_average = s.get("average_efficiency")
            result.efficiency_best = s.get("best_efficiency")
    except Exception as e:
        logger.warning(f"Progress efficiency failed: {e}")

    # --- Period Comparison ---
    try:
        now = datetime.utcnow()
        end_current = now
        start_current = now - timedelta(days=days)
        end_previous = start_current
        start_previous = start_current - timedelta(days=days)

        def fetch_period(start, end):
            acts = db.query(Activity).filter(
                Activity.athlete_id == athlete_id,
                Activity.sport == "run",
                Activity.start_time >= start,
                Activity.start_time < end,
            ).all()
            total_m = sum(float(a.distance_m or 0) for a in acts)
            total_s = sum(float(a.duration_s or 0) for a in acts)
            hrs = [int(a.avg_hr) for a in acts if a.avg_hr is not None]
            return PeriodMetrics(
                run_count=len([a for a in acts if a.distance_m]),
                total_distance_mi=round(total_m / 1609.344, 1),
                total_duration_hr=round(total_s / 3600.0, 1),
                avg_hr=round(sum(hrs) / len(hrs), 1) if hrs else None,
            )

        current = fetch_period(start_current, end_current)
        previous = fetch_period(start_previous, end_previous)

        vol_change = None
        if previous.total_distance_mi > 0:
            vol_change = round(
                ((current.total_distance_mi - previous.total_distance_mi)
                 / previous.total_distance_mi) * 100, 1
            )

        hr_change = None
        if current.avg_hr and previous.avg_hr:
            hr_change = round(current.avg_hr - previous.avg_hr, 1)

        result.period_comparison = PeriodComparison(
            current=current,
            previous=previous,
            volume_change_pct=vol_change,
            run_count_change=current.run_count - previous.run_count,
            hr_change=hr_change,
        )
    except Exception as e:
        logger.warning(f"Progress period comparison failed: {e}")

    # --- Recovery & Durability ---
    try:
        from services.coach_tools import get_recovery_status
        recovery_data = get_recovery_status(db, athlete_id)
        if recovery_data.get("ok"):
            d = recovery_data["data"]
            result.recovery = RecoveryData(
                durability_index=d.get("durability_index"),
                recovery_half_life_hours=d.get("recovery_half_life_hours"),
                injury_risk_score=d.get("injury_risk_score"),
                false_fitness=bool(d.get("false_fitness")),
                masked_fatigue=bool(d.get("masked_fatigue")),
                status=d.get("status"),
            )
    except Exception as e:
        logger.warning(f"Progress recovery failed: {e}")

    # --- Race Predictions ---
    try:
        from services.coach_tools import get_race_predictions
        preds = get_race_predictions(db, athlete_id)
        if preds.get("ok"):
            pred_data = preds.get("data", {}).get("predictions", {})
            race_list = []
            for dist_name in ["5K", "10K", "Half Marathon", "Marathon"]:
                p = pred_data.get(dist_name, {})
                pred_info = p.get("prediction", {})
                if pred_info.get("time_formatted"):
                    race_list.append(RacePrediction(
                        distance=dist_name,
                        predicted_time=pred_info["time_formatted"],
                        confidence=pred_info.get("confidence"),
                    ))
            if race_list:
                result.race_predictions = race_list
    except Exception as e:
        logger.warning(f"Progress race predictions failed: {e}")

    # --- Training Paces / Runner Profile ---
    try:
        from services.coach_tools import get_training_paces, get_athlete_profile
        paces_data = get_training_paces(db, athlete_id)
        profile_data = get_athlete_profile(db, athlete_id)

        paces = None
        if paces_data.get("ok"):
            pd = paces_data["data"]
            pace_dict = pd.get("paces", {})
            paces = TrainingPaces(
                rpi=pd.get("rpi"),
                easy=pace_dict.get("easy"),
                marathon=pace_dict.get("marathon"),
                threshold=pace_dict.get("threshold"),
                interval=pace_dict.get("interval"),
                repetition=pace_dict.get("repetition"),
            )

        runner_type = None
        max_hr = None
        age = None
        sex = None
        rpi = paces.rpi if paces else None
        if profile_data.get("ok"):
            prof = profile_data["data"]
            runner_type = prof.get("runner_type")
            max_hr = prof.get("max_hr")
            age = prof.get("age")
            sex = prof.get("sex")
            if not rpi:
                rpi = prof.get("rpi")

        result.runner_profile = RunnerProfile(
            runner_type=runner_type,
            max_hr=max_hr,
            rpi=rpi,
            training_paces=paces,
            age=age,
            sex=sex,
        )
    except Exception as e:
        logger.warning(f"Progress runner profile failed: {e}")

    # --- Wellness Trends ---
    try:
        from services.coach_tools import get_wellness_trends
        wellness = get_wellness_trends(db, athlete_id, days=days)
        if wellness.get("ok"):
            wd = wellness["data"]
            result.wellness = WellnessTrends(
                avg_sleep=wd.get("avg_sleep"),
                avg_readiness=wd.get("avg_readiness"),
                avg_soreness=wd.get("avg_soreness"),
                avg_stress=wd.get("avg_stress"),
                checkin_count=wd.get("checkin_count", 0),
                trend_direction=wd.get("trend_direction"),
            )
    except Exception as e:
        logger.warning(f"Progress wellness failed: {e}")

    # --- Volume Trajectory ---
    try:
        from services.coach_tools import get_weekly_volume
        weekly = get_weekly_volume(db, athlete_id, weeks=8)
        if weekly.get("ok"):
            weeks_data = weekly.get("data", {}).get("weeks_data",
                         weekly.get("data", {}).get("weeks", []))
            if weeks_data:
                completed = []
                current_mi = None
                for w in weeks_data:
                    dist = w.get("total_distance_mi", 0)
                    if w.get("is_current_week"):
                        current_mi = round(dist, 1)
                    else:
                        completed.append({
                            "week_start": w.get("week_start", ""),
                            "miles": round(dist, 1),
                            "runs": w.get("run_count", 0),
                        })

                peak = max((c["miles"] for c in completed), default=0) if completed else 0
                trend_pct = None
                if len(completed) >= 2 and completed[0]["miles"] > 0:
                    trend_pct = round(
                        ((completed[-1]["miles"] - completed[0]["miles"]) / completed[0]["miles"]) * 100, 1
                    )

                result.volume_trajectory = VolumeTrajectory(
                    recent_weeks=completed[-6:],
                    current_week_mi=current_mi,
                    peak_week_mi=round(peak, 1) if peak else None,
                    trend_pct=trend_pct,
                )
    except Exception as e:
        logger.warning(f"Progress volume trajectory failed: {e}")

    # --- Consistency Index ---
    try:
        from services.recovery_metrics import calculate_consistency_index
        ci = calculate_consistency_index(db, str(athlete_id), days=90)
        if ci is not None:
            result.consistency_index = round(ci, 1)
    except Exception as e:
        logger.warning(f"Progress consistency failed: {e}")

    # --- PB Patterns ---
    try:
        from services.coach_tools import get_pb_patterns
        pb_data = get_pb_patterns(db, athlete_id)
        if pb_data.get("ok"):
            d = pb_data.get("data", {})
            pbs = d.get("pbs", [])
            result.pb_count_last_90d = len([
                p for p in pbs
                if p.get("date") and
                (datetime.utcnow() - datetime.fromisoformat(str(p["date"])[:10])).days <= 90
            ])
            if d.get("summary"):
                result.pb_patterns = d["summary"]
    except Exception as e:
        logger.warning(f"Progress PB patterns failed: {e}")

    # --- Goal Race Info ---
    try:
        from models import TrainingPlan
        plan = (
            db.query(TrainingPlan)
            .filter(TrainingPlan.athlete_id == athlete_id, TrainingPlan.status == "active")
            .first()
        )
        _tz = get_athlete_timezone_from_db(db, athlete_id)
        _lt = athlete_local_today(_tz)
        if plan and plan.goal_race_date and plan.goal_race_date >= _lt:
            result.goal_race_name = plan.goal_race_name or plan.name
            result.goal_race_date = plan.goal_race_date.isoformat()
            result.goal_race_days_remaining = (plan.goal_race_date - _lt).days
            if plan.goal_time_seconds:
                h = plan.goal_time_seconds // 3600
                m = (plan.goal_time_seconds % 3600) // 60
                s = plan.goal_time_seconds % 60
                result.goal_time = f"{h}:{m:02d}:{s:02d}"
    except Exception as e:
        logger.warning(f"Progress goal race failed: {e}")

    # P1-D: Consent gate — skip all LLM calls if athlete has not opted in.
    from services.consent import has_ai_consent as _progress_consent
    _ai_allowed = _progress_consent(athlete_id=athlete_id, db=db)

    if _ai_allowed:
        import asyncio
        # DB-prefetch phase — single thread, shared session (thread-safe)
        try:
            from services.coach_tools import build_athlete_brief as _build_brief
            _prefetched_brief = _build_brief(db, athlete_id)  # cached 15 min
        except Exception:
            _prefetched_brief = None
        _prefetched_checkin = _latest_checkin_context(db, str(athlete_id))

        # Parallel LLM phase — no DB access when pre-fetched data is provided
        try:
            _headline, _cards = await asyncio.gather(
                asyncio.to_thread(
                    _generate_progress_headline,
                    str(athlete_id), None, result, days,
                    prefetched_brief=_prefetched_brief,
                ),
                asyncio.to_thread(
                    _generate_progress_cards,
                    str(athlete_id), None, result, days,
                    prefetched_brief=_prefetched_brief,
                    prefetched_checkin=_prefetched_checkin,
                ),
            )
        except Exception as e:
            logger.warning(f"Progress LLM parallel gather failed: {e}")
            _headline, _cards = None, None

        result.headline = _headline
        result.coach_cards = _cards or _consent_required_fallback_cards()
    else:
        result.coach_cards = _consent_required_fallback_cards()

    return result


class TrainingPatternItem(BaseModel):
    text: str
    source: str = "n1"


class TrainingPatternsResponse(BaseModel):
    what_works: List[TrainingPatternItem] = []
    what_doesnt: List[TrainingPatternItem] = []
    injury_patterns: List[TrainingPatternItem] = []
    checkin_count: int = 0
    checkins_needed: int = 10


@router.get("/training-patterns", response_model=TrainingPatternsResponse)
def get_training_patterns(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Training pattern intelligence from activity data (no tier gate).

    Layer 1 of the dual-layer What's Working system:
    - Training patterns from InsightAggregator (available immediately, needs activities only)
    - Separate from correlation engine (which needs check-in data and produces Layer 2)
    """
    from services.insight_aggregator import InsightAggregator
    from models import DailyCheckin

    result = TrainingPatternsResponse()

    # Get check-in count for progress indicator
    try:
        result.checkin_count = (
            db.query(DailyCheckin)
            .filter(DailyCheckin.athlete_id == current_user.id)
            .count()
        )
    except Exception:
        pass

    # Get training patterns from InsightAggregator
    try:
        aggregator = InsightAggregator(db, current_user)
        intelligence = aggregator.get_athlete_intelligence()

        def _to_item(x) -> TrainingPatternItem:
            if isinstance(x, dict):
                return TrainingPatternItem(
                    text=str(x.get("text") or ""),
                    source=str(x.get("source") or "n1"),
                )
            return TrainingPatternItem(text=str(x), source="n1")

        result.what_works = [_to_item(w) for w in (intelligence.what_works or [])]
        result.what_doesnt = [_to_item(w) for w in (intelligence.what_doesnt or [])]
        result.injury_patterns = [_to_item(w) for w in (intelligence.injury_patterns or [])]
    except Exception as e:
        logger.warning(f"Training patterns failed: {e}")

    return result


def _generate_progress_headline(
    athlete_id: str = None,
    db: Session = None,
    summary: "ProgressSummary" = None,
    days: int = 90,
    athlete: "Athlete" = None,
    metrics: Dict = None,
    prefetched_brief: Optional[str] = None,
) -> Optional["ProgressHeadline"]:
    """
    Generate a coaching progress headline using the full athlete brief.

    Supports two calling conventions:
      Old (endpoint): _generate_progress_headline(str(athlete_id), db, summary, days)
      New (consent-gated): _generate_progress_headline(athlete=obj, metrics={}, db=db)
    """
    # P1-D: Consent gate — new-style call passes athlete object.
    if athlete is not None:
        from services.consent import has_ai_consent as _has_consent
        if not _has_consent(athlete_id=athlete.id, db=db):
            return None
        athlete_id = str(athlete.id)

    # Old-style callers pass athlete_id; no consent check (endpoint gates first).
    if athlete_id is None:
        return None
    import hashlib
    import json

    # Cache key based on all data
    cache_input = json.dumps({
        "ctl": summary.ctl, "tsb": summary.tsb,
        "ctl_trend": summary.ctl_trend,
        "eff_trend": summary.efficiency_trend,
        "recovery": summary.recovery.model_dump() if summary.recovery else None,
        "consistency": summary.consistency_index,
        "pbs_90d": summary.pb_count_last_90d,
        "pc": summary.period_comparison.model_dump() if summary.period_comparison else None,
    }, sort_keys=True, default=str)
    data_hash = hashlib.md5(cache_input.encode()).hexdigest()[:12]
    cache_key = f"progress_headline:{athlete_id}:{data_hash}"

    # Check Redis cache
    from core.cache import get_cache, set_cache as _set_cache
    _cached_headline = get_cache(cache_key)
    if _cached_headline is not None:
        return ProgressHeadline(**_cached_headline)

    # ADR-16: Use pre-fetched brief if provided (thread-safe path); else fetch via db.
    if prefetched_brief is not None:
        athlete_brief = prefetched_brief
    else:
        try:
            from services.coach_tools import build_athlete_brief
            athlete_brief = build_athlete_brief(db, UUID(athlete_id))
        except Exception as e:
            logger.warning(f"Failed to build athlete brief for progress headline: {e}")
            athlete_brief = "(Brief unavailable)"

    prompt = (
        "You are an elite running coach. Based on this athlete's full profile, "
        "write ONE headline about their overall progress trajectory — are they "
        "getting better, plateauing, or declining? Be direct, concrete, and coach-like.\n\n"
        "COACHING TONE RULES (non-negotiable):\n"
        "- State facts first, then implication. Let the data speak — no cheerleading, no praise.\n"
        "- Never quote raw metrics or numeric score readouts to the athlete.\n"
        "- Frame any concern as a forward-looking action.\n"
        "- Never use acronyms or jargon. Say 'fitness level' not 'CTL', 'fatigue' not 'ATL', 'form' not 'TSB'. No acronyms ever.\n"
        "- Use only provided evidence. Do not invent.\n\n"
        f"=== ATHLETE BRIEF ===\n{athlete_brief}\n"
    )

    try:
        from google import genai
        import os

        api_key = os.getenv("GOOGLE_AI_API_KEY")
        if not api_key:
            return None

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                max_output_tokens=2000,
                temperature=0.3,
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "text": {
                            "type": "STRING",
                            "description": "One coaching headline about overall progress. No raw metric readouts.",
                        },
                        "subtext": {
                            "type": "STRING",
                            "description": "One supporting sentence with context and action. No raw metric readouts.",
                        },
                    },
                    "required": ["text", "subtext"],
                },
            ),
        )

        data = json.loads(response.text)
        headline = ProgressHeadline(**data)
        _set_cache(cache_key, data, ttl=1800)
        return headline

    except Exception as e:
        logger.warning(f"Progress headline LLM failed: {type(e).__name__}: {e}")
        return None


def _latest_checkin_context(db: Session, athlete_id: str) -> Optional[Dict[str, str]]:
    """
    Return latest self-report labels so coach language can validate athlete perception.
    """
    try:
        athlete_uuid = UUID(athlete_id)
        latest = (
            db.query(DailyCheckin)
            .filter(DailyCheckin.athlete_id == athlete_uuid)
            .order_by(DailyCheckin.date.desc())
            .first()
        )
        if not latest:
            return None

        readiness_map = {5: "High", 4: "Good", 3: "Neutral", 2: "Low", 1: "Poor"}
        sleep_map = {8: "Great", 7: "OK", 6: "Fair", 5: "Poor"}
        soreness_map = {1: "None", 2: "Mild", 3: "Moderate", 4: "High", 5: "Severe"}

        return {
            "date": latest.date.isoformat() if latest.date else "",
            "readiness": readiness_map.get(int(latest.readiness_1_5 or 0), "Unknown"),
            "sleep": sleep_map.get(int(latest.sleep_h or 0), "Unknown"),
            "soreness": soreness_map.get(int(latest.soreness_1_5 or 0), "Unknown"),
        }
    except Exception as e:
        logger.debug(f"Progress check-in context lookup failed: {e}")
        return None


def _fallback_progress_cards(
    summary: ProgressSummary,
    checkin: Optional[Dict[str, str]],
    days: int,
) -> List[ProgressCoachCard]:
    """Deterministic fallback card narratives when LLM or key is unavailable."""
    trend = (summary.efficiency_trend or "").lower()
    momentum_summary = (
        "Your running economy trend is moving in a productive direction."
        if trend == "improving"
        else "Your fitness signal looks stable, and consistency is keeping momentum alive."
        if trend == "stable"
        else "You still have useful momentum, and this is a good moment to sharpen execution."
    )
    momentum_next = (
        "Keep stacking mostly controlled runs this week, then let one quality session carry the progression."
    )

    freshness_state = (summary.tsb_zone or "").replace("_", " ").lower()
    recovery_summary = (
        "You are absorbing work well, which is exactly what supports the next block."
        if "fresh" in freshness_state or "race" in freshness_state
        else "Your load is doing its job; protect recovery so gains can consolidate."
    )
    if checkin and checkin.get("motivation"):
        recovery_summary = (
            f"You reported feeling {checkin['motivation'].lower()}, and the best move is to preserve that momentum with smart recovery rhythm."
        )

    volume_summary = (
        "Your recent training rhythm is building the durability needed for long-term progress."
    )
    consistency_summary = (
        "Your habits are the main advantage right now; repeating the basics is paying off."
    )

    return [
        ProgressCoachCard(
            id="fitness_momentum",
            title="Fitness Momentum",
            summary=momentum_summary,
            trend_context="Your recent training arc points to progress when effort stays controlled.",
            drivers="Consistency and repeatable aerobic work are the main contributors.",
            next_step=momentum_next,
            ask_coach_query="What should I focus on this week to keep momentum building?",
        ),
        ProgressCoachCard(
            id="recovery_readiness",
            title="Recovery Readiness",
            summary=recovery_summary,
            trend_context="The goal is to stay responsive, not just work harder.",
            drivers="Training load and recovery habits are interacting in a manageable way.",
            next_step="Use easy days intentionally so harder sessions stay high quality.",
            ask_coach_query="How should I balance effort and recovery over the next few days?",
        ),
        ProgressCoachCard(
            id="volume_trajectory",
            title=f"Volume Pattern ({days}d)",
            summary=volume_summary,
            trend_context="You are creating repeatable volume instead of one-off spikes.",
            drivers="Regular run frequency is supporting aerobic durability.",
            next_step="Keep the weekly rhythm steady before adding any extra stress.",
            ask_coach_query="Where should my volume focus be next: frequency or long-run support?",
        ),
        ProgressCoachCard(
            id="consistency_signal",
            title="Consistency Signal",
            summary=consistency_summary,
            trend_context="When training rhythm stays stable, performance usually follows.",
            drivers="Showing up consistently is reducing performance volatility.",
            next_step="Protect your routine anchors: easy days, key session, and recovery habits.",
            ask_coach_query="What small habit would give me the biggest consistency gain right now?",
        ),
    ]


def _consent_required_fallback_cards() -> "List[ProgressCoachCard]":
    """Deterministic fallback cards shown when AI consent is not granted."""
    return [
        ProgressCoachCard(
            id="fitness_momentum",
            title="Fitness Momentum",
            summary="Enable AI insights to see personalized coaching analysis of your fitness trend.",
            trend_context="Your training data is ready. AI coaching requires your consent to process it.",
            drivers="",
            next_step="Go to Settings → AI Processing to enable personalized coaching insights.",
            ask_coach_query="",
        ),
        ProgressCoachCard(
            id="recovery_readiness",
            title="Recovery Readiness",
            summary="Enable AI insights to see how your recovery is tracking.",
            trend_context="Recovery analysis requires AI processing consent.",
            drivers="",
            next_step="Go to Settings → AI Processing to enable personalized coaching insights.",
            ask_coach_query="",
        ),
        ProgressCoachCard(
            id="volume_trajectory",
            title="Volume Pattern",
            summary="Enable AI insights to see your volume trajectory analysis.",
            trend_context="Volume coaching requires AI processing consent.",
            drivers="",
            next_step="Go to Settings → AI Processing to enable personalized coaching insights.",
            ask_coach_query="",
        ),
        ProgressCoachCard(
            id="consistency_signal",
            title="Consistency Signal",
            summary="Enable AI insights to see your consistency coaching signal.",
            trend_context="Consistency analysis requires AI processing consent.",
            drivers="",
            next_step="Go to Settings → AI Processing to enable personalized coaching insights.",
            ask_coach_query="",
        ),
    ]


def _generate_progress_cards(
    athlete_id: str = None,
    db: Session = None,
    summary: "ProgressSummary" = None,
    days: int = 90,
    athlete: "Athlete" = None,
    metrics: Dict = None,
    prefetched_brief: Optional[str] = None,
    prefetched_checkin: Optional[Dict] = None,
) -> "List[ProgressCoachCard]":
    """
    Generate coach-led progress cards that replace raw quick metrics.

    Supports two calling conventions:
      Old (endpoint): _generate_progress_cards(str(athlete_id), db, summary, days)
      New (consent-gated): _generate_progress_cards(athlete=obj, metrics={}, db=db)
    """
    # P1-D: Consent gate — new-style call passes athlete object.
    if athlete is not None:
        from services.consent import has_ai_consent as _has_consent
        if not _has_consent(athlete_id=athlete.id, db=db):
            return _consent_required_fallback_cards()
        athlete_id = str(athlete.id)
        if summary is None:
            return _consent_required_fallback_cards()
    import hashlib
    import json

    checkin_context = prefetched_checkin if prefetched_checkin is not None else _latest_checkin_context(db, athlete_id)
    cache_input = json.dumps(
        {
            "days": days,
            "headline": summary.headline.model_dump() if summary.headline else None,
            "period_comparison": summary.period_comparison.model_dump() if summary.period_comparison else None,
            "recovery": summary.recovery.model_dump() if summary.recovery else None,
            "volume_trajectory": summary.volume_trajectory.model_dump() if summary.volume_trajectory else None,
            "consistency_index": summary.consistency_index,
            "efficiency_trend": summary.efficiency_trend,
            "ctl_trend": summary.ctl_trend,
            "tsb_zone": summary.tsb_zone,
            "checkin": checkin_context,
        },
        sort_keys=True,
        default=str,
    )
    data_hash = hashlib.md5(cache_input.encode()).hexdigest()[:12]
    cache_key = f"progress_coach_cards:{athlete_id}:{data_hash}"

    from core.cache import get_cache as _get_cache_cards, set_cache as _set_cache_cards
    _cached_cards = _get_cache_cards(cache_key)
    if _cached_cards is not None:
        return [ProgressCoachCard(**card) for card in _cached_cards.get("cards", [])]

    # Use pre-fetched brief if provided (thread-safe path); else fetch via db.
    if prefetched_brief is not None:
        athlete_brief = prefetched_brief
    else:
        try:
            from services.coach_tools import build_athlete_brief
            athlete_brief = build_athlete_brief(db, UUID(athlete_id))
        except Exception as e:
            logger.warning(f"Failed to build athlete brief for progress cards: {e}")
            athlete_brief = "(Brief unavailable)"

    prompt_parts = [
        "You are an elite running coach creating the 4 top cards for an athlete's Progress page.",
        "This must feel like coaching, not a dashboard.",
        "Return card language that is specific, evidence-based, and actionable.",
        "",
        "CRITICAL SAFETY / TONE RULES (non-negotiable):",
        "- State facts first, then implication. Let the data speak — no cheerleading, no praise.",
        "- NEVER quote raw metrics or values (no CTL/ATL/TSB numbers, no percentages, no score readouts).",
        "- NEVER contradict how the athlete says they feel.",
        "- Frame concerns as forward-looking actions.",
        "- NEVER use acronyms or jargon. Say 'fitness level' not 'CTL', 'fatigue' not 'ATL', 'form' not 'TSB'. No acronyms ever.",
        "- Use only facts from provided context. Do not invent.",
        "",
        "OUTPUT REQUIREMENTS:",
        "- Return EXACTLY 4 cards with ids:",
        "  1) fitness_momentum",
        "  2) recovery_readiness",
        f"  3) volume_trajectory (reflect last {days} days context)",
        "  4) consistency_signal",
        "- 1-2 sentences per field max. Keep concise and coach-like.",
        "- ENFORCE A->I->A SHAPE PER CARD:",
        "  - summary = Assessment (interpretive; not just raw numbers).",
        "  - trend_context = Implication (why this matters now).",
        "  - next_step = Action (concrete next step).",
        "- Never output internal labels or schema language.",
        "",
        "=== LATEST SELF-REPORT ===",
        json.dumps(checkin_context or {"status": "No recent check-in available"}, ensure_ascii=True),
        "",
        "=== PROGRESS SUMMARY (INTERNAL - translate, never quote raw values) ===",
        json.dumps(
            {
                "headline": summary.headline.model_dump() if summary.headline else None,
                "period_comparison": summary.period_comparison.model_dump() if summary.period_comparison else None,
                "recovery": summary.recovery.model_dump() if summary.recovery else None,
                "wellness": summary.wellness.model_dump() if summary.wellness else None,
                "volume_trajectory": summary.volume_trajectory.model_dump() if summary.volume_trajectory else None,
                "consistency_index": summary.consistency_index,
                "goal_race_name": summary.goal_race_name,
                "goal_race_days_remaining": summary.goal_race_days_remaining,
                "pb_count_last_90d": summary.pb_count_last_90d,
                "efficiency_trend": summary.efficiency_trend,
                "ctl_trend": summary.ctl_trend,
                "tsb_zone": summary.tsb_zone,
            },
            ensure_ascii=True,
            default=str,
        ),
        "",
        "=== ATHLETE BRIEF ===",
        athlete_brief,
    ]
    prompt = "\n".join(prompt_parts)

    try:
        import os
        from google import genai

        api_key = os.getenv("GOOGLE_AI_API_KEY")
        if not api_key:
            return _fallback_progress_cards(summary, checkin_context, days)

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                max_output_tokens=2200,
                temperature=0.25,
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "cards": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "id": {"type": "STRING"},
                                    "title": {"type": "STRING"},
                                    "summary": {"type": "STRING"},
                                    "trend_context": {"type": "STRING"},
                                    "drivers": {"type": "STRING"},
                                    "next_step": {"type": "STRING"},
                                    "ask_coach_query": {"type": "STRING"},
                                },
                                "required": [
                                    "id",
                                    "title",
                                    "summary",
                                    "trend_context",
                                    "drivers",
                                    "next_step",
                                    "ask_coach_query",
                                ],
                            },
                        }
                    },
                    "required": ["cards"],
                },
            ),
        )

        data = json.loads(response.text)
        cards = [ProgressCoachCard(**card) for card in data.get("cards", [])]
        if not cards:
            return _fallback_progress_cards(summary, checkin_context, days)
        if not all(_valid_progress_card_contract(c) for c in cards):
            logger.warning("Progress coach cards failed A->I->A contract validation; using fallback cards.")
            return _fallback_progress_cards(summary, checkin_context, days)

        _set_cache_cards(cache_key, {"cards": [c.model_dump() for c in cards]}, ttl=1800)
        return cards
    except Exception as e:
        logger.warning(f"Progress coach cards LLM failed: {type(e).__name__}: {e}")
        return _fallback_progress_cards(summary, checkin_context, days)


# ═══════════════════════════════════════════════════════════════════
# Progress Narrative — Visual-first progress story (Spec V1)
# ═══════════════════════════════════════════════════════════════════

def _assemble_verdict_data(db: Session, athlete_id: UUID) -> VerdictResponse:
    """Phase 1: Assemble the verdict sparkline from CTL history."""
    try:
        from services.training_load import TrainingLoadCalculator
        calc = TrainingLoadCalculator(db)
        history = calc.get_load_history(athlete_id, days=60)

        if not history or len(history) < 7:
            return VerdictResponse(
                text="Not enough data yet to show a trend.",
                confidence="low",
            )

        # Extract weekly CTL values (last 8 weeks)
        weekly_ctl: List[float] = []
        for i in range(0, len(history), 7):
            chunk = history[i:i + 7]
            if chunk:
                weekly_ctl.append(round(chunk[-1].ctl, 1))
        weekly_ctl = weekly_ctl[-8:] if len(weekly_ctl) > 8 else weekly_ctl

        current_ctl = weekly_ctl[-1] if weekly_ctl else 0.0

        # Determine direction
        if len(weekly_ctl) >= 2:
            first_half = weekly_ctl[:len(weekly_ctl) // 2]
            second_half = weekly_ctl[len(weekly_ctl) // 2:]
            avg_first = sum(first_half) / len(first_half) if first_half else 0
            avg_second = sum(second_half) / len(second_half) if second_half else 0
            change_pct = ((avg_second - avg_first) / avg_first * 100) if avg_first > 0 else 0
            if change_pct > 5:
                direction = "rising"
            elif change_pct < -5:
                direction = "declining"
            else:
                direction = "stable"
        else:
            direction = "stable"

        load = calc.calculate_training_load(athlete_id)
        grounding = [f"Fitness level {current_ctl}"]
        if load:
            grounding.append(f"Form {load.current_tsb:+.1f}")

        confidence = "high" if len(history) >= 42 else "moderate" if len(history) >= 21 else "low"

        fallback_text = f"{direction.capitalize()} fitness trend over {len(weekly_ctl)} weeks."

        return VerdictResponse(
            sparkline_data=weekly_ctl,
            sparkline_direction=direction,
            current_value=current_ctl,
            text=fallback_text,
            grounding=grounding,
            confidence=confidence,
        )
    except Exception as e:
        logger.warning(f"Narrative verdict assembly failed: {e}")
        return VerdictResponse(text="Insufficient data for fitness trend.", confidence="low")


def _assemble_chapters_data(db: Session, athlete_id: UUID) -> List[ChapterResponse]:
    """Phase 1: Assemble deterministic visual data for progress chapters."""
    chapters: List[ChapterResponse] = []

    # --- Volume Trajectory ---
    try:
        from services.coach_tools import get_weekly_volume
        weekly = get_weekly_volume(db, athlete_id, weeks=8)
        if weekly.get("ok"):
            weeks_data = weekly.get("data", {}).get("weeks_data",
                         weekly.get("data", {}).get("weeks", []))
            if weeks_data:
                labels = []
                values = []
                for w in weeks_data:
                    labels.append(w.get("week_start", "")[-5:])
                    values.append(round(w.get("total_distance_mi", 0), 1))

                current_mi = values[-1] if values else 0
                avg_4wk = sum(values[-4:]) / len(values[-4:]) if len(values) >= 4 else current_mi
                trend_pct = round(((current_mi - avg_4wk) / avg_4wk * 100), 1) if avg_4wk > 0 else 0

                chapters.append(ChapterResponse(
                    title="Volume Trajectory",
                    topic="volume_trajectory",
                    visual_type="bar_chart",
                    visual_data={
                        "labels": labels,
                        "values": values,
                        "highlight_index": len(values) - 1,
                        "unit": "mi",
                    },
                    observation=f"Weekly volume: {current_mi}mi this week. {trend_pct:+.0f}% vs 4-week average.",
                    evidence=f"{current_mi}mi this week | Avg: {avg_4wk:.1f}mi | Trend: {trend_pct:+.1f}%",
                    relevance_score=0.85,
                ))
    except Exception as e:
        logger.warning(f"Narrative volume chapter failed: {e}")

    # --- Efficiency Trend ---
    try:
        from services.efficiency_analytics import get_efficiency_trends
        trends = get_efficiency_trends(
            athlete_id=str(athlete_id), db=db, days=90,
            include_stability=False, include_load_response=False, include_annotations=False,
        )
        if trends and trends.get("summary") and trends.get("time_series"):
            summary = trends["summary"]
            ts = trends["time_series"]
            ef_values = [p["efficiency_factor"] for p in ts[-14:] if p.get("efficiency_factor")]

            direction = summary.get("trend_direction", "stable")
            current_ef = summary.get("current_efficiency", 0)
            avg_ef = summary.get("average_efficiency", 0)

            chapters.append(ChapterResponse(
                title="Efficiency Trend",
                topic="efficiency_trend",
                visual_type="sparkline",
                visual_data={
                    "values": [round(v, 4) for v in ef_values],
                    "current": round(current_ef, 4),
                    "average": round(avg_ef, 4),
                    "direction": direction,
                },
                observation=f"Efficiency {direction} over 90 days. Current: {current_ef:.4f}.",
                evidence=f"Current: {current_ef:.4f} | Avg: {avg_ef:.4f} | Direction: {direction}",
                relevance_score=0.80,
            ))
    except Exception as e:
        logger.warning(f"Narrative efficiency chapter failed: {e}")

    # --- Recovery / Health Strip ---
    try:
        from services.coach_tools import get_wellness_trends
        wellness = get_wellness_trends(db, athlete_id, days=14)
        if wellness.get("ok"):
            wd = wellness["data"]
            indicators = []
            avg_sleep = wd.get("avg_sleep") or wd.get("garmin_sleep_avg_h")
            avg_hrv = wd.get("avg_hrv") or wd.get("garmin_hrv_avg")
            avg_rhr = wd.get("avg_resting_hr") or wd.get("garmin_rhr_avg")
            avg_stress = wd.get("avg_stress") or wd.get("garmin_stress_avg")

            parts = []
            if avg_sleep is not None:
                indicators.append({"label": "Sleep", "value": f"{avg_sleep:.1f}h", "status": "green" if avg_sleep >= 7 else "amber" if avg_sleep >= 6 else "red"})
                parts.append(f"Sleep {avg_sleep:.1f}h avg")
            if avg_hrv is not None:
                indicators.append({"label": "HRV", "value": f"{avg_hrv:.0f}ms", "status": "green"})
                parts.append(f"HRV {avg_hrv:.0f}ms")
            if avg_rhr is not None:
                indicators.append({"label": "RHR", "value": f"{avg_rhr:.0f}bpm", "status": "green"})
                parts.append(f"RHR {avg_rhr:.0f}bpm")
            if avg_stress is not None:
                indicators.append({"label": "Stress", "value": f"{avg_stress:.0f}", "status": "green" if avg_stress <= 30 else "amber" if avg_stress <= 50 else "red"})

            if indicators:
                evidence_str = " | ".join(parts) if parts else "Recovery data available"
                chapters.append(ChapterResponse(
                    title="Recovery Signals",
                    topic="recovery_signals",
                    visual_type="health_strip",
                    visual_data={"indicators": indicators},
                    observation=evidence_str,
                    evidence=evidence_str,
                    relevance_score=0.75,
                ))
    except Exception as e:
        logger.warning(f"Narrative recovery chapter failed: {e}")

    # --- Training Load / Form Gauge ---
    try:
        from services.training_load import TrainingLoadCalculator
        calc = TrainingLoadCalculator(db)
        load = calc.calculate_training_load(athlete_id)
        if load and load.current_ctl >= 10:
            zone_info = calc.get_tsb_zone(load.current_tsb, athlete_id=athlete_id)
            zone_label = zone_info.label if zone_info else "Unknown"

            chapters.append(ChapterResponse(
                title="Training Load",
                topic="training_load",
                visual_type="gauge",
                visual_data={
                    "value": round(load.current_tsb, 1),
                    "zone_label": zone_label,
                    "zones": ["fatigued", "training", "fresh", "peaked"],
                },
                observation=f"Your form score is {load.current_tsb:+.1f}. Current zone: {zone_label}.",
                evidence=f"Form {load.current_tsb:+.1f} | Fitness {load.current_ctl:.1f} | Fatigue {load.current_atl:.1f}",
                relevance_score=0.70,
            ))
    except Exception as e:
        logger.warning(f"Narrative load chapter failed: {e}")

    # --- Consistency ---
    try:
        from services.recovery_metrics import calculate_consistency_index
        ci = calculate_consistency_index(db, str(athlete_id), days=90)
        if ci is not None:
            chapters.append(ChapterResponse(
                title="Consistency",
                topic="consistency",
                visual_type="completion_ring",
                visual_data={"pct": round(ci, 1)},
                observation=f"{ci:.0f}% of planned workouts completed.",
                evidence=f"Consistency index: {ci:.1f}%",
                relevance_score=0.65,
            ))
    except Exception as e:
        logger.warning(f"Narrative consistency chapter failed: {e}")

    # --- Personal Bests ---
    try:
        from models import PersonalBest
        recent_pbs = (
            db.query(PersonalBest)
            .filter(
                PersonalBest.athlete_id == athlete_id,
                PersonalBest.achieved_at >= datetime.utcnow() - timedelta(days=90),
            )
            .order_by(PersonalBest.achieved_at.desc())
            .limit(3)
            .all()
        )
        if recent_pbs:
            pb = recent_pbs[0]
            dist_label = (pb.distance_category or "").replace("_", " ").title()
            h = pb.time_seconds // 3600
            m = (pb.time_seconds % 3600) // 60
            s = pb.time_seconds % 60
            time_str = f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m}:{s:02d}"
            date_str = pb.achieved_at.strftime("%b %d") if pb.achieved_at else ""

            chapters.append(ChapterResponse(
                title="Personal Best",
                topic="personal_best",
                visual_type="stat_highlight",
                visual_data={
                    "distance": dist_label,
                    "time": time_str,
                    "date_achieved": date_str,
                },
                observation=f"New {dist_label} PB: {time_str} on {date_str}.",
                evidence=f"{dist_label}: {time_str} ({date_str})",
                relevance_score=0.90,
            ))
    except Exception as e:
        logger.warning(f"Narrative PB chapter failed: {e}")

    # Sort by relevance score descending
    chapters.sort(key=lambda c: c.relevance_score, reverse=True)
    return chapters[:4]


def _assemble_patterns_data(
    db: Session, athlete_id: UUID
) -> tuple[List[PersonalPatternResponse], Optional[PatternsFormingResponse]]:
    """Phase 1: Assemble N=1 correlation data for personal patterns."""
    patterns: List[PersonalPatternResponse] = []
    forming: Optional[PatternsFormingResponse] = None

    try:
        from models import CorrelationFinding
        from services.fingerprint_context import _SUPPRESSED_SIGNALS, _ENVIRONMENT_SIGNALS
        _suppressed = _SUPPRESSED_SIGNALS | _ENVIRONMENT_SIGNALS
        findings = (
            db.query(CorrelationFinding)
            .filter(
                CorrelationFinding.athlete_id == athlete_id,
                CorrelationFinding.is_active == True,  # noqa: E712
                CorrelationFinding.times_confirmed >= 1,
                ~CorrelationFinding.input_name.in_(_suppressed),
            )
            .order_by((CorrelationFinding.times_confirmed * CorrelationFinding.confidence).desc())
            .limit(2)
            .all()
        )

        for f in findings:
            tc = f.times_confirmed
            conf = _pf_tier_for(tc).lower()

            # Build deterministic fallback narrative
            fallback_narrative = (
                f"Pattern: {f.input_name} → {f.output_metric}. "
                f"{_pf_evidence_phrase(tc).capitalize()}."
            )

            patterns.append(PersonalPatternResponse(
                narrative=fallback_narrative,
                input_metric=f.input_name,
                output_metric=f.output_metric,
                visual_type="paired_sparkline",
                visual_data={
                    "input_series": [],
                    "output_series": [],
                    "input_label": friendly_signal_name(f.input_name).title(),
                    "output_label": friendly_signal_name(f.output_metric).title(),
                },
                times_confirmed=tc,
                current_relevance="",
                confidence=conf,
            ))

        if not findings:
            checkin_count = (
                db.query(DailyCheckin)
                .filter(DailyCheckin.athlete_id == athlete_id)
                .count()
            )
            needed = 14
            forming = PatternsFormingResponse(
                checkin_count=checkin_count,
                checkins_needed=needed,
                progress_pct=round(min(100, (checkin_count / needed) * 100), 1),
                message=f"Your personal patterns are forming. {checkin_count}/{needed} check-ins collected. Daily check-ins accelerate discovery.",
            )

    except Exception as e:
        logger.warning(f"Narrative patterns assembly failed: {e}")
        checkin_count = 0
        try:
            checkin_count = db.query(DailyCheckin).filter(DailyCheckin.athlete_id == athlete_id).count()
        except Exception:
            pass
        forming = PatternsFormingResponse(
            checkin_count=checkin_count,
            checkins_needed=14,
            progress_pct=round(min(100, (checkin_count / 14) * 100), 1),
            message=f"Your personal patterns are forming. {checkin_count}/14 check-ins collected.",
        )

    return patterns, forming


def _assemble_looking_ahead(db: Session, athlete_id: UUID) -> LookingAheadResponse:
    """Phase 1: Assemble Looking Ahead — race or trajectory variant."""
    try:
        from models import TrainingPlan
        plan = (
            db.query(TrainingPlan)
            .filter(TrainingPlan.athlete_id == athlete_id, TrainingPlan.status == "active")
            .first()
        )

        _tz = get_athlete_timezone_from_db(db, athlete_id)
        _lt = athlete_local_today(_tz)
        if plan and plan.goal_race_date and plan.goal_race_date >= _lt:
            days_remaining = (plan.goal_race_date - _lt).days
            race_name = plan.goal_race_name or plan.name or "Goal Race"

            # Get readiness score
            readiness_score = 50.0
            readiness_label = "Building"
            training_phase = "build"
            try:
                from services.training_load import TrainingLoadCalculator
                calc = TrainingLoadCalculator(db)
                readiness = calc.calculate_race_readiness(athlete_id)
                readiness_score = readiness.score
                training_phase = readiness.tsb_trend

                if readiness_score >= 80:
                    readiness_label = "Peaked"
                elif readiness_score >= 65:
                    readiness_label = "Ready"
                elif readiness_score >= 45:
                    readiness_label = "Building"
                else:
                    readiness_label = "Building"
            except Exception:
                pass

            # Build scenarios
            scenarios = [
                RaceScenario(
                    label="If current trend holds",
                    narrative=f"{race_name} in {days_remaining} days. Readiness: {readiness_score:.0f}%.",
                ),
            ]

            # Get estimated finish if predictions available
            try:
                from services.coach_tools import get_race_predictions
                preds = get_race_predictions(db, athlete_id)
                if preds.get("ok"):
                    pred_data = preds.get("data", {}).get("predictions", {})
                    # Match plan distance to prediction
                    for dist_name in ["Marathon", "Half Marathon", "10K", "5K"]:
                        p = pred_data.get(dist_name, {})
                        pred_info = p.get("prediction", {}) if isinstance(p, dict) else {}
                        if pred_info.get("time_formatted"):
                            scenarios[0].estimated_finish = pred_info["time_formatted"]
                            break
            except Exception:
                pass

            return LookingAheadResponse(
                variant="race",
                race=RaceAhead(
                    race_name=race_name,
                    days_remaining=days_remaining,
                    readiness_score=readiness_score,
                    readiness_label=readiness_label,
                    scenarios=scenarios,
                    training_phase=training_phase,
                ),
            )
        else:
            # Trajectory variant
            capabilities: List[TrajectoryCapability] = []
            try:
                from services.coach_tools import get_race_predictions
                preds = get_race_predictions(db, athlete_id)
                if preds.get("ok"):
                    pred_data = preds.get("data", {}).get("predictions", {})
                    for dist_name in ["5K", "10K", "Half Marathon", "Marathon"]:
                        p = pred_data.get(dist_name, {})
                        if not isinstance(p, dict):
                            continue
                        pred_info = p.get("prediction", {})
                        if pred_info.get("time_formatted"):
                            conf = pred_info.get("confidence", "low")
                            if isinstance(conf, str):
                                conf = "high" if conf.lower() in ("high", "race-anchored") else "moderate" if conf.lower() in ("moderate", "estimate") else "low"
                            capabilities.append(TrajectoryCapability(
                                distance=dist_name,
                                current=pred_info["time_formatted"],
                                confidence=conf,
                            ))
            except Exception:
                pass

            fallback_narrative = ""
            if capabilities:
                parts = [f"{c.distance}: {c.current}" for c in capabilities if c.current]
                fallback_narrative = "Current projections — " + " | ".join(parts) if parts else ""

            return LookingAheadResponse(
                variant="trajectory",
                trajectory=TrajectoryAhead(
                    capabilities=capabilities,
                    narrative=fallback_narrative,
                    trend_driver="",
                ),
            )

    except Exception as e:
        logger.warning(f"Narrative looking ahead failed: {e}")
        return LookingAheadResponse(
            variant="trajectory",
            trajectory=TrajectoryAhead(narrative="Insufficient data for projections."),
        )


def _assemble_data_coverage(db: Session, athlete_id: UUID) -> DataCoverageResponse:
    """Phase 1: Count available data sources."""
    coverage = DataCoverageResponse()
    cutoff = datetime.utcnow() - timedelta(days=90)

    try:
        coverage.activity_days = (
            db.query(Activity)
            .filter(Activity.athlete_id == athlete_id, Activity.start_time >= cutoff)
            .count()
        )
    except Exception:
        pass

    try:
        coverage.checkin_days = (
            db.query(DailyCheckin)
            .filter(DailyCheckin.athlete_id == athlete_id, DailyCheckin.date >= cutoff.date())
            .count()
        )
    except Exception:
        pass

    try:
        from models import GarminDay
        coverage.garmin_days = (
            db.query(GarminDay)
            .filter(GarminDay.athlete_id == athlete_id, GarminDay.calendar_date >= cutoff.date())
            .count()
        )
    except Exception:
        pass

    try:
        from models import CorrelationFinding
        coverage.correlation_findings = (
            db.query(CorrelationFinding)
            .filter(CorrelationFinding.athlete_id == athlete_id, CorrelationFinding.is_active.is_(True))
            .count()
        )
    except Exception:
        pass

    return coverage


def _generate_narrative_llm(visual_snapshot: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Phase 2: Call Gemini 2.5 Flash to synthesize narrative for each section.

    Returns a dict with narrative fields for verdict, chapters, patterns,
    looking_ahead. Returns None if LLM is unavailable or fails.
    """
    if gemini_client is None:
        return None

    prompt_parts = [
        "You are an elite running coach writing a progress narrative for one specific athlete.",
        "You are given their visual data snapshot. Write coaching narrative for each section.",
        "",
        "RULES (non-negotiable):",
        "- Interpretation leads, metrics follow. Coach voice first, numbers as evidence.",
        "- Every claim must be grounded in the provided data. No invention.",
        "- No raw metric readouts to open a sentence — interpret first.",
        "- No generic templates. Reference THIS athlete's specific data.",
        "- Max 3 sentences per section narrative.",
        "- N=1 patterns: use EXACT confidence language:",
        "  emerging (1-2 confirmations) = 'Early signal to watch'",
        "  confirmed (3-5) = 'In your data: becoming reliable'",
        "  strong (6+) = 'Your body consistently shows'",
        "- Emerging patterns NEVER use causal language.",
        "- Frame actions as athlete-controlled. The athlete decides.",
        "",
        "=== VISUAL DATA SNAPSHOT ===",
        json.dumps(visual_snapshot, default=str, ensure_ascii=True),
    ]
    prompt = "\n".join(prompt_parts)

    try:
        from google import genai

        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                max_output_tokens=3000,
                temperature=0.3,
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "verdict_text": {"type": "STRING"},
                        "chapters": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "topic": {"type": "STRING"},
                                    "observation": {"type": "STRING"},
                                    "interpretation": {"type": "STRING"},
                                    "action": {"type": "STRING"},
                                },
                                "required": ["topic", "observation", "interpretation", "action"],
                            },
                        },
                        "patterns": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "input_metric": {"type": "STRING"},
                                    "narrative": {"type": "STRING"},
                                    "current_relevance": {"type": "STRING"},
                                },
                                "required": ["input_metric", "narrative", "current_relevance"],
                            },
                        },
                        "looking_ahead_narrative": {"type": "STRING"},
                    },
                    "required": ["verdict_text", "chapters"],
                },
            ),
        )

        return json.loads(response.text)
    except Exception as e:
        logger.warning(f"Narrative LLM generation failed: {type(e).__name__}: {e}")
        return None


def _apply_llm_narratives(
    response: ProgressNarrativeResponse,
    llm_output: Dict[str, Any],
) -> None:
    """Merge LLM-generated narratives into the deterministic response."""
    # Verdict
    if llm_output.get("verdict_text"):
        response.verdict.text = llm_output["verdict_text"]

    # Chapters
    llm_chapters = {c["topic"]: c for c in llm_output.get("chapters", []) if c.get("topic")}
    for chapter in response.chapters:
        llm_ch = llm_chapters.get(chapter.topic)
        if llm_ch:
            if llm_ch.get("observation"):
                chapter.observation = llm_ch["observation"]
            if llm_ch.get("interpretation"):
                chapter.interpretation = llm_ch["interpretation"]
            if llm_ch.get("action"):
                chapter.action = llm_ch["action"]

    # Patterns
    llm_patterns = {p["input_metric"]: p for p in llm_output.get("patterns", []) if p.get("input_metric")}
    for pattern in response.personal_patterns:
        llm_p = llm_patterns.get(pattern.input_metric)
        if llm_p:
            # Validate N=1 confidence gating
            narrative = llm_p.get("narrative", "")
            causal_terms = ["causes", "makes you", "leads to", "results in", "because of"]
            if pattern.confidence == "emerging" and any(t in narrative.lower() for t in causal_terms):
                logger.warning(f"LLM violated confidence gating for emerging pattern {pattern.input_metric}; using fallback")
            else:
                if narrative:
                    pattern.narrative = narrative
            if llm_p.get("current_relevance"):
                pattern.current_relevance = llm_p["current_relevance"]

    # Looking ahead
    if llm_output.get("looking_ahead_narrative"):
        la = response.looking_ahead
        if la.variant == "race" and la.race and la.race.scenarios:
            la.race.scenarios[0].narrative = llm_output["looking_ahead_narrative"]
        elif la.variant == "trajectory" and la.trajectory:
            la.trajectory.narrative = llm_output["looking_ahead_narrative"]


@router.get("/narrative", response_model=ProgressNarrativeResponse)
async def get_progress_narrative(
    db: Session = Depends(get_db),
    current_user: Athlete = Depends(get_current_user),
):
    """
    Visual-first progress narrative. Single endpoint, single call.

    Phase 1: Deterministic visual data assembly (< 500ms target).
    Phase 2: LLM narrative synthesis (< 5s target).
    Cache: Redis 30min TTL. Fallback: visuals + deterministic labels.
    """
    athlete_id = current_user.id
    cache_key = f"progress_narrative:{athlete_id}"

    # Cache check
    cached = get_cache(cache_key)
    if cached is not None:
        return ProgressNarrativeResponse(**cached)

    # Phase 1: Deterministic data assembly
    verdict = _assemble_verdict_data(db, athlete_id)

    # Clean session after training load queries
    try:
        db.rollback()
    except Exception:
        pass

    chapters = _assemble_chapters_data(db, athlete_id)
    personal_patterns, patterns_forming = _assemble_patterns_data(db, athlete_id)
    looking_ahead = _assemble_looking_ahead(db, athlete_id)
    data_coverage = _assemble_data_coverage(db, athlete_id)

    response = ProgressNarrativeResponse(
        verdict=verdict,
        chapters=chapters,
        personal_patterns=personal_patterns,
        patterns_forming=patterns_forming,
        looking_ahead=looking_ahead,
        athlete_controls=AthleteControlsResponse(),
        generated_at=datetime.utcnow().isoformat() + "Z",
        data_coverage=data_coverage,
    )

    # Phase 2: LLM narrative synthesis
    from services.consent import has_ai_consent
    if has_ai_consent(athlete_id=athlete_id, db=db):
        visual_snapshot = {
            "verdict": verdict.model_dump(),
            "chapters": [c.model_dump() for c in chapters],
            "patterns": [p.model_dump() for p in personal_patterns],
            "looking_ahead": looking_ahead.model_dump(),
        }

        import asyncio
        try:
            llm_output = await asyncio.to_thread(_generate_narrative_llm, visual_snapshot)
            if llm_output:
                _apply_llm_narratives(response, llm_output)
        except Exception as e:
            logger.warning(f"Narrative LLM phase failed: {e}")

    # Suppress chapters without interpretation (spec rule)
    response.chapters = [
        c for c in response.chapters
        if c.observation or c.interpretation
    ]

    # Cache the full response
    _set_cache(cache_key, response.model_dump(), ttl=1800)

    return response


@router.post("/narrative/feedback")
def post_narrative_feedback(
    body: NarrativeFeedbackRequest,
    db: Session = Depends(get_db),
    current_user: Athlete = Depends(get_current_user),
):
    """Log athlete feedback on the progress narrative."""
    from models import NarrativeFeedback

    if body.feedback_type not in ("positive", "negative", "coach"):
        raise HTTPException(status_code=400, detail="feedback_type must be positive, negative, or coach")

    feedback = NarrativeFeedback(
        athlete_id=current_user.id,
        feedback_type=body.feedback_type,
        feedback_detail=body.feedback_detail,
    )
    db.add(feedback)
    db.commit()

    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════
# Progress Knowledge — Phase 1: Ship the Moat
# ═══════════════════════════════════════════════════════════════════

class CorrelationNode(BaseModel):
    id: str
    label: str
    group: str  # "input" or "output"

class CorrelationEdge(BaseModel):
    source: str
    target: str
    r: float
    direction: str  # "positive" or "negative"
    lag_days: int
    times_confirmed: int
    strength: str
    note: str

class ProvedFact(BaseModel):
    input_metric: str
    output_metric: str
    headline: str
    evidence: str
    implication: str
    times_confirmed: int
    confidence_tier: str  # "emerging", "confirmed", "strong"
    direction: str
    correlation_coefficient: float
    lag_days: int

class HeroStat(BaseModel):
    label: str
    value: str
    color: str

class HeroData(BaseModel):
    date_label: str
    headline: str
    headline_accent: str
    subtext: str
    stats: List[HeroStat]

class DataCoverageKnowledge(BaseModel):
    total_findings: int
    confirmed_findings: int
    emerging_findings: int
    checkin_count: int

class PatternsFormingKnowledge(BaseModel):
    checkin_count: int
    checkins_needed: int
    progress_pct: float
    message: str

class KnowledgeResponse(BaseModel):
    hero: HeroData
    correlation_web: Dict[str, Any]
    proved_facts: List[ProvedFact]
    patterns_forming: Optional[PatternsFormingKnowledge] = None
    recovery_curve: Optional[Dict[str, Any]] = None
    generated_at: str
    data_coverage: DataCoverageKnowledge


def _confidence_tier(times_confirmed: int) -> str:
    if times_confirmed >= 6:
        return "strong"
    elif times_confirmed >= 3:
        return "confirmed"
    return "emerging"


_METRIC_LABELS: dict = {
    "efficiency": "Efficiency",
    "pace_easy": "Easy Pace",
    "pace_threshold": "Threshold Pace",
    "completion": "Completion",
    "efficiency_threshold": "Threshold Efficiency",
    "efficiency_race": "Race Efficiency",
    "efficiency_easy": "Easy Efficiency",
    "efficiency_trend": "Efficiency Trend",
    "pb_events": "Personal Bests",
    "race_pace": "Race Pace",
    "readiness_1_5": "Morning Readiness",
    "enjoyment_1_5": "Enjoyment",
    "confidence_1_5": "Confidence",
    "stress_1_5": "Stress",
    "soreness_1_5": "Soreness",
    "rpe_1_10": "Effort (RPE)",
    "sleep_hours": "Sleep",
    "sleep_quality_1_5": "Sleep Quality",
    "hrv_rmssd": "Heart Rate Variability",
    "resting_hr": "Resting Heart Rate",
    "atl": "Fatigue",
    "ctl": "Fitness",
    "tsb": "Form",
    "daily_session_stress": "Session Stress",
    "weight_kg": "Weight",
}


def _humanize_metric(raw: str) -> str:
    """Athlete-friendly metric names. No raw acronyms."""
    if raw in _METRIC_LABELS:
        return _METRIC_LABELS[raw]
    cleaned = raw.replace("_1_5", "").replace("_1_10", "").replace("_", " ")
    return cleaned.title()


def _build_headline(finding: CorrelationFinding) -> str:
    inp = _humanize_metric(finding.input_name)
    out = _humanize_metric(finding.output_metric)
    verb = "improves" if finding.direction == "positive" else "reduces"
    lag = f"within {finding.time_lag_days} day{'s' if finding.time_lag_days != 1 else ''}" if finding.time_lag_days > 0 else "same day"
    return f"High {inp} {verb} {out} {lag}"


def _assemble_knowledge(athlete_id, db: Session) -> KnowledgeResponse:
    """Deterministic assembly of all Phase 1 knowledge data."""
    from services.training_load import TrainingLoadCalculator

    from services.fingerprint_context import _SUPPRESSED_SIGNALS, _ENVIRONMENT_SIGNALS
    _suppressed = _SUPPRESSED_SIGNALS | _ENVIRONMENT_SIGNALS
    findings = (
        db.query(CorrelationFinding)
        .filter(
            CorrelationFinding.athlete_id == athlete_id,
            CorrelationFinding.is_active.is_(True),
            CorrelationFinding.times_confirmed >= 1,
            ~CorrelationFinding.input_name.in_(_suppressed),
        )
        .order_by(
            (CorrelationFinding.times_confirmed * CorrelationFinding.confidence).desc()
        )
        .all()
    )

    # 2. Build nodes (deduplicate)
    input_names = list(dict.fromkeys(f.input_name for f in findings))
    output_names = list(dict.fromkeys(f.output_metric for f in findings))

    nodes = []
    for name in input_names:
        nodes.append(CorrelationNode(id=name, label=_humanize_metric(name), group="input"))
    for name in output_names:
        nodes.append(CorrelationNode(id=name, label=_humanize_metric(name), group="output"))

    # 3. Build edges
    edges = []
    for f in findings:
        edges.append(CorrelationEdge(
            source=f.input_name,
            target=f.output_metric,
            r=round(f.correlation_coefficient, 2),
            direction=f.direction,
            lag_days=f.time_lag_days,
            times_confirmed=f.times_confirmed,
            strength=f.strength,
            note=f.insight_text or f"Correlation between {_humanize_metric(f.input_name)} and {_humanize_metric(f.output_metric)}.",
        ))

    # 4. Build proved facts
    proved_facts = []
    for f in sorted(findings, key=lambda x: x.times_confirmed, reverse=True):
        proved_facts.append(ProvedFact(
            input_metric=f.input_name,
            output_metric=f.output_metric,
            headline=_build_headline(f),
            evidence=(
                f.insight_text
                or f"Pattern {_pf_evidence_phrase(f.times_confirmed)} (r={f.correlation_coefficient:.2f})."
            ),
            implication="",
            times_confirmed=f.times_confirmed,
            confidence_tier=_confidence_tier(f.times_confirmed),
            direction=f.direction,
            correlation_coefficient=round(f.correlation_coefficient, 2),
            lag_days=f.time_lag_days,
        ))

    # 5. Hero data
    calc = TrainingLoadCalculator(db)
    history = calc.get_load_history(athlete_id, days=90)

    ctl_first = round(history[0].ctl, 1) if history else 0
    ctl_now = round(history[-1].ctl, 1) if history else 0
    weeks_tracked = len(history) // 7 if history else 0

    plan = db.query(TrainingPlan).filter(
        TrainingPlan.athlete_id == athlete_id,
        TrainingPlan.status == "active",
    ).first()

    _tz = get_athlete_timezone_from_db(db, athlete_id)
    today = athlete_local_today(_tz)
    day_name = today.strftime("%A")
    date_str = today.strftime("%b %-d") if os.name != "nt" else today.strftime("%b %d").replace(" 0", " ")

    if plan and plan.goal_race_date:
        race_name = plan.goal_race_name or plan.name
        days_out = (plan.goal_race_date - today).days
        date_label = f"{day_name}, {date_str} · {race_name} in {days_out} days"
        stat_third = HeroStat(label="Days out", value=str(max(0, days_out)), color="orange")
    else:
        date_label = f"{day_name}, {date_str}"
        n_findings = len(findings) if findings else 0
        stat_third = HeroStat(label="Patterns found", value=str(n_findings), color="orange")

    # Build headline based on context
    ctl_delta = ctl_now - ctl_first if ctl_now and ctl_first else 0
    if plan and plan.goal_race_date:
        hero_headline = f"Your progress over {weeks_tracked} weeks."
        hero_accent = "Here's what the data shows."
    elif ctl_delta >= 10:
        hero_headline = f"Fitness surged: {ctl_first} to {ctl_now} in {weeks_tracked} weeks."
        hero_accent = "Your data reveals what drives your performance."
    elif findings:
        hero_headline = f"{weeks_tracked} weeks of data. {len(findings)} pattern{'s' if len(findings) != 1 else ''} discovered."
        hero_accent = "Your data reveals what drives your performance."
    else:
        hero_headline = "Building your physiological profile."
        hero_accent = "Every session teaches the system about your body."

    hero = HeroData(
        date_label=date_label,
        headline=hero_headline,
        headline_accent=hero_accent,
        subtext="Facts discovered from your own training data — confirmed across your own physiology, your own patterns.",
        stats=[
            HeroStat(label="Fitness then", value=str(ctl_first), color="muted"),
            HeroStat(label="Fitness now", value=str(ctl_now), color="blue"),
            stat_third,
        ],
    )

    # 6. Patterns forming fallback
    patterns_forming = None
    if not findings:
        checkin_count = db.query(DailyCheckin).filter(
            DailyCheckin.athlete_id == athlete_id
        ).count()
        needed = 14
        patterns_forming = PatternsFormingKnowledge(
            checkin_count=checkin_count,
            checkins_needed=needed,
            progress_pct=min(100.0, (checkin_count / needed) * 100),
            message="Keep doing your daily check-ins. The system needs about two weeks of data to discover how your body responds to training inputs.",
        )

    # 7. Data coverage
    confirmed_count = sum(1 for f in findings if f.times_confirmed >= 3)
    emerging_count = sum(1 for f in findings if f.times_confirmed < 3)

    checkin_total = db.query(DailyCheckin).filter(
        DailyCheckin.athlete_id == athlete_id
    ).count()

    data_coverage = DataCoverageKnowledge(
        total_findings=len(findings),
        confirmed_findings=confirmed_count,
        emerging_findings=emerging_count,
        checkin_count=checkin_total,
    )

    # Recovery curve
    try:
        from services.recovery_metrics import compute_recovery_curve
        rc = compute_recovery_curve(db, str(athlete_id))
    except Exception:
        rc = None

    return KnowledgeResponse(
        hero=hero,
        correlation_web={
            "nodes": [n.model_dump() for n in nodes],
            "edges": [e.model_dump() for e in edges],
        },
        proved_facts=proved_facts,
        patterns_forming=patterns_forming,
        recovery_curve=rc,
        generated_at=datetime.utcnow().isoformat() + "Z",
        data_coverage=data_coverage,
    )


def _generate_knowledge_llm(response: KnowledgeResponse, athlete_id) -> Optional[Dict]:
    """LLM pass: generate hero headline + per-finding implications."""
    if not gemini_client:
        return None

    try:
        from google import genai

        facts_summary = []
        for f in response.proved_facts[:8]:
            facts_summary.append(
                f"- {f.headline} (r={f.correlation_coefficient}, confirmed {f.times_confirmed}x, {f.confidence_tier})"
            )

        stats_text = ", ".join(f"{s.label}: {s.value}" for s in response.hero.stats)

        prompt = f"""You are a running coach writing for a progress page. The athlete's data:
{stats_text}

Confirmed patterns from their data:
{chr(10).join(facts_summary)}

Generate JSON with:
1. "headline": A short, powerful sentence about their training arc (max 8 words). No generic praise.
2. "headline_accent": A second line that reframes what follows (max 10 words). Must reference their specific data.
3. "subtext": One paragraph (2-3 sentences) framing what the page shows. Reference that these are facts from THEIR data, not population averages.
4. "implications": An object mapping each fact index (0, 1, 2...) to a one-sentence current implication. Connect the pattern to their current training state. If you can't say something specific and true, use empty string.

Rules:
- No generic motivational language
- No "Great job" or "Keep it up"
- Reference specific numbers from their data
- Every sentence must be grounded in the data provided
- Suppress over hallucinate — if uncertain, omit"""

        result = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                max_output_tokens=1500,
                temperature=0.3,
                response_mime_type="application/json",
            ),
        )
        return json.loads(result.text)
    except Exception as e:
        logger.warning(f"Knowledge LLM failed: {e}")
        return None


def _apply_knowledge_llm(response: KnowledgeResponse, llm_output: Dict):
    """Merge LLM-generated text into the deterministic response."""
    if "headline" in llm_output and llm_output["headline"]:
        response.hero.headline = llm_output["headline"]
    if "headline_accent" in llm_output and llm_output["headline_accent"]:
        response.hero.headline_accent = llm_output["headline_accent"]
    if "subtext" in llm_output and llm_output["subtext"]:
        response.hero.subtext = llm_output["subtext"]

    implications = llm_output.get("implications", {})
    for idx_str, text in implications.items():
        try:
            idx = int(idx_str)
            if 0 <= idx < len(response.proved_facts) and text:
                tier = response.proved_facts[idx].confidence_tier
                if tier == "emerging" and any(w in text.lower() for w in ["causes", "drives", "guarantees", "always"]):
                    continue
                response.proved_facts[idx].implication = text
        except (ValueError, IndexError):
            continue


@router.get("/knowledge", response_model=KnowledgeResponse)
async def get_progress_knowledge(
    db: Session = Depends(get_db),
    current_user: Athlete = Depends(get_current_user),
):
    """Phase 1 progress knowledge: correlation web, proved facts, hero."""
    import asyncio
    from services.consent import has_ai_consent

    athlete_id = current_user.id
    cache_key = f"progress_knowledge:{athlete_id}"

    cached = get_cache(cache_key)
    if cached is not None:
        return KnowledgeResponse(**cached)

    response = _assemble_knowledge(athlete_id, db)

    if has_ai_consent(athlete_id=athlete_id, db=db):
        llm_output = await asyncio.to_thread(_generate_knowledge_llm, response, athlete_id)
        if llm_output:
            _apply_knowledge_llm(response, llm_output)

    _set_cache(cache_key, response.model_dump(), ttl=1800)

    return response


# ═══════════════════════════════════════════════════════
#  Training Story endpoint
# ═══════════════════════════════════════════════════════


@router.get("/training-story")
def get_training_story(
    db: Session = Depends(get_db),
    current_user: Athlete = Depends(get_current_user),
):
    """Training story synthesis — race stories, progressions, connections.

    Reads from stored AthleteFinding (fast path, populated by post-sync
    and daily fingerprint refresh). Falls back to recompute if no stored
    findings exist yet.
    """
    from services.finding_persistence import get_active_findings
    from services.training_story_engine import synthesize_training_story
    from services.race_input_analysis import RaceInputFinding

    athlete_id = current_user.id

    cache_key = f"training_story:{athlete_id}"
    cached = get_cache(cache_key)
    if cached is not None:
        return cached

    stored = get_active_findings(athlete_id, db)
    honest_gaps = []

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
        findings, honest_gaps = mine_race_inputs(athlete_id, db)

    if not findings:
        return {"race_stories": [], "progressions": [], "connections": [],
                "campaign_narrative": None, "honest_gaps": honest_gaps, "finding_count": 0}

    events = db.query(PerformanceEvent).filter(
        PerformanceEvent.athlete_id == athlete_id,
        PerformanceEvent.user_confirmed.is_(True),
    ).order_by(PerformanceEvent.event_date).all()

    story = synthesize_training_story(findings, events)
    result = story.to_dict()
    result['honest_gaps'] = honest_gaps

    _set_cache(cache_key, result, ttl=3600)

    return result


# ═══════════════════════════════════════════════════════
#  Personal Operating Manual
# ═══════════════════════════════════════════════════════


@router.get("/manual")
def get_operating_manual(
    db: Session = Depends(get_db),
    current_user: Athlete = Depends(get_current_user),
):
    """Personal Operating Manual — everything the system has learned about this athlete.

    Assembles all confirmed correlation findings (with L1-L4 enrichment),
    investigation findings, and cascade chains into a domain-organized
    document. Deterministic — no LLM calls.

    Cached for 30 minutes (1800s). The manual is deterministic and only
    changes after daily sweep or post-sync processing.
    """
    from services.operating_manual import assemble_manual

    athlete_id = current_user.id
    cache_key = f"operating_manual:{athlete_id}"

    cached = get_cache(cache_key)
    if cached is not None:
        return cached

    result = assemble_manual(athlete_id, db)

    _set_cache(cache_key, result, ttl=1800)

    return result


@router.get("/first-insights")
def get_first_insights_endpoint(
    db: Session = Depends(get_db),
    current_user: Athlete = Depends(get_current_user),
):
    """First-session insights — the aha moment.

    Returns the top findings from the athlete's imported history.
    Returns {"ready": false} if insufficient data exists yet.

    Cache strategy: ready=false caches for 15s (matches frontend poll
    interval so we don't block the reveal), ready=true caches for 30min
    (stable once populated).
    """
    from services.first_insights import get_first_insights

    athlete_id = current_user.id
    cache_key = f"first_insights:{athlete_id}"

    cached = get_cache(cache_key)
    if cached is not None:
        return cached

    result = get_first_insights(athlete_id, db)
    if result is None:
        result = {"ready": False}

    ttl = 1800 if result.get("ready") else 15
    _set_cache(cache_key, result, ttl=ttl)

    return result
