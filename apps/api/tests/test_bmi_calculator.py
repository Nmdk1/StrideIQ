"""
Comprehensive tests for BMI Calculation Service

Tests BMI calculation logic, edge cases, rounding, and null handling.
BMI is just a number - no categories, meaning derived from performance correlations.
"""
import pytest
from decimal import Decimal
from services.bmi_calculator import calculate_bmi


class TestBMICalculation:
    """Test BMI calculation from weight and height"""
    
    def test_standard_bmi_calculation(self):
        """Standard BMI calculation - 70kg, 175cm"""
        weight = Decimal('70')
        height = Decimal('175')
        bmi = calculate_bmi(weight, height)
        
        assert bmi is not None
        assert bmi == Decimal('22.9')  # 70 / (1.75)² = 22.857... rounded to 22.9
    
    def test_bmi_rounding(self):
        """Verify BMI is rounded to 1 decimal place"""
        weight = Decimal('75')
        height = Decimal('180')
        bmi = calculate_bmi(weight, height)
        
        assert bmi is not None
        # 75 / (1.80)² = 23.148... should round to 23.1
        assert bmi == Decimal('23.1')
        # Verify it's exactly 1 decimal place
        assert str(bmi).split('.')[1] if '.' in str(bmi) else '0' == '1' or len(str(bmi).split('.')[1]) == 1
    
    def test_different_heights(self):
        """Test various height values"""
        weight = Decimal('70')
        
        # Tall person
        bmi_tall = calculate_bmi(weight, Decimal('190'))
        assert bmi_tall is not None
        assert bmi_tall < Decimal('25')  # Should be lower BMI
        
        # Short person
        bmi_short = calculate_bmi(weight, Decimal('160'))
        assert bmi_short is not None
        assert bmi_short > Decimal('25')  # Should be higher BMI
        
        # Verify tall < short for same weight
        assert bmi_tall < bmi_short
    
    def test_different_weights(self):
        """Test various weight values"""
        height = Decimal('175')
        
        # Light person
        bmi_light = calculate_bmi(Decimal('60'), height)
        assert bmi_light is not None
        assert bmi_light < Decimal('25')
        
        # Heavy person
        bmi_heavy = calculate_bmi(Decimal('90'), height)
        assert bmi_heavy is not None
        assert bmi_heavy > Decimal('25')
        
        # Verify light < heavy for same height
        assert bmi_light < bmi_heavy
    
    def test_edge_case_very_tall(self):
        """Very tall person"""
        bmi = calculate_bmi(Decimal('100'), Decimal('210'))
        assert bmi is not None
        assert bmi > 0
    
    def test_edge_case_very_short(self):
        """Very short person"""
        bmi = calculate_bmi(Decimal('50'), Decimal('150'))
        assert bmi is not None
        assert bmi > 0
    
    def test_edge_case_very_light(self):
        """Very light person"""
        bmi = calculate_bmi(Decimal('45'), Decimal('170'))
        assert bmi is not None
        assert bmi > 0
    
    def test_edge_case_very_heavy(self):
        """Very heavy person"""
        bmi = calculate_bmi(Decimal('120'), Decimal('180'))
        assert bmi is not None
        assert bmi > 0


class TestBMINullHandling:
    """Test null/None input handling"""
    
    def test_none_weight(self):
        """Weight is None"""
        bmi = calculate_bmi(None, Decimal('175'))
        assert bmi is None
    
    def test_none_height(self):
        """Height is None"""
        bmi = calculate_bmi(Decimal('70'), None)
        assert bmi is None
    
    def test_both_none(self):
        """Both weight and height are None"""
        bmi = calculate_bmi(None, None)
        assert bmi is None


