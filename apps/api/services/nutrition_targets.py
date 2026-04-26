"""
Nutrition target computation: BMR, load-adaptive daily targets, macro splits.

Base = Mifflin-St Jeor BMR × 1.2 (fixed sedentary NEAT).
Training load handled by tier multipliers — never uses Garmin active_kcal.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session

from models import (
    Activity,
    Athlete,
    BodyComposition,
    CorrelationFinding,
    NutritionEntry,
    NutritionGoal,
    PlannedWorkout,
)

logger = logging.getLogger(__name__)

DEFAULT_MULTIPLIERS_PERFORMANCE = {
    "rest": 1.0, "easy": 1.15, "moderate": 1.3, "hard": 1.45, "long": 1.6,
}
DEFAULT_MULTIPLIERS_RECOMP = {
    "rest": 0.85, "easy": 1.0, "moderate": 1.3, "hard": 1.45, "long": 1.6,
}

_TIER_ORDER = ["rest", "easy", "moderate", "hard", "long"]

_WORKOUT_TYPE_TO_TIER = {
    "rest": "rest",
    "recovery": "rest",
    "easy": "easy",
    "threshold": "moderate",
    "steady_state": "moderate",
    "intervals": "hard",
    "threshold_intervals": "hard",
    "race": "hard",
    "long": "long",
}

NUTRITION_INSIGHT_METRICS = {
    "daily_calories", "daily_protein_g", "daily_carbs_g", "daily_fat_g",
    "daily_caffeine_mg", "pre_run_carbs_g", "pre_run_caffeine_mg",
    "pre_run_meal_gap_minutes", "during_run_carbs_g_per_hour",
}


def compute_bmr(weight_kg: float, height_cm: float, age_years: int, sex: str) -> int:
    if sex and sex.lower().startswith("f"):
        return round((10 * weight_kg) + (6.25 * height_cm) - (5 * age_years) - 161)
    return round((10 * weight_kg) + (6.25 * height_cm) - (5 * age_years) + 5)


def get_latest_weight(db: Session, athlete_id: UUID) -> Optional[float]:
    bc = (
        db.query(BodyComposition.weight_kg)
        .filter(BodyComposition.athlete_id == athlete_id, BodyComposition.weight_kg.isnot(None))
        .order_by(BodyComposition.date.desc())
        .first()
    )
    if bc:
        return float(bc.weight_kg)
    return None


def _resolve_tier(workout_type: Optional[str]) -> str:
    if not workout_type:
        return "rest"
    return _WORKOUT_TYPE_TO_TIER.get(workout_type.lower(), "moderate")


def _tier_rank(tier: str) -> int:
    try:
        return _TIER_ORDER.index(tier)
    except ValueError:
        return 2


def get_day_tier(db: Session, athlete_id: UUID, target_date: date) -> str:
    planned = (
        db.query(PlannedWorkout.workout_type)
        .filter(
            PlannedWorkout.athlete_id == athlete_id,
            PlannedWorkout.scheduled_date == target_date,
        )
        .all()
    )
    if planned:
        tiers = [_resolve_tier(p.workout_type) for p in planned]
        return max(tiers, key=_tier_rank)

    activities = (
        db.query(Activity.workout_type)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= datetime.combine(target_date, datetime.min.time()),
            Activity.start_time < datetime.combine(target_date + timedelta(days=1), datetime.min.time()),
        )
        .all()
    )
    if activities:
        tiers = [_resolve_tier(a.workout_type) for a in activities]
        return max(tiers, key=_tier_rank)

    return "rest"


def compute_daily_targets(
    db: Session, athlete_id: UUID, target_date: Optional[date] = None,
) -> Optional[Dict[str, Any]]:
    target_date = target_date or date.today()

    goal = db.query(NutritionGoal).filter(NutritionGoal.athlete_id == athlete_id).first()
    if not goal:
        return None

    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        return None

    weight_kg = get_latest_weight(db, athlete_id)
    height_cm = float(athlete.height_cm) if athlete.height_cm else None
    if not weight_kg or not height_cm or not athlete.birthdate:
        return None

    age_years = (target_date - athlete.birthdate).days // 365
    if age_years < 10:
        return None

    bmr = compute_bmr(weight_kg, height_cm, age_years, athlete.sex or "male")
    base_calories = round(bmr * 1.2)

    day_tier = get_day_tier(db, athlete_id, target_date)
    multipliers = goal.load_multipliers or (
        DEFAULT_MULTIPLIERS_RECOMP if goal.goal_type == "recomp"
        else DEFAULT_MULTIPLIERS_PERFORMANCE
    )
    multiplier = multipliers.get(day_tier, 1.0)

    if goal.load_adaptive:
        calorie_target = round(base_calories * multiplier)
    else:
        calorie_target = goal.calorie_target or base_calories

    protein_g = round(goal.protein_g_per_kg * weight_kg, 1)
    protein_cal = protein_g * 4
    remaining_cal = max(0, calorie_target - protein_cal)
    carb_pct = goal.carb_pct or 0.55
    fat_pct = goal.fat_pct or 0.45
    carbs_g = round((remaining_cal * carb_pct) / 4, 1)
    fat_g = round((remaining_cal * fat_pct) / 9, 1)

    planned = (
        db.query(PlannedWorkout.title)
        .filter(PlannedWorkout.athlete_id == athlete_id, PlannedWorkout.scheduled_date == target_date)
        .first()
    )

    return {
        "calorie_target": calorie_target,
        "protein_g": protein_g,
        "carbs_g": carbs_g,
        "fat_g": fat_g,
        "caffeine_mg": goal.caffeine_target_mg,
        "day_tier": day_tier,
        "base_calories": base_calories,
        "multiplier": multiplier,
        "load_adaptive": goal.load_adaptive,
        "goal_type": goal.goal_type,
        "workout_title": planned.title if planned else None,
    }


def get_daily_actuals(db: Session, athlete_id: UUID, target_date: date) -> Dict[str, float]:
    entries = (
        db.query(NutritionEntry)
        .filter(NutritionEntry.athlete_id == athlete_id, NutritionEntry.date == target_date)
        .all()
    )
    return {
        "calories": sum(float(e.calories or 0) for e in entries),
        "protein_g": sum(float(e.protein_g or 0) for e in entries),
        "carbs_g": sum(float(e.carbs_g or 0) for e in entries),
        "fat_g": sum(float(e.fat_g or 0) for e in entries),
        "caffeine_mg": sum(float(e.caffeine_mg or 0) for e in entries),
    }


def get_local_hour(athlete: Athlete) -> int:
    tz_name = athlete.timezone
    if tz_name:
        try:
            tz = ZoneInfo(tz_name)
            return datetime.now(tz).hour
        except Exception:
            pass
    return datetime.utcnow().hour


def get_nutrition_insights(
    db: Session, athlete_id: UUID, day_tier: str, limit: int = 1,
) -> List[Dict[str, str]]:
    findings = (
        db.query(CorrelationFinding)
        .filter(
            CorrelationFinding.athlete_id == athlete_id,
            CorrelationFinding.input_name.in_(NUTRITION_INSIGHT_METRICS),
            CorrelationFinding.is_active.is_(True),
            CorrelationFinding.times_confirmed >= 3,
        )
        .order_by(CorrelationFinding.times_confirmed.desc())
        .limit(limit * 3)
        .all()
    )

    results = []
    for f in findings:
        direction = "higher" if (f.direction or "") == "positive" else "lower"
        metric_label = f.input_name.replace("_", " ").replace("daily ", "").replace("pre run ", "pre-run ")
        output_label = (f.output_metric or "performance").replace("_", " ")
        text = f"Your data: {output_label} tends to be better with {direction} {metric_label}."
        results.append({"metric": f.input_name, "text": text})
        if len(results) >= limit:
            break

    return results
