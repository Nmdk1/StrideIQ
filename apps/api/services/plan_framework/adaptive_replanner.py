"""Adaptive Re-Plan Service (N1 Engine Phase 4)

Detects meaningful divergence between plan and reality, generates a
proposed 2-week adjustment, and presents it for athlete approval.

Triggers:
  1. Missed long run (skipped or date passed without completion)
  2. 3+ consecutive missed days in a 7-day window
  3. 5+ consecutive days with readiness below reduce_volume_threshold

Principles (from Founder Operating Contract):
  - The system INFORMS, the athlete DECIDES (Guiding Principle #4)
  - Self-regulation is signal, not a problem (#7)
  - Silence = keep original plan (no silent swaps)
  - Max 2 adaptations per plan cycle; max 5 changed days per proposal
  - No adaptation during taper or within 48h of trigger
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

MAX_ADAPTATIONS_PER_CYCLE = 2
MAX_CHANGED_DAYS = 5
READINESS_TANK_DAYS = 5
CONSECUTIVE_MISSED_THRESHOLD = 3
TRIGGER_COOLDOWN_HOURS = 48
MICRO_PLAN_WEEKS = 2


@dataclass
class TriggerResult:
    trigger_type: str
    detail: Dict
    triggered_at: date


@dataclass
class DayDiff:
    scheduled_date: date
    day_of_week: int
    original_type: str
    original_title: str
    original_miles: Optional[float]
    proposed_type: str
    proposed_title: str
    proposed_miles: Optional[float]
    reason: str
    changed: bool


def check_adaptation_triggers(
    athlete_id: UUID,
    plan_id: UUID,
    target_date: date,
    db: Session,
) -> Optional[TriggerResult]:
    """Evaluate whether the athlete's plan needs an adaptation proposal.

    Checks three triggers in priority order. Returns the first one that
    fires, or None if no adaptation is warranted.
    """
    from models import TrainingPlan, PlannedWorkout, PlanAdaptationProposal

    plan = (
        db.query(TrainingPlan)
        .filter(TrainingPlan.id == plan_id, TrainingPlan.status == "active")
        .first()
    )
    if not plan:
        return None

    current_phase = _get_current_phase(plan_id, target_date, db)
    if current_phase == "taper":
        logger.debug("adaptive_replanner: skipping — athlete is in taper phase")
        return None

    existing = (
        db.query(PlanAdaptationProposal)
        .filter(
            PlanAdaptationProposal.plan_id == plan_id,
            PlanAdaptationProposal.status == "pending",
        )
        .first()
    )
    if existing:
        logger.debug("adaptive_replanner: skipping — pending proposal already exists")
        return None

    accepted_count = (
        db.query(PlanAdaptationProposal)
        .filter(
            PlanAdaptationProposal.plan_id == plan_id,
            PlanAdaptationProposal.status == "accepted",
        )
        .count()
    )
    if accepted_count >= MAX_ADAPTATIONS_PER_CYCLE:
        logger.debug(
            "adaptive_replanner: skipping — %d adaptations already accepted (max %d)",
            accepted_count, MAX_ADAPTATIONS_PER_CYCLE,
        )
        return None

    cooldown_cutoff = target_date - timedelta(hours=TRIGGER_COOLDOWN_HOURS)
    recent_proposal = (
        db.query(PlanAdaptationProposal)
        .filter(
            PlanAdaptationProposal.plan_id == plan_id,
            PlanAdaptationProposal.created_at >= datetime.combine(
                cooldown_cutoff, datetime.min.time(), tzinfo=timezone.utc,
            ),
        )
        .first()
    )
    if recent_proposal:
        logger.debug("adaptive_replanner: skipping — within 48h cooldown")
        return None

    trigger = _check_missed_long_run(athlete_id, plan_id, target_date, db)
    if trigger:
        return trigger

    trigger = _check_consecutive_missed(athlete_id, plan_id, target_date, db)
    if trigger:
        return trigger

    trigger = _check_readiness_tank(athlete_id, target_date, db)
    if trigger:
        return trigger

    return None


def generate_adaptation_proposal(
    athlete_id: UUID,
    plan_id: UUID,
    trigger: TriggerResult,
    target_date: date,
    db: Session,
) -> Optional[Dict]:
    """Generate a 2-week micro-plan adjustment and compute the diff.

    Returns a dict suitable for creating a PlanAdaptationProposal, or
    None if the diff is too large or the micro-plan fails.
    """
    from models import TrainingPlan, PlannedWorkout, PlanAdaptationProposal

    plan = db.query(TrainingPlan).filter(TrainingPlan.id == plan_id).first()
    if not plan or not plan.plan_start_date:
        return None

    current_week = _current_week_number(plan.plan_start_date, target_date)
    week_start = current_week
    week_end = min(current_week + MICRO_PLAN_WEEKS - 1, plan.total_weeks or 999)

    if plan.goal_race_date and (plan.goal_race_date - target_date).days <= 14:
        week_end = _current_week_number(plan.plan_start_date, plan.goal_race_date)

    original_workouts = (
        db.query(PlannedWorkout)
        .filter(
            PlannedWorkout.plan_id == plan_id,
            PlannedWorkout.week_number >= week_start,
            PlannedWorkout.week_number <= week_end,
            PlannedWorkout.scheduled_date >= target_date,
        )
        .order_by(PlannedWorkout.scheduled_date)
        .all()
    )

    if not original_workouts:
        return None

    original_snapshot = [_workout_to_dict(w) for w in original_workouts]

    phase_context = _derive_phase_context(plan_id, current_week, db)

    try:
        micro_plan = _generate_micro_plan(
            athlete_id, plan, trigger, target_date,
            week_start, week_end, phase_context, db,
        )
    except Exception as exc:
        logger.warning("adaptive_replanner: micro-plan generation failed: %s", exc)
        return None

    diffs = _compute_diff(original_workouts, micro_plan, target_date)

    changed_days = [d for d in diffs if d.changed]
    if len(changed_days) == 0:
        logger.info("adaptive_replanner: micro-plan identical to original — no proposal")
        return None
    if len(changed_days) > MAX_CHANGED_DAYS:
        logger.info(
            "adaptive_replanner: %d changed days exceeds max %d — suggesting full regen",
            len(changed_days), MAX_CHANGED_DAYS,
        )
        return None

    expires_at = _compute_expires_at(plan.plan_start_date, week_end)

    accepted_count = (
        db.query(PlanAdaptationProposal)
        .filter(
            PlanAdaptationProposal.plan_id == plan_id,
            PlanAdaptationProposal.status == "accepted",
        )
        .count()
    )

    return {
        "athlete_id": athlete_id,
        "plan_id": plan_id,
        "trigger_type": trigger.trigger_type,
        "trigger_detail": trigger.detail,
        "proposed_changes": [
            {
                "scheduled_date": d.scheduled_date.isoformat(),
                "day_of_week": d.day_of_week,
                "original_type": d.original_type,
                "original_title": d.original_title,
                "original_miles": d.original_miles,
                "proposed_type": d.proposed_type,
                "proposed_title": d.proposed_title,
                "proposed_miles": d.proposed_miles,
                "reason": d.reason,
                "changed": d.changed,
            }
            for d in diffs
        ],
        "original_snapshot": original_snapshot,
        "affected_week_start": week_start,
        "affected_week_end": week_end,
        "expires_at": expires_at,
        "adaptation_number": accepted_count + 1,
    }


def accept_proposal(proposal_id: UUID, db: Session) -> bool:
    """Apply a pending proposal to the plan's workouts."""
    from models import PlanAdaptationProposal, PlannedWorkout, PlanModificationLog

    proposal = (
        db.query(PlanAdaptationProposal)
        .filter(
            PlanAdaptationProposal.id == proposal_id,
            PlanAdaptationProposal.status == "pending",
        )
        .first()
    )
    if not proposal:
        return False

    now = datetime.now(timezone.utc)
    if proposal.expires_at and now > proposal.expires_at:
        proposal.status = "expired"
        db.flush()
        return False

    changes = proposal.proposed_changes or []
    for change in changes:
        if not change.get("changed"):
            continue
        sched_date = date.fromisoformat(change["scheduled_date"])
        workout = (
            db.query(PlannedWorkout)
            .filter(
                PlannedWorkout.plan_id == proposal.plan_id,
                PlannedWorkout.scheduled_date == sched_date,
            )
            .first()
        )
        if not workout:
            continue

        before = _workout_to_dict(workout)

        workout.workout_type = change["proposed_type"]
        workout.title = change["proposed_title"]
        if change.get("proposed_miles") is not None:
            workout.target_distance_km = round(change["proposed_miles"] * 1.609, 2)

        db.add(PlanModificationLog(
            athlete_id=proposal.athlete_id,
            plan_id=proposal.plan_id,
            workout_id=workout.id,
            action="adaptive_replan",
            before_state=before,
            after_state=_workout_to_dict(workout),
            reason=f"Adaptive Re-Plan: {proposal.trigger_type}",
            source="adaptive_replan",
        ))

    proposal.status = "accepted"
    proposal.responded_at = now
    db.flush()
    logger.info(
        "adaptive_replanner: proposal %s accepted for plan %s",
        proposal.id, proposal.plan_id,
    )
    return True


