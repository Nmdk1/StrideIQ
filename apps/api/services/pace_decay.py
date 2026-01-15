"""
Pace Decay Analysis Service

Quantifies pace fade in races and compares to historical patterns.
Provides insights on pacing strategy and potential causes.

ADR-012: Pace Decay Analysis
"""

from datetime import date, datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from uuid import UUID
from sqlalchemy.orm import Session
import math
import statistics


class SplitPattern(str, Enum):
    """Classification of pacing pattern."""
    NEGATIVE = "negative"           # Faster in second half (excellent)
    EVEN = "even"                   # Within ±2%
    MILD_POSITIVE = "mild_positive"     # 2-5% slower
    MODERATE_POSITIVE = "moderate_positive"  # 5-10% slower
    SEVERE_POSITIVE = "severe_positive"      # >10% slower


class ConfidenceLevel(str, Enum):
    """Confidence level for analysis."""
    HIGH = "high"           # Many splits, consistent data
    MODERATE = "moderate"   # Sufficient data
    LOW = "low"             # Limited data
    INSUFFICIENT = "insufficient"  # Cannot analyze


@dataclass
class SplitData:
    """Individual split data."""
    split_number: int
    distance_m: float
    elapsed_time_s: float
    pace_s_per_km: float
    pace_s_per_mile: float
    average_hr: Optional[int] = None
    is_outlier: bool = False


@dataclass
class DecayMetrics:
    """Core pace decay metrics."""
    first_half_pace_s_per_km: float
    second_half_pace_s_per_km: float
    half_split_decay_pct: float       # Positive = slowed down
    
    first_third_pace_s_per_km: float
    last_third_pace_s_per_km: float
    third_split_decay_pct: float
    
    peak_pace_s_per_km: float         # Fastest segment
    final_segment_pace_s_per_km: float  # Last 20% average
    peak_to_final_decay_pct: float
    
    overall_pattern: SplitPattern
    total_distance_m: float
    total_time_s: float
    splits_used: int
    outliers_excluded: int


@dataclass
class HistoricalComparison:
    """Comparison to athlete's historical patterns."""
    typical_decay_pct: float
    current_decay_pct: float
    deviation_pct: float              # How different from typical
    deviation_direction: str          # "better", "worse", "typical"
    sample_size: int                  # Number of historical races
    insight: str


@dataclass
class DecayAnalysis:
    """Complete decay analysis for an activity."""
    activity_id: str
    activity_name: Optional[str]
    activity_date: Optional[date]
    is_race: bool
    metrics: Optional[DecayMetrics]
    splits: List[SplitData]
    comparison: Optional[HistoricalComparison]
    insights: List[str]
    warnings: List[str]
    confidence: ConfidenceLevel


@dataclass
class DecayProfile:
    """Athlete's decay profile across distances."""
    athlete_id: str
    by_distance: Dict[str, Dict]      # {"5K": {avg_decay, races, ...}}
    overall_avg_decay: float
    total_races_analyzed: int
    trend: str                        # "improving", "stable", "declining"
    insights: List[str]


# Minimum splits needed for analysis
MIN_SPLITS_FOR_ANALYSIS = 3
MIN_SPLITS_FOR_THIRDS = 6

# Outlier detection threshold (percentage from median pace)
OUTLIER_THRESHOLD_PCT = 40.0

# Distance category thresholds (meters)
DISTANCE_CATEGORIES = {
    "5K": (4500, 5500),
    "10K": (9500, 10500),
    "10 Mile": (15500, 16500),
    "Half Marathon": (20500, 21500),
    "Marathon": (41000, 43000),
}


def calculate_pace_from_split(distance_m: float, elapsed_time_s: float) -> Tuple[float, float]:
    """
    Calculate pace from distance and time.
    
    Returns:
        (pace_s_per_km, pace_s_per_mile)
    """
    if distance_m <= 0 or elapsed_time_s <= 0:
        return (0.0, 0.0)
    
    pace_s_per_km = elapsed_time_s / (distance_m / 1000)
    pace_s_per_mile = elapsed_time_s / (distance_m / 1609.34)
    
    return (pace_s_per_km, pace_s_per_mile)


