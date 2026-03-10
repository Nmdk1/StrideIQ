"""
Unit tests for Efficiency Trending Service (V2)

Tests statistical trend detection, confidence classification,
and insight generation.

ADR-008: Efficiency Factor Trending Enhancement
"""

import pytest
from datetime import datetime, timedelta
from services.efficiency_trending import (
    analyze_efficiency_trend,
    linear_regression,
    calculate_p_value_from_t,
    calculate_efficiency_percentile,
    estimate_days_to_pr_efficiency,
    TrendDirection,
    TrendConfidence,
    to_dict
)


class TestLinearRegression:
    """Test linear regression calculations."""
    
    def test_perfect_positive_correlation(self):
        """Perfect positive linear relationship."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 4.0, 6.0, 8.0, 10.0]  # y = 2x
        
        slope, intercept, r_squared, std_error = linear_regression(x, y)
        
        assert abs(slope - 2.0) < 0.001
        assert abs(intercept - 0.0) < 0.001
        assert abs(r_squared - 1.0) < 0.001
        assert std_error < 0.001
    
    def test_perfect_negative_correlation(self):
        """Perfect negative linear relationship."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [10.0, 8.0, 6.0, 4.0, 2.0]  # y = -2x + 12
        
        slope, intercept, r_squared, std_error = linear_regression(x, y)
        
        assert abs(slope - (-2.0)) < 0.001
        assert abs(intercept - 12.0) < 0.001
        assert abs(r_squared - 1.0) < 0.001
    
    def test_no_correlation(self):
        """No correlation - flat line."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [5.0, 5.0, 5.0, 5.0, 5.0]  # constant
        
        slope, intercept, r_squared, std_error = linear_regression(x, y)
        
        assert abs(slope) < 0.001
        assert abs(intercept - 5.0) < 0.001
    
    def test_noisy_positive_trend(self):
        """Noisy data with positive trend."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        y = [10.2, 10.5, 11.0, 10.8, 11.2, 11.5, 11.3, 11.8, 12.0, 12.2]
        
        slope, intercept, r_squared, std_error = linear_regression(x, y)
        
        assert slope > 0  # Positive trend
        assert 0 < r_squared < 1  # Imperfect correlation
        assert std_error > 0  # Some error
    
    def test_minimum_data_points(self):
        """Regression requires at least 3 points."""
        x = [1.0, 2.0]
        y = [5.0, 6.0]
        
        with pytest.raises(ValueError):
            linear_regression(x, y)


class TestPValueCalculation:
    """Test p-value approximation."""
    
    def test_high_t_stat_low_p_value(self):
        """High t-statistic should give low p-value."""
        p = calculate_p_value_from_t(5.0, 30)
        assert p < 0.001
    
    def test_low_t_stat_high_p_value(self):
        """Low t-statistic should give high p-value."""
        p = calculate_p_value_from_t(0.5, 30)
        assert p > 0.5
    
    def test_zero_t_stat(self):
        """Zero t-statistic should give p-value near 1."""
        p = calculate_p_value_from_t(0.0, 30)
        assert p > 0.9
    
    def test_negative_t_stat(self):
        """Negative t-stat should give same p-value as positive."""
        p_pos = calculate_p_value_from_t(3.0, 30)
        p_neg = calculate_p_value_from_t(-3.0, 30)
        assert abs(p_pos - p_neg) < 0.01


