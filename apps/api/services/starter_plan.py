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
from services.plan_quality_gate import evaluate_starter_plan_quality

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


def _apply_cold_start_guardrails(plan):
    """
    Cold-start guardrails:
    - week 1 total <= 25 mi
    - week 1 long run <= 8 mi
    - first 4 weeks ramp <= +15%
    """
    if not plan or not getattr(plan, "workouts", None):
        return plan

    week_totals = {}
    week_longs = {}
    for w in plan.workouts:
        miles = float(w.distance_miles or 0)
        week_totals[w.week] = week_totals.get(w.week, 0.0) + miles
        if w.workout_type in ("long", "long_mp", "long_hmp"):
            week_longs[w.week] = max(week_longs.get(w.week, 0.0), miles)

    # Week 1 caps
    w1_total = week_totals.get(1, 0.0)
    if w1_total > 25.0 and w1_total > 0:
        scale = 25.0 / w1_total
        for w in plan.workouts:
            if w.week == 1 and w.workout_type != "rest" and w.distance_miles:
                w.distance_miles = max(2.0, round(float(w.distance_miles) * scale, 1))
                if w.duration_minutes:
                    w.duration_minutes = max(20, int(w.duration_minutes * scale))

    for w in plan.workouts:
        if w.week == 1 and w.workout_type in ("long", "long_mp", "long_hmp") and w.distance_miles:
            w.distance_miles = min(float(w.distance_miles), 8.0)

    # Re-normalize week 1 after long-run clamp to ensure strict 25mi cap.
    week1_total = sum(float(w.distance_miles or 0) for w in plan.workouts if w.week == 1)
    if week1_total > 25.0 and week1_total > 0:
        non_long = [w for w in plan.workouts if w.week == 1 and w.workout_type not in ("long", "long_mp", "long_hmp")]
        non_long_total = sum(float(w.distance_miles or 0) for w in non_long)
        remaining = 25.0 - sum(float(w.distance_miles or 0) for w in plan.workouts if w.week == 1 and w.workout_type in ("long", "long_mp", "long_hmp"))
        if non_long_total > 0 and remaining > 0:
            scale = remaining / non_long_total
            for w in non_long:
                if w.distance_miles:
                    w.distance_miles = max(2.0, round(float(w.distance_miles) * scale, 1))
        # Final deterministic correction for rounding drift.
        week1_total = sum(float(w.distance_miles or 0) for w in plan.workouts if w.week == 1)
        overflow = round(week1_total - 25.0, 2)
        if overflow > 0:
            adjustable = [w for w in plan.workouts if w.week == 1 and w.workout_type not in ("long", "long_mp", "long_hmp") and float(w.distance_miles or 0) > 2.0]
            if adjustable:
                w = max(adjustable, key=lambda x: float(x.distance_miles or 0))
                w.distance_miles = max(2.0, round(float(w.distance_miles or 0) - overflow, 1))

    # Rebuild totals after week 1 caps
    week_totals = {}
    for w in plan.workouts:
        week_totals[w.week] = week_totals.get(w.week, 0.0) + float(w.distance_miles or 0)

    # Ramp cap for first 4 weeks
    for wk in (2, 3, 4):
        prev = max(week_totals.get(wk - 1, 0.0), 1.0)
        cur = week_totals.get(wk, 0.0)
        allowed = prev * 1.15
        if cur > allowed and cur > 0:
            scale = allowed / cur
            for w in plan.workouts:
                if w.week == wk and w.workout_type != "rest" and w.distance_miles:
                    w.distance_miles = max(2.0, round(float(w.distance_miles) * scale, 1))
                    if w.duration_minutes:
                        w.duration_minutes = max(20, int(w.duration_minutes * scale))
            week_totals[wk] = allowed

    # Keep summary values coherent.
    plan.total_miles = sum(float(w.distance_miles or 0) for w in plan.workouts)
    if hasattr(plan, "weekly_volumes") and isinstance(plan.weekly_volumes, list):
        weekly = []
        for i in range(1, max(week_totals.keys()) + 1):
            weekly.append(round(week_totals.get(i, 0.0), 1))
        plan.weekly_volumes = weekly
        if weekly:
            plan.peak_volume = max(weekly)
    return plan
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
            # Production safety: ignore implausible anchors (e.g. "1:02" parsed as 62 seconds).
            if anchor_now and anchor_now.distance_key and anchor_now.time_seconds and int(anchor_now.time_seconds) >= 600:
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
        has_valid_anchor = bool(anchor and anchor.distance_key and anchor.time_seconds and int(anchor.time_seconds) >= 600)
        from models import Activity
        activity_runs = db.query(Activity).filter(Activity.athlete_id == athlete.id, Activity.sport.ilike("run")).count()
        is_cold_start = activity_runs == 0 and not has_valid_anchor

        plan = None
        generation_kind = "starter_v1_effort"
        if has_valid_anchor:
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
            effective_weekly = min(weekly_miles, 25.0) if is_cold_start else weekly_miles
            tier = gen.tier_classifier.classify(
                current_weekly_miles=float(effective_weekly),
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
        if is_cold_start:
            plan = _apply_cold_start_guardrails(plan)
            gate = evaluate_starter_plan_quality(plan)
            if not gate.passed:
                # Single retry with stricter intent floor.
                tier = gen.tier_classifier.classify(
                    current_weekly_miles=20.0,
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
                plan = _apply_cold_start_guardrails(plan)
                gate2 = evaluate_starter_plan_quality(plan)
                if not gate2.passed:
                    raise ValueError(f"starter_plan_quality_gate_failed: {gate2.reasons}")

        # Use pace profile scalar as baseline_rpi if available (does not change plan paces).
        pace_prof = (
            db.query(AthleteTrainingPaceProfile)
            .filter(AthleteTrainingPaceProfile.athlete_id == athlete.id)
            .first()
        )
        baseline_rpi = None
        try:
            baseline_rpi = float(pace_prof.fitness_score) if pace_prof and pace_prof.fitness_score is not None else None
        except Exception:
            baseline_rpi = None

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
            baseline_rpi=baseline_rpi,
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