def reject_proposal(proposal_id: UUID, db: Session) -> bool:
    """Mark a pending proposal as rejected."""
    from models import PlanAdaptationProposal

    proposal = (
        db.query(PlanAdaptationProposal)
        .filter(
            PlanAdaptationProposal.id == proposal_id,
            PlanAdaptationProposal.status == "pending",
        )
        .first()
    )
    if not proposal:
        return False

    proposal.status = "rejected"
    proposal.responded_at = datetime.now(timezone.utc)
    db.flush()
    logger.info(
        "adaptive_replanner: proposal %s rejected for plan %s",
        proposal.id, proposal.plan_id,
    )
    return True


def expire_stale_proposals(db: Session) -> int:
    """Mark expired pending proposals. Called from nightly task."""
    from models import PlanAdaptationProposal

    now = datetime.now(timezone.utc)
    stale = (
        db.query(PlanAdaptationProposal)
        .filter(
            PlanAdaptationProposal.status == "pending",
            PlanAdaptationProposal.expires_at < now,
        )
        .all()
    )
    for p in stale:
        p.status = "expired"
    db.flush()
    if stale:
        logger.info("adaptive_replanner: expired %d stale proposals", len(stale))
    return len(stale)


# ---------------------------------------------------------------------------
# Trigger detection helpers
# ---------------------------------------------------------------------------

