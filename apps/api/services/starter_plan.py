"""
Starter plan auto-provisioning.

Problem:
- New athletes can complete onboarding + intake but have zero TrainingPlan rows.
- Calendar is the primary UI surface; an empty calendar after intake breaks trust.

Policy:
- Only create a plan if:
  - onboarding_completed is true
  - athlete has no active plan
  - goals intake exists
- Deterministic, best-effort; do not block Calendar if something fails.

Notes:
- If a valid race/time-trial anchor exists, we generate a pace-integrated plan (semi-custom)
  so the athlete immediately sees value from their input.
- If no valid anchor exists, we generate an effort-based plan and explicitly avoid fake precision.
"""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models import Athlete, IntakeQuestionnaire, TrainingPlan, PlannedWorkout, AthleteTrainingPaceProfile, AthleteRaceResultAnchor

logger = logging.getLogger(__name__)


def _next_monday(d: date) -> date:
    # Python weekday: Monday=0 ... Sunday=6
    delta = (7 - d.weekday()) % 7
    return d if delta == 0 else d + timedelta(days=delta)


def _clamp_int(v: int, lo: int, hi: int) -> int:
    try:
        vv = int(v)
    except Exception:
        vv = lo
    return max(lo, min(hi, vv))


def _clamp_float(v, lo: float, hi: float) -> float:
    try:
        vv = float(v)
    except Exception:
        vv = lo
    return max(lo, min(hi, vv))


def _goal_distance_from_intake(responses: dict) -> str:
    dist = (responses.get("goal_event_type") or "").strip().lower()
    if dist in ("5k", "10k", "half_marathon", "marathon"):
        return dist
    return "5k"


def _goal_date_from_intake(responses: dict) -> Optional[date]:
    s = responses.get("goal_event_date")
    if not s:
        return None
    try:
        return date.fromisoformat(str(s))
    except Exception:
        return None


