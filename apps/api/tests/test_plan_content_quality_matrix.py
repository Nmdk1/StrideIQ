"""
Plan Content Quality Matrix

This is the real quality gate. These tests generate actual plans with
realistic synthetic athlete profiles and assert on plan CONTENT — not
just that generation succeeds.

If a test here passes, a rational plan was produced. If it fails, the
generator produced something a coach would reject.

Archetypes:
  founder_mirror  — 55–65 mpw, 39:14 10K (RPI ~51.5), long runs 18–22mi,
                    healthy after injury period. Based on founder's May–Nov data.
  consistent_mid  — 40–50 mpw, 45:00 10K (RPI ~47), no major injuries.
  comeback        — 25–35 mpw current, peak was 50 mpw, 3 months off.
  high_mileage    — 70–80 mpw, 35:00 10K (RPI ~56), established volume.

Distances: 5k, 10k, half_marathon, marathon
Plan types: constraint-aware (full matrix), model-driven (key archetypes)
"""

from datetime import date, timedelta
from types import SimpleNamespace
from typing import List
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from services.constraint_aware_planner import generate_constraint_aware_plan
from services.fitness_bank import (
    ConstraintType,
    ExperienceLevel,
    FitnessBank,
    RacePerformance,
)
from services.model_driven_plan_generator import (
    ModelDrivenPlanGenerator,
    generate_model_driven_plan,
)
from services.individual_performance_model import BanisterModel, ModelConfidence


# ---------------------------------------------------------------------------
# Athlete archetypes — realistic synthetic profiles
# ---------------------------------------------------------------------------

def _race(distance: str, distance_m: float, finish_s: int, pace_per_mile: float, rpi: float) -> RacePerformance:
    return RacePerformance(
        date=date.today() - timedelta(days=90),
        distance=distance,
        distance_m=distance_m,
        finish_time_seconds=finish_s,
        pace_per_mile=pace_per_mile,
        rpi=rpi,
    )


def _make_founder_mirror(race_distance_context: str = "10k") -> FitnessBank:
    """
    Based on founder's May–Nov training history.
    55–65 mpw, 39:14 10K while slightly injured (RPI ~51.5),
    long runs 18–22 mi, medium-long ~15 mi on Tuesdays.
    Currently healthy and building back.
    """
    race_10k = _race("10k", 10000.0, 2354, 6.33, 51.5)  # 39:14 10K
    peak_mpw = 65.0
    current_mpw = 55.0
    return FitnessBank(
        athlete_id=str(uuid4()),
        peak_weekly_miles=peak_mpw,
        peak_monthly_miles=peak_mpw * 4.3,
        peak_long_run_miles=22.0,
        peak_mp_long_run_miles=16.0,
        peak_threshold_miles=8.0,
        peak_ctl=78.0,
        race_performances=[race_10k],
        best_rpi=51.5,
        best_race=race_10k,
        current_weekly_miles=current_mpw,
        current_ctl=66.0,
        current_atl=58.0,
        weeks_since_peak=6,
        current_long_run_miles=18.0,
        average_long_run_miles=19.0,
        tau1=42.0,
        tau2=7.0,
        experience_level=ExperienceLevel.EXPERIENCED,
        constraint_type=ConstraintType.NONE,
        constraint_details=None,
        is_returning_from_break=False,
        typical_long_run_day=6,   # Sunday
        typical_quality_day=3,    # Thursday
        typical_rest_days=[0],    # Monday
        weeks_to_80pct_ctl=1,
        weeks_to_race_ready=3,
        sustainable_peak_weekly=peak_mpw * 0.92,
        recent_quality_sessions_28d=6,
        recent_8w_median_weekly_miles=58.0,
        recent_16w_p90_weekly_miles=64.0,
        recent_8w_p75_long_run_miles=20.0,
        recent_16w_p50_long_run_miles=18.0,
        recent_16w_run_count=80,
        peak_confidence="high",
    )


