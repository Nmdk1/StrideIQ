"""
Training Pace Calculator - Based on Daniels' Running Formula

Comprehensive calculator for fitness scores, training paces, and equivalent race performances.
Based on publicly available formulas from Dr. Jack Daniels' research in "Daniels' Running Formula."

Uses lookup-based system for accurate calculations.
This implementation uses mathematical formulas and methodology from Dr. Daniels' work.
Not affiliated with VDOT O2 or The Run SMART Project.
"""
from typing import Dict, List, Optional, Tuple
import math

# Import lookup service for accurate calculations
try:
    from services.vdot_lookup import (
        calculate_vdot_from_race_time_lookup,
        get_training_paces_from_vdot,
        get_equivalent_race_times
    )
    LOOKUP_AVAILABLE = True
except ImportError:
    LOOKUP_AVAILABLE = False


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


def calculate_vdot_from_race_time(distance_meters: float, time_seconds: int) -> Optional[float]:
    """
    Calculate VDOT from a race time and distance.
    
    Uses lookup-based calculation with actual VDOT formula for accuracy.
    Falls back to approximation if lookup service unavailable.
    
    Args:
        distance_meters: Race distance in meters
        time_seconds: Race time in seconds
        
    Returns:
        VDOT score (float) or None if calculation fails
    """
    if distance_meters <= 0 or time_seconds <= 0:
        return None
    
    # Use lookup service if available (more accurate)
    if LOOKUP_AVAILABLE:
        try:
            vdot = calculate_vdot_from_race_time_lookup(distance_meters, time_seconds)
            if vdot:
                return vdot
        except Exception:
            pass  # Fall back to approximation
    
    # Fallback: Approximation formulas
    distance_miles = distance_meters / 1609.34
    time_minutes = time_seconds / 60.0
    
    if distance_miles <= 0 or time_minutes <= 0:
        return None
    
    pace_per_mile = time_minutes / distance_miles
    
    # Approximation formulas (less accurate than lookup)
    if distance_miles <= 0.5:  # 800m or less
        velocity_ms = distance_meters / time_seconds
        vdot = (velocity_ms * 3.5) / 0.2989558
    elif distance_miles <= 1.0:  # Mile
        vdot = 100 * (distance_miles / pace_per_mile) * 0.88
    elif distance_miles <= 3.1:  # 5K
        vdot = 100 * (distance_miles / pace_per_mile) * 0.92
    elif distance_miles <= 6.2:  # 10K
        vdot = 100 * (distance_miles / pace_per_mile) * 0.96
    elif distance_miles <= 13.1:  # Half Marathon
        vdot = 100 * (distance_miles / pace_per_mile) * 1.0
    else:  # Marathon or longer
        vdot = 100 * (distance_miles / pace_per_mile) * 1.04
    
    return round(vdot, 1)


def calculate_vdot_from_pace(pace_minutes_per_mile: float) -> Optional[float]:
    """
    Calculate VDOT from a training pace (reverse calculation).
    
    Args:
        pace_minutes_per_mile: Pace in minutes per mile
        
    Returns:
        VDOT score (float) or None if calculation fails
    """
    if pace_minutes_per_mile <= 0:
        return None
    
    # Approximate VDOT from pace
    # This assumes the pace is approximately threshold or marathon pace
    # VDOT ≈ 1000 / pace_per_mile (simplified)
    vdot = 1000 / pace_minutes_per_mile
    
    return round(vdot, 1)


