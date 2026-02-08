"""
Progress API Router — ADR-17 Phase 3

Unified "Am I getting better?" endpoint.
Pulls from ALL coach tools: training load, recovery, efficiency, correlations,
race predictions, training paces, PB patterns, wellness trends, athlete profile,
consistency, pace decay, volume trajectory — the full system.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Athlete, Activity
from routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/progress", tags=["progress"])


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
    avg_motivation: Optional[float] = None
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

    # --- Efficiency Trend ---
    try:
        from services.efficiency_analyzer import EfficiencyAnalyzer
        analyzer = EfficiencyAnalyzer(db)
        trends = analyzer.get_efficiency_trends(
            athlete_id=str(athlete_id),
            days=days,
            include_stability=False,
            include_load_response=False,
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
                avg_motivation=wd.get("avg_motivation"),
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
        from datetime import date
        plan = (
            db.query(TrainingPlan)
            .filter(TrainingPlan.athlete_id == athlete_id, TrainingPlan.status == "active")
            .first()
        )
        if plan and plan.goal_race_date and plan.goal_race_date >= date.today():
            result.goal_race_name = plan.goal_race_name or plan.name
            result.goal_race_date = plan.goal_race_date.isoformat()
            result.goal_race_days_remaining = (plan.goal_race_date - date.today()).days
            if plan.goal_time_seconds:
                h = plan.goal_time_seconds // 3600
                m = (plan.goal_time_seconds % 3600) // 60
                s = plan.goal_time_seconds % 60
                result.goal_time = f"{h}:{m:02d}:{s:02d}"
    except Exception as e:
        logger.warning(f"Progress goal race failed: {e}")

    # --- LLM Headline (uses FULL athlete brief via ADR-16) ---
    try:
        result.headline = _generate_headline(str(athlete_id), db, result, days)
    except Exception as e:
        logger.warning(f"Progress headline generation failed: {e}")

    return result


def _generate_headline(
    athlete_id: str,
    db: Session,
    summary: ProgressSummary,
    days: int,
) -> Optional[ProgressHeadline]:
    """Generate a coaching progress headline using the full athlete brief."""
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
    r = None
    try:
        import redis
        import os
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        r = redis.from_url(redis_url, decode_responses=True)
        cached = r.get(cache_key)
        if cached:
            data = json.loads(cached)
            return ProgressHeadline(**data)
    except Exception:
        r = None

    # ADR-16: Get the full athlete brief
    try:
        from services.coach_tools import build_athlete_brief
        athlete_brief = build_athlete_brief(db, UUID(athlete_id))
    except Exception as e:
        logger.warning(f"Failed to build athlete brief for progress headline: {e}")
        athlete_brief = "(Brief unavailable)"

    prompt = (
        "You are an elite running coach. Based on this athlete's full profile, "
        "write ONE headline about their overall progress trajectory — are they "
        "getting better, plateauing, or declining? Be direct, reference specific "
        "numbers. Sound like a coach who has been watching them for months.\n\n"
        f"=== ATHLETE BRIEF ===\n{athlete_brief}\n\n"
        "CRITICAL: Reference actual data from the brief. Do not invent numbers."
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
                            "description": "One coaching headline about overall progress. Reference specific numbers.",
                        },
                        "subtext": {
                            "type": "STRING",
                            "description": "One supporting detail sentence with a specific data point.",
                        },
                    },
                    "required": ["text", "subtext"],
                },
            ),
        )

        data = json.loads(response.text)
        headline = ProgressHeadline(**data)

        if r:
            try:
                r.setex(cache_key, 1800, json.dumps(data))
            except Exception:
                pass

        return headline

    except Exception as e:
        logger.warning(f"Progress headline LLM failed: {type(e).__name__}: {e}")
        return None