def _make_consistent_mid() -> FitnessBank:
    """40–50 mpw, no major injuries, consistent runner."""
    race_10k = _race("10k", 10000.0, 2700, 7.26, 47.0)  # 45:00 10K
    peak_mpw = 50.0
    current_mpw = 45.0
    return FitnessBank(
        athlete_id=str(uuid4()),
        peak_weekly_miles=peak_mpw,
        peak_monthly_miles=peak_mpw * 4.2,
        peak_long_run_miles=16.0,
        peak_mp_long_run_miles=12.0,
        peak_threshold_miles=6.0,
        peak_ctl=60.0,
        race_performances=[race_10k],
        best_rpi=47.0,
        best_race=race_10k,
        current_weekly_miles=current_mpw,
        current_ctl=54.0,
        current_atl=48.0,
        weeks_since_peak=4,
        current_long_run_miles=14.0,
        average_long_run_miles=13.0,
        tau1=40.0,
        tau2=7.0,
        experience_level=ExperienceLevel.INTERMEDIATE,
        constraint_type=ConstraintType.NONE,
        constraint_details=None,
        is_returning_from_break=False,
        typical_long_run_day=6,
        typical_quality_day=3,
        typical_rest_days=[0],
        weeks_to_80pct_ctl=2,
        weeks_to_race_ready=4,
        sustainable_peak_weekly=peak_mpw * 0.90,
        recent_quality_sessions_28d=4,
        recent_8w_median_weekly_miles=44.0,
        recent_16w_p90_weekly_miles=49.0,
        recent_8w_p75_long_run_miles=15.0,
        recent_16w_p50_long_run_miles=13.0,
        recent_16w_run_count=60,
        peak_confidence="high",
    )


def _make_comeback() -> FitnessBank:
    """25–35 mpw current, peak was 50 mpw, coming back from 3 months off."""
    race_half = _race("half_marathon", 21097.5, 6300, 8.05, 43.0)  # 1:45 HM
    peak_mpw = 50.0
    current_mpw = 30.0
    return FitnessBank(
        athlete_id=str(uuid4()),
        peak_weekly_miles=peak_mpw,
        peak_monthly_miles=peak_mpw * 4.0,
        peak_long_run_miles=18.0,
        peak_mp_long_run_miles=0.0,
        peak_threshold_miles=5.0,
        peak_ctl=60.0,
        race_performances=[race_half],
        best_rpi=43.0,
        best_race=race_half,
        current_weekly_miles=current_mpw,
        current_ctl=36.0,
        current_atl=32.0,
        weeks_since_peak=14,
        current_long_run_miles=10.0,
        average_long_run_miles=9.0,
        tau1=40.0,
        tau2=7.0,
        experience_level=ExperienceLevel.INTERMEDIATE,
        constraint_type=ConstraintType.INJURY,
        constraint_details="injury_return",
        is_returning_from_break=True,
        typical_long_run_day=6,
        typical_quality_day=3,
        typical_rest_days=[0],
        weeks_to_80pct_ctl=6,
        weeks_to_race_ready=10,
        sustainable_peak_weekly=peak_mpw * 0.80,
        recent_quality_sessions_28d=1,
        recent_8w_median_weekly_miles=28.0,
        recent_16w_p90_weekly_miles=42.0,
        recent_8w_p75_long_run_miles=11.0,
        recent_16w_p50_long_run_miles=9.0,
        recent_16w_run_count=28,
        peak_confidence="moderate",
    )


