"""
Age Grading Service

Normalizes performance data across ages and genders using WMA standards.
This is CRITICAL for comparing recreational athletes fairly.

A 45-year-old running 3:30 marathon is NOT the same as a 25-year-old
running 3:30 - the 45-year-old is relatively much faster.

Age-grading allows us to:
- Compare athletes fairly regardless of age
- Track TRUE improvement over time (not just raw times)
- Identify who is actually performing well vs who is just young
- Build "people like you" baselines that are meaningful
"""

from typing import Optional, Tuple, Dict
from dataclasses import dataclass
import math


@dataclass
class AgeGradedResult:
    """Result of age-grading a performance"""
    raw_time_seconds: float
    age_graded_time_seconds: float
    age_grade_percentage: float  # 0-100+, higher = better (vs WORLD record)
    us_age_grade_percentage: Optional[float]  # vs US record for age group
    age_factor: float  # Multiplier applied
    world_record_seconds: float  # Open world record for reference
    us_record_seconds: Optional[float]  # US age-group record for reference
    age: int
    sex: str
    distance_meters: float


# WMA Age Grading Factors (simplified - full tables have 1-year increments)
# These are approximate factors for key age brackets
# Factor = how much slower expected at this age vs peak (1.0 = peak)

AGE_FACTORS_MALE = {
    # Age: (5K factor, 10K factor, Half factor, Marathon factor)
    18: (1.000, 1.000, 1.000, 1.000),
    20: (1.000, 1.000, 1.000, 1.000),
    25: (1.000, 1.000, 1.000, 1.000),
    30: (1.003, 1.003, 1.004, 1.005),
    35: (1.022, 1.023, 1.026, 1.030),
    40: (1.050, 1.052, 1.058, 1.065),
    45: (1.086, 1.090, 1.100, 1.112),
    50: (1.131, 1.137, 1.152, 1.170),
    55: (1.186, 1.195, 1.217, 1.242),
    60: (1.253, 1.267, 1.298, 1.332),
    65: (1.336, 1.356, 1.400, 1.448),
    70: (1.438, 1.467, 1.530, 1.597),
    75: (1.566, 1.607, 1.697, 1.792),
    80: (1.728, 1.787, 1.915, 2.052),
    85: (1.938, 2.023, 2.208, 2.410),
    90: (2.217, 2.342, 2.615, 2.920),
}

AGE_FACTORS_FEMALE = {
    # Age: (5K factor, 10K factor, Half factor, Marathon factor)
    18: (1.000, 1.000, 1.000, 1.000),
    20: (1.000, 1.000, 1.000, 1.000),
    25: (1.000, 1.000, 1.000, 1.000),
    30: (1.003, 1.003, 1.004, 1.005),
    35: (1.020, 1.021, 1.024, 1.028),
    40: (1.045, 1.048, 1.054, 1.062),
    45: (1.079, 1.084, 1.095, 1.108),
    50: (1.122, 1.130, 1.148, 1.168),
    55: (1.177, 1.189, 1.216, 1.246),
    60: (1.247, 1.265, 1.305, 1.349),
    65: (1.336, 1.363, 1.422, 1.488),
    70: (1.450, 1.490, 1.577, 1.673),
    75: (1.599, 1.658, 1.787, 1.929),
    80: (1.796, 1.886, 2.080, 2.296),
    85: (2.062, 2.201, 2.498, 2.835),
    90: (2.429, 2.649, 3.113, 3.658),
}

# World Records (Open - for age-grade % calculation)
WORLD_RECORDS_MALE = {
    5000: 12 * 60 + 35,      # 12:35 (Joshua Cheptegei)
    10000: 26 * 60 + 11,     # 26:11 (Joshua Cheptegei)
    21097: 57 * 60 + 31,     # 57:31 (Jacob Kiplimo)
    42195: 2 * 3600 + 35,    # 2:00:35 (Kelvin Kiptum)
}

WORLD_RECORDS_FEMALE = {
    5000: 14 * 60 + 0,       # 14:00 (Gudaf Tsegay)
    10000: 28 * 60 + 54,     # 28:54 (Letesenbet Gidey)
    21097: 63 * 60 + 44,     # 1:03:44 (Letesenbet Gidey)
    42195: 2 * 3600 + 9 * 60 + 56,  # 2:09:56 (Tigst Assefa)
}

# US Records (Open - for national-level age-grade %)
US_RECORDS_MALE = {
    5000: 12 * 60 + 51,      # 12:51 (Grant Fisher)
    10000: 26 * 60 + 33,     # 26:33 (Grant Fisher)
    21097: 59 * 60 + 36,     # 59:36 (Conner Mantz)
    42195: 2 * 3600 + 4 * 60 + 38,  # 2:04:38 (Khalid Khannouchi - still stands!)
}

