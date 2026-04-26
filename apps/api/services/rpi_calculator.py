"""
Training Pace Calculator - Based on Daniels' Running Formula

RPI-to-race-time: uses published Daniels/Gilbert oxygen cost + time-to-exhaustion
equations (public research, not copyrighted).

Training paces: uses a hardcoded lookup table (_RPI_PACE_TABLE) covering RPI 20-85.
This table was DERIVED from the published equations using our own regression +
slow-runner correction. Full derivation and verification in rpi_pace_derivation.py.

CRITICAL: The _RPI_PACE_TABLE is the SINGLE SOURCE OF TRUTH for training paces.
DO NOT replace it with intensity-percentage approaches or formula-based pipelines.
Those have regressed 3+ times. The table is verified against the official Daniels
reference calculator (vdoto2.com) to +/- 1 second at all tested RPI levels.
"""
from typing import Dict, List, Optional
import math

# Training paces are derived from published Daniels/Gilbert equations (public
# research) using our own derivation (see rpi_pace_derivation.py).
# The hardcoded table (_RPI_PACE_TABLE) is the SINGLE SOURCE OF TRUTH.
# DO NOT replace with formula-based approaches — they have regressed 3+ times.
LOOKUP_AVAILABLE = False  # Legacy flag; table-based lookup always used


# Standard race distances in meters
STANDARD_DISTANCES = {
    "marathon": 42195,
    "half_marathon": 21097.5,
    "15k": 15000,
    "10k": 10000,
    "5k": 5000,
    "3mi": 4828,
    "2mi": 3218.7,
    "3200m": 3200,
    "3k": 3000,
    "1mi": 1609.34,
    "1600m": 1600,
    "1500m": 1500,
    "800m": 800,
    "400m": 400,
}


def calculate_rpi_from_race_time(distance_meters: float, time_seconds: int) -> Optional[float]:
    """
    Calculate RPI from a race time and distance.
    
    Uses lookup-based calculation with actual RPI formula for accuracy.
    Falls back to approximation if lookup service unavailable.
    
    Args:
        distance_meters: Race distance in meters
        time_seconds: Race time in seconds
        
    Returns:
        RPI score (float) or None if calculation fails
    """
    if distance_meters <= 0 or time_seconds <= 0:
        return None
    
    # Use lookup service if available (more accurate)
    if LOOKUP_AVAILABLE:
        try:
            rpi = calculate_rpi_from_race_time_lookup(distance_meters, time_seconds)  # noqa: F821
            if rpi:
                return rpi
        except Exception:
            pass  # Fall back to approximation
    
    # Fallback: Daniels' RPI formula (scientifically accurate)
    # Based on equations from Daniels' Running Formula
    time_minutes = time_seconds / 60.0
    
    if time_minutes <= 0:
        return None
    
    # Velocity in meters per minute
    velocity = distance_meters / time_minutes
    
    # Oxygen cost of running at this velocity (ml O2/kg/min)
    # VO2 = -4.6 + 0.182258*v + 0.000104*v^2
    vo2 = -4.6 + (0.182258 * velocity) + (0.000104 * velocity * velocity)
    
    # Percent of VO2max that can be sustained for the duration
    # %VO2max = 0.8 + 0.1894393*e^(-0.012778*t) + 0.2989558*e^(-0.1932605*t)
    pct_max = 0.8 + (0.1894393 * math.exp(-0.012778 * time_minutes)) + \
              (0.2989558 * math.exp(-0.1932605 * time_minutes))
    
    # RPI = VO2 / %VO2max
    if pct_max <= 0:
        return None
    
    rpi = vo2 / pct_max
    
    return round(rpi, 1)


def calculate_rpi_from_pace(pace_minutes_per_mile: float) -> Optional[float]:
    """
    Calculate RPI from a training pace (reverse calculation).
    
    Args:
        pace_minutes_per_mile: Pace in minutes per mile
        
    Returns:
        RPI score (float) or None if calculation fails
    """
    if pace_minutes_per_mile <= 0:
        return None
    
    # Approximate RPI from pace
    # This assumes the pace is approximately threshold or marathon pace
    # RPI ≈ 1000 / pace_per_mile (simplified)
    rpi = 1000 / pace_minutes_per_mile
    
    return round(rpi, 1)


