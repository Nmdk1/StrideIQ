"""
Alan Jones 2025 Road Running Age-Grading Factors

Official source: https://github.com/AlanLyttonJones/Age-Grade-Tables
Approved by USATF Masters Long Distance Running Council on 2025-01-10

These are TIME MULTIPLIERS (1 / performance_factor).
To get age-graded time: actual_time / time_multiplier
To get age standard: open_standard * time_multiplier

The factors are provided per-year (not 5-year groups).
"""

from typing import Dict

# 5K Male Road Running - Time Multipliers (1 / WMA performance factor)
# Source: MaleRoadStd2025.xlsx "Age Factors" sheet, column "5 km"
ALAN_JONES_5K_MALE: Dict[int, float] = {
    5: 2.2664,
    6: 1.9685,
    7: 1.7537,
    8: 1.5926,
    9: 1.4680,
    10: 1.3697,
    11: 1.2912,
    12: 1.2277,
    13: 1.1765,
    14: 1.1350,
    15: 1.1015,
    16: 1.0753,
    17: 1.0526,
    18: 1.0331,
    19: 1.0183,
    20: 1.0081,
    21: 1.0019,
    22: 1.0000,
    23: 1.0000,
    24: 1.0000,
    25: 1.0000,
    26: 1.0000,
    27: 1.0000,
    28: 1.0000,
    29: 1.0000,
    30: 1.0023,
    31: 1.0088,
    32: 1.0158,
    33: 1.0231,
    34: 1.0304,
    35: 1.0378,
    36: 1.0454,
    37: 1.0530,
    38: 1.0608,
    39: 1.0686,
    40: 1.0765,
    41: 1.0847,
    42: 1.0929,
    43: 1.1013,
    44: 1.1098,
    45: 1.1183,
    46: 1.1271,
    47: 1.1360,
    48: 1.1451,
    49: 1.1542,
    50: 1.1635,
    51: 1.1730,
    52: 1.1826,
    53: 1.1925,
    54: 1.2024,
    55: 1.2124,
    56: 1.2228,
    57: 1.2332,
    58: 1.2439,
    59: 1.2547,
    60: 1.2657,
    61: 1.2770,
    62: 1.2883,
    63: 1.3001,
    64: 1.3118,
    65: 1.3238,
    66: 1.3362,
    67: 1.3486,
    68: 1.3615,
    69: 1.3748,
    70: 1.3897,
    71: 1.4063,
    72: 1.4247,
    73: 1.4451,
    74: 1.4676,
    75: 1.4923,
    76: 1.5195,
    77: 1.5494,
    78: 1.5823,
    79: 1.6184,
    80: 1.6581,
    81: 1.7018,
    82: 1.7501,
    83: 1.8034,
    84: 1.8625,
    85: 1.9283,
    86: 2.0012,
    87: 2.0833,
    88: 2.1758,
    89: 2.2805,
    90: 2.3992,
    91: 2.5361,
    92: 2.6947,
    93: 2.8794,
    94: 3.0989,
    95: 3.3625,
    96: 3.6832,
    97: 4.0850,
    98: 4.5977,
    99: 5.2798,
    100: 6.2228,
}


def get_alan_jones_factor(age: int, sex: str, distance_meters: float) -> float:
    """
    Get the Alan Jones 2025 age factor for a given age, sex, and distance.
    
    Args:
        age: Athlete's age (5-100)
        sex: 'M' or 'F'
        distance_meters: Distance in meters (currently only 5K supported with exact factors)
    
    Returns:
        Time multiplier (factor to multiply open standard to get age standard)
    """
    # Clamp age to valid range
    age = max(5, min(100, age))
    
    # Currently only have exact 5K factors
    # For 5K, use exact per-year factors
    if abs(distance_meters - 5000) < 500:
        if sex.upper() == 'M':
            return ALAN_JONES_5K_MALE.get(age, 1.0)
        else:
            # Female factors not yet extracted - use male with adjustment
            male_factor = ALAN_JONES_5K_MALE.get(age, 1.0)
            # Approximate female adjustment (typically ~8% higher time multiplier)
            return male_factor * 1.08
    
    # For other distances, fall back to interpolation
    # This is a placeholder - should extract actual factors for each distance
    return ALAN_JONES_5K_MALE.get(age, 1.0)