US_RECORDS_FEMALE = {
    5000: 14 * 60 + 12,      # 14:12 (Elle St. Pierre)
    10000: 29 * 60 + 56,     # 29:56 (Emily Sisson)
    21097: 64 * 60 + 2,      # 1:04:02 (Emily Sisson)
    42195: 2 * 3600 + 18 * 60 + 29,  # 2:18:29 (Emily Sisson)
}

# ============ US MASTERS AGE GROUP RECORDS ============
# These allow for national-level age-grading
# Source: USATF + various masters associations

US_MASTERS_RECORDS_MALE = {
    # Format: age_group: {distance_m: time_seconds}
    40: {
        5000: 13 * 60 + 38,      # 13:38 (Bernard Lagat)
        10000: 28 * 60 + 0,      # 28:00 (Abdi Abdirahman)
        21097: 61 * 60 + 18,     # 1:01:18
        42195: 2 * 3600 + 8 * 60 + 24,  # 2:08:24 (Meb Keflezighi)
    },
    45: {
        5000: 14 * 60 + 44,      # 14:44
        10000: 30 * 60 + 18,     # 30:18
        21097: 66 * 60 + 52,     # 1:06:52
        42195: 2 * 3600 + 19 * 60 + 29,  # 2:19:29
    },
    50: {
        5000: 15 * 60 + 9,       # 15:09 (Tommy Hughes)
        10000: 31 * 60 + 18,     # 31:18
        21097: 69 * 60 + 0,      # 1:09:00
        42195: 2 * 3600 + 26 * 60 + 22,  # 2:26:22
    },
    55: {
        5000: 16 * 60 + 4,       # 16:04
        10000: 33 * 60 + 1,      # 33:01 (Norm Green)
        21097: 73 * 60 + 40,     # 1:13:40
        42195: 2 * 3600 + 38 * 60 + 15,  # 2:38:15
    },
    60: {
        5000: 16 * 60 + 59,      # 16:59
        10000: 35 * 60 + 15,     # 35:15
        21097: 78 * 60 + 10,     # 1:18:10
        42195: 2 * 3600 + 49 * 60 + 47,  # 2:49:47
    },
    65: {
        5000: 17 * 60 + 56,      # 17:56
        10000: 37 * 60 + 32,     # 37:32
        21097: 82 * 60 + 30,     # 1:22:30
        42195: 2 * 3600 + 58 * 60 + 48,  # 2:58:48
    },
    70: {
        5000: 19 * 60 + 16,      # 19:16
        10000: 40 * 60 + 18,     # 40:18
        21097: 88 * 60 + 54,     # 1:28:54
        42195: 3 * 3600 + 13 * 60 + 44,  # 3:13:44
    },
    75: {
        5000: 21 * 60 + 6,       # 21:06
        10000: 44 * 60 + 26,     # 44:26
        21097: 98 * 60 + 12,     # 1:38:12
        42195: 3 * 3600 + 33 * 60 + 50,  # 3:33:50
    },
    80: {
        5000: 23 * 60 + 43,      # 23:43
        10000: 50 * 60 + 20,     # 50:20
        21097: 112 * 60 + 0,     # 1:52:00
        42195: 4 * 3600 + 5 * 60 + 15,   # 4:05:15
    },
}

