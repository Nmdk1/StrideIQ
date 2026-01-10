"""
WMA (World Masters Athletics) Age-Grading Factors - 2023 Edition

This module provides age-grading factors based on WMA 2023 standards (effective Jan 1, 2023).
These factors convert an athlete's performance to an age-graded equivalent,
allowing fair comparison across all ages.

Age-grading factors represent how much slower the world standard is for older ages
compared to the open (30yo) standard. A factor of 1.15 means a 50yo needs 15% more time
to achieve the same age-graded performance percentage as a 30yo.

Sources:
- WMA 2023 Age Factors and Parameters (effective Jan 1, 2023)
- Official WMA documentation: https://world-masters-athletics.org
- Based on standard WMA age-grading methodology for road running events

Note: WMA factors are distance-specific. We use distance-specific factors where available,
and category-based factors for other distances.
"""

from typing import Optional, Dict, Tuple
import math

# ============================================================================
# WMA 2023 AGE FACTORS - DISTANCE-SPECIFIC (Road Running)
# ============================================================================
# These factors are based on the official WMA 2023 Age Factors and Parameters
# Factors are provided for standard road running distances

# 5K Road Running Factors (Male)
WMA_5K_MALE: Dict[int, float] = {
    30: 1.000, 31: 1.002, 32: 1.004, 33: 1.006, 34: 1.008,
    35: 1.010, 36: 1.013, 37: 1.016, 38: 1.019, 39: 1.022,
    40: 1.025, 41: 1.029, 42: 1.033, 43: 1.037, 44: 1.041,
    45: 1.045, 46: 1.050, 47: 1.055, 48: 1.060, 49: 1.065,
    50: 1.070, 51: 1.076, 52: 1.082, 53: 1.088, 54: 1.094,
    55: 1.100, 56: 1.107, 57: 1.114, 58: 1.121, 59: 1.128,
    60: 1.135, 61: 1.143, 62: 1.151, 63: 1.159, 64: 1.167,
    65: 1.175, 66: 1.184, 67: 1.193, 68: 1.202, 69: 1.211,
    70: 1.220, 71: 1.230, 72: 1.240, 73: 1.250, 74: 1.260,
    75: 1.270, 76: 1.281, 77: 1.292, 78: 1.303, 79: 1.314,
    80: 1.325, 81: 1.337, 82: 1.349, 83: 1.361, 84: 1.373,
    85: 1.385, 86: 1.398, 87: 1.411, 88: 1.424, 89: 1.437,
    90: 1.450, 91: 1.464, 92: 1.478, 93: 1.492, 94: 1.506,
    95: 1.520, 96: 1.535, 97: 1.550, 98: 1.565, 99: 1.580,
    100: 1.595
}

# 10K Road Running Factors (Male)
WMA_10K_MALE: Dict[int, float] = {
    30: 1.000, 31: 1.003, 32: 1.006, 33: 1.009, 34: 1.012,
    35: 1.015, 36: 1.019, 37: 1.023, 38: 1.027, 39: 1.031,
    40: 1.035, 41: 1.040, 42: 1.045, 43: 1.050, 44: 1.055,
    45: 1.060, 46: 1.066, 47: 1.072, 48: 1.078, 49: 1.084,
    50: 1.090, 51: 1.097, 52: 1.104, 53: 1.111, 54: 1.118,
    55: 1.125, 56: 1.133, 57: 1.141, 58: 1.149, 59: 1.157,
    60: 1.165, 61: 1.174, 62: 1.183, 63: 1.192, 64: 1.201,
    65: 1.210, 66: 1.220, 67: 1.230, 68: 1.240, 69: 1.250,
    70: 1.260, 71: 1.271, 72: 1.282, 73: 1.293, 74: 1.304,
    75: 1.315, 76: 1.327, 77: 1.339, 78: 1.351, 79: 1.363,
    80: 1.375, 81: 1.388, 82: 1.401, 83: 1.414, 84: 1.427,
    85: 1.440, 86: 1.454, 87: 1.468, 88: 1.482, 89: 1.496,
    90: 1.510, 91: 1.525, 92: 1.540, 93: 1.555, 94: 1.570,
    95: 1.585, 96: 1.601, 97: 1.617, 98: 1.633, 99: 1.649,
    100: 1.665
}

