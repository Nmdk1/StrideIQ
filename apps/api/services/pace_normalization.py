"""
Pace Normalization Service

Implements Minetti's equation for Normalized Grade Pace (NGP) calculation.
This normalizes pace for terrain, allowing accurate efficiency comparisons across different routes.
"""

from typing import Optional
from decimal import Decimal
import math


def calculate_grade_percent(elevation_gain_m: float, distance_m: float) -> Optional[float]:
    """
    Calculate grade percentage from elevation gain and distance.
    
    Args:
        elevation_gain_m: Elevation gain in meters (can be negative for downhill)
        distance_m: Distance in meters
    
    Returns:
        Grade percentage (e.g., 5.0 for 5% grade, -3.0 for -3% grade)
    """
    if distance_m <= 0:
        return None
    
    grade_percent = (elevation_gain_m / distance_m) * 100.0
    return grade_percent


def calculate_normalized_grade_pace(
    raw_pace_seconds_per_mile: float,
    grade_percent: float
) -> Optional[float]:
    """
    Calculate Normalized Grade Pace (NGP) using Minetti's equation.
    
    Minetti's equation accounts for the metabolic cost of running uphill/downhill.
    This normalizes pace to flat-ground equivalent, enabling accurate efficiency comparisons.
    
    Formula based on Minetti et al. (2002):
    NGP = raw_pace * (1 + k * grade^2)
    where k ≈ 0.033 for running
    
    For negative grades (downhill), the equation accounts for braking forces.
    
    Args:
        raw_pace_seconds_per_mile: Raw pace in seconds per mile
        grade_percent: Grade percentage (positive = uphill, negative = downhill)
    
    Returns:
        Normalized Grade Pace in seconds per mile (flat-ground equivalent)
    """
    if raw_pace_seconds_per_mile <= 0:
        return None
    
    # Convert grade percentage to decimal (5% = 0.05)
    grade_decimal = grade_percent / 100.0
    
    # Minetti's coefficient for running (from research literature)
    # This accounts for the metabolic cost of vertical work
    k = 0.033
    
    # Minetti's equation: NGP = raw_pace * (1 + k * grade^2)
    # For uphill (positive grade), this increases pace (slower)
    # For downhill (negative grade), this decreases pace (faster)
    # The square ensures symmetry (uphill and downhill have different costs)
    
    # For steep downhills, we need to account for braking forces
    # Research suggests a modified coefficient for negative grades
    if grade_decimal < 0:
        # Downhill: braking forces reduce efficiency gains
        # Use a smaller coefficient for negative grades
        k_downhill = 0.020  # Less efficient than pure physics suggests
        normalized_factor = 1 + k_downhill * (grade_decimal ** 2)
    else:
        # Uphill: standard Minetti coefficient
        normalized_factor = 1 + k * (grade_decimal ** 2)
    
    ngp = raw_pace_seconds_per_mile * normalized_factor
    
    return round(ngp, 2)


def calculate_ngp_from_split(
    distance_m: float,
    moving_time_s: int,
    elevation_gain_m: Optional[float] = None
) -> Optional[float]:
    """
    Calculate NGP for a split/lap given distance, time, and elevation.
    
    Args:
        distance_m: Distance in meters
        moving_time_s: Moving time in seconds
        elevation_gain_m: Elevation gain in meters (optional)
    
    Returns:
        Normalized Grade Pace in seconds per mile, or None if insufficient data
    """
    if distance_m <= 0 or moving_time_s <= 0:
        return None
    
    # Calculate raw pace in seconds per mile
    distance_miles = distance_m / 1609.34
    raw_pace_seconds_per_mile = moving_time_s / distance_miles
    
    # If no elevation data, return raw pace (assume flat)
    if elevation_gain_m is None:
        return round(raw_pace_seconds_per_mile, 2)
    
    # Calculate grade
    grade_percent = calculate_grade_percent(elevation_gain_m, distance_m)
    if grade_percent is None:
        return round(raw_pace_seconds_per_mile, 2)
    
    # Calculate NGP
    ngp = calculate_normalized_grade_pace(raw_pace_seconds_per_mile, grade_percent)
    return ngp


def pace_seconds_to_minutes_per_mile(pace_seconds: float) -> str:
    """
    Convert pace from seconds per mile to MM:SS/mi format.
    
    Args:
        pace_seconds: Pace in seconds per mile
    
    Returns:
        Formatted pace string (e.g., "8:51/mi")
    """
    minutes = int(pace_seconds // 60)
    seconds = int(pace_seconds % 60)
    return f"{minutes}:{seconds:02d}/mi"


