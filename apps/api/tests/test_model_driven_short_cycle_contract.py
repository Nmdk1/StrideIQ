from datetime import date
from unittest.mock import MagicMock

from services.model_driven_plan_generator import ModelDrivenPlanGenerator
from services.optimal_load_calculator import OptimalLoadCalculator, TrainingPhase


def test_optimal_load_short_cycle_limits_taper_and_preserves_build():
    calc = OptimalLoadCalculator(db=MagicMock())
    assert calc._clamp_taper_weeks_for_cycle_length(weeks_to_race=5, taper_weeks=3) == 1
    assert calc._base_weeks_for_cycle(build_weeks=2) == 0


def test_model_driven_race_week_uses_requested_weekday():
    gen = ModelDrivenPlanGenerator(db=MagicMock())
    # 2026-05-02 is Saturday (weekday=5)
    structure = gen._get_race_week_structure(race_day_of_week=5)
    race_days = [s for s in structure if s["type"] == "race"]
    assert len(race_days) == 1
    assert race_days[0]["day"] == 5
    # No workouts after race day.
    assert all(s["type"] == "rest" for s in structure if s["day"] > 5)


def test_model_driven_10k_high_mileage_long_run_not_collapsed():
    gen = ModelDrivenPlanGenerator(db=MagicMock())
    paces = {"e_pace": "8:20/mi", "m_pace": "7:05/mi"}
    baseline = {
        "weekly_miles": 70.0,
        "long_run_miles": 16.0,
        "peak_long_run_miles": 18.0,
        "experience_level": "experienced",
        "mp_long_run_miles": 0.0,
    }
    day = gen._create_day_plan(
        date=date(2026, 4, 5),
        day_of_week="Sunday",
        workout_type="long",
        target_tss=80.0,
        paces=paces,
        race_distance="10k",
        phase=TrainingPhase.BUILD,
        baseline=baseline,
        week_number=2,
        total_weeks=5,
    )
    assert day.workout_type == "long_run"
    assert day.target_miles >= 15.0
