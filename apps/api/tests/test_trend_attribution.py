"""
Unit tests for Trend Attribution Service

Tests attribution calculation, ranking, and insight generation.

ADR-014: Why This Trend? Attribution Integration
"""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch
from services.trend_attribution import (
    TrendMetric,
    AttributionConfidence,
    TrendSummary,
    Attribution,
    MethodContribution,
    TrendAttributionResult,
    pearson_correlation,
    classify_confidence,
    generate_attribution_insight,
    get_trend_attribution,
    attribution_result_to_dict,
    FACTOR_CONFIGS,
    HIGH_CONFIDENCE_R,
    MODERATE_CONFIDENCE_R,
    LOW_CONFIDENCE_R,
)


class TestTrendMetric:
    """Test TrendMetric enum."""
    
    def test_metric_values(self):
        """All metric types exist."""
        assert TrendMetric.EFFICIENCY.value == "efficiency"
        assert TrendMetric.LOAD.value == "load"
        assert TrendMetric.SPEED.value == "speed"
        assert TrendMetric.PACING.value == "pacing"


class TestAttributionConfidence:
    """Test AttributionConfidence enum."""
    
    def test_confidence_values(self):
        """All confidence levels exist."""
        assert AttributionConfidence.HIGH.value == "high"
        assert AttributionConfidence.MODERATE.value == "moderate"
        assert AttributionConfidence.LOW.value == "low"
        assert AttributionConfidence.INSUFFICIENT.value == "insufficient"


class TestPearsonCorrelation:
    """Test Pearson correlation calculation."""
    
    def test_perfect_positive_correlation(self):
        """r=1 for perfect positive correlation."""
        x = [1, 2, 3, 4, 5]
        y = [1, 2, 3, 4, 5]
        r, p = pearson_correlation(x, y)
        assert r > 0.99
        assert p < 0.01
    
    def test_perfect_negative_correlation(self):
        """r=-1 for perfect negative correlation."""
        x = [1, 2, 3, 4, 5]
        y = [5, 4, 3, 2, 1]
        r, p = pearson_correlation(x, y)
        assert r < -0.99
        assert p < 0.01
    
    def test_no_correlation(self):
        """r~0 for uncorrelated data."""
        x = [1, 2, 3, 4, 5]
        y = [3, 1, 4, 2, 5]
        r, p = pearson_correlation(x, y)
        assert abs(r) <= 0.5  # Weak correlation at most
    
    def test_insufficient_data(self):
        """Returns (0, 1) for insufficient data."""
        x = [1, 2]
        y = [1, 2]
        r, p = pearson_correlation(x, y)
        assert r == 0.0
        assert p == 1.0
    
    def test_mismatched_lengths(self):
        """Returns (0, 1) for mismatched lengths."""
        x = [1, 2, 3]
        y = [1, 2]
        r, p = pearson_correlation(x, y)
        assert r == 0.0
        assert p == 1.0
    
    def test_zero_variance(self):
        """Handles zero variance gracefully."""
        x = [5, 5, 5, 5, 5]
        y = [1, 2, 3, 4, 5]
        r, p = pearson_correlation(x, y)
        assert r == 0.0


class TestClassifyConfidence:
    """Test confidence classification."""
    
    def test_high_confidence(self):
        """High confidence for strong correlation + large sample."""
        conf = classify_confidence(r=0.8, sample_size=25, p_value=0.01)
        assert conf == AttributionConfidence.HIGH
    
    def test_moderate_confidence(self):
        """Moderate confidence for moderate correlation."""
        conf = classify_confidence(r=0.5, sample_size=15, p_value=0.05)
        assert conf == AttributionConfidence.MODERATE
    
    def test_low_confidence(self):
        """Low confidence for weak correlation."""
        conf = classify_confidence(r=0.3, sample_size=8, p_value=0.15)
        assert conf == AttributionConfidence.LOW
    
    def test_insufficient_confidence(self):
        """Insufficient for very weak correlation."""
        conf = classify_confidence(r=0.1, sample_size=3, p_value=0.5)
        assert conf == AttributionConfidence.INSUFFICIENT
    
    def test_negative_correlation(self):
        """Works with negative correlations."""
        conf = classify_confidence(r=-0.75, sample_size=25, p_value=0.01)
        assert conf == AttributionConfidence.HIGH


