"""
Public week-generation interface for the plan framework.

This module exposes `generate_plan_week` as the stable public API consumed by
both `PlanGenerator._generate_workouts` (via delegation) and by
`ConstraintAwarePlanner` (T3 convergence).

Design: this is a thin facade over `PlanGenerator._generate_week`. The
implementation lives in `generator.py`; moving it here in a future pass
(T5+) would make `_generate_week` a literal one-liner wrapper, but the
interface contract is established here for T3.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from .phase_builder import TrainingPhase


def generate_plan_week(
    week: int,
    phase: TrainingPhase,
    week_in_phase: int,
    weekly_volume: float,
    days_per_week: int,
    distance: str,
    tier: str,
    duration_weeks: int,
    *,
    is_cutback: bool = False,
    is_mp_long_week: bool = False,
    is_hmp_long_week: bool = False,
    is_mp_medium_long_week: bool = False,
    mp_week: int = 1,
    paces: Optional[Any] = None,
    athlete_ctx: Optional[Dict[str, Any]] = None,
    easy_long_state: Optional[Dict[str, Any]] = None,
    history_override: bool = False,
    start_date: Optional[date] = None,
    prev_mp_miles: Optional[int] = None,
    prev_threshold_continuous_min: Optional[int] = None,
    prev_threshold_intervals: Optional[Tuple[int, int]] = None,
) -> List[Any]:
    """
    Public interface for single-week plan generation.

    Consumed by both `PlanGenerator._generate_workouts` (standard / semi-custom
    paths) and `ConstraintAwarePlanner` (T3 convergence).

    Returns List[GeneratedWorkout].

    Args:
        week: 1-indexed global week number within the plan.
        phase: TrainingPhase from PhaseBuilder for this week.
        week_in_phase: 1-indexed position within the phase.
        weekly_volume: Target weekly mileage for this week.
        days_per_week: Number of training days (3-7). Drives WEEKLY_STRUCTURES lookup.
        distance: Goal race distance string (e.g., "marathon", "10k").
        tier: Volume tier string (e.g., "mid", "high").
        duration_weeks: Total plan length in weeks.
        is_cutback: Whether this is a planned cutback week.
        is_mp_long_week: Whether Sunday should be a long_mp run.
        is_hmp_long_week: Whether Sunday should be a long_hmp run.
        is_mp_medium_long_week: Whether Tuesday slot should be medium_long_mp.
        mp_week: Sequential MP long run count for progression (1=first, 2=second…).
        paces: Optional TrainingPaces for athlete-specific pace descriptions.
        athlete_ctx: Optional dict of athlete context flags.
        easy_long_state: Optional dict tracking previous/floor long run miles.
        history_override: Whether to allow above-standard spike protection.
        start_date: First day of the week (Monday). Used to date each workout.
        prev_mp_miles: Previous MP long run distance for progression copy.
        prev_threshold_continuous_min: Previous threshold continuous duration.
        prev_threshold_intervals: Previous threshold interval (reps, duration).
    """
    # Late import to avoid circular dependencies at module load time.
    from .generator import PlanGenerator

    gen = PlanGenerator()
    # Resolve the daily slot structure from the shared WEEKLY_STRUCTURES table.
    structure = gen.WEEKLY_STRUCTURES.get(days_per_week, gen.WEEKLY_STRUCTURES[6])

    return gen._generate_week(
        week=week,
        phase=phase,
        week_in_phase=week_in_phase,
        is_mp_long_week=is_mp_long_week,
        is_hmp_long_week=is_hmp_long_week,
        is_mp_medium_long_week=is_mp_medium_long_week,
        weekly_volume=weekly_volume,
        tier=tier,
        distance=distance,
        days_per_week=days_per_week,
        structure=structure,
        start_date=start_date,
        paces=paces,
        is_cutback=is_cutback,
        mp_week=mp_week,
        athlete_ctx=athlete_ctx,
        duration_weeks=duration_weeks,
        easy_long_state=easy_long_state,
        history_override=history_override,
        prev_mp_miles=prev_mp_miles,
        prev_threshold_continuous_min=prev_threshold_continuous_min,
        prev_threshold_intervals=prev_threshold_intervals,
    )