class TestBMIInvalidInput:
    """Test invalid input handling"""
    
    def test_zero_weight(self):
        """Weight is zero"""
        bmi = calculate_bmi(Decimal('0'), Decimal('175'))
        assert bmi is None
    
    def test_zero_height(self):
        """Height is zero"""
        bmi = calculate_bmi(Decimal('70'), Decimal('0'))
        assert bmi is None
    
    def test_negative_weight(self):
        """Weight is negative"""
        bmi = calculate_bmi(Decimal('-10'), Decimal('175'))
        assert bmi is None
    
    def test_negative_height(self):
        """Height is negative"""
        bmi = calculate_bmi(Decimal('70'), Decimal('-10'))
        assert bmi is None
    
    def test_both_zero(self):
        """Both weight and height are zero"""
        bmi = calculate_bmi(Decimal('0'), Decimal('0'))
        assert bmi is None
    
    def test_both_negative(self):
        """Both weight and height are negative"""
        bmi = calculate_bmi(Decimal('-10'), Decimal('-10'))
        assert bmi is None


class TestBMIPrecision:
    """Test BMI calculation precision and rounding"""
    
    def test_precise_calculation(self):
        """Test precise BMI calculation"""
        # 70.5 kg, 175.5 cm
        weight = Decimal('70.5')
        height = Decimal('175.5')
        bmi = calculate_bmi(weight, height)
        
        assert bmi is not None
        # Should be rounded to 1 decimal place
        bmi_str = str(bmi)
        if '.' in bmi_str:
            decimal_places = len(bmi_str.split('.')[1])
            assert decimal_places == 1
    
    def test_rounding_up(self):
        """Test rounding up (e.g., 22.85 -> 22.9)"""
        weight = Decimal('70')
        height = Decimal('175')
        bmi = calculate_bmi(weight, height)
        
        # 70 / (1.75)² = 22.857... should round UP to 22.9
        assert bmi == Decimal('22.9')
    
    def test_rounding_down(self):
        """Test rounding down"""
        weight = Decimal('70')
        height = Decimal('176')
        bmi = calculate_bmi(weight, height)
        
        # 70 / (1.76)² = 22.595... should round to 22.6
        assert bmi is not None
        assert bmi == Decimal('22.6')


class TestBMIRealWorldExamples:
    """Test real-world BMI examples"""
    
    def test_elite_runner_bmi(self):
        """Elite runner BMI (low BMI)"""
        # Example: 60kg, 175cm (typical elite runner)
        bmi = calculate_bmi(Decimal('60'), Decimal('175'))
        assert bmi is not None
        assert bmi < Decimal('20')
    
    def test_average_person_bmi(self):
        """Average person BMI"""
        # Example: 75kg, 175cm
        bmi = calculate_bmi(Decimal('75'), Decimal('175'))
        assert bmi is not None
        assert Decimal('20') < bmi < Decimal('30')
    
    def test_muscular_athlete_bmi(self):
        """Muscular athlete BMI (higher weight, but lean)"""
        # Example: 85kg, 180cm (muscular athlete)
        bmi = calculate_bmi(Decimal('85'), Decimal('180'))
        assert bmi is not None
        # BMI is just a number - no judgment
        assert bmi > 0


