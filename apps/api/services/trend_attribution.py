"""
Trend Attribution Service

Answers "Why This Trend?" by aggregating signals from all analytics methods
and correlating inputs to efficiency/performance changes.

ADR-014: Why This Trend? Attribution Integration

Design Principles:
- N=1: Uses YOUR data patterns, not generic advice
- Ranked: Shows what matters most, not everything
- Honest: Confidence badges reflect certainty
- Sparse: Non-prescriptive tone ("Data hints X. Test it.")
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum
from uuid import UUID
import math
import logging

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from models import (
    Activity, DailyCheckin, NutritionEntry, BodyComposition
)

logger = logging.getLogger(__name__)


class TrendMetric(str, Enum):
    """Metrics that can be explained."""
    EFFICIENCY = "efficiency"
    LOAD = "load"
    SPEED = "speed"
    PACING = "pacing"


class AttributionConfidence(str, Enum):
    """Confidence level for attributions."""
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    INSUFFICIENT = "insufficient"


@dataclass
class TrendSummary:
    """Summary of the trend being explained."""
    metric: str
    direction: str  # "improving", "declining", "stable"
    change_percent: float
    p_value: Optional[float]
    confidence: str
    period_days: int


@dataclass
class Attribution:
    """Single factor attribution."""
    factor: str
    label: str
    contribution_pct: float
    correlation: float
    confidence: str
    insight: str
    sample_size: int
    time_lag_days: int = 0


@dataclass
class MethodContribution:
    """Which analytics methods contributed to the attribution."""
    efficiency_trending: bool = False
    tsb_analysis: bool = False
    # critical_speed removed - archived to branch archive/cs-model-2026-01
    fingerprinting: bool = False
    pace_decay: bool = False


@dataclass
class TrendAttributionResult:
    """Complete attribution result."""
    trend_summary: TrendSummary
    attributions: List[Attribution]
    method_contributions: MethodContribution
    generated_at: datetime


# Factor configuration
FACTOR_CONFIGS = {
    # Sleep & Recovery
    "sleep_quality": {"label": "Sleep Quality", "lag_days": [0, 1, 2], "category": "recovery"},
    "sleep_duration": {"label": "Sleep Duration", "lag_days": [0, 1, 2], "category": "recovery"},
    "hrv": {"label": "HRV", "lag_days": [0, 1], "category": "recovery"},
    "resting_hr": {"label": "Resting HR", "lag_days": [0, 1], "category": "recovery"},
    
    # Stress & Wellness
    "stress": {"label": "Stress Level", "lag_days": [0, 1], "category": "wellness"},
    "soreness": {"label": "Soreness", "lag_days": [0, 1], "category": "wellness"},
    "fatigue": {"label": "Fatigue", "lag_days": [0, 1], "category": "wellness"},
    "mood": {"label": "Mood", "lag_days": [0, 1], "category": "wellness"},
    
    # Nutrition
    "calories": {"label": "Calorie Intake", "lag_days": [0, 1], "category": "nutrition"},
    "protein": {"label": "Protein Intake", "lag_days": [0, 1], "category": "nutrition"},
    "carbs": {"label": "Carb Intake", "lag_days": [0, 1], "category": "nutrition"},
    "hydration": {"label": "Hydration", "lag_days": [0], "category": "nutrition"},
    
    # Body Composition
    "weight": {"label": "Body Weight", "lag_days": [0, 7], "category": "body"},
    "bmi": {"label": "BMI", "lag_days": [0, 7], "category": "body"},
    
    # Training Load
    "weekly_mileage": {"label": "Weekly Mileage", "lag_days": [7], "category": "training"},
    "consistency": {"label": "Training Consistency", "lag_days": [7], "category": "training"},
    "long_run_pct": {"label": "Long Run Ratio", "lag_days": [14], "category": "training"},
    "easy_run_pct": {"label": "Easy Run Ratio", "lag_days": [14], "category": "training"},
    "intensity": {"label": "Training Intensity", "lag_days": [7], "category": "training"},
    
    # TSB Metrics
    "tsb": {"label": "Training Stress Balance", "lag_days": [0], "category": "load"},
    "atl": {"label": "Acute Training Load", "lag_days": [0], "category": "load"},
    "ctl": {"label": "Chronic Training Load", "lag_days": [0], "category": "load"},
}

# Confidence thresholds
HIGH_CONFIDENCE_R = 0.7
HIGH_CONFIDENCE_SAMPLE = 20
HIGH_CONFIDENCE_P = 0.05

MODERATE_CONFIDENCE_R = 0.4
MODERATE_CONFIDENCE_SAMPLE = 10
MODERATE_CONFIDENCE_P = 0.10

LOW_CONFIDENCE_R = 0.2
LOW_CONFIDENCE_SAMPLE = 5


def pearson_correlation(x: List[float], y: List[float]) -> Tuple[float, float]:
    """
    Calculate Pearson correlation coefficient and p-value.
    
    Returns (r, p_value).
    """
    if len(x) != len(y) or len(x) < 3:
        return 0.0, 1.0
    
    n = len(x)
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    
    numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    sum_sq_x = sum((xi - mean_x) ** 2 for xi in x)
    sum_sq_y = sum((yi - mean_y) ** 2 for yi in y)
    
    if sum_sq_x == 0 or sum_sq_y == 0:
        return 0.0, 1.0
    
    denominator = math.sqrt(sum_sq_x * sum_sq_y)
    r = numerator / denominator if denominator != 0 else 0.0
    
    # Calculate p-value using t-test approximation
    if abs(r) >= 0.9999 or n <= 2:
        p_value = 0.0001 if abs(r) >= 0.9999 else 1.0
    else:
        try:
            t_stat = r * math.sqrt((n - 2) / (1 - r ** 2))
            # Simplified p-value approximation
            p_value = 2 * _approx_p_from_t(abs(t_stat), n - 2)
        except (ValueError, ZeroDivisionError):
            p_value = 1.0
    
    return r, max(0.0001, min(1.0, p_value))


def _approx_p_from_t(t: float, df: int) -> float:
    """Approximate p-value from t-statistic."""
    if t > 6:
        return 0.0001
    if t < 0.5:
        return 0.4
    # Simple approximation
    return max(0.0001, min(0.5, 0.5 * math.exp(-0.5 * t)))


def classify_confidence(
    r: float, 
    sample_size: int, 
    p_value: float
) -> AttributionConfidence:
    """Classify attribution confidence based on stats."""
    abs_r = abs(r)
    
    if abs_r >= HIGH_CONFIDENCE_R and sample_size >= HIGH_CONFIDENCE_SAMPLE and p_value < HIGH_CONFIDENCE_P:
        return AttributionConfidence.HIGH
    elif abs_r >= MODERATE_CONFIDENCE_R and sample_size >= MODERATE_CONFIDENCE_SAMPLE and p_value < MODERATE_CONFIDENCE_P:
        return AttributionConfidence.MODERATE
    elif abs_r >= LOW_CONFIDENCE_R and sample_size >= LOW_CONFIDENCE_SAMPLE:
        return AttributionConfidence.LOW
    else:
        return AttributionConfidence.INSUFFICIENT


def generate_attribution_insight(
    factor: str,
    label: str,
    correlation: float,
    trend_direction: str,
    lag_days: int
) -> str:
    """
    Generate sparse, non-prescriptive insight text.
    
    Tone: Direct, data-hints, test-it style.
    """
    direction = "higher" if correlation > 0 else "lower"
    trend_word = "better" if trend_direction == "improving" else "worse"
    
    lag_text = ""
    if lag_days > 0:
        lag_text = f" ({lag_days}-day lag)"
    
    # Category-specific insights
    if "sleep" in factor.lower():
        return f"{direction.capitalize()} sleep scores{lag_text} precede your {trend_word} days. Data hints causation. Test it."
    elif "hrv" in factor.lower():
        if correlation < 0:
            return f"Lower HRV{lag_text} correlates with your {trend_word} performances. Inverted pattern — may be your normal."
        return f"Higher HRV{lag_text} correlates with {trend_word} performances. Expected pattern confirmed."
    elif "consistency" in factor.lower():
        return f"Weeks with more runs show {trend_word} efficiency. Consistency compounds."
    elif "mileage" in factor.lower():
        return f"{direction.capitalize()} weekly mileage correlates with {trend_word} efficiency."
    elif "stress" in factor.lower():
        return f"{direction.capitalize()} stress levels{lag_text} precede {trend_word} performances."
    elif "tsb" in factor.lower():
        return f"Training stress balance correlates with performance. Current form matters."
    elif "weight" in factor.lower() or "bmi" in factor.lower():
        return f"Body composition changes correlate with efficiency changes."
    elif "protein" in factor.lower() or "carb" in factor.lower() or "calorie" in factor.lower():
        return f"Nutrition patterns{lag_text} correlate with {trend_word} performances."
    else:
        return f"{label}{lag_text} correlates with your trend. Worth monitoring."


def get_trend_summary(
    athlete_id: str,
    metric: TrendMetric,
    days: int,
    db: Session
) -> Optional[TrendSummary]:
    """
    Get summary of the specified trend from efficiency trending service.
    """
    try:
        if metric == TrendMetric.EFFICIENCY:
            from services.efficiency_analytics import get_efficiency_trends
            
            trends = get_efficiency_trends(UUID(athlete_id), db, days=days)
            
            if not trends or "trend_analysis" not in trends:
                return None
            
            analysis = trends.get("trend_analysis", {})
            
            return TrendSummary(
                metric=metric.value,
                direction=analysis.get("direction", "stable"),
                change_percent=abs(analysis.get("change_percent", 0)),
                p_value=analysis.get("p_value"),
                confidence=analysis.get("confidence", "low"),
                period_days=days
            )
        
        # For other metrics, return basic summary
        return TrendSummary(
            metric=metric.value,
            direction="stable",
            change_percent=0,
            p_value=None,
            confidence="low",
            period_days=days
        )
        
    except Exception as e:
        logger.warning(f"Error getting trend summary: {e}")
        return None


def collect_factor_data(
    athlete_id: str,
    days: int,
    db: Session
) -> Dict[str, List[Tuple[date, float]]]:
    """
    Collect all factor data for the athlete over the specified period.
    
    Returns dict mapping factor name to list of (date, value) tuples.
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=days + 14)  # Extra buffer for lags
    
    factor_data: Dict[str, List[Tuple[date, float]]] = {}
    
    # Collect from DailyCheckin
    checkins = db.query(DailyCheckin).filter(
        DailyCheckin.athlete_id == athlete_id,
        DailyCheckin.date >= start_date,
        DailyCheckin.date <= end_date
    ).all()
    
    for checkin in checkins:
        d = checkin.date
        # NOTE: The DailyCheckin schema has evolved. Use getattr() to remain compatible
        # and avoid 500s from missing columns.
        #
        # Current model fields include: sleep_h, stress_1_5, soreness_1_5, rpe_1_10,
        # hrv_rmssd/hrv_sdnn, resting_hr, overnight_avg_hr, enjoyment_1_5, confidence_1_5, motivation_1_5.
        #
        # We only include factors that we can measure reliably from stored columns.

        sleep_duration = getattr(checkin, "sleep_h", None)
        if sleep_duration is None:
            sleep_duration = getattr(checkin, "sleep_hours", None)  # legacy
        if sleep_duration is not None:
            factor_data.setdefault("sleep_duration", []).append((d, float(sleep_duration)))

        hrv = getattr(checkin, "hrv_rmssd", None)
        if hrv is None:
            hrv = getattr(checkin, "hrv_sdnn", None)
        if hrv is None:
            hrv = getattr(checkin, "hrv", None)  # legacy
        if hrv is not None:
            factor_data.setdefault("hrv", []).append((d, float(hrv)))

        resting_hr = getattr(checkin, "resting_hr", None)
        if resting_hr is not None:
            factor_data.setdefault("resting_hr", []).append((d, float(resting_hr)))

        stress = getattr(checkin, "stress_1_5", None)
        if stress is None:
            stress = getattr(checkin, "stress_level", None)  # legacy
        if stress is not None:
            factor_data.setdefault("stress", []).append((d, float(stress)))

        soreness = getattr(checkin, "soreness_1_5", None)
        if soreness is None:
            soreness = getattr(checkin, "soreness", None)  # legacy
        if soreness is not None:
            factor_data.setdefault("soreness", []).append((d, float(soreness)))

        # Optional proxy for fatigue when no explicit fatigue field exists.
        fatigue = getattr(checkin, "rpe_1_10", None)
        if fatigue is None:
            fatigue = getattr(checkin, "fatigue", None)  # legacy
        if fatigue is not None:
            factor_data.setdefault("fatigue", []).append((d, float(fatigue)))
    
    # Collect from BodyComposition
    body_comps = db.query(BodyComposition).filter(
        BodyComposition.athlete_id == athlete_id,
        BodyComposition.date >= start_date,
        BodyComposition.date <= end_date
    ).all()
    
    for bc in body_comps:
        d = bc.date
        if bc.weight_kg is not None:
            factor_data.setdefault("weight", []).append((d, float(bc.weight_kg)))
        if bc.bmi is not None:
            factor_data.setdefault("bmi", []).append((d, float(bc.bmi)))
    
    # Collect training metrics from Activities
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.start_time >= start_date,
        Activity.start_time <= end_date
    ).order_by(Activity.start_time).all()
    
    # Calculate weekly mileage and consistency
    weekly_data: Dict[int, List[Activity]] = {}
    for act in activities:
        week_num = act.start_time.isocalendar()[1]
        weekly_data.setdefault(week_num, []).append(act)
    
    for week_num, week_acts in weekly_data.items():
        total_distance_km = sum((a.distance_m or 0) / 1000 for a in week_acts)
        consistency = len(week_acts)
        week_date = min(a.start_time.date() for a in week_acts)
        
        factor_data.setdefault("weekly_mileage", []).append((week_date, total_distance_km))
        factor_data.setdefault("consistency", []).append((week_date, float(consistency)))
    
    return factor_data