class TestGenerateAttributionInsight:
    """Test insight generation."""
    
    def test_sleep_insight_positive(self):
        """Sleep insight with positive correlation."""
        insight = generate_attribution_insight(
            "sleep_quality", "Sleep Quality", 0.7, "improving", 1
        )
        assert "sleep" in insight.lower()
        assert "better" in insight.lower()
    
    def test_hrv_insight_inverted(self):
        """HRV insight with inverted pattern."""
        insight = generate_attribution_insight(
            "hrv", "HRV", -0.6, "improving", 0
        )
        assert "hrv" in insight.lower()
        assert "inverted" in insight.lower() or "lower" in insight.lower()
    
    def test_consistency_insight(self):
        """Consistency insight."""
        insight = generate_attribution_insight(
            "consistency", "Training Consistency", 0.5, "improving", 7
        )
        assert "consistency" in insight.lower()
    
    def test_lag_in_insight(self):
        """Time lag appears in insight."""
        insight = generate_attribution_insight(
            "sleep_quality", "Sleep Quality", 0.7, "improving", 2
        )
        assert "2-day lag" in insight or "lag" in insight.lower()
    
    def test_tsb_insight(self):
        """TSB insight."""
        insight = generate_attribution_insight(
            "tsb", "Training Stress Balance", 0.6, "improving", 0
        )
        assert "stress balance" in insight.lower() or "tsb" in insight.lower()


class TestTrendSummary:
    """Test TrendSummary dataclass."""
    
    def test_create_summary(self):
        """Can create TrendSummary."""
        summary = TrendSummary(
            metric="efficiency",
            direction="improving",
            change_percent=4.2,
            p_value=0.02,
            confidence="high",
            period_days=28
        )
        
        assert summary.metric == "efficiency"
        assert summary.direction == "improving"
        assert summary.change_percent == 4.2


class TestAttribution:
    """Test Attribution dataclass."""
    
    def test_create_attribution(self):
        """Can create Attribution."""
        attr = Attribution(
            factor="sleep_quality",
            label="Sleep Quality (1-day lag)",
            contribution_pct=35.0,
            correlation=0.72,
            confidence="moderate",
            insight="Higher sleep scores precede better days.",
            sample_size=24,
            time_lag_days=1
        )
        
        assert attr.factor == "sleep_quality"
        assert attr.contribution_pct == 35.0
        assert attr.time_lag_days == 1


class TestMethodContribution:
    """Test MethodContribution dataclass."""
    
    def test_default_values(self):
        """Default values are False."""
        mc = MethodContribution()
        assert mc.efficiency_trending is False
        assert mc.tsb_analysis is False
        # critical_speed removed - archived
        assert mc.fingerprinting is False
        assert mc.pace_decay is False
    
    def test_set_values(self):
        """Can set values."""
        mc = MethodContribution(
            efficiency_trending=True,
            tsb_analysis=True
        )
        assert mc.efficiency_trending is True
        assert mc.tsb_analysis is True


class TestTrendAttributionResult:
    """Test TrendAttributionResult dataclass."""
    
    def test_create_result(self):
        """Can create TrendAttributionResult."""
        summary = TrendSummary(
            metric="efficiency",
            direction="improving",
            change_percent=4.2,
            p_value=0.02,
            confidence="high",
            period_days=28
        )
        
        attributions = [
            Attribution(
                factor="sleep_quality",
                label="Sleep Quality",
                contribution_pct=35.0,
                correlation=0.72,
                confidence="moderate",
                insight="Test insight",
                sample_size=24
            )
        ]
        
        mc = MethodContribution(efficiency_trending=True)
        
        result = TrendAttributionResult(
            trend_summary=summary,
            attributions=attributions,
            method_contributions=mc,
            generated_at=datetime(2026, 1, 14, 10, 30)
        )
        
        assert result.trend_summary.metric == "efficiency"
        assert len(result.attributions) == 1


class TestAttributionResultToDict:
    """Test serialization to dictionary."""
    
    def test_serialization(self):
        """Serializes correctly."""
        summary = TrendSummary(
            metric="efficiency",
            direction="improving",
            change_percent=4.2,
            p_value=0.02,
            confidence="high",
            period_days=28
        )
        
        attributions = [
            Attribution(
                factor="sleep_quality",
                label="Sleep Quality (1-day lag)",
                contribution_pct=35.0,
                correlation=0.72,
                confidence="moderate",
                insight="Higher sleep scores precede better days.",
                sample_size=24,
                time_lag_days=1
            )
        ]
        
        mc = MethodContribution(efficiency_trending=True, tsb_analysis=True)
        
        result = TrendAttributionResult(
            trend_summary=summary,
            attributions=attributions,
            method_contributions=mc,
            generated_at=datetime(2026, 1, 14, 10, 30)
        )
        
        d = attribution_result_to_dict(result)
        
        assert "trend_summary" in d
        assert "attributions" in d
        assert "method_contributions" in d
        assert "generated_at" in d
        
        assert d["trend_summary"]["metric"] == "efficiency"
        assert d["trend_summary"]["direction"] == "improving"
        
        assert len(d["attributions"]) == 1
        assert d["attributions"][0]["factor"] == "sleep_quality"
        assert d["attributions"][0]["contribution_pct"] == 35.0
        
        assert d["method_contributions"]["efficiency_trending"] is True
        assert d["method_contributions"]["tsb_analysis"] is True


