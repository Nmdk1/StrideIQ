"""
Comprehensive WMA Age-Grading Tests - Alan Jones 2025 Edition

Verifies our implementation against the official Alan Jones 2025 tables.
Source: https://github.com/AlanLyttonJones/Age-Grade-Tables

Key difference from old WMA methodology:
- Alan Jones 2025 provides PER-YEAR factors (not 5-year groups)
- More accurate age-grading for all ages 5-100
- Distance-specific factors for 1 Mile, 5K, 8K, 10K, 10 Mile, Half, Marathon
"""

import pytest
from services.wma_age_factors import (
    get_wma_age_factor,
    get_wma_open_standard_seconds,
    _get_age_group_start,
)


class TestAgeGroupStartHelper:
    """Test the age group start helper function.
    
    Note: This is a utility function for compatibility with old methodology.
    Alan Jones 2025 uses per-year factors, not 5-year groups.
    """
    
    def test_age_group_start_under_35(self):
        """Ages under 35 should return the actual age."""
        assert _get_age_group_start(25) == 25
        assert _get_age_group_start(30) == 30
        assert _get_age_group_start(34) == 34
    
    def test_age_group_start_35_plus(self):
        """Ages 35+ should round down to 5-year group start."""
        assert _get_age_group_start(35) == 35
        assert _get_age_group_start(36) == 35
        assert _get_age_group_start(39) == 35
        assert _get_age_group_start(40) == 40
        assert _get_age_group_start(44) == 40
        assert _get_age_group_start(45) == 45
        assert _get_age_group_start(55) == 55
        assert _get_age_group_start(57) == 55
        assert _get_age_group_start(59) == 55
        assert _get_age_group_start(60) == 60


class TestAlanJones2025PerYearFactors:
    """Test that Alan Jones 2025 provides per-year factors (not grouped)."""
    
    def test_adjacent_ages_have_different_factors(self):
        """Each age should have its own distinct factor."""
        factor_55 = get_wma_age_factor(55, 'M', 5000)
        factor_56 = get_wma_age_factor(56, 'M', 5000)
        factor_57 = get_wma_age_factor(57, 'M', 5000)
        
        # Per-year factors should be different
        assert factor_55 != factor_56
        assert factor_56 != factor_57
        
        # Older ages should have higher factors (slower equivalent times)
        assert factor_55 < factor_56 < factor_57
    
    def test_factors_increase_monotonically_after_peak(self):
        """After peak age, factors should increase each year."""
        factors = [get_wma_age_factor(age, 'M', 5000) for age in range(30, 70)]
        
        # Find peak (lowest factor, usually around age 25-30)
        min_idx = factors.index(min(factors))
        
        # After peak, factors should generally increase
        for i in range(min_idx + 1, len(factors) - 1):
            assert factors[i] <= factors[i + 1], f"Factor at {30+i} should be <= {30+i+1}"
    
    def test_age_boundaries(self):
        """Test transitions between ages."""
        factor_54 = get_wma_age_factor(54, 'M', 5000)
        factor_55 = get_wma_age_factor(55, 'M', 5000)
        
        # Adjacent years should have slightly different factors
        assert factor_54 < factor_55
        # But the difference should be small (< 2%)
        assert (factor_55 - factor_54) / factor_54 < 0.02


class TestFactorValues:
    """Test specific factor values from Alan Jones 2025 tables."""
    
    def test_open_ages_factor_is_approximately_one(self):
        """Ages 19-29 should have factors very close to 1.0."""
        for age in range(19, 30):
            factor = get_wma_age_factor(age, 'M', 5000)
            assert factor is not None
            assert 0.99 <= factor <= 1.01, f"Age {age} factor {factor} not ~1.0"
    
    def test_factors_increase_with_age(self):
        """Factors should increase as age increases (after prime)."""
        ages = [40, 50, 60, 70, 80]
        factors = [get_wma_age_factor(age, 'M', 5000) for age in ages]
        
        for i in range(len(factors) - 1):
            assert factors[i] < factors[i + 1], f"Factor at {ages[i]} should be < {ages[i+1]}"
    
    def test_specific_alan_jones_5k_male_factors(self):
        """Verify specific factor values from Alan Jones 2025 5K Male table."""
        # These values come directly from WMA_5K_MALE in wma_age_factors.py
        expected = {
            19: 1.0,
            25: 1.0,
            30: 1.0001,
            40: 1.0554,
            50: 1.1396,
            55: 1.1869,
            60: 1.2384,
            70: 1.36,
            80: 1.6152,
            90: 2.2578,
        }
        
        for age, expected_factor in expected.items():
            actual = get_wma_age_factor(age, 'M', 5000)
            assert abs(actual - expected_factor) < 0.001, \
                f"M{age} 5K factor {actual} != {expected_factor}"


class TestOpenStandards:
    """Test open (prime age) standards."""
    
    def test_5k_male_open_standard(self):
        """5K male open standard should be around 12:49."""
        standard = get_wma_open_standard_seconds('M', 5000)
        assert standard is not None
        # Alan Jones 2025: 769.0 seconds (12:49)
        assert 765 < standard < 775
    
    def test_10k_male_open_standard(self):
        """10K male open standard should be around 26:24."""
        standard = get_wma_open_standard_seconds('M', 10000)
        assert standard is not None
        # 26:24 = 1584 seconds
        assert 1570 < standard < 1600
    
    def test_half_marathon_male_open_standard(self):
        """Half marathon male standard should be around 58:xx."""
        standard = get_wma_open_standard_seconds('M', 21097)
        assert standard is not None
        # Around 58:30-59:00 = ~3510-3540 seconds
        assert 3400 < standard < 3600
    
    def test_marathon_male_open_standard(self):
        """Marathon male standard should be around 2:02:xx."""
        standard = get_wma_open_standard_seconds('M', 42195)
        assert standard is not None
        # 2:02:00 = 7320 seconds
        assert 7200 < standard < 7500