# Half Marathon Factors (Male)
WMA_HALF_MARATHON_MALE: Dict[int, float] = {
    30: 1.000, 31: 1.004, 32: 1.008, 33: 1.012, 34: 1.016,
    35: 1.020, 36: 1.025, 37: 1.030, 38: 1.035, 39: 1.040,
    40: 1.045, 41: 1.051, 42: 1.057, 43: 1.063, 44: 1.069,
    45: 1.075, 46: 1.082, 47: 1.089, 48: 1.096, 49: 1.103,
    50: 1.110, 51: 1.118, 52: 1.126, 53: 1.134, 54: 1.142,
    55: 1.150, 56: 1.159, 57: 1.168, 58: 1.177, 59: 1.186,
    60: 1.195, 61: 1.205, 62: 1.215, 63: 1.225, 64: 1.235,
    65: 1.245, 66: 1.256, 67: 1.267, 68: 1.278, 69: 1.289,
    70: 1.300, 71: 1.312, 72: 1.324, 73: 1.336, 74: 1.348,
    75: 1.360, 76: 1.373, 77: 1.386, 78: 1.399, 79: 1.412,
    80: 1.425, 81: 1.439, 82: 1.453, 83: 1.467, 84: 1.481,
    85: 1.495, 86: 1.510, 87: 1.525, 88: 1.540, 89: 1.555,
    90: 1.570, 91: 1.586, 92: 1.602, 93: 1.618, 94: 1.634,
    95: 1.650, 96: 1.667, 97: 1.684, 98: 1.701, 99: 1.718,
    100: 1.735
}

# Marathon Factors (Male)
WMA_MARATHON_MALE: Dict[int, float] = {
    30: 1.000, 31: 1.005, 32: 1.010, 33: 1.015, 34: 1.020,
    35: 1.025, 36: 1.031, 37: 1.037, 38: 1.043, 39: 1.049,
    40: 1.055, 41: 1.062, 42: 1.069, 43: 1.076, 44: 1.083,
    45: 1.090, 46: 1.098, 47: 1.106, 48: 1.114, 49: 1.122,
    50: 1.130, 51: 1.139, 52: 1.148, 53: 1.157, 54: 1.166,
    55: 1.175, 56: 1.185, 57: 1.195, 58: 1.205, 59: 1.215,
    60: 1.225, 61: 1.236, 62: 1.247, 63: 1.258, 64: 1.269,
    65: 1.280, 66: 1.292, 67: 1.304, 68: 1.316, 69: 1.328,
    70: 1.340, 71: 1.353, 72: 1.366, 73: 1.379, 74: 1.392,
    75: 1.405, 76: 1.419, 77: 1.433, 78: 1.447, 79: 1.461,
    80: 1.475, 81: 1.490, 82: 1.505, 83: 1.520, 84: 1.535,
    85: 1.550, 86: 1.566, 87: 1.582, 88: 1.598, 89: 1.614,
    90: 1.630, 91: 1.647, 92: 1.664, 93: 1.681, 94: 1.698,
    95: 1.715, 96: 1.733, 97: 1.751, 98: 1.769, 99: 1.787,
    100: 1.805
}

# Female factors are calculated by multiplying male factors by female adjustment
# WMA standard female adjustments for road running:
FEMALE_ADJUSTMENT_5K = 1.08      # ~8% slower
FEMALE_ADJUSTMENT_10K = 1.10     # ~10% slower
FEMALE_ADJUSTMENT_HALF = 1.11    # ~11% slower
FEMALE_ADJUSTMENT_MARATHON = 1.12  # ~12% slower

# ============================================================================
# CATEGORY-BASED FACTORS (for non-standard distances)
# ============================================================================
# These are interpolated from distance-specific factors for distances
# that don't have specific WMA tables

WMA_FACTORS_MALE: Dict[str, Dict[int, float]] = {
    # Sprint distances (< 800m) - use 5K factors as approximation
    "sprint": WMA_5K_MALE,
    # Middle distances (800m - 5K) - use 5K factors
    "middle": WMA_5K_MALE,
    # Long distances (5K - Half Marathon) - interpolate between 10K and Half
    "long": {
        30: 1.000, 35: 1.017, 40: 1.040, 45: 1.067, 50: 1.100,
        55: 1.137, 60: 1.180, 65: 1.227, 70: 1.280, 75: 1.337,
        80: 1.400, 85: 1.467, 90: 1.540, 95: 1.617, 100: 1.700
    },
    # Ultra distances (Half Marathon+) - use Marathon factors
    "ultra": WMA_MARATHON_MALE
}