def _make_high_mileage() -> FitnessBank:
    """70–80 mpw, elite-adjacent, 35:00 10K (RPI ~56)."""
    race_10k = _race("10k", 10000.0, 2100, 5.64, 56.0)  # 35:00 10K
    peak_mpw = 80.0
    current_mpw = 72.0
    return FitnessBank(
        athlete_id=str(uuid4()),
        peak_weekly_miles=peak_mpw,
        peak_monthly_miles=peak_mpw * 4.4,
        peak_long_run_miles=24.0,
        peak_mp_long_run_miles=18.0,
        peak_threshold_miles=12.0,
        peak_ctl=96.0,
        race_performances=[race_10k],
        best_rpi=56.0,
        best_race=race_10k,
        current_weekly_miles=current_mpw,
        current_ctl=86.0,
        current_atl=76.0,
        weeks_since_peak=3,
        current_long_run_miles=22.0,
        average_long_run_miles=21.0,
        tau1=44.0,
        tau2=7.0,
        experience_level=ExperienceLevel.ELITE,
        constraint_type=ConstraintType.NONE,
        constraint_details=None,
        is_returning_from_break=False,
        typical_long_run_day=6,
        typical_quality_day=3,
        typical_rest_days=[0],
        weeks_to_80pct_ctl=1,
        weeks_to_race_ready=2,
        sustainable_peak_weekly=peak_mpw * 0.95,
        recent_quality_sessions_28d=8,
        recent_8w_median_weekly_miles=74.0,
        recent_16w_p90_weekly_miles=79.0,
        recent_8w_p75_long_run_miles=23.0,
        recent_16w_p50_long_run_miles=21.0,
        recent_16w_run_count=100,
        peak_confidence="high",
    )


# ---------------------------------------------------------------------------
# Content quality assertions (shared helpers)
# ---------------------------------------------------------------------------

def _all_days(plan) -> list:
    """Flatten all DayPlan objects from any plan shape."""
    if hasattr(plan, "weeks"):
        return [d for w in plan.weeks for d in w.days]
    return []


def _all_workout_types(plan) -> list:
    return [d.workout_type for d in _all_days(plan)]


def _week1_long_run_miles(plan) -> float:
    """Return the long run miles in week 1."""
    if not hasattr(plan, "weeks") or not plan.weeks:
        return 0.0
    week1_days = plan.weeks[0].days
    long_days = [d for d in week1_days if d.workout_type in ("long", "easy_long", "long_mp", "long_hmp")]
    if not long_days:
        return 0.0
    return max(d.target_miles for d in long_days)


def assert_no_marathon_pace_work(plan, distance: str):
    """5K/10K plans must never include long_mp or mp_medium sessions."""
    if distance not in ("5k", "10k"):
        return
    bad = [d for d in _all_days(plan) if d.workout_type in ("long_mp", "mp_medium")]
    assert not bad, (
        f"{distance.upper()} plan has marathon pace work: "
        f"{[(d.workout_type, getattr(d, 'name', ''), getattr(d, 'target_miles', 0)) for d in bad]}"
    )


def assert_intervals_present(plan, distance: str):
    """5K/10K plans must contain interval sessions."""
    if distance not in ("5k", "10k"):
        return
    interval_days = [d for d in _all_days(plan) if d.workout_type == "intervals"]
    assert interval_days, (
        f"{distance.upper()} plan must contain interval sessions. "
        f"Workout types found: {set(_all_workout_types(plan))}"
    )


def assert_w1_long_run_proportional(plan, recent_weekly_miles: float, distance: str):
    """Week 1 long run must not exceed 32% of the athlete's recent weekly mileage."""
    long_miles = _week1_long_run_miles(plan)
    max_allowed = recent_weekly_miles * 0.36  # slightly generous for test stability
    assert long_miles <= max_allowed, (
        f"W1 long run too high for {distance}: {long_miles:.1f}mi "
        f"vs max allowed {max_allowed:.1f}mi (athlete runs {recent_weekly_miles:.0f}mpw). "
        f"This is the '27mi Week 1' class of bug."
    )


def assert_saturday_before_sunday_long_is_easy(plan):
    """If Sunday (day 6) is a long run, Saturday (day 5) must be easy or rest."""
    for w in getattr(plan, "weeks", []):
        sunday = next((d for d in w.days if d.day_of_week == 6), None)
        saturday = next((d for d in w.days if d.day_of_week == 5), None)
        if sunday is None or saturday is None:
            continue
        if sunday.workout_type not in ("long", "easy_long", "long_mp", "long_hmp"):
            continue
        assert saturday.workout_type in ("easy", "easy_strides", "rest"), (
            f"Saturday before Sunday long run must be easy or rest. "
            f"Got Saturday={saturday.workout_type}, Sunday={sunday.workout_type} "
            f"in week {w.week_number}."
        )