def _check_missed_long_run(
    athlete_id: UUID,
    plan_id: UUID,
    target_date: date,
    db: Session,
) -> Optional[TriggerResult]:
    """Trigger 1: missed long run in the last 7 days (excluding last 48h)."""
    from models import PlannedWorkout

    lookback_start = target_date - timedelta(days=7)
    lookback_end = target_date - timedelta(days=2)

    missed_long = (
        db.query(PlannedWorkout)
        .filter(
            PlannedWorkout.plan_id == plan_id,
            PlannedWorkout.scheduled_date >= lookback_start,
            PlannedWorkout.scheduled_date <= lookback_end,
            PlannedWorkout.workout_type.ilike("%long%"),
            PlannedWorkout.completed == False,  # noqa: E712
        )
        .all()
    )

    missed_long = [w for w in missed_long if w.skipped or w.scheduled_date < target_date]

    if missed_long:
        w = missed_long[0]
        return TriggerResult(
            trigger_type="missed_long_run",
            detail={
                "workout_id": str(w.id),
                "scheduled_date": w.scheduled_date.isoformat(),
                "workout_type": w.workout_type,
                "title": w.title,
                "target_miles": round(
                    (w.target_distance_km or 0) / 1.609, 1
                ) if w.target_distance_km else None,
            },
            triggered_at=target_date,
        )
    return None


