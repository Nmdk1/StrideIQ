"""
Comprehensive tests for Activity Analysis Service

Tests efficiency calculations, baseline comparisons, trend detection,
and run type classification.
"""
import pytest
from datetime import datetime, timedelta, date
from decimal import Decimal
from uuid import uuid4
from services.activity_analysis import (
    ActivityAnalysis,
    EfficiencyMetrics,
    Baseline,
    analyze_activity,
    MIN_IMPROVEMENT_PCT,
    CONFIRMED_IMPROVEMENT_PCT,
    TREND_CONFIRMATION_RUNS
)

try:
    from models import Athlete, Activity, ActivitySplit, PersonalBest, BestEffort
    _MODELS_OK = True
except Exception:
    _MODELS_OK = False


@pytest.fixture
def analysis_athlete(db_session):
    """Create a test athlete with birthdate and seeded HR history for classify_effort()"""
    athlete = Athlete(
        email=f"test_analysis_{uuid4()}@example.com",
        display_name="Test Analysis Athlete",
        birthdate=date(1980, 1, 1),
        height_cm=Decimal('175'),
        subscription_tier="free"
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)

    seed_hrs = [110, 115, 118, 120, 122, 125, 128, 130, 132, 135, 140, 145, 155, 160, 170]
    for i, hr in enumerate(seed_hrs):
        db_session.add(Activity(
            athlete_id=athlete.id,
            start_time=datetime.now() - timedelta(days=60 - i),
            sport="run",
            distance_m=5000,
            duration_s=1800,
            avg_hr=hr,
            average_speed=Decimal('2.78'),
        ))
    db_session.commit()

    from services.effort_classification import invalidate_effort_cache
    invalidate_effort_cache(str(athlete.id))

    return athlete


class TestEfficiencyMetrics:

    def test_efficiency_calculation(self):
        metrics = EfficiencyMetrics(
            pace_per_mile=9.0,
            avg_heart_rate=150
        )
        efficiency = metrics.calculate_efficiency_score()
        assert efficiency == pytest.approx(0.06, rel=1e-2)

    def test_efficiency_lower_is_better(self):
        metrics1 = EfficiencyMetrics(pace_per_mile=8.0, avg_heart_rate=150)
        metrics2 = EfficiencyMetrics(pace_per_mile=9.0, avg_heart_rate=150)
        assert metrics1.calculate_efficiency_score() < metrics2.calculate_efficiency_score()

    def test_efficiency_missing_data(self):
        metrics = EfficiencyMetrics(pace_per_mile=9.0, avg_heart_rate=None)
        assert metrics.calculate_efficiency_score() is None

        metrics = EfficiencyMetrics(pace_per_mile=None, avg_heart_rate=150)
        assert metrics.calculate_efficiency_score() is None

    def test_is_complete(self):
        assert EfficiencyMetrics(pace_per_mile=9.0, avg_heart_rate=150).is_complete()
        assert not EfficiencyMetrics(pace_per_mile=9.0, avg_heart_rate=None).is_complete()
        assert not EfficiencyMetrics(pace_per_mile=None, avg_heart_rate=150).is_complete()


