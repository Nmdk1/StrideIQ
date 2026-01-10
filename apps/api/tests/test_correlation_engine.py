"""
Comprehensive tests for the Correlation Analysis Engine.

Tests statistical validity, data alignment, time-shifted correlations,
and edge cases.
"""

import pytest
from datetime import datetime, timedelta, date
from decimal import Decimal
from sqlalchemy.orm import Session
from models import (
    Athlete, Activity, ActivitySplit, NutritionEntry, DailyCheckin,
    WorkPattern, BodyComposition
)
from services.correlation_engine import (
    calculate_pearson_correlation,
    classify_correlation_strength,
    aggregate_daily_inputs,
    aggregate_efficiency_outputs,
    find_time_shifted_correlations,
    analyze_correlations,
    CorrelationResult,
    _align_time_series
)


class TestCorrelationCalculations:
    """Test core correlation calculation functions."""
    
    def test_pearson_correlation_positive(self):
        """Test positive correlation."""
        x = [1, 2, 3, 4, 5]
        y = [2, 4, 6, 8, 10]
        r, p = calculate_pearson_correlation(x, y)
        assert abs(r - 1.0) < 0.01  # Perfect positive correlation
        assert p < 0.05  # Should be significant
    
    def test_pearson_correlation_negative(self):
        """Test negative correlation."""
        x = [1, 2, 3, 4, 5]
        y = [10, 8, 6, 4, 2]
        r, p = calculate_pearson_correlation(x, y)
        assert abs(r - (-1.0)) < 0.01  # Perfect negative correlation
        assert p < 0.05  # Should be significant
    
    def test_pearson_correlation_no_correlation(self):
        """Test no correlation."""
        x = [1, 2, 3, 4, 5]
        y = [5, 2, 8, 1, 9]  # Random
        r, p = calculate_pearson_correlation(x, y)
        assert abs(r) < 0.5  # Weak correlation
        assert p > 0.05  # Not significant
    
    def test_pearson_correlation_insufficient_data(self):
        """Test with insufficient data."""
        x = [1, 2, 3]
        y = [2, 4, 6]
        r, p = calculate_pearson_correlation(x, y)
        assert p == 1.0  # Should return p=1.0 for insufficient data
    
    def test_classify_correlation_strength(self):
        """Test correlation strength classification."""
        assert classify_correlation_strength(0.2) == "weak"
        assert classify_correlation_strength(0.5) == "moderate"
        assert classify_correlation_strength(0.8) == "strong"
        assert classify_correlation_strength(-0.5) == "moderate"
        assert classify_correlation_strength(-0.9) == "strong"


class TestTimeSeriesAlignment:
    """Test time series alignment functions."""
    
    def test_align_time_series_perfect_match(self):
        """Test alignment with perfect date matches."""
        series1 = [
            (date(2024, 1, 1), 10.0),
            (date(2024, 1, 2), 20.0),
            (date(2024, 1, 3), 30.0),
        ]
        series2 = [
            (date(2024, 1, 1), 5.0),
            (date(2024, 1, 2), 10.0),
            (date(2024, 1, 3), 15.0),
        ]
        aligned = _align_time_series(series1, series2)
        assert len(aligned) == 3
        assert aligned[0] == (10.0, 5.0)
        assert aligned[1] == (20.0, 10.0)
        assert aligned[2] == (30.0, 15.0)
    
    def test_align_time_series_partial_match(self):
        """Test alignment with partial date matches."""
        series1 = [
            (date(2024, 1, 1), 10.0),
            (date(2024, 1, 2), 20.0),
            (date(2024, 1, 3), 30.0),
        ]
        series2 = [
            (date(2024, 1, 1), 5.0),
            (date(2024, 1, 3), 15.0),
        ]
        aligned = _align_time_series(series1, series2)
        assert len(aligned) == 2
        assert aligned[0] == (10.0, 5.0)
        assert aligned[1] == (30.0, 15.0)
    
    def test_align_time_series_no_match(self):
        """Test alignment with no matching dates."""
        series1 = [
            (date(2024, 1, 1), 10.0),
            (date(2024, 1, 2), 20.0),
        ]
        series2 = [
            (date(2024, 1, 3), 5.0),
            (date(2024, 1, 4), 10.0),
        ]
        aligned = _align_time_series(series1, series2)
        assert len(aligned) == 0