def assert_plan_has_correct_week_count(plan, expected_weeks: int):
    actual = len(getattr(plan, "weeks", []))
    assert actual == expected_weeks, (
        f"Plan has {actual} weeks, expected {expected_weeks}."
    )


def assert_race_week_is_last(plan):
    weeks = getattr(plan, "weeks", [])
    if not weeks:
        return
    last_week = weeks[-1]
    last_week_types = {d.workout_type for d in last_week.days}
    assert "race" in last_week_types, (
        f"Last week must contain a race day. Got: {last_week_types}"
    )


# ---------------------------------------------------------------------------
# Constraint-aware content quality matrix
# ---------------------------------------------------------------------------

DISTANCES = ["5k", "10k", "half_marathon", "marathon"]
WEEKS = 12
RACE_DATE = date.today() + timedelta(weeks=WEEKS)

ARCHETYPES = [
    ("founder_mirror", _make_founder_mirror),
    ("consistent_mid", _make_consistent_mid),
    ("comeback", _make_comeback),
    ("high_mileage", _make_high_mileage),
]


@pytest.mark.parametrize("distance", DISTANCES)
@pytest.mark.parametrize("archetype_name,make_bank", ARCHETYPES, ids=[a[0] for a in ARCHETYPES])
def test_constraint_aware_content_quality(monkeypatch, distance, archetype_name, make_bank):
    """
    Full content quality matrix: 4 archetypes × 4 distances = 16 scenarios.

    Each scenario generates a real plan and asserts on content:
    - W1 long run proportional to athlete volume
    - 5K/10K have intervals
    - 5K/10K have no marathon pace work
    - Saturday before Sunday long is easy
    - Race week is last
    """
    bank = make_bank()
    athlete_id = uuid4()

    monkeypatch.setattr(
        "services.constraint_aware_planner.get_fitness_bank",
        lambda _id, _db: bank,
    )

    plan = generate_constraint_aware_plan(
        athlete_id=athlete_id,
        race_date=RACE_DATE,
        race_distance=distance,
        tune_up_races=[],
        db=MagicMock(),
    )

    assert plan is not None, f"Plan generation returned None for {archetype_name}/{distance}"
    assert plan.weeks, f"Plan has no weeks for {archetype_name}/{distance}"

    # Core content quality assertions
    assert_no_marathon_pace_work(plan, distance)
    assert_intervals_present(plan, distance)
    assert_w1_long_run_proportional(plan, bank.recent_8w_median_weekly_miles, distance)
    assert_saturday_before_sunday_long_is_easy(plan)
    assert_race_week_is_last(plan)


# ---------------------------------------------------------------------------
# Model-driven content quality — key archetypes
# (Patches DB-dependent methods with realistic values)
# ---------------------------------------------------------------------------

def _make_banister_model(athlete_id, tau1=42.0, tau2=7.0) -> BanisterModel:
    m = BanisterModel.__new__(BanisterModel)
    m.athlete_id = str(athlete_id)
    m.tau1 = tau1
    m.tau2 = tau2
    m.k1 = 1.0
    m.k2 = 2.0
    m.p0 = 50.0
    m.fit_error = 0.5
    m.r_squared = 0.85
    m.n_performance_markers = 5
    m.n_training_days = 180
    m.confidence = ModelConfidence.HIGH
    return m


def _make_baseline(weekly_miles, long_run_miles, peak_long_run_miles=None, is_injury=False):
    return {
        "weekly_miles": weekly_miles,
        "long_run_miles": long_run_miles,
        "peak_long_run_miles": peak_long_run_miles or long_run_miles * 1.1,
        "quality_miles_per_week": weekly_miles * 0.12,
        "is_returning_from_injury": is_injury,
        "peak_weekly_miles": weekly_miles * 1.15,
    }


def _mock_race_prediction():
    p = SimpleNamespace()
    p.predicted_time_seconds = 14400  # 4:00 marathon
    p.predicted_pace_per_mile = 9.15
    p.confidence = "moderate"
    return p