class TestAnalyzeEfficiencyTrend:
    """Test main trend analysis function."""
    
    def test_insufficient_data(self):
        """Less than 5 data points returns insufficient."""
        time_series = [
            {"date": "2026-01-01T10:00:00", "efficiency_factor": 10.5},
            {"date": "2026-01-03T10:00:00", "efficiency_factor": 10.3},
            {"date": "2026-01-05T10:00:00", "efficiency_factor": 10.4},
        ]
        
        result = analyze_efficiency_trend(time_series)
        
        assert result.direction == TrendDirection.INSUFFICIENT
        assert result.confidence == TrendConfidence.INSUFFICIENT
        assert result.sample_size == 3
    
    def test_clear_improving_trend(self):
        """Clear improving trend (increasing EF) should be detected."""
        # Generate 20 data points with clear upward trend
        base_date = datetime(2026, 1, 1)
        time_series = []
        for i in range(20):
            date = base_date + timedelta(days=i * 3)
            # EF increasing from 10 to 12 (higher = better)
            ef = 10.0 + (i * 0.1)
            time_series.append({
                "date": date.isoformat(),
                "efficiency_factor": ef
            })
        
        result = analyze_efficiency_trend(time_series)
        
        assert result.direction == TrendDirection.IMPROVING
        assert result.confidence in [TrendConfidence.HIGH, TrendConfidence.MODERATE]
        assert result.slope_per_week > 0  # Positive = improving
        assert result.p_value < 0.05
        assert result.is_actionable
    
    def test_clear_declining_trend(self):
        """Clear declining trend (decreasing EF) should be detected."""
        base_date = datetime(2026, 1, 1)
        time_series = []
        for i in range(20):
            date = base_date + timedelta(days=i * 3)
            # EF decreasing from 12 to 10 (lower = worse)
            ef = 12.0 - (i * 0.1)
            time_series.append({
                "date": date.isoformat(),
                "efficiency_factor": ef
            })
        
        result = analyze_efficiency_trend(time_series)
        
        assert result.direction == TrendDirection.DECLINING
        assert result.slope_per_week < 0  # Negative = declining
        assert result.p_value < 0.05
    
    def test_stable_no_trend(self):
        """Flat data should show stable/no significant trend."""
        base_date = datetime(2026, 1, 1)
        time_series = []
        for i in range(15):
            date = base_date + timedelta(days=i * 3)
            # EF with small random-ish noise but no trend
            ef = 11.0 + (0.1 if i % 2 == 0 else -0.1)
            time_series.append({
                "date": date.isoformat(),
                "efficiency_factor": ef
            })
        
        result = analyze_efficiency_trend(time_series)
        
        # Should be stable (high p-value, near-zero slope)
        assert result.direction == TrendDirection.STABLE
        # slope_per_week may be None or near-zero for stable trends
        if result.slope_per_week is not None:
            assert abs(result.slope_per_week) < 0.5
    
    def test_noisy_improving_trend(self):
        """Noisy but overall improving trend."""
        import random
        random.seed(42)
        
        base_date = datetime(2026, 1, 1)
        time_series = []
        for i in range(30):
            date = base_date + timedelta(days=i * 2)
            # Clear upward trend with noise
            ef = 10.0 + (i * 0.05) + random.uniform(-0.3, 0.3)
            time_series.append({
                "date": date.isoformat(),
                "efficiency_factor": ef
            })
        
        result = analyze_efficiency_trend(time_series)
        
        assert result.direction == TrendDirection.IMPROVING
        assert result.slope_per_week > 0
        assert result.sample_size == 30
    
    def test_handles_missing_efficiency_factor(self):
        """Should skip entries with None efficiency_factor."""
        time_series = [
            {"date": "2026-01-01T10:00:00", "efficiency_factor": 10.5},
            {"date": "2026-01-02T10:00:00", "efficiency_factor": None},
            {"date": "2026-01-03T10:00:00", "efficiency_factor": 10.3},
            {"date": "2026-01-04T10:00:00", "efficiency_factor": 10.2},
            {"date": "2026-01-05T10:00:00", "efficiency_factor": None},
            {"date": "2026-01-06T10:00:00", "efficiency_factor": 10.1},
            {"date": "2026-01-07T10:00:00", "efficiency_factor": 10.0},
        ]
        
        result = analyze_efficiency_trend(time_series)
        
        assert result.sample_size == 5  # Only non-None values
    
    def test_change_percent_calculation(self):
        """Verify change percentage is calculated correctly."""
        base_date = datetime(2026, 1, 1)
        time_series = []
        for i in range(10):
            date = base_date + timedelta(days=i * 7)
            # EF from 10 to 12 = ~20% improvement
            ef = 10.0 + (i * 0.22)
            time_series.append({
                "date": date.isoformat(),
                "efficiency_factor": ef
            })
        
        result = analyze_efficiency_trend(time_series)
        
        assert result.change_percent is not None
        assert result.change_percent > 0  # Positive = improvement


