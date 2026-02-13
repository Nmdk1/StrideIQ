"""
Efficiency Analytics Service

Calculates efficiency trends, stability metrics, and load-response relationships.
This is the core differentiator - showing athletes if they're getting fitter or just accumulating work.

V2 Enhancement (ADR-008): Adds statistical significance testing for trends.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from collections import defaultdict
from models import Activity, Athlete, ActivitySplit
from services.efficiency_calculation import calculate_activity_efficiency_with_decoupling
from services.efficiency_trending import (
    analyze_efficiency_trend,
    calculate_efficiency_percentile,
    estimate_days_to_pr_efficiency,
    to_dict as trend_to_dict
)


def bulk_load_splits_for_activities(
    activity_ids: List[str],
    db: Session
) -> Dict[str, List[ActivitySplit]]:
    """
    Bulk load all splits for multiple activities in a single query.
    Returns a dict mapping activity_id -> list of splits (ordered by split_number).
    
    This eliminates N+1 query problems.
    """
    if not activity_ids:
        return {}
    
    # Load all splits for these activities in one query
    splits = db.query(ActivitySplit).filter(
        ActivitySplit.activity_id.in_(activity_ids)
    ).order_by(ActivitySplit.activity_id, ActivitySplit.split_number).all()
    
    # Group by activity_id
    splits_by_activity = defaultdict(list)
    for split in splits:
        splits_by_activity[str(split.activity_id)].append(split)
    
    return dict(splits_by_activity)


def calculate_efficiency_factor(
    pace_per_mile: Optional[float],
    avg_hr: Optional[int],
    max_hr: Optional[int] = None
) -> Optional[float]:
    """
    Calculate Efficiency Factor (EF): Pace @ HR or HR @ Pace
    
    EF = speed / HR

    Higher EF = more efficient (more speed at the same cardiovascular cost).
    
    If we don't have max HR, we use raw HR (less accurate but still useful)
    """
    if pace_per_mile is None or avg_hr is None:
        return None
    
    if pace_per_mile <= 0 or avg_hr <= 0:
        return None
    
    # Convert pace (min/mi) to speed (m/s)
    pace_sec_per_mile = pace_per_mile * 60.0
    speed_mps = 1609.34 / pace_sec_per_mile
    ef = speed_mps / avg_hr
    return round(ef, 4)


def is_quality_activity(activity: Activity) -> bool:
    """
    Filter out garbage data:
    - Short runs (< 1 mile or < 5 minutes)
    - Missing critical data (pace or HR)
    - Suspicious data (pace too fast/slow, HR too high/low)
    """
    # Must have distance and duration
    if not activity.distance_m or not activity.duration_s:
        return False
    
    # Minimum distance: 1 mile (1609 meters)
    if activity.distance_m < 1609:
        return False
    
    # Minimum duration: 5 minutes
    if activity.duration_s < 300:
        return False
    
    # Must have pace or speed
    if not activity.average_speed and not activity.pace_per_mile:
        return False
    
    # Must have HR for efficiency calculation
    if not activity.avg_hr:
        return False
    
    # Sanity checks
    pace = activity.pace_per_mile
    if pace:
        if pace < 4.0 or pace > 15.0:
            return False
    
    # HR should be between 100 and 220
    if activity.avg_hr < 100 or activity.avg_hr > 220:
        return False
    
    return True


def calculate_rolling_average(values: List[float], window: int = 7) -> List[Optional[float]]:
    """
    Calculate rolling average with None for insufficient data.
    
    For longer windows (30+ days), we need fewer points to be meaningful
    since activities are sparse. For 30-day window, we might only have 8-12 runs.
    """
    result = []
    for i in range(len(values)):
        start_idx = max(0, i - window + 1)
        window_values = values[start_idx:i + 1]
        
        # For longer windows, require fewer points (proportional to window size)
        # 7-day: need at least 3 points
        # 30-day: need at least 3 points (might only have 8-12 runs in 30 days)
        # 60-day: need at least 4 points
        # 90-day+: need at least 5 points
        min_points = max(3, min(5, window // 20))
        
        if len(window_values) >= min_points:
            result.append(sum(window_values) / len(window_values))
        else:
            result.append(None)
    return result


def calculate_stability_metrics(
    activities: List[Activity],
    date_range: Tuple[datetime, datetime],
    db: Session
) -> Dict:
    """
    Calculate stability/repeatability metrics:
    - Variance of similar-effort runs
    - Consistency score
    
    Uses workout_type + intensity_score for classification, NOT HR zones.
    A half marathon PR at 152 HR is HARD. A 5K race at 175 HR is HARD.
    Both are maximal efforts regardless of absolute HR.
    """
    if len(activities) < 3:
        return {
            "consistency_score": None,
            "variance": None,
            "sample_size": len(activities)
        }
    
    # Hard workout types (quality sessions, races)
    # Includes both base keywords and full enum values from WorkoutClassifier
    HARD_TYPES = {
        'race', 'interval', 'intervals', 'tempo', 'threshold', 
        'vo2max', 'speed', 'fartlek', 'repetition', 'cruise_intervals',
        'race_pace', 'marathon_pace', 'half_marathon_pace',
        # Full enum values from WorkoutClassifier
        'threshold_run', 'tempo_run', 'tempo_intervals', 
        'vo2max_intervals', 'track_workout', 'repetitions',
        'hill_sprints', 'hill_repetitions', 'tune_up_race', 'race_simulation'
    }
    
    # Moderate workout types (aerobic stress but not maximal)
    MODERATE_TYPES = {'long_run', 'progression_run', 'steady_state', 
                      'moderate_run', 'aerobic_threshold', 'medium_long_run',
                      'fast_finish_long_run', 'negative_split_run', 'goal_pace_run'}
    
    # Easy workout types
    EASY_TYPES = {'easy_run', 'recovery', 'recovery_run', 'aerobic_run', 
                  'warm_up', 'cool_down', 'shakeout', 'strides'}
    
    easy_runs = []
    moderate_runs = []
    hard_runs = []
    
    for activity in activities:
        wt = (activity.workout_type or '').lower().strip()
        intensity = activity.intensity_score or 0
        
        # Classification priority:
        # 1. Intensity score >= 70 → HARD (race efforts, quality sessions)
        # 2. Workout type in HARD_TYPES → HARD
        # 3. Workout type in MODERATE_TYPES → MODERATE
        # 4. Intensity score >= 50 and long_run → MODERATE
        # 5. Everything else → EASY
        
        if intensity >= 70 or wt in HARD_TYPES:
            hard_runs.append(activity)
        elif wt in MODERATE_TYPES or (wt == 'long_run' and intensity >= 50):
            moderate_runs.append(activity)
        elif wt in EASY_TYPES or intensity < 50:
            easy_runs.append(activity)
        else:
            # Default: use intensity score as tiebreaker
            if intensity >= 60:
                moderate_runs.append(activity)
            else:
                easy_runs.append(activity)
    
    # Calculate variance for each effort level
    def calculate_effort_variance(runs: List[Activity], db: Session) -> Optional[float]:
        if len(runs) < 3:
            return None
        
        # Bulk load splits for all runs (eliminates N+1)
        run_ids = [str(run.id) for run in runs]
        splits_by_activity = bulk_load_splits_for_activities(run_ids, db)
        
        efficiencies = []
        for run in runs:
            # Get splits from bulk-loaded dict
            splits = splits_by_activity.get(str(run.id), [])
            
            # Calculate efficiency with GAP
            efficiency_data = calculate_activity_efficiency_with_decoupling(
                activity=run,
                splits=splits,
                max_hr=None
            )
            
            ef = efficiency_data.get("efficiency_factor")
            if ef:
                efficiencies.append(ef)
        
        if len(efficiencies) < 3:
            return None
        
        mean = sum(efficiencies) / len(efficiencies)
        variance = sum((x - mean) ** 2 for x in efficiencies) / len(efficiencies)
        return variance
    
    easy_variance = calculate_effort_variance(easy_runs, db)
    moderate_variance = calculate_effort_variance(moderate_runs, db)
    hard_variance = calculate_effort_variance(hard_runs, db)
    
    # Overall consistency score (lower variance = higher consistency)
    variances = [v for v in [easy_variance, moderate_variance, hard_variance] if v is not None]
    if variances:
        avg_variance = sum(variances) / len(variances)
        # Normalize to 0-100 score (lower variance = higher score)
        consistency_score = max(0, 100 - (avg_variance * 10))
    else:
        consistency_score = None
        avg_variance = None
    
    return {
        "consistency_score": round(consistency_score, 1) if consistency_score else None,
        "variance": round(avg_variance, 2) if avg_variance else None,
        "sample_size": len(activities),
        "easy_runs": len(easy_runs),
        "moderate_runs": len(moderate_runs),
        "hard_runs": len(hard_runs)
    }


def calculate_load_response(
    activities: List[Activity],
    db: Session,
    weeks: int = 4
) -> List[Dict]:
    """
    Calculate load → response relationship:
    - Weekly load (distance, time)
    - Weekly efficiency delta
    - Identify productive vs wasted vs harmful load
    """
    if len(activities) < 7:  # Need at least a week of data
        return []
    
    # Group by week
    weekly_data = {}
    
    for activity in activities:
        week_start = activity.start_time.date() - timedelta(days=activity.start_time.weekday())
        week_key = week_start.isoformat()
        
        if week_key not in weekly_data:
            weekly_data[week_key] = {
                "week_start": week_key,
                "activities": [],
                "total_distance_m": 0,
                "total_duration_s": 0,
                "efficiencies": []
            }
        
        weekly_data[week_key]["activities"].append(activity)
        weekly_data[week_key]["total_distance_m"] += activity.distance_m or 0
        weekly_data[week_key]["total_duration_s"] += activity.duration_s or 0
    
    # Bulk load splits for all activities (eliminates N+1)
    activity_ids = [str(a.id) for a in activities]
    splits_by_activity = bulk_load_splits_for_activities(activity_ids, db)
    
    # Calculate efficiencies using bulk-loaded splits
    for activity in activities:
        week_start = activity.start_time.date() - timedelta(days=activity.start_time.weekday())
        week_key = week_start.isoformat()
        
        # Get splits from bulk-loaded dict
        splits = splits_by_activity.get(str(activity.id), [])
        
        # Calculate efficiency with GAP
        efficiency_data = calculate_activity_efficiency_with_decoupling(
            activity=activity,
            splits=splits,
            max_hr=None
        )
        
        ef = efficiency_data.get("efficiency_factor")
        if ef:
            weekly_data[week_key]["efficiencies"].append(ef)
    
    # Calculate weekly metrics
    weeks_list = sorted(weekly_data.keys())
    result = []
    
    for i, week_key in enumerate(weeks_list):
        week_data = weekly_data[week_key]
        
        avg_efficiency = None
        if week_data["efficiencies"]:
            avg_efficiency = sum(week_data["efficiencies"]) / len(week_data["efficiencies"])
        
        # Calculate efficiency delta from previous week
        efficiency_delta = None
        if i > 0:
            prev_week_key = weeks_list[i - 1]
            prev_week_data = weekly_data[prev_week_key]
            if prev_week_data["efficiencies"]:
                prev_avg = sum(prev_week_data["efficiencies"]) / len(prev_week_data["efficiencies"])
                if avg_efficiency:
                    efficiency_delta = avg_efficiency - prev_avg  # Positive = improvement
        
        # Classify load type — neutral labels because pace/HR ratio is
        # directionally ambiguous.  See Athlete Trust Safety Contract.
        load_type = "neutral"
        if efficiency_delta is not None and avg_efficiency:
            if efficiency_delta > 0.0005:
                load_type = "adaptation_signal"
            elif efficiency_delta < -0.0005:
                load_type = "load_signal"
            elif abs(efficiency_delta) < 0.0001:
                load_type = "stable"
        
        result.append({
            "week_start": week_key,
            "total_distance_km": round(week_data["total_distance_m"] / 1000, 2),
            "total_distance_miles": round(week_data["total_distance_m"] / 1609.34, 2),
            "total_duration_hours": round(week_data["total_duration_s"] / 3600, 2),
            "activity_count": len(week_data["activities"]),
            "avg_efficiency": round(avg_efficiency, 4) if avg_efficiency else None,
            "efficiency_delta": round(efficiency_delta, 4) if efficiency_delta else None,
            "load_type": load_type
        })
    
    return result[-weeks:]  # Return last N weeks


def annotate_periods(
    time_series: List[Dict],
    activities: List[Activity]
) -> List[Dict]:
    """
    Annotate time series with:
    - Best-effort windows (periods of peak efficiency)
    - Regressions (sustained efficiency decline)
    - Plateaus (periods of no change)
    """
    if len(time_series) < 10:  # Need enough data for annotations
        return time_series
    
    # Calculate rolling 30-day efficiency averages
    efficiencies = [p["efficiency_factor"] for p in time_series]
    rolling_30d = calculate_rolling_average(efficiencies, window=30)
    
    # Find best-effort windows (local maxima in rolling average)
    best_effort_windows = []
    for i in range(1, len(rolling_30d) - 1):
        if rolling_30d[i] and rolling_30d[i-1] and rolling_30d[i+1]:
            if rolling_30d[i] > rolling_30d[i-1] and rolling_30d[i] > rolling_30d[i+1]:
                # Local maximum - potential best-effort window
                if rolling_30d[i] > max(efficiencies) * 0.95:  # Within 5% of best
                    best_effort_windows.append({
                        "date": time_series[i]["date"],
                        "type": "best_effort",
                        "efficiency": rolling_30d[i]
                    })
    
    # Find regressions (sustained decline over 30+ days)
    regressions = []
    for i in range(30, len(rolling_30d)):
        if rolling_30d[i] and rolling_30d[i-30]:
            if rolling_30d[i] < rolling_30d[i-30] * 0.95:  # 5%+ decline
                regressions.append({
                    "date": time_series[i]["date"],
                    "type": "regression",
                    "efficiency": rolling_30d[i]
                })
    
    # Find plateaus (no change over 30+ days)
    plateaus = []
    for i in range(30, len(rolling_30d)):
        if rolling_30d[i] and rolling_30d[i-30]:
            change_pct = abs(rolling_30d[i] - rolling_30d[i-30]) / rolling_30d[i-30]
            if change_pct < 0.02:  # Less than 2% change
                plateaus.append({
                    "date": time_series[i]["date"],
                    "type": "plateau",
                    "efficiency": rolling_30d[i]
                })
    
    # Add annotations to time series
    annotated = time_series.copy()
    for point in annotated:
        point["annotations"] = []
        
        # Check if this point is in a best-effort window
        for window in best_effort_windows:
            if abs((datetime.fromisoformat(point["date"]) - datetime.fromisoformat(window["date"])).days) < 7:
                point["annotations"].append("best_effort")
                break
        
        # Check if this point is in a regression
        for regression in regressions:
            if abs((datetime.fromisoformat(point["date"]) - datetime.fromisoformat(regression["date"])).days) < 7:
                point["annotations"].append("regression")
                break
        
        # Check if this point is in a plateau
        for plateau in plateaus:
            if abs((datetime.fromisoformat(point["date"]) - datetime.fromisoformat(plateau["date"])).days) < 7:
                point["annotations"].append("plateau")
                break
    
    return annotated


def get_efficiency_trends(
    athlete_id: str,
    db: Session,
    days: int = 90,
    include_stability: bool = True,
    include_load_response: bool = True,
    include_annotations: bool = True
) -> Dict:
    """
    Main function to get efficiency trends data.
    
    Returns:
    - Time series of efficiency factors
    - Rolling averages
    - Stability metrics
    - Load-response relationships
    - Age-graded trends
    - Annotations (best-effort windows, regressions, plateaus)
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Get all activities for athlete
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.start_time >= cutoff_date
    ).order_by(Activity.start_time.asc()).all()
    
    # Filter quality activities
    quality_activities = [a for a in activities if is_quality_activity(a)]
    
    if len(quality_activities) < 3:
        return {
            "error": "Insufficient quality data",
            "sample_size": len(quality_activities),
            "required": 3
        }
    
    # Get athlete for max HR if available
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    max_hr = None  # Could extract from athlete profile if stored
    
    # Bulk load splits for all activities (eliminates N+1)
    activity_ids = [str(a.id) for a in quality_activities]
    splits_by_activity = bulk_load_splits_for_activities(activity_ids, db)
    
    # Calculate efficiency time series using GAP and decoupling
    time_series = []
    efficiencies = []
    
    for activity in quality_activities:
        # Get splits from bulk-loaded dict
        splits = splits_by_activity.get(str(activity.id), [])
        
        # Calculate efficiency with decoupling using GAP
        efficiency_data = calculate_activity_efficiency_with_decoupling(
            activity=activity,
            splits=splits,
            max_hr=max_hr
        )
        
        ef = efficiency_data.get("efficiency_factor")
        if ef:
            efficiencies.append(ef)
            time_series.append({
                "date": activity.start_time.isoformat(),
                "efficiency_factor": ef,
                "pace_per_mile": round(activity.pace_per_mile, 2) if activity.pace_per_mile else None,
                "avg_hr": activity.avg_hr,
                "distance_m": float(activity.distance_m) if activity.distance_m else None,
                "duration_s": activity.duration_s,
                "performance_percentage": float(activity.performance_percentage) if activity.performance_percentage else None,
                "activity_id": str(activity.id),
                # Decoupling metrics
                "decoupling_percent": efficiency_data.get("decoupling_percent"),
                "decoupling_status": efficiency_data.get("decoupling_status"),
                "first_half_ef": efficiency_data.get("first_half_ef"),
                "second_half_ef": efficiency_data.get("second_half_ef"),
            })
    
    if len(efficiencies) < 3:
        return {
            "error": "Insufficient efficiency data",
            "sample_size": len(efficiencies),
            "required": 3
        }
    
    # Calculate rolling averages for different time windows
    rolling_7d = calculate_rolling_average(efficiencies, window=7)
    rolling_30d = calculate_rolling_average(efficiencies, window=30)
    rolling_60d = calculate_rolling_average(efficiencies, window=60)
    rolling_90d = calculate_rolling_average(efficiencies, window=90)
    rolling_120d = calculate_rolling_average(efficiencies, window=120)
    
    # Add rolling averages to time series
    for i, point in enumerate(time_series):
        point["rolling_7d_avg"] = round(rolling_7d[i], 2) if rolling_7d[i] else None
        point["rolling_30d_avg"] = round(rolling_30d[i], 2) if rolling_30d[i] else None
        point["rolling_60d_avg"] = round(rolling_60d[i], 2) if rolling_60d[i] else None
        point["rolling_90d_avg"] = round(rolling_90d[i], 2) if rolling_90d[i] else None
        point["rolling_120d_avg"] = round(rolling_120d[i], 2) if rolling_120d[i] else None
    
    # Add annotations if requested
    if include_annotations:
        time_series = annotate_periods(time_series, quality_activities)
    
    # Calculate trend direction using 60-day windows for meaningful signal
    # Compare first 60 days vs last 60 days (or available data)
    if len(efficiencies) >= 60:
        # Use 60-day windows for trend calculation
        recent_window = min(60, len(efficiencies))
        early_window = min(60, len(efficiencies))
        recent_avg = sum(efficiencies[-recent_window:]) / recent_window
        early_avg = sum(efficiencies[:early_window]) / early_window
        trend_direction = "improving" if recent_avg > early_avg else "declining" if recent_avg < early_avg else "stable"
        trend_magnitude = abs(recent_avg - early_avg)
    elif len(efficiencies) >= 30:
        # Fall back to 30-day if we don't have 60 days
        recent_window = min(30, len(efficiencies))
        early_window = min(30, len(efficiencies))
        recent_avg = sum(efficiencies[-recent_window:]) / recent_window
        early_avg = sum(efficiencies[:early_window]) / early_window
        trend_direction = "improving" if recent_avg > early_avg else "declining" if recent_avg < early_avg else "stable"
        trend_magnitude = abs(recent_avg - early_avg)
    else:
        trend_direction = "insufficient_data"
        trend_magnitude = None
    
    # V2: Statistical trend analysis with significance testing
    statistical_trend = analyze_efficiency_trend(time_series)
    
    # Calculate efficiency percentile (where does current EF sit in history)
    efficiency_percentile = calculate_efficiency_percentile(
        efficiencies[-1], 
        efficiencies[:-1] if len(efficiencies) > 1 else efficiencies
    )
    
    # Estimate days to PR efficiency if improving
    days_to_pr = None
    if statistical_trend.slope_per_week and statistical_trend.slope_per_week > 0:
        best_ef = max(efficiencies)
        days_to_pr = estimate_days_to_pr_efficiency(
            efficiencies[-1], 
            best_ef, 
            statistical_trend.slope_per_week
        )
    
    result = {
        "time_series": time_series,
        "summary": {
            "total_activities": len(quality_activities),
            "date_range": {
                "start": time_series[0]["date"],
                "end": time_series[-1]["date"]
            },
            "current_efficiency": round(efficiencies[-1], 4),
            "average_efficiency": round(sum(efficiencies) / len(efficiencies), 4),
            "best_efficiency": round(max(efficiencies), 4),
            "worst_efficiency": round(min(efficiencies), 4),
            "trend_direction": trend_direction,
            "trend_magnitude": round(trend_magnitude, 2) if trend_magnitude else None,
            # V2: Enhanced statistical metrics
            "efficiency_percentile": efficiency_percentile,
            "days_to_pr_efficiency": days_to_pr
        },
        # V2: Statistical trend analysis
        "trend_analysis": trend_to_dict(statistical_trend)
    }
    
    # Add stability metrics
    if include_stability:
        result["stability"] = calculate_stability_metrics(
            quality_activities,
            (cutoff_date, datetime.utcnow()),
            db
        )
    
    # Add load-response
    if include_load_response:
        result["load_response"] = calculate_load_response(quality_activities, db, weeks=8)
    
    return result
