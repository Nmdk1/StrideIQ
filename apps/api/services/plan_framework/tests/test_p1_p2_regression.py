"""
Focused regression tests for P1 easy-long curve/spike and P2 weighted easy fill.

Broader coverage lives in tests/test_plan_validation_matrix.py; these assert
specific coaching invariants called out in code review.
"""

from __future__ import annotations

from datetime import date

import pytest

from services.plan_framework.generator import (
    GeneratedWorkout,
    PlanGenerator,
    _easy_fill_adjacency_weight,
)
from services.plan_framework.workout_scaler import WorkoutScaler, spike_step_miles_and_pct


class _DayStub:
    __slots__ = ("workout_type",)

    def __init__(self, workout_type: str) -> None:
        self.workout_type = workout_type


def test_mp_touch_counts_as_quality_for_easy_fill_adjacency() -> None:
    """Day after mp_touch must downweight the next easy (P2 coherence)."""
    by_day = {
        2: _DayStub("mp_touch"),
        3: _DayStub("easy"),
    }
    assert _easy_fill_adjacency_weight(3, by_day) == pytest.approx(0.7)


def test_spike_cap_mid_tier_math() -> None:
    """Spike ceiling = min(prev + step, prev * (1 + pct)) for mid."""
    step, pct = spike_step_miles_and_pct("mid", history_override=False)
    assert step == 2.0 and pct == pytest.approx(0.10)
    prev = 14.0
    cap = min(prev + step, prev * (1.0 + pct))
    assert cap == pytest.approx(15.4)

    scaler = WorkoutScaler()
    sw = scaler._scale_long_run(
        70.0,
        "mid",
        "marathon",
        plan_week=14,
        duration_weeks=18,
        is_cutback=False,
        previous_easy_long_mi=prev,
        history_override=False,
    )
    assert float(sw.total_distance_miles) <= cap + 0.01


def test_cutback_reduces_easy_long_vs_same_week_non_cutback() -> None:
    scaler = WorkoutScaler()
    base = scaler._scale_long_run(
        60.0,
        "mid",
        "marathon",
        plan_week=10,
        duration_weeks=18,
        is_cutback=False,
        previous_easy_long_mi=None,
        history_override=False,
    )
    cut = scaler._scale_long_run(
        60.0,
        "mid",
        "marathon",
        plan_week=10,
        duration_weeks=18,
        is_cutback=True,
        previous_easy_long_mi=None,
        history_override=False,
    )
    assert float(cut.total_distance_miles) < float(base.total_distance_miles)


def test_taper_week_shortens_easy_long_vs_peak_build_week() -> None:
    scaler = WorkoutScaler()
    build_last = scaler._scale_long_run(
        55.0,
        "mid",
        "marathon",
        plan_week=16,
        duration_weeks=18,
        is_cutback=False,
        previous_easy_long_mi=12.0,
        history_override=False,
    )
    taper = scaler._scale_long_run(
        55.0,
        "mid",
        "marathon",
        plan_week=17,
        duration_weeks=18,
        is_cutback=False,
        previous_easy_long_mi=12.0,
        history_override=False,
    )
    assert float(taper.total_distance_miles) < float(build_last.total_distance_miles)


def _minimal_gw(day: int, workout_type: str, miles: float) -> GeneratedWorkout:
    return GeneratedWorkout(
        week=1,
        day=day,
        day_name="Mon",
        date=None,
        workout_type=workout_type,
        title="",
        description="",
        phase="threshold",
        phase_name="",
        distance_miles=miles,
        duration_minutes=0,
        pace_description="",
        segments=None,
        option="A",
    )


def test_weighted_easy_fill_preserves_week_total_and_orders_after_quality() -> None:
    """
    One quality day, two easy days (one following quality), one long.
    Post-quality easy should receive fewer miles than the standalone easy.
    """
    gen = PlanGenerator()
    weekly = 40.0
    week = [
        _minimal_gw(0, "threshold", 10.0),
        _minimal_gw(1, "easy", 5.0),
        _minimal_gw(2, "easy", 5.0),
        _minimal_gw(6, "long", 12.0),
    ]
    gen._apply_weighted_easy_volume_fill(week, weekly)

    by_day = {w.day: w for w in week}
    d1 = float(by_day[1].distance_miles or 0)
    d2 = float(by_day[2].distance_miles or 0)
    assert d1 < d2, "day after quality should be shorter than standalone easy"
    total = sum(float(w.distance_miles or 0) for w in week)
    assert total == pytest.approx(weekly, abs=0.2)
    for w in week:
        if w.workout_type in {"easy", "easy_strides", "recovery", "medium_long"}:
            assert 3.0 <= float(w.distance_miles or 0) <= 12.0


def test_builder_spike_step_matches_spec() -> None:
    step, pct = spike_step_miles_and_pct("builder", history_override=False)
    assert step == pytest.approx(1.5)
    assert pct == pytest.approx(0.15)


def test_history_override_spike_is_looser_than_mid() -> None:
    s_mid, _ = spike_step_miles_and_pct("mid", history_override=False)
    s_ov, _ = spike_step_miles_and_pct("mid", history_override=True)
    assert s_ov > s_mid