def ensure_starter_plan(db: Session, *, athlete: Athlete) -> Optional[TrainingPlan]:
    """
    Ensure the athlete has an active training plan.

    Returns the active plan if present/created, else None.
    """
    if not athlete or not getattr(athlete, "onboarding_completed", False):
        return None

    existing = (
        db.query(TrainingPlan)
        .filter(TrainingPlan.athlete_id == athlete.id, TrainingPlan.status == "active")
        .first()
    )
    # If an older starter plan exists (generic/effort-only) but we now have a real race anchor,
    # upgrade it immediately to a paced plan. This prevents the "first 10 seconds" trust failure.
    if existing:
        try:
            anchor_now = (
                db.query(AthleteRaceResultAnchor)
                .filter(AthleteRaceResultAnchor.athlete_id == athlete.id)
                .first()
            )
            if anchor_now and anchor_now.distance_key and anchor_now.time_seconds:
                if (existing.generation_method or "") in ("starter_v1", "starter_v1_effort"):
                    existing.status = "archived"
                    db.commit()
                else:
                    return existing
            else:
                return existing
        except Exception:
            return existing

    intake = (
        db.query(IntakeQuestionnaire)
        .filter(IntakeQuestionnaire.athlete_id == athlete.id, IntakeQuestionnaire.stage == "goals")
        .order_by(IntakeQuestionnaire.created_at.desc())
        .first()
    )
    if not intake or not isinstance(intake.responses, dict):
        return None

    responses = intake.responses
    goal_distance = _goal_distance_from_intake(responses)
    goal_date = _goal_date_from_intake(responses) or (date.today() + timedelta(weeks=8))

    # Constraints from intake
    days_per_week = _clamp_int(responses.get("days_per_week", 6), 5, 7)
    weekly_miles = _clamp_float(responses.get("weekly_mileage_target", 30), 10.0, 150.0)

    # Start next Monday so we never back-date workouts into "missed" immediately.
    start_date = _next_monday(date.today())

    # Duration in weeks, clamped to generator limits.
    # If the goal is very soon/past, we still generate a minimal 4-week block.
    weeks_to_goal = int(((goal_date - start_date).days + 7) // 7)  # ceil-ish
    duration_weeks = _clamp_int(max(4, weeks_to_goal), 4, 24)

    try:
        from services.plan_framework.generator import PlanGenerator

        gen = PlanGenerator(db)
        # If we have a real race/time-trial anchor, generate a pace-integrated plan.
        # This is the "value in the first 10 seconds" requirement.
        anchor = (
            db.query(AthleteRaceResultAnchor)
            .filter(AthleteRaceResultAnchor.athlete_id == athlete.id)
            .first()
        )

        plan = None
        generation_kind = "starter_v1_effort"
        if anchor and anchor.distance_key and anchor.time_seconds:
            try:
                plan = gen.generate_semi_custom(
                    distance=goal_distance,
                    duration_weeks=duration_weeks,
                    current_weekly_miles=float(weekly_miles),
                    days_per_week=days_per_week,
                    race_date=goal_date,
                    recent_race_distance=str(anchor.distance_key),
                    recent_race_time_seconds=int(anchor.time_seconds),
                    athlete_id=athlete.id,
                )
                generation_kind = "starter_v1_paced"
            except Exception:
                plan = None

        # Fallback: effort-based standard plan (still better than empty calendar).
        if plan is None:
            tier = gen.tier_classifier.classify(
                current_weekly_miles=float(weekly_miles),
                goal_distance=goal_distance,
                athlete_id=athlete.id,
            )
            plan = gen.generate_standard(
                distance=goal_distance,
                duration_weeks=duration_weeks,
                tier=tier.value,
                days_per_week=days_per_week,
                start_date=start_date,
            )

        # Use pace profile scalar as baseline_vdot if available (does not change plan paces).
        pace_prof = (
            db.query(AthleteTrainingPaceProfile)
            .filter(AthleteTrainingPaceProfile.athlete_id == athlete.id)
            .first()
        )
        baseline_vdot = None
        try:
            baseline_vdot = float(pace_prof.fitness_score) if pace_prof and pace_prof.fitness_score is not None else None
        except Exception:
            baseline_vdot = None

        # Archive any existing active plans (should be none, but keep invariant).
        for p in db.query(TrainingPlan).filter(TrainingPlan.athlete_id == athlete.id, TrainingPlan.status == "active").all():
            p.status = "archived"

        plan_name = f"{goal_distance.replace('_', ' ').title()} Starter Plan"

        # Distance meters mapping (avoid trademark naming).
        DISTANCE_METERS = {"5k": 5000, "10k": 10000, "half_marathon": 21097, "marathon": 42195}
        distance_m = DISTANCE_METERS.get(goal_distance, 5000)

        db_plan = TrainingPlan(
            athlete_id=athlete.id,
            name=plan_name,
            goal_race_name=None,
            status="active",
            goal_race_date=goal_date,
            goal_race_distance_m=distance_m,
            plan_start_date=plan.start_date or start_date,
            plan_end_date=goal_date,
            total_weeks=plan.duration_weeks,
            baseline_vdot=baseline_vdot,
            baseline_weekly_volume_km=(plan.weekly_volumes[0] * 1.609) if plan.weekly_volumes else None,
            plan_type=goal_distance,
            generation_method=generation_kind,
        )
        db.add(db_plan)
        db.flush()

        for w in plan.workouts:
            if w.workout_type == "rest":
                continue
            if not w.date:
                continue
            if w.date > goal_date:
                continue
            db.add(
                PlannedWorkout(
                    plan_id=db_plan.id,
                    athlete_id=athlete.id,
                    scheduled_date=w.date,
                    week_number=w.week,
                    day_of_week=w.day,
                    workout_type=w.workout_type,
                    title=w.title,
                    description=w.description,
                    phase=w.phase,
                    target_duration_minutes=w.duration_minutes,
                    target_distance_km=round(w.distance_miles * 1.609, 2) if w.distance_miles else None,
                    segments=w.segments,
                    coach_notes=w.pace_description,
                )
            )

        db.commit()
        return db_plan
    except Exception as e:
        logger.exception("starter_plan_failed", extra={"extra_fields": {"athlete_id": str(getattr(athlete, "id", None)), "error": str(e)}})
        db.rollback()
        # In tests, fail loudly so we can see the actual exception.
        if os.getenv("PYTEST_CURRENT_TEST"):
            raise
        return None

