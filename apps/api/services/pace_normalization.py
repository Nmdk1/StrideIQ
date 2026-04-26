"""
Pace Normalization Service

Implements Minetti's equation for Normalized Grade Pace (NGP) calculation.
This normalizes pace for terrain, allowing accurate efficiency comparisons across different routes.
"""

from typing import Optional


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


def _minetti_cost(grade_decimal: float) -> float:
    """
    Metabolic cost of running at a given grade per Minetti et al. (2002).

    C(i) = 155.4i^5 - 30.4i^4 - 43.3i^3 + 46.3i^2 + 19.5i + 3.6
    where i = grade as a decimal fraction (0.05 = 5% grade).

    Returns cost in J/(kg·m). Clamped to a minimum of 1.0 to avoid
    division-by-zero or negative cost at extreme downhill grades.
    """
    i = grade_decimal
    cost = 155.4*i**5 - 30.4*i**4 - 43.3*i**3 + 46.3*i**2 + 19.5*i + 3.6
    return max(cost, 1.0)


_FLAT_COST = _minetti_cost(0.0)  # 3.6 J/(kg·m)


def calculate_normalized_grade_pace(
    raw_pace_seconds_per_mile: float,
    grade_percent: float
) -> Optional[float]:
    """
    Calculate Normalized Grade Pace (NGP) using the full Minetti polynomial.

    GAP = raw_pace * C_flat / C_grade

    Running uphill costs more energy per meter, so GAP is faster than actual
    pace (you would have gone faster on flat with the same effort). Downhill
    is cheaper, so GAP is slower than actual pace.

    Args:
        raw_pace_seconds_per_mile: Raw pace in seconds per mile
        grade_percent: Grade percentage (positive = uphill, negative = downhill)

    Returns:
        Normalized Grade Pace in seconds per mile (flat-ground equivalent)
    """
    if raw_pace_seconds_per_mile <= 0:
        return None

    grade_decimal = grade_percent / 100.0
    grade_cost = _minetti_cost(grade_decimal)
    ngp = raw_pace_seconds_per_mile * _FLAT_COST / grade_cost

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


