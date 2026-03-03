"""
Comprehensive tests for Activity Analysis Service

Tests efficiency calculations, baseline comparisons, trend detection,
and run type classification.
"""
import pytest
from datetime import datetime, timedelta, date
from decimal import Decimal
from uuid import uuid4
from core.database import SessionLocal
from models import Athlete, Activity, ActivitySplit, PersonalBest, BestEffort
from services.activity_analysis import (
    ActivityAnalysis,
    EfficiencyMetrics,
    Baseline,
    analyze_activity,
    MIN_IMPROVEMENT_PCT,
    CONFIRMED_IMPROVEMENT_PCT,
    TREND_CONFIRMATION_RUNS
)


@pytest.fixture
def test_athlete():
    """Create a test athlete with birthdate and seeded HR history for classify_effort()"""
    db = SessionLocal()
    try:
        athlete = Athlete(
            email=f"test_analysis_{uuid4()}@example.com",
            display_name="Test Analysis Athlete",
            birthdate=date(1980, 1, 1),  # Age ~44
            height_cm=Decimal('175'),
            subscription_tier="free"
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)

        # Seed HR distribution so classify_effort() uses Tier 1 (percentile).
        # P40 ≈ 127, P80 ≈ 147  →  115=easy, 135=moderate, 170=hard
        seed_hrs = [110, 115, 118, 120, 122, 125, 128, 130, 132, 135, 140, 145, 155, 160, 170]
        for i, hr in enumerate(seed_hrs):
            db.add(Activity(
                athlete_id=athlete.id,
                start_time=datetime.now() - timedelta(days=60 - i),
                sport="run",
                distance_m=5000,
                duration_s=1800,
                avg_hr=hr,
                average_speed=Decimal('2.78'),
            ))
        db.commit()

        from services.effort_classification import invalidate_effort_cache
        invalidate_effort_cache(str(athlete.id))

        yield athlete
        # Cleanup - delete in correct order to respect foreign keys
        # Must commit between each to ensure order is respected
        try:
            db.query(PersonalBest).filter(PersonalBest.athlete_id == athlete.id).delete()
            db.commit()
            db.query(BestEffort).filter(BestEffort.athlete_id == athlete.id).delete()
            db.commit()
            act_ids = [a.id for a in db.query(Activity.id).filter(Activity.athlete_id == athlete.id).all()]
            if act_ids:
                db.query(ActivitySplit).filter(ActivitySplit.activity_id.in_(act_ids)).delete(synchronize_session=False)
                db.commit()
            db.query(Activity).filter(Activity.athlete_id == athlete.id).delete()
            db.commit()
            db.delete(athlete)
            db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


@pytest.fixture
def test_activity(test_athlete):
    """Create a test activity with pace and HR"""
    db = SessionLocal()
    try:
        activity = Activity(
            athlete_id=test_athlete.id,
            start_time=datetime.now(),
            sport="run",
            source="manual",
            duration_s=1800,  # 30 minutes
            distance_m=5000,  # 5K
            avg_hr=150,
            max_hr=165,
            average_speed=Decimal('2.78')  # ~9:00/mile pace
        )
        db.add(activity)
        db.commit()
        db.refresh(activity)
        yield activity
        db.delete(activity)
        db.commit()
    finally:
        db.close()


class TestEfficiencyMetrics:
    """Test EfficiencyMetrics class"""
    
    def test_efficiency_calculation(self):
        """Test efficiency score calculation"""
        metrics = EfficiencyMetrics(
            pace_per_mile=9.0,
            avg_heart_rate=150
        )
        efficiency = metrics.calculate_efficiency_score()
        assert efficiency == pytest.approx(0.06, rel=1e-2)
    
    def test_efficiency_lower_is_better(self):
        """Test that lower efficiency score = better performance"""
        metrics1 = EfficiencyMetrics(pace_per_mile=8.0, avg_heart_rate=150)
        metrics2 = EfficiencyMetrics(pace_per_mile=9.0, avg_heart_rate=150)
        
        eff1 = metrics1.calculate_efficiency_score()
        eff2 = metrics2.calculate_efficiency_score()
        
        assert eff1 < eff2  # Faster pace at same HR = better efficiency
    
    def test_efficiency_missing_data(self):
        """Test efficiency calculation with missing data"""
        metrics = EfficiencyMetrics(pace_per_mile=9.0, avg_heart_rate=None)
        assert metrics.calculate_efficiency_score() is None
        
        metrics = EfficiencyMetrics(pace_per_mile=None, avg_heart_rate=150)
        assert metrics.calculate_efficiency_score() is None
    
    def test_is_complete(self):
        """Test is_complete check"""
        assert EfficiencyMetrics(pace_per_mile=9.0, avg_heart_rate=150).is_complete()
        assert not EfficiencyMetrics(pace_per_mile=9.0, avg_heart_rate=None).is_complete()
        assert not EfficiencyMetrics(pace_per_mile=None, avg_heart_rate=150).is_complete()