class TestFactorConfigs:
    """Test factor configuration."""
    
    def test_all_factors_have_labels(self):
        """All factors have labels."""
        for factor, config in FACTOR_CONFIGS.items():
            assert "label" in config
            assert len(config["label"]) > 0
    
    def test_all_factors_have_lag_days(self):
        """All factors have lag_days."""
        for factor, config in FACTOR_CONFIGS.items():
            assert "lag_days" in config
            assert isinstance(config["lag_days"], list)
    
    def test_all_factors_have_categories(self):
        """All factors have categories."""
        for factor, config in FACTOR_CONFIGS.items():
            assert "category" in config
            assert config["category"] in ["recovery", "wellness", "nutrition", "body", "training", "load"]


class TestConfidenceThresholds:
    """Test confidence threshold constants."""
    
    def test_thresholds_in_order(self):
        """Thresholds are in descending order."""
        assert HIGH_CONFIDENCE_R > MODERATE_CONFIDENCE_R
        assert MODERATE_CONFIDENCE_R > LOW_CONFIDENCE_R
    
    def test_thresholds_reasonable(self):
        """Thresholds are reasonable values."""
        assert 0.5 <= HIGH_CONFIDENCE_R <= 0.9
        assert 0.3 <= MODERATE_CONFIDENCE_R <= 0.6
        assert 0.1 <= LOW_CONFIDENCE_R <= 0.4


class TestGetTrendAttribution:
    """Test main attribution function."""
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()
    
    def test_returns_result(self, mock_db):
        """Returns TrendAttributionResult or dict."""
        with patch('services.trend_attribution.get_trend_summary') as mock_summary, \
             patch('services.trend_attribution.calculate_factor_attributions') as mock_attrs, \
             patch('services.trend_attribution.get_method_contributions') as mock_methods:
            
            mock_summary.return_value = TrendSummary(
                metric="efficiency",
                direction="improving",
                change_percent=4.2,
                p_value=0.02,
                confidence="high",
                period_days=28
            )
            mock_attrs.return_value = []
            mock_methods.return_value = MethodContribution()
            
            result = get_trend_attribution("test-athlete", "efficiency", 28, mock_db)
            
            assert result is not None
            assert isinstance(result, TrendAttributionResult)
    
    def test_handles_invalid_metric(self, mock_db):
        """Handles invalid metric gracefully."""
        with patch('services.trend_attribution.get_trend_summary') as mock_summary, \
             patch('services.trend_attribution.calculate_factor_attributions') as mock_attrs, \
             patch('services.trend_attribution.get_method_contributions') as mock_methods:
            
            mock_summary.return_value = None
            mock_attrs.return_value = []
            mock_methods.return_value = MethodContribution()
            
            result = get_trend_attribution("test-athlete", "invalid_metric", 28, mock_db)
            
            # Should default to efficiency and return result
            assert result is not None


class TestEdgeCases:
    """Test edge cases."""
    
    def test_empty_correlation_data(self):
        """Handles empty data."""
        r, p = pearson_correlation([], [])
        assert r == 0.0
        assert p == 1.0
    
    def test_single_point(self):
        """Handles single data point."""
        r, p = pearson_correlation([1], [1])
        assert r == 0.0
        assert p == 1.0
    
    def test_insight_with_no_lag(self):
        """Insight generation with zero lag."""
        insight = generate_attribution_insight(
            "tsb", "Training Stress Balance", 0.6, "improving", 0
        )
        assert "0-day lag" not in insight  # No lag text for 0 days


class TestCorrelationMath:
    """Test correlation math accuracy."""
    
    def test_known_correlation_value(self):
        """Test against known correlation value."""
        # Simple case: y = 2x + noise
        x = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        y = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20]
        r, p = pearson_correlation(x, y)
        assert abs(r - 1.0) < 0.001  # Should be nearly perfect
    
    def test_moderate_correlation(self):
        """Test moderate correlation."""
        x = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        y = [2, 5, 4, 7, 8, 7, 10, 9, 12, 11]  # Noisy positive trend
        r, p = pearson_correlation(x, y)
        assert 0.8 < r < 1.0  # Strong positive correlation
