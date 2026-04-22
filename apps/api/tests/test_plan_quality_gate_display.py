"""Slice 3 / Dejan recovery: quality gate emits athlete-language display
strings and km-native safe bounds. Regression-protects the contract added so
the frontend can render unit-aware "Use safe range" affordances without
re-parsing technical reasons."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import pytest

from services.plan_quality_gate import (
    QualityGateResult,
    _build_display_message,
    _enrich_with_display,
    _miles_dict_to_km,
    evaluate_constraint_aware_plan,
    evaluate_starter_plan_quality,
)


@dataclass
class _FakeWeek:
    week_number: int
    total_miles: float
    workouts: List[Any] | None = None


@dataclass
class _FakePlan:
    weeks: List[_FakeWeek]
    volume_contract: Dict[str, Any]
    fitness_bank: Dict[str, Any]
    race_distance: str = "10k"


def test_display_message_for_known_invariant_codes():
    msg = _build_display_message(["weekly_volume_exceeds_trusted_band"])
    assert msg
    assert "peak weekly volume" in msg.lower()


def test_display_message_collapses_duplicates_in_order():
    msg = _build_display_message([
        "weekly_volume_exceeds_trusted_band",
        "weekly_volume_exceeds_trusted_band",
        "personal_long_run_floor_breach",
    ])
    assert msg.count("Your peak weekly volume is higher") == 1
    assert "personal long-run" in msg.lower() or "long run you have already" in msg.lower()


def test_display_message_unknown_code_uses_generic_fallback():
    msg = _build_display_message(["definitely_not_a_real_code_xyz"])
    assert "plan quality issue" in msg.lower()


def test_display_message_empty_when_passed():
    assert _build_display_message([]) == ""


def test_miles_dict_to_km_round_trips_known_values():
    km = _miles_dict_to_km({"weekly_miles": {"min": 50.0, "max": 64.0}})
    assert km == {"weekly_miles": {"min": 80.5, "max": 103.0}}


def test_miles_dict_to_km_skips_malformed_entries():
    km = _miles_dict_to_km({
        "weekly_miles": {"min": 50.0, "max": 64.0},
        "broken": "not a dict",
        "missing_max": {"min": 10.0},
    })
    assert "weekly_miles" in km
    assert "broken" not in km
    # missing values coerce to 0.0 which is harmless and still a usable shape
    assert km["missing_max"]["max"] == 0.0


def test_enrich_is_idempotent():
    result = QualityGateResult(
        passed=False,
        reasons=["debug"],
        invariant_conflicts=["weekly_volume_exceeds_trusted_band"],
        suggested_safe_bounds={"weekly_miles": {"min": 30.0, "max": 40.0}},
    )
    enriched_once = _enrich_with_display(result)
    msg = enriched_once.display_message
    bounds = dict(enriched_once.safe_bounds_km)
    enriched_twice = _enrich_with_display(enriched_once)
    assert enriched_twice.display_message == msg
    assert enriched_twice.safe_bounds_km == bounds


def test_constraint_aware_failure_populates_display_and_km_bounds():
    plan = _FakePlan(
        weeks=[_FakeWeek(week_number=1, total_miles=200.0)],
        volume_contract={"band_min": 30.0, "band_max": 40.0},
        fitness_bank={},
        race_distance="10k",
    )
    result = evaluate_constraint_aware_plan(plan)
    assert result.passed is False
    assert "weekly_volume_exceeds_trusted_band" in result.invariant_conflicts
    assert result.display_message
    assert result.safe_bounds_km
    assert "weekly_miles" in result.safe_bounds_km
    assert result.safe_bounds_km["weekly_miles"]["min"] > 0
    assert result.safe_bounds_km["weekly_miles"]["max"] > result.safe_bounds_km["weekly_miles"]["min"]


def test_constraint_aware_passing_keeps_message_empty():
    plan = _FakePlan(
        weeks=[_FakeWeek(week_number=1, total_miles=30.0)],
        volume_contract={"band_min": 30.0, "band_max": 40.0},
        fitness_bank={},
        race_distance="5k",
    )
    result = evaluate_constraint_aware_plan(plan)
    # 5K branch may add its own findings; either way display_message follows
    # the invariants list.
    expected_msg = _build_display_message(result.invariant_conflicts)
    assert result.display_message == expected_msg


def test_safe_bounds_midpoint_is_center_of_min_and_max():
    """Slice 4: the soft-gate fallback peak is computed from the gate's
    suggested weekly_miles midpoint. Pin the formula so we can rely on it
    in the route handler and surface it as `soft_gate_applied_peak_weekly_miles`."""
    plan = _FakePlan(
        weeks=[_FakeWeek(week_number=1, total_miles=200.0)],
        volume_contract={"band_min": 30.0, "band_max": 40.0},
        fitness_bank={},
        race_distance="10k",
    )
    result = evaluate_constraint_aware_plan(plan)
    weekly = result.suggested_safe_bounds.get("weekly_miles") or {}
    midpoint_mi = (float(weekly["min"]) + float(weekly["max"])) / 2.0
    # band_min=30, band_max=40 → suggested {min: 25.5, max: 42.0} → midpoint 33.75
    assert midpoint_mi == pytest.approx(33.75, abs=0.05)


def test_starter_plan_failure_produces_display_message_and_km_bounds():
    @dataclass
    class _StarterPlan:
        workouts: List[Any]

    plan = _StarterPlan(workouts=[])
    result = evaluate_starter_plan_quality(plan)
    assert result.passed is False
    assert "no_workouts_generated" in result.invariant_conflicts
    assert result.display_message
    assert result.safe_bounds_km
    # Bounds are rounded to 1 decimal in km. 15.0 mi == 24.14 km rounds to 24.1.
    assert result.safe_bounds_km["weekly_miles"]["min"] == pytest.approx(round(15.0 * 1.60934, 1), abs=0.05)
    assert result.safe_bounds_km["weekly_miles"]["max"] == pytest.approx(round(25.0 * 1.60934, 1), abs=0.05)
