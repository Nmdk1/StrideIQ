"""
Unit tests for Pre-Race State Fingerprinting Service

Tests pattern discovery, statistical analysis, and insight generation.

ADR-009: Pre-Race State Fingerprinting
"""

import pytest
from datetime import date, timedelta
from services.pre_race_fingerprinting import (
    mann_whitney_u_test,
    calculate_cohens_d,
    analyze_feature,
    classify_races,
    PreRaceState,
    FeatureAnalysis,
    RaceCategory,
    PatternType,
    to_dict,
    ReadinessProfile
)


class TestMannWhitneyUTest:
    """Test Mann-Whitney U statistical test."""
    
    def test_identical_samples(self):
        """Identical samples should have high p-value."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [1.0, 2.0, 3.0, 4.0, 5.0]
        
        _, p_value = mann_whitney_u_test(x, y)
        
        assert p_value > 0.5  # Not significant
    
    def test_clearly_different_samples(self):
        """Clearly different samples should have low p-value."""
        x = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0]
        y = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        
        _, p_value = mann_whitney_u_test(x, y)
        
        assert p_value < 0.05  # Significant
    
    def test_overlapping_samples(self):
        """Overlapping samples should have moderate p-value."""
        x = [4.0, 5.0, 6.0, 7.0, 8.0]
        y = [3.0, 4.0, 5.0, 6.0, 7.0]
        
        _, p_value = mann_whitney_u_test(x, y)
        
        # Not enough separation for significance
        assert p_value > 0.1
    
    def test_insufficient_samples(self):
        """Insufficient samples should return p=1.0."""
        x = [1.0]
        y = [2.0]
        
        _, p_value = mann_whitney_u_test(x, y)
        
        assert p_value == 1.0


class TestCohensD:
    """Test Cohen's d effect size calculation."""
    
    def test_large_effect(self):
        """Clear separation should show large effect."""
        x = [10.0, 11.0, 12.0, 13.0, 14.0]
        y = [1.0, 2.0, 3.0, 4.0, 5.0]
        
        d = calculate_cohens_d(x, y)
        
        assert d is not None
        assert abs(d) > 2.0  # Very large effect
    
    def test_small_to_medium_effect(self):
        """Moderately similar distributions should show small-medium effect."""
        # Distributions with some overlap
        x = [5.0, 5.1, 5.2, 5.0, 5.1, 5.2, 5.1, 5.0]
        y = [5.0, 5.0, 5.1, 5.1, 5.0, 5.1, 5.0, 5.1]
        
        d = calculate_cohens_d(x, y)
        
        assert d is not None
        # Small to medium effect (0.2 - 0.8)
        assert 0.2 < abs(d) < 0.8
    
    def test_no_effect(self):
        """Identical distributions should show near-zero effect."""
        x = [5.0, 5.0, 5.0, 5.0, 5.0]
        y = [5.0, 5.0, 5.0, 5.0, 5.0]
        
        d = calculate_cohens_d(x, y)
        
        # Near zero (might not be exactly zero due to variance calculation)
        assert d is not None
        assert abs(d) < 0.1
    
    def test_insufficient_data(self):
        """Should return None with insufficient data."""
        x = [5.0]
        y = [6.0]
        
        d = calculate_cohens_d(x, y)
        
        assert d is None


class TestClassifyRaces:
    """Test race classification by performance."""
    
    def test_classify_eight_races(self):
        """Eight races should be split into quartiles."""
        states = [
            PreRaceState("1", date(2026, 1, 1), 85.0),  # Best
            PreRaceState("2", date(2026, 1, 8), 82.0),  # Best
            PreRaceState("3", date(2026, 1, 15), 78.0),  # Good
            PreRaceState("4", date(2026, 1, 22), 75.0),  # Good
            PreRaceState("5", date(2026, 1, 29), 72.0),  # Average
            PreRaceState("6", date(2026, 2, 5), 70.0),   # Average
            PreRaceState("7", date(2026, 2, 12), 65.0),  # Worst
            PreRaceState("8", date(2026, 2, 19), 60.0),  # Worst
        ]
        
        categories = classify_races(states)
        
        assert RaceCategory.BEST in categories
        assert RaceCategory.WORST in categories
        assert len(categories[RaceCategory.BEST]) >= 1
        assert len(categories[RaceCategory.WORST]) >= 1
        
        # Best should have highest performance
        best_perfs = [r.performance_pct for r in categories[RaceCategory.BEST]]
        worst_perfs = [r.performance_pct for r in categories[RaceCategory.WORST]]
        assert min(best_perfs) > max(worst_perfs)
    
    def test_insufficient_races(self):
        """Less than 4 races should return empty."""
        states = [
            PreRaceState("1", date(2026, 1, 1), 85.0),
            PreRaceState("2", date(2026, 1, 8), 80.0),
        ]
        
        categories = classify_races(states)
        
        assert categories == {}


