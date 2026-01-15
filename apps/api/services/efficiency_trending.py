"""
Efficiency Trending Service (V2)

Statistically rigorous efficiency trend analysis:
- Linear regression with significance testing
- Confidence classification
- Insight surfacing with actionability checks

ADR-008: Efficiency Factor Trending Enhancement
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import statistics
import math


class TrendConfidence(str, Enum):
    """Confidence level for trend detection."""
    HIGH = "high"           # p < 0.01, n >= 20, R² > 0.5
    MODERATE = "moderate"   # p < 0.05, n >= 10
    LOW = "low"             # p < 0.10, n >= 5
    INSUFFICIENT = "insufficient"  # p >= 0.10 or n < 5


class TrendDirection(str, Enum):
    """Direction of efficiency trend."""
    IMPROVING = "improving"     # Negative slope (lower EF = better)
    DECLINING = "declining"     # Positive slope
    STABLE = "stable"          # No significant trend
    INSUFFICIENT = "insufficient_data"


@dataclass
class TrendAnalysis:
    """Complete trend analysis result."""
    direction: TrendDirection
    confidence: TrendConfidence
    slope_per_week: Optional[float]  # EF change per week
    p_value: Optional[float]
    r_squared: Optional[float]
    sample_size: int
    period_days: int
    change_percent: Optional[float]  # Total % change over period
    insight_text: Optional[str]
    is_actionable: bool


def linear_regression(x: List[float], y: List[float]) -> Tuple[float, float, float, float]:
    """
    Simple linear regression: y = slope * x + intercept
    
    Returns:
        slope: Coefficient for x
        intercept: Y-intercept
        r_squared: Coefficient of determination
        std_error: Standard error of the slope
    """
    n = len(x)
    if n < 3:
        raise ValueError("Need at least 3 data points for regression")
    
    # Calculate means
    x_mean = sum(x) / n
    y_mean = sum(y) / n
    
    # Calculate slope and intercept
    numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
    denominator = sum((xi - x_mean) ** 2 for xi in x)
    
    if denominator == 0:
        return 0, y_mean, 0, float('inf')
    
    slope = numerator / denominator
    intercept = y_mean - slope * x_mean
    
    # Calculate R-squared
    y_pred = [slope * xi + intercept for xi in x]
    ss_res = sum((yi - ypi) ** 2 for yi, ypi in zip(y, y_pred))
    ss_tot = sum((yi - y_mean) ** 2 for yi in y)
    
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
    
    # Calculate standard error of slope
    # For perfect fit (ss_res = 0), use a very small std_error
    if n > 2 and denominator > 0:
        if ss_res < 1e-10:
            # Near-perfect fit - use very small std_error
            std_error = 1e-10
        else:
            mse = ss_res / (n - 2)
            std_error = math.sqrt(mse / denominator) if mse > 0 else 1e-10
    else:
        std_error = float('inf')
    
    return slope, intercept, r_squared, std_error


def calculate_p_value_from_t(t_stat: float, df: int) -> float:
    """
    Approximate two-tailed p-value from t-statistic using normal approximation.
    For df > 30, t-distribution ≈ normal distribution.
    
    For more precise values, use scipy.stats.t.sf() - but this avoids scipy dependency.
    """
    if df <= 0:
        return 1.0
    
    abs_t = abs(t_stat)
    
    # For very large t-stats (extremely significant), return very small p-value
    if abs_t > 100:
        return 0.0001  # Effectively 0, but avoid exact 0
    
    # For very small t-stats, return high p-value
    if abs_t < 0.001:
        return 1.0
    
    # Standard normal CDF approximation (Abramowitz and Stegun)
    def norm_cdf(z):
        # Clamp z to avoid overflow
        z = max(-37, min(37, z))
        
        a1 = 0.254829592
        a2 = -0.284496736
        a3 = 1.421413741
        a4 = -1.453152027
        a5 = 1.061405429
        p = 0.3275911
        
        sign = 1 if z >= 0 else -1
        z = abs(z)
        
        t = 1.0 / (1.0 + p * z)
        exp_val = math.exp(-z * z / 2)
        y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * exp_val
        
        return 0.5 * (1.0 + sign * y)
    
    # For t-distribution with df degrees of freedom
    # When df is large, t ≈ z
    # For smaller df, we need a correction factor
    if df > 30:
        correction = 1.0
    else:
        # Rough correction for small df
        correction = math.sqrt(df / (df - 2)) if df > 2 else 1.5
    
    adjusted_t = abs_t / correction
    p_value = 2 * (1 - norm_cdf(adjusted_t))
    
    return min(1.0, max(0.0, p_value))


def analyze_efficiency_trend(
    time_series: List[Dict],
    min_sample_size: int = 5
) -> TrendAnalysis:
    """
    Analyze efficiency trend with statistical rigor.
    
    Args:
        time_series: List of dicts with 'date' and 'efficiency_factor'
        min_sample_size: Minimum data points required
    
    Returns:
        TrendAnalysis with direction, confidence, and insight
    """
    # Extract valid data points
    valid_points = [
        (datetime.fromisoformat(p['date'].replace('Z', '+00:00') if p['date'].endswith('Z') else p['date']), 
         p['efficiency_factor'])
        for p in time_series
        if p.get('efficiency_factor') is not None
    ]
    
    n = len(valid_points)
    
    if n < min_sample_size:
        return TrendAnalysis(
            direction=TrendDirection.INSUFFICIENT,
            confidence=TrendConfidence.INSUFFICIENT,
            slope_per_week=None,
            p_value=None,
            r_squared=None,
            sample_size=n,
            period_days=0,
            change_percent=None,
            insight_text=f"Need at least {min_sample_size} quality runs to detect trends. Currently have {n}.",
            is_actionable=False
        )
    
    # Sort by date
    valid_points.sort(key=lambda x: x[0])
    
    # Convert dates to days from start
    start_date = valid_points[0][0]
    x = [(p[0] - start_date).days for p in valid_points]
    y = [p[1] for p in valid_points]
    
    period_days = x[-1] - x[0] if x else 0
    
    # Perform linear regression
    try:
        slope, intercept, r_squared, std_error = linear_regression(
            [float(xi) for xi in x], 
            y
        )
    except ValueError as e:
        return TrendAnalysis(
            direction=TrendDirection.INSUFFICIENT,
            confidence=TrendConfidence.INSUFFICIENT,
            slope_per_week=None,
            p_value=None,
            r_squared=None,
            sample_size=n,
            period_days=period_days,
            change_percent=None,
            insight_text=str(e),
            is_actionable=False
        )
    
    # Convert slope to per-week (slope is per day)
    slope_per_week = slope * 7
    
    # Calculate t-statistic and p-value
    if std_error > 0 and std_error != float('inf'):
        t_stat = slope / std_error
        df = n - 2
        p_value = calculate_p_value_from_t(t_stat, df)
    else:
        t_stat = 0
        p_value = 1.0
    
    # Calculate total change percentage
    if y[0] != 0:
        predicted_start = intercept
        predicted_end = slope * x[-1] + intercept
        change_percent = ((predicted_end - predicted_start) / predicted_start) * 100
    else:
        change_percent = None
    
    # Determine confidence level
    if p_value < 0.01 and n >= 20 and r_squared > 0.5:
        confidence = TrendConfidence.HIGH
    elif p_value < 0.05 and n >= 10:
        confidence = TrendConfidence.MODERATE
    elif p_value < 0.10 and n >= 5:
        confidence = TrendConfidence.LOW
    else:
        confidence = TrendConfidence.INSUFFICIENT
    
    # Determine direction (negative slope = improving for EF)
    # Only declare direction if statistically significant
    if p_value < 0.05:
        if slope < 0:
            direction = TrendDirection.IMPROVING
        elif slope > 0:
            direction = TrendDirection.DECLINING
        else:
            direction = TrendDirection.STABLE
    elif p_value < 0.10:
        # Suggestive but not significant
        direction = TrendDirection.STABLE
    else:
        direction = TrendDirection.STABLE
    
    # Generate insight text
    insight_text = _generate_trend_insight(
        direction, confidence, slope_per_week, change_percent, period_days, n
    )
    
    # Determine if actionable
    # Actionable if:
    # 1. Statistically significant (p < 0.05)
    # 2. Effect size meaningful (>3% change)
    # 3. Enough data (n >= 10)
    is_actionable = (
        p_value < 0.05 and 
        abs(change_percent or 0) > 3.0 and 
        n >= 10
    )
    
    return TrendAnalysis(
        direction=direction,
        confidence=confidence,
        slope_per_week=round(slope_per_week, 4) if slope_per_week else None,
        p_value=round(p_value, 4) if p_value else None,
        r_squared=round(r_squared, 4) if r_squared else None,
        sample_size=n,
        period_days=period_days,
        change_percent=round(change_percent, 2) if change_percent else None,
        insight_text=insight_text,
        is_actionable=is_actionable
    )


def _generate_trend_insight(
    direction: TrendDirection,
    confidence: TrendConfidence,
    slope_per_week: Optional[float],
    change_percent: Optional[float],
    period_days: int,
    sample_size: int
) -> str:
    """Generate human-readable insight text."""
    
    if direction == TrendDirection.INSUFFICIENT:
        return f"Need more data to detect trends. Currently have {sample_size} runs."
    
    if confidence == TrendConfidence.INSUFFICIENT:
        return "No clear trend detected. Efficiency is variable but not trending."
    
    weeks = period_days / 7
    
    if direction == TrendDirection.IMPROVING:
        if confidence == TrendConfidence.HIGH:
            return f"Efficiency improving significantly over {weeks:.0f} weeks ({abs(change_percent or 0):.1f}% better). Aerobic fitness is building."
        elif confidence == TrendConfidence.MODERATE:
            return f"Efficiency trending better over {weeks:.0f} weeks. Pattern suggests fitness gains."
        else:
            return f"Slight efficiency improvement detected. Continue current approach to confirm."
    
    elif direction == TrendDirection.DECLINING:
        if confidence == TrendConfidence.HIGH:
            return f"Efficiency declining over {weeks:.0f} weeks ({abs(change_percent or 0):.1f}% worse). Consider recovery or load adjustment."
        elif confidence == TrendConfidence.MODERATE:
            return f"Efficiency trending worse. May indicate fatigue accumulation."
        else:
            return f"Slight efficiency decline detected. Monitor for continued pattern."
    
    else:  # STABLE
        if sample_size >= 20:
            return "Efficiency stable. Consistent training but no fitness breakthrough."
        else:
            return "No significant trend detected. Continue building data."


def calculate_efficiency_percentile(
    current_ef: float,
    historical_efs: List[float]
) -> Optional[float]:
    """
    Calculate where current efficiency sits in athlete's own history.
    
    Returns percentile (0-100), where lower is better for EF.
    """
    if not historical_efs or len(historical_efs) < 5:
        return None
    
    # Count how many historical values are worse (higher) than current
    worse_count = sum(1 for ef in historical_efs if ef > current_ef)
    percentile = (worse_count / len(historical_efs)) * 100
    
    return round(percentile, 1)


def estimate_days_to_pr_efficiency(
    current_ef: float,
    pr_ef: float,
    slope_per_week: float
) -> Optional[int]:
    """
    Estimate days until current trend would reach PR efficiency level.
    
    Returns None if:
    - Not improving (positive slope)
    - Already at or better than PR
    - Would take more than 365 days
    """
    if slope_per_week >= 0:
        return None  # Not improving
    
    if current_ef <= pr_ef:
        return 0  # Already at or better than PR
    
    # EF difference to close
    ef_gap = current_ef - pr_ef
    
    # Weeks to close gap
    weeks_needed = ef_gap / abs(slope_per_week)
    days_needed = int(weeks_needed * 7)
    
    if days_needed > 365:
        return None  # Too far out to be meaningful
    
    return days_needed


def to_dict(analysis: TrendAnalysis) -> Dict:
    """Convert TrendAnalysis to dictionary for API response."""
    return {
        "direction": analysis.direction.value,
        "confidence": analysis.confidence.value,
        "slope_per_week": analysis.slope_per_week,
        "p_value": analysis.p_value,
        "r_squared": analysis.r_squared,
        "sample_size": analysis.sample_size,
        "period_days": analysis.period_days,
        "change_percent": analysis.change_percent,
        "insight_text": analysis.insight_text,
        "is_actionable": analysis.is_actionable
    }