class TestRunTypeClassification:
    """Test run type classification"""
    
    def test_race_classification(self, test_athlete):
        """Test race detection"""
        db = SessionLocal()
        try:
            activity = Activity(
                athlete_id=test_athlete.id,
                start_time=datetime.now(),
                sport="run",
                is_race_candidate=True,
                distance_m=5000,
                avg_hr=170,
                average_speed=Decimal('3.33')  # ~8:00/mile
            )
            db.add(activity)
            db.commit()
            
            analysis = ActivityAnalysis(activity, test_athlete, db)
            run_type = analysis._classify_run_type()
            assert run_type == "race"
            
            db.delete(activity)
            db.commit()
        finally:
            db.close()
    
    def test_easy_run_classification(self, test_athlete):
        """Test easy run classification — below P40 in seeded distribution"""
        db = SessionLocal()
        try:
            activity = Activity(
                athlete_id=test_athlete.id,
                start_time=datetime.now(),
                sport="run",
                distance_m=5000,
                avg_hr=115,
                average_speed=Decimal('2.5'),
            )
            db.add(activity)
            db.commit()

            analysis = ActivityAnalysis(activity, test_athlete, db)
            run_type = analysis._classify_run_type()
            assert run_type == "easy"

            db.delete(activity)
            db.commit()
        finally:
            db.close()

    def test_tempo_classification(self, test_athlete):
        """Test tempo (moderate effort) — between P40 and P80"""
        db = SessionLocal()
        try:
            activity = Activity(
                athlete_id=test_athlete.id,
                start_time=datetime.now(),
                sport="run",
                distance_m=5000,
                avg_hr=135,
                average_speed=Decimal('3.0'),
            )
            db.add(activity)
            db.commit()

            analysis = ActivityAnalysis(activity, test_athlete, db)
            run_type = analysis._classify_run_type()
            assert run_type == "tempo"

            db.delete(activity)
            db.commit()
        finally:
            db.close()

    def test_threshold_classification(self, test_athlete):
        """Test threshold — hard effort with steady split paces (no alternation)"""
        db = SessionLocal()
        try:
            activity = Activity(
                athlete_id=test_athlete.id,
                start_time=datetime.now(),
                sport="run",
                distance_m=8000,
                duration_s=2400,
                avg_hr=155,
                average_speed=Decimal('3.3'),
            )
            db.add(activity)
            db.commit()

            # Steady-state splits — low pace variance → threshold
            for i in range(8):
                db.add(ActivitySplit(
                    activity_id=activity.id,
                    split_number=i + 1,
                    distance=1000,
                    elapsed_time=300 + (i % 2) * 5,  # 5:00-5:05/km, minimal variance
                ))
            db.commit()

            analysis = ActivityAnalysis(activity, test_athlete, db)
            run_type = analysis._classify_run_type()
            assert run_type == "threshold"

            db.query(ActivitySplit).filter(ActivitySplit.activity_id == activity.id).delete()
            db.delete(activity)
            db.commit()
        finally:
            db.close()

    def test_interval_classification(self, test_athlete):
        """Test interval — hard effort with alternating fast/slow split paces"""
        db = SessionLocal()
        try:
            activity = Activity(
                athlete_id=test_athlete.id,
                start_time=datetime.now(),
                sport="run",
                distance_m=6000,
                duration_s=1800,
                avg_hr=155,
                average_speed=Decimal('3.3'),
            )
            db.add(activity)
            db.commit()

            # 6 splits alternating fast reps / slow recovery jogs
            split_paces = [
                (1000, 240),   # fast — 4:00/km
                (500, 200),    # slow jog — 6:40/km
                (1000, 245),   # fast
                (500, 210),    # slow jog
                (1000, 238),   # fast
                (500, 195),    # slow jog
            ]
            for i, (dist, elapsed) in enumerate(split_paces):
                db.add(ActivitySplit(
                    activity_id=activity.id,
                    split_number=i + 1,
                    distance=dist,
                    elapsed_time=elapsed,
                ))
            db.commit()

            analysis = ActivityAnalysis(activity, test_athlete, db)
            run_type = analysis._classify_run_type()
            assert run_type == "interval"

            db.query(ActivitySplit).filter(ActivitySplit.activity_id == activity.id).delete()
            db.delete(activity)
            db.commit()
        finally:
            db.close()

    def test_long_run_classification(self, test_athlete):
        """Test long run — distance-based with easy/moderate effort"""
        db = SessionLocal()
        try:
            activity = Activity(
                athlete_id=test_athlete.id,
                start_time=datetime.now(),
                sport="run",
                distance_m=16093,  # 10 miles
                duration_s=5400,   # 90 minutes
                avg_hr=130,
                average_speed=Decimal('2.98'),
            )
            db.add(activity)
            db.commit()

            analysis = ActivityAnalysis(activity, test_athlete, db)
            run_type = analysis._classify_run_type()
            assert run_type == "long_run"

            db.delete(activity)
            db.commit()
        finally:
            db.close()