class TestTrendConfidenceClassification:
    """Test confidence level classification."""
    
    def test_high_confidence_criteria(self):
        """High confidence requires p < 0.01, n >= 20, R² > 0.5."""
        # Create very clean data with 25 points - must have non-zero slope
        base_date = datetime(2026, 1, 1)
        time_series = []
        for i in range(25):
            date = base_date + timedelta(days=i * 2)
            ef = 12.0 - (i * 0.08)  # Very clean trend
            time_series.append({
                "date": date.isoformat(),
                "efficiency_factor": ef
            })
        
        result = analyze_efficiency_trend(time_series)
        
        # With clean trend data, should get high confidence
        assert result.confidence == TrendConfidence.HIGH
        assert result.p_value is not None and result.p_value < 0.01
        assert result.sample_size >= 20
        assert result.r_squared is not None and result.r_squared > 0.5
    
    def test_moderate_confidence_criteria(self):
        """Moderate confidence: p < 0.05, n >= 10."""
        import random
        random.seed(123)
        
        base_date = datetime(2026, 1, 1)
        time_series = []
        for i in range(12):
            date = base_date + timedelta(days=i * 5)
            # Trend with more noise
            ef = 11.5 - (i * 0.08) + random.uniform(-0.2, 0.2)
            time_series.append({
                "date": date.isoformat(),
                "efficiency_factor": ef
            })
        
        result = analyze_efficiency_trend(time_series)
        
        # Should be moderate or higher
        assert result.confidence in [TrendConfidence.MODERATE, TrendConfidence.HIGH]
        assert result.p_value < 0.05
        assert result.sample_size >= 10


class TestEfficiencyPercentile:
    """Test percentile calculation."""
    
    def test_best_efficiency(self):
        """Best efficiency should be high percentile."""
        current_ef = 13.0  # Higher is better
        historical = [10.0, 10.5, 11.0, 11.5, 12.0, 10.2, 10.8]
        
        percentile = calculate_efficiency_percentile(current_ef, historical)
        
        assert percentile == 100.0  # Better than all historical
    
    def test_worst_efficiency(self):
        """Worst efficiency should be low percentile."""
        current_ef = 9.0  # Lower is worse
        historical = [10.0, 10.5, 11.0, 11.5, 12.0]
        
        percentile = calculate_efficiency_percentile(current_ef, historical)
        
        assert percentile == 0.0  # Worse than all historical
    
    def test_median_efficiency(self):
        """Median efficiency should be around 50th percentile."""
        current_ef = 11.0
        historical = [10.0, 10.5, 11.0, 11.5, 12.0, 12.5, 13.0]
        
        percentile = calculate_efficiency_percentile(current_ef, historical)
        
        # 2 values are worse (lower), 4 are better (higher), 1 equal
        # percentile = 2/7 * 100 ≈ 28.6%
        assert 25 < percentile < 35
    
    def test_insufficient_history(self):
        """Should return None with less than 5 historical points."""
        current_ef = 11.0
        historical = [10.0, 10.5, 11.0]
        
        percentile = calculate_efficiency_percentile(current_ef, historical)
        
        assert percentile is None


class TestDaysToPREfficiency:
    """Test days-to-PR estimation."""
    
    def test_improving_trend(self):
        """Should estimate days when improving."""
        current_ef = 11.0
        pr_ef = 12.0
        slope_per_week = 0.2  # Improving 0.2 EF per week
        
        days = estimate_days_to_pr_efficiency(current_ef, pr_ef, slope_per_week)
        
        # Gap = 1.0, rate = 0.2/week → 5 weeks = 35 days
        assert days is not None
        assert 30 <= days <= 40
    
    def test_not_improving(self):
        """Should return None when not improving."""
        current_ef = 11.0
        pr_ef = 12.0
        slope_per_week = -0.1  # Declining
        
        days = estimate_days_to_pr_efficiency(current_ef, pr_ef, slope_per_week)
        
        assert days is None
    
    def test_already_at_pr(self):
        """Should return 0 when at or better than PR."""
        current_ef = 12.5
        pr_ef = 12.0
        slope_per_week = 0.1
        
        days = estimate_days_to_pr_efficiency(current_ef, pr_ef, slope_per_week)
        
        assert days == 0
    
    def test_too_far_out(self):
        """Should return None if > 365 days away."""
        current_ef = 10.0
        pr_ef = 15.0
        slope_per_week = 0.01  # Very slow improvement
        
        days = estimate_days_to_pr_efficiency(current_ef, pr_ef, slope_per_week)
        
        assert days is None