@pytest.mark.parametrize("distance,archetype,current_ctl,current_atl,weekly_miles,long_run_miles,tau1", [
    # founder_mirror → marathon
    ("marathon", "founder_mirror", 66.0, 58.0, 55.0, 18.0, 42.0),
    # founder_mirror → 10k (should get intervals, no MP work)
    ("10k", "founder_mirror", 66.0, 58.0, 55.0, 18.0, 42.0),
    # consistent_mid → half
    ("half_marathon", "consistent_mid", 54.0, 48.0, 45.0, 14.0, 40.0),
    # comeback → marathon (low volume — W1 long run must not be hardcoded 14mi)
    ("marathon", "comeback", 36.0, 32.0, 30.0, 10.0, 40.0),
    # high_mileage → 5k (should get intervals, zero MP work)
    ("5k", "high_mileage", 86.0, 76.0, 72.0, 22.0, 44.0),
], ids=[
    "founder_mirror/marathon",
    "founder_mirror/10k",
    "consistent_mid/half",
    "comeback/marathon",
    "high_mileage/5k",
])
def test_model_driven_content_quality(
    monkeypatch,
    distance,
    archetype,
    current_ctl,
    current_atl,
    weekly_miles,
    long_run_miles,
    tau1,
):
    """
    Model-driven content quality for key archetype × distance combinations.

    Patches all DB-dependent methods with realistic synthetic values so we
    test the actual plan-building logic, not the data-retrieval layer.
    """
    athlete_id = uuid4()
    model = _make_banister_model(athlete_id, tau1=tau1)
    baseline = _make_baseline(weekly_miles, long_run_miles)

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    mock_db.query.return_value.filter.return_value.all.return_value = []

    # Use the generator's own default pace format (avoids needing to replicate
    # rpi_calculator's dict structure in test setup)
    generator_instance = ModelDrivenPlanGenerator(mock_db)
    realistic_paces = generator_instance._default_paces()

    with (
        patch("services.model_driven_plan_generator.get_or_calibrate_model", return_value=model),
        patch.object(ModelDrivenPlanGenerator, "_get_current_state", return_value=(current_ctl, current_atl)),
        patch.object(ModelDrivenPlanGenerator, "_get_established_baseline", return_value=baseline),
        patch.object(ModelDrivenPlanGenerator, "_get_training_paces", return_value=realistic_paces),
        patch("services.model_driven_plan_generator.RacePredictor") as mock_predictor_cls,
    ):
        mock_predictor_cls.return_value.predict.return_value = _mock_race_prediction()

        plan = generate_model_driven_plan(
            athlete_id=athlete_id,
            race_date=date.today() + timedelta(weeks=12),
            race_distance=distance,
            db=mock_db,
        )

    assert plan is not None
    assert plan.weeks, f"No weeks generated for {archetype}/{distance}"

    # Flatten model-driven weeks (ModelDrivenPlan.weeks is List[ModelDrivenWeek])
    all_workout_types = [
        day.workout_type
        for week in plan.weeks
        for day in week.days
    ]

    # No marathon pace work for 5K/10K
    if distance in ("5k", "10k"):
        mp_days = [t for t in all_workout_types if t in ("long_mp", "mp_medium")]
        assert not mp_days, (
            f"{distance.upper()} model-driven plan has MP work: {mp_days}"
        )

    # W1 long run must be proportional to athlete volume
    week1_days = plan.weeks[0].days
    long_days_w1 = [d for d in week1_days if d.workout_type in ("long", "long_mp", "long_hmp")]
    if long_days_w1:
        w1_long = max(d.target_miles for d in long_days_w1)
        max_allowed = weekly_miles * 0.40  # slightly generous for model-driven
        assert w1_long <= max_allowed, (
            f"W1 long run {w1_long:.1f}mi too high for {archetype}/{distance} "
            f"({weekly_miles:.0f}mpw athlete). Max allowed: {max_allowed:.1f}mi."
        )
