from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import MagicMock

import pytest

from services.constraint_aware_planner import generate_constraint_aware_plan
from services.fitness_bank import ConstraintType, ExperienceLevel, FitnessBank, RacePerformance
from services.plan_quality_gate import evaluate_constraint_aware_plan
from services.workout_prescription import WorkoutPrescriptionGenerator
from services.week_theme_generator import WeekTheme


def _make_bank(*, athlete_id: str, peak_mpw: float, current_mpw: float, experience: ExperienceLevel, injury: bool) -> FitnessBank:
    race = RacePerformance(
        date=date.today() - timedelta(days=35),
        distance="10k",
        distance_m=10000.0,
        finish_time_seconds=2350,
        pace_per_mile=6.3,
        rpi=55.0,
    )
    return FitnessBank(
        athlete_id=athlete_id,
        peak_weekly_miles=peak_mpw,
        peak_monthly_miles=peak_mpw * 4.0,
        peak_long_run_miles=max(10.0, peak_mpw * 0.28),
        peak_mp_long_run_miles=max(0.0, peak_mpw * 0.18),
        peak_threshold_miles=max(4.0, peak_mpw * 0.1),
        peak_ctl=max(35.0, peak_mpw * 1.2),
        race_performances=[race],
        best_rpi=55.0,
        best_race=race,
        current_weekly_miles=current_mpw,
        current_ctl=max(25.0, current_mpw),
        current_atl=max(20.0, current_mpw * 0.9),
        weeks_since_peak=8,
        current_long_run_miles=max(8.0, current_mpw * 0.22),
        average_long_run_miles=max(8.0, current_mpw * 0.2),
        tau1=40.0,
        tau2=7.0,
        experience_level=experience,
        constraint_type=ConstraintType.INJURY if injury else ConstraintType.NONE,
        constraint_details="injury_return" if injury else None,
        is_returning_from_break=injury,
        typical_long_run_day=6,
        typical_quality_day=3,
        typical_rest_days=[0],
        weeks_to_80pct_ctl=2,
        weeks_to_race_ready=4,
        sustainable_peak_weekly=peak_mpw * 0.9,
        recent_quality_sessions_28d=4,
        recent_8w_median_weekly_miles=max(10.0, current_mpw * 0.95),
        recent_16w_p90_weekly_miles=max(current_mpw, peak_mpw * 0.9),
        recent_8w_p75_long_run_miles=max(8.0, current_mpw * 0.24),
        recent_16w_p50_long_run_miles=max(8.0, current_mpw * 0.22),
        recent_16w_run_count=36,
        peak_confidence="high",
    )


PROFILES = [
    pytest.param({"peak_mpw": 70.0, "current_mpw": 62.0, "experience": ExperienceLevel.EXPERIENCED, "injury": False}, id="experienced"),
    pytest.param({"peak_mpw": 50.0, "current_mpw": 42.0, "experience": ExperienceLevel.INTERMEDIATE, "injury": False}, id="moderate"),
    pytest.param({"peak_mpw": 38.0, "current_mpw": 22.0, "experience": ExperienceLevel.BEGINNER, "injury": True}, id="cold-start-ish"),
]

DISTANCES = ["5k", "10k", "half_marathon", "marathon"]


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("distance", DISTANCES)
def test_constraint_aware_smoke_matrix_generates_all_distances(profile, distance, monkeypatch):
    athlete_id = uuid4()
    bank = _make_bank(athlete_id=str(athlete_id), **profile)
    monkeypatch.setattr("services.constraint_aware_planner.get_fitness_bank", lambda _athlete_id, _db: bank)

    plan = generate_constraint_aware_plan(
        athlete_id=athlete_id,
        race_date=date.today() + timedelta(weeks=12),
        race_distance=distance,
        db=MagicMock(),
    )
    assert plan.total_weeks > 0
    assert len(plan.weeks) > 0
    assert plan.race_distance == distance


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("distance", DISTANCES)
def test_constraint_aware_smoke_matrix_runs_quality_gate(profile, distance, monkeypatch):
    athlete_id = uuid4()
    bank = _make_bank(athlete_id=str(athlete_id), **profile)
    monkeypatch.setattr("services.constraint_aware_planner.get_fitness_bank", lambda _athlete_id, _db: bank)

    plan = generate_constraint_aware_plan(
        athlete_id=athlete_id,
        race_date=date.today() + timedelta(weeks=10),
        race_distance=distance,
        db=MagicMock(),
    )
    gate = evaluate_constraint_aware_plan(plan)
    assert isinstance(gate.passed, bool)
    assert isinstance(gate.reasons, list)


