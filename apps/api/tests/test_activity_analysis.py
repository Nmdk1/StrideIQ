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
from models import Athlete, Activity, PersonalBest, BestEffort
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
    """Create a test athlete with birthdate for age calculations"""
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
        yield athlete
        # Cleanup - delete in correct order to respect foreign keys
        # Must commit between each to ensure order is respected
        try:
            db.query(PersonalBest).filter(PersonalBest.athlete_id == athlete.id).delete()
            db.commit()
            db.query(BestEffort).filter(BestEffort.athlete_id == athlete.id).delete()
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
        """Test easy run classification (low HR)"""
        db = SessionLocal()
        try:
            # Age ~44, max HR ~176, easy = 60-70% = 106-123 bpm
            activity = Activity(
                athlete_id=test_athlete.id,
                start_time=datetime.now(),
                sport="run",
                distance_m=5000,
                avg_hr=115,  # ~65% max HR
                average_speed=Decimal('2.5')  # ~10:40/mile
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
        """Test tempo run classification (moderate HR)"""
        db = SessionLocal()
        try:
            # Tempo = 70-80% max HR = 123-141 bpm
            activity = Activity(
                athlete_id=test_athlete.id,
                start_time=datetime.now(),
                sport="run",
                distance_m=5000,
                avg_hr=135,  # ~77% max HR
                average_speed=Decimal('3.0')  # ~9:20/mile
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
    
    def test_long_run_classification(self, test_athlete):
        """Test long run classification (distance-based)"""
        db = SessionLocal()
        try:
            # Long run = >=10 miles or >=90 minutes
            activity = Activity(
                athlete_id=test_athlete.id,
                start_time=datetime.now(),
                sport="run",
                distance_m=16093,  # 10 miles
                duration_s=5400,  # 90 minutes
                avg_hr=130,  # Moderate effort
                average_speed=Decimal('2.98')  # ~9:00/mile
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


