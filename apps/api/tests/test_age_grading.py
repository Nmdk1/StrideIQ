"""
Comprehensive tests for WMA Age-Grading Calculator
Tests formulas, equivalent times, and edge cases
"""
import pytest
from services.performance_engine import (
    calculate_age_graded_performance,
    get_wma_age_factor,
)
from services.wma_age_factors import get_wma_world_record_pace


class TestAgeGradingCalculation:
    """Test age-graded performance percentage calculation"""
    
    def test_57_year_old_half_marathon(self):
        """Test the specific case that was failing"""
        # 57-year-old male, Half Marathon in 1:27:14
        time_seconds = 87 * 60 + 14  # 1:27:14
        distance_meters = 21097.5  # Half Marathon
        pace_per_mile = (time_seconds / 60) / (distance_meters / 1609.34)
        
        performance_pct = calculate_age_graded_performance(
            actual_pace_per_mile=pace_per_mile,
            age=57,
            sex='M',
            distance_meters=distance_meters,
            use_national=False
        )
        
        assert performance_pct is not None
        assert 70 <= performance_pct <= 80  # Should be around 76.9%
    
    def test_equivalent_open_time_faster(self):
        """Equivalent open time should be faster than actual time"""
        time_seconds = 87 * 60 + 14  # 1:27:14
        distance_meters = 21097.5
        age = 57
        age_factor = get_wma_age_factor(age, 'M', distance_meters)
        
        assert age_factor is not None
        assert age_factor > 1.0  # Age factor should slow down older athletes
        
        # Equivalent open time = actual_time / age_factor
        equivalent_time = time_seconds / age_factor
        
        assert equivalent_time < time_seconds  # Should be faster
    
    def test_30_year_old_factor_is_approximately_one(self):
        """30-year-old should have factor very close to 1.0 (open standard)"""
        factor = get_wma_age_factor(30, 'M', 5000)
        # Alan Jones 2025 has 1.0001 for age 30 (very close to peak)
        assert factor is not None
        assert 0.999 <= factor <= 1.002
    
    def test_older_athletes_higher_factor(self):
        """Older athletes should have higher factors"""
        factor_40 = get_wma_age_factor(40, 'M', 5000)
        factor_50 = get_wma_age_factor(50, 'M', 5000)
        factor_60 = get_wma_age_factor(60, 'M', 5000)
        
        assert factor_40 < factor_50 < factor_60
    
    def test_female_adjustment(self):
        """Female factors should be adjusted"""
        factor_male = get_wma_age_factor(50, 'M', 5000)
        factor_female = get_wma_age_factor(50, 'F', 5000)
        
        # Female factors are typically higher (slower standard)
        assert factor_female > factor_male


class TestAgeGradingEdgeCases:
    """Test edge cases for age-grading"""
    
    def test_prime_age_factor_is_one(self):
        """Prime age (around 19-29) should use factor 1.0"""
        factor = get_wma_age_factor(25, 'M', 5000)
        # Alan Jones 2025: ages 19-29 have factor = 1.0
        assert factor == 1.0
    
    def test_very_old_age(self):
        """Very old age should still return valid factor"""
        factor = get_wma_age_factor(90, 'M', 5000)
        assert factor is not None
        assert factor > 1.0
    
    def test_zero_pace(self):
        """Zero pace should return None"""
        performance_pct = calculate_age_graded_performance(
            actual_pace_per_mile=0,
            age=50,
            sex='M',
            distance_meters=5000
        )
        assert performance_pct is None
    
    def test_negative_pace(self):
        """Negative pace should return None"""
        performance_pct = calculate_age_graded_performance(
            actual_pace_per_mile=-10,
            age=50,
            sex='M',
            distance_meters=5000
        )
        assert performance_pct is None
    
    def test_none_age(self):
        """None age should return None"""
        performance_pct = calculate_age_graded_performance(
            actual_pace_per_mile=8.0,
            age=None,
            sex='M',
            distance_meters=5000
        )
        assert performance_pct is None


class TestDistanceSpecificFactors:
    """Test that different distances use appropriate factors"""
    
    def test_5k_factors(self):
        """5K should use 5K-specific factors"""
        factor_5k = get_wma_age_factor(50, 'M', 5000)
        assert factor_5k is not None
    
    def test_10k_factors(self):
        """10K should use 10K-specific factors"""
        factor_10k = get_wma_age_factor(50, 'M', 10000)
        assert factor_10k is not None
    
    def test_half_marathon_factors(self):
        """Half Marathon should use half-specific factors"""
        factor_half = get_wma_age_factor(50, 'M', 21097.5)
        assert factor_half is not None
    
    def test_marathon_factors(self):
        """Marathon should use marathon-specific factors"""
        factor_marathon = get_wma_age_factor(50, 'M', 42195)
        assert factor_marathon is not None
    
    def test_factors_differ_by_distance(self):
        """Factors should differ by distance"""
        factor_5k = get_wma_age_factor(50, 'M', 5000)
        factor_10k = get_wma_age_factor(50, 'M', 10000)
        factor_marathon = get_wma_age_factor(50, 'M', 42195)
        
        # Each distance has its own factors - they should differ
        # Note: The relationship between distances varies by age and methodology
        assert factor_5k != factor_10k or factor_10k != factor_marathon

