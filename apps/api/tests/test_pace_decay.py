"""
Unit tests for Pace Decay Analysis Service

Tests decay calculation, pattern classification, outlier detection,
and historical comparison.

ADR-012: Pace Decay Analysis
"""

import pytest
from datetime import date
from services.pace_decay import (
    calculate_pace_from_split,
    detect_outliers,
    calculate_segment_average_pace,
    classify_split_pattern,
    calculate_decay_metrics,
    compare_to_history,
    generate_insights,
    format_pace,
    get_distance_category,
    to_dict,
    profile_to_dict,
    SplitData,
    DecayMetrics,
    DecayAnalysis,
    DecayProfile,
    HistoricalComparison,
    SplitPattern,
    ConfidenceLevel,
    MIN_SPLITS_FOR_ANALYSIS,
    DISTANCE_CATEGORIES
)


class TestPaceCalculation:
    """Test pace calculation from splits."""
    
    def test_calculate_pace_standard(self):
        """Standard 1km split calculation."""
        # 1000m in 300 seconds = 5:00/km
        pace_km, pace_mile = calculate_pace_from_split(1000, 300)
        
        assert abs(pace_km - 300) < 0.1
        assert abs(pace_mile - 483) < 1  # ~8:03/mile
    
    def test_calculate_pace_mile_split(self):
        """1 mile split calculation."""
        # 1609.34m in 420 seconds = 7:00/mile
        pace_km, pace_mile = calculate_pace_from_split(1609.34, 420)
        
        assert abs(pace_mile - 420) < 0.1
        assert abs(pace_km - 261) < 1  # ~4:21/km
    
    def test_calculate_pace_zero_distance(self):
        """Zero distance returns zero paces."""
        pace_km, pace_mile = calculate_pace_from_split(0, 300)
        
        assert pace_km == 0.0
        assert pace_mile == 0.0
    
    def test_calculate_pace_zero_time(self):
        """Zero time returns zero paces."""
        pace_km, pace_mile = calculate_pace_from_split(1000, 0)
        
        assert pace_km == 0.0
        assert pace_mile == 0.0


class TestOutlierDetection:
    """Test outlier detection in splits."""
    
    def test_no_outliers(self):
        """Consistent paces should have no outliers."""
        splits = [
            SplitData(1, 1000, 300, 300, 483, None),
            SplitData(2, 1000, 305, 305, 491, None),
            SplitData(3, 1000, 298, 298, 480, None),
            SplitData(4, 1000, 302, 302, 486, None),
        ]
        
        result = detect_outliers(splits)
        
        outliers = [s for s in result if s.is_outlier]
        assert len(outliers) == 0
    
    def test_detect_slow_outlier(self):
        """Very slow split should be flagged."""
        splits = [
            SplitData(1, 1000, 300, 300, 483, None),
            SplitData(2, 1000, 305, 305, 491, None),
            SplitData(3, 1000, 500, 500, 805, None),  # Way slower (bathroom break?)
            SplitData(4, 1000, 302, 302, 486, None),
        ]
        
        result = detect_outliers(splits)
        
        outliers = [s for s in result if s.is_outlier]
        assert len(outliers) == 1
        assert outliers[0].split_number == 3
    
    def test_detect_fast_outlier(self):
        """Very fast split should be flagged (GPS error?)."""
        splits = [
            SplitData(1, 1000, 300, 300, 483, None),
            SplitData(2, 1000, 305, 305, 491, None),
            SplitData(3, 1000, 150, 150, 241, None),  # Impossibly fast
            SplitData(4, 1000, 302, 302, 486, None),
        ]
        
        result = detect_outliers(splits)
        
        outliers = [s for s in result if s.is_outlier]
        assert len(outliers) == 1
        assert outliers[0].split_number == 3
    
    def test_few_splits_no_detection(self):
        """With <3 splits, cannot detect outliers."""
        splits = [
            SplitData(1, 1000, 300, 300, 483, None),
            SplitData(2, 1000, 500, 500, 805, None),  # Would be outlier
        ]
        
        result = detect_outliers(splits)
        
        outliers = [s for s in result if s.is_outlier]
        assert len(outliers) == 0