# ═══════════════════════════════════════════════════════════════════════════════
# RPI TRAINING PACE TABLE — Hardcoded Lookup (DO NOT REPLACE WITH FORMULAS)
#
# Derived 2026-04-04 from first principles using published Daniels/Gilbert
# equations. Full derivation with verification in rpi_pace_derivation.py.
#
# THIS TABLE IS THE SINGLE SOURCE OF TRUTH FOR TRAINING PACES.
# DO NOT replace it with intensity percentages, curve fits, or formula-based
# approaches. Those have regressed 3+ times. The table is verified against
# the official Daniels reference calculator (vdoto2.com) to +/- 1 second.
#
# Key: RPI (integer 20-85)
# Value: (easy_fast, easy_slow, marathon, threshold, interval, repetition)
#        All values in SECONDS PER MILE.
#
# Derivation method (see rpi_pace_derivation.py for full proof):
#   1. Velocity function: v = 29.54 + 5.000663*vdot - 0.007546*vdot^2
#      (quadratic regression of exact inverse of oxygen cost equation)
#   2. Effort fractions: E=70%/62%, T=88%, I=97.5% of effective VO2max
#   3. Slow-runner correction (RPI<39): adjusted = RPI*(2/3)+13
#      Compensates for oxygen cost equation's systematic underestimation
#      at low velocities (equation was calibrated on trained runners).
#   4. Marathon pace: Newton's method on time-to-exhaustion equation
#   5. Repetition: I pace minus 24.1 sec/mi (6 sec per 400m)
#
# Verified against vdoto2.com reference at RPI 31 (10K=1:02:00):
#   E(fast) 11:14 OK, E(slow) 12:19 OK, M 10:45 +1s,
#   T 9:43 +1s, I 8:40 OK, R 8:16 OK — all within +/-1s
# ═══════════════════════════════════════════════════════════════════════════════
_RPI_PACE_TABLE = {
    20: (810, 884, 896, 752, 631, 607),
    21: (796, 869, 865, 733, 619, 595),
    22: (782, 854, 837, 714, 608, 584),
    23: (768, 839, 810, 696, 596, 572),
    24: (755, 825, 785, 680, 586, 562),
    25: (742, 812, 761, 664, 575, 551),
    26: (730, 799, 739, 649, 565, 541),
    27: (718, 786, 718, 634, 556, 532),
    28: (706, 774, 698, 620, 546, 522),
    29: (695, 762, 680, 607, 537, 513),
    30: (685, 750, 662, 595, 529, 505),
    31: (674, 739, 645, 583, 520, 496),
    32: (664, 728, 629, 571, 512, 488),
    33: (655, 718, 614, 560, 504, 480),
    34: (645, 708, 600, 549, 497, 473),
    35: (636, 698, 586, 539, 490, 466),
    36: (627, 688, 573, 529, 483, 459),
    37: (618, 679, 560, 520, 476, 452),
    38: (610, 670, 548, 511, 469, 445),
    39: (602, 661, 537, 502, 462, 438),
    40: (590, 648, 526, 492, 453, 429),
    41: (579, 636, 515, 482, 444, 420),
    42: (568, 624, 505, 473, 436, 412),
    43: (557, 613, 495, 464, 427, 403),
    44: (547, 602, 486, 456, 419, 395),
    45: (538, 592, 477, 448, 412, 388),
    46: (528, 582, 468, 440, 405, 381),
    47: (519, 572, 460, 432, 398, 374),
    48: (511, 562, 452, 425, 391, 367),
    49: (502, 553, 444, 418, 384, 360),
    50: (494, 545, 437, 411, 378, 354),
    51: (487, 536, 429, 404, 372, 348),
    52: (479, 528, 422, 398, 366, 342),
    53: (472, 520, 416, 392, 361, 337),
    54: (465, 512, 409, 386, 355, 331),
    55: (458, 505, 403, 380, 350, 326),
    56: (451, 498, 397, 375, 345, 321),
    57: (445, 491, 391, 369, 340, 316),
    58: (439, 484, 385, 364, 335, 311),
    59: (433, 477, 379, 359, 330, 306),
    60: (427, 471, 374, 354, 326, 302),
    61: (421, 465, 369, 350, 322, 298),
    62: (416, 458, 364, 345, 317, 293),
    63: (410, 453, 359, 341, 313, 289),
    64: (405, 447, 354, 336, 309, 285),
    65: (400, 441, 349, 332, 305, 281),
    66: (395, 436, 345, 328, 302, 278),
    67: (390, 431, 340, 324, 298, 274),
    68: (386, 425, 336, 320, 294, 270),
    69: (381, 420, 332, 316, 291, 267),
    70: (377, 416, 328, 313, 288, 264),
    71: (372, 411, 324, 309, 284, 260),
    72: (368, 406, 320, 305, 281, 257),
    73: (364, 402, 316, 302, 278, 254),
    74: (360, 397, 312, 299, 275, 251),
    75: (356, 393, 309, 296, 272, 248),
    76: (352, 389, 305, 292, 269, 245),
    77: (348, 385, 302, 289, 266, 242),
    78: (345, 381, 299, 286, 264, 240),
    79: (341, 377, 295, 283, 261, 237),
    80: (338, 373, 292, 281, 258, 234),
    81: (334, 369, 289, 278, 256, 232),
    82: (331, 365, 286, 275, 253, 229),
    83: (328, 362, 283, 272, 251, 227),
    84: (325, 358, 280, 270, 249, 225),
    85: (321, 355, 277, 267, 246, 222),
}


