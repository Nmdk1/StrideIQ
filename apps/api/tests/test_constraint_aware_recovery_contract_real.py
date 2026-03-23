from datetime import date, timedelta
from uuid import uuid4
from unittest.mock import MagicMock

from services.constraint_aware_planner import generate_constraint_aware_plan
from services.fitness_bank import ConstraintType, ExperienceLevel, FitnessBank, RacePerformance
from services.plan_quality_gate import compute_athlete_long_run_floor, evaluate_constraint_aware_plan


def _bank(*, peak_mpw: float = 72.0, current_mpw: float = 62.0, injury: bool = False) -> FitnessBank:
    race = RacePerformance(
        date=date.today() - timedelta(days=35),
        distance="10k",
        distance_m=10000.0,
        finish_time_seconds=2360,
        pace_per_mile=6.3,
        rpi=55.0,
    )
    return FitnessBank(
        athlete_id=str(uuid4()),
        peak_weekly_miles=peak_mpw,
        peak_monthly_miles=peak_mpw * 4.0,
        peak_long_run_miles=20.0,
        peak_mp_long_run_miles=13.0,
        peak_threshold_miles=8.0,
        peak_ctl=85.0,
        race_performances=[race],
        best_rpi=55.0,
        best_race=race,
        current_weekly_miles=current_mpw,
        current_ctl=78.0,
        current_atl=72.0,
        weeks_since_peak=5,
        current_long_run_miles=16.0,
        average_long_run_miles=15.0,
        tau1=36.0,
        tau2=8.0,
        experience_level=ExperienceLevel.EXPERIENCED,
        constraint_type=ConstraintType.INJURY if injury else ConstraintType.NONE,
        constraint_details="injury" if injury else None,
        is_returning_from_break=injury,
        typical_long_run_day=6,
        typical_quality_day=3,
        typical_rest_days=[0],
        weeks_to_80pct_ctl=0,
        weeks_to_race_ready=2,
        sustainable_peak_weekly=68.0,
        recent_quality_sessions_28d=5,
        recent_8w_median_weekly_miles=63.0,
        recent_16w_p90_weekly_miles=68.0,
        recent_8w_p75_long_run_miles=15.5,
        recent_16w_p50_long_run_miles=14.5,
        recent_16w_run_count=40,
        peak_confidence="high",
    )


def _gen(distance: str, bank: FitnessBank, monkeypatch):
    monkeypatch.setattr("services.constraint_aware_planner.get_fitness_bank", lambda _athlete_id, _db: bank)
    return generate_constraint_aware_plan(
        athlete_id=uuid4(),
        race_date=date.today() + timedelta(weeks=12),
        race_distance=distance,
        db=MagicMock(),
    )


def _week_long(week) -> float:
    longs = [float(d.target_miles or 0) for d in week.days if d.workout_type in ("long", "long_mp", "long_hmp", "easy_long")]
    return max(longs) if longs else 0.0


def test_high_data_10k_long_run_floor_not_breached(monkeypatch):
    bank = _bank()
    plan = _gen("10k", bank, monkeypatch)
    floor = compute_athlete_long_run_floor(
        l30_max_easy_long_mi=bank.current_long_run_miles,
        recent_8w_p75_long_run_miles=bank.recent_8w_p75_long_run_miles,
        recent_16w_p50_long_run_miles=bank.recent_16w_p50_long_run_miles,
        recent_16w_run_count=bank.recent_16w_run_count,
        peak_long_run_miles=bank.peak_long_run_miles,
        current_weekly_miles=bank.current_weekly_miles,
        constraint_type=bank.constraint_type.value,
        race_distance="10k",
    )
    for week in plan.weeks[:2]:
        assert _week_long(week) + 1e-6 >= floor


def test_10k_valid_high_mileage_plan_not_false_flagged(monkeypatch):
    plan = _gen("10k", _bank(), monkeypatch)
    gate = evaluate_constraint_aware_plan(plan)
    assert gate.passed is True, gate.reasons


def test_marathon_not_10k_gated(monkeypatch):
    plan = _gen("marathon", _bank(), monkeypatch)
    gate = evaluate_constraint_aware_plan(plan)
    assert all("tenk_" not in c for c in gate.invariant_conflicts)


def test_half_quality_mix_remains_threshold_mp(monkeypatch):
    plan = _gen("half_marathon", _bank(), monkeypatch)
    days = [d for w in plan.weeks for d in w.days]
    workout_types = [d.workout_type for d in days]
    assert "threshold" in workout_types or "threshold_short" in workout_types
    has_hmp_long = ("long_hmp" in workout_types) or any(
        d.workout_type == "long_mp" and "HMP" in str(getattr(d, "name", "")).upper() for d in days
    )
    assert has_hmp_long is True


def test_cutback_is_real_reduction(monkeypatch):
    plan = _gen("marathon", _bank(), monkeypatch)
    totals = [float(w.total_miles or 0) for w in plan.weeks]
    has_cutback = any(prev > 0 and (prev - cur) / prev >= 0.15 for prev, cur in zip(totals, totals[1:]))
    assert has_cutback is True


def test_prediction_contract_unchanged_real_generation(monkeypatch):
    plan = _gen("10k", _bank(), monkeypatch)
    prediction = plan.to_dict()["prediction"]
    assert "time" in prediction
    assert "ci" in prediction
    assert "rationale_tags" in prediction
    assert "scenarios" in prediction
    assert "uncertainty_reason" in prediction


def test_5k_real_generation_not_false_flagged(monkeypatch):
    plan = _gen("5k", _bank(), monkeypatch)
    gate = evaluate_constraint_aware_plan(plan)
    assert gate.passed is True, gate.reasons
