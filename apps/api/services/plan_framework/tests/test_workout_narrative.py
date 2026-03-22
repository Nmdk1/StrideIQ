"""P3: grounded plan narrative copy (MP long + threshold)."""

from __future__ import annotations

from typing import List, Optional, Tuple

import pytest

from services.plan_framework.generator import (
    GeneratedWorkout,
    PlanGenerator,
    _extract_mp_miles_from_long_mp,
    _extract_threshold_continuous_minutes,
    _extract_threshold_intervals_shape,
)
from services.plan_framework.workout_narrative import (
    hmp_long_copy,
    mp_long_option_a_copy,
    mp_long_option_b_copy,
    mp_touch_copy,
    threshold_continuous_description,
    threshold_intervals_description,
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


def test_threshold_continuous_first_vs_progression():
    d0 = threshold_continuous_description(20, None)
    assert "first threshold block" in d0.lower()
    assert "building from" not in d0.lower()
    d1 = threshold_continuous_description(25, 20)
    assert "building from 20 to 25" in d1.lower()


def test_threshold_intervals_progression_reps_only():
    d = threshold_intervals_description(5, 5, (4, 5))
    assert "5x5" in d
    assert "4x5" in d
    assert "more reps" in d.lower()


def test_extract_threshold_helpers():
    cw = GeneratedWorkout(
        week=1,
        day=0,
        day_name="Mon",
        date=None,
        workout_type="threshold",
        title="",
        description="",
        phase="build",
        phase_name="",
        distance_miles=5.0,
        duration_minutes=45,
        pace_description="",
        segments=[
            {"type": "warmup", "distance_miles": 2, "pace": "easy"},
            {"type": "threshold", "duration_min": 20, "pace": "threshold", "distance_miles": 3.0},
            {"type": "cooldown", "distance_miles": 1, "pace": "easy"},
        ],
        option="A",
    )
    assert _extract_threshold_continuous_minutes(cw) == 20
    iw = GeneratedWorkout(
        week=1,
        day=0,
        day_name="Mon",
        date=None,
        workout_type="threshold_intervals",
        title="",
        description="",
        phase="build",
        phase_name="",
        distance_miles=6.0,
        duration_minutes=50,
        pace_description="",
        segments=[
            {"type": "warmup", "distance_miles": 2, "pace": "easy"},
            {
                "type": "intervals",
                "reps": 4,
                "duration_min": 5,
                "rest_min": 2,
                "pace": "threshold",
                "distance_miles": 3.4,
            },
            {"type": "cooldown", "distance_miles": 1.5, "pace": "easy"},
        ],
        option="A",
    )
    assert _extract_threshold_intervals_shape(iw) == (4, 5)


def test_scaled_threshold_variant_ids_unchanged():
    scaler = WorkoutScaler()
    t = scaler.scale_workout(
        "threshold",
        weekly_volume=50,
        tier="mid",
        phase="build",
        week_in_phase=2,
        prev_threshold_continuous_min=15,
    )
    from services.plan_framework.workout_variant_dispatch import resolve_workout_variant_id

    assert resolve_workout_variant_id(t.workout_type, t.title, t.segments) == (
        "threshold_continuous_progressive"
    )
    assert t.title.startswith("Threshold Run:")
    assert "building from" in t.description.lower()

    s = scaler.scale_workout(
        "threshold_intervals",
        weekly_volume=50,
        tier="mid",
        phase="build",
        week_in_phase=2,
        prev_threshold_intervals=(4, 5),
    )
    assert resolve_workout_variant_id(s.workout_type, s.title, s.segments) in (
        "threshold_intervals_5_to_6_min",
        "threshold_intervals_8_to_12_min",
    )
    assert s.title.startswith("Threshold Intervals:")


def test_generate_workouts_passes_prev_threshold_intervals_across_weeks(monkeypatch):
    """
    Regression (P3.1): `prev_threshold_intervals` must be passed from `_generate_workouts`
    into each `_generate_week` and refreshed after each week — not only initialized.
    """
    calls: List[Tuple[int, Optional[Tuple[int, int]]]] = []
    orig = PlanGenerator._generate_week

    def spy(self, *a, **kw):
        calls.append((kw["week"], kw.get("prev_threshold_intervals")))
        return orig(self, *a, **kw)

    monkeypatch.setattr(PlanGenerator, "_generate_week", spy)
    gen = PlanGenerator(None)
    gen.generate_standard(
        distance="marathon",
        duration_weeks=24,
        tier="mid",
        days_per_week=6,
    )
    by_week = dict(calls)
    # Canonical template: first threshold_intervals in week 5 (4x5); week 6 must see (4, 5).
    assert by_week.get(5) is None
    assert by_week.get(6) == (4, 5)


def test_marathon_plan_threshold_intervals_progression_after_first():
    """Marathon template often schedules one continuous T; intervals repeat with progression."""
    gen = PlanGenerator(None)
    plan = gen.generate_standard(
        distance="marathon",
        duration_weeks=24,
        tier="mid",
        days_per_week=6,
    )
    ints = [w for w in plan.workouts if w.workout_type == "threshold_intervals"]
    assert len(ints) >= 2
    assert "first threshold intervals" in ints[0].description.lower()
    later = [w.description.lower() for w in ints[1:]]
    assert any(
        "progressing from" in d or "same prescription as last time" in d for d in later
    ), f"expected progression or repeat copy in later intervals: {later[:2]}"


def test_marathon_plan_threshold_intervals_have_coach_opening():
    gen = PlanGenerator(None)
    plan = gen.generate_standard(
        distance="marathon",
        duration_weeks=24,
        tier="mid",
        days_per_week=6,
    )
    ints = [w for w in plan.workouts if w.workout_type == "threshold_intervals"]
    assert ints
    assert (
        "first threshold intervals" in ints[0].description.lower()
        or "progressing from" in ints[0].description.lower()
    )


def test_mp_touch_copy_consolidation_tone():
    _, desc = mp_touch_copy(3.0, 7.0)
    assert "cutback consolidation" in desc.lower()
    assert "dress rehearsal" not in desc.lower()


def test_hmp_long_title_prefix_for_variant_dispatch():
    title, desc = hmp_long_copy(14.0, 11.0, 3.0, week_in_phase=1)
    assert title.startswith("Long Run with HMP:")
    assert "first hmp segment" in desc.lower()
    from services.plan_framework.workout_variant_dispatch import resolve_workout_variant_id

    assert (
        resolve_workout_variant_id("long_hmp", title, None)
        == "long_hmp_finish_half_marathon"
    )


def test_scaled_mp_touch_variant_id_stable():
    scaler = WorkoutScaler()
    s = scaler.scale_workout("mp_touch", weekly_volume=50, tier="mid", phase="build", week_in_phase=1)
    from services.plan_framework.workout_variant_dispatch import resolve_workout_variant_id

    assert (
        resolve_workout_variant_id(s.workout_type, s.title, s.segments)
        == "long_mp_continuous_marathon"
    )
    assert "cutback consolidation" in s.description.lower()
