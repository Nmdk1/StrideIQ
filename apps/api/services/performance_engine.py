"""
Performance Physics Engine - Core Diagnostic Calculations

Implements WMA Age-Grading and Race Detection Logic per the Manifesto.
This is the heart of the system - converting raw performance into normalized,
age-graded metrics that allow fair comparison across all ages.
"""
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Tuple, List, Dict
import math
import re


def _now_utc() -> datetime:
    """Get current time as timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def _make_aware(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (assume UTC if naive)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ============================================================================
# AGE CATEGORY CLASSIFICATION (Manifesto Section 3: Taxonomy)
# ============================================================================

def get_age_category(age: Optional[int]) -> Optional[str]:
    """
    Classify athlete into age category per manifesto taxonomy.
    
    Categories:
    - Open: <35
    - Masters: 40-49
    - Grandmasters: 50-59
    - Senior Grandmasters: 60-69
    - Legend Masters: 70-79
    - Icon Masters: 80-89
    - Centurion Masters: 90-99
    - Centurion Prime: 100+
    
    Args:
        age: Athlete's age
        
    Returns:
        Category name string or None if age is unavailable
    """
    if age is None:
        return None
    
    if age < 35:
        return "Open"
    elif age < 40:
        return "Open"  # Still Open until 40
    elif age < 50:
        return "Masters"
    elif age < 60:
        return "Grandmasters"
    elif age < 70:
        return "Senior Grandmasters"
    elif age < 80:
        return "Legend Masters"
    elif age < 90:
        return "Icon Masters"
    elif age < 100:
        return "Centurion Masters"
    else:
        return "Centurion Prime"


# ============================================================================
# AGE CALCULATION
# ============================================================================

def calculate_age_at_date(birthdate: Optional[date], activity_date: datetime) -> Optional[int]:
    """
    Calculate athlete's age at the time of activity.
    Returns None if birthdate is not available.
    """
    if not birthdate:
        return None
    
    activity_date_only = activity_date.date() if isinstance(activity_date, datetime) else activity_date
    
    age = activity_date_only.year - birthdate.year
    # Adjust if birthday hasn't occurred yet this year
    if (activity_date_only.month, activity_date_only.day) < (birthdate.month, birthdate.day):
        age -= 1
    
    return age


# ============================================================================
# WMA AGE-GRADING (Manifesto Section 4: Key Metrics)
# ============================================================================

def get_wma_age_factor(age: int, sex: Optional[str], distance_meters: float) -> Optional[float]:
    """
    Get WMA (World Masters Athletics) age-grading factor for a given age, sex, and distance.
    
    This uses improved WMA age-grading factors based on standard WMA methodology.
    
    Args:
        age: Athlete's age at time of activity
        sex: 'M' or 'F' (or None)
        distance_meters: Distance of the activity in meters
    
    Returns:
        Age factor (multiplier) or None if calculation not possible
    """
    from services.wma_age_factors import get_wma_age_factor as get_factor
    
    if age is None or age < 5:
        return None
    
    return get_factor(age, sex, distance_meters)


def calculate_age_graded_performance(
    actual_pace_per_mile: float,
    age: Optional[int],
    sex: Optional[str],
    distance_meters: float,
    use_national: bool = False
) -> Optional[float]:
    """
    Calculate age-graded performance percentage (Manifesto Section 4: Key Metrics).
    
    This is the core metric: what percentage of the world standard did the athlete achieve?
    A 100% means they matched the world record for their age/sex/distance.
    A 50% means they performed at half the world standard pace.
    
    WMA Age-Grading Formula:
    - Age-graded time = Actual time / Age factor
    - Performance % = (World Standard Time / Age-graded time) * 100
    
    For pace (inverse of speed):
    - Age-graded pace = Actual pace * Age factor
    - Performance % = (World Standard Pace / Age-graded pace) * 100
    
    Since we don't have world standard pace directly, we use:
    - Performance % = (1 / Age factor) * 100 * (some normalization)
    
    Actually, the correct formula is:
    - If a 50yo runs at pace P, their age-graded pace is P * factor
    - To compare to 30yo standard: we need to know what % of 30yo standard P represents
    - Performance % = (Standard Pace for 30yo / (P * factor)) * 100
    
    Simplified approach: Use factor to normalize, then compare to baseline.
    Performance % = 100 / age_factor (when actual pace equals age-standard pace)
    
    Args:
        actual_pace_per_mile: Actual pace in minutes per mile
        age: Athlete's age at time of activity
        sex: 'M' or 'F'
        distance_meters: Distance in meters
        
    Returns:
        Performance percentage (0-100+) or None if calculation not possible
    """
    if actual_pace_per_mile is None or actual_pace_per_mile <= 0:
        return None
    
    if age is None:
        return None
    
    # Get age factor
    age_factor = get_wma_age_factor(age, sex, distance_meters)
    if age_factor is None or age_factor <= 0:
        return None
    
    # Get record pace from WMA factors module (world or national)
    from services.wma_age_factors import get_wma_world_record_pace, get_national_world_record_pace
    
    if use_national:
        record_pace_30yo = get_national_world_record_pace(sex, distance_meters)
    else:
        record_pace_30yo = get_wma_world_record_pace(sex, distance_meters)
    
    if record_pace_30yo is None:
        return None
    
    # Age-graded pace: normalize to 30yo equivalent
    # If age_factor is 1.15, the athlete's pace is equivalent to a 30yo running 15% slower
    age_graded_pace = actual_pace_per_mile / age_factor
    
    # Performance percentage: how close to record?
    # Formula: (Record Pace / Age-Graded Pace) * 100
    # Lower pace = faster = higher percentage
    if age_graded_pace <= 0:
        return None
    
    performance_percentage = (record_pace_30yo / age_graded_pace) * 100
    
    return round(performance_percentage, 2)


# ============================================================================
# DERIVED SIGNALS (Manifesto Section 4: Key Metrics)
# ============================================================================

def calculate_durability_index(
    activities: List[Dict],
    lookback_days: int = 90
) -> Optional[float]:
    """
    Calculate Durability Index: Measures how well an athlete can handle 
    increasing volume without injury.
    
    Formula: (Total Volume / Injury-Free Days) * Consistency Factor
    
    Args:
        activities: List of activity dicts with distance_m, start_time
        lookback_days: Number of days to look back
        
    Returns:
        Durability Index (0-100+) or None if insufficient data
    """
    if not activities:
        return None
    
    # Filter to lookback period
    cutoff_date = _now_utc() - timedelta(days=lookback_days)
    recent_activities = [
        a for a in activities
        if isinstance(a.get('start_time'), datetime) and a['start_time'] >= cutoff_date
    ]
    
    if len(recent_activities) < 5:  # Need at least 5 activities
        return None
    
    # Calculate total volume
    total_distance = sum(float(a.get('distance_m', 0) or 0) for a in recent_activities)
    
    # Calculate consistency (coefficient of variation of weekly volume)
    weekly_volumes = {}
    for activity in recent_activities:
        week_start = activity['start_time'].date() - timedelta(days=activity['start_time'].weekday())
        if week_start not in weekly_volumes:
            weekly_volumes[week_start] = 0
        weekly_volumes[week_start] += float(activity.get('distance_m', 0) or 0)
    
    if len(weekly_volumes) < 3:
        return None
    
    volumes = list(weekly_volumes.values())
    avg_volume = sum(volumes) / len(volumes)
    variance = sum((v - avg_volume) ** 2 for v in volumes) / len(volumes)
    std_dev = math.sqrt(variance)
    cv = (std_dev / avg_volume * 100) if avg_volume > 0 else 100
    
    # Durability Index: Higher volume + lower variation = higher durability
    # Normalize: 0-100 scale
    volume_score = min(100, (total_distance / lookback_days) / 10)  # 10km/day = 100
    consistency_score = max(0, 100 - cv)  # Lower CV = higher consistency
    
    durability_index = (volume_score * 0.6 + consistency_score * 0.4)
    
    return round(durability_index, 2)


def calculate_recovery_half_life(
    activities: List[Dict],
    lookback_days: int = 30
) -> Optional[float]:
    """
    Calculate Recovery Half-Life: The amount of time it takes for an athlete 
    to recover post-intense effort.
    
    Measures time between high-intensity activities to baseline performance.
    
    Args:
        activities: List of activity dicts with performance_percentage, start_time, avg_hr, max_hr
        lookback_days: Number of days to analyze
        
    Returns:
        Recovery Half-Life in hours, or None if insufficient data
    """
    if not activities:
        return None
    
    # Filter to lookback period and sort by time
    cutoff_date = _now_utc() - timedelta(days=lookback_days)
    recent_activities = sorted(
        [a for a in activities if isinstance(a.get('start_time'), datetime) and _make_aware(a['start_time']) >= cutoff_date],
        key=lambda x: x['start_time']
    )
    
    if len(recent_activities) < 3:
        return None
    
    # Identify high-intensity activities (high HR or race candidates)
    high_intensity_activities = []
    for activity in recent_activities:
        max_hr = activity.get('max_hr')
        avg_hr = activity.get('avg_hr')
        is_race = activity.get('is_race_candidate', False)
        
        # High intensity = race candidate OR avg HR > 85% of max HR
        if is_race or (max_hr and avg_hr and avg_hr / max_hr > 0.85):
            high_intensity_activities.append(activity)
    
    if len(high_intensity_activities) < 2:
        return None
    
    # Calculate time between high-intensity activities
    recovery_times = []
    for i in range(len(high_intensity_activities) - 1):
        time_diff = high_intensity_activities[i + 1]['start_time'] - high_intensity_activities[i]['start_time']
        recovery_times.append(time_diff.total_seconds() / 3600)  # Convert to hours
    
    if not recovery_times:
        return None
    
    # Recovery Half-Life = median recovery time
    recovery_times.sort()
    median_recovery = recovery_times[len(recovery_times) // 2]
    
    return round(median_recovery, 1)


def calculate_consistency_index(
    activities: List[Dict],
    lookback_days: int = 90
) -> Optional[float]:
    """
    Calculate Consistency Index: Evaluates long-term training consistency 
    and its predictive value for success.
    
    Measures: Regularity of training, volume consistency, performance trends
    
    Args:
        activities: List of activity dicts with start_time, distance_m
        lookback_days: Number of days to analyze
        
    Returns:
        Consistency Index (0-100) or None if insufficient data
    """
    if not activities:
        return None
    
    # Filter to lookback period
    cutoff_date = _now_utc() - timedelta(days=lookback_days)
    recent_activities = [
        a for a in activities
        if isinstance(a.get('start_time'), datetime) and a['start_time'] >= cutoff_date
    ]
    
    if len(recent_activities) < 10:  # Need at least 10 activities
        return None
    
    # Factor 1: Training frequency (30% weight)
    # How many days per week on average
    activity_dates = set(a['start_time'].date() for a in recent_activities)
    days_with_activity = len(activity_dates)
    frequency_score = min(100, (days_with_activity / lookback_days) * 100 * 7)  # Normalize to weekly
    
    # Factor 2: Volume consistency (40% weight)
    # Coefficient of variation of weekly volume
    weekly_volumes = {}
    for activity in recent_activities:
        week_start = activity['start_time'].date() - timedelta(days=activity['start_time'].weekday())
        if week_start not in weekly_volumes:
            weekly_volumes[week_start] = 0
        weekly_volumes[week_start] += float(activity.get('distance_m', 0) or 0)
    
    if len(weekly_volumes) < 3:
        return None
    
    volumes = list(weekly_volumes.values())
    avg_volume = sum(volumes) / len(volumes)
    variance = sum((v - avg_volume) ** 2 for v in volumes) / len(volumes)
    std_dev = math.sqrt(variance)
    cv = (std_dev / avg_volume * 100) if avg_volume > 0 else 100
    volume_consistency_score = max(0, 100 - cv)  # Lower CV = higher consistency
    
    # Factor 3: Performance trend (30% weight)
    # Are performances improving, stable, or declining?
    performance_values = []
    for activity in recent_activities:
        perf = activity.get('performance_percentage')
        if perf:
            performance_values.append(perf)
    
    trend_score = 50.0  # Default neutral
    if len(performance_values) >= 5:
        # Simple linear trend
        first_half = performance_values[:len(performance_values)//2]
        second_half = performance_values[len(performance_values)//2:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        
        if avg_second > avg_first * 1.02:  # 2% improvement
            trend_score = 75.0
        elif avg_second > avg_first * 0.98:  # Within 2% = stable
            trend_score = 50.0
        else:
            trend_score = 25.0
    
    # Weighted combination
    consistency_index = (
        frequency_score * 0.3 +
        volume_consistency_score * 0.4 +
        trend_score * 0.3
    )
    
    return round(consistency_index, 2)


# ============================================================================
# RACE DETECTION (Existing Implementation)
# ============================================================================

RACE_DISTANCES = {
    'mile': (1500, 1700),
    '5k': (4900, 5400),
    '10k': (9800, 10700),
    '15k': (14700, 15400),
    '25k': (24500, 25500),
    'half_marathon': (20800, 21600),
    'marathon': (41500, 43500),
    '50k': (49000, 51000),
}

RACE_NAME_PATTERNS = [
    r'\brace\b', r'\bclassic\b', r'\bcharity\b',
    r'\bmarathon\b', r'\bhalf\b', r'\b5k\b', r'\b10k\b',
    r'\b\d+k\b', r'\bchip\s*time\b',
    r'\b(?:1st|2nd|3rd|\d+th)\b',
    r'\boverall\b', r'\bgrandmaster\b', r'\bags?\s*group\b',
    r'\bfinish(?:er)?\b', r'\bbib\b', r'\bcourse\b',
]


def _name_race_score(activity_name: Optional[str]) -> float:
    if not activity_name:
        return 0.0
    name_lower = activity_name.lower()
    matches = sum(1 for p in RACE_NAME_PATTERNS
                  if re.search(p, name_lower))
    if matches >= 3:
        return 1.0
    elif matches >= 2:
        return 0.8
    elif matches >= 1:
        return 0.5
    return 0.0


def detect_race_candidate(
    activity_pace: Optional[float],
    max_hr: Optional[int],
    avg_hr: Optional[int],
    splits: List[dict],
    distance_meters: float,
    duration_seconds: Optional[int],
    activity_name: Optional[str] = None,
) -> Tuple[bool, float]:
    """
    Detect if an activity is likely a race.

    Signals (weights): HR intensity 35%, pace consistency 25%,
    distance match 15%, name signals 15%, effort profile 10%.
    HR is not required — activities with name + distance + pace
    consistency can still qualify at a lower threshold.
    """
    confidence_score = 0.0
    has_hr = bool(max_hr and avg_hr and max_hr > 0)

    # Gate: must match a standard race distance
    matched_category = None
    for cat, (lo, hi) in RACE_DISTANCES.items():
        if lo <= distance_meters <= hi:
            matched_category = cat
            break

    if not matched_category:
        return False, 0.0

    is_short = matched_category in ('mile', '5k')

    # Signal 1: Heart Rate Intensity (35%)
    hr_score = 0.0
    if has_hr:
        hr_intensity = avg_hr / max_hr
        if is_short:
            if hr_intensity >= 0.93:
                hr_score = 1.0
            elif hr_intensity >= 0.90:
                hr_score = 0.7
            elif hr_intensity >= 0.88:
                hr_score = 0.4
        else:
            if hr_intensity >= 0.92:
                hr_score = 1.0
            elif hr_intensity >= 0.88:
                hr_score = 0.8
            elif hr_intensity >= 0.85:
                hr_score = 0.5
            elif hr_intensity >= 0.80:
                hr_score = 0.2
        confidence_score += hr_score * 0.35

    # Signal 2: Pace Consistency (25%)
    pace_score = 0.0
    if len(splits) >= 3:
        split_paces = []
        for split in splits:
            if split.get('distance') and split.get('moving_time'):
                dist_m = float(split['distance'])
                time_s = split['moving_time'] or split.get('elapsed_time', 0)
                if dist_m > 0 and time_s > 0:
                    miles = dist_m / 1609.34
                    minutes = time_s / 60.0
                    if miles > 0:
                        pace = minutes / miles
                        split_paces.append(pace)

        if len(split_paces) >= 3:
            avg_pace = sum(split_paces) / len(split_paces)
            variance = sum((p - avg_pace) ** 2 for p in split_paces) / len(split_paces)
            std_dev = math.sqrt(variance)
            cv = (std_dev / avg_pace) * 100 if avg_pace > 0 else 100

            if cv < 2:
                pace_score = 1.0
            elif cv < 4:
                pace_score = 0.8
            elif cv < 6:
                pace_score = 0.5
            else:
                pace_score = 0.2

            confidence_score += pace_score * 0.25

    # Signal 3: Distance Match (15%)
    confidence_score += 1.0 * 0.15

    # Signal 4: Name Signal (15%)
    name_score = _name_race_score(activity_name)
    confidence_score += name_score * 0.15

    # Signal 5: Effort Profile (10%)
    if len(splits) >= 4:
        first_half_hr = []
        second_half_hr = []
        midpoint = len(splits) // 2

        for i, split in enumerate(splits):
            hr = split.get('average_heartrate') or split.get('avg_hr')
            if hr:
                if i < midpoint:
                    first_half_hr.append(hr)
                else:
                    second_half_hr.append(hr)

        if first_half_hr and second_half_hr:
            avg_first = sum(first_half_hr) / len(first_half_hr)
            avg_second = sum(second_half_hr) / len(second_half_hr)

            if avg_second >= avg_first * 0.97:
                effort_score = 1.0
            elif avg_second >= avg_first * 0.93:
                effort_score = 0.7
            else:
                effort_score = 0.3

            confidence_score += effort_score * 0.1

    # Without HR: max possible = 0.65 (distance 0.15 + pace 0.25 + name 0.15 + effort 0.10).
    # With HR: max = 1.0. Thresholds calibrated accordingly.
    if has_hr:
        threshold = 0.85 if is_short else 0.80
    else:
        threshold = 0.50

    is_race = confidence_score >= threshold

    return is_race, round(confidence_score, 3)
