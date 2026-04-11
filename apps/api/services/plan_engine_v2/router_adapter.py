"""
Plan Engine V2 — router adapter.

Bridges the existing ConstraintAwarePlanRequest into V2's generate_plan_v2()
and returns a response compatible with the V1 shape so the frontend works
unchanged.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from services.fitness_bank import FitnessBank, get_fitness_bank, rpi_equivalent_time
from services.plan_framework.fingerprint_bridge import build_fingerprint_params
from services.plan_framework.load_context import build_load_context, history_anchor_date

from .engine import generate_plan_v2
from .models import TuneUpRace as V2TuneUpRace, V2PlanPreview
from .plan_saver import save_v2_plan

logger = logging.getLogger(__name__)

_EVENT_MAP = {
    "5k": "5K",
    "10k": "10K",
    "10_mile": "10_mile",
    "half_marathon": "half_marathon",
    "half": "half_marathon",
    "marathon": "marathon",
}


def _map_tune_up_races(
    raw_races: Optional[list],
) -> Optional[List[V2TuneUpRace]]:
    """Convert V1 TuneUpRace Pydantic models or dicts to V2 TuneUpRace dataclasses."""
    if not raw_races:
        return None
    result = []
    for r in raw_races:
        if hasattr(r, "race_date"):
            rd, dist, name, purpose = r.race_date, r.distance, r.name, r.purpose
        else:
            rd = r.get("date") or r.get("race_date")
            dist = r.get("distance", "10k")
            name = r.get("name", "Tune-up")
            purpose = r.get("purpose", "tune_up")
        result.append(V2TuneUpRace(
            race_date=rd,
            distance=_EVENT_MAP.get(dist.lower(), dist) if dist else "10K",
            name=name or "Tune-up race",
            purpose=purpose or "sharpening",
        ))
    return result


def _compute_plan_start(race_date: date, total_weeks: int) -> date:
    """Compute plan start date: race_date minus total_weeks, aligned to Monday."""
    start = race_date - timedelta(weeks=total_weeks)
    monday = start - timedelta(days=start.weekday())
    return monday


def _build_prediction(bank: FitnessBank, race_distance: str) -> dict:
    """Build a prediction block from FitnessBank data."""
    dist_meters = {
        "5k": 5000, "10k": 10000, "10_mile": 16093,
        "half_marathon": 21097, "half": 21097, "marathon": 42195,
    }
    meters = dist_meters.get(race_distance, 42195)
    try:
        base_seconds = rpi_equivalent_time(bank.best_rpi, meters)
        hours = int(base_seconds // 3600)
        mins = int((base_seconds % 3600) // 60)
        secs = int(base_seconds % 60)
        if hours > 0:
            time_str = f"{hours}:{mins:02d}:{secs:02d}"
        else:
            time_str = f"{mins}:{secs:02d}"
        ci_pct = 0.03
        lo = base_seconds * (1 - ci_pct)
        hi = base_seconds * (1 + ci_pct)
        ci_str = f"-{(base_seconds - lo) / 60:.0f}/+{(hi - base_seconds) / 60:.0f} min"
    except Exception:
        time_str = None
        ci_str = None

    return {
        "time": time_str,
        "confidence_interval": ci_str,
        "uncertainty_reason": None,
        "rationale_tags": [],
        "scenarios": None,
    }


def _generate_model_insights(tau1: float, tau2: float) -> List[str]:
    """Human-readable insights from model parameters."""
    insights = []
    if tau1 < 38:
        insights.append(f"You adapt faster than average (tau1={tau1:.0f} vs typical 42 days)")
    elif tau1 > 46:
        insights.append(f"You benefit from longer training blocks (tau1={tau1:.0f} vs typical 42 days)")

    if tau2 < 6:
        insights.append(f"You recover quickly from fatigue (tau2={tau2:.0f} vs typical 7 days)")
    elif tau2 > 9:
        insights.append(f"You need extra recovery time (tau2={tau2:.0f} vs typical 7 days)")

    optimal_taper = max(7, min(21, int(2.0 * tau2)))
    insights.append(f"Your optimal taper length: {optimal_taper} days")
    return insights


def _estimate_total_miles(plan: V2PlanPreview, easy_pace: float) -> float:
    """Sum total plan miles from all weeks."""
    from .plan_saver import _estimate_day_distance_km
    total_km = 0.0
    for week in plan.weeks:
        for day in week.days:
            if day.workout_type == "rest":
                continue
            km = _estimate_day_distance_km(day)
            if km:
                total_km += km
    return round(total_km / 1.60934, 1)


def _estimate_peak_miles(plan: V2PlanPreview, easy_pace: float) -> float:
    """Find peak weekly mileage."""
    from .plan_saver import _estimate_day_distance_km
    peak = 0.0
    for week in plan.weeks:
        week_km = 0.0
        for day in week.days:
            if day.workout_type == "rest":
                continue
            km = _estimate_day_distance_km(day)
            if km:
                week_km += km
        peak = max(peak, week_km)
    return round(peak / 1.60934, 1)


def generate_and_save_v2(
    athlete_id: UUID,
    db: Session,
    race_date: date,
    race_distance: str,
    *,
    race_name: Optional[str] = None,
    goal_time_seconds: Optional[int] = None,
    tune_up_races: Optional[list] = None,
    target_peak_weekly_miles: Optional[float] = None,
    taper_weeks: Optional[int] = None,
    dry_run: bool = False,
    preferred_units: str = "imperial",
) -> Dict[str, Any]:
    """Full V2 generation flow: load athlete data, generate, save, return response.

    This is the V2 equivalent of the V1 constraint-aware generation path.
    Returns a response dict compatible with the existing frontend.
    """
    start_time = datetime.now()

    bank = get_fitness_bank(athlete_id, db)
    reference_date = history_anchor_date(None, db, athlete_id)
    load_ctx = build_load_context(athlete_id, db, reference_date)
    fp_params = build_fingerprint_params(athlete_id, db)

    goal_event = _EVENT_MAP.get(race_distance.lower(), "marathon")
    v2_tune_ups = _map_tune_up_races(tune_up_races)

    weeks_to_race = (race_date - date.today()).days // 7
    plan_start = _compute_plan_start(race_date, weeks_to_race)

    plan = generate_plan_v2(
        fitness_bank=bank,
        fingerprint=fp_params,
        load_ctx=load_ctx,
        mode="race",
        goal_event=goal_event,
        target_date=race_date,
        weeks_available=weeks_to_race,
        units=preferred_units,
        desired_peak_weekly_miles=target_peak_weekly_miles,
        goal_time_seconds=goal_time_seconds,
        tune_up_races=v2_tune_ups,
        plan_start_date=plan_start,
    )

    fb_dict = bank.to_dict()
    easy_pace = getattr(bank, "easy_pace_sec_km", 0) or 0
    if hasattr(plan, "pace_ladder") and isinstance(plan.pace_ladder, dict):
        easy_pace = plan.pace_ladder.get("easy", easy_pace)

    plan_id = None
    if not dry_run:
        saved_plan = save_v2_plan(
            db, athlete_id, plan, race_date, race_distance.lower(),
            plan_start,
            race_name=race_name,
            goal_time_seconds=goal_time_seconds,
            fitness_bank_dict=fb_dict,
            easy_pace_sec_km=easy_pace,
        )
        plan_id = str(saved_plan.id)

    gen_time = (datetime.now() - start_time).total_seconds()
    logger.info(
        "V2 plan generated for %s in %.2fs%s",
        athlete_id, gen_time,
        " (dry_run)" if dry_run else f", saved as {plan_id}",
    )

    total_miles = _estimate_total_miles(plan, easy_pace)
    peak_miles = _estimate_peak_miles(plan, easy_pace)

    return {
        "success": True,
        "plan_id": plan_id,
        "dry_run": dry_run,
        "engine": "v2",
        "race": {
            "date": race_date.isoformat(),
            "distance": race_distance,
            "name": race_name,
        },
        "fitness_bank": fb_dict,
        "model": {
            "confidence": bank.peak_confidence,
            "tau1": round(bank.tau1, 1),
            "tau2": round(bank.tau2, 1),
            "insights": _generate_model_insights(bank.tau1, bank.tau2),
        },
        "prediction": _build_prediction(bank, race_distance),
        "volume_contract": {
            "recent_8w_median_weekly_miles": bank.recent_8w_median_weekly_miles,
            "sustainable_peak_weekly": bank.sustainable_peak_weekly,
            "target_peak_weekly_miles": target_peak_weekly_miles,
            "band_max": target_peak_weekly_miles or bank.sustainable_peak_weekly,
        },
        "quality_gate_fallback": False,
        "quality_gate_reasons": [],
        "quality_gate": {
            "passed": plan.quality_gate_passed,
            "details": plan.quality_gate_details,
        },
        "personalization": {
            "notes": fp_params.disclosures,
            "tune_up_races": [
                {"date": t.race_date.isoformat(), "distance": t.distance,
                 "name": t.name, "purpose": t.purpose}
                for t in (v2_tune_ups or [])
            ],
        },
        "summary": {
            "total_weeks": plan.total_weeks,
            "total_miles": total_miles,
            "peak_miles": peak_miles,
        },
        "weeks": [w.to_dict(units=preferred_units) for w in plan.weeks],
        "generated_at": datetime.now().isoformat(),
    }