class TestDataAggregation:
    """Test data aggregation functions."""
    
    def test_aggregate_daily_inputs_sleep(self, db_session: Session, test_athlete: Athlete):
        """Test sleep data aggregation."""
        # Create test data
        for i in range(10):
            checkin = DailyCheckin(
                athlete_id=test_athlete.id,
                date=date.today() - timedelta(days=i),
                sleep_h=Decimal('7.5') + Decimal(str(i * 0.1))
            )
            db_session.add(checkin)
        db_session.commit()
        
        start_date = datetime.utcnow() - timedelta(days=15)
        end_date = datetime.utcnow()
        
        inputs = aggregate_daily_inputs(
            str(test_athlete.id),
            start_date,
            end_date,
            db_session
        )
        
        assert "sleep_hours" in inputs
        assert len(inputs["sleep_hours"]) == 10
    
    def test_aggregate_daily_inputs_nutrition(self, db_session: Session, test_athlete: Athlete):
        """Test nutrition data aggregation."""
        # Create test data
        for i in range(10):
            nutrition = NutritionEntry(
                athlete_id=test_athlete.id,
                date=date.today() - timedelta(days=i),
                entry_type='daily',
                protein_g=Decimal('100') + Decimal(str(i * 5))
            )
            db_session.add(nutrition)
        db_session.commit()
        
        start_date = datetime.utcnow() - timedelta(days=15)
        end_date = datetime.utcnow()
        
        inputs = aggregate_daily_inputs(
            str(test_athlete.id),
            start_date,
            end_date,
            db_session
        )
        
        assert "daily_protein_g" in inputs
        assert len(inputs["daily_protein_g"]) == 10
    
    def test_aggregate_efficiency_outputs(self, db_session: Session, test_athlete: Athlete):
        """Test efficiency output aggregation."""
        # Create test activities with splits
        for i in range(5):
            activity = Activity(
                athlete_id=test_athlete.id,
                start_time=datetime.utcnow() - timedelta(days=i),
                sport='run',
                source='test',
                duration_s=3600,
                distance_m=5000,
                avg_hr=150,
                average_speed=Decimal('3.0')
            )
            db_session.add(activity)
            db_session.flush()
            
            # Create splits
            for split_num in range(1, 6):
                split = ActivitySplit(
                    activity_id=activity.id,
                    split_number=split_num,
                    distance=Decimal('1000'),
                    moving_time=200,
                    average_heartrate=150,
                    gap_seconds_per_mile=Decimal('400')
                )
                db_session.add(split)
        
        db_session.commit()
        
        start_date = datetime.utcnow() - timedelta(days=10)
        end_date = datetime.utcnow()
        
        outputs = aggregate_efficiency_outputs(
            str(test_athlete.id),
            start_date,
            end_date,
            db_session
        )
        
        assert len(outputs) == 5
        assert all(isinstance(item[1], float) for item in outputs)


class TestTimeShiftedCorrelations:
    """Test time-shifted correlation detection."""
    
    def test_find_time_shifted_correlations(self):
        """Test finding correlations with time shifts."""
        # Create data where input 1 day before affects output
        input_data = [
            (date(2024, 1, 1), 7.0),
            (date(2024, 1, 2), 8.0),
            (date(2024, 1, 3), 9.0),
            (date(2024, 1, 4), 8.5),
            (date(2024, 1, 5), 7.5),
        ]
        
        # Output is correlated with input from 1 day before
        output_data = [
            (date(2024, 1, 2), 10.0),  # Correlates with input from day 1
            (date(2024, 1, 3), 12.0),  # Correlates with input from day 2
            (date(2024, 1, 4), 13.0),  # Correlates with input from day 3
            (date(2024, 1, 5), 12.5),  # Correlates with input from day 4
            (date(2024, 1, 6), 11.5),  # Correlates with input from day 5
        ]
        
        results = find_time_shifted_correlations(
            input_data,
            output_data,
            max_lag_days=3
        )
        
        # Should find correlation at lag 1 day
        assert len(results) > 0
        lag_1_results = [r for r in results if r.time_lag_days == 1]
        assert len(lag_1_results) > 0


class TestFullCorrelationAnalysis:
    """Test full correlation analysis pipeline."""
    
    def test_analyze_correlations_insufficient_data(self, db_session: Session, test_athlete: Athlete):
        """Test with insufficient data."""
        result = analyze_correlations(
            athlete_id=str(test_athlete.id),
            days=90,
            db=db_session
        )
        
        assert "error" in result
        assert result["sample_size"] < 10
    
    def test_analyze_correlations_with_data(
        self, 
        db_session: Session, 
        test_athlete: Athlete
    ):
        """Test full analysis with sufficient data."""
        # Create activities with splits
        for i in range(15):
            activity = Activity(
                athlete_id=test_athlete.id,
                start_time=datetime.utcnow() - timedelta(days=i),
                sport='run',
                source='test',
                duration_s=3600,
                distance_m=5000,
                avg_hr=150,
                average_speed=Decimal('3.0')
            )
            db_session.add(activity)
            db_session.flush()
            
            # Create splits
            for split_num in range(1, 6):
                split = ActivitySplit(
                    activity_id=activity.id,
                    split_number=split_num,
                    distance=Decimal('1000'),
                    moving_time=200,
                    average_heartrate=150,
                    gap_seconds_per_mile=Decimal('400')
                )
                db_session.add(split)
        
        # Create sleep data (correlated with efficiency)
        for i in range(15):
            checkin = DailyCheckin(
                athlete_id=test_athlete.id,
                date=date.today() - timedelta(days=i),
                sleep_h=Decimal('7.5')
            )
            db_session.add(checkin)
        
        db_session.commit()
        
        result = analyze_correlations(
            athlete_id=str(test_athlete.id),
            days=30,
            db=db_session
        )
        
        assert "error" not in result
        assert "correlations" in result
        assert "sample_sizes" in result
        assert isinstance(result["correlations"], list)


@pytest.fixture
def test_athlete(db_session: Session) -> Athlete:
    """Create a test athlete."""
    athlete = Athlete(
        email=f"test_{datetime.now().timestamp()}@test.com",
        display_name="Test Athlete"
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)
    return athlete


