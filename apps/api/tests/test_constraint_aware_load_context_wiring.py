from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

from services.constraint_aware_planner import ConstraintAwarePlanner
from services.fitness_bank import ConstraintType, ExperienceLevel, FitnessBank, RacePerformance
from services.week_theme_generator import WeekTheme, WeekThemePlan


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


def _one_theme():
    return [
        WeekThemePlan(
            week_number=1,
            theme=WeekTheme.BUILD_T_EMPHASIS,
            start_date=date.today() + timedelta(days=7),
            target_volume_pct=0.9,
            notes=[],
        )
    ]


def test_constraint_aware_passes_load_context_into_workout_generator(monkeypatch):
    planner = ConstraintAwarePlanner(db=SimpleNamespace())
    bank = _bank()
    captured = {}

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

    class _FakeWorkoutGenerator:
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)

        def generate_week(self, **kwargs):
            return SimpleNamespace(total_miles=58.0, notes=[], days=[])

    monkeypatch.setattr("services.constraint_aware_planner.WorkoutPrescriptionGenerator", _FakeWorkoutGenerator)
    monkeypatch.setattr(planner.theme_generator, "generate", lambda **_kwargs: _one_theme())

    plan = planner.generate_plan(
        athlete_id=uuid4(),
        race_date=date.today() + timedelta(weeks=10),
        race_distance="10k",
    )

    assert captured["load_easy_long_floor_mi"] == 15.5
    assert captured["load_history_override_easy_long"] is True
    assert captured["load_count_long_15plus"] == 14
    assert captured["load_count_long_18plus"] == 6
    assert captured["load_recency_last_18plus_days"] == 30
    assert "d4_history_override" in plan.prediction_rationale_tags


def test_constraint_aware_load_context_failure_falls_back_safely(monkeypatch):
    planner = ConstraintAwarePlanner(db=SimpleNamespace())
    bank = _bank()
    captured = {}

    monkeypatch.setattr("services.constraint_aware_planner.get_fitness_bank", lambda *_: bank)
    monkeypatch.setattr(
        "services.constraint_aware_planner.build_load_context",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    class _FakeWorkoutGenerator:
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)

        def generate_week(self, **kwargs):
            return SimpleNamespace(total_miles=55.0, notes=[], days=[])

    monkeypatch.setattr("services.constraint_aware_planner.WorkoutPrescriptionGenerator", _FakeWorkoutGenerator)
    monkeypatch.setattr(planner.theme_generator, "generate", lambda **_kwargs: _one_theme())

    planner.generate_plan(
        athlete_id=uuid4(),
        race_date=date.today() + timedelta(weeks=10),
        race_distance="10k",
    )

    assert captured["load_easy_long_floor_mi"] is None
    assert captured["load_history_override_easy_long"] is False