class TestBaselineCalculations:
    """Test baseline calculation methods"""
    
    def test_pr_baseline(self, test_athlete):
        """Test PR baseline retrieval"""
        db = SessionLocal()
        try:
            # Create a PR
            pr_activity = Activity(
                athlete_id=test_athlete.id,
                start_time=datetime.now() - timedelta(days=30),
                sport="run",
                distance_m=5000,
                avg_hr=165,
                average_speed=Decimal('3.33')  # 8:00/mile
            )
            db.add(pr_activity)
            db.commit()
            
            pb = PersonalBest(
                athlete_id=test_athlete.id,
                distance_category="5k",
                distance_meters=5000,
                time_seconds=1500,  # 25:00
                pace_per_mile=8.0,
                activity_id=pr_activity.id,
                achieved_at=pr_activity.start_time,
                is_race=True
            )
            db.add(pb)
            db.commit()
            
            # Create current activity
            current_activity = Activity(
                athlete_id=test_athlete.id,
                start_time=datetime.now(),
                sport="run",
                distance_m=5000,
                avg_hr=150,  # Lower HR
                average_speed=Decimal('3.33')  # Same pace
            )
            db.add(current_activity)
            db.commit()
            
            analysis = ActivityAnalysis(current_activity, test_athlete, db)
            baselines = analysis.get_all_baselines()
            
            pr_baseline = next((b for b in baselines if b.baseline_type == "pr"), None)
            assert pr_baseline is not None
            assert pr_baseline.pace_per_mile == pytest.approx(8.0, rel=0.1)
            assert pr_baseline.avg_heart_rate == 165
            
            # Cleanup - must commit between deletes for FK order
            db.delete(current_activity)
            db.commit()
            db.delete(pb)
            db.commit()
            db.delete(pr_activity)
            db.commit()
        finally:
            db.close()
    
    def test_current_block_baseline(self, test_athlete):
        """Test current block baseline calculation"""
        db = SessionLocal()
        try:
            # Create multiple activities in last 6 weeks
            base_time = datetime.now()
            activities = []
            for i in range(5):
                activity = Activity(
                    athlete_id=test_athlete.id,
                    start_time=base_time - timedelta(weeks=i),
                    sport="run",
                    distance_m=5000,
                    avg_hr=150 + i,
                    average_speed=Decimal('2.78')  # ~9:00/mile
                )
                db.add(activity)
                activities.append(activity)
            db.commit()
            
            # Create current activity
            current_activity = Activity(
                athlete_id=test_athlete.id,
                start_time=base_time,
                sport="run",
                distance_m=5000,
                avg_hr=145,  # Lower HR
                average_speed=Decimal('2.78')  # Same pace
            )
            db.add(current_activity)
            db.commit()
            
            analysis = ActivityAnalysis(current_activity, test_athlete, db)
            baselines = analysis.get_all_baselines()
            
            block_baseline = next((b for b in baselines if b.baseline_type == "current_block"), None)
            assert block_baseline is not None
            assert block_baseline.sample_size >= 3
            
            # Cleanup
            db.delete(current_activity)
            for activity in activities:
                db.delete(activity)
            db.commit()
        finally:
            db.close()