def _check_consecutive_missed(
    athlete_id: UUID,
    plan_id: UUID,
    target_date: date,
    db: Session,
) -> Optional[TriggerResult]:
    """Trigger 2: 3+ consecutive missed days in the last 7 days."""
    from models import PlannedWorkout

    lookback = target_date - timedelta(days=7)
    workouts = (
        db.query(PlannedWorkout)
        .filter(
            PlannedWorkout.plan_id == plan_id,
            PlannedWorkout.scheduled_date >= lookback,
            PlannedWorkout.scheduled_date < target_date,
            PlannedWorkout.workout_type != "rest",
        )
        .order_by(PlannedWorkout.scheduled_date)
        .all()
    )

    consecutive = 0
    max_consecutive = 0
    missed_dates = []

    for w in workouts:
        if not w.completed and (w.skipped or w.scheduled_date < target_date):
            consecutive += 1
            missed_dates.append(w.scheduled_date.isoformat())
            max_consecutive = max(max_consecutive, consecutive)
        else:
            consecutive = 0

    if max_consecutive >= CONSECUTIVE_MISSED_THRESHOLD:
        return TriggerResult(
            trigger_type="consecutive_missed",
            detail={
                "consecutive_count": max_consecutive,
                "missed_dates": missed_dates[-max_consecutive:],
            },
            triggered_at=target_date,
        )
    return None


def _check_readiness_tank(
    athlete_id: UUID,
    target_date: date,
    db: Session,
) -> Optional[TriggerResult]:
    """Trigger 3: 5+ consecutive days with readiness below threshold."""
    from models import DailyReadiness, AthleteAdaptationThresholds

    thresholds = (
        db.query(AthleteAdaptationThresholds)
        .filter(AthleteAdaptationThresholds.athlete_id == athlete_id)
        .first()
    )
    reduce_threshold = thresholds.reduce_volume_threshold if thresholds else 25.0

    lookback = target_date - timedelta(days=READINESS_TANK_DAYS + 1)
    scores = (
        db.query(DailyReadiness)
        .filter(
            DailyReadiness.athlete_id == athlete_id,
            DailyReadiness.date >= lookback,
            DailyReadiness.date <= target_date,
        )
        .order_by(DailyReadiness.date)
        .all()
    )

    if len(scores) < READINESS_TANK_DAYS:
        return None

    consecutive_low = 0
    for s in scores:
        if s.score < reduce_threshold:
            consecutive_low += 1
        else:
            consecutive_low = 0

    if consecutive_low >= READINESS_TANK_DAYS:
        recent_scores = [
            {"date": s.date.isoformat(), "score": round(s.score, 1)}
            for s in scores[-READINESS_TANK_DAYS:]
        ]
        return TriggerResult(
            trigger_type="readiness_tank",
            detail={
                "consecutive_days": consecutive_low,
                "threshold": reduce_threshold,
                "recent_scores": recent_scores,
            },
            triggered_at=target_date,
        )
    return None


# ---------------------------------------------------------------------------
# Phase context derivation
# ---------------------------------------------------------------------------

def _get_current_phase(
    plan_id: UUID,
    target_date: date,
    db: Session,
) -> Optional[str]:
    from models import PlannedWorkout

    w = (
        db.query(PlannedWorkout.phase)
        .filter(
            PlannedWorkout.plan_id == plan_id,
            PlannedWorkout.scheduled_date <= target_date,
        )
        .order_by(PlannedWorkout.scheduled_date.desc())
        .first()
    )
    return w[0] if w else None