def _interpolate_pace(rpi: float, idx: int) -> int:
    """Linearly interpolate a pace from the RPI table for fractional RPIs."""
    rpis = sorted(_RPI_PACE_TABLE.keys())
    clamped = max(rpis[0], min(rpis[-1], rpi))
    lo = int(clamped)
    if lo >= rpis[-1]:
        return _RPI_PACE_TABLE[rpis[-1]][idx]
    if lo < rpis[0]:
        return _RPI_PACE_TABLE[rpis[0]][idx]
    hi = lo + 1
    if hi > rpis[-1]:
        return _RPI_PACE_TABLE[lo][idx]
    frac = clamped - lo
    v_lo = _RPI_PACE_TABLE[lo][idx]
    v_hi = _RPI_PACE_TABLE[hi][idx]
    return int(round(v_lo + frac * (v_hi - v_lo)))


def _secs_to_pace_dict(pace_seconds: int) -> Dict[str, Optional[str]]:
    """Format pace seconds as {mi: "M:SS", km: "M:SS"}."""
    if pace_seconds <= 0:
        return {"mi": None, "km": None}
    minutes = pace_seconds // 60
    seconds = pace_seconds % 60
    pace_mi = f"{minutes}:{seconds:02d}"
    km_secs = int(pace_seconds / 1.60934)
    km_m = km_secs // 60
    km_s = km_secs % 60
    pace_km = f"{km_m}:{km_s:02d}"
    return {"mi": pace_mi, "km": pace_km}


def _secs_to_easy_dict(pace_seconds: int) -> Dict[str, Optional[str]]:
    """Format easy pace as {mi, km, display_mi, display_km}."""
    base = _secs_to_pace_dict(pace_seconds)
    if base["mi"]:
        base["display_mi"] = f"{base['mi']} or slower"
        base["display_km"] = f"{base['km']} or slower"
    return base