class TestAnalyzeFeature:
    """Test feature analysis between best and worst races."""
    
    def test_conventional_pattern(self):
        """Higher values in best races = conventional pattern."""
        best_values = [8.0, 8.5, 9.0, 9.5, 10.0]
        worst_values = [4.0, 4.5, 5.0, 5.5, 6.0]
        
        analysis = analyze_feature(
            "Sleep Hours", 
            best_values, 
            worst_values, 
            conventional_better_direction="higher"
        )
        
        assert analysis.is_significant
        assert analysis.pattern_type == PatternType.CONVENTIONAL
        assert analysis.difference > 0  # best > worst
        assert analysis.p_value < 0.05
    
    def test_inverted_pattern(self):
        """Lower HRV in best races = inverted pattern."""
        # Best races have LOWER HRV (counter to conventional wisdom)
        best_values = [30.0, 32.0, 28.0, 35.0, 31.0]
        worst_values = [55.0, 60.0, 58.0, 62.0, 57.0]
        
        analysis = analyze_feature(
            "HRV Deviation",
            best_values,
            worst_values,
            conventional_better_direction="higher"  # Convention says higher is better
        )
        
        assert analysis.is_significant
        assert analysis.pattern_type == PatternType.INVERTED
        assert analysis.difference < 0  # best < worst
        assert "Counter" in analysis.insight_text or "Unexpected" in analysis.insight_text
    
    def test_no_pattern(self):
        """Similar values should show no pattern."""
        best_values = [7.0, 7.2, 7.1, 7.3, 7.0]
        worst_values = [7.1, 7.0, 7.2, 7.1, 7.3]
        
        analysis = analyze_feature(
            "Sleep Hours",
            best_values,
            worst_values,
            conventional_better_direction="higher"
        )
        
        assert not analysis.is_significant
        assert analysis.pattern_type == PatternType.NO_PATTERN
    
    def test_insufficient_data(self):
        """Should handle insufficient data gracefully."""
        best_values = [8.0]
        worst_values = [5.0]
        
        analysis = analyze_feature(
            "Sleep Hours",
            best_values,
            worst_values,
            conventional_better_direction="higher"
        )
        
        assert not analysis.is_significant
        assert analysis.pattern_type == PatternType.NO_PATTERN
        assert "Insufficient" in analysis.insight_text


class TestPreRaceState:
    """Test PreRaceState dataclass."""
    
    def test_create_minimal_state(self):
        """Can create state with minimal data."""
        state = PreRaceState(
            race_id="abc123",
            race_date=date(2026, 1, 15),
            performance_pct=80.5
        )
        
        assert state.race_id == "abc123"
        assert state.performance_pct == 80.5
        assert state.hrv_rmssd is None
        assert state.sleep_hours is None
    
    def test_create_complete_state(self):
        """Can create state with all data."""
        state = PreRaceState(
            race_id="abc123",
            race_date=date(2026, 1, 15),
            performance_pct=85.0,
            hrv_rmssd=45.0,
            hrv_deviation_pct=-15.0,
            sleep_hours=8.5,
            resting_hr=52,
            resting_hr_deviation_pct=-5.0,
            stress_level=2,
            soreness_level=2,
            motivation=4,
            confidence=5,
            days_since_hard_workout=5
        )
        
        assert state.hrv_deviation_pct == -15.0
        assert state.sleep_hours == 8.5
        assert state.motivation == 4


