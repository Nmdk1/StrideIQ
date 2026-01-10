"""
Comprehensive tests for VDOT (Training Pace) Calculator
Tests formulas, edge cases, unit conversions, and accuracy
"""
import pytest
from services.vdot_calculator import (
    calculate_vdot_from_time,
    calculate_training_paces,
    calculate_equivalent_race_time,
)
from services.vdot_enhanced import (
    calculate_equivalent_races_enhanced,
    calculate_race_paces,
)


class TestVDOTCalculation:
    """Test VDOT calculation from race times"""
    
    def test_5k_20_minutes(self):
        """Standard 5K time"""
        vdot = calculate_vdot_from_time(20 * 60, 5000)
        assert vdot is not None
        assert 40 <= vdot <= 60  # Reasonable range for 20 min 5K
    
    def test_marathon_3_hours(self):
        """Standard marathon time"""
        vdot = calculate_vdot_from_time(3 * 3600, 42195)
        assert vdot is not None
        assert 40 <= vdot <= 60
    
    def test_one_mile_5_33(self):
        """One mile race time (recently added)"""
        vdot = calculate_vdot_from_time(5 * 60 + 33, 1609.34)
        assert vdot is not None
        assert vdot > 0
    
    def test_edge_case_very_fast(self):
        """Very fast time"""
        vdot = calculate_vdot_from_time(15 * 60, 5000)  # 15 min 5K
        assert vdot is not None
        assert vdot > 60
    
    def test_edge_case_very_slow(self):
        """Very slow time"""
        vdot = calculate_vdot_from_time(40 * 60, 5000)  # 40 min 5K
        assert vdot is not None
        assert vdot < 40


class TestTrainingPaces:
    """Test training pace calculations"""
    
    def test_training_paces_exist(self):
        """Verify all training paces are calculated"""
        vdot = 50.0
        paces = calculate_training_paces(vdot)
        
        assert 'easy' in paces
        assert 'marathon' in paces
        assert 'threshold' in paces
        assert 'interval' in paces
        assert 'repetition' in paces
    
    def test_pace_progression(self):
        """Verify paces are in correct order (easy > marathon > threshold > interval > repetition)"""
        vdot = 50.0
        paces = calculate_training_paces(vdot)
        
        # All paces should be in min/mile
        easy = paces['easy']
        marathon = paces['marathon']
        threshold = paces['threshold']
        interval = paces['interval']
        repetition = paces['repetition']
        
        # Easy should be slowest, repetition fastest
        assert easy > marathon > threshold > interval > repetition
    
    def test_paces_positive(self):
        """All paces should be positive"""
        vdot = 50.0
        paces = calculate_training_paces(vdot)
        
        for pace_name, pace_value in paces.items():
            assert pace_value > 0, f"{pace_name} pace should be positive"


class TestEquivalentRaceTimes:
    """Test equivalent race time calculations"""
    
    def test_equivalent_5k_to_10k(self):
        """5K time should predict slower 10K time"""
        vdot = calculate_vdot_from_time(20 * 60, 5000)
        equivalent_10k = calculate_equivalent_race_time(vdot, 10000)
        
        assert equivalent_10k is not None
        assert equivalent_10k > 20 * 60  # 10K should be slower than 5K
    
    def test_equivalent_marathon_to_5k(self):
        """Marathon time should predict faster 5K time"""
        vdot = calculate_vdot_from_time(3 * 3600, 42195)
        equivalent_5k = calculate_equivalent_race_time(vdot, 5000)
        
        assert equivalent_5k is not None
        assert equivalent_5k < 3 * 3600  # 5K should be faster than marathon
    
    def test_one_mile_equivalent(self):
        """Test one mile equivalent calculation"""
        vdot = calculate_vdot_from_time(5 * 60 + 33, 1609.34)
        equivalent_5k = calculate_equivalent_race_time(vdot, 5000)
        
        assert equivalent_5k is not None
        assert equivalent_5k > 0
    
    def test_race_paces_accuracy(self):
        """Test that race paces match equivalent times"""
        race_time_5k = 20 * 60  # 20 minutes
        vdot = calculate_vdot_from_time(race_time_5k, 5000)
        
        # Get race paces
        race_paces = calculate_race_paces(vdot)
        
        # Verify 5K pace matches input
        assert '5K' in race_paces
        pace_5k = race_paces['5K']  # min/mile
        
        # Convert pace to time: pace (min/mile) * distance (miles) = time (minutes)
        distance_miles_5k = 5000 / 1609.34
        calculated_time_minutes = pace_5k * distance_miles_5k
        calculated_time_seconds = calculated_time_minutes * 60
        
        # Should be close to original time (within 5%)
        assert abs(calculated_time_seconds - race_time_5k) / race_time_5k < 0.05


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_zero_time(self):
        """Zero time should return None"""
        vdot = calculate_vdot_from_time(0, 5000)
        assert vdot is None
    
    def test_negative_time(self):
        """Negative time should return None"""
        vdot = calculate_vdot_from_time(-100, 5000)
        assert vdot is None
    
    def test_zero_distance(self):
        """Zero distance should return None"""
        vdot = calculate_vdot_from_time(20 * 60, 0)
        assert vdot is None
    
    def test_very_short_distance(self):
        """Very short distance should handle gracefully"""
        vdot = calculate_vdot_from_time(60, 100)  # 100m in 1 minute
        # Should either return None or a valid VDOT
        assert vdot is None or vdot > 0
    
    def test_very_long_distance(self):
        """Very long distance (ultra) should handle gracefully"""
        vdot = calculate_vdot_from_time(10 * 3600, 100000)  # 100K in 10 hours
        assert vdot is None or vdot > 0