US_MASTERS_RECORDS_FEMALE = {
    40: {
        5000: 15 * 60 + 19,      # 15:19 (Jen Rhines)
        10000: 31 * 60 + 32,     # 31:32
        21097: 68 * 60 + 50,     # 1:08:50
        42195: 2 * 3600 + 28 * 60 + 40,  # 2:28:40
    },
    45: {
        5000: 16 * 60 + 3,       # 16:03
        10000: 33 * 60 + 10,     # 33:10
        21097: 73 * 60 + 30,     # 1:13:30
        42195: 2 * 3600 + 37 * 60 + 6,   # 2:37:06
    },
    50: {
        5000: 17 * 60 + 7,       # 17:07
        10000: 35 * 60 + 30,     # 35:30
        21097: 77 * 60 + 45,     # 1:17:45
        42195: 2 * 3600 + 49 * 60 + 57,  # 2:49:57
    },
    55: {
        5000: 18 * 60 + 22,      # 18:22
        10000: 38 * 60 + 0,      # 38:00
        21097: 83 * 60 + 24,     # 1:23:24
        42195: 3 * 3600 + 2 * 60 + 0,    # 3:02:00
    },
    60: {
        5000: 19 * 60 + 28,      # 19:28
        10000: 40 * 60 + 44,     # 40:44
        21097: 89 * 60 + 42,     # 1:29:42
        42195: 3 * 3600 + 17 * 60 + 30,  # 3:17:30
    },
    65: {
        5000: 20 * 60 + 48,      # 20:48
        10000: 43 * 60 + 29,     # 43:29
        21097: 95 * 60 + 48,     # 1:35:48
        42195: 3 * 3600 + 31 * 60 + 26,  # 3:31:26
    },
    70: {
        5000: 22 * 60 + 29,      # 22:29
        10000: 47 * 60 + 15,     # 47:15
        21097: 104 * 60 + 0,     # 1:44:00
        42195: 3 * 3600 + 52 * 60 + 32,  # 3:52:32
    },
    75: {
        5000: 22 * 60 + 41,      # 22:41 (Jeannie Rice - world record!)
        10000: 50 * 60 + 14,     # 50:14
        21097: 110 * 60 + 18,    # 1:50:18
        42195: 4 * 3600 + 4 * 60 + 23,   # 4:04:23
    },
    80: {
        5000: 25 * 60 + 44,      # 25:44
        10000: 55 * 60 + 0,      # 55:00
        21097: 122 * 60 + 30,    # 2:02:30
        42195: 4 * 3600 + 34 * 60 + 38,  # 4:34:38
    },
}


def get_age_factor(age: int, sex: str, distance_meters: float) -> float:
    """
    Get the age-grading factor for a given age, sex, and distance.
    
    Returns a multiplier (1.0 at peak age, higher as you get older/younger).
    """
    factors = AGE_FACTORS_MALE if sex.upper() in ('M', 'MALE') else AGE_FACTORS_FEMALE
    
    # Determine distance index
    if distance_meters <= 6000:
        dist_idx = 0  # 5K
    elif distance_meters <= 12000:
        dist_idx = 1  # 10K
    elif distance_meters <= 25000:
        dist_idx = 2  # Half
    else:
        dist_idx = 3  # Marathon
    
    # Find bracketing ages and interpolate
    ages = sorted(factors.keys())
    
    if age <= ages[0]:
        return factors[ages[0]][dist_idx]
    if age >= ages[-1]:
        return factors[ages[-1]][dist_idx]
    
    # Find bracket
    for i, bracket_age in enumerate(ages):
        if bracket_age >= age:
            lower_age = ages[i-1]
            upper_age = bracket_age
            lower_factor = factors[lower_age][dist_idx]
            upper_factor = factors[upper_age][dist_idx]
            
            # Linear interpolation
            ratio = (age - lower_age) / (upper_age - lower_age)
            return lower_factor + ratio * (upper_factor - lower_factor)
    
    return 1.0


def get_world_record(sex: str, distance_meters: float) -> float:
    """Get approximate world record for distance and sex."""
    records = WORLD_RECORDS_MALE if sex.upper() in ('M', 'MALE') else WORLD_RECORDS_FEMALE
    
    # Find closest distance
    closest_dist = min(records.keys(), key=lambda d: abs(d - distance_meters))
    base_record = records[closest_dist]
    
    # Scale linearly for different distances (rough approximation)
    if distance_meters != closest_dist:
        scale = distance_meters / closest_dist
        # Not quite linear - longer races are proportionally slower
        return base_record * scale * (1 + 0.02 * math.log(scale) if scale > 1 else 1)
    
    return base_record