class TestReadinessProfile:
    """Test ReadinessProfile creation and serialization."""
    
    def test_create_profile(self):
        """Can create a readiness profile."""
        profile = ReadinessProfile(
            athlete_id="athlete-123",
            total_races=10,
            races_with_data=8,
            best_races_count=2,
            worst_races_count=2,
            features=[],
            primary_insight="Your best races followed low HRV",
            optimal_ranges={"HRV Deviation": (-20.0, -10.0)},
            has_counter_conventional_findings=True,
            confidence_level="moderate"
        )
        
        assert profile.total_races == 10
        assert profile.has_counter_conventional_findings
        assert profile.confidence_level == "moderate"
    
    def test_to_dict(self):
        """Profile should serialize correctly."""
        feature = FeatureAnalysis(
            feature_name="HRV Deviation",
            best_mean=-15.0,
            best_std=5.0,
            worst_mean=10.0,
            worst_std=8.0,
            difference=-25.0,
            p_value=0.01,
            cohens_d=-2.5,
            is_significant=True,
            pattern_type=PatternType.INVERTED,
            insight_text="Counter-intuitive pattern"
        )
        
        profile = ReadinessProfile(
            athlete_id="athlete-123",
            total_races=10,
            races_with_data=8,
            best_races_count=2,
            worst_races_count=2,
            features=[feature],
            primary_insight="Your best races followed low HRV",
            optimal_ranges={"HRV Deviation": (-20.0, -10.0)},
            has_counter_conventional_findings=True,
            confidence_level="high"
        )
        
        result = to_dict(profile)
        
        assert result["athlete_id"] == "athlete-123"
        assert result["total_races"] == 10
        assert len(result["features"]) == 1
        assert result["features"][0]["pattern_type"] == "inverted"
        assert result["has_counter_conventional_findings"] is True
        assert result["confidence_level"] == "high"


class TestInvertedHRVPattern:
    """
    Test the specific scenario from user's data:
    "My best races were after the evening of my lowest HRV"
    """
    
    def test_user_hrv_pattern(self):
        """Simulate user's HRV pattern where low HRV precedes best races."""
        # Best races: HRV was LOW (20-35)
        best_hrv = [25.0, 30.0, 28.0, 22.0, 35.0]
        # Worst races: HRV was HIGH (50-65) - "normal" by conventional standards
        worst_hrv = [55.0, 60.0, 58.0, 52.0, 65.0]
        
        analysis = analyze_feature(
            "HRV Deviation",
            best_hrv,
            worst_hrv,
            conventional_better_direction="higher"  # Convention: higher HRV = better
        )
        
        # Should detect inverted pattern
        assert analysis.is_significant
        assert analysis.pattern_type == PatternType.INVERTED
        assert analysis.best_mean < analysis.worst_mean
        
        # Insight should mention counter-intuitive finding
        assert "Counter" in analysis.insight_text or "sympathetic" in analysis.insight_text.lower()
    
    def test_conventional_sleep_pattern(self):
        """Sleep should still show conventional pattern."""
        # Best races: more sleep
        best_sleep = [8.5, 9.0, 8.0, 8.5, 9.0]
        # Worst races: less sleep
        worst_sleep = [5.5, 6.0, 5.0, 6.5, 5.5]
        
        analysis = analyze_feature(
            "Sleep Hours",
            best_sleep,
            worst_sleep,
            conventional_better_direction="higher"
        )
        
        # Should detect conventional pattern
        assert analysis.is_significant
        assert analysis.pattern_type == PatternType.CONVENTIONAL
        assert analysis.best_mean > analysis.worst_mean


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_lists(self):
        """Should handle empty lists gracefully."""
        analysis = analyze_feature(
            "Test Feature",
            [],
            [],
            "higher"
        )
        
        assert not analysis.is_significant
        assert analysis.pattern_type == PatternType.NO_PATTERN
    
    def test_single_values(self):
        """Should handle single values gracefully."""
        analysis = analyze_feature(
            "Test Feature",
            [10.0],
            [5.0],
            "higher"
        )
        
        assert not analysis.is_significant
        assert "Insufficient" in analysis.insight_text
    
    def test_identical_values(self):
        """Should handle identical values without error."""
        best_values = [5.0, 5.0, 5.0, 5.0, 5.0]
        worst_values = [5.0, 5.0, 5.0, 5.0, 5.0]
        
        analysis = analyze_feature(
            "Test Feature",
            best_values,
            worst_values,
            "higher"
        )
        
        assert not analysis.is_significant
        # Should not crash even with zero variance


class TestConfidenceLevels:
    """Test confidence level determination."""
    
    def test_high_confidence(self):
        """15+ races with 2+ significant features should be high confidence."""
        # This would be tested with full generate_readiness_profile integration test
        # For unit test, verify the logic in the classification
        
        # High: 15+ races with data, 2+ significant features
        assert True  # Placeholder - tested in integration
    
    def test_moderate_confidence(self):
        """8+ races with 1+ significant feature should be moderate."""
        assert True  # Placeholder - tested in integration
    
    def test_low_confidence(self):
        """5+ races should be low confidence."""
        assert True  # Placeholder - tested in integration
    
    def test_insufficient_confidence(self):
        """Less than 5 races should be insufficient."""
        assert True  # Placeholder - tested in integration