def collect_efficiency_data(
    athlete_id: str,
    days: int,
    db: Session
) -> Dict[date, float]:
    """
    Collect efficiency values per day for correlation analysis.
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.start_time >= start_date,
        Activity.start_time <= end_date,
        Activity.avg_hr.isnot(None),
        Activity.distance_m > 0,
        Activity.duration_s > 0
    ).all()
    
    efficiency_by_date: Dict[date, List[float]] = {}
    
    for act in activities:
        # Calculate simple efficiency: pace / HR
        pace_per_km = act.duration_s / (act.distance_m / 1000)
        if act.avg_hr and act.avg_hr > 0:
            efficiency = pace_per_km / act.avg_hr
            act_date = act.start_time.date()
            efficiency_by_date.setdefault(act_date, []).append(efficiency)
    
    # Average efficiency per day
    return {d: sum(vals) / len(vals) for d, vals in efficiency_by_date.items()}


def calculate_factor_attributions(
    athlete_id: str,
    metric: TrendMetric,
    trend_direction: str,
    days: int,
    db: Session
) -> List[Attribution]:
    """
    Calculate attribution for each factor by correlating with outcome metric.
    """
    # Collect factor data
    factor_data = collect_factor_data(athlete_id, days, db)
    
    # Collect outcome data (efficiency by day)
    if metric == TrendMetric.EFFICIENCY:
        outcome_data = collect_efficiency_data(athlete_id, days, db)
    else:
        # For other metrics, use efficiency as default
        outcome_data = collect_efficiency_data(athlete_id, days, db)
    
    if not outcome_data:
        return []
    
    attributions: List[Attribution] = []
    total_contribution = 0
    
    for factor_key, config in FACTOR_CONFIGS.items():
        if factor_key not in factor_data:
            continue
        
        factor_values = factor_data[factor_key]
        best_correlation = 0.0
        best_p_value = 1.0
        best_lag = 0
        best_sample = 0
        
        # Try different time lags
        for lag in config.get("lag_days", [0]):
            x_vals = []
            y_vals = []
            
            for outcome_date, outcome_val in outcome_data.items():
                input_date = outcome_date - timedelta(days=lag)
                
                # Find matching input value
                for fdate, fval in factor_values:
                    if fdate == input_date:
                        x_vals.append(fval)
                        y_vals.append(outcome_val)
                        break
            
            if len(x_vals) >= LOW_CONFIDENCE_SAMPLE:
                r, p = pearson_correlation(x_vals, y_vals)
                if abs(r) > abs(best_correlation):
                    best_correlation = r
                    best_p_value = p
                    best_lag = lag
                    best_sample = len(x_vals)
        
        # Skip if no meaningful correlation
        if best_sample < LOW_CONFIDENCE_SAMPLE or abs(best_correlation) < LOW_CONFIDENCE_R:
            continue
        
        confidence = classify_confidence(best_correlation, best_sample, best_p_value)
        
        if confidence == AttributionConfidence.INSUFFICIENT:
            continue
        
        # Calculate contribution (simplified: based on R²)
        contribution = abs(best_correlation) ** 2 * 100
        total_contribution += contribution
        
        insight = generate_attribution_insight(
            factor_key,
            config["label"],
            best_correlation,
            trend_direction,
            best_lag
        )
        
        lag_text = f" ({best_lag}-day lag)" if best_lag > 0 else ""
        
        attributions.append(Attribution(
            factor=factor_key,
            label=f"{config['label']}{lag_text}",
            contribution_pct=contribution,
            correlation=best_correlation,
            confidence=confidence.value,
            insight=insight,
            sample_size=best_sample,
            time_lag_days=best_lag
        ))
    
    # Normalize contributions to sum to 100% (if we have any)
    if total_contribution > 0 and attributions:
        for attr in attributions:
            attr.contribution_pct = round(attr.contribution_pct / total_contribution * 100, 1)
    
    # Sort by contribution (highest first)
    attributions.sort(key=lambda a: a.contribution_pct, reverse=True)
    
    # Limit to top 8 factors
    return attributions[:8]


def get_method_contributions(
    athlete_id: str,
    db: Session
) -> MethodContribution:
    """
    Check which analytics methods contributed to the analysis.
    """
    contributions = MethodContribution()
    
    # Check efficiency trending
    try:
        from services.efficiency_analytics import get_efficiency_trends
        trends = get_efficiency_trends(UUID(athlete_id), db, days=28)
        if trends and trends.get("trend_analysis"):
            contributions.efficiency_trending = True
    except Exception:
        pass
    
    # Check TSB
    try:
        from services.training_load import TrainingLoadCalculator
        calc = TrainingLoadCalculator(db)
        load = calc.calculate_training_load(UUID(athlete_id))
        if load and load.current_ctl > 10:
            contributions.tsb_analysis = True
    except Exception:
        pass
    
    # CS check removed - archived to branch archive/cs-model-2026-01
    
    # Check Fingerprinting
    try:
        from services.pre_race_fingerprinting import generate_readiness_profile
        profile = generate_readiness_profile(athlete_id, db)
        if profile and len(profile.features) > 2:
            contributions.fingerprinting = True
    except Exception:
        pass
    
    # Check Pace Decay
    try:
        from services.pace_decay import get_athlete_decay_profile
        profile = get_athlete_decay_profile(athlete_id, db)
        if profile and profile.total_races_analyzed > 2:
            contributions.pace_decay = True
    except Exception:
        pass
    
    return contributions


def get_trend_attribution(
    athlete_id: str,
    metric: str,
    days: int,
    db: Session
) -> Optional[TrendAttributionResult]:
    """
    Main function: Get complete trend attribution analysis.
    
    Args:
        athlete_id: UUID string of athlete
        metric: Which metric to explain (efficiency, load, speed, pacing)
        days: Time window in days
        db: Database session
    
    Returns:
        TrendAttributionResult or None if insufficient data
    """
    try:
        metric_enum = TrendMetric(metric)
    except ValueError:
        metric_enum = TrendMetric.EFFICIENCY
    
    # Get trend summary
    trend_summary = get_trend_summary(athlete_id, metric_enum, days, db)
    
    if not trend_summary:
        # Return minimal result if no trend data
        trend_summary = TrendSummary(
            metric=metric_enum.value,
            direction="stable",
            change_percent=0,
            p_value=None,
            confidence="insufficient",
            period_days=days
        )
    
    # Calculate attributions
    attributions = calculate_factor_attributions(
        athlete_id,
        metric_enum,
        trend_summary.direction,
        days,
        db
    )
    
    # Get method contributions
    method_contributions = get_method_contributions(athlete_id, db)
    
    return TrendAttributionResult(
        trend_summary=trend_summary,
        attributions=attributions,
        method_contributions=method_contributions,
        generated_at=datetime.utcnow()
    )


def attribution_result_to_dict(result: TrendAttributionResult) -> Dict[str, Any]:
    """Convert TrendAttributionResult to dictionary for API response."""
    return {
        "trend_summary": {
            "metric": result.trend_summary.metric,
            "direction": result.trend_summary.direction,
            "change_percent": result.trend_summary.change_percent,
            "p_value": result.trend_summary.p_value,
            "confidence": result.trend_summary.confidence,
            "period_days": result.trend_summary.period_days
        },
        "attributions": [
            {
                "factor": a.factor,
                "label": a.label,
                "contribution_pct": a.contribution_pct,
                "correlation": round(a.correlation, 3),
                "confidence": a.confidence,
                "insight": a.insight,
                "sample_size": a.sample_size,
                "time_lag_days": a.time_lag_days
            }
            for a in result.attributions
        ],
        "method_contributions": {
            "efficiency_trending": result.method_contributions.efficiency_trending,
            "tsb_analysis": result.method_contributions.tsb_analysis,
            # critical_speed removed - archived
            "fingerprinting": result.method_contributions.fingerprinting,
            "pace_decay": result.method_contributions.pace_decay
        },
        "generated_at": result.generated_at.isoformat()
    }
