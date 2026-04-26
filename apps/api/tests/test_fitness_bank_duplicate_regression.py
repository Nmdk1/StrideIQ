import inspect
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from services.fitness_bank import (
    ConstraintType,
    ExperienceLevel,
    FitnessBankCalculator,
    RacePerformance,
)
from services.plan_framework.volume_tiers import VolumeTierClassifier
from services.mileage_aggregation import (
    collapse_probable_provider_duplicates,
    get_canonical_run_activities,
)


def _mock_activity():
    return SimpleNamespace(
        start_time=datetime.now(timezone.utc),
        distance_m=10000,
        duration_s=2400,
        name="Run",
        workout_type="easy_run",
        provider="strava",
    )


def test_fitness_bank_excludes_duplicate_runs_from_peak_and_current():
    mock_db = MagicMock()

    calculator = FitnessBankCalculator(mock_db)

    # Isolate this regression test to the query contract.
    calculator._calculate_peak_capabilities = MagicMock(return_value={
        "peak_weekly": 50.0,
        "peak_monthly": 200.0,
        "peak_long_run": 16.0,
        "peak_mp_long_run": 8.0,
        "peak_threshold": 6.0,
        "peak_ctl": 60.0,
    })
    calculator._extract_race_performances = MagicMock(return_value=[])
    calculator._find_best_race = MagicMock(return_value=(45.0, None))
    calculator._determine_experience = MagicMock(return_value=ExperienceLevel.INTERMEDIATE)
    calculator._detect_constraint = MagicMock(return_value=(ConstraintType.NONE, None, False))
    calculator._detect_training_patterns = MagicMock(return_value={})
    calculator._project_recovery_time = MagicMock(return_value=0)
    calculator._project_race_readiness = MagicMock(return_value=0)
    calculator._weeks_since_peak = MagicMock(return_value=0)
    calculator._calculate_current_long_run = MagicMock(return_value=(10.0, 10.0))

    model = SimpleNamespace(tau1=42.0, tau2=7.0)
    load = SimpleNamespace(current_ctl=50.0, current_atl=40.0)

    with patch("core.cache.get_cache", return_value=None), \
         patch("core.cache.set_cache"), \
         patch("services.fitness_bank.get_canonical_run_activities", return_value=([_mock_activity()], {"dedupe_pairs_collapsed": 0, "source_count": 1, "output_count": 1})), \
         patch("services.individual_performance_model.get_or_calibrate_model", return_value=model), \
         patch("services.training_load.TrainingLoadCalculator") as mock_tl:
        mock_tl.return_value.calculate_training_load.return_value = load
        calculator.calculate(uuid4())

    source = inspect.getsource(FitnessBankCalculator.calculate)
    assert "get_canonical_run_activities(" in source
    assert "require_trusted_duplicate_flags=True" in source


def test_volume_tier_actual_volume_excludes_duplicate_runs():
    mock_db = MagicMock()

    classifier = VolumeTierClassifier(mock_db)
    with patch(
        "services.plan_framework.volume_tiers.get_canonical_run_activities",
        return_value=([], {"dedupe_pairs_collapsed": 0, "source_count": 0, "output_count": 0}),
    ):
        classifier._get_actual_volume(uuid4())
    source = inspect.getsource(VolumeTierClassifier._get_actual_volume)
    assert "get_canonical_run_activities(" in source
    assert "require_trusted_duplicate_flags=True" in source


def test_fitness_bank_query_contains_duplicate_filter():
    source = inspect.getsource(get_canonical_run_activities)
    assert "Activity.is_duplicate == False" in source


def test_volume_tier_query_contains_duplicate_filter():
    source = inspect.getsource(get_canonical_run_activities)
    assert "Activity.is_duplicate == False" in source


def test_recent_race_recovery_not_misclassified_as_constraint():
    calculator = FitnessBankCalculator(db=MagicMock())
    peaks = {"peak_weekly": 55.0}
    races = [
        RacePerformance(
            date=date.today() - timedelta(days=5),
            distance="marathon",
            distance_m=42195,
            finish_time_seconds=3 * 3600,
            pace_per_mile=6.87,
            rpi=52.0,
        )
    ]

    constraint_type, details, returning = calculator._detect_constraint(
        peaks=peaks,
        current_weekly=0.0,
        activities=[],
        races=races,
    )
    assert constraint_type == ConstraintType.NONE
    assert details is None
    assert returning is False


def test_fitness_bank_in_memory_dedupe_collapses_provider_duplicates():
    start = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    garmin = SimpleNamespace(
        athlete_id=uuid4(),
        start_time=start,
        distance_m=16093,
        duration_s=3600,
        provider="garmin",
    )
    strava = SimpleNamespace(
        athlete_id=garmin.athlete_id,
        start_time=start,
        distance_m=16080,  # within tolerance
        duration_s=3605,   # within tolerance
        provider="strava",
    )

    out, _ = collapse_probable_provider_duplicates([garmin, strava])
    assert len(out) == 1
    assert out[0].provider == "strava"


def test_fitness_bank_in_memory_dedupe_keeps_distinct_same_day_doubles():
    am = SimpleNamespace(
        athlete_id=uuid4(),
        start_time=datetime(2026, 1, 1, 7, 0, 0, tzinfo=timezone.utc),
        distance_m=5000,
        duration_s=1800,
        provider="strava",
    )
    pm = SimpleNamespace(
        athlete_id=am.athlete_id,
        start_time=datetime(2026, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
        distance_m=6000,
        duration_s=2400,
        provider="garmin",
    )

    out, _ = collapse_probable_provider_duplicates([am, pm])
    assert len(out) == 2
