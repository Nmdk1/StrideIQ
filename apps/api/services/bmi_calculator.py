"""
BMI Calculation Service

Calculates BMI automatically when body composition data is recorded.
BMI = weight_kg / (height_m)²

Strategy: Internal metric initially, revealed when meaningful correlations are found.
"""
from decimal import Decimal
from typing import Optional


def calculate_bmi(weight_kg: Optional[Decimal], height_cm: Optional[Decimal]) -> Optional[Decimal]:
    """
    Calculate BMI from weight (kg) and height (cm).
    
    Formula: BMI = weight_kg / (height_m)²
    where height_m = height_cm / 100
    
    Args:
        weight_kg: Weight in kilograms
        height_cm: Height in centimeters
        
    Returns:
        BMI value (rounded to 1 decimal place) or None if inputs are missing
        
    Examples:
        >>> calculate_bmi(Decimal('70'), Decimal('175'))
        Decimal('22.9')
        >>> calculate_bmi(Decimal('70'), None)
        None
    """
    if weight_kg is None or height_cm is None:
        return None
    
    if weight_kg <= 0 or height_cm <= 0:
        return None
    
    # Convert height from cm to meters
    height_m = float(height_cm) / 100.0
    weight_float = float(weight_kg)
    
    # Calculate BMI
    bmi = weight_float / (height_m ** 2)
    
    # Round to 1 decimal place
    return Decimal(str(round(bmi, 1)))


# Note: BMI categories are NOT used in this program.
# BMI is just a number. Meaning is derived from hard data - correlations with performance.
# We do not label BMI as "overweight", "normal", etc.
# The data speaks - correlations with race times, efficiency, biomarkers.