class TestSplitPatternClassification:
    """Test split pattern classification."""
    
    def test_negative_split(self):
        """Negative split (finished faster)."""
        assert classify_split_pattern(-5) == SplitPattern.NEGATIVE
        assert classify_split_pattern(-2.5) == SplitPattern.NEGATIVE
    
    def test_even_split(self):
        """Even split (within ±2%)."""
        assert classify_split_pattern(0) == SplitPattern.EVEN
        assert classify_split_pattern(1.5) == SplitPattern.EVEN
        assert classify_split_pattern(-1.5) == SplitPattern.EVEN
        assert classify_split_pattern(2) == SplitPattern.EVEN
        assert classify_split_pattern(-2) == SplitPattern.EVEN
    
    def test_mild_positive_split(self):
        """Mild positive split (2-5% slower)."""
        assert classify_split_pattern(3) == SplitPattern.MILD_POSITIVE
        assert classify_split_pattern(4.5) == SplitPattern.MILD_POSITIVE
        assert classify_split_pattern(5) == SplitPattern.MILD_POSITIVE
    
    def test_moderate_positive_split(self):
        """Moderate positive split (5-10% slower)."""
        assert classify_split_pattern(6) == SplitPattern.MODERATE_POSITIVE
        assert classify_split_pattern(8) == SplitPattern.MODERATE_POSITIVE
        assert classify_split_pattern(10) == SplitPattern.MODERATE_POSITIVE
    
    def test_severe_positive_split(self):
        """Severe positive split (>10% slower)."""
        assert classify_split_pattern(11) == SplitPattern.SEVERE_POSITIVE
        assert classify_split_pattern(15) == SplitPattern.SEVERE_POSITIVE
        assert classify_split_pattern(25) == SplitPattern.SEVERE_POSITIVE


class TestDecayMetricsCalculation:
    """Test decay metrics calculation."""
    
    def test_even_paced_race(self):
        """Evenly paced race should have low decay."""
        splits = [
            SplitData(1, 1000, 300, 300, 483, None),
            SplitData(2, 1000, 300, 300, 483, None),
            SplitData(3, 1000, 300, 300, 483, None),
            SplitData(4, 1000, 300, 300, 483, None),
        ]
        
        metrics = calculate_decay_metrics(splits)
        
        assert metrics is not None
        assert abs(metrics.half_split_decay_pct) < 1
        assert metrics.overall_pattern == SplitPattern.EVEN
    
    def test_positive_split_race(self):
        """Slowing race should have positive decay."""
        splits = [
            SplitData(1, 1000, 280, 280, 451, None),  # Fast start
            SplitData(2, 1000, 290, 290, 467, None),
            SplitData(3, 1000, 310, 310, 499, None),  # Slowing
            SplitData(4, 1000, 330, 330, 531, None),  # Slow finish
        ]
        
        metrics = calculate_decay_metrics(splits)
        
        assert metrics is not None
        assert metrics.half_split_decay_pct > 5
        assert metrics.overall_pattern in [SplitPattern.MODERATE_POSITIVE, SplitPattern.SEVERE_POSITIVE]
    
    def test_negative_split_race(self):
        """Speeding up should have negative decay."""
        splits = [
            SplitData(1, 1000, 320, 320, 515, None),  # Slow start
            SplitData(2, 1000, 310, 310, 499, None),
            SplitData(3, 1000, 295, 295, 475, None),  # Speeding up
            SplitData(4, 1000, 280, 280, 451, None),  # Fast finish
        ]
        
        metrics = calculate_decay_metrics(splits)
        
        assert metrics is not None
        assert metrics.half_split_decay_pct < -2
        assert metrics.overall_pattern == SplitPattern.NEGATIVE
    
    def test_insufficient_splits(self):
        """Should return None with <3 splits."""
        splits = [
            SplitData(1, 1000, 300, 300, 483, None),
            SplitData(2, 1000, 305, 305, 491, None),
        ]
        
        metrics = calculate_decay_metrics(splits)
        
        assert metrics is None
    
    def test_outliers_excluded(self):
        """Outliers should be excluded from calculation."""
        splits = [
            SplitData(1, 1000, 300, 300, 483, None, is_outlier=False),
            SplitData(2, 1000, 300, 300, 483, None, is_outlier=False),
            SplitData(3, 1000, 600, 600, 966, None, is_outlier=True),  # Outlier
            SplitData(4, 1000, 300, 300, 483, None, is_outlier=False),
            SplitData(5, 1000, 300, 300, 483, None, is_outlier=False),
        ]
        
        metrics = calculate_decay_metrics(splits)
        
        assert metrics is not None
        assert metrics.outliers_excluded == 1
        assert metrics.splits_used == 4