def detect_outliers(splits: List[SplitData], threshold_pct: float = OUTLIER_THRESHOLD_PCT) -> List[SplitData]:
    """
    Detect outlier splits (e.g., bathroom breaks, wrong GPS).
    
    Returns splits with is_outlier flag set.
    """
    if len(splits) < 3:
        return splits
    
    paces = [s.pace_s_per_km for s in splits if s.pace_s_per_km > 0]
    if len(paces) < 2:
        return splits
    
    median_pace = statistics.median(paces)
    
    result = []
    for split in splits:
        is_outlier = False
        if split.pace_s_per_km > 0 and median_pace > 0:
            deviation_pct = abs((split.pace_s_per_km - median_pace) / median_pace) * 100
            is_outlier = deviation_pct > threshold_pct
        
        result.append(SplitData(
            split_number=split.split_number,
            distance_m=split.distance_m,
            elapsed_time_s=split.elapsed_time_s,
            pace_s_per_km=split.pace_s_per_km,
            pace_s_per_mile=split.pace_s_per_mile,
            average_hr=split.average_hr,
            is_outlier=is_outlier
        ))
    
    return result


def calculate_segment_average_pace(splits: List[SplitData], exclude_outliers: bool = True) -> float:
    """Calculate average pace for a segment of splits."""
    valid_splits = [s for s in splits if not (exclude_outliers and s.is_outlier) and s.pace_s_per_km > 0]
    
    if not valid_splits:
        return 0.0
    
    total_distance = sum(s.distance_m for s in valid_splits)
    total_time = sum(s.elapsed_time_s for s in valid_splits)
    
    if total_distance <= 0:
        return 0.0
    
    return total_time / (total_distance / 1000)


def classify_split_pattern(decay_pct: float) -> SplitPattern:
    """
    Classify the pacing pattern based on decay percentage.
    
    Args:
        decay_pct: Positive = slowed down, Negative = sped up
    """
    if decay_pct < -2:
        return SplitPattern.NEGATIVE
    elif -2 <= decay_pct <= 2:
        return SplitPattern.EVEN
    elif 2 < decay_pct <= 5:
        return SplitPattern.MILD_POSITIVE
    elif 5 < decay_pct <= 10:
        return SplitPattern.MODERATE_POSITIVE
    else:
        return SplitPattern.SEVERE_POSITIVE


