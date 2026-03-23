from datetime import date, timedelta
from uuid import uuid4

from services.constraint_aware_planner import ConstraintAwarePlanner
from services.fitness_bank import ConstraintType, ExperienceLevel, FitnessBank
from services.plan_quality_gate import evaluate_constraint_aware_plan
from services.plan_framework.constants import PlanTier
from services.plan_framework.generator import GeneratedPlan, GeneratedWorkout
from services.starter_plan import _apply_cold_start_guardrails
from services.week_theme_generator import WeekTheme
from services.workout_prescription import WorkoutPrescriptionGenerator


def _bank(**overrides) -> FitnessBank:
    base = FitnessBank(
        athlete_id=str(uuid4()),
        peak_weekly_miles=70.0,
        peak_monthly_miles=260.0,
        peak_long_run_miles=18.0,
        peak_mp_long_run_miles=12.0,
        peak_threshold_miles=7.0,
        peak_ctl=85.0,
        race_performances=[],
        best_rpi=52.0,
        best_race=None,
        current_weekly_miles=62.0,
        current_ctl=70.0,
        current_atl=68.0,
        weeks_since_peak=6,
        current_long_run_miles=14.0,
        average_long_run_miles=13.5,
        tau1=36.0,
        tau2=8.0,
        experience_level=ExperienceLevel.EXPERIENCED,
        constraint_type=ConstraintType.NONE,
        constraint_details=None,
        is_returning_from_break=False,
        typical_long_run_day=6,
        typical_quality_day=3,
        typical_rest_days=[0],
        weeks_to_80pct_ctl=0,
        weeks_to_race_ready=0,
        sustainable_peak_weekly=64.0,
        recent_quality_sessions_28d=4,
        recent_8w_median_weekly_miles=64.0,
        recent_16w_p90_weekly_miles=69.0,
        peak_confidence="high",
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


def test_founder_style_10k_keeps_high_mileage_band_when_trusted():
    planner = ConstraintAwarePlanner(db=None)
    bank = _bank()
    vc = planner._build_volume_contract(
        bank=bank,
        race_distance="10k",
        target_peak_weekly_miles=None,
        target_peak_weekly_range=None,
    )
    assert vc["source"] in ("trusted_peak", "trusted_recent_band")
    assert vc["band_min"] >= 55
    assert vc["band_max"] >= 65
    assert vc["applied_peak"] >= 60


def test_untrusted_peak_is_suppressed_for_volume_targets():
    planner = ConstraintAwarePlanner(db=None)
    bank = _bank(peak_weekly_miles=114.0, peak_confidence="low", recent_16w_p90_weekly_miles=67.0)
    vc = planner._build_volume_contract(
        bank=bank,
        race_distance="10k",
        target_peak_weekly_miles=None,
        target_peak_weekly_range=None,
    )
    assert vc["source"] == "trusted_recent_band"
    assert vc["applied_peak"] <= 70


def test_10k_workout_mix_differs_from_marathon_at_similar_mileage():
    bank = _bank()
    tenk = WorkoutPrescriptionGenerator(bank, race_distance="10k")
    mara = WorkoutPrescriptionGenerator(bank, race_distance="marathon")
    wk10 = tenk.generate_week(
        theme=WeekTheme.BUILD_T_EMPHASIS,
        week_number=1,
        total_weeks=10,
        target_miles=65,
        start_date=date.today(),
    )
    wkm = mara.generate_week(
        theme=WeekTheme.BUILD_T_EMPHASIS,
        week_number=1,
        total_weeks=10,
        target_miles=65,
        start_date=date.today(),
    )
    tenk_long = max((d.target_miles for d in wk10.days if d.workout_type == "long"), default=0)
    mara_long = max((d.target_miles for d in wkm.days if d.workout_type == "long"), default=0)
    tenk_threshold = [d.target_miles for d in wk10.days if d.workout_type in ("threshold", "threshold_short")]
    mara_threshold = [d.target_miles for d in wkm.days if d.workout_type in ("threshold", "threshold_short")]
    assert tenk_long <= 18.0
    assert max(tenk_threshold or [0]) <= 8.0
    assert len(tenk_threshold) >= len(mara_threshold)


def test_no_marathon_style_session_sizes_in_10k_block():
    bank = _bank()
    tenk = WorkoutPrescriptionGenerator(bank, race_distance="10k")
    week = tenk.generate_week(
        theme=WeekTheme.PEAK,
        week_number=3,
        total_weeks=10,
        target_miles=70,
        start_date=date.today(),
    )
    long_run = max((d.target_miles for d in week.days if d.workout_type == "long"), default=0.0)
    thresholds = [d.target_miles for d in week.days if d.workout_type == "threshold"]
    assert long_run <= 18.0
    assert all(t <= 8.0 for t in thresholds)


def test_starter_plan_cold_start_week1_guardrail():
    workouts = []
    start = date.today()
    for i in range(1, 5):
        for d in range(5):
            workouts.append(
                GeneratedWorkout(
                    week=i,
                    day=d,
                    day_name="Mon",
                    date=start + timedelta(days=(i - 1) * 7 + d),
                    workout_type="easy",
                    title="Easy",
                    description="Easy",
                    phase="base",
                    phase_name="Base",
                    distance_miles=12.0,
                    duration_minutes=90,
                    pace_description="easy",
                    segments=None,
                    option="A",
                )
            )
        workouts.append(
            GeneratedWorkout(
                week=i,
                day=6,
                day_name="Sun",
                date=start + timedelta(days=(i - 1) * 7 + 6),
                workout_type="long",
                title="Long",
                description="Long",
                phase="base",
                phase_name="Base",
                distance_miles=20.0,
                duration_minutes=180,
                pace_description="long",
                segments=None,
                option="A",
            )
        )
    plan = GeneratedPlan(
        plan_tier=PlanTier.STANDARD,
        distance="marathon",
        duration_weeks=4,
        volume_tier="high",
        days_per_week=6,
        athlete_id=None,
        rpi=None,
        start_date=start,
        end_date=start + timedelta(days=27),
        race_date=None,
        phases=[],
        workouts=workouts,
        weekly_volumes=[80.0, 85.0, 90.0, 95.0],
        peak_volume=95.0,
        total_miles=350.0,
        total_quality_sessions=0,
    )
    guarded = _apply_cold_start_guardrails(plan)
    week1_total = sum(w.distance_miles or 0 for w in guarded.workouts if w.week == 1)
    week1_long = max((w.distance_miles or 0 for w in guarded.workouts if w.week == 1 and w.workout_type == "long"), default=0)
    assert week1_total <= 25.1
    assert week1_long <= 8.0


def test_athlete_peak_override_applied_or_clamped_with_reason():
    planner = ConstraintAwarePlanner(db=None)
    bank = _bank()
    vc_ok = planner._build_volume_contract(
        bank=bank,
        race_distance="10k",
        target_peak_weekly_miles=66.0,
        target_peak_weekly_range=None,
    )
    assert vc_ok["source"] == "athlete_override"
    assert vc_ok["clamped"] is False
    vc_clamped = planner._build_volume_contract(
        bank=bank,
        race_distance="10k",
        target_peak_weekly_miles=200.0,
        target_peak_weekly_range=None,
    )
    assert vc_clamped["source"] == "athlete_override"
    assert vc_clamped["clamped"] is True
    assert vc_clamped["clamp_reason"]


def test_prediction_contract_unchanged():
    plan = ConstraintAwarePlanner(db=None)._generate_minimal_plan(
        bank=_bank(),
        race_date=date.today() + timedelta(days=5),
        race_distance="10k",
    )
    prediction = plan.to_dict()["prediction"]
    assert "time" in prediction
    assert "ci" in prediction
    assert "rationale_tags" in prediction
    assert "scenarios" in prediction
    assert "uncertainty_reason" in prediction


def test_high_mileage_runner_keeps_long_run_floor():
    bank = _bank(current_long_run_miles=10.0, peak_long_run_miles=20.0, current_weekly_miles=62.0)
    gen = WorkoutPrescriptionGenerator(bank, race_distance="10k")
    assert gen.long_run_current >= 15.0


def test_quality_gate_allows_reasonable_high_mileage_10k_long_run():
    week = type("Week", (), {})()
    week.week_number = 2
    week.total_miles = 60.0
    long_day = type("Day", (), {})()
    long_day.workout_type = "long"
    long_day.target_miles = 16.5
    t_day = type("Day", (), {})()
    t_day.workout_type = "threshold"
    t_day.target_miles = 8.0
    week.days = [long_day, t_day]

    plan = type("Plan", (), {})()
    plan.weeks = [week]
    plan.race_distance = "10k"
    plan.volume_contract = {"band_max": 60.0}

    result = evaluate_constraint_aware_plan(plan)
    assert result.passed is True, result.reasons


def test_quality_gate_caps_personal_floor_to_weekly_share_for_10k():
    week = type("Week", (), {})()
    week.week_number = 1
    week.total_miles = 52.0
    long_day = type("Day", (), {})()
    long_day.workout_type = "long"
    long_day.target_miles = 17.2  # exactly 33% of week
    threshold_day = type("Day", (), {})()
    threshold_day.workout_type = "threshold"
    threshold_day.target_miles = 7.0
    week.days = [long_day, threshold_day]

    plan = type("Plan", (), {})()
    plan.weeks = [week]
    plan.race_distance = "10k"
    plan.volume_contract = {"band_min": 45.0, "band_max": 60.0}
    plan.fitness_bank = {
        "current": {"weekly_miles": 55.0, "long_run": 26.4},
        "peak": {"long_run": 30.0},
        "volume_contract": {
            "recent_8w_p75_long_run_miles": 20.0,
            "recent_16w_p50_long_run_miles": 18.0,
            "recent_16w_run_count": 36,
        },
        "constraint": {"type": "none"},
    }

    result = evaluate_constraint_aware_plan(plan)
    assert "personal_long_run_floor_breach" not in result.invariant_conflicts


def test_quality_gate_allows_small_early_week_floor_near_miss_for_10k():
    week = type("Week", (), {})()
    week.week_number = 1
    week.total_miles = 54.0
    long_day = type("Day", (), {})()
    long_day.workout_type = "long"
    long_day.target_miles = 17.2  # Slightly below 33% floor (17.8) but within tolerance.
    threshold_day = type("Day", (), {})()
    threshold_day.workout_type = "threshold"
    threshold_day.target_miles = 7.0
    week.days = [long_day, threshold_day]

    plan = type("Plan", (), {})()
    plan.weeks = [week]
    plan.race_distance = "10k"
    plan.volume_contract = {"band_min": 45.0, "band_max": 65.0}
    plan.fitness_bank = {
        "current": {"weekly_miles": 60.0, "long_run": 22.0},
        "peak": {"long_run": 24.0},
        "volume_contract": {
            "recent_8w_p75_long_run_miles": 18.5,
            "recent_16w_p50_long_run_miles": 17.0,
            "recent_16w_run_count": 36,
        },
        "constraint": {"type": "none"},
    }

    result = evaluate_constraint_aware_plan(plan)
    assert "personal_long_run_floor_breach" not in result.invariant_conflicts