class TestRunTypeClassification:

    def test_race_classification(self, analysis_athlete, db_session):
        activity = Activity(
            athlete_id=analysis_athlete.id,
            start_time=datetime.now(),
            sport="run",
            is_race_candidate=True,
            distance_m=5000,
            avg_hr=170,
            average_speed=Decimal('3.33')
        )
        db_session.add(activity)
        db_session.commit()

        analysis = ActivityAnalysis(activity, analysis_athlete, db_session)
        run_type = analysis._classify_run_type()
        assert run_type == "race"

    def test_easy_run_classification(self, analysis_athlete, db_session):
        activity = Activity(
            athlete_id=analysis_athlete.id,
            start_time=datetime.now(),
            sport="run",
            distance_m=5000,
            avg_hr=115,
            average_speed=Decimal('2.5'),
        )
        db_session.add(activity)
        db_session.commit()

        analysis = ActivityAnalysis(activity, analysis_athlete, db_session)
        run_type = analysis._classify_run_type()
        assert run_type == "easy"

    def test_tempo_classification(self, analysis_athlete, db_session):
        activity = Activity(
            athlete_id=analysis_athlete.id,
            start_time=datetime.now(),
            sport="run",
            distance_m=5000,
            avg_hr=135,
            average_speed=Decimal('3.0'),
        )
        db_session.add(activity)
        db_session.commit()

        analysis = ActivityAnalysis(activity, analysis_athlete, db_session)
        run_type = analysis._classify_run_type()
        assert run_type == "tempo"

    def test_threshold_classification(self, analysis_athlete, db_session):
        activity = Activity(
            athlete_id=analysis_athlete.id,
            start_time=datetime.now(),
            sport="run",
            distance_m=8000,
            duration_s=2400,
            avg_hr=155,
            average_speed=Decimal('3.3'),
        )
        db_session.add(activity)
        db_session.commit()

        for i in range(8):
            db_session.add(ActivitySplit(
                activity_id=activity.id,
                split_number=i + 1,
                distance=1000,
                elapsed_time=300 + (i % 2) * 5,
            ))
        db_session.commit()

        analysis = ActivityAnalysis(activity, analysis_athlete, db_session)
        run_type = analysis._classify_run_type()
        assert run_type == "threshold"

    def test_interval_classification(self, analysis_athlete, db_session):
        activity = Activity(
            athlete_id=analysis_athlete.id,
            start_time=datetime.now(),
            sport="run",
            distance_m=6000,
            duration_s=1800,
            avg_hr=155,
            average_speed=Decimal('3.3'),
        )
        db_session.add(activity)
        db_session.commit()

        split_paces = [
            (1000, 240), (500, 200), (1000, 245),
            (500, 210), (1000, 238), (500, 195),
        ]
        for i, (dist, elapsed) in enumerate(split_paces):
            db_session.add(ActivitySplit(
                activity_id=activity.id,
                split_number=i + 1,
                distance=dist,
                elapsed_time=elapsed,
            ))
        db_session.commit()

        analysis = ActivityAnalysis(activity, analysis_athlete, db_session)
        run_type = analysis._classify_run_type()
        assert run_type == "interval"

    def test_long_run_classification(self, analysis_athlete, db_session):
        activity = Activity(
            athlete_id=analysis_athlete.id,
            start_time=datetime.now(),
            sport="run",
            distance_m=16093,
            duration_s=5400,
            avg_hr=130,
            average_speed=Decimal('2.98'),
        )
        db_session.add(activity)
        db_session.commit()

        analysis = ActivityAnalysis(activity, analysis_athlete, db_session)
        run_type = analysis._classify_run_type()
        assert run_type == "long_run"


class TestBaselineCalculations:

    def test_pr_baseline(self, analysis_athlete, db_session):
        pr_activity = Activity(
            athlete_id=analysis_athlete.id,
            start_time=datetime.now() - timedelta(days=30),
            sport="run",
            distance_m=5000,
            avg_hr=165,
            average_speed=Decimal('3.33')
        )
        db_session.add(pr_activity)
        db_session.commit()

        pb = PersonalBest(
            athlete_id=analysis_athlete.id,
            distance_category="5k",
            distance_meters=5000,
            time_seconds=1500,
            pace_per_mile=8.0,
            activity_id=pr_activity.id,
            achieved_at=pr_activity.start_time,
            is_race=True
        )
        db_session.add(pb)
        db_session.commit()

        current_activity = Activity(
            athlete_id=analysis_athlete.id,
            start_time=datetime.now(),
            sport="run",
            distance_m=5000,
            avg_hr=150,
            average_speed=Decimal('3.33')
        )
        db_session.add(current_activity)
        db_session.commit()

        analysis = ActivityAnalysis(current_activity, analysis_athlete, db_session)
        baselines = analysis.get_all_baselines()

        pr_baseline = next((b for b in baselines if b.baseline_type == "pr"), None)
        assert pr_baseline is not None
        assert pr_baseline.pace_per_mile == pytest.approx(8.0, rel=0.1)
        assert pr_baseline.avg_heart_rate == 165

    def test_current_block_baseline(self, analysis_athlete, db_session):
        base_time = datetime.now()
        for i in range(5):
            activity = Activity(
                athlete_id=analysis_athlete.id,
                start_time=base_time - timedelta(weeks=i),
                sport="run",
                distance_m=5000,
                avg_hr=150 + i,
                average_speed=Decimal('2.78')
            )
            db_session.add(activity)
        db_session.commit()

        current_activity = Activity(
            athlete_id=analysis_athlete.id,
            start_time=base_time,
            sport="run",
            distance_m=5000,
            avg_hr=145,
            average_speed=Decimal('2.78')
        )
        db_session.add(current_activity)
        db_session.commit()

        analysis = ActivityAnalysis(current_activity, analysis_athlete, db_session)
        baselines = analysis.get_all_baselines()

        block_baseline = next((b for b in baselines if b.baseline_type == "current_block"), None)
        assert block_baseline is not None
        assert block_baseline.sample_size >= 3