def calculate_decay_metrics(splits: List[SplitData]) -> Optional[DecayMetrics]:
    """
    Calculate comprehensive decay metrics from splits.
    
    Args:
        splits: List of SplitData with outliers already flagged
    
    Returns:
        DecayMetrics or None if insufficient data
    """
    # Filter valid splits
    valid_splits = [s for s in splits if not s.is_outlier and s.pace_s_per_km > 0]
    
    if len(valid_splits) < MIN_SPLITS_FOR_ANALYSIS:
        return None
    
    n = len(valid_splits)
    outliers_excluded = len(splits) - len(valid_splits)
    
    # Calculate total distance and time
    total_distance = sum(s.distance_m for s in valid_splits)
    total_time = sum(s.elapsed_time_s for s in valid_splits)
    
    # Half split analysis
    mid = n // 2
    first_half = valid_splits[:mid]
    second_half = valid_splits[mid:]
    
    first_half_pace = calculate_segment_average_pace(first_half)
    second_half_pace = calculate_segment_average_pace(second_half)
    
    half_decay = 0.0
    if first_half_pace > 0:
        half_decay = ((second_half_pace - first_half_pace) / first_half_pace) * 100
    
    # Third split analysis
    if n >= MIN_SPLITS_FOR_THIRDS:
        third = n // 3
        first_third = valid_splits[:third]
        last_third = valid_splits[-third:]
    else:
        first_third = first_half
        last_third = second_half
    
    first_third_pace = calculate_segment_average_pace(first_third)
    last_third_pace = calculate_segment_average_pace(last_third)
    
    third_decay = 0.0
    if first_third_pace > 0:
        third_decay = ((last_third_pace - first_third_pace) / first_third_pace) * 100
    
    # Peak to final analysis
    paces = [s.pace_s_per_km for s in valid_splits]
    peak_pace = min(paces)  # Fastest = lowest pace value
    
    # Final 20% (at least 1 split)
    final_count = max(1, n // 5)
    final_splits = valid_splits[-final_count:]
    final_pace = calculate_segment_average_pace(final_splits)
    
    peak_to_final_decay = 0.0
    if peak_pace > 0:
        peak_to_final_decay = ((final_pace - peak_pace) / peak_pace) * 100
    
    # Classify overall pattern (use half split as primary)
    pattern = classify_split_pattern(half_decay)
    
    return DecayMetrics(
        first_half_pace_s_per_km=first_half_pace,
        second_half_pace_s_per_km=second_half_pace,
        half_split_decay_pct=round(half_decay, 2),
        first_third_pace_s_per_km=first_third_pace,
        last_third_pace_s_per_km=last_third_pace,
        third_split_decay_pct=round(third_decay, 2),
        peak_pace_s_per_km=peak_pace,
        final_segment_pace_s_per_km=final_pace,
        peak_to_final_decay_pct=round(peak_to_final_decay, 2),
        overall_pattern=pattern,
        total_distance_m=total_distance,
        total_time_s=total_time,
        splits_used=len(valid_splits),
        outliers_excluded=outliers_excluded
    )


def compare_to_history(
    current_decay: float,
    historical_decays: List[float],
    distance_category: Optional[str] = None
) -> Optional[HistoricalComparison]:
    """
    Compare current decay to historical patterns.
    
    Args:
        current_decay: Current race decay percentage
        historical_decays: List of past decay percentages
        distance_category: Optional distance for context
    
    Returns:
        HistoricalComparison or None if insufficient history
    """
    if len(historical_decays) < 2:
        return None
    
    typical = statistics.mean(historical_decays)
    std_dev = statistics.stdev(historical_decays) if len(historical_decays) > 1 else 0
    
    deviation = current_decay - typical
    deviation_pct = abs(deviation)
    
    # Determine direction
    if deviation_pct <= 1.5:
        direction = "typical"
        insight = "Decay matches your typical pattern."
    elif deviation < 0:
        direction = "better"
        insight = f"Less decay than usual — {abs(deviation):.1f}% better than your typical {typical:.1f}%."
    else:
        direction = "worse"
        insight = f"More decay than usual — {deviation:.1f}% more than your typical {typical:.1f}%."
    
    if distance_category:
        insight = f"{distance_category}: {insight}"
    
    return HistoricalComparison(
        typical_decay_pct=round(typical, 2),
        current_decay_pct=round(current_decay, 2),
        deviation_pct=round(deviation_pct, 2),
        deviation_direction=direction,
        sample_size=len(historical_decays),
        insight=insight
    )


def format_pace(seconds_per_km: float) -> str:
    """Format pace as MM:SS/km."""
    if seconds_per_km <= 0:
        return "N/A"
    
    minutes = int(seconds_per_km // 60)
    secs = int(seconds_per_km % 60)
    return f"{minutes}:{secs:02d}/km"


def generate_insights(
    metrics: DecayMetrics,
    is_race: bool,
    comparison: Optional[HistoricalComparison]
) -> List[str]:
    """Generate human-readable insights from decay metrics."""
    insights = []
    
    activity_type = "Race" if is_race else "Run"
    
    # Primary decay insight
    if metrics.overall_pattern == SplitPattern.NEGATIVE:
        insights.append(
            f"Strong negative split — finished {abs(metrics.half_split_decay_pct):.1f}% faster than you started. Excellent pacing."
        )
    elif metrics.overall_pattern == SplitPattern.EVEN:
        insights.append(
            f"Even split — pace varied only {abs(metrics.half_split_decay_pct):.1f}%. Solid pacing execution."
        )
    elif metrics.overall_pattern == SplitPattern.MILD_POSITIVE:
        insights.append(
            f"Mild positive split — slowed {metrics.half_split_decay_pct:.1f}% in second half. Normal range."
        )
    elif metrics.overall_pattern == SplitPattern.MODERATE_POSITIVE:
        insights.append(
            f"Pace decayed {metrics.half_split_decay_pct:.1f}% — consider starting slightly slower or fueling earlier."
        )
    else:  # SEVERE_POSITIVE
        insights.append(
            f"Significant pace fade — {metrics.half_split_decay_pct:.1f}% slower in second half. May indicate pacing, fueling, or fitness issue."
        )
    
    # Peak to final decay
    if metrics.peak_to_final_decay_pct > 15:
        insights.append(
            f"Dropped {metrics.peak_to_final_decay_pct:.1f}% from peak pace to final segment — common in longer races."
        )
    
    # Historical comparison
    if comparison:
        insights.append(comparison.insight)
    
    # Outlier note
    if metrics.outliers_excluded > 0:
        insights.append(
            f"Excluded {metrics.outliers_excluded} outlier split(s) from analysis."
        )
    
    return insights


def get_distance_category(distance_m: float) -> Optional[str]:
    """Get distance category name from distance."""
    for category, (low, high) in DISTANCE_CATEGORIES.items():
        if low <= distance_m <= high:
            return category
    
    if distance_m < 4500:
        return "Short"
    elif distance_m > 43000:
        return "Ultra"
    else:
        return "Other"


def get_activity_pace_decay(
    activity_id: str,
    db: Session
) -> DecayAnalysis:
    """
    Analyze pace decay for a specific activity.
    
    Args:
        activity_id: Activity UUID
        db: Database session
    
    Returns:
        DecayAnalysis with metrics and insights
    """
    from models import Activity, ActivitySplit
    
    warnings = []
    
    # Get activity
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    
    if not activity:
        return DecayAnalysis(
            activity_id=activity_id,
            activity_name=None,
            activity_date=None,
            is_race=False,
            metrics=None,
            splits=[],
            comparison=None,
            insights=[],
            warnings=["Activity not found."],
            confidence=ConfidenceLevel.INSUFFICIENT
        )
    
    # Get splits
    splits_query = db.query(ActivitySplit).filter(
        ActivitySplit.activity_id == activity_id
    ).order_by(ActivitySplit.split_number).all()
    
    if len(splits_query) < MIN_SPLITS_FOR_ANALYSIS:
        return DecayAnalysis(
            activity_id=activity_id,
            activity_name=activity.name,
            activity_date=activity.start_time.date() if activity.start_time else None,
            is_race=activity.is_race or False,
            metrics=None,
            splits=[],
            comparison=None,
            insights=[],
            warnings=[f"Need at least {MIN_SPLITS_FOR_ANALYSIS} splits for decay analysis. Found {len(splits_query)}."],
            confidence=ConfidenceLevel.INSUFFICIENT
        )
    
    # Convert to SplitData
    split_data = []
    for s in splits_query:
        distance = float(s.distance) if s.distance else 0
        time = float(s.elapsed_time) if s.elapsed_time else 0
        pace_km, pace_mile = calculate_pace_from_split(distance, time)
        
        split_data.append(SplitData(
            split_number=s.split_number,
            distance_m=distance,
            elapsed_time_s=time,
            pace_s_per_km=pace_km,
            pace_s_per_mile=pace_mile,
            average_hr=s.average_heartrate
        ))
    
    # Detect outliers
    split_data = detect_outliers(split_data)
    
    # Calculate metrics
    metrics = calculate_decay_metrics(split_data)
    
    if not metrics:
        return DecayAnalysis(
            activity_id=activity_id,
            activity_name=activity.name,
            activity_date=activity.start_time.date() if activity.start_time else None,
            is_race=activity.is_race or False,
            metrics=None,
            splits=split_data,
            comparison=None,
            insights=[],
            warnings=["Could not calculate decay metrics — insufficient valid splits."],
            confidence=ConfidenceLevel.INSUFFICIENT
        )
    
    # Get historical comparison (for races)
    comparison = None
    if activity.is_race and activity.athlete_id:
        historical = _get_historical_decays(
            str(activity.athlete_id),
            metrics.total_distance_m,
            str(activity_id),
            db
        )
        if historical:
            comparison = compare_to_history(
                metrics.half_split_decay_pct,
                historical,
                get_distance_category(metrics.total_distance_m)
            )
    
    # Generate insights
    insights = generate_insights(metrics, activity.is_race or False, comparison)
    
    # Determine confidence
    if len(split_data) >= 10 and metrics.outliers_excluded <= 1:
        confidence = ConfidenceLevel.HIGH
    elif len(split_data) >= MIN_SPLITS_FOR_THIRDS:
        confidence = ConfidenceLevel.MODERATE
    else:
        confidence = ConfidenceLevel.LOW
    
    return DecayAnalysis(
        activity_id=activity_id,
        activity_name=activity.name,
        activity_date=activity.start_time.date() if activity.start_time else None,
        is_race=activity.is_race or False,
        metrics=metrics,
        splits=split_data,
        comparison=comparison,
        insights=insights,
        warnings=warnings,
        confidence=confidence
    )


def _get_historical_decays(
    athlete_id: str,
    target_distance_m: float,
    exclude_activity_id: str,
    db: Session,
    tolerance_pct: float = 15.0
) -> List[float]:
    """Get historical decay percentages for similar distance races."""
    from models import Activity, ActivitySplit
    
    # Get athlete's past races at similar distance
    low = target_distance_m * (1 - tolerance_pct / 100)
    high = target_distance_m * (1 + tolerance_pct / 100)
    
    # Use race detection fields
    from sqlalchemy import or_, and_
    races = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        or_(
            Activity.user_verified_race == True,
            Activity.workout_type == 'race',
            and_(Activity.is_race_candidate == True, Activity.race_confidence >= 0.7)
        ),
        Activity.distance_m >= low,
        Activity.distance_m <= high,
        Activity.id != exclude_activity_id
    ).order_by(Activity.start_time.desc()).limit(20).all()
    
    decays = []
    for race in races:
        splits = db.query(ActivitySplit).filter(
            ActivitySplit.activity_id == race.id
        ).order_by(ActivitySplit.split_number).all()
        
        if len(splits) >= MIN_SPLITS_FOR_ANALYSIS:
            split_data = []
            for s in splits:
                distance = float(s.distance) if s.distance else 0
                time = float(s.elapsed_time) if s.elapsed_time else 0
                pace_km, _ = calculate_pace_from_split(distance, time)
                split_data.append(SplitData(
                    split_number=s.split_number,
                    distance_m=distance,
                    elapsed_time_s=time,
                    pace_s_per_km=pace_km,
                    pace_s_per_mile=0,
                    average_hr=None
                ))
            
            split_data = detect_outliers(split_data)
            metrics = calculate_decay_metrics(split_data)
            if metrics:
                decays.append(metrics.half_split_decay_pct)
    
    return decays


def get_athlete_decay_profile(
    athlete_id: str,
    db: Session
) -> DecayProfile:
    """
    Build decay profile across all athlete's races.
    
    Args:
        athlete_id: Athlete UUID
        db: Database session
    
    Returns:
        DecayProfile with trends and insights
    """
    from models import Activity, ActivitySplit
    
    # Get all races using race detection fields
    from sqlalchemy import or_, and_
    races = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        or_(
            Activity.user_verified_race == True,
            Activity.workout_type == 'race',
            and_(Activity.is_race_candidate == True, Activity.race_confidence >= 0.7)
        )
    ).order_by(Activity.start_time.desc()).limit(100).all()
    
    by_distance = {}
    all_decays = []
    recent_decays = []  # Last 10 races for trend
    
    for i, race in enumerate(races):
        splits = db.query(ActivitySplit).filter(
            ActivitySplit.activity_id == race.id
        ).order_by(ActivitySplit.split_number).all()
        
        if len(splits) < MIN_SPLITS_FOR_ANALYSIS:
            continue
        
        split_data = []
        for s in splits:
            distance = float(s.distance) if s.distance else 0
            time = float(s.elapsed_time) if s.elapsed_time else 0
            pace_km, _ = calculate_pace_from_split(distance, time)
            split_data.append(SplitData(
                split_number=s.split_number,
                distance_m=distance,
                elapsed_time_s=time,
                pace_s_per_km=pace_km,
                pace_s_per_mile=0,
                average_hr=None
            ))
        
        split_data = detect_outliers(split_data)
        metrics = calculate_decay_metrics(split_data)
        
        if metrics:
            decay = metrics.half_split_decay_pct
            all_decays.append(decay)
            
            if i < 10:
                recent_decays.append(decay)
            
            category = get_distance_category(metrics.total_distance_m)
            if category not in by_distance:
                by_distance[category] = {
                    "decays": [],
                    "avg_decay": 0,
                    "best_decay": 100,
                    "worst_decay": -100,
                    "races": 0
                }
            
            by_distance[category]["decays"].append(decay)
            by_distance[category]["races"] += 1
    
    # Calculate averages per distance
    for category in by_distance:
        decays = by_distance[category]["decays"]
        if decays:
            by_distance[category]["avg_decay"] = round(statistics.mean(decays), 2)
            by_distance[category]["best_decay"] = round(min(decays), 2)
            by_distance[category]["worst_decay"] = round(max(decays), 2)
        del by_distance[category]["decays"]  # Remove raw data
    
    # Calculate trend
    trend = "stable"
    if len(recent_decays) >= 3 and len(all_decays) >= 6:
        recent_avg = statistics.mean(recent_decays)
        older_decays = all_decays[10:] if len(all_decays) > 10 else all_decays[3:]
        if older_decays:
            older_avg = statistics.mean(older_decays)
            if recent_avg < older_avg - 2:
                trend = "improving"
            elif recent_avg > older_avg + 2:
                trend = "declining"
    
    # Generate insights
    insights = []
    overall_avg = statistics.mean(all_decays) if all_decays else 0
    
    if overall_avg < 3:
        insights.append("Excellent pacing discipline — you typically maintain pace well.")
    elif overall_avg < 6:
        insights.append("Solid pacing — mild decay is normal for most runners.")
    elif overall_avg < 10:
        insights.append("Moderate pace fade — consider starting conservatively or fueling earlier.")
    else:
        insights.append("Significant pace decay pattern — opportunity to improve race execution.")
    
    if trend == "improving":
        insights.append("Pacing is improving in recent races. Keep it up.")
    elif trend == "declining":
        insights.append("Decay has increased in recent races. May need pacing or fueling adjustment.")
    
    return DecayProfile(
        athlete_id=athlete_id,
        by_distance=by_distance,
        overall_avg_decay=round(overall_avg, 2),
        total_races_analyzed=len(all_decays),
        trend=trend,
        insights=insights
    )