def _mk_week(week_number: int, total_miles: float, theme: str, days):
    return SimpleNamespace(
        week_number=week_number,
        total_miles=total_miles,
        theme=SimpleNamespace(value=theme),
        days=days,
    )


def _mk_day(workout_type: str, miles: float, name: str = ""):
    return SimpleNamespace(workout_type=workout_type, target_miles=miles, name=name)


def _mk_plan(distance: str, weeks):
    return SimpleNamespace(
        race_distance=distance,
        weeks=weeks,
        volume_contract={"band_min": 40.0, "band_max": 70.0},
        fitness_bank={
            "peak": {"long_run": 18.0},
            "constraint": {"type": "none"},
            "volume_contract": {
                "recent_8w_p75_long_run_miles": 14.0,
                "recent_16w_p50_long_run_miles": 13.0,
                "recent_16w_run_count": 30,
            },
        },
    )


def test_marathon_gate_flags_missing_mp_progression():
    plan = _mk_plan(
        "marathon",
        [
            _mk_week(1, 55.0, "build_mixed", [_mk_day("long", 14.0), _mk_day("threshold", 6.0)]),
            _mk_week(2, 56.0, "build_mixed", [_mk_day("long", 14.5), _mk_day("threshold", 6.0)]),
            _mk_week(3, 57.0, "build_mixed", [_mk_day("long", 15.0), _mk_day("threshold", 6.0)]),
            _mk_week(4, 49.0, "recovery", [_mk_day("long", 12.0)]),
        ],
    )
    gate = evaluate_constraint_aware_plan(plan)
    assert gate.passed is False
    assert "marathon_mp_progression_missing" in gate.invariant_conflicts


def test_half_gate_blocks_marathon_artifact():
    plan = _mk_plan(
        "half_marathon",
        [
            _mk_week(1, 48.0, "build_t", [_mk_day("threshold", 6.0), _mk_day("long_mp", 14.0, name="14mi w/ 6@MP")]),
            _mk_week(2, 46.0, "build_t", [_mk_day("threshold", 6.0), _mk_day("long_hmp", 12.0, name="12mi w/ 4@HMP")]),
        ],
    )
    gate = evaluate_constraint_aware_plan(plan)
    assert gate.passed is False
    assert "half_marathon_artifact" in gate.invariant_conflicts


def test_5k_gate_requires_sharpen_speed_sessions():
    plan = _mk_plan(
        "5k",
        [
            _mk_week(1, 42.0, "build_t", [_mk_day("threshold", 5.0), _mk_day("long", 14.0)]),
            _mk_week(2, 40.0, "peak", [_mk_day("threshold", 4.0), _mk_day("long", 14.0)]),
        ],
    )
    gate = evaluate_constraint_aware_plan(plan)
    assert gate.passed is False
    assert "fivek_speed_sharpen_missing" in gate.invariant_conflicts


def test_5k_gate_accepts_sharpen_competency_variants():
    plan = _mk_plan(
        "5k",
        [
            _mk_week(1, 44.0, "build_t", [_mk_day("threshold", 5.5), _mk_day("long", 11.0)]),
            _mk_week(2, 42.0, "peak", [_mk_day("threshold_short", 4.0), _mk_day("hill_sprints", 6.0)]),
        ],
    )
    gate = evaluate_constraint_aware_plan(plan)
    assert "fivek_speed_sharpen_missing" not in gate.invariant_conflicts