def calculate_training_paces(rpi: float) -> Dict:
    """
    Calculate all training paces from RPI using the hardcoded lookup table.

    The table was derived from first principles (Daniels/Gilbert published
    equations) and verified against the official reference calculator.
    See rpi_pace_derivation.py for the full derivation and proof.

    DO NOT replace this with formula-based approaches. They have regressed
    3+ times. The table is the single source of truth.
    """
    if rpi is None or rpi <= 0:
        return {
            "easy": {"mi": None, "km": None},
            "marathon": {"mi": None, "km": None},
            "threshold": {"mi": None, "km": None},
            "interval": {"mi": None, "km": None},
            "repetition": {"mi": None, "km": None},
            "fast_reps": {"mi": None, "km": None},
        }

    easy_fast_sec = _interpolate_pace(rpi, 0)
    easy_slow_sec = _interpolate_pace(rpi, 1)
    marathon_sec  = _interpolate_pace(rpi, 2)
    threshold_sec = _interpolate_pace(rpi, 3)
    interval_sec  = _interpolate_pace(rpi, 4)
    rep_sec       = _interpolate_pace(rpi, 5)
    fast_reps_sec = max(rep_sec - 10, 180)

    return {
        "easy": _secs_to_easy_dict(easy_fast_sec),
        "marathon": _secs_to_pace_dict(marathon_sec),
        "threshold": _secs_to_pace_dict(threshold_sec),
        "interval": _secs_to_pace_dict(interval_sec),
        "repetition": _secs_to_pace_dict(rep_sec),
        "fast_reps": _secs_to_pace_dict(fast_reps_sec),
        "easy_pace_low": easy_fast_sec,
        "easy_pace_high": easy_slow_sec,
        "marathon_pace": marathon_sec,
        "threshold_pace": threshold_sec,
        "interval_pace": interval_sec,
        "repetition_pace": rep_sec,
    }


def _calculate_rpi_for_time(distance_meters: float, time_seconds: float) -> float:
    """
    Calculate RPI for a given distance and time using Daniels formula.
    
    RPI = (-4.60 + 0.182258*V + 0.000104*V²) / (0.8 + 0.1894393*e^(-0.012778*T) + 0.2989558*e^(-0.1932605*T))
    
    Where V = velocity in m/min, T = time in minutes
    """
    import math
    
    velocity_m_per_min = (distance_meters / time_seconds) * 60
    time_minutes = time_seconds / 60.0
    
    numerator = -4.60 + 0.182258 * velocity_m_per_min + 0.000104 * (velocity_m_per_min ** 2)
    
    exp1 = math.exp(-0.012778 * time_minutes)
    exp2 = math.exp(-0.1932605 * time_minutes)
    denominator = 0.8 + 0.1894393 * exp1 + 0.2989558 * exp2
    
    if denominator == 0:
        return 0
    
    return numerator / denominator