def calculate_training_paces(vdot: float) -> Dict:
    """
    Calculate all training paces from VDOT.
    
    Based on Daniels' Running Formula pace tables.
    Returns paces in both per mile and per km.
    
    Args:
        vdot: VDOT score
        
    Returns:
        Dictionary with training paces in MM:SS format (both mi and km)
    """
    if vdot <= 0:
        return {
            "easy": {"mi": None, "km": None},
            "marathon": {"mi": None, "km": None},
            "threshold": {"mi": None, "km": None},
            "interval": {"mi": None, "km": None},
            "repetition": {"mi": None, "km": None},
            "fast_reps": {"mi": None, "km": None},
        }
    
    # Use lookup service if available (more accurate)
    if LOOKUP_AVAILABLE:
        try:
            paces = get_training_paces_from_vdot(vdot)
            if paces:
                def pace_to_dict(pace_str: str) -> Dict:
                    """Convert pace string to dict format."""
                    if not pace_str:
                        return {"mi": None, "km": None}
                    try:
                        parts = pace_str.split(":")
                        total_seconds = int(parts[0]) * 60 + int(parts[1])
                        km_seconds = int(total_seconds / 1.60934)
                        km_mins = km_seconds // 60
                        km_secs = km_seconds % 60
                        return {
                            "mi": pace_str,
                            "km": f"{km_mins}:{km_secs:02d}"
                        }
                    except:
                        return {"mi": pace_str, "km": None}
                
                return {
                    "easy": pace_to_dict(paces.get("e_pace", "")),
                    "marathon": pace_to_dict(paces.get("m_pace", "")),
                    "threshold": pace_to_dict(paces.get("t_pace", "")),
                    "interval": pace_to_dict(paces.get("i_pace", "")),
                    "repetition": pace_to_dict(paces.get("r_pace", "")),
                    "fast_reps": pace_to_dict(paces.get("r_pace", "")),  # Fast reps = R pace
                }
        except Exception as e:
            # Fall back to approximation if lookup fails
            pass
    
    # Fallback: Approximation formulas
    vo2max_pace_per_mile = (1000 / vdot) * 0.98
    
    # Calculate training paces based on percentages of VO2max
    # From reference site and Daniels' formula:
    easy_pace_mi = vo2max_pace_per_mile / 0.72  # ~72% of VO2max (59-74% range)
    marathon_pace_mi = vo2max_pace_per_mile / 0.80  # ~80% of VO2max (75-84% range)
    threshold_pace_mi = vo2max_pace_per_mile / 0.86  # ~86% of VO2max (83-88% range)
    interval_pace_mi = vo2max_pace_per_mile / 0.98  # ~98% of VO2max (97-100% range)
    repetition_pace_mi = vo2max_pace_per_mile / 1.08  # ~108% of VO2max (105-110% range)
    fast_reps_pace_mi = vo2max_pace_per_mile / 1.12  # ~112% of VO2max (faster than reps)
    
    def format_pace(minutes_per_mile: float) -> Dict[str, Optional[str]]:
        """Format pace as MM:SS in both mi and km"""
        if minutes_per_mile <= 0:
            return {"mi": None, "km": None}
        
        # Per mile
        minutes = int(minutes_per_mile)
        seconds = int((minutes_per_mile - minutes) * 60)
        pace_mi = f"{minutes}:{seconds:02d}"
        
        # Per km (convert: 1 mile = 1.60934 km)
        minutes_per_km = minutes_per_mile / 1.60934
        minutes_km = int(minutes_per_km)
        seconds_km = int((minutes_per_km - minutes_km) * 60)
        pace_km = f"{minutes_km}:{seconds_km:02d}"
        
        return {"mi": pace_mi, "km": pace_km}
    
    return {
        "easy": format_pace(easy_pace_mi),
        "marathon": format_pace(marathon_pace_mi),
        "threshold": format_pace(threshold_pace_mi),
        "interval": format_pace(interval_pace_mi),
        "repetition": format_pace(repetition_pace_mi),
        "fast_reps": format_pace(fast_reps_pace_mi),
    }


