"""
Load-context wiring contract for constraint-aware planner (T3 version).

T3 replaced WorkoutPrescriptionGenerator with generate_plan_week. The
load_context now feeds easy_long_state["floor_mi"] rather than
WorkoutPrescriptionGenerator.__init__ kwargs. These tests verify the
new wiring contract:

  1. l30_max_easy_long_mi from load_ctx becomes the week-1 easy-long floor.
  2. history_override tag is preserved in prediction_rationale_tags.
  3. load_context failure falls back safely to bank.current_long_run_miles.
"""
from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import MagicMock, patch

from services.constraint_aware_planner import ConstraintAwarePlanner, generate_constraint_aware_plan
from services.fitness_bank import ConstraintType, ExperienceLevel, FitnessBank, RacePerformance


def _bank() -> FitnessBank:
    race = RacePerformance(
        date=date.today() - timedelta(days=30),
        distance="10k",
        distance_m=10000.0,
        finish_time_seconds=2400,
        pace_per_mile=6.4,
        rpi=54.0,
    )
    return FitnessBank(
        athlete_id=str(uuid4()),
        peak_weekly_miles=68.0,
        peak_monthly_miles=260.0,
        peak_long_run_miles=18.0,
        peak_mp_long_run_miles=12.0,
        peak_threshold_miles=8.0,
        peak_ctl=82.0,
        race_performances=[race],
        best_rpi=54.0,
        best_race=race,
        current_weekly_miles=60.0,
        current_ctl=75.0,
        current_atl=70.0,
        weeks_since_peak=6,
        current_long_run_miles=14.0,
        average_long_run_miles=13.0,
        tau1=38.0,
        tau2=8.0,
        experience_level=ExperienceLevel.EXPERIENCED,
        constraint_type=ConstraintType.NONE,
        constraint_details=None,
        is_returning_from_break=False,
        typical_long_run_day=6,
        typical_quality_day=3,
        typical_rest_days=[0],
        weeks_to_80pct_ctl=0,
        weeks_to_race_ready=2,
        sustainable_peak_weekly=64.0,
        recent_quality_sessions_28d=4,
        recent_8w_median_weekly_miles=61.0,
        recent_16w_p90_weekly_miles=66.0,
        recent_8w_p75_long_run_miles=15.0,
        recent_16w_p50_long_run_miles=14.0,
        recent_16w_run_count=36,
        peak_confidence="high",
    )


def test_constraint_aware_passes_load_context_into_workout_generator(monkeypatch):
    """
    T3 wiring: l30_max_easy_long_mi flows into easy_long_state["floor_mi"] for
    the first week's call to generate_plan_week. The d4_history_override tag
    must be present when load_ctx.history_override_easy_long is True.
    """
    bank = _bank()
    floor_captured = {}

    monkeypatch.setattr("services.constraint_aware_planner.get_fitness_bank", lambda *_: bank)
    monkeypatch.setattr(
        "services.constraint_aware_planner.build_load_context",
        lambda *_args, **_kwargs: SimpleNamespace(
            l30_max_easy_long_mi=15.5,
            history_override_easy_long=True,
            count_long_15plus=14,
            count_long_18plus=6,
            recency_last_18plus_days=30,
        ),
    )

    original_gpw = None
    import services.constraint_aware_planner as _cap_mod

    _orig = _cap_mod.generate_plan_week

    def _capturing_gpw(*args, **kwargs):
        if kwargs.get("week") == 1 or (args and args[0] == 1):
            state = kwargs.get("easy_long_state") or {}
            floor_captured["floor_mi"] = state.get("floor_mi")
        return _orig(*args, **kwargs)

    monkeypatch.setattr("services.constraint_aware_planner.generate_plan_week", _capturing_gpw)

    plan = generate_constraint_aware_plan(
        athlete_id=uuid4(),
        race_date=date.today() + timedelta(weeks=10),
        race_distance="10k",
        db=MagicMock(),
    )

    # l30_max_easy_long_mi=15.5 must be the week-1 floor
    assert floor_captured.get("floor_mi") == 15.5, (
        f"Week-1 easy_long_state floor_mi expected 15.5, got {floor_captured.get('floor_mi')}"
    )
    # history_override tag preserved
    assert "d4_history_override" in plan.prediction_rationale_tags


def test_constraint_aware_load_context_failure_falls_back_safely(monkeypatch):
    """
    T3 wiring: when build_load_context raises, the planner falls back to
    bank.current_long_run_miles as the floor and generates the plan without error.
    The d4_history_override tag must NOT be present.
    """
    bank = _bank()
    floor_captured = {}

    monkeypatch.setattr("services.constraint_aware_planner.get_fitness_bank", lambda *_: bank)
    monkeypatch.setattr(
        "services.constraint_aware_planner.build_load_context",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    import services.constraint_aware_planner as _cap_mod
    _orig = _cap_mod.generate_plan_week

    def _capturing_gpw(*args, **kwargs):
        if kwargs.get("week") == 1 or (args and args[0] == 1):
            state = kwargs.get("easy_long_state") or {}
            floor_captured["floor_mi"] = state.get("floor_mi")
        return _orig(*args, **kwargs)

    monkeypatch.setattr("services.constraint_aware_planner.generate_plan_week", _capturing_gpw)

    plan = generate_constraint_aware_plan(
        athlete_id=uuid4(),
        race_date=date.today() + timedelta(weeks=10),
        race_distance="10k",
        db=MagicMock(),
    )

    assert plan is not None, "Plan should generate when load_context fails"
    # Fallback floor is bank.current_long_run_miles (14.0) or average (13.0)
    fallback_floor = floor_captured.get("floor_mi")
    assert fallback_floor is not None, "Fallback floor should be set from bank"
    assert fallback_floor >= bank.average_long_run_miles, (
        f"Fallback floor {fallback_floor} should be >= average_long_run_miles {bank.average_long_run_miles}"
    )
    # No history override tag when load_ctx is unavailable
    assert "d4_history_override" not in plan.prediction_rationale_tags