class TestHistoricalComparison:
    """Test historical comparison."""
    
    def test_typical_decay(self):
        """Decay within 1.5% of average is typical."""
        comparison = compare_to_history(5.0, [4.5, 5.2, 4.8, 5.5])
        
        assert comparison is not None
        assert comparison.deviation_direction == "typical"
        assert "matches" in comparison.insight.lower() or "typical" in comparison.insight.lower()
    
    def test_better_than_typical(self):
        """Lower decay than average is better."""
        comparison = compare_to_history(2.0, [5.0, 6.0, 5.5, 4.5])  # Avg ~5.25%
        
        assert comparison is not None
        assert comparison.deviation_direction == "better"
        assert "less" in comparison.insight.lower() or "better" in comparison.insight.lower()
    
    def test_worse_than_typical(self):
        """Higher decay than average is worse."""
        comparison = compare_to_history(10.0, [5.0, 5.5, 4.5, 5.0])  # Avg 5%
        
        assert comparison is not None
        assert comparison.deviation_direction == "worse"
        assert "more" in comparison.insight.lower() or "worse" in comparison.insight.lower()
    
    def test_insufficient_history(self):
        """Should return None with <2 historical points."""
        comparison = compare_to_history(5.0, [4.0])
        
        assert comparison is None
    
    def test_distance_category_in_insight(self):
        """Distance category should be included in insight."""
        comparison = compare_to_history(5.0, [5.0, 5.2, 4.8], "10K")
        
        assert comparison is not None
        assert "10K" in comparison.insight


class TestInsightGeneration:
    """Test insight generation."""
    
    def test_negative_split_insight(self):
        """Negative split should praise execution."""
        metrics = DecayMetrics(
            first_half_pace_s_per_km=310,
            second_half_pace_s_per_km=295,
            half_split_decay_pct=-4.8,
            first_third_pace_s_per_km=315,
            last_third_pace_s_per_km=290,
            third_split_decay_pct=-7.9,
            peak_pace_s_per_km=280,
            final_segment_pace_s_per_km=290,
            peak_to_final_decay_pct=3.6,
            overall_pattern=SplitPattern.NEGATIVE,
            total_distance_m=10000,
            total_time_s=3020,
            splits_used=10,
            outliers_excluded=0
        )
        
        insights = generate_insights(metrics, True, None)
        
        assert len(insights) >= 1
        assert any("negative" in i.lower() for i in insights)
        assert any("excellent" in i.lower() or "strong" in i.lower() for i in insights)
    
    def test_severe_decay_insight(self):
        """Severe decay should suggest adjustments."""
        metrics = DecayMetrics(
            first_half_pace_s_per_km=280,
            second_half_pace_s_per_km=330,
            half_split_decay_pct=17.9,
            first_third_pace_s_per_km=275,
            last_third_pace_s_per_km=345,
            third_split_decay_pct=25.5,
            peak_pace_s_per_km=270,
            final_segment_pace_s_per_km=360,
            peak_to_final_decay_pct=33.3,
            overall_pattern=SplitPattern.SEVERE_POSITIVE,
            total_distance_m=10000,
            total_time_s=3050,
            splits_used=10,
            outliers_excluded=0
        )
        
        insights = generate_insights(metrics, True, None)
        
        assert len(insights) >= 1
        assert any("fade" in i.lower() or "significant" in i.lower() for i in insights)
    
    def test_outlier_note_in_insights(self):
        """Should note excluded outliers."""
        metrics = DecayMetrics(
            first_half_pace_s_per_km=300,
            second_half_pace_s_per_km=305,
            half_split_decay_pct=1.7,
            first_third_pace_s_per_km=298,
            last_third_pace_s_per_km=307,
            third_split_decay_pct=3.0,
            peak_pace_s_per_km=290,
            final_segment_pace_s_per_km=310,
            peak_to_final_decay_pct=6.9,
            overall_pattern=SplitPattern.EVEN,
            total_distance_m=10000,
            total_time_s=3025,
            splits_used=9,
            outliers_excluded=2
        )
        
        insights = generate_insights(metrics, True, None)
        
        assert any("outlier" in i.lower() for i in insights)


class TestFormatting:
    """Test pace formatting."""
    
    def test_format_pace_standard(self):
        """Format standard paces."""
        assert format_pace(300) == "5:00/km"
        assert format_pace(270) == "4:30/km"
        assert format_pace(330) == "5:30/km"
    
    def test_format_pace_with_seconds(self):
        """Format paces with odd seconds."""
        assert format_pace(275) == "4:35/km"
        assert format_pace(327) == "5:27/km"
    
    def test_format_pace_invalid(self):
        """Invalid pace returns N/A."""
        assert format_pace(0) == "N/A"
        assert format_pace(-60) == "N/A"