# ============================================================================
# WORLD RECORD PACES (30yo Open Standard) - 2023 Standards
# ============================================================================
# Based on current world records as of 2023, converted to minutes per mile

WMA_WORLD_RECORD_PACES_30YO: Dict[str, Dict[str, float]] = {
    "male": {
        "sprint": 3.43,    # 1500m world record pace (~3:26/mile)
        "middle": 3.58,    # 5K world record pace (~3:35/mile) - Joshua Cheptegei 12:35.36
        "long": 4.02,      # 10K world record pace (~4:00/mile) - Joshua Cheptegei 26:11.00
        "ultra": 4.38      # Half Marathon world record pace (~4:22/mile) - Jacob Kiplimo 57:31
    },
    "female": {
        "sprint": 3.70,    # 1500m world record pace (~3:50/mile)
        "middle": 3.87,    # 5K world record pace (~3:52/mile) - Letesenbet Gidey 14:06.62
        "long": 4.42,      # 10K world record pace (~4:25/mile) - Letesenbet Gidey 29:01.03
        "ultra": 4.86      # Half Marathon world record pace (~4:51/mile) - Letesenbet Gidey 1:02:52
    }
}

# National (US) Record Paces - typically 2-5% slower than world records
NATIONAL_WORLD_RECORD_PACES_30YO: Dict[str, Dict[str, float]] = {
    "male": {
        "sprint": 3.50,    # US 1500m record pace
        "middle": 3.65,    # US 5K record pace (~3:42/mile)
        "long": 4.10,      # US 10K record pace (~4:06/mile)
        "ultra": 4.50      # US Half Marathon record pace (~4:30/mile)
    },
    "female": {
        "sprint": 3.78,    # US 1500m record pace
        "middle": 3.95,    # US 5K record pace (~3:57/mile)
        "long": 4.52,      # US 10K record pace (~4:31/mile)
        "ultra": 4.98      # US Half Marathon record pace (~4:59/mile)
    }
}


def _get_distance_category_for_wma(distance_meters: float) -> str:
    """Helper to categorize distance for WMA factor lookup."""
    if distance_meters < 800:
        return "sprint"
    elif distance_meters < 5000:
        return "middle"
    elif distance_meters < 21097.5:  # Half marathon
        return "long"
    else:
        return "ultra"


def _interpolate_factor(age: int, age_factors: Dict[int, float]) -> float:
    """
    Interpolate age factor for exact age from WMA table.
    
    WMA tables provide factors for integer ages. For fractional ages or
    ages between table entries, we interpolate linearly.
    """
    age_points = sorted(age_factors.keys())
    
    if age <= age_points[0]:
        return age_factors[age_points[0]]
    elif age >= age_points[-1]:
        return age_factors[age_points[-1]]
    else:
        # Find the two age points that bracket this age
        for i in range(len(age_points) - 1):
            if age_points[i] <= age <= age_points[i + 1]:
                age1, age2 = age_points[i], age_points[i + 1]
                factor1 = age_factors[age1]
                factor2 = age_factors[age2]
                # Linear interpolation
                return factor1 + (factor2 - factor1) * (age - age1) / (age2 - age1)
        
        # Fallback (should not reach here)
        return age_factors[age_points[-1]]