def to_dict(analysis: DecayAnalysis) -> Dict:
    """Convert DecayAnalysis to dictionary for API response."""
    metrics_dict = None
    if analysis.metrics:
        metrics_dict = {
            "first_half_pace": format_pace(analysis.metrics.first_half_pace_s_per_km),
            "second_half_pace": format_pace(analysis.metrics.second_half_pace_s_per_km),
            "half_split_decay_pct": analysis.metrics.half_split_decay_pct,
            "first_third_pace": format_pace(analysis.metrics.first_third_pace_s_per_km),
            "last_third_pace": format_pace(analysis.metrics.last_third_pace_s_per_km),
            "third_split_decay_pct": analysis.metrics.third_split_decay_pct,
            "peak_pace": format_pace(analysis.metrics.peak_pace_s_per_km),
            "final_segment_pace": format_pace(analysis.metrics.final_segment_pace_s_per_km),
            "peak_to_final_decay_pct": analysis.metrics.peak_to_final_decay_pct,
            "overall_pattern": analysis.metrics.overall_pattern.value,
            "splits_used": analysis.metrics.splits_used,
            "outliers_excluded": analysis.metrics.outliers_excluded
        }
    
    splits_list = []
    for s in analysis.splits:
        splits_list.append({
            "split_number": s.split_number,
            "distance_m": s.distance_m,
            "elapsed_time_s": s.elapsed_time_s,
            "pace_per_km": format_pace(s.pace_s_per_km),
            "pace_per_km_seconds": round(s.pace_s_per_km, 1),
            "average_hr": s.average_hr,
            "is_outlier": s.is_outlier
        })
    
    comparison_dict = None
    if analysis.comparison:
        comparison_dict = {
            "typical_decay_pct": analysis.comparison.typical_decay_pct,
            "current_decay_pct": analysis.comparison.current_decay_pct,
            "deviation_pct": analysis.comparison.deviation_pct,
            "deviation_direction": analysis.comparison.deviation_direction,
            "sample_size": analysis.comparison.sample_size,
            "insight": analysis.comparison.insight
        }
    
    return {
        "activity_id": analysis.activity_id,
        "activity_name": analysis.activity_name,
        "activity_date": analysis.activity_date.isoformat() if analysis.activity_date else None,
        "is_race": analysis.is_race,
        "metrics": metrics_dict,
        "splits": splits_list,
        "comparison": comparison_dict,
        "insights": analysis.insights,
        "warnings": analysis.warnings,
        "confidence": analysis.confidence.value
    }


def profile_to_dict(profile: DecayProfile) -> Dict:
    """Convert DecayProfile to dictionary for API response."""
    return {
        "athlete_id": profile.athlete_id,
        "by_distance": profile.by_distance,
        "overall_avg_decay": profile.overall_avg_decay,
        "total_races_analyzed": profile.total_races_analyzed,
        "trend": profile.trend,
        "insights": profile.insights
    }
