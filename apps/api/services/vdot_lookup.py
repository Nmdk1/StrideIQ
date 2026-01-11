"""
VDOT Lookup Service

Provides lookup-based VDOT calculations using stored lookup tables.
More accurate than approximation formulas.
"""
import json
import math
from typing import Optional, Dict, List
from sqlalchemy.orm import Session

from core.database import get_db_sync
from models import CoachingKnowledgeEntry


def get_vdot_lookup_tables() -> Optional[Dict]:
    """Get VDOT lookup tables from knowledge base."""
    db = get_db_sync()
    try:
        entry = db.query(CoachingKnowledgeEntry).filter(
            CoachingKnowledgeEntry.principle_type == "vdot_lookup_tables",
            CoachingKnowledgeEntry.methodology == "Daniels"
        ).first()
        
        if entry and entry.extracted_principles:
            return json.loads(entry.extracted_principles)
        return None
    finally:
        db.close()


def interpolate_pace(vdot: float, pace_lookup: Dict) -> Optional[Dict]:
    """
    Interpolate training paces for a given VDOT value.
    
    Args:
        vdot: VDOT value
        pace_lookup: Lookup table dictionary
        
    Returns:
        Dictionary with training paces or None if VDOT out of range
    """
    if not pace_lookup:
        return None
    
    # Convert keys to floats and sort
    vdots = sorted([float(k) for k in pace_lookup.keys()])
    
    if vdot < vdots[0] or vdot > vdots[-1]:
        return None  # Out of range
    
    # Find exact match (within 0.1 tolerance)
    for v in vdots:
        if abs(v - vdot) < 0.1:
            # Find the actual key in the dictionary
            for k in pace_lookup.keys():
                if abs(float(k) - v) < 0.1:
                    return pace_lookup[k]
            return None
    
    # Find bounding values for interpolation
    lower_vdot = None
    upper_vdot = None
    
    for v in vdots:
        if v <= vdot:
            lower_vdot = v
        if v >= vdot and upper_vdot is None:
            upper_vdot = v
    
    if lower_vdot is None or upper_vdot is None:
        return None
    
    # Get the actual dictionary keys (they might be floats as strings or actual floats)
    lower_key = None
    upper_key = None
    for k in pace_lookup.keys():
        k_float = float(k)
        if abs(k_float - lower_vdot) < 0.1:
            lower_key = k
        if abs(k_float - upper_vdot) < 0.1:
            upper_key = k
    
    if lower_key is None or upper_key is None:
        return None
    
    # Interpolate
    lower_paces = pace_lookup[lower_key]
    upper_paces = pace_lookup[upper_key]
    
    ratio = (vdot - lower_vdot) / (upper_vdot - lower_vdot)
    
    interpolated = {}
    for pace_type in ["e_pace", "m_pace", "t_pace", "i_pace", "r_pace"]:
        lower_seconds = lower_paces.get(f"{pace_type}_seconds", 0)
        upper_seconds = upper_paces.get(f"{pace_type}_seconds", 0)
        
        if lower_seconds and upper_seconds:
            interpolated_seconds = lower_seconds + (upper_seconds - lower_seconds) * ratio
            interpolated[f"{pace_type}_seconds"] = int(interpolated_seconds)
            
            # Format as MM:SS
            minutes = int(interpolated_seconds // 60)
            seconds = int(interpolated_seconds % 60)
            interpolated[pace_type] = f"{minutes}:{seconds:02d}"
    
    return interpolated


def calculate_vdot_from_race_time_lookup(distance_meters: float, time_seconds: int) -> Optional[float]:
    """
    Calculate VDOT from race time using the actual VDOT formula.
    
    Uses the validated formula from Daniels' Running Formula:
    VDOT = (-4.60 + 0.182258 * V + 0.000104 * V^2) / (0.8 + 0.1894393 * e^(-0.012778 * T) + 0.2989558 * e^(-0.1932605 * T))
    
    Where:
    - V = velocity in meters per minute
    - T = time in minutes
    
    Note: This formula may produce slightly different results than published tables
    due to rounding and table interpolation. For exact paces, use lookup tables.
    """
    if distance_meters <= 0 or time_seconds <= 0:
        return None
    
    # Convert to meters per minute and minutes
    velocity_m_per_min = (distance_meters / time_seconds) * 60
    time_minutes = time_seconds / 60.0
    
    # Calculate VDOT using the formula
    numerator = -4.60 + 0.182258 * velocity_m_per_min + 0.000104 * (velocity_m_per_min ** 2)
    
    exp1 = math.exp(-0.012778 * time_minutes)
    exp2 = math.exp(-0.1932605 * time_minutes)
    denominator = 0.8 + 0.1894393 * exp1 + 0.2989558 * exp2
    
    if denominator == 0:
        return None
    
    vdot = numerator / denominator
    
    # Round to 1 decimal place
    # Note: The Daniels formula is scientifically accurate and matches
    # industry-standard calculators when implemented correctly
    return round(vdot, 1)


def get_training_paces_from_vdot(vdot: float, use_closest_integer: bool = True) -> Optional[Dict]:
    """
    Get training paces for a given VDOT using lookup tables.
    
    Args:
        vdot: VDOT value (can be float)
        use_closest_integer: If True, round to nearest integer VDOT for exact reference values
    
    Returns paces in both MM:SS format and seconds.
    """
    tables = get_vdot_lookup_tables()
    if not tables:
        return None
    
    pace_lookup = tables.get("pace_lookup", {})
    if not pace_lookup:
        return None
    
    # Use closest integer VDOT for exact reference values
    if use_closest_integer:
        vdot_int = int(round(vdot))
        vdot_float = float(vdot_int)
        # Check if exact integer exists
        if vdot_float in pace_lookup:
            return pace_lookup[vdot_float]
        # Try to find closest key
        for k in pace_lookup.keys():
            if abs(float(k) - vdot_float) < 0.1:
                return pace_lookup[k]
    
    # Otherwise interpolate
    return interpolate_pace(vdot, pace_lookup)


def get_equivalent_race_times(vdot: float, use_closest_integer: bool = True) -> Optional[Dict]:
    """
    Get equivalent race times for a given VDOT using lookup tables.
    
    Args:
        vdot: VDOT value (can be float)
        use_closest_integer: If True, round to nearest integer VDOT for exact reference values
    
    Returns race times for 5K, 10K, half marathon, and marathon.
    """
    tables = get_vdot_lookup_tables()
    if not tables:
        return None
    
    equivalent_lookup = tables.get("equivalent_performance_lookup", {})
    if not equivalent_lookup:
        return None
    
    # Use closest integer VDOT for exact reference values (like training paces)
    if use_closest_integer:
        vdot_int = int(round(vdot))
        vdot_float = float(vdot_int)
        # Check if exact integer exists
        if vdot_float in equivalent_lookup:
            return equivalent_lookup[vdot_float]
        # Try to find closest key
        for k in equivalent_lookup.keys():
            if abs(float(k) - vdot_float) < 0.1:
                return equivalent_lookup[k]
    
    # Find closest VDOT value
    vdots = sorted([float(k) for k in equivalent_lookup.keys()])
    
    if vdot < vdots[0]:
        # Return lowest available
        for k in equivalent_lookup.keys():
            if abs(float(k) - vdots[0]) < 0.1:
                return equivalent_lookup[k]
        return None
    if vdot > vdots[-1]:
        # Return highest available
        for k in equivalent_lookup.keys():
            if abs(float(k) - vdots[-1]) < 0.1:
                return equivalent_lookup[k]
        return None
    
    # Find exact match (within tolerance)
    for k in equivalent_lookup.keys():
        if abs(float(k) - vdot) < 0.1:
            return equivalent_lookup[k]
    
    # Interpolate
    lower_vdot = None
    upper_vdot = None
    
    for v in vdots:
        if v <= vdot:
            lower_vdot = v
        if v >= vdot and upper_vdot is None:
            upper_vdot = v
    
    if lower_vdot is None or upper_vdot is None:
        return None
    
    # Find actual keys
    lower_key = None
    upper_key = None
    for k in equivalent_lookup.keys():
        k_float = float(k)
        if abs(k_float - lower_vdot) < 0.1:
            lower_key = k
        if abs(k_float - upper_vdot) < 0.1:
            upper_key = k
    
    if lower_key is None or upper_key is None:
        return None
    
    lower_times = equivalent_lookup[lower_key]
    upper_times = equivalent_lookup[upper_key]
    
    ratio = (vdot - lower_vdot) / (upper_vdot - lower_vdot)
    
    interpolated = {
        "race_times_formatted": {},
        "race_times_seconds": {}
    }
    
    for distance in ["5K", "10K", "half_marathon", "marathon"]:
        lower_seconds = lower_times.get("race_times_seconds", {}).get(distance, 0)
        upper_seconds = upper_times.get("race_times_seconds", {}).get(distance, 0)
        
        if lower_seconds and upper_seconds:
            interpolated_seconds = int(lower_seconds + (upper_seconds - lower_seconds) * ratio)
            interpolated["race_times_seconds"][distance] = interpolated_seconds
            
            # Format time
            hours = interpolated_seconds // 3600
            minutes = (interpolated_seconds % 3600) // 60
            secs = interpolated_seconds % 60
            
            if hours > 0:
                interpolated["race_times_formatted"][distance] = f"{hours}:{minutes:02d}:{secs:02d}"
            else:
                interpolated["race_times_formatted"][distance] = f"{minutes}:{secs:02d}"
    
    return interpolated