class TestDistanceCategory:
    """Test distance category detection."""
    
    def test_standard_distances(self):
        """Standard distances should be categorized."""
        assert get_distance_category(5000) == "5K"
        assert get_distance_category(10000) == "10K"
        assert get_distance_category(21097) == "Half Marathon"
        assert get_distance_category(42195) == "Marathon"
    
    def test_with_tolerance(self):
        """Distances within tolerance should match."""
        assert get_distance_category(4900) == "5K"
        assert get_distance_category(5100) == "5K"
        assert get_distance_category(10200) == "10K"
    
    def test_short_distance(self):
        """Short races should be categorized."""
        assert get_distance_category(3000) == "Short"
        assert get_distance_category(1600) == "Short"
    
    def test_ultra_distance(self):
        """Ultra distances should be categorized."""
        assert get_distance_category(50000) == "Ultra"
        assert get_distance_category(100000) == "Ultra"


class TestDecayAnalysisDataclass:
    """Test DecayAnalysis creation and serialization."""
    
    def test_create_analysis(self):
        """Can create DecayAnalysis."""
        metrics = DecayMetrics(
            first_half_pace_s_per_km=300,
            second_half_pace_s_per_km=310,
            half_split_decay_pct=3.3,
            first_third_pace_s_per_km=295,
            last_third_pace_s_per_km=315,
            third_split_decay_pct=6.8,
            peak_pace_s_per_km=290,
            final_segment_pace_s_per_km=320,
            peak_to_final_decay_pct=10.3,
            overall_pattern=SplitPattern.MILD_POSITIVE,
            total_distance_m=10000,
            total_time_s=3050,
            splits_used=10,
            outliers_excluded=0
        )
        
        analysis = DecayAnalysis(
            activity_id="test-123",
            activity_name="Test 10K",
            activity_date=date(2026, 1, 14),
            is_race=True,
            metrics=metrics,
            splits=[],
            comparison=None,
            insights=["Test insight"],
            warnings=[],
            confidence=ConfidenceLevel.HIGH
        )
        
        assert analysis.activity_id == "test-123"
        assert analysis.metrics.overall_pattern == SplitPattern.MILD_POSITIVE
    
    def test_to_dict(self):
        """Analysis should serialize correctly."""
        metrics = DecayMetrics(
            first_half_pace_s_per_km=300,
            second_half_pace_s_per_km=315,
            half_split_decay_pct=5.0,
            first_third_pace_s_per_km=295,
            last_third_pace_s_per_km=320,
            third_split_decay_pct=8.5,
            peak_pace_s_per_km=285,
            final_segment_pace_s_per_km=330,
            peak_to_final_decay_pct=15.8,
            overall_pattern=SplitPattern.MODERATE_POSITIVE,
            total_distance_m=10000,
            total_time_s=3075,
            splits_used=10,
            outliers_excluded=1
        )
        
        split = SplitData(
            split_number=1,
            distance_m=1000,
            elapsed_time_s=300,
            pace_s_per_km=300,
            pace_s_per_mile=483,
            average_hr=150,
            is_outlier=False
        )
        
        comparison = HistoricalComparison(
            typical_decay_pct=4.0,
            current_decay_pct=5.0,
            deviation_pct=1.0,
            deviation_direction="typical",
            sample_size=5,
            insight="Decay matches typical."
        )
        
        analysis = DecayAnalysis(
            activity_id="test-456",
            activity_name="Race 10K",
            activity_date=date(2026, 1, 14),
            is_race=True,
            metrics=metrics,
            splits=[split],
            comparison=comparison,
            insights=["Insight 1"],
            warnings=["Warning 1"],
            confidence=ConfidenceLevel.MODERATE
        )
        
        result = to_dict(analysis)
        
        assert result["activity_id"] == "test-456"
        assert result["metrics"]["half_split_decay_pct"] == 5.0
        assert result["metrics"]["overall_pattern"] == "moderate_positive"
        assert len(result["splits"]) == 1
        assert result["splits"][0]["pace_per_km"] == "5:00/km"
        assert result["comparison"]["sample_size"] == 5
        assert result["confidence"] == "moderate"


