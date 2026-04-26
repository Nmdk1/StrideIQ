"""
Plan Engine V2 — save V2 plan output to TrainingPlan + PlannedWorkout rows.

Maps V2WeekPlan/V2DayPlan dataclasses to the same DB schema that V1 uses,
so the existing calendar, detail, exports, and edit views work unchanged.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from .models import V2PlanPreview, V2DayPlan

logger = logging.getLogger(__name__)

_DISTANCE_METERS = {
    "5k": 5000, "5K": 5000,
    "10k": 10000, "10K": 10000,
    "10_mile": 16093,
    "half_marathon": 21097, "half": 21097,
    "marathon": 42195,
    "50K": 50000, "50k": 50000,
    "50_mile": 80467,
    "100K": 100000, "100k": 100000,
    "100_mile": 160934,
}

_MI_TO_KM = 1.60934


def _estimate_day_distance_km(day: V2DayPlan) -> Optional[float]:
    """Best-effort distance estimate from a V2DayPlan, in km."""
    if day.target_distance_km:
        return day.target_distance_km
    if day.segments:
        total = 0.0
        for s in day.segments:
            if s.distance_km:
                total += s.distance_km
            elif s.duration_min and s.pace_sec_per_km and s.pace_sec_per_km > 0:
                total += (s.duration_min * 60.0) / s.pace_sec_per_km
        if total > 0:
            return round(total, 2)
    if day.distance_range_km:
        return round((day.distance_range_km[0] + day.distance_range_km[1]) / 2.0, 2)
    return None


def _estimate_day_duration_min(day: V2DayPlan, easy_pace_sec_km: float) -> Optional[int]:
    """Estimate workout duration from distance and pace."""
    dist_km = _estimate_day_distance_km(day)
    if dist_km and easy_pace_sec_km > 0:
        return int(dist_km * easy_pace_sec_km / 60.0)
    if day.segments:
        total_min = 0.0
        for s in day.segments:
            if s.duration_min:
                total_min += s.duration_min
            elif s.distance_km and s.pace_sec_per_km and s.pace_sec_per_km > 0:
                total_min += s.distance_km * s.pace_sec_per_km / 60.0
        if total_min > 0:
            return int(total_min)
    return None


def _build_segments_json(day: V2DayPlan) -> Optional[list]:
    """Convert V2 WorkoutSegments to JSONB-ready dicts."""
    if not day.segments:
        return None
    return [s.to_dict(units="imperial") for s in day.segments]


def _build_coach_notes(day: V2DayPlan) -> Optional[str]:
    """Build coach notes from segments and fueling info."""
    parts: List[str] = []
    if day.segments:
        seg_descs = [s.description for s in day.segments if s.description]
        if seg_descs:
            parts.append(" → ".join(seg_descs))
    if day.fueling:
        parts.append(f"Fueling: {day.fueling.during_run_carbs_g_per_hr}g carbs/hr")
        if day.fueling.notes:
            parts.append(day.fueling.notes)
    return " | ".join(parts) if parts else None


def save_v2_plan(
    db: Session,
    athlete_id: UUID,
    plan: V2PlanPreview,
    race_date: date,
    race_distance: str,
    plan_start_date: date,
    *,
    race_name: Optional[str] = None,
    goal_time_seconds: Optional[int] = None,
    fitness_bank_dict: Optional[dict] = None,
    easy_pace_sec_km: float = 0.0,
) -> "TrainingPlan":
    """Save a V2 plan to TrainingPlan + PlannedWorkout rows.

    Archives existing active plans for this athlete, then inserts the
    new plan and all non-rest day workouts. Returns the saved TrainingPlan.
    """
    from models import TrainingPlan, PlannedWorkout

    db.query(TrainingPlan).filter(
        TrainingPlan.athlete_id == athlete_id,
        TrainingPlan.status == "active",
    ).update({"status": "archived"})

    distance_m = _DISTANCE_METERS.get(race_distance, 42195)
    dist_label = race_distance.replace("_", " ").title()
    plan_name = race_name if race_name else f"{dist_label} Plan"

    baseline_rpi = None
    baseline_volume_km = None
    if isinstance(fitness_bank_dict, dict):
        baseline_rpi = fitness_bank_dict.get("best_rpi")
        current = fitness_bank_dict.get("current") or {}
        peak = fitness_bank_dict.get("peak") or {}
        weekly_mi = current.get("weekly_miles") or peak.get("weekly_miles") or 0
        if weekly_mi:
            baseline_volume_km = round(float(weekly_mi) * _MI_TO_KM, 1)

    plan_monday = plan_start_date - timedelta(days=plan_start_date.weekday())

    db_plan = TrainingPlan(
        athlete_id=athlete_id,
        name=plan_name,
        goal_race_name=race_name,
        status="active",
        goal_race_date=race_date,
        goal_race_distance_m=distance_m,
        plan_start_date=plan_monday,
        plan_end_date=race_date,
        total_weeks=plan.total_weeks,
        baseline_rpi=baseline_rpi,
        baseline_weekly_volume_km=baseline_volume_km,
        plan_type=race_distance,
        generation_method="v2",
        goal_time_seconds=goal_time_seconds,
    )
    db.add(db_plan)
    db.flush()

    phase_counter: Dict[str, int] = {}
    phase_spans: Dict[str, int] = {}
    for week in plan.weeks:
        phase_spans[week.phase] = phase_spans.get(week.phase, 0) + 1

    seen_dates: set = set()
    for week in plan.weeks:
        phase = week.phase
        phase_counter[phase] = phase_counter.get(phase, 0) + 1
        week_in_phase = phase_counter[phase]

        week_monday = plan_monday + timedelta(weeks=week.week_number - 1)

        for day in week.days:
            if day.workout_type == "rest":
                continue

            workout_date = week_monday + timedelta(days=day.day_of_week)
            if workout_date in seen_dates:
                continue
            seen_dates.add(workout_date)

            db_workout = PlannedWorkout(
                plan_id=db_plan.id,
                athlete_id=athlete_id,
                scheduled_date=workout_date,
                week_number=week.week_number,
                day_of_week=day.day_of_week,
                workout_type=day.workout_type,
                title=day.title,
                description=day.description,
                phase=day.phase,
                phase_week=week_in_phase,
                target_distance_km=_estimate_day_distance_km(day),
                target_duration_minutes=_estimate_day_duration_min(day, easy_pace_sec_km),
                segments=_build_segments_json(day),
                coach_notes=_build_coach_notes(day),
                workout_variant_id=None,
            )
            db.add(db_workout)

    db.commit()
    logger.info(
        "Saved V2 plan %s for athlete %s: %d weeks, %d workouts",
        db_plan.id, athlete_id, plan.total_weeks, len(seen_dates),
    )
    return db_plan
