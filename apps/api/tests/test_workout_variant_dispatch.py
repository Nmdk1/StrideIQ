"""Phase 3: deterministic workout_variant_id dispatch vs workout_scaler outputs."""

from __future__ import annotations

from pathlib import Path

import pytest

from services.plan_framework.workout_scaler import WorkoutScaler
from services.plan_framework.workout_variant_dispatch import (
    clear_workout_variant_id_cache,
    resolve_workout_variant_id,
)

REGISTRY_PATH = (
    Path(__file__).resolve().parents[3]
    / "_AI_CONTEXT_"
    / "KNOWLEDGE_BASE"
    / "workouts"
    / "variants"
    / "workout_registry.json"
)


@pytest.fixture(autouse=True)
def _reset_registry_cache():
    clear_workout_variant_id_cache()
    yield
    clear_workout_variant_id_cache()


@pytest.mark.skipif(not REGISTRY_PATH.is_file(), reason="workout_registry.json not in workspace")
@pytest.mark.parametrize(
    ("week_in_phase", "expected_id"),
    [
        (1, "threshold_intervals_5_to_6_min"),
        (4, "threshold_intervals_8_to_12_min"),
    ],
)
def test_threshold_intervals_by_week_in_phase(week_in_phase, expected_id):
    scaler = WorkoutScaler()
    s = scaler.scale_workout(
        "threshold_intervals",
        weekly_volume=50,
        tier="mid",
        phase="build",
        week_in_phase=week_in_phase,
    )
    assert resolve_workout_variant_id(s.workout_type, s.title, s.segments) == expected_id


@pytest.mark.skipif(not REGISTRY_PATH.is_file(), reason="workout_registry.json not in workspace")
def test_continuous_threshold_and_long_staples():
    scaler = WorkoutScaler()
    t = scaler.scale_workout(
        "threshold", weekly_volume=50, tier="mid", phase="build", week_in_phase=2
    )
    assert (
        resolve_workout_variant_id(t.workout_type, t.title, t.segments)
        == "threshold_continuous_progressive"
    )
    lng = scaler.scale_workout(
        "long", weekly_volume=50, tier="mid", phase="base", distance="marathon"
    )
    assert (
        resolve_workout_variant_id(lng.workout_type, lng.title, lng.segments)
        == "long_easy_aerobic_staple"
    )


@pytest.mark.skipif(not REGISTRY_PATH.is_file(), reason="workout_registry.json not in workspace")
def test_mp_long_option_b_variant_ids():
    scaler = WorkoutScaler()
    s = scaler.scale_workout(
        "long_mp",
        weekly_volume=55,
        tier="mid",
        phase="build",
        distance="marathon",
        week_in_phase=2,
        mp_week=2,
    )
    assert s.option_b is not None
    assert (
        resolve_workout_variant_id(s.workout_type, s.title, s.segments)
        == "long_mp_continuous_marathon"
    )
    ob = s.option_b
    assert (
        resolve_workout_variant_id(ob.workout_type, ob.title, ob.segments)
        == "long_mp_intervals_in_long"
    )


@pytest.mark.skipif(not REGISTRY_PATH.is_file(), reason="workout_registry.json not in workspace")
def test_generator_sets_workout_variant_ids():
    from services.plan_framework.generator import PlanGenerator

    gen = PlanGenerator(None)
    plan = gen.generate_standard(
        distance="marathon",
        duration_weeks=8,
        tier="mid",
        days_per_week=5,
    )
    non_rest = [w for w in plan.workouts if w.workout_type != "rest"]
    assert non_rest, "expected at least one non-rest workout"
    assert all(w.workout_variant_id is not None for w in non_rest), (
        "framework workouts should resolve a variant id when registry is present"
    )