def _derive_phase_context(
    plan_id: UUID,
    current_week: int,
    db: Session,
) -> Dict:
    """Derive phase label, week_in_phase, and total_phase_weeks from PlannedWorkout rows."""
    from models import PlannedWorkout
    from sqlalchemy import distinct

    week_phases = (
        db.query(
            PlannedWorkout.week_number,
            PlannedWorkout.phase,
        )
        .filter(PlannedWorkout.plan_id == plan_id)
        .group_by(PlannedWorkout.week_number, PlannedWorkout.phase)
        .order_by(PlannedWorkout.week_number)
        .all()
    )

    if not week_phases:
        return {"phase": "build", "week_in_phase": 1, "total_phase_weeks": 4}

    current_phase = None
    phase_start_week = None
    phase_end_week = None

    for wn, ph in week_phases:
        if wn <= current_week:
            current_phase = ph
            if phase_start_week is None or ph != current_phase:
                phase_start_week = wn

    if current_phase is None:
        current_phase = week_phases[-1][1]

    same_phase_weeks = [wn for wn, ph in week_phases if ph == current_phase]
    total_phase_weeks = len(same_phase_weeks)
    week_in_phase = 1
    for i, wn in enumerate(same_phase_weeks):
        if wn <= current_week:
            week_in_phase = i + 1

    return {
        "phase": current_phase,
        "week_in_phase": week_in_phase,
        "total_phase_weeks": total_phase_weeks,
    }