class TestToDict:
    """Test serialization to dictionary."""
    
    def test_to_dict_complete(self):
        """Should serialize all fields."""
        base_date = datetime(2026, 1, 1)
        time_series = []
        for i in range(15):
            date = base_date + timedelta(days=i * 3)
            ef = 10.0 + (i * 0.1)
            time_series.append({
                "date": date.isoformat(),
                "efficiency_factor": ef
            })
        
        result = analyze_efficiency_trend(time_series)
        result_dict = to_dict(result)
        
        assert "direction" in result_dict
        assert "confidence" in result_dict
        assert "slope_per_week" in result_dict
        assert "p_value" in result_dict
        assert "r_squared" in result_dict
        assert "sample_size" in result_dict
        assert "period_days" in result_dict
        assert "change_percent" in result_dict
        assert "insight_text" in result_dict
        assert "is_actionable" in result_dict
        
        # Enums should be converted to strings
        assert isinstance(result_dict["direction"], str)
        assert isinstance(result_dict["confidence"], str)


class TestInsightGeneration:
    """Test insight text generation."""
    
    def test_improving_high_confidence_insight(self):
        """High confidence improving should have specific insight."""
        base_date = datetime(2026, 1, 1)
        time_series = []
        for i in range(25):
            date = base_date + timedelta(days=i * 3)
            ef = 10.0 + (i * 0.1)
            time_series.append({
                "date": date.isoformat(),
                "efficiency_factor": ef
            })
        
        result = analyze_efficiency_trend(time_series)
        
        assert "improving" in result.insight_text.lower() or "better" in result.insight_text.lower()
        assert "fitness" in result.insight_text.lower() or "aerobic" in result.insight_text.lower()
    
    def test_declining_insight(self):
        """Declining trend should warn about recovery."""
        base_date = datetime(2026, 1, 1)
        time_series = []
        for i in range(20):
            date = base_date + timedelta(days=i * 3)
            ef = 12.0 - (i * 0.12)
            time_series.append({
                "date": date.isoformat(),
                "efficiency_factor": ef
            })
        
        result = analyze_efficiency_trend(time_series)
        
        if result.direction == TrendDirection.DECLINING:
            assert "declining" in result.insight_text.lower() or "worse" in result.insight_text.lower()


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_time_series(self):
        """Empty time series should return insufficient."""
        result = analyze_efficiency_trend([])
        
        assert result.direction == TrendDirection.INSUFFICIENT
        assert result.sample_size == 0
    
    def test_all_none_efficiency_factors(self):
        """All None EF values should return insufficient."""
        time_series = [
            {"date": "2026-01-01T10:00:00", "efficiency_factor": None},
            {"date": "2026-01-02T10:00:00", "efficiency_factor": None},
        ]
        
        result = analyze_efficiency_trend(time_series)
        
        assert result.direction == TrendDirection.INSUFFICIENT
        assert result.sample_size == 0
    
    def test_single_day_data(self):
        """All data on same day should handle gracefully."""
        time_series = [
            {"date": "2026-01-01T10:00:00", "efficiency_factor": 10.5},
            {"date": "2026-01-01T11:00:00", "efficiency_factor": 10.3},
            {"date": "2026-01-01T12:00:00", "efficiency_factor": 10.4},
            {"date": "2026-01-01T13:00:00", "efficiency_factor": 10.2},
            {"date": "2026-01-01T14:00:00", "efficiency_factor": 10.1},
        ]
        
        result = analyze_efficiency_trend(time_series)
        
        # Should handle without error
        assert result.sample_size == 5
        assert result.period_days == 0
    
    def test_iso_format_with_z_suffix(self):
        """Should handle ISO format with Z suffix."""
        time_series = [
            {"date": "2026-01-01T10:00:00Z", "efficiency_factor": 10.5},
            {"date": "2026-01-02T10:00:00Z", "efficiency_factor": 10.4},
            {"date": "2026-01-03T10:00:00Z", "efficiency_factor": 10.3},
            {"date": "2026-01-04T10:00:00Z", "efficiency_factor": 10.2},
            {"date": "2026-01-05T10:00:00Z", "efficiency_factor": 10.1},
        ]
        
        result = analyze_efficiency_trend(time_series)
        
        assert result.sample_size == 5