def test_marathon_gate_tolerates_boundary_quantization_near_contract_limits():
    plan = _mk_plan(
        "marathon",
        [
            _mk_week(1, 60.0, "build_mixed", [_mk_day("long_mp", 6.0), _mk_day("long", 14.0)]),
            _mk_week(2, 59.0, "build_mixed", [_mk_day("threshold", 6.0), _mk_day("long", 14.2)]),
            _mk_week(3, 58.0, "build_mixed", [_mk_day("long_mp", 5.9), _mk_day("long", 14.4)]),
            _mk_week(4, 49.4, "recovery", [_mk_day("easy", 6.0), _mk_day("long", 13.9)]),
        ],
    )
    gate = evaluate_constraint_aware_plan(plan)
    assert "marathon_mp_total_too_low" not in gate.invariant_conflicts
    assert "marathon_long_run_progression_stall" not in gate.invariant_conflicts
    assert "marathon_cutback_missing" not in gate.invariant_conflicts


def _pace_to_seconds(pace: str) -> int:
    minutes, seconds = pace.split(":")
    return int(minutes) * 60 + int(seconds)


def test_tuneup_distance_preserved_from_request(monkeypatch):
    athlete_id = uuid4()
    bank = _make_bank(
        athlete_id=str(athlete_id),
        peak_mpw=70.0,
        current_mpw=60.0,
        experience=ExperienceLevel.EXPERIENCED,
        injury=False,
    )
    monkeypatch.setattr("services.constraint_aware_planner.get_fitness_bank", lambda _athlete_id, _db: bank)

    tune_up_date = date.today() + timedelta(weeks=8)
    plan = generate_constraint_aware_plan(
        athlete_id=athlete_id,
        race_date=date.today() + timedelta(weeks=12),
        race_distance="10k",
        tune_up_races=[{"date": tune_up_date, "distance": "5k", "name": "Tuneup 5K", "purpose": "threshold"}],
        db=MagicMock(),
    )

    tuneup_days = [
        d
        for w in plan.weeks
        for d in w.days
        if d.workout_type == "tune_up_race" and d.day_of_week == tune_up_date.weekday()
    ]
    assert tuneup_days
    assert tuneup_days[0].target_miles == pytest.approx(3.1, abs=0.05)


def test_distance_alias_normalization_half_marathon(monkeypatch):
    athlete_id = uuid4()
    bank = _make_bank(
        athlete_id=str(athlete_id),
        peak_mpw=55.0,
        current_mpw=50.0,
        experience=ExperienceLevel.INTERMEDIATE,
        injury=False,
    )
    monkeypatch.setattr("services.constraint_aware_planner.get_fitness_bank", lambda _athlete_id, _db: bank)

    plan_half = generate_constraint_aware_plan(
        athlete_id=athlete_id,
        race_date=date.today() + timedelta(weeks=10),
        race_distance="half",
        db=MagicMock(),
    )
    plan_half_full = generate_constraint_aware_plan(
        athlete_id=athlete_id,
        race_date=date.today() + timedelta(weeks=10),
        race_distance="half_marathon",
        db=MagicMock(),
    )
    assert plan_half.predicted_time == plan_half_full.predicted_time


def test_race_day_uses_distance_specific_race_pace():
    bank = _make_bank(
        athlete_id=str(uuid4()),
        peak_mpw=70.0,
        current_mpw=60.0,
        experience=ExperienceLevel.EXPERIENCED,
        injury=False,
    )
    gen = WorkoutPrescriptionGenerator(bank, race_distance="10k")
    week = gen.generate_week(
        theme=WeekTheme.RACE,
        week_number=10,
        total_weeks=10,
        target_miles=40.0,
        start_date=date.today(),
    )
    race_day = next(d for d in week.days if d.workout_type == "race")
    race_sec = _pace_to_seconds(race_day.paces["race"])
    marathon_sec = _pace_to_seconds(gen.pace_strs["marathon"])
    assert race_sec < marathon_sec