def _current_week_number(plan_start: date, target_date: date) -> int:
    days = (target_date - plan_start).days
    return max(1, (days // 7) + 1)


# ---------------------------------------------------------------------------
# Micro-plan generation
# ---------------------------------------------------------------------------

def _generate_micro_plan(
    athlete_id: UUID,
    plan,
    trigger: TriggerResult,
    target_date: date,
    week_start: int,
    week_end: int,
    phase_context: Dict,
    db: Session,
) -> List[Dict]:
    """Generate a constrained 2-week micro-plan using the N1 engine.

    Passes current athlete state + phase context to produce workouts
    that fit the training phase and respond to the trigger.
    """
    from models import PlannedWorkout
    from services.fitness_bank import get_fitness_bank
    from services.plan_framework.n1_engine import generate_n1_plan
    from services.plan_framework.fingerprint_bridge import build_fingerprint_params

    bank = get_fitness_bank(athlete_id, db)
    if not bank:
        raise ValueError("No fitness bank for athlete")

    horizon_weeks = week_end - week_start + 1

    actual_volume = _get_recent_actual_volume(athlete_id, target_date, db)
    starting_vol = actual_volume if actual_volume > 0 else bank.current_weekly_miles

    fp_params = None
    try:
        fp_params = build_fingerprint_params(athlete_id, db)
    except Exception:
        pass

    plan_start = target_date
    race_date = plan.goal_race_date or (target_date + timedelta(weeks=horizon_weeks))

    if (race_date - target_date).days < horizon_weeks * 7:
        race_date = target_date + timedelta(weeks=horizon_weeks)

    best_rpi = bank.best_rpi

    rest_days = bank.typical_rest_days or []
    days_per_week = max(3, min(6, 7 - len(rest_days)))

    race_distance = _distance_from_meters(plan.goal_race_distance_m)

    weeks = generate_n1_plan(
        race_distance=race_distance,
        race_date=race_date,
        plan_start=plan_start,
        horizon_weeks=horizon_weeks,
        days_per_week=days_per_week,
        starting_vol=starting_vol,
        current_lr=bank.current_long_run_miles or 0,
        applied_peak=bank.peak_weekly_miles or starting_vol * 1.2,
        experience=bank.experience_level,
        best_rpi=best_rpi,
        fingerprint=fp_params,
        peak_long_run_miles=float(getattr(bank, "peak_long_run_miles", 0.0) or 0.0),
        long_run_capability_proven=bool(
            getattr(bank, "long_run_capability_proven", False)
        ),
    )

    micro_plan = []
    for week in weeks:
        week_start_date = plan_start + timedelta(weeks=week.week_number - 1)
        for day in week.days:
            workout_date = week_start_date + timedelta(days=day.day_of_week)
            if workout_date < target_date:
                continue
            micro_plan.append({
                "scheduled_date": workout_date,
                "day_of_week": day.day_of_week,
                "workout_type": day.workout_type,
                "title": day.name,
                "target_miles": day.target_miles,
                "description": day.description,
            })

    return micro_plan


# ---------------------------------------------------------------------------
# Diff computation
# ---------------------------------------------------------------------------

def _compute_diff(
    original_workouts: list,
    micro_plan: List[Dict],
    target_date: date,
) -> List[DayDiff]:
    """Compare original planned workouts against micro-plan output."""
    micro_by_date = {d["scheduled_date"]: d for d in micro_plan}
    diffs = []

    for w in original_workouts:
        if w.scheduled_date < target_date:
            continue

        micro = micro_by_date.get(w.scheduled_date)
        if not micro:
            diffs.append(DayDiff(
                scheduled_date=w.scheduled_date,
                day_of_week=w.day_of_week,
                original_type=w.workout_type,
                original_title=w.title or "",
                original_miles=round((w.target_distance_km or 0) / 1.609, 1),
                proposed_type=w.workout_type,
                proposed_title=w.title or "",
                proposed_miles=round((w.target_distance_km or 0) / 1.609, 1),
                reason="",
                changed=False,
            ))
            continue

        orig_type = (w.workout_type or "").lower()
        prop_type = (micro["workout_type"] or "").lower()
        orig_miles = round((w.target_distance_km or 0) / 1.609, 1)
        prop_miles = round(micro.get("target_miles") or 0, 1)

        type_changed = orig_type != prop_type
        miles_changed = abs(orig_miles - prop_miles) >= 1.0
        changed = type_changed or miles_changed

        reason = ""
        if changed:
            if type_changed and miles_changed:
                reason = f"{orig_type} → {prop_type}, {orig_miles}→{prop_miles}mi"
            elif type_changed:
                reason = f"{orig_type} → {prop_type}"
            else:
                reason = f"{orig_miles}→{prop_miles}mi"

        diffs.append(DayDiff(
            scheduled_date=w.scheduled_date,
            day_of_week=w.day_of_week,
            original_type=w.workout_type,
            original_title=w.title or "",
            original_miles=orig_miles,
            proposed_type=micro["workout_type"],
            proposed_title=micro.get("title") or "",
            proposed_miles=prop_miles,
            reason=reason,
            changed=changed,
        ))

    return diffs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_recent_actual_volume(
    athlete_id: UUID,
    target_date: date,
    db: Session,
) -> float:
    """Get the athlete's actual running volume in the last 7 days."""
    from models import Activity
    from sqlalchemy import func

    lookback = target_date - timedelta(days=7)
    result = (
        db.query(func.sum(Activity.distance_m))
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.sport == "run",
            Activity.start_time >= datetime.combine(lookback, datetime.min.time()),
            Activity.start_time < datetime.combine(target_date, datetime.min.time()),
            Activity.is_duplicate == False,  # noqa: E712
        )
        .scalar()
    )
    return round((result or 0) / 1609.34, 1)


def _workout_to_dict(w) -> Dict:
    return {
        "id": str(w.id),
        "scheduled_date": w.scheduled_date.isoformat() if w.scheduled_date else None,
        "workout_type": w.workout_type,
        "title": w.title,
        "phase": w.phase,
        "week_number": w.week_number,
        "target_distance_km": float(w.target_distance_km) if w.target_distance_km else None,
        "target_duration_minutes": w.target_duration_minutes,
        "description": w.description,
        "completed": w.completed,
        "skipped": w.skipped,
    }


def _compute_expires_at(plan_start: date, week_end: int) -> datetime:
    """Expires end-of-day Sunday of the second adjusted week."""
    week_end_date = plan_start + timedelta(weeks=week_end)
    days_to_sunday = (6 - week_end_date.weekday()) % 7
    sunday = week_end_date + timedelta(days=days_to_sunday)
    return datetime.combine(sunday, datetime.max.time(), tzinfo=timezone.utc)


_METER_TO_DISTANCE = {
    5000: "5k",
    10000: "10k",
    21097: "half_marathon",
    21098: "half_marathon",
    42195: "marathon",
}


def _distance_from_meters(meters) -> str:
    if not meters:
        return "10k"
    m = int(round(meters))
    if m in _METER_TO_DISTANCE:
        return _METER_TO_DISTANCE[m]
    if m < 7500:
        return "5k"
    if m < 15000:
        return "10k"
    if m < 30000:
        return "half_marathon"
    return "marathon"