class TestTrendConfirmation:
    """Test trend confirmation logic"""
    
    def test_trend_confirmation_requires_multiple_runs(self, test_athlete):
        """Test that trend confirmation requires multiple runs"""
        db = SessionLocal()
        try:
            # Create baseline activity
            baseline_activity = Activity(
                athlete_id=test_athlete.id,
                start_time=datetime.now() - timedelta(weeks=2),
                sport="run",
                distance_m=5000,
                avg_hr=150,
                average_speed=Decimal('2.78')  # 9:00/mile
            )
            db.add(baseline_activity)
            db.commit()
            
            # Create single improved activity (not enough for trend)
            current_activity = Activity(
                athlete_id=test_athlete.id,
                start_time=datetime.now(),
                sport="run",
                distance_m=5000,
                avg_hr=145,  # Lower HR
                average_speed=Decimal('2.78')  # Same pace
            )
            db.add(current_activity)
            db.commit()
            
            analysis = ActivityAnalysis(current_activity, test_athlete, db)
            result = analysis.analyze()
            
            # Should not have confirmed trend with only 1 run
            comparisons = result.get("comparisons", [])
            for comp in comparisons:
                if comp.get("baseline_type") == "current_block":
                    assert comp.get("is_confirmed_trend") == False
            
            # Cleanup
            db.delete(current_activity)
            db.delete(baseline_activity)
            db.commit()
        finally:
            db.close()
    
    def test_meaningful_improvement_threshold(self, test_athlete):
        """Test that improvements must meet 2-3% threshold"""
        db = SessionLocal()
        try:
            # Create baseline with known efficiency
            baseline_activity = Activity(
                athlete_id=test_athlete.id,
                start_time=datetime.now() - timedelta(weeks=2),
                sport="run",
                distance_m=5000,
                avg_hr=150,
                average_speed=Decimal('2.78')  # 9:00/mile, efficiency = 9.0/150 = 0.06
            )
            db.add(baseline_activity)
            db.commit()
            
            # Create activity with small improvement (<2%)
            # Efficiency = 8.9/150 = 0.0593, improvement = (0.06-0.0593)/0.06 = 1.17%
            current_activity = Activity(
                athlete_id=test_athlete.id,
                start_time=datetime.now(),
                sport="run",
                distance_m=5000,
                avg_hr=150,
                average_speed=Decimal('2.79')  # Slightly faster, but <2% improvement
            )
            db.add(current_activity)
            db.commit()
            
            analysis = ActivityAnalysis(current_activity, test_athlete, db)
            result = analysis.analyze()
            
            # Should not flag as meaningful (below threshold)
            assert result.get("has_meaningful_insight") == False
            
            # Cleanup
            db.delete(current_activity)
            db.delete(baseline_activity)
            db.commit()
        finally:
            db.close()


class TestActivityAnalysisIntegration:
    """Integration tests for full analysis flow"""
    
    def test_analysis_without_complete_data(self, test_athlete):
        """Test analysis when activity lacks pace or HR"""
        db = SessionLocal()
        try:
            activity = Activity(
                athlete_id=test_athlete.id,
                start_time=datetime.now(),
                sport="run",
                distance_m=5000,
                avg_hr=None,  # Missing HR
                average_speed=Decimal('2.78')
            )
            db.add(activity)
            db.commit()
            
            analysis = ActivityAnalysis(activity, test_athlete, db)
            result = analysis.analyze()
            
            assert result.get("has_meaningful_insight") == False
            assert result.get("metrics", {}).get("efficiency_score") is None
            
            db.delete(activity)
            db.commit()
        finally:
            db.close()
    
    def test_analysis_with_all_baselines(self, test_athlete):
        """Test analysis with multiple baseline types available"""
        db = SessionLocal()
        try:
            # Create PR
            pr_activity = Activity(
                athlete_id=test_athlete.id,
                start_time=datetime.now() - timedelta(days=60),
                sport="run",
                distance_m=5000,
                avg_hr=165,
                average_speed=Decimal('3.33'),
                is_race_candidate=True
            )
            db.add(pr_activity)
            db.commit()
            
            pb = PersonalBest(
                athlete_id=test_athlete.id,
                distance_category="5k",
                distance_meters=5000,
                time_seconds=1500,
                pace_per_mile=8.0,
                activity_id=pr_activity.id,
                achieved_at=pr_activity.start_time,
                is_race=True
            )
            db.add(pb)
            db.commit()
            
            # Create historical activities for baselines
            base_time = datetime.now()
            for i in range(5):
                activity = Activity(
                    athlete_id=test_athlete.id,
                    start_time=base_time - timedelta(weeks=i+1),
                    sport="run",
                    distance_m=5000,
                    avg_hr=150,
                    average_speed=Decimal('2.78')
                )
                db.add(activity)
            db.commit()
            
            # Create current improved activity
            current_activity = Activity(
                athlete_id=test_athlete.id,
                start_time=base_time,
                sport="run",
                distance_m=5000,
                avg_hr=145,  # Lower HR at same pace
                average_speed=Decimal('2.78')
            )
            db.add(current_activity)
            db.commit()
            
            analysis = ActivityAnalysis(current_activity, test_athlete, db)
            result = analysis.analyze()
            
            # Should have multiple baseline comparisons
            comparisons = result.get("comparisons", [])
            assert len(comparisons) > 0
            
            # Should have efficiency metrics
            assert result.get("metrics", {}).get("efficiency_score") is not None

            # Cleanup - must delete pb first (FK constraint)
            db.delete(pb)
            db.commit()
            db.query(Activity).filter(Activity.athlete_id == test_athlete.id).delete()
            db.commit()
        finally:
            db.close()


