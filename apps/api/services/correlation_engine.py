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
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from statistics import mean, stdev
import math

from models import (
    Activity, ActivitySplit, NutritionEntry, DailyCheckin, 
    WorkPattern, BodyComposition, ActivityFeedback
)
from services.efficiency_calculation import calculate_activity_efficiency_with_decoupling


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


def calculate_pearson_correlation(x: List[float], y: List[float]) -> Tuple[float, float]:
    """
    Calculate Pearson correlation coefficient and p-value.
    
    Returns:
        (correlation_coefficient, p_value)
    """
    if len(x) != len(y) or len(x) < MIN_SAMPLE_SIZE:
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
        # Simplified p-value approximation (two-tailed)
        # For production, use scipy.stats.pearsonr or proper t-distribution
        df = n - 2
        p_value = 2 * (1 - _t_cdf(abs(t_statistic), df))
    
    return r, p_value


def _t_cdf(t: float, df: int) -> float:
    """
    Approximate t-distribution CDF.
    Simplified version - for production use scipy.stats.t.cdf
    """
    # Very simplified approximation
    # In production, use proper statistical library
    if abs(t) > 3:
        return 0.999 if t > 0 else 0.001
    return 0.5 + (t / (2 * math.sqrt(df)))


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
    
    return inputs


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


def find_time_shifted_correlations(
    input_data: List[Tuple[datetime, float]],
    output_data: List[Tuple[datetime, float]],
    max_lag_days: int = 14
) -> List[CorrelationResult]:
    """
    Find correlations with time shifts (delayed effects).
    
    Tests correlations with input lagged by 0, 1, 2, ... max_lag_days days.
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
        
        if len(aligned_data) < MIN_SAMPLE_SIZE:
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
    db: Session = None
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
    
    # Aggregate outputs (efficiency)
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
    
    return {
        "athlete_id": athlete_id,
        "analysis_period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "days": days
        },
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
    good_high_inputs = {'sleep_hours', 'hrv_rmssd', 'daily_protein_g', 'daily_carbs_g'}
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

