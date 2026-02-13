"""
Correlation Analysis Engine

The core discovery engine that identifies which inputs (and combinations) lead to
statistically significant efficiency improvements over time.

Key principles:
- Personal curves only (no global averages)
- Time-shifted correlations (delayed effects)
- Combination analysis (multi-factor patterns)
- Statistical significance testing
- Filter noise (single-run improvements vs. sustained trends)

Based on manifesto Section 3: Correlation Engines
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
import logging
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from statistics import mean, stdev
import math
from scipy.stats import t as t_dist

from models import (
    Activity, ActivitySplit, NutritionEntry, DailyCheckin, 
    WorkPattern, BodyComposition, ActivityFeedback,
    PlannedWorkout, TrainingPlan, Athlete, PersonalBest
)
from datetime import date as date_type
from services.efficiency_calculation import calculate_activity_efficiency_with_decoupling

logger = logging.getLogger(__name__)


# Statistical thresholds
MIN_SAMPLE_SIZE = 10  # Minimum data points for meaningful correlation
MIN_CORRELATION_STRENGTH = 0.3  # Minimum |r| to be considered meaningful
SIGNIFICANCE_LEVEL = 0.05  # p-value threshold
TREND_CONFIRMATION_RUNS = 3  # Minimum runs to confirm a trend


class CorrelationResult:
    """Result of a correlation analysis."""
    
    def __init__(
        self,
        input_name: str,
        correlation_coefficient: float,
        p_value: float,
        sample_size: int,
        is_significant: bool,
        direction: str,  # 'positive' or 'negative'
        strength: str,  # 'weak', 'moderate', 'strong'
        time_lag_days: int = 0,  # Days between input and output
        combination_factors: Optional[List[str]] = None  # For multi-factor correlations
    ):
        self.input_name = input_name
        self.correlation_coefficient = correlation_coefficient
        self.p_value = p_value
        self.sample_size = sample_size
        self.is_significant = is_significant
        self.direction = direction
        self.strength = strength
        self.time_lag_days = time_lag_days
        self.combination_factors = combination_factors or []
    
    def to_dict(self) -> Dict:
        return {
            "input_name": self.input_name,
            "correlation_coefficient": round(self.correlation_coefficient, 3),
            "p_value": round(self.p_value, 4),
            "sample_size": self.sample_size,
            "is_significant": self.is_significant,
            "direction": self.direction,
            "strength": self.strength,
            "time_lag_days": self.time_lag_days,
            "combination_factors": self.combination_factors
        }


def calculate_pearson_correlation(x: List[float], y: List[float], min_samples: int = 5) -> Tuple[float, float]:
    """
    Calculate Pearson correlation coefficient and p-value.
    
    Args:
        x: First variable values
        y: Second variable values
        min_samples: Minimum number of samples required (default 5)
                     For meaningful correlation analysis, use MIN_SAMPLE_SIZE (10)
    
    Returns:
        (correlation_coefficient, p_value)
    """
    if len(x) != len(y) or len(x) < min_samples:
        return 0.0, 1.0
    
    n = len(x)
    mean_x = mean(x)
    mean_y = mean(y)
    
    # Calculate correlation coefficient
    numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    sum_sq_x = sum((x[i] - mean_x) ** 2 for i in range(n))
    sum_sq_y = sum((y[i] - mean_y) ** 2 for i in range(n))
    
    if sum_sq_x == 0 or sum_sq_y == 0:
        return 0.0, 1.0
    
    denominator = math.sqrt(sum_sq_x * sum_sq_y)
    r = numerator / denominator if denominator != 0 else 0.0
    
    # Calculate p-value using t-test
    if abs(r) == 1.0 or n <= 2:
        p_value = 0.0 if abs(r) == 1.0 else 1.0
    else:
        t_statistic = r * math.sqrt((n - 2) / (1 - r ** 2))
        df = n - 2
        # Two-tailed p-value from exact t-distribution (scipy)
        p_value = float(2 * t_dist.sf(abs(t_statistic), df))
    
    return r, p_value


def classify_correlation_strength(r: float) -> str:
    """Classify correlation strength."""
    abs_r = abs(r)
    if abs_r < 0.3:
        return "weak"
    elif abs_r < 0.7:
        return "moderate"
    else:
        return "strong"


def aggregate_daily_inputs(
    athlete_id: str,
    start_date: datetime,
    end_date: datetime,
    db: Session
) -> Dict[str, List[Tuple[datetime, float]]]:
    """
    Aggregate daily inputs into time-series data.
    
    Returns:
        Dictionary mapping input names to list of (date, value) tuples
    """
    inputs = {}
    
    # Sleep hours
    sleep_data = db.query(
        DailyCheckin.date,
        DailyCheckin.sleep_h
    ).filter(
        DailyCheckin.athlete_id == athlete_id,
        DailyCheckin.date >= start_date.date(),
        DailyCheckin.date <= end_date.date(),
        DailyCheckin.sleep_h.isnot(None)
    ).all()
    
    inputs["sleep_hours"] = [(row.date, float(row.sleep_h)) for row in sleep_data]
    
    # HRV (rMSSD)
    hrv_data = db.query(
        DailyCheckin.date,
        DailyCheckin.hrv_rmssd
    ).filter(
        DailyCheckin.athlete_id == athlete_id,
        DailyCheckin.date >= start_date.date(),
        DailyCheckin.date <= end_date.date(),
        DailyCheckin.hrv_rmssd.isnot(None)
    ).all()
    
    inputs["hrv_rmssd"] = [(row.date, float(row.hrv_rmssd)) for row in hrv_data]
    
    # Resting HR
    resting_hr_data = db.query(
        DailyCheckin.date,
        DailyCheckin.resting_hr
    ).filter(
        DailyCheckin.athlete_id == athlete_id,
        DailyCheckin.date >= start_date.date(),
        DailyCheckin.date <= end_date.date(),
        DailyCheckin.resting_hr.isnot(None)
    ).all()
    
    inputs["resting_hr"] = [(row.date, float(row.resting_hr)) for row in resting_hr_data]
    
    # Work stress
    work_stress_data = db.query(
        WorkPattern.date,
        WorkPattern.stress_level
    ).filter(
        WorkPattern.athlete_id == athlete_id,
        WorkPattern.date >= start_date.date(),
        WorkPattern.date <= end_date.date(),
        WorkPattern.stress_level.isnot(None)
    ).all()
    
    inputs["work_stress"] = [(row.date, float(row.stress_level)) for row in work_stress_data]
    
    # Work hours
    work_hours_data = db.query(
        WorkPattern.date,
        WorkPattern.hours_worked
    ).filter(
        WorkPattern.athlete_id == athlete_id,
        WorkPattern.date >= start_date.date(),
        WorkPattern.date <= end_date.date(),
        WorkPattern.hours_worked.isnot(None)
    ).all()
    
    inputs["work_hours"] = [(row.date, float(row.hours_worked)) for row in work_hours_data]
    
    # Daily protein intake (aggregate from NutritionEntry)
    protein_data = db.query(
        NutritionEntry.date,
        func.sum(NutritionEntry.protein_g).label('total_protein')
    ).filter(
        NutritionEntry.athlete_id == athlete_id,
        NutritionEntry.date >= start_date.date(),
        NutritionEntry.date <= end_date.date(),
        NutritionEntry.protein_g.isnot(None)
    ).group_by(NutritionEntry.date).all()
    
    inputs["daily_protein_g"] = [(row.date, float(row.total_protein)) for row in protein_data]
    
    # Daily carbs intake
    carbs_data = db.query(
        NutritionEntry.date,
        func.sum(NutritionEntry.carbs_g).label('total_carbs')
    ).filter(
        NutritionEntry.athlete_id == athlete_id,
        NutritionEntry.date >= start_date.date(),
        NutritionEntry.date <= end_date.date(),
        NutritionEntry.carbs_g.isnot(None)
    ).group_by(NutritionEntry.date).all()
    
    inputs["daily_carbs_g"] = [(row.date, float(row.total_carbs)) for row in carbs_data]
    
    # Body composition trends (weight, BMI)
    weight_data = db.query(
        BodyComposition.date,
        BodyComposition.weight_kg
    ).filter(
        BodyComposition.athlete_id == athlete_id,
        BodyComposition.date >= start_date.date(),
        BodyComposition.date <= end_date.date(),
        BodyComposition.weight_kg.isnot(None)
    ).order_by(BodyComposition.date).all()
    
    inputs["weight_kg"] = [(row.date, float(row.weight_kg)) for row in weight_data]
    
    bmi_data = db.query(
        BodyComposition.date,
        BodyComposition.bmi
    ).filter(
        BodyComposition.athlete_id == athlete_id,
        BodyComposition.date >= start_date.date(),
        BodyComposition.date <= end_date.date(),
        BodyComposition.bmi.isnot(None)
    ).order_by(BodyComposition.date).all()
    
    inputs["bmi"] = [(row.date, float(row.bmi)) for row in bmi_data]

    # Stress (1-5 scale)
    stress_data = db.query(
        DailyCheckin.date,
        DailyCheckin.stress_1_5
    ).filter(
        DailyCheckin.athlete_id == athlete_id,
        DailyCheckin.date >= start_date.date(),
        DailyCheckin.date <= end_date.date(),
        DailyCheckin.stress_1_5.isnot(None)
    ).all()

    inputs["stress_1_5"] = [(row.date, float(row.stress_1_5)) for row in stress_data]

    # Soreness (1-5 scale)
    soreness_data = db.query(
        DailyCheckin.date,
        DailyCheckin.soreness_1_5
    ).filter(
        DailyCheckin.athlete_id == athlete_id,
        DailyCheckin.date >= start_date.date(),
        DailyCheckin.date <= end_date.date(),
        DailyCheckin.soreness_1_5.isnot(None)
    ).all()

    inputs["soreness_1_5"] = [(row.date, float(row.soreness_1_5)) for row in soreness_data]

    # RPE (1-10 scale)
    rpe_data = db.query(
        DailyCheckin.date,
        DailyCheckin.rpe_1_10
    ).filter(
        DailyCheckin.athlete_id == athlete_id,
        DailyCheckin.date >= start_date.date(),
        DailyCheckin.date <= end_date.date(),
        DailyCheckin.rpe_1_10.isnot(None)
    ).all()

    inputs["rpe_1_10"] = [(row.date, float(row.rpe_1_10)) for row in rpe_data]

    # Enjoyment (1-5 scale)
    enjoyment_data = db.query(
        DailyCheckin.date,
        DailyCheckin.enjoyment_1_5
    ).filter(
        DailyCheckin.athlete_id == athlete_id,
        DailyCheckin.date >= start_date.date(),
        DailyCheckin.date <= end_date.date(),
        DailyCheckin.enjoyment_1_5.isnot(None)
    ).all()

    inputs["enjoyment_1_5"] = [(row.date, float(row.enjoyment_1_5)) for row in enjoyment_data]

    # Confidence (1-5 scale)
    confidence_data = db.query(
        DailyCheckin.date,
        DailyCheckin.confidence_1_5
    ).filter(
        DailyCheckin.athlete_id == athlete_id,
        DailyCheckin.date >= start_date.date(),
        DailyCheckin.date <= end_date.date(),
        DailyCheckin.confidence_1_5.isnot(None)
    ).all()

    inputs["confidence_1_5"] = [(row.date, float(row.confidence_1_5)) for row in confidence_data]

    # Motivation (1-5 scale)
    motivation_data = db.query(
        DailyCheckin.date,
        DailyCheckin.motivation_1_5
    ).filter(
        DailyCheckin.athlete_id == athlete_id,
        DailyCheckin.date >= start_date.date(),
        DailyCheckin.date <= end_date.date(),
        DailyCheckin.motivation_1_5.isnot(None)
    ).all()

    inputs["motivation_1_5"] = [(row.date, float(row.motivation_1_5)) for row in motivation_data]

    # Overnight average HR
    overnight_hr_data = db.query(
        DailyCheckin.date,
        DailyCheckin.overnight_avg_hr
    ).filter(
        DailyCheckin.athlete_id == athlete_id,
        DailyCheckin.date >= start_date.date(),
        DailyCheckin.date <= end_date.date(),
        DailyCheckin.overnight_avg_hr.isnot(None)
    ).all()

    inputs["overnight_avg_hr"] = [(row.date, float(row.overnight_avg_hr)) for row in overnight_hr_data]

    # HRV SDNN
    hrv_sdnn_data = db.query(
        DailyCheckin.date,
        DailyCheckin.hrv_sdnn
    ).filter(
        DailyCheckin.athlete_id == athlete_id,
        DailyCheckin.date >= start_date.date(),
        DailyCheckin.date <= end_date.date(),
        DailyCheckin.hrv_sdnn.isnot(None)
    ).all()

    inputs["hrv_sdnn"] = [(row.date, float(row.hrv_sdnn)) for row in hrv_sdnn_data]
    
    return inputs


def aggregate_activity_nutrition(
    athlete_id: str,
    start_date: datetime,
    end_date: datetime,
    db: Session,
) -> Dict[str, List[Tuple[date_type, float, float]]]:
    """
    Aggregate activity-linked nutrition with efficiency.

    Returns:
        {
            "pre_carbs_vs_efficiency": [(date, carbs_g, efficiency), ...],
            "pre_protein_vs_efficiency": [(date, protein_g, efficiency), ...],
            "post_protein_vs_next_efficiency": [(date, protein_g, next_eff_delta), ...],
        }
    """
    result: Dict[str, List[Tuple[date_type, float, float]]] = {
        "pre_carbs_vs_efficiency": [],
        "pre_protein_vs_efficiency": [],
        "post_protein_vs_next_efficiency": [],
    }

    # --- Pre-activity nutrition linked to same activity efficiency ---
    try:
        pre_rows = (
            db.query(
                NutritionEntry.activity_id,
                NutritionEntry.carbs_g,
                NutritionEntry.protein_g,
                Activity.start_time,
                Activity.avg_hr,
                Activity.duration_s,
                Activity.distance_m,
            )
            .join(Activity, Activity.id == NutritionEntry.activity_id)
            .filter(
                NutritionEntry.athlete_id == athlete_id,
                NutritionEntry.date >= start_date.date(),
                NutritionEntry.date <= end_date.date(),
                NutritionEntry.entry_type == "pre_activity",
                NutritionEntry.activity_id.isnot(None),
            )
            .all()
        )
    except Exception:
        # Be defensive: if join fails in some envs, fall back to empty.
        pre_rows = []

    for row in pre_rows:
        activity_date = row.start_time.date() if row.start_time else None
        avg_hr = float(row.avg_hr) if row.avg_hr is not None else None
        duration_s = float(row.duration_s) if row.duration_s is not None else None
        distance_m = float(row.distance_m) if row.distance_m is not None else None
        if (
            activity_date is None
            or avg_hr is None
            or avg_hr <= 0
            or duration_s is None
            or duration_s <= 0
            or distance_m is None
            or distance_m <= 0
        ):
            continue

        pace_per_km = duration_s / (distance_m / 1000.0)
        efficiency = pace_per_km / avg_hr  # Higher = same pace at lower HR = better

        if row.carbs_g is not None:
            carbs = float(row.carbs_g)
            if carbs > 0:
                result["pre_carbs_vs_efficiency"].append((activity_date, carbs, float(efficiency)))

        if row.protein_g is not None:
            protein = float(row.protein_g)
            if protein > 0:
                result["pre_protein_vs_efficiency"].append((activity_date, protein, float(efficiency)))

    # --- Post-activity protein vs next-day efficiency delta ---
    try:
        post_rows = (
            db.query(
                NutritionEntry.activity_id,
                NutritionEntry.protein_g,
                NutritionEntry.date,
                Activity.avg_hr,
                Activity.duration_s,
                Activity.distance_m,
            )
            .outerjoin(Activity, Activity.id == NutritionEntry.activity_id)
            .filter(
                NutritionEntry.athlete_id == athlete_id,
                NutritionEntry.date >= start_date.date(),
                NutritionEntry.date <= end_date.date(),
                NutritionEntry.entry_type == "post_activity",
                NutritionEntry.protein_g.isnot(None),
            )
            .all()
        )
    except Exception:
        post_rows = []

    # Prefetch next-day run activities (first run per day) to avoid N+1.
    next_activity_by_date: Dict[date_type, Tuple[float, float, float]] = {}
    try:
        next_candidates = (
            db.query(
                func.date(Activity.start_time).label("d"),
                Activity.avg_hr,
                Activity.duration_s,
                Activity.distance_m,
                Activity.start_time,
            )
            .filter(
                Activity.athlete_id == athlete_id,
                Activity.sport == "run",
                Activity.start_time >= start_date,
                Activity.start_time <= (end_date + timedelta(days=1)),
            )
            .order_by(Activity.start_time.asc())
            .all()
        )
        for r in next_candidates:
            d = r.d
            if d is None or d in next_activity_by_date:
                continue
            avg_hr = float(r.avg_hr) if r.avg_hr is not None else None
            duration_s = float(r.duration_s) if r.duration_s is not None else None
            distance_m = float(r.distance_m) if r.distance_m is not None else None
            if (
                avg_hr is None
                or avg_hr <= 0
                or duration_s is None
                or duration_s <= 0
                or distance_m is None
                or distance_m <= 0
            ):
                continue
            next_activity_by_date[d] = (avg_hr, duration_s, distance_m)
    except Exception:
        next_activity_by_date = {}

    for row in post_rows:
        entry_date = row.date
        if entry_date is None:
            continue

        protein = float(row.protein_g) if row.protein_g is not None else None
        if protein is None or protein <= 0:
            continue

        # Current activity efficiency (if linked)
        avg_hr = float(row.avg_hr) if row.avg_hr is not None else None
        duration_s = float(row.duration_s) if row.duration_s is not None else None
        distance_m = float(row.distance_m) if row.distance_m is not None else None
        if (
            avg_hr is None
            or avg_hr <= 0
            or duration_s is None
            or duration_s <= 0
            or distance_m is None
            or distance_m <= 0
        ):
            continue

        current_eff = (duration_s / (distance_m / 1000.0)) / avg_hr

        next_day = entry_date + timedelta(days=1)
        next_metrics = next_activity_by_date.get(next_day)
        if not next_metrics:
            continue

        next_avg_hr, next_duration_s, next_distance_m = next_metrics
        next_eff = (next_duration_s / (next_distance_m / 1000.0)) / next_avg_hr

        eff_delta = float(next_eff - current_eff)
        result["post_protein_vs_next_efficiency"].append((entry_date, float(protein), eff_delta))

    return result


def aggregate_training_load_inputs(
    athlete_id: str,
    start_date: datetime,
    end_date: datetime,
    db: Session
) -> Dict[str, List[Tuple[datetime, float]]]:
    """
    Aggregate TSB/CTL/ATL into time-series data for correlation.
    
    These are derived metrics from TrainingLoadCalculator.
    """
    from services.training_load import TrainingLoadCalculator
    
    inputs: Dict[str, List[Tuple[datetime, float]]] = {}
    calc = TrainingLoadCalculator(db)
    
    # Get load history for the period
    try:
        load_history = calc.get_load_history(
            athlete_id=UUID(athlete_id),
            days=(end_date - start_date).days + 1
        )
        
        # ADR-045 pseudocode assumes a dict; our implementation returns a List[DailyLoad].
        if isinstance(load_history, dict):
            daily_loads = load_history.get("daily_loads", [])
        else:
            daily_loads = load_history or []
        
        tsb_data = []
        ctl_data = []
        atl_data = []
        
        for day_load in daily_loads:
            # Support both dict-like and attribute-like objects
            day_date = None
            tsb_val = None
            ctl_val = None
            atl_val = None
            
            if isinstance(day_load, dict):
                day_date = day_load.get("date")
                tsb_val = day_load.get("tsb")
                ctl_val = day_load.get("ctl")
                atl_val = day_load.get("atl")
            else:
                day_date = getattr(day_load, "date", None)
                tsb_val = getattr(day_load, "tsb", None)
                ctl_val = getattr(day_load, "ctl", None)
                atl_val = getattr(day_load, "atl", None)
            
            if isinstance(day_date, str):
                day_date = datetime.fromisoformat(day_date).date()
            elif isinstance(day_date, datetime):
                day_date = day_date.date()
            
            if tsb_val is not None:
                tsb_data.append((day_date, float(tsb_val)))
            if ctl_val is not None:
                ctl_data.append((day_date, float(ctl_val)))
            if atl_val is not None:
                atl_data.append((day_date, float(atl_val)))
        
        inputs["tsb"] = tsb_data
        inputs["ctl"] = ctl_data
        inputs["atl"] = atl_data
        
    except Exception as e:
        logger.warning(f"Failed to get training load for correlation: {e}")
        inputs["tsb"] = []
        inputs["ctl"] = []
        inputs["atl"] = []
    
    return inputs


def aggregate_pace_at_effort(
    athlete_id: str,
    start_date: datetime,
    end_date: datetime,
    db: Session,
    effort_level: str = "easy"  # "easy", "threshold"
) -> List[Tuple[datetime, float]]:
    """
    Aggregate pace at specific effort levels.
    
    Args:
        effort_level: "easy" (< 75% max_hr) or "threshold" (85-92% max_hr)
    
    Returns:
        List of (activity_date, pace_per_km_seconds) tuples
    """
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete or not athlete.max_hr:
        return []
    
    max_hr = athlete.max_hr
    
    if effort_level == "easy":
        hr_min = 0
        hr_max = int(max_hr * 0.75)
    elif effort_level == "threshold":
        hr_min = int(max_hr * 0.85)
        hr_max = int(max_hr * 0.92)
    else:
        return []
    
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.start_time >= start_date,
        Activity.start_time <= end_date,
        Activity.avg_hr >= hr_min,
        Activity.avg_hr <= hr_max,
        Activity.distance_m > 0,
        Activity.duration_s > 0
    ).order_by(Activity.start_time).all()
    
    pace_data = []
    for activity in activities:
        pace_per_km = activity.duration_s / (activity.distance_m / 1000.0)
        pace_data.append((activity.start_time.date(), pace_per_km))
    
    return pace_data


def aggregate_workout_completion(
    athlete_id: str,
    start_date: datetime,
    end_date: datetime,
    db: Session,
    window_days: int = 7
) -> List[Tuple[datetime, float]]:
    """
    Calculate rolling workout completion rate.
    
    Returns:
        List of (date, completion_rate) tuples where rate is 0.0-1.0
    """
    # Get active plan
    plan = db.query(TrainingPlan).filter(
        TrainingPlan.athlete_id == athlete_id,
        TrainingPlan.status == "active"
    ).first()
    
    if not plan:
        return []
    
    completion_data = []
    current_date = start_date.date()
    end = end_date.date()
    
    while current_date <= end:
        window_start = current_date - timedelta(days=window_days)
        
        scheduled = db.query(PlannedWorkout).filter(
            PlannedWorkout.plan_id == plan.id,
            PlannedWorkout.scheduled_date >= window_start,
            PlannedWorkout.scheduled_date <= current_date
        ).count()
        
        completed = db.query(PlannedWorkout).filter(
            PlannedWorkout.plan_id == plan.id,
            PlannedWorkout.scheduled_date >= window_start,
            PlannedWorkout.scheduled_date <= current_date,
            PlannedWorkout.completed == True
        ).count()
        
        if scheduled > 0:
            rate = completed / scheduled
            completion_data.append((current_date, rate))
        
        current_date += timedelta(days=1)
    
    return completion_data


def aggregate_efficiency_outputs(
    athlete_id: str,
    start_date: datetime,
    end_date: datetime,
    db: Session
) -> List[Tuple[datetime, float]]:
    """
    Aggregate efficiency outputs (EF) from activities.
    
    Returns:
        List of (activity_date, efficiency_factor) tuples
    """
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.start_time >= start_date,
        Activity.start_time <= end_date
    ).order_by(Activity.start_time).all()
    
    efficiency_data = []
    
    for activity in activities:
        # Get splits for this activity
        splits = db.query(ActivitySplit).filter(
            ActivitySplit.activity_id == activity.id
        ).order_by(ActivitySplit.split_number).all()
        
        # Calculate efficiency with decoupling
        efficiency_result = calculate_activity_efficiency_with_decoupling(
            activity=activity,
            splits=splits,
            max_hr=None
        )
        
        ef = efficiency_result.get("efficiency_factor")
        if ef:
            efficiency_data.append((activity.start_time.date(), ef))
    
    return efficiency_data


def aggregate_efficiency_by_effort_zone(
    athlete_id: str,
    start_date: datetime,
    end_date: datetime,
    db: Session,
    effort_zone: str = "threshold"  # "easy", "threshold", "race"
) -> List[Tuple[date_type, float]]:
    """
    Aggregate efficiency for COMPARABLE runs only.
    
    Effort zones (% max HR):
    - easy: < 75%
    - threshold: 80-88%
    - race: > 88%
    
    Returns Pace/HR ratio (higher = better efficiency — same pace at lower HR)
    """
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete or not athlete.max_hr:
        return []
    
    max_hr = athlete.max_hr
    
    if effort_zone == "easy":
        hr_min, hr_max = 0, int(max_hr * 0.75)
    elif effort_zone == "threshold":
        hr_min, hr_max = int(max_hr * 0.80), int(max_hr * 0.88)
    elif effort_zone == "race":
        hr_min, hr_max = int(max_hr * 0.88), 999
    else:
        return []
    
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.start_time >= start_date,
        Activity.start_time <= end_date,
        Activity.avg_hr >= hr_min,
        Activity.avg_hr <= hr_max,
        Activity.distance_m >= 3000,  # Minimum 3km for meaningful data
        Activity.duration_s > 0
    ).order_by(Activity.start_time).all()
    
    result = []
    for a in activities:
        pace_sec_km = a.duration_s / (a.distance_m / 1000)
        efficiency = pace_sec_km / a.avg_hr  # Higher = same pace at lower HR = better
        result.append((a.start_time.date(), efficiency))
    
    return result


def aggregate_efficiency_trend(
    athlete_id: str,
    start_date: datetime,
    end_date: datetime,
    db: Session,
    effort_zone: str = "threshold",
    window_days: int = 30
) -> List[Tuple[date_type, float]]:
    """
    Calculate rolling efficiency improvement rate.
    
    Returns % change in efficiency vs baseline (positive = improvement)
    """
    raw_data = aggregate_efficiency_by_effort_zone(
        athlete_id, start_date, end_date, db, effort_zone
    )
    
    if len(raw_data) < 5:
        return []
    
    # Baseline: first 5 data points average
    baseline = sum(d[1] for d in raw_data[:5]) / 5
    
    result = []
    for d, eff in raw_data[5:]:
        pct_change = ((eff - baseline) / baseline) * 100
        result.append((d, pct_change))
    
    return result


def aggregate_pb_events(
    athlete_id: str,
    start_date: datetime,
    end_date: datetime,
    db: Session
) -> List[Tuple[date_type, float]]:
    """
    Aggregate PB events as binary time series.
    
    Returns:
        List of (date, 1.0) for PB days, (date, 0.0) for non-PB days
    """
    # Get all PB dates
    pbs = db.query(PersonalBest.achieved_at).filter(
        PersonalBest.athlete_id == athlete_id,
        PersonalBest.achieved_at >= start_date,
        PersonalBest.achieved_at <= end_date
    ).all()
    
    pb_dates = {pb.achieved_at.date() for pb in pbs}
    
    # Get all activity dates
    activities = db.query(Activity.start_time).filter(
        Activity.athlete_id == athlete_id,
        Activity.start_time >= start_date,
        Activity.start_time <= end_date
    ).all()
    
    activity_dates = {a.start_time.date() for a in activities}
    
    # Create binary series
    result = []
    for d in sorted(activity_dates):
        result.append((d, 1.0 if d in pb_dates else 0.0))
    
    return result


def aggregate_race_pace(
    athlete_id: str,
    start_date: datetime,
    end_date: datetime,
    db: Session
) -> List[Tuple[date_type, float]]:
    """
    Aggregate pace on race-like efforts.
    
    Filters to activities that are likely races or hard efforts:
    - avg_hr > 85% max_hr, OR
    - distance > 5km with avg_hr > 80% max_hr
    
    Returns:
        List of (date, pace_per_km_seconds) tuples
    """
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete or not athlete.max_hr:
        return []
    
    max_hr = athlete.max_hr
    hr_threshold_high = int(max_hr * 0.85)
    hr_threshold_mid = int(max_hr * 0.80)
    
    # Race-like efforts: high HR OR long + moderately high HR
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.start_time >= start_date,
        Activity.start_time <= end_date,
        Activity.distance_m > 0,
        Activity.duration_s > 0,
        Activity.avg_hr.isnot(None)
    ).filter(
        or_(
            Activity.avg_hr >= hr_threshold_high,
            and_(
                Activity.distance_m >= 5000,
                Activity.avg_hr >= hr_threshold_mid
            )
        )
    ).order_by(Activity.start_time).all()
    
    pace_data = []
    for activity in activities:
        pace_per_km = activity.duration_s / (activity.distance_m / 1000.0)
        pace_data.append((activity.start_time.date(), pace_per_km))
    
    return pace_data


def aggregate_pre_pb_state(
    athlete_id: str,
    start_date: datetime,
    end_date: datetime,
    db: Session,
    days_before: int = 1
) -> Dict:
    """
    Analyze training state in days leading up to PBs.
    
    Returns summary statistics, not time series.
    """
    from services.training_load import TrainingLoadCalculator
    
    pbs = db.query(PersonalBest).filter(
        PersonalBest.athlete_id == athlete_id,
        PersonalBest.achieved_at >= start_date,
        PersonalBest.achieved_at <= end_date
    ).all()
    
    if not pbs:
        return {"pb_count": 0, "patterns": None}
    
    calc = TrainingLoadCalculator(db)
    
    try:
        history = calc.get_load_history(UUID(athlete_id) if isinstance(athlete_id, str) else athlete_id, days=365)
    except Exception as e:
        logger.warning(f"Failed to get load history for pre-PB analysis: {e}")
        return {"pb_count": len(pbs), "patterns": None, "error": str(e)}
    
    # Build lookup - handle both list and dict return types
    load_by_date = {}
    items = history if isinstance(history, list) else history.get("daily_loads", [])
    for item in items:
        d = item.date if hasattr(item, 'date') else item.get('date')
        if hasattr(d, 'date'):
            d = d.date()
        elif isinstance(d, str):
            d = datetime.fromisoformat(d).date()
        load_by_date[d] = item
    
    pre_pb_tsb = []
    pre_pb_ctl = []
    
    for pb in pbs:
        pb_date = pb.achieved_at.date()
        # Get state 1 day before PB
        check_date = pb_date - timedelta(days=days_before)
        if check_date in load_by_date:
            item = load_by_date[check_date]
            tsb = item.tsb if hasattr(item, 'tsb') else item.get('tsb')
            ctl = item.ctl if hasattr(item, 'ctl') else item.get('ctl')
            if tsb is not None:
                pre_pb_tsb.append(float(tsb))
            if ctl is not None:
                pre_pb_ctl.append(float(ctl))
    
    return {
        "pb_count": len(pbs),
        "pre_pb_tsb_mean": sum(pre_pb_tsb) / len(pre_pb_tsb) if pre_pb_tsb else None,
        "pre_pb_tsb_min": min(pre_pb_tsb) if pre_pb_tsb else None,
        "pre_pb_tsb_max": max(pre_pb_tsb) if pre_pb_tsb else None,
        "pre_pb_ctl_mean": sum(pre_pb_ctl) / len(pre_pb_ctl) if pre_pb_ctl else None,
        "optimal_tsb_range": (min(pre_pb_tsb), max(pre_pb_tsb)) if pre_pb_tsb else None
    }


def find_time_shifted_correlations(
    input_data: List[Tuple[datetime, float]],
    output_data: List[Tuple[datetime, float]],
    max_lag_days: int = 14,
    min_samples: int = 3
) -> List[CorrelationResult]:
    """
    Find correlations with time shifts (delayed effects).
    
    Tests correlations with input lagged by 0, 1, 2, ... max_lag_days days.
    
    Args:
        input_data: List of (date, value) tuples for input variable
        output_data: List of (date, value) tuples for output variable
        max_lag_days: Maximum lag days to test
        min_samples: Minimum sample size for correlation (default 3)
                     Higher-level functions should use MIN_SAMPLE_SIZE (10) for meaningful insights
    """
    
    results = []
    
    for lag_days in range(max_lag_days + 1):
        # Shift input data forward by lag_days
        shifted_input = [
            (date + timedelta(days=lag_days), value)
            for date, value in input_data
        ]
        
        # Align input and output by date
        aligned_data = _align_time_series(shifted_input, output_data)
        
        if len(aligned_data) < min_samples:
            continue
        
        x_values = [point[0] for point in aligned_data]
        y_values = [point[1] for point in aligned_data]
        
        r, p_value = calculate_pearson_correlation(x_values, y_values)
        
        if abs(r) >= MIN_CORRELATION_STRENGTH:
            # Note: input_name will be set by caller
            result = CorrelationResult(
                input_name="",  # Will be set by caller
                correlation_coefficient=r,
                p_value=p_value,
                sample_size=len(aligned_data),
                is_significant=p_value < SIGNIFICANCE_LEVEL,
                direction="positive" if r > 0 else "negative",
                strength=classify_correlation_strength(r),
                time_lag_days=lag_days
            )
            results.append(result)
    
    return results


def _align_time_series(
    series1: List[Tuple[datetime, float]],
    series2: List[Tuple[datetime, float]]
) -> List[Tuple[float, float]]:
    """
    Align two time series by date, returning (value1, value2) pairs.
    """
    # Create date lookup dictionaries
    dict1 = {date: value for date, value in series1}
    dict2 = {date: value for date, value in series2}
    
    # Find common dates
    common_dates = set(dict1.keys()) & set(dict2.keys())
    
    # Return aligned pairs
    return [(dict1[date], dict2[date]) for date in sorted(common_dates)]


def analyze_correlations(
    athlete_id: str,
    days: int = 90,
    db: Session = None,
    include_training_load: bool = True,  # NEW PARAMETER
    output_metric: str = "efficiency"     # NEW PARAMETER: "efficiency", "pace_easy", "completion"
) -> Dict:
    """
    Main correlation analysis function.
    
    Analyzes all inputs vs efficiency outputs and returns discovered correlations.
    """
    if not db:
        raise ValueError("Database session required")
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Aggregate inputs
    inputs = aggregate_daily_inputs(athlete_id, start_date, end_date, db)

    # Add training load inputs if requested
    if include_training_load:
        load_inputs = aggregate_training_load_inputs(athlete_id, start_date, end_date, db)
        inputs.update(load_inputs)
    
    # Get outputs based on metric
    if output_metric == "efficiency":
        outputs = aggregate_efficiency_outputs(athlete_id, start_date, end_date, db)
    elif output_metric == "pace_easy":
        outputs = aggregate_pace_at_effort(athlete_id, start_date, end_date, db, "easy")
    elif output_metric == "pace_threshold":
        outputs = aggregate_pace_at_effort(athlete_id, start_date, end_date, db, "threshold")
    elif output_metric == "completion":
        outputs = aggregate_workout_completion(athlete_id, start_date, end_date, db)
    elif output_metric == "efficiency_threshold":
        outputs = aggregate_efficiency_by_effort_zone(athlete_id, start_date, end_date, db, "threshold")
    elif output_metric == "efficiency_race":
        outputs = aggregate_efficiency_by_effort_zone(athlete_id, start_date, end_date, db, "race")
    elif output_metric == "efficiency_easy":
        outputs = aggregate_efficiency_by_effort_zone(athlete_id, start_date, end_date, db, "easy")
    elif output_metric == "efficiency_trend":
        outputs = aggregate_efficiency_trend(athlete_id, start_date, end_date, db, "threshold")
    elif output_metric == "pb_events":
        outputs = aggregate_pb_events(athlete_id, start_date, end_date, db)
    elif output_metric == "race_pace":
        outputs = aggregate_race_pace(athlete_id, start_date, end_date, db)
    else:
        outputs = aggregate_efficiency_outputs(athlete_id, start_date, end_date, db)
    
    if len(outputs) < MIN_SAMPLE_SIZE:
        return {
            "error": "Insufficient data",
            "sample_size": len(outputs),
            "required": MIN_SAMPLE_SIZE
        }
    
    # Analyze each input
    correlations = []
    
    for input_name, input_data in inputs.items():
        if len(input_data) < MIN_SAMPLE_SIZE:
            continue
        
        # Find time-shifted correlations
        lagged_results = find_time_shifted_correlations(input_data, outputs, max_lag_days=7)
        
        # Set input name and keep only significant correlations
        significant = []
        for r in lagged_results:
            if r.is_significant:
                r.input_name = input_name
                significant.append(r)
        
        if significant:
            # Keep the strongest correlation (by absolute value)
            best = max(significant, key=lambda r: abs(r.correlation_coefficient))
            correlations.append(best.to_dict())
    
    # Sort by correlation strength (absolute value)
    correlations.sort(key=lambda x: abs(x["correlation_coefficient"]), reverse=True)
    
    # Attach output metric metadata so downstream consumers (insight generator,
    # coach tools) never have to guess polarity from raw correlation sign.
    from services.n1_insight_generator import get_metric_meta
    meta = get_metric_meta(output_metric)
    output_metric_metadata = {
        "metric_key": meta.metric_key,
        "metric_definition": meta.metric_definition,
        "higher_is_better": meta.higher_is_better,
        "polarity_ambiguous": meta.polarity_ambiguous,
        "direction_interpretation": meta.direction_interpretation,
    }

    return {
        "athlete_id": athlete_id,
        "analysis_period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "days": days
        },
        "output_metric": output_metric,
        "output_metric_metadata": output_metric_metadata,
        "sample_sizes": {
            "activities": len(outputs),
            "inputs": {name: len(data) for name, data in inputs.items()}
        },
        "correlations": correlations,
        "total_correlations_found": len(correlations)
    }


def discover_combination_correlations(
    athlete_id: str,
    days: int = 90,
    db: Session = None
) -> Dict:
    """
    Discover multi-factor combination correlations.
    
    Tests combinations of inputs to find patterns like:
    - "High sleep + Low work stress = Better efficiency"
    - "High protein + Good HRV = Better decoupling"
    
    Uses median splits to create binary high/low categories for each input,
    then tests efficiency differences between combinations.
    """
    if not db:
        raise ValueError("Database session required")
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Aggregate inputs
    inputs = aggregate_daily_inputs(athlete_id, start_date, end_date, db)
    
    # Aggregate outputs
    outputs = aggregate_efficiency_outputs(athlete_id, start_date, end_date, db)
    
    if len(outputs) < MIN_SAMPLE_SIZE:
        return {
            "error": "Insufficient data",
            "sample_size": len(outputs),
            "required": MIN_SAMPLE_SIZE
        }
    
    # Convert outputs to dict for easy lookup
    output_dict = {date: ef for date, ef in outputs}
    
    # For each input, create high/low split based on median
    input_splits = {}
    for input_name, data in inputs.items():
        if len(data) < MIN_SAMPLE_SIZE:
            continue
        
        values = [v for _, v in data]
        median_val = sorted(values)[len(values) // 2]
        
        high_dates = {date for date, val in data if val >= median_val}
        low_dates = {date for date, val in data if val < median_val}
        
        input_splits[input_name] = {
            'high': high_dates,
            'low': low_dates,
            'median': median_val
        }
    
    # Test two-factor combinations
    combination_results = []
    input_names = list(input_splits.keys())
    
    for i in range(len(input_names)):
        for j in range(i + 1, len(input_names)):
            name1 = input_names[i]
            name2 = input_names[j]
            
            split1 = input_splits[name1]
            split2 = input_splits[name2]
            
            # Test: both high vs both low
            both_high = split1['high'] & split2['high']
            both_low = split1['low'] & split2['low']
            
            # Get efficiency for each group
            ef_both_high = [output_dict[d] for d in both_high if d in output_dict]
            ef_both_low = [output_dict[d] for d in both_low if d in output_dict]
            
            if len(ef_both_high) >= 5 and len(ef_both_low) >= 5:
                # Compare means
                mean_high = mean(ef_both_high)
                mean_low = mean(ef_both_low)
                
                # Effect size (Cohen's d approximation)
                pooled_std = math.sqrt(
                    (stdev(ef_both_high) ** 2 + stdev(ef_both_low) ** 2) / 2
                ) if len(ef_both_high) > 1 and len(ef_both_low) > 1 else 1
                
                effect_size = (mean_high - mean_low) / pooled_std if pooled_std > 0 else 0
                
                # Only report if effect size is meaningful (|d| > 0.5 is moderate)
                if abs(effect_size) > 0.5:
                    is_improvement = mean_high < mean_low  # Lower EF is better
                    
                    combination_results.append({
                        'factors': [name1, name2],
                        'condition': 'both_high' if is_improvement else 'both_low',
                        'better_group': 'high' if is_improvement else 'low',
                        'effect_size': round(effect_size, 2),
                        'mean_ef_high': round(mean_high, 4),
                        'mean_ef_low': round(mean_low, 4),
                        'sample_size_high': len(ef_both_high),
                        'sample_size_low': len(ef_both_low),
                        'interpretation': _interpret_combination(
                            name1, name2, is_improvement, effect_size
                        )
                    })
    
    # Sort by effect size
    combination_results.sort(key=lambda x: abs(x['effect_size']), reverse=True)
    
    return {
        "athlete_id": athlete_id,
        "analysis_period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "days": days
        },
        "combination_correlations": combination_results[:10],  # Top 10
        "total_combinations_tested": len(combination_results)
    }


def _interpret_combination(name1: str, name2: str, is_improvement: bool, effect_size: float) -> str:
    """Generate human-readable interpretation of combination correlation."""
    strength = "strongly" if abs(effect_size) > 0.8 else "moderately"
    
    # Determine if inputs are "good high" or "good low"
    # NOTE: hrv_rmssd is INTENTIONALLY excluded from good_high_inputs.
    # Build plan Principle 6: "No metric is assumed directional."
    # HRV direction must be discovered per-athlete by the correlation engine,
    # not assumed from population norms. Some athletes perform better with
    # lower HRV (parasympathetic withdrawal before competition).
    # See: docs/TRAINING_PLAN_REBUILD_PLAN.md — HRV Correlation Study
    good_high_inputs = {'sleep_hours', 'daily_protein_g', 'daily_carbs_g'}
    good_low_inputs = {'resting_hr', 'work_stress', 'work_hours'}
    
    def describe_input(name: str, is_high: bool) -> str:
        if name in good_high_inputs:
            return f"higher {name.replace('_', ' ')}" if is_high else f"lower {name.replace('_', ' ')}"
        elif name in good_low_inputs:
            return f"lower {name.replace('_', ' ')}" if not is_high else f"higher {name.replace('_', ' ')}"
        return f"{'high' if is_high else 'low'} {name.replace('_', ' ')}"
    
    desc1 = describe_input(name1, is_improvement)
    desc2 = describe_input(name2, is_improvement)
    
    return f"Days with {desc1} AND {desc2} {strength} correlate with better efficiency."


def get_combination_insights(
    athlete_id: str,
    days: int = 90,
    db: Session = None
) -> List[Dict]:
    """
    Get actionable combination insights for the athlete.
    
    Returns interpretations of what combinations work/don't work.
    """
    result = discover_combination_correlations(athlete_id, days, db)
    
    if 'error' in result:
        return []
    
    insights = []
    for combo in result.get('combination_correlations', []):
        if combo['effect_size'] > 0:
            insights.append({
                'type': 'positive_combination',
                'factors': combo['factors'],
                'insight': combo['interpretation'],
                'confidence': 'high' if abs(combo['effect_size']) > 0.8 else 'moderate'
            })
    
    return insights