class TestDecayProfile:
    """Test DecayProfile creation and serialization."""
    
    def test_create_profile(self):
        """Can create DecayProfile."""
        profile = DecayProfile(
            athlete_id="athlete-123",
            by_distance={
                "5K": {"avg_decay": 3.5, "best_decay": 1.2, "worst_decay": 6.8, "races": 5},
                "10K": {"avg_decay": 5.2, "best_decay": 2.5, "worst_decay": 9.0, "races": 3}
            },
            overall_avg_decay=4.1,
            total_races_analyzed=8,
            trend="improving",
            insights=["Solid pacing."]
        )
        
        assert profile.athlete_id == "athlete-123"
        assert profile.total_races_analyzed == 8
        assert profile.trend == "improving"
    
    def test_profile_to_dict(self):
        """Profile should serialize correctly."""
        profile = DecayProfile(
            athlete_id="athlete-789",
            by_distance={"5K": {"avg_decay": 4.0, "races": 3}},
            overall_avg_decay=4.0,
            total_races_analyzed=3,
            trend="stable",
            insights=["Test insight"]
        )
        
        result = profile_to_dict(profile)
        
        assert result["athlete_id"] == "athlete-789"
        assert result["overall_avg_decay"] == 4.0
        assert result["trend"] == "stable"


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_all_zero_paces(self):
        """Should handle all zero paces gracefully."""
        splits = [
            SplitData(1, 0, 0, 0, 0, None),
            SplitData(2, 0, 0, 0, 0, None),
            SplitData(3, 0, 0, 0, 0, None),
        ]
        
        metrics = calculate_decay_metrics(splits)
        
        # Should return None or handle gracefully
        assert metrics is None
    
    def test_single_split(self):
        """Single split cannot calculate decay."""
        splits = [
            SplitData(1, 1000, 300, 300, 483, None),
        ]
        
        metrics = calculate_decay_metrics(splits)
        
        assert metrics is None
    
    def test_empty_splits(self):
        """Empty splits list."""
        metrics = calculate_decay_metrics([])
        
        assert metrics is None
    
    def test_all_outliers(self):
        """All splits marked as outliers."""
        splits = [
            SplitData(1, 1000, 300, 300, 483, None, is_outlier=True),
            SplitData(2, 1000, 300, 300, 483, None, is_outlier=True),
            SplitData(3, 1000, 300, 300, 483, None, is_outlier=True),
        ]
        
        metrics = calculate_decay_metrics(splits)
        
        assert metrics is None


class TestRealWorldScenarios:
    """Test with realistic race data."""
    
    def test_typical_marathon_decay(self):
        """Simulate typical marathon with positive split."""
        # First half: 5:00/km, Second half: 5:30/km
        splits = []
        for i in range(1, 22):  # ~21 miles
            if i <= 10:
                pace = 300 + (i * 2)  # Slowly degrading
            else:
                pace = 320 + ((i - 10) * 5)  # Faster degradation in second half
            
            splits.append(SplitData(
                split_number=i,
                distance_m=1609.34,
                elapsed_time_s=pace * 1.609,
                pace_s_per_km=pace,
                pace_s_per_mile=pace * 1.609,
                average_hr=150 + i
            ))
        
        metrics = calculate_decay_metrics(splits)
        
        assert metrics is not None
        assert metrics.half_split_decay_pct > 5  # Should show decay
        assert metrics.overall_pattern in [SplitPattern.MODERATE_POSITIVE, SplitPattern.SEVERE_POSITIVE]
    
    def test_elite_even_split(self):
        """Simulate elite runner with even splits."""
        splits = []
        for i in range(1, 11):  # 10K
            # Very consistent ~3:00/km with ±3 second variance
            pace = 180 + (i % 3) - 1  # 179-181
            
            splits.append(SplitData(
                split_number=i,
                distance_m=1000,
                elapsed_time_s=pace,
                pace_s_per_km=pace,
                pace_s_per_mile=pace * 1.609,
                average_hr=175
            ))
        
        metrics = calculate_decay_metrics(splits)
        
        assert metrics is not None
        assert abs(metrics.half_split_decay_pct) < 3
        assert metrics.overall_pattern in [SplitPattern.EVEN, SplitPattern.NEGATIVE]


class TestConstants:
    """Test service constants."""
    
    def test_min_splits_value(self):
        """Minimum splits should be reasonable."""
        assert MIN_SPLITS_FOR_ANALYSIS >= 3
        assert MIN_SPLITS_FOR_ANALYSIS <= 5
    
    def test_distance_categories_exist(self):
        """Standard distance categories should exist."""
        assert "5K" in DISTANCE_CATEGORIES
        assert "10K" in DISTANCE_CATEGORIES
        assert "Half Marathon" in DISTANCE_CATEGORIES
        assert "Marathon" in DISTANCE_CATEGORIES
    
    def test_distance_category_ranges(self):
        """Distance category ranges should be valid."""
        for category, (low, high) in DISTANCE_CATEGORIES.items():
            assert low < high
            assert low > 0