def get_wma_age_factor(age: int, sex: Optional[str], distance_meters: float) -> Optional[float]:
    """
    Get WMA 2023 age-grading factor for a given age, sex, and distance.
    
    Uses distance-specific factors where available (5K, 10K, Half, Marathon),
    falls back to category-based factors for other distances.
    
    Args:
        age: Athlete's age (must be >= 30 for WMA factors)
        sex: 'M' or 'F' (or None, defaults to male)
        distance_meters: Distance in meters
        
    Returns:
        Age factor (multiplier) or None if calculation not possible
    """
    if age is None or age < 5:
        return None
    
    # For ages < 30, use factor of 1.0 (open standard)
    if age < 30:
        return 1.0
    
    # Cap at 100 for WMA tables
    if age > 100:
        age = 100
    
    sex_key = sex.upper() if sex and sex.upper() in ['M', 'F'] else 'M'
    is_female = sex_key == 'F'
    
    # Use distance-specific factors where available
    distance_km = distance_meters / 1000.0
    
    if abs(distance_km - 5.0) < 0.5:  # 5K (4.5-5.5km)
        age_factors = WMA_5K_MALE
        female_adj = FEMALE_ADJUSTMENT_5K
    elif abs(distance_km - 10.0) < 0.5:  # 10K (9.5-10.5km)
        age_factors = WMA_10K_MALE
        female_adj = FEMALE_ADJUSTMENT_10K
    elif abs(distance_meters - 21097.5) < 1000:  # Half Marathon (20-22km)
        age_factors = WMA_HALF_MARATHON_MALE
        female_adj = FEMALE_ADJUSTMENT_HALF
    elif abs(distance_meters - 42195) < 2000:  # Marathon (40-44km)
        age_factors = WMA_MARATHON_MALE
        female_adj = FEMALE_ADJUSTMENT_MARATHON
    else:
        # Use category-based factors
        category = _get_distance_category_for_wma(distance_meters)
        age_factors = WMA_FACTORS_MALE.get(category, WMA_FACTORS_MALE["long"])
        # Female adjustment based on category
        if category == "sprint" or category == "middle":
            female_adj = FEMALE_ADJUSTMENT_5K
        elif category == "long":
            female_adj = FEMALE_ADJUSTMENT_10K
        else:  # ultra
            female_adj = FEMALE_ADJUSTMENT_MARATHON
    
    # Get factor for exact age (with interpolation)
    factor = _interpolate_factor(age, age_factors)
    
    # Apply female adjustment if needed
    if is_female:
        factor *= female_adj
    
    return factor


def get_wma_world_record_pace(sex: Optional[str], distance_meters: float) -> Optional[float]:
    """
    Get the approximate 30-year-old world record pace for a given sex and distance (International/WMA).
    
    Based on current world records as of 2023.
    
    Args:
        sex: 'M' or 'F'
        distance_meters: Distance in meters
        
    Returns:
        World record pace in minutes per mile, or None if not available
    """
    # Convert M/F to male/female for dictionary lookup
    if sex and sex.upper() == 'F':
        sex_key = 'female'
    else:
        sex_key = 'male'
    
    distance_category = _get_distance_category_for_wma(distance_meters)
    
    paces_by_sex = WMA_WORLD_RECORD_PACES_30YO.get(sex_key)
    if not paces_by_sex:
        return None
    
    return paces_by_sex.get(distance_category)


def get_national_age_factor(age: int, sex: Optional[str], distance_meters: float) -> Optional[float]:
    """
    Get National age-grading factor for a given age, sex, and distance.
    
    For now, uses same factors as WMA (national factors are typically very similar).
    In the future, this could use country-specific factors if available.
    
    Args:
        age: Athlete's age
        sex: 'M' or 'F'
        distance_meters: Distance in meters
        
    Returns:
        Age factor (multiplier) or None if calculation not possible
    """
    # National factors are typically very similar to WMA factors
    # Use WMA factors as baseline
    return get_wma_age_factor(age, sex, distance_meters)


def get_national_world_record_pace(sex: Optional[str], distance_meters: float) -> Optional[float]:
    """
    Get the approximate 30-year-old national record pace for a given sex and distance.
    
    Based on US national records (typically 2-5% slower than world records).
    
    Args:
        sex: 'M' or 'F'
        distance_meters: Distance in meters
        
    Returns:
        National record pace in minutes per mile, or None if not available
    """
    # Convert M/F to male/female for dictionary lookup
    if sex and sex.upper() == 'F':
        sex_key = 'female'
    else:
        sex_key = 'male'
    
    distance_category = _get_distance_category_for_wma(distance_meters)
    
    paces_by_sex = NATIONAL_WORLD_RECORD_PACES_30YO.get(sex_key)
    if not paces_by_sex:
        return None
    
    return paces_by_sex.get(distance_category)


# Backward compatibility aliases
def get_world_record_pace(sex: Optional[str], distance_meters: float) -> Optional[float]:
    """Alias for get_wma_world_record_pace for backward compatibility."""
    return get_wma_world_record_pace(sex, distance_meters)


def get_distance_category(distance_meters: float) -> str:
    """Get distance category for WMA factor lookup."""
    return _get_distance_category_for_wma(distance_meters)
