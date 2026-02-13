"""
No-Race-Planned Modes (Phase 2E)

Two rule-driven modes for athletes between race cycles.

Maintenance Mode:
    - Consistent volume at ~80% of last build's peak
    - Easy runs + strides + 1 modest quality session per week
    - Readiness monitoring (flag if efficiency drops)
    - Purpose: hold fitness without building fatigue

Base Building Mode:
    - Progressive volume increase (10% / 3 weeks, cutback on week 4)
    - Strides + hills for neuromuscular activation
    - No hard threshold/interval work
    - Purpose: build aerobic base for next race cycle

Both modes:
    - Generate a rolling 4-week plan that refreshes weekly
    - Adaptation engine (2C) applies identically
    - Transition to race plan is seamless (base building feeds into Phase 1)

Sources:
    docs/TRAINING_PLAN_REBUILD_PLAN.md (Phase 2E)
    _AI_CONTEXT_/KNOWLEDGE_BASE/TRAINING_PHILOSOPHY.md (Green's base philosophy)
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session

import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class NoRaceWorkout:
    """A single workout in a no-race plan."""
    date: date
    week_number: int
    day_of_week: int           # 0=Monday, 6=Sunday
    workout_type: str          # 'easy', 'long', 'strides', 'hills', 'threshold', 'recovery'
    title: str
    description: str
    target_distance_km: Optional[float] = None
    target_duration_minutes: Optional[int] = None
    phase: str = "maintenance"  # or "base"


@dataclass
class NoRacePlan:
    """A 4-week rolling no-race plan."""
    mode: str                  # "maintenance" or "base_building"
    athlete_id: UUID
    start_date: date
    end_date: date
    total_weeks: int = 4
    workouts: List[NoRaceWorkout] = field(default_factory=list)
    weekly_volumes_km: List[float] = field(default_factory=list)
    peak_volume_km: float = 0.0
    base_volume_km: float = 0.0


# ---------------------------------------------------------------------------
# Weekly structure templates
# ---------------------------------------------------------------------------

# Day indices: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun

MAINTENANCE_WEEK = [
    # day, type, pct_of_weekly, title, description
    (0, "easy", 0.14, "Easy Run", "Relaxed effort, conversational pace."),
    (1, "strides", 0.14, "Easy + Strides", "Easy run with 4-6 x 20s strides at mile pace after."),
    (2, "recovery", 0.0, "Rest or Cross-Train", "Full rest or easy cross-training."),
    (3, "threshold", 0.18, "Threshold Session", "20-25 min at threshold effort. The one quality session this week."),
    (4, "easy", 0.12, "Easy Run", "Relaxed effort. Keep it genuinely easy."),
    (5, "strides", 0.14, "Easy + Strides", "Easy run with 4-6 x 20s strides. Keep legs turning over."),
    (6, "long", 0.28, "Long Run", "Steady aerobic effort. Not a race, not a shuffle."),
]

BASE_BUILDING_WEEK = [
    # Base building: no threshold. Strides and hills for neuromuscular activation.
    (0, "easy", 0.14, "Easy Run", "Relaxed effort, conversational pace."),
    (1, "strides", 0.14, "Easy + Strides", "Easy run with 6 x 20s strides. Build leg speed without fatigue."),
    (2, "recovery", 0.0, "Rest or Cross-Train", "Full rest or easy cross-training."),
    (3, "hills", 0.16, "Easy + Hill Sprints", "Easy run with 6-8 x 10s hill sprints. Neuromuscular power."),
    (4, "easy", 0.12, "Easy Run", "Relaxed effort. Easy means easy."),
    (5, "strides", 0.14, "Easy + Strides", "Easy run with strides. Stay loose."),
    (6, "long", 0.30, "Long Run", "The cornerstone of base building. Steady and comfortable."),
]


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class NoRaceModeGenerator:
    """
    Generate rolling 4-week plans for maintenance or base building.

    Usage:
        generator = NoRaceModeGenerator(db)

        # Maintenance: hold fitness
        plan = generator.generate_maintenance(
            athlete_id=uuid,
            start_date=date(2026, 2, 16),
            base_volume_km=60.0,  # from last plan's peak * 0.80
        )

        # Base building: progressive volume
        plan = generator.generate_base_building(
            athlete_id=uuid,
            start_date=date(2026, 2, 16),
            current_volume_km=50.0,
        )
    """

    def __init__(self, db: Session):
        self.db = db

    def generate_maintenance(
        self,
        athlete_id: UUID,
        start_date: date,
        base_volume_km: Optional[float] = None,
        days_per_week: int = 6,
    ) -> NoRacePlan:
        """
        Generate a 4-week maintenance plan.

        Volume stays at ~80% of last build peak. Consistent week to week.

        Args:
            athlete_id: The athlete's UUID
            start_date: Monday of the first week
            base_volume_km: Target weekly volume (if None, derived from history)
            days_per_week: Number of training days per week (4-7)
        """
        if base_volume_km is None:
            base_volume_km = self._derive_maintenance_volume(athlete_id)

        weeks = 4
        # Maintenance volume is flat — no progression, no cutback
        weekly_volumes = [base_volume_km] * weeks

        workouts = []
        for week_idx in range(weeks):
            week_start = start_date + timedelta(weeks=week_idx)
            week_workouts = self._build_week(
                week_start=week_start,
                week_number=week_idx + 1,
                weekly_km=weekly_volumes[week_idx],
                template=MAINTENANCE_WEEK,
                phase="maintenance",
                days_per_week=days_per_week,
            )
            workouts.extend(week_workouts)

        return NoRacePlan(
            mode="maintenance",
            athlete_id=athlete_id,
            start_date=start_date,
            end_date=start_date + timedelta(weeks=weeks) - timedelta(days=1),
            total_weeks=weeks,
            workouts=workouts,
            weekly_volumes_km=weekly_volumes,
            peak_volume_km=base_volume_km,
            base_volume_km=base_volume_km,
        )

    def generate_base_building(
        self,
        athlete_id: UUID,
        start_date: date,
        current_volume_km: Optional[float] = None,
        days_per_week: int = 6,
    ) -> NoRacePlan:
        """
        Generate a 4-week base building plan.

        Volume progresses 10% over 3 weeks, then cutback on week 4.

        Args:
            athlete_id: The athlete's UUID
            start_date: Monday of the first week
            current_volume_km: Starting weekly volume (if None, derived from history)
            days_per_week: Number of training days per week (4-7)
        """
        if current_volume_km is None:
            current_volume_km = self._derive_current_volume(athlete_id)

        # Progressive volume: 100%, 105%, 110%, 85% (cutback)
        progression = [1.00, 1.05, 1.10, 0.85]
        weekly_volumes = [round(current_volume_km * p, 1) for p in progression]

        workouts = []
        for week_idx in range(4):
            week_start = start_date + timedelta(weeks=week_idx)
            week_workouts = self._build_week(
                week_start=week_start,
                week_number=week_idx + 1,
                weekly_km=weekly_volumes[week_idx],
                template=BASE_BUILDING_WEEK,
                phase="base",
                days_per_week=days_per_week,
            )
            workouts.extend(week_workouts)

        return NoRacePlan(
            mode="base_building",
            athlete_id=athlete_id,
            start_date=start_date,
            end_date=start_date + timedelta(weeks=4) - timedelta(days=1),
            total_weeks=4,
            workouts=workouts,
            weekly_volumes_km=weekly_volumes,
            peak_volume_km=max(weekly_volumes),
            base_volume_km=current_volume_km,
        )

    def _build_week(
        self,
        week_start: date,
        week_number: int,
        weekly_km: float,
        template: list,
        phase: str,
        days_per_week: int = 6,
    ) -> List[NoRaceWorkout]:
        """Build a week of workouts from a template and volume target."""
        workouts = []

        # Filter template to match days_per_week
        # Always keep: long run (Sun), threshold/hills (mid-week), at least 2 easy
        active_days = [t for t in template if t[2] > 0]  # Skip rest days
        if len(active_days) > days_per_week:
            # Prioritize: long, threshold/hills, strides, easy
            priority = {"long": 0, "threshold": 1, "hills": 1, "strides": 2, "easy": 3}
            active_days.sort(key=lambda t: priority.get(t[1], 4))
            active_days = active_days[:days_per_week]

        # Renormalize percentages
        total_pct = sum(t[2] for t in active_days)
        if total_pct <= 0:
            total_pct = 1.0

        for day_idx, wtype, pct, title, description in active_days:
            distance_km = round(weekly_km * (pct / total_pct), 1)
            # Estimate duration from distance (assume ~5:30/km for easy, 5:00 for quality)
            pace_min_per_km = 5.0 if wtype in ("threshold",) else 5.5
            duration_min = int(distance_km * pace_min_per_km)

            workouts.append(NoRaceWorkout(
                date=week_start + timedelta(days=day_idx),
                week_number=week_number,
                day_of_week=day_idx,
                workout_type=wtype,
                title=title,
                description=description,
                target_distance_km=distance_km,
                target_duration_minutes=duration_min,
                phase=phase,
            ))

        return workouts

    def _derive_maintenance_volume(self, athlete_id: UUID) -> float:
        """
        Derive maintenance volume from the athlete's last plan peak.

        Maintenance = 80% of the last build's peak weekly volume.
        Falls back to recent activity average if no plan exists.
        """
        from models import TrainingPlan

        last_plan = (
            self.db.query(TrainingPlan)
            .filter(
                TrainingPlan.athlete_id == athlete_id,
                TrainingPlan.status.in_(["completed", "active"]),
            )
            .order_by(TrainingPlan.plan_end_date.desc())
            .first()
        )

        if last_plan and last_plan.baseline_weekly_volume_km:
            # 80% of the plan's baseline volume
            return round(float(last_plan.baseline_weekly_volume_km) * 0.80, 1)

        # Fallback: derive from recent activity volume
        return self._derive_current_volume(athlete_id)

    def _derive_current_volume(self, athlete_id: UUID) -> float:
        """
        Derive current weekly volume from the last 14 days of activities.

        Returns average weekly km, with a minimum floor of 20km.
        """
        from models import Activity
        from datetime import datetime

        lookback = date.today() - timedelta(days=14)
        activities = (
            self.db.query(Activity)
            .filter(
                Activity.athlete_id == athlete_id,
                Activity.start_time >= datetime.combine(lookback, datetime.min.time()),
                Activity.distance_m.isnot(None),
            )
            .all()
        )

        total_km = sum(float(a.distance_m or 0) / 1000.0 for a in activities)
        weekly_avg = total_km / 2.0  # 14 days = 2 weeks

        return max(20.0, round(weekly_avg, 1))


# ---------------------------------------------------------------------------
# Plan persistence
# ---------------------------------------------------------------------------

def save_no_race_plan(
    plan: NoRacePlan,
    db: Session,
) -> UUID:
    """
    Persist a no-race plan to the database.

    Creates a TrainingPlan and PlannedWorkout records.
    The plan_type is 'maintenance' or 'base_building'.

    Returns:
        UUID of the created TrainingPlan
    """
    from models import TrainingPlan, PlannedWorkout

    # Create the training plan record
    db_plan = TrainingPlan(
        athlete_id=plan.athlete_id,
        name=f"{'Maintenance' if plan.mode == 'maintenance' else 'Base Building'} Plan",
        status="active",
        goal_race_date=plan.end_date,  # No race — use plan end date
        goal_race_distance_m=0,         # No race distance
        plan_start_date=plan.start_date,
        plan_end_date=plan.end_date,
        total_weeks=plan.total_weeks,
        plan_type=plan.mode,            # 'maintenance' or 'base_building'
        generation_method="no_race_mode",
        baseline_weekly_volume_km=plan.base_volume_km,
    )
    db.add(db_plan)
    db.flush()

    # Create planned workouts
    for workout in plan.workouts:
        db_workout = PlannedWorkout(
            plan_id=db_plan.id,
            athlete_id=plan.athlete_id,
            scheduled_date=workout.date,
            week_number=workout.week_number,
            day_of_week=workout.day_of_week,
            workout_type=workout.workout_type,
            title=workout.title,
            description=workout.description,
            phase=workout.phase,
            target_distance_km=workout.target_distance_km,
            target_duration_minutes=workout.target_duration_minutes,
        )
        db.add(db_workout)

    db.flush()

    logger.info(
        f"Created {plan.mode} plan for athlete {plan.athlete_id}: "
        f"{len(plan.workouts)} workouts, "
        f"{plan.total_weeks} weeks, "
        f"volume {plan.base_volume_km:.1f} km/week"
    )

    return db_plan.id


def refresh_rolling_plan(
    athlete_id: UUID,
    db: Session,
) -> Optional[UUID]:
    """
    Refresh a rolling no-race plan by extending it by one week.

    Called weekly (e.g., by the morning intelligence task on Mondays).
    Generates the next week's workouts and archives the oldest week.

    Returns:
        Plan UUID if refreshed, None if no active no-race plan found.
    """
    from models import TrainingPlan, PlannedWorkout

    # Find active no-race plan
    active_plan = (
        db.query(TrainingPlan)
        .filter(
            TrainingPlan.athlete_id == athlete_id,
            TrainingPlan.status == "active",
            TrainingPlan.plan_type.in_(["maintenance", "base_building"]),
        )
        .order_by(TrainingPlan.created_at.desc())
        .first()
    )

    if not active_plan:
        return None

    # Determine mode and generate next week
    generator = NoRaceModeGenerator(db)
    mode = active_plan.plan_type

    # Calculate next week's start (plan_end_date + 1 day)
    next_week_start = active_plan.plan_end_date + timedelta(days=1)
    base_volume = float(active_plan.baseline_weekly_volume_km or 40.0)

    if mode == "maintenance":
        # Maintenance: flat volume
        weekly_km = base_volume
        template = MAINTENANCE_WEEK
        phase = "maintenance"
    else:
        # Base building: determine progression week (cycle of 4)
        # Count existing weeks to determine position in cycle
        existing_weeks = (
            db.query(PlannedWorkout.week_number)
            .filter(PlannedWorkout.plan_id == active_plan.id)
            .distinct()
            .count()
        )
        cycle_position = existing_weeks % 4  # 0, 1, 2, 3
        progression = [1.00, 1.05, 1.10, 0.85]
        weekly_km = round(base_volume * progression[cycle_position], 1)
        template = BASE_BUILDING_WEEK
        phase = "base"

    # Generate the week
    new_workouts = generator._build_week(
        week_start=next_week_start,
        week_number=existing_weeks + 1 if mode == "base_building" else active_plan.total_weeks + 1,
        weekly_km=weekly_km,
        template=template,
        phase=phase,
    )

    # Update plan end date
    active_plan.plan_end_date = next_week_start + timedelta(days=6)
    active_plan.total_weeks += 1

    # Add workouts
    for workout in new_workouts:
        db_workout = PlannedWorkout(
            plan_id=active_plan.id,
            athlete_id=athlete_id,
            scheduled_date=workout.date,
            week_number=workout.week_number,
            day_of_week=workout.day_of_week,
            workout_type=workout.workout_type,
            title=workout.title,
            description=workout.description,
            phase=workout.phase,
            target_distance_km=workout.target_distance_km,
            target_duration_minutes=workout.target_duration_minutes,
        )
        db.add(db_workout)

    db.flush()

    logger.info(
        f"Refreshed {mode} plan for {athlete_id}: "
        f"added week starting {next_week_start}, "
        f"volume {weekly_km:.1f} km"
    )

    return active_plan.id