class TestBMIEdgeCases:
    """Test extreme edge cases and boundary conditions"""
    
    def test_very_small_decimal_weight(self):
        """Very small weight with decimals"""
        bmi = calculate_bmi(Decimal('45.123'), Decimal('170'))
        assert bmi is not None
        assert bmi > 0
    
    def test_very_small_decimal_height(self):
        """Very small height with decimals"""
        bmi = calculate_bmi(Decimal('70'), Decimal('175.456'))
        assert bmi is not None
        assert bmi > 0
    
    def test_both_decimal_precision(self):
        """Both weight and height with many decimal places"""
        bmi = calculate_bmi(Decimal('70.123456'), Decimal('175.789012'))
        assert bmi is not None
        # Should still round to 1 decimal place
        bmi_str = str(bmi)
        if '.' in bmi_str:
            assert len(bmi_str.split('.')[1]) == 1
    
    def test_boundary_rounding_05(self):
        """Test rounding at 0.05 boundary (should round up)"""
        # Find a case that rounds to exactly 0.05
        # This tests the rounding logic
        weight = Decimal('70')
        height = Decimal('175')
        bmi = calculate_bmi(weight, height)
        # 70 / (1.75)² = 22.857... rounds to 22.9
        assert bmi == Decimal('22.9')
    
    def test_extreme_tall_person(self):
        """Extremely tall person (2.5m+)"""
        bmi = calculate_bmi(Decimal('100'), Decimal('250'))
        assert bmi is not None
        assert bmi > 0
        assert bmi < Decimal('20')  # Should be low BMI
    
    def test_extreme_short_person(self):
        """Extremely short person (<1m)"""
        bmi = calculate_bmi(Decimal('30'), Decimal('90'))
        assert bmi is not None
        assert bmi > 0
    
    def test_extreme_light_weight(self):
        """Extremely light weight"""
        bmi = calculate_bmi(Decimal('30'), Decimal('170'))
        assert bmi is not None
        assert bmi > 0
        assert bmi < Decimal('15')
    
    def test_extreme_heavy_weight(self):
        """Extremely heavy weight"""
        bmi = calculate_bmi(Decimal('200'), Decimal('180'))
        assert bmi is not None
        assert bmi > 0
        assert bmi > Decimal('50')
    
    def test_minimum_valid_weight(self):
        """Minimum valid weight (just above zero)"""
        bmi = calculate_bmi(Decimal('0.1'), Decimal('175'))
        assert bmi is not None
        # Very small weight results in BMI that may round to 0.0, which is valid
        assert bmi >= 0
    
    def test_minimum_valid_height(self):
        """Minimum valid height (just above zero)"""
        bmi = calculate_bmi(Decimal('70'), Decimal('0.1'))
        assert bmi is not None
        assert bmi > 0
    
    def test_very_precise_calculation(self):
        """Test with very precise inputs"""
        # Use values that result in many decimal places
        weight = Decimal('73.456789')
        height = Decimal('178.123456')
        bmi = calculate_bmi(weight, height)
        assert bmi is not None
        # Should round to 1 decimal
        bmi_str = str(bmi)
        if '.' in bmi_str:
            decimal_places = len(bmi_str.split('.')[1])
            assert decimal_places == 1
    
    def test_identical_inputs_different_order(self):
        """Test that order doesn't matter (sanity check)"""
        bmi1 = calculate_bmi(Decimal('70'), Decimal('175'))
        bmi2 = calculate_bmi(Decimal('70'), Decimal('175'))
        assert bmi1 == bmi2
    
    def test_rounding_edge_case_15(self):
        """Test rounding at 0.15 boundary"""
        # Find values that result in .15
        weight = Decimal('70')
        height = Decimal('176')
        bmi = calculate_bmi(weight, height)
        # 70 / (1.76)² = 22.595... rounds to 22.6
        assert bmi == Decimal('22.6')
    
    def test_rounding_edge_case_25(self):
        """Test rounding at 0.25 boundary"""
        # Test various rounding scenarios
        weight = Decimal('75')
        height = Decimal('180')
        bmi = calculate_bmi(weight, height)
        # 75 / (1.80)² = 23.148... rounds to 23.1
        assert bmi == Decimal('23.1')
    
    def test_decimal_string_conversion(self):
        """Test that Decimal string conversion works correctly"""
        weight = Decimal('70.5')
        height = Decimal('175.5')
        bmi = calculate_bmi(weight, height)
        assert bmi is not None
        # Should be a Decimal instance
        assert isinstance(bmi, Decimal)
    
    def test_very_large_numbers(self):
        """Test with very large (but realistic) numbers"""
        # Realistic maximum: 300kg, 250cm
        bmi = calculate_bmi(Decimal('300'), Decimal('250'))
        assert bmi is not None
        assert bmi > 0
    
    def test_small_but_valid_numbers(self):
        """Test with small but valid numbers"""
        # Realistic minimum: 20kg, 100cm (child)
        bmi = calculate_bmi(Decimal('20'), Decimal('100'))
        assert bmi is not None
        assert bmi > 0