def calculate_equivalent_race_time(vdot: float, target_distance_meters: float) -> Optional[Dict]:
    """
    Calculate equivalent race time for a target distance based on VDOT.
    
    Uses lookup tables for accuracy. Falls back to approximation if unavailable.
    
    Args:
        vdot: VDOT score
        target_distance_meters: Target race distance in meters
        
    Returns:
        Dictionary with equivalent time and pace, or None if calculation fails
    """
    if vdot <= 0 or target_distance_meters <= 0:
        return None
    
    # Use lookup service if available
    if LOOKUP_AVAILABLE:
        try:
            # Use closest integer VDOT for exact reference values
            equivalent = get_equivalent_race_times(vdot, use_closest_integer=True)
            if equivalent:
                # Map distance to lookup key
                distance_map = {
                    5000: "5K",
                    10000: "10K",
                    21097.5: "half_marathon",
                    42195: "marathon"
                }
                
                # Find closest distance
                closest_dist = min(distance_map.keys(), key=lambda x: abs(x - target_distance_meters))
                if abs(closest_dist - target_distance_meters) / target_distance_meters < 0.1:  # Within 10%
                    race_time_str = equivalent.get("race_times_formatted", {}).get(distance_map[closest_dist])
                    race_time_seconds = equivalent.get("race_times_seconds", {}).get(distance_map[closest_dist])
                    
                    if race_time_str and race_time_seconds:
                        # Calculate pace from time and distance
                        pace_seconds_per_mile = (race_time_seconds / closest_dist) * 1609.34
                        pace_mins = int(pace_seconds_per_mile // 60)
                        pace_secs = int(pace_seconds_per_mile % 60)
                        pace_mi = f"{pace_mins}:{pace_secs:02d}"
                        
                        pace_km_seconds = race_time_seconds / (closest_dist / 1000)
                        pace_km_mins = int(pace_km_seconds // 60)
                        pace_km_secs = int(pace_km_seconds % 60)
                        pace_km = f"{pace_km_mins}:{pace_km_secs:02d}"
                        
                        return {
                            "distance_m": closest_dist,
                            "distance_name": _get_distance_name(closest_dist),
                            "time_seconds": race_time_seconds,
                            "time_formatted": race_time_str,
                            "pace_mi": pace_mi,
                            "pace_km": pace_km,
                        }
        except Exception:
            pass  # Fall back to approximation
    
    # Fallback: Approximation using lookup table interpolation
    # Try to interpolate from known distances in lookup table
    if LOOKUP_AVAILABLE:
        try:
            equivalent = get_equivalent_race_times(vdot, use_closest_integer=True)
            if equivalent:
                race_times_seconds = equivalent.get("race_times_seconds", {})
                
                # Get 5K time as reference (most common)
                if "5K" in race_times_seconds:
                    ref_time_5k = race_times_seconds["5K"]
                    ref_distance_5k = 5000
                    
                    # Use power law: time = a * distance^b
                    # For running, b ≈ 1.07-1.08 (slightly faster than linear)
                    # Calculate from 5K reference
                    b = 1.075  # Power law exponent
                    a = ref_time_5k / (ref_distance_5k ** b)
                    time_seconds = a * (target_distance_meters ** b)
                    
                    # Format time
                    hours = int(time_seconds // 3600)
                    minutes = int((time_seconds % 3600) // 60)
                    secs = int(time_seconds % 60)
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
                        "time_seconds": int(time_seconds),
                        "time_formatted": time_formatted,
                        "pace_mi": pace_mi,
                        "pace_km": pace_km,
                    }
        except Exception:
            pass  # Fall back to simple approximation
    
    # Simple fallback: Approximation
    vo2max_pace_per_mile = (1000 / vdot) * 0.98
    
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


def calculate_all_equivalent_races(vdot: float) -> List[Dict]:
    """
    Calculate equivalent race times for all standard distances.
    
    Args:
        vdot: VDOT score
        
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
        equivalent = calculate_equivalent_race_time(vdot, distance_m)
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


def calculate_vdot_comprehensive(distance_meters: Optional[float] = None, 
                                  time_seconds: Optional[int] = None,
                                  pace_minutes_per_mile: Optional[float] = None) -> Dict:
    """
    Comprehensive VDOT calculator with training paces and equivalent races.
    
    Can calculate from:
    - Race time and distance
    - Or from pace (reverse calculation)
    
    Args:
        distance_meters: Race distance in meters (if calculating from race)
        time_seconds: Race time in seconds (if calculating from race)
        pace_minutes_per_mile: Pace in minutes per mile (if reverse calculation)
        
    Returns:
        Comprehensive dictionary with VDOT, training paces, and equivalent races
    """
    # Calculate VDOT
    if distance_meters and time_seconds:
        vdot = calculate_vdot_from_race_time(distance_meters, time_seconds)
        input_type = "race_time"
    elif pace_minutes_per_mile:
        vdot = calculate_vdot_from_pace(pace_minutes_per_mile)
        input_type = "pace"
    else:
        return {
            "error": "Must provide either (distance_meters + time_seconds) or pace_minutes_per_mile"
        }
    
    if vdot is None:
        return {
            "error": "Invalid input: could not calculate VDOT"
        }
    
    # Calculate training paces
    training_paces = calculate_training_paces(vdot)
    
    # Calculate equivalent race performances
    equivalent_races = calculate_all_equivalent_races(vdot)
    
    result = {
        "vdot": vdot,
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