def calculate_equivalent_race_time(rpi: float, target_distance_meters: float) -> Optional[Dict]:
    """
    Calculate equivalent race time for a target distance based on RPI/RPI.
    
    Uses binary search to find the time that produces the target RPI
    for the given distance using the Daniels formula.
    
    Args:
        rpi: RPI/RPI score
        target_distance_meters: Target race distance in meters
        
    Returns:
        Dictionary with equivalent time and pace, or None if calculation fails
    """
    if rpi <= 0 or target_distance_meters <= 0:
        return None
    
    # Use binary search to find the time that gives us this RPI
    # Start with reasonable bounds based on world records and slow joggers
    
    # Estimate initial bounds based on distance
    # World record pace is about 2.8 min/km for short, 3.0 for marathon
    # Slow joggers might be 10+ min/km
    min_pace_per_km = 2.5  # Elite (minutes)
    max_pace_per_km = 12.0  # Very slow (minutes)
    
    distance_km = target_distance_meters / 1000.0
    
    min_time_seconds = min_pace_per_km * 60 * distance_km
    max_time_seconds = max_pace_per_km * 60 * distance_km
    
    # Binary search for the correct time
    tolerance = 0.01  # RPI tolerance
    max_iterations = 50
    
    for _ in range(max_iterations):
        mid_time = (min_time_seconds + max_time_seconds) / 2
        calculated_rpi = _calculate_rpi_for_time(target_distance_meters, mid_time)
        
        if abs(calculated_rpi - rpi) < tolerance:
            time_seconds = mid_time
            break
        
        # Higher RPI = faster time, so if calculated > target, we need slower time
        if calculated_rpi > rpi:
            min_time_seconds = mid_time  # Need slower (longer) time
        else:
            max_time_seconds = mid_time  # Need faster (shorter) time
    else:
        # Use the best approximation we found
        time_seconds = (min_time_seconds + max_time_seconds) / 2
    
    time_seconds = int(round(time_seconds))
    
    # Format time
    hours = time_seconds // 3600
    minutes = (time_seconds % 3600) // 60
    secs = time_seconds % 60
    
    if hours > 0:
        time_formatted = f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        time_formatted = f"{minutes}:{secs:02d}"
    
    # Calculate pace
    pace_seconds_per_mile = (time_seconds / target_distance_meters) * 1609.34
    pace_mins = int(pace_seconds_per_mile // 60)
    pace_secs = int(pace_seconds_per_mile % 60)
    pace_mi = f"{pace_mins}:{pace_secs:02d}"
    
    pace_km_seconds = time_seconds / (target_distance_meters / 1000)
    pace_km_mins = int(pace_km_seconds // 60)
    pace_km_secs = int(pace_km_seconds % 60)
    pace_km = f"{pace_km_mins}:{pace_km_secs:02d}"
    
    return {
        "distance_m": target_distance_meters,
        "distance_name": _get_distance_name(target_distance_meters),
        "time_seconds": time_seconds,
        "time_formatted": time_formatted,
        "pace_mi": pace_mi,
        "pace_km": pace_km,
    }


def calculate_race_time_from_rpi(rpi: float, distance_meters: float) -> Optional[int]:
    """
    Calculate race time in seconds from RPI and distance.
    
    Simple wrapper around calculate_equivalent_race_time that returns just the time.
    
    Args:
        rpi: RPI/RPI score
        distance_meters: Race distance in meters
        
    Returns:
        Time in seconds, or None if calculation fails
    """
    result = calculate_equivalent_race_time(rpi, distance_meters)
    if result is None:
        return None
    return result.get("time_seconds")


def _old_calculate_equivalent_race_time_fallback(rpi: float, target_distance_meters: float) -> Optional[Dict]:
    """DEPRECATED - Old fallback code kept for reference."""
    # Simple fallback: Approximation
    vo2max_pace_per_mile = (1000 / rpi) * 0.98
    
    # For equivalent race performance, use approximately 95-98% of VO2max pace
    # (varies by distance - shorter = faster, longer = slower)
    target_distance_miles = target_distance_meters / 1609.34
    
    if target_distance_miles <= 1.0:  # Mile or shorter
        race_pace_factor = 0.95  # Faster pace for shorter races
    elif target_distance_miles <= 3.1:  # 5K
        race_pace_factor = 0.96
    elif target_distance_miles <= 6.2:  # 10K
        race_pace_factor = 0.97
    elif target_distance_miles <= 13.1:  # Half Marathon
        race_pace_factor = 0.98
    else:  # Marathon
        race_pace_factor = 0.99
    
    race_pace_per_mile = vo2max_pace_per_mile / race_pace_factor
    time_minutes = race_pace_per_mile * target_distance_miles
    time_seconds = int(time_minutes * 60)
    
    # Format time
    hours = time_seconds // 3600
    minutes = (time_seconds % 3600) // 60
    seconds = time_seconds % 60
    
    if hours > 0:
        time_formatted = f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        time_formatted = f"{minutes}:{seconds:02d}"
    
    # Format pace
    pace_minutes = int(race_pace_per_mile)
    pace_seconds = int((race_pace_per_mile - pace_minutes) * 60)
    pace_mi = f"{pace_minutes}:{pace_seconds:02d}"
    
    pace_per_km = race_pace_per_mile / 1.60934
    pace_minutes_km = int(pace_per_km)
    pace_seconds_km = int((pace_per_km - pace_minutes_km) * 60)
    pace_km = f"{pace_minutes_km}:{pace_seconds_km:02d}"
    
    return {
        "distance_m": target_distance_meters,
        "distance_name": _get_distance_name(target_distance_meters),
        "time_seconds": time_seconds,
        "time_formatted": time_formatted,
        "pace_mi": pace_mi,
        "pace_km": pace_km,
    }


def calculate_all_equivalent_races(rpi: float) -> List[Dict]:
    """
    Calculate equivalent race times for all standard distances.
    
    Args:
        rpi: RPI score
        
    Returns:
        List of equivalent race performances
    """
    equivalent_races = []
    
    # Standard distances to calculate
    distances_to_calc = [
        ("marathon", 42195),
        ("half_marathon", 21097.5),
        ("15k", 15000),
        ("10k", 10000),
        ("5k", 5000),
        ("3mi", 4828),
        ("2mi", 3218.7),
        ("3200m", 3200),
        ("3k", 3000),
        ("1mi", 1609.34),
        ("1600m", 1600),
        ("1500m", 1500),
    ]
    
    for name, distance_m in distances_to_calc:
        equivalent = calculate_equivalent_race_time(rpi, distance_m)
        if equivalent:
            equivalent_races.append(equivalent)
    
    return equivalent_races


def _get_distance_name(distance_meters: float) -> str:
    """Get human-readable distance name."""
    distance_map = {
        42195: "Marathon",
        21097.5: "Half Marathon",
        15000: "15K",
        10000: "10K",
        5000: "5K",
        4828: "3 Mile",
        3218.7: "2 Mile",
        3200: "3200m",
        3000: "3K",
        1609.34: "1 Mile",
        1600: "1600m",
        1500: "1500m",
    }
    
    # Find closest match
    for dist, name in distance_map.items():
        if abs(distance_meters - dist) < 100:  # Within 100m
            return name
    
    # Fallback
    if distance_meters >= 1000:
        return f"{distance_meters / 1000:.1f}K"
    else:
        return f"{int(distance_meters)}m"


def calculate_rpi_comprehensive(distance_meters: Optional[float] = None, 
                                  time_seconds: Optional[int] = None,
                                  pace_minutes_per_mile: Optional[float] = None) -> Dict:
    """
    Comprehensive RPI calculator with training paces and equivalent races.
    
    Can calculate from:
    - Race time and distance
    - Or from pace (reverse calculation)
    
    Args:
        distance_meters: Race distance in meters (if calculating from race)
        time_seconds: Race time in seconds (if calculating from race)
        pace_minutes_per_mile: Pace in minutes per mile (if reverse calculation)
        
    Returns:
        Comprehensive dictionary with RPI, training paces, and equivalent races
    """
    # Calculate RPI
    if distance_meters and time_seconds:
        rpi = calculate_rpi_from_race_time(distance_meters, time_seconds)
        input_type = "race_time"
    elif pace_minutes_per_mile:
        rpi = calculate_rpi_from_pace(pace_minutes_per_mile)
        input_type = "pace"
    else:
        return {
            "error": "Must provide either (distance_meters + time_seconds) or pace_minutes_per_mile"
        }
    
    if rpi is None:
        return {
            "error": "Invalid input: could not calculate RPI"
        }
    
    # Calculate training paces
    training_paces = calculate_training_paces(rpi)
    
    # Calculate equivalent race performances
    equivalent_races = calculate_all_equivalent_races(rpi)
    
    result = {
        "rpi": rpi,
        "input_type": input_type,
        "training_paces": training_paces,
        "equivalent_races": equivalent_races,
    }
    
    # Add input details if from race time
    if input_type == "race_time":
        result["race_distance_m"] = distance_meters
        result["race_time_seconds"] = time_seconds
        
        # Format race time
        hours = time_seconds // 3600
        minutes = (time_seconds % 3600) // 60
        seconds = time_seconds % 60
        if hours > 0:
            result["race_time_formatted"] = f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            result["race_time_formatted"] = f"{minutes}:{seconds:02d}"
    
    return result
