"""
Enhanced Training Pace Calculator - Based on Daniels' Running Formula

Provides comprehensive fitness score calculations with:
- Race Paces tab: Paces for different distances (5K, 1Mi, 1K, 800M, 400M)
- Training tab: Training paces with ranges and interval distances
- Equivalent tab: Equivalent race times for all standard distances

Based on publicly available formulas from Dr. Jack Daniels' research.
Not affiliated with VDOT O2 or The Run SMART Project.
"""

from typing import Dict, List, Optional
from services.vdot_calculator import (
    calculate_vdot_from_race_time,
    STANDARD_DISTANCES,
    _get_distance_name,
    calculate_equivalent_race_time
)
from services.vdot_lookup import (
    get_training_paces_from_vdot,
    get_equivalent_race_times
)

# Interval distances for training paces
INTERVAL_DISTANCES = {
    "long": [1200, 800, 600],  # meters - for Threshold, Interval, Repetition
    "short": [400, 300, 200],  # meters - for Interval, Repetition, Fast Reps
}


def calculate_race_paces(vdot: float, input_distance_m: float, input_time_seconds: int) -> List[Dict]:
    """
    Calculate race paces for different distances (Race Paces tab).
    
    Returns paces for: 5K, 1Mi, 1K, 800M, 400M
    Uses equivalent race time calculations for accuracy.
    """
    race_paces = []
    
    # Get equivalent race times for standard distances
    equivalent = get_equivalent_race_times(vdot, use_closest_integer=True)
    
    # Distances to show in Race Paces tab (in order)
    race_pace_distances = [
        ("5K", 5000),
        ("1Mi", 1609.34),
        ("1K", 1000),
        ("800M", 800),
        ("400M", 400),
    ]
    
    # Get training paces for pace calculations
    training_paces = get_training_paces_from_vdot(vdot, use_closest_integer=True)
    
    for name, distance_m in race_pace_distances:
        time_seconds = None
        time_formatted = None
        
        # For 5K, use equivalent lookup if available
        if distance_m == 5000 and equivalent:
            time_seconds = equivalent.get("race_times_seconds", {}).get("5K")
            if time_seconds:
                time_formatted = equivalent.get("race_times_formatted", {}).get("5K")
        
        # For other distances, calculate from equivalent race time function
        if not time_seconds:
            from services.vdot_calculator import calculate_equivalent_race_time
            equiv_result = calculate_equivalent_race_time(vdot, distance_m)
            if equiv_result:
                time_seconds = equiv_result.get("time_seconds")
                time_formatted = equiv_result.get("time_formatted")
        
        # Fallback: calculate from training paces (should rarely be needed)
        if not time_seconds and training_paces:
            i_pace_seconds = training_paces.get("i_pace_seconds")
            if i_pace_seconds:
                # Distance-specific pace factors (based on vdoto2.com patterns)
                distance_miles = distance_m / 1609.34
                if distance_miles <= 0.25:  # 400m
                    factor = 0.85
                elif distance_miles <= 0.5:  # 800m
                    factor = 0.90
                elif distance_miles <= 0.62:  # 1K
                    factor = 0.92
                elif distance_miles <= 1.0:  # 1Mi
                    factor = 0.95
                else:  # 5K
                    factor = 0.98
                
                race_pace_seconds_per_mile = i_pace_seconds * factor
                time_seconds = race_pace_seconds_per_mile * distance_miles
                
                # Format time
                mins = int(time_seconds // 60)
                secs = int(time_seconds % 60)
                time_formatted = f"{mins}:{secs:02d}"
        
        if time_seconds:
            # Calculate pace per mile
            pace_seconds_per_mile = (time_seconds / distance_m) * 1609.34
            pace_mins = int(pace_seconds_per_mile // 60)
            pace_secs = int(pace_seconds_per_mile % 60)
            pace_decimal = int((pace_seconds_per_mile % 1) * 10)
            pace_mi = f"{pace_mins}:{pace_secs:02d}.{pace_decimal}"
            
            race_paces.append({
                "distance": name,
                "distance_m": distance_m,
                "time_seconds": int(time_seconds),
                "time_formatted": time_formatted or f"{int(time_seconds // 60)}:{int(time_seconds % 60):02d}",
                "pace_mi": pace_mi,
            })
    
    return race_paces


def calculate_training_paces_enhanced(vdot: float) -> Dict:
    """
    Calculate comprehensive training paces matching vdoto2.com format.
    
    Returns:
    - Per mile/km paces (with Easy pace range)
    - Interval distances (1200m, 800m, 600m)
    - Shorter intervals (400m, 300m, 200m)
    """
    training_paces = get_training_paces_from_vdot(vdot, use_closest_integer=True)
    
    if not training_paces:
        return {}
    
    result = {
        "per_mile_km": {},
        "interval_distances": {},
        "short_intervals": {},
    }
    
    # Per mile/km paces
    e_pace_seconds = training_paces.get("e_pace_seconds")
    m_pace_seconds = training_paces.get("m_pace_seconds")
    t_pace_seconds = training_paces.get("t_pace_seconds")
    i_pace_seconds = training_paces.get("i_pace_seconds")
    r_pace_seconds = training_paces.get("r_pace_seconds")
    
    def format_pace(seconds: Optional[int], is_km: bool = False) -> Optional[str]:
        if seconds is None:
            return None
        if is_km:
            seconds = int(seconds / 1.60934)
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins}:{secs:02d}"
    
    def format_pace_range(seconds: Optional[int], is_km: bool = False) -> Optional[str]:
        """
        Format Easy pace as a range (faster ~ slower).
        Based on vdoto2.com: Easy pace range is approximately -24 to +26 seconds per mile.
        """
        if seconds is None:
            return None
        if is_km:
            seconds_km = int(seconds / 1.60934)
        else:
            seconds_km = seconds
        
        # Easy pace range: approximately -24 to +26 seconds per mile
        # For km: approximately -15 to +16 seconds
        if is_km:
            fast_seconds = seconds_km - 15  # Faster pace (less time)
            slow_seconds = seconds_km + 16  # Slower pace (more time)
        else:
            fast_seconds = seconds - 24  # Faster pace (less time)
            slow_seconds = seconds + 26  # Slower pace (more time)
        
        # Ensure non-negative
        fast_seconds = max(0, fast_seconds)
        slow_seconds = max(0, slow_seconds)
        
        fast_mins = fast_seconds // 60
        fast_secs = fast_seconds % 60
        slow_mins = slow_seconds // 60
        slow_secs = slow_seconds % 60
        
        return f"{fast_mins}:{fast_secs:02d} ~ {slow_mins}:{slow_secs:02d}"
    
    # Per mile/km training paces
    result["per_mile_km"] = {
        "easy": {
            "mi": format_pace_range(e_pace_seconds, is_km=False),
            "km": format_pace_range(e_pace_seconds, is_km=True),
        },
        "marathon": {
            "mi": format_pace(m_pace_seconds, is_km=False),
            "km": format_pace(m_pace_seconds, is_km=True),
        },
        "threshold": {
            "mi": format_pace(t_pace_seconds, is_km=False),
            "km": format_pace(t_pace_seconds, is_km=True),
        },
        "interval": {
            "mi": format_pace(i_pace_seconds, is_km=False),
            "km": format_pace(i_pace_seconds, is_km=True),
        },
        "repetition": {
            "mi": format_pace(r_pace_seconds, is_km=False),
            "km": format_pace(r_pace_seconds, is_km=True),
        },
    }
    
    # Interval distances (1200m, 800m, 600m) for Threshold, Interval, Repetition
    interval_distances = {}
    for pace_type, pace_seconds in [("threshold", t_pace_seconds), ("interval", i_pace_seconds), ("repetition", r_pace_seconds)]:
        if pace_seconds:
            interval_distances[pace_type] = {}
            for dist_m in INTERVAL_DISTANCES["long"]:
                # Calculate time for this distance at this pace
                # pace_seconds is seconds per mile, so time = pace * (distance_m / 1609.34)
                time_seconds = pace_seconds * (dist_m / 1609.34)
                mins = int(time_seconds // 60)
                secs = int(time_seconds % 60)
                interval_distances[pace_type][f"{dist_m}m"] = f"{mins}:{secs:02d}"
    
    result["interval_distances"] = interval_distances
    
    # Short intervals (400m, 300m, 200m) for Interval, Repetition, Fast Reps
    short_intervals = {}
    
    # Fast Reps pace (slightly faster than Repetition)
    fast_reps_seconds = int(r_pace_seconds * 0.95) if r_pace_seconds else None
    
    for pace_type, pace_seconds in [
        ("interval", i_pace_seconds),
        ("repetition", r_pace_seconds),
        ("fast_reps", fast_reps_seconds),
    ]:
        if pace_seconds:
            short_intervals[pace_type] = {}
            for dist_m in INTERVAL_DISTANCES["short"]:
                # Calculate time for this distance at this pace
                # pace_seconds is seconds per mile, so time = pace * (distance_m / 1609.34)
                time_seconds = pace_seconds * (dist_m / 1609.34)
                mins = int(time_seconds // 60)
                secs = int(time_seconds % 60)
                short_intervals[pace_type][f"{dist_m}m"] = f"{mins}:{secs:02d}"
    
    result["short_intervals"] = short_intervals
    
    return result


def calculate_equivalent_races_enhanced(vdot: float) -> List[Dict]:
    """
    Calculate equivalent race times for all standard distances.
    
    Returns list of equivalent race performances matching vdoto2.com format.
    """
    equivalent = get_equivalent_race_times(vdot, use_closest_integer=True)
    
    if not equivalent:
        return []
    
    equivalent_races = []
    
    # Standard distances in order (matching vdoto2.com)
    distances = [
        ("Marathon", 42195),
        ("Half Marathon", 21097.5),
        ("15K", 15000),
        ("10K", 10000),
        ("5K", 5000),
        ("3Mi", 4828),
        ("2Mi", 3218.7),
        ("3200M", 3200),
        ("3K", 3000),
        ("1mi", 1609.34),
        ("1600M", 1600),
        ("1500M", 1500),
    ]
    
    distance_map = {
        "marathon": "Marathon",
        "half_marathon": "Half Marathon",
        "10K": "10K",
        "5K": "5K",
    }
    
    race_times_seconds = equivalent.get("race_times_seconds", {})
    race_times_formatted = equivalent.get("race_times_formatted", {})
    
    for name, distance_m in distances:
        # Try to find matching distance
        time_seconds = None
        time_formatted = None
        
        # Check lookup first
        lookup_key = None
        if distance_m == 42195:
            lookup_key = "marathon"
        elif abs(distance_m - 21097.5) < 100:
            lookup_key = "half_marathon"
        elif distance_m == 10000:
            lookup_key = "10K"
        elif distance_m == 5000:
            lookup_key = "5K"
        
        if lookup_key and lookup_key in race_times_seconds:
            time_seconds = race_times_seconds[lookup_key]
            time_formatted = race_times_formatted.get(lookup_key)
        else:
            # Calculate from VDOT for other distances using proper equivalent race time function
            equiv_result = calculate_equivalent_race_time(vdot, distance_m)
            if equiv_result:
                time_seconds = equiv_result.get("time_seconds")
                time_formatted = equiv_result.get("time_formatted")
        
        if time_seconds:
            # Calculate pace
            pace_seconds_per_mile = (time_seconds / distance_m) * 1609.34
            pace_mins = int(pace_seconds_per_mile // 60)
            pace_secs = int(pace_seconds_per_mile % 60)
            pace_mi = f"{pace_mins}:{pace_secs:02d}"
            
            pace_km_seconds = time_seconds / (distance_m / 1000)
            pace_km_mins = int(pace_km_seconds // 60)
            pace_km_secs = int(pace_km_seconds % 60)
            pace_km = f"{pace_km_mins}:{pace_km_secs:02d}"
            
            equivalent_races.append({
                "race": name,
                "distance_m": distance_m,
                "time_seconds": int(time_seconds),
                "time_formatted": time_formatted or f"{int(time_seconds // 60)}:{int(time_seconds % 60):02d}",
                "pace_mi": pace_mi,
                "pace_km": pace_km,
            })
    
    return equivalent_races


def calculate_vdot_enhanced(distance_meters: float, time_seconds: int) -> Dict:
    """
    Enhanced VDOT calculator matching vdoto2.com functionality.
    
    Returns comprehensive data structure with three tabs:
    1. Race Paces: Paces for different distances
    2. Training: Training paces with ranges and interval distances
    3. Equivalent: Equivalent race times for all distances
    """
    # Calculate VDOT
    vdot = calculate_vdot_from_race_time(distance_meters, time_seconds)
    
    if vdot is None:
        return {"error": "Could not calculate VDOT"}
    
    # Format input race time
    hours = time_seconds // 3600
    minutes = (time_seconds % 3600) // 60
    seconds = time_seconds % 60
    if hours > 0:
        race_time_formatted = f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        race_time_formatted = f"{minutes}:{seconds:02d}"
    
    # Calculate pace for input race
    distance_miles = distance_meters / 1609.34
    pace_per_mile_seconds = time_seconds / distance_miles
    pace_mins = int(pace_per_mile_seconds // 60)
    pace_secs = int(pace_per_mile_seconds % 60)
    pace_decimal = int((pace_per_mile_seconds % 1) * 10)
    input_pace_mi = f"{pace_mins}:{pace_secs:02d}.{pace_decimal}"
    
    return {
        "vdot": round(vdot, 1),
        "input": {
            "distance_m": distance_meters,
            "distance_name": _get_distance_name(distance_meters),
            "time_seconds": time_seconds,
            "time_formatted": race_time_formatted,
            "pace_mi": input_pace_mi,
        },
        "race_paces": calculate_race_paces(vdot, distance_meters, time_seconds),
        "training": calculate_training_paces_enhanced(vdot),
        "equivalent": calculate_equivalent_races_enhanced(vdot),
    }
