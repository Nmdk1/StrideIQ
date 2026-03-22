"""P3.0: grounded MP long narrative copy."""

from __future__ import annotations

import pytest

from services.plan_framework.generator import (
    GeneratedWorkout,
    PlanGenerator,
    _extract_mp_miles_from_long_mp,
)
from services.plan_framework.workout_narrative import (
    mp_long_option_a_copy,
    mp_long_option_b_copy,
)
from services.plan_framework.workout_scaler import WorkoutScaler


def test_mp_long_option_a_first_has_no_comparative_phrase():
    title, desc = mp_long_option_a_copy(
        mp_week=1,
        mp_miles=6.0,
        mp_structure="2x3 miles at MP with 1 mile easy between",
        total_miles=12.0,
        prev_mp_miles=None,
    )
    assert "week 1" in title.lower()
    assert "first mp long" in desc.lower()
    assert "building from" not in desc.lower()


def test_mp_long_option_a_comparative_uses_prev_and_current():
    title, desc = mp_long_option_a_copy(
        mp_week=2,
        mp_miles=8.0,
        mp_structure="8 miles continuous at MP",
        total_miles=14.0,
        prev_mp_miles=6,
    )
    assert "building from 6 to 8" in desc.lower()
    assert "week 2" in title.lower()


def test_mp_long_option_b_comparative():
    _, desc = mp_long_option_b_copy(
        mp_week=2,
        reps=4,
        rep_distance=2,
        total_miles=14.0,
        mp_miles=8.0,
        prev_mp_miles=6,
    )
    assert "building from 6 to 8" in desc.lower()
    assert "option b" in desc.lower()


def test_extract_mp_miles_from_long_mp_segment():
    w = GeneratedWorkout(
        week=1,
        day=0,
        day_name="Mon",
        date=None,
        workout_type="long_mp",
        title="",
        description="",
        phase="marathon_specific",
        phase_name="",
        distance_miles=14.0,
        duration_minutes=100,
        pace_description="",
        segments=[
            {"type": "warmup", "distance_miles": 3, "pace": "easy"},
            {"type": "marathon_pace", "distance_miles": 8, "pace": "MP"},
            {"type": "cooldown", "distance_miles": 3, "pace": "easy"},
        ],
        option="A",
    )
    assert _extract_mp_miles_from_long_mp(w) == 8


def test_marathon_plan_second_mp_long_narrative_references_progression():
    gen = PlanGenerator(None)
    plan = gen.generate_standard(
        distance="marathon",
        duration_weeks=24,
        tier="mid",
        days_per_week=6,
    )
    mp_workouts = [w for w in plan.workouts if w.workout_type == "long_mp"]
    assert len(mp_workouts) >= 2
    first, second = mp_workouts[0], mp_workouts[1]
    assert "first mp long" in first.description.lower()
    assert "building from" in second.description.lower()


@pytest.mark.parametrize("mp_week", [1, 2])
def test_scaled_mp_long_variant_ids_stable(mp_week: int):
    """Registry dispatch uses workout_type for long_mp — titles may evolve."""
    scaler = WorkoutScaler()
    prev = None if mp_week <= 1 else 6
    s = scaler.scale_workout(
        "long_mp",
        weekly_volume=55,
        tier="mid",
        phase="marathon_specific",
        week_in_phase=1,
        distance="marathon",
        mp_week=mp_week,
        prev_mp_miles=prev,
    )
    from services.plan_framework.workout_variant_dispatch import resolve_workout_variant_id

    assert resolve_workout_variant_id(s.workout_type, s.title, s.segments) == (
        "long_mp_continuous_marathon"
    )
    assert s.option_b is not None
    assert (
        resolve_workout_variant_id(
            s.option_b.workout_type, s.option_b.title, s.option_b.segments
        )
        == "long_mp_intervals_in_long"
    )