def get_us_age_group_record(age: int, sex: str, distance_meters: float) -> Optional[float]:
    """
    Get US age-group record for distance, sex, and age.
    
    Returns None if no record available for this age group.
    """
    records = US_MASTERS_RECORDS_MALE if sex.upper() in ('M', 'MALE') else US_MASTERS_RECORDS_FEMALE
    
    # Find the age group (round down to nearest 5-year bracket)
    age_group = (age // 5) * 5
    if age_group < 40:
        # Use open US record for under-40
        open_records = US_RECORDS_MALE if sex.upper() in ('M', 'MALE') else US_RECORDS_FEMALE
        closest_dist = min(open_records.keys(), key=lambda d: abs(d - distance_meters))
        return open_records.get(closest_dist)
    
    if age_group not in records:
        # Find closest available age group
        available = sorted(records.keys())
        if age_group < available[0]:
            age_group = available[0]
        elif age_group > available[-1]:
            age_group = available[-1]
        else:
            age_group = min(available, key=lambda a: abs(a - age_group))
    
    if age_group not in records:
        return None
    
    age_records = records[age_group]
    
    # Find closest distance
    closest_dist = min(age_records.keys(), key=lambda d: abs(d - distance_meters))
    
    # Only return if distance is close enough (within 20%)
    if abs(closest_dist - distance_meters) / distance_meters > 0.2:
        return None
    
    return age_records.get(closest_dist)


def age_grade_performance(
    time_seconds: float,
    distance_meters: float,
    age: int,
    sex: str
) -> AgeGradedResult:
    """
    Age-grade a running performance.
    
    Returns an AgeGradedResult with:
    - age_graded_time: What time this is equivalent to at peak age
    - age_grade_percentage: Performance as % of age-adjusted WORLD record
    - us_age_grade_percentage: Performance as % of US age-group record
    
    Example:
    - 45-year-old male runs 3:30 marathon (12,600 seconds)
    - Age factor ~1.112
    - Age-graded time = 12,600 / 1.112 = 11,331 seconds (3:08:51)
    - World age-grade: ~59% (vs Kipchoge's WR adjusted for age)
    - US age-grade: ~66% (vs US M45 record of 2:19:29)
    """
    age_factor = get_age_factor(age, sex, distance_meters)
    world_record = get_world_record(sex, distance_meters)
    
    # Age-graded time (what it would be at peak age)
    age_graded_time = time_seconds / age_factor
    
    # World age-grade percentage (how close to age-adjusted WR)
    # Higher = better, 100% = world record pace for your age
    age_grade_pct = (world_record * age_factor / time_seconds) * 100
    
    # US age-grade percentage (how close to US record for your age group)
    us_record = get_us_age_group_record(age, sex, distance_meters)
    us_age_grade_pct = None
    if us_record:
        us_age_grade_pct = (us_record / time_seconds) * 100
    
    return AgeGradedResult(
        raw_time_seconds=time_seconds,
        age_graded_time_seconds=age_graded_time,
        age_grade_percentage=age_grade_pct,
        us_age_grade_percentage=us_age_grade_pct,
        age_factor=age_factor,
        world_record_seconds=world_record,
        us_record_seconds=us_record,
        age=age,
        sex=sex,
        distance_meters=distance_meters
    )


def classify_performance_level(age_grade_pct: float) -> Tuple[str, str]:
    """
    Classify a performance level based on age-grade percentage.
    
    Returns (level, description).
    
    This is for RECREATIONAL athletes - not elites.
    """
    if age_grade_pct >= 90:
        return "elite", "World-class masters performance"
    elif age_grade_pct >= 80:
        return "national", "National-level age-group competitor"
    elif age_grade_pct >= 70:
        return "regional", "Regional competitive - top of local races"
    elif age_grade_pct >= 60:
        return "local_competitive", "Local competitive - solid club runner"
    elif age_grade_pct >= 50:
        return "recreational_fast", "Fast recreational - mid-pack at races"
    elif age_grade_pct >= 40:
        return "recreational", "Recreational runner - back of pack at races"
    else:
        return "beginner", "Building fitness"


def estimate_equivalent_time(
    known_time_seconds: float,
    known_distance_meters: float,
    target_distance_meters: float,
    age: int,
    sex: str
) -> float:
    """
    Estimate equivalent time at a different distance.
    
    Uses Riegel's formula with age-grading adjustments.
    """
    # Riegel's formula: T2 = T1 * (D2/D1)^1.06
    # The 1.06 exponent accounts for fatigue at longer distances
    
    # Adjust exponent slightly by age (older runners fatigue more)
    fatigue_exponent = 1.06 + (max(0, age - 40) * 0.002)
    
    ratio = target_distance_meters / known_distance_meters
    estimated_time = known_time_seconds * (ratio ** fatigue_exponent)
    
    return estimated_time


# ============ Population Percentile Functions ============

# These will be populated from research data
# For now, using approximate distributions from running literature

def get_population_percentile_by_age_grade(
    age_grade_pct: float,
    runner_type: str = "recreational"
) -> float:
    """
    Get percentile rank among runners of similar type.
    
    runner_type: "recreational", "competitive", "all"
    
    Based on research showing age-grade distributions.
    """
    # Approximate percentiles for recreational runners
    # Data suggests recreational runners cluster around 40-55% age-grade
    
    if runner_type == "recreational":
        # Mean ~47%, SD ~10%
        mean = 47
        sd = 10
    elif runner_type == "competitive":
        # Mean ~62%, SD ~8%
        mean = 62
        sd = 8
    else:
        # All runners
        mean = 52
        sd = 12
    
    # Convert to percentile using normal distribution approximation
    z_score = (age_grade_pct - mean) / sd
    
    # Approximate CDF of standard normal
    percentile = 0.5 * (1 + math.erf(z_score / math.sqrt(2))) * 100
    
    return max(0, min(100, percentile))