class TestTrendConfirmation:

    def test_trend_confirmation_requires_multiple_runs(self, analysis_athlete, db_session):
        baseline_activity = Activity(
            athlete_id=analysis_athlete.id,
            start_time=datetime.now() - timedelta(weeks=2),
            sport="run",
            distance_m=5000,
            avg_hr=150,
            average_speed=Decimal('2.78')
        )
        db_session.add(baseline_activity)
        db_session.commit()

        current_activity = Activity(
            athlete_id=analysis_athlete.id,
            start_time=datetime.now(),
            sport="run",
            distance_m=5000,
            avg_hr=145,
            average_speed=Decimal('2.78')
        )
        db_session.add(current_activity)
        db_session.commit()

        analysis = ActivityAnalysis(current_activity, analysis_athlete, db_session)
        result = analysis.analyze()

        comparisons = result.get("comparisons", [])
        for comp in comparisons:
            if comp.get("baseline_type") == "current_block":
                assert comp.get("is_confirmed_trend") == False

    def test_meaningful_improvement_threshold(self, analysis_athlete, db_session):
        baseline_activity = Activity(
            athlete_id=analysis_athlete.id,
            start_time=datetime.now() - timedelta(weeks=2),
            sport="run",
            distance_m=5000,
            avg_hr=150,
            average_speed=Decimal('2.78')
        )
        db_session.add(baseline_activity)
        db_session.commit()

        current_activity = Activity(
            athlete_id=analysis_athlete.id,
            start_time=datetime.now(),
            sport="run",
            distance_m=5000,
            avg_hr=150,
            average_speed=Decimal('2.79')
        )
        db_session.add(current_activity)
        db_session.commit()

        analysis = ActivityAnalysis(current_activity, analysis_athlete, db_session)
        result = analysis.analyze()
        assert result.get("has_meaningful_insight") == False


class TestActivityAnalysisIntegration:

    def test_analysis_without_complete_data(self, analysis_athlete, db_session):
        activity = Activity(
            athlete_id=analysis_athlete.id,
            start_time=datetime.now(),
            sport="run",
            distance_m=5000,
            avg_hr=None,
            average_speed=Decimal('2.78')
        )
        db_session.add(activity)
        db_session.commit()

        analysis = ActivityAnalysis(activity, analysis_athlete, db_session)
        result = analysis.analyze()

        assert result.get("has_meaningful_insight") == False
        assert result.get("metrics", {}).get("efficiency_score") is None

    def test_analysis_with_all_baselines(self, analysis_athlete, db_session):
        pr_activity = Activity(
            athlete_id=analysis_athlete.id,
            start_time=datetime.now() - timedelta(days=60),
            sport="run",
            distance_m=5000,
            avg_hr=165,
            average_speed=Decimal('3.33'),
            is_race_candidate=True
        )
        db_session.add(pr_activity)
        db_session.commit()

        pb = PersonalBest(
            athlete_id=analysis_athlete.id,
            distance_category="5k",
            distance_meters=5000,
            time_seconds=1500,
            pace_per_mile=8.0,
            activity_id=pr_activity.id,
            achieved_at=pr_activity.start_time,
            is_race=True
        )
        db_session.add(pb)
        db_session.commit()

        base_time = datetime.now()
        for i in range(5):
            activity = Activity(
                athlete_id=analysis_athlete.id,
                start_time=base_time - timedelta(weeks=i+1),
                sport="run",
                distance_m=5000,
                avg_hr=150,
                average_speed=Decimal('2.78')
            )
            db_session.add(activity)
        db_session.commit()

        current_activity = Activity(
            athlete_id=analysis_athlete.id,
            start_time=base_time,
            sport="run",
            distance_m=5000,
            avg_hr=145,
            average_speed=Decimal('2.78')
        )
        db_session.add(current_activity)
        db_session.commit()

        analysis = ActivityAnalysis(current_activity, analysis_athlete, db_session)
        result = analysis.analyze()

        comparisons = result.get("comparisons", [])
        assert len(comparisons) > 0
        assert result.get("metrics", {}).get("efficiency_score") is not None