class TestPerformanceCalculations:
    """Test age-graded performance calculations."""
    
    def test_age_graded_performance_formula(self):
        """Verify the age-grading formula works correctly."""
        age = 57
        sex = 'M'
        distance = 5000
        actual_time = 18 * 60 + 53  # 18:53
        
        factor = get_wma_age_factor(age, sex, distance)
        open_standard = get_wma_open_standard_seconds(sex, distance)
        
        # Age-graded time = actual_time / factor
        age_graded_time = actual_time / factor
        
        # Performance % = (open_standard / age_graded_time) * 100
        performance_pct = (open_standard / age_graded_time) * 100
        
        # Should be around 80% for this example
        assert 75 < performance_pct < 85
    
    def test_equivalent_performance_calculation(self):
        """An 80% performance should be equivalent across ages."""
        distance = 5000
        open_standard = get_wma_open_standard_seconds('M', distance)
        
        # 80% performance at open standard
        target_pct = 80.0
        open_equivalent = open_standard / (target_pct / 100)
        
        # For a 55yo, the equivalent time should be longer
        factor_55 = get_wma_age_factor(55, 'M', distance)
        time_55 = open_equivalent * factor_55
        
        # 55yo time should be longer than open standard time
        assert time_55 > open_equivalent


class TestEdgeCases:
    """Test edge cases and boundaries."""
    
    def test_age_100_returns_valid_factor(self):
        """Age 100 should return a valid (high) factor."""
        factor = get_wma_age_factor(100, 'M', 5000)
        assert factor is not None
        assert factor > 4  # Very high factor for centenarian
    
    def test_age_over_100_capped(self):
        """Ages over 100 should be capped at 100."""
        factor_100 = get_wma_age_factor(100, 'M', 5000)
        factor_105 = get_wma_age_factor(105, 'M', 5000)
        assert factor_100 == factor_105
    
    def test_very_young_age_returns_factor(self):
        """Young ages (5-18) should return valid factors."""
        factor_10 = get_wma_age_factor(10, 'M', 5000)
        assert factor_10 is not None
        assert factor_10 > 1.0  # Young athletes have slower equivalent times
    
    def test_age_below_5_returns_none(self):
        """Ages below 5 should return None."""
        assert get_wma_age_factor(4, 'M', 5000) is None
        assert get_wma_age_factor(0, 'M', 5000) is None
    
    def test_female_factors_exist(self):
        """Female factors should be provided."""
        factor = get_wma_age_factor(40, 'F', 5000)
        assert factor is not None
        assert factor > 1.0


class TestDistanceSpecificFactors:
    """Test that factors are distance-specific."""
    
    def test_different_distances_different_factors(self):
        """Same age should have different factors for different distances."""
        factor_5k = get_wma_age_factor(55, 'M', 5000)
        factor_10k = get_wma_age_factor(55, 'M', 10000)
        factor_marathon = get_wma_age_factor(55, 'M', 42195)
        
        # Factors should differ by distance
        assert factor_5k != factor_10k
        assert factor_10k != factor_marathon
    
    def test_all_supported_distances_work(self):
        """All supported distances should return valid factors."""
        distances = [1609.34, 5000, 8000, 10000, 16093, 21097, 42195]
        
        for dist in distances:
            factor = get_wma_age_factor(50, 'M', dist)
            assert factor is not None, f"No factor for distance {dist}"
            assert factor > 1.0


class TestMaleVsFemaleFactors:
    """Test male vs female factor relationships."""
    
    def test_female_open_standards_slower_than_male(self):
        """Female open standards should be slower than male."""
        male_5k = get_wma_open_standard_seconds('M', 5000)
        female_5k = get_wma_open_standard_seconds('F', 5000)
        
        assert female_5k > male_5k
    
    def test_both_sexes_have_factors_for_all_ages(self):
        """Both M and F should have factors for ages 5-100."""
        for age in [10, 25, 40, 55, 70, 85, 100]:
            male = get_wma_age_factor(age, 'M', 5000)
            female = get_wma_age_factor(age, 'F', 5000)
            
            assert male is not None, f"No male factor for age {age}"
            assert female is not None, f"No female factor for age {age}"


class TestConsistencyAcrossDistances:
    """Test consistency of the implementation across all distances."""
    
    def test_marathon_factors_reasonable(self):
        """Marathon factors should be reasonable."""
        factor_30 = get_wma_age_factor(30, 'M', 42195)
        factor_60 = get_wma_age_factor(60, 'M', 42195)
        factor_80 = get_wma_age_factor(80, 'M', 42195)
        
        # 30yo should be close to 1.0
        assert 0.99 <= factor_30 <= 1.02
        
        # 60yo should be meaningfully higher
        assert factor_60 > 1.2
        
        # 80yo should be much higher
        assert factor_80 > 1.5
    
    def test_one_mile_factors_exist(self):
        """1 Mile distance should work."""
        factor = get_wma_age_factor(50, 'M', 1609.34)
        assert factor is not None
        assert factor > 1.0
