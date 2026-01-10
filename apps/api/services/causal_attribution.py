"""
Causal Attribution Engine

THE MOAT: Moving from correlation to causation.

This engine implements:
1. DUAL-FREQUENCY ANALYSIS:
   - Readiness Loop (0-7 days): Sleep, HRV, Stress, Nutrition - immediate impacts
   - Fitness Loop (14-42 days): Volume, Zone Distribution, Long Runs - adaptation

2. GRANGER CAUSALITY TEST:
   - Does X happening BEFORE Y help predict Y better than Y's own history?
   - If yes, X "Granger-causes" Y (statistically defensible leading indicator)

3. LAG DETECTION:
   - Discovers optimal lag for each input-output pair from THIS athlete's data
   - "Sleep changes preceded efficiency gains by 2 days (Granger p<0.05)"

PHILOSOPHY:
- N=1 is the only N. Population research informs questions, not answers.
- Sparse, forensic language. "Data hints X preceded Y. Test it."
- Only surface insights we can statistically defend.
- Never prescribe. Report math. Athlete decides.

OUTPUT:
- Leading Indicators with confidence and statistical backing
- Injected into AI Coach context for smarter recommendations
- Surfaced in "Why This Trend?" dashboard button
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
from enum import Enum
import statistics
import math
from decimal import Decimal

from sqlalchemy import func, and_, text
from sqlalchemy.orm import Session

from models import Activity, DailyCheckin, BodyComposition, NutritionEntry


# =============================================================================
# CONFIGURATION
# =============================================================================

class FrequencyLoop(str, Enum):
    """Dual-Frequency Analysis Loops"""
    READINESS = "readiness"  # 0-7 days: Acute impacts
    FITNESS = "fitness"      # 14-42 days: Chronic adaptation


class CausalConfidence(str, Enum):
    """Confidence in causal relationship"""
    HIGH = "high"           # Granger p < 0.01, strong effect
    MODERATE = "moderate"   # Granger p < 0.05
    SUGGESTIVE = "suggestive"  # p < 0.10, worth watching
    INSUFFICIENT = "insufficient"  # Not enough data or p >= 0.10


class ImpactDirection(str, Enum):
    """Direction of causal impact"""
    POSITIVE = "positive"    # Input PRECEDES improvement
    NEGATIVE = "negative"    # Input PRECEDES decline
    NEUTRAL = "neutral"      # No clear direction


# Input variable configurations
READINESS_INPUTS = {
    "sleep_hours": {
        "name": "Sleep Duration",
        "icon": "😴",
        "lag_range": (0, 7),
        "positive_direction": 1,  # More sleep = better
        "min_samples": 7,
    },
    "hrv_rmssd": {
        "name": "HRV",
        "icon": "💓",
        "lag_range": (0, 7),
        "positive_direction": 1,  # Higher HRV = better readiness
        "min_samples": 5,
    },
    "stress": {
        "name": "Stress Level",
        "icon": "😤",
        "lag_range": (0, 7),
        "positive_direction": -1,  # Lower stress = better
        "min_samples": 5,
    },
    "soreness": {
        "name": "Muscle Soreness",
        "icon": "🦵",
        "lag_range": (0, 7),
        "positive_direction": -1,  # Lower soreness = better
        "min_samples": 5,
    },
    "resting_hr": {
        "name": "Resting HR",
        "icon": "❤️",
        "lag_range": (0, 7),
        "positive_direction": -1,  # Lower RHR = better recovery
        "min_samples": 5,
    },
}

FITNESS_INPUTS = {
    "weekly_volume_km": {
        "name": "Weekly Volume",
        "icon": "📏",
        "lag_range": (14, 42),  # Supercompensation window
        "positive_direction": 1,  # More volume = better (usually)
        "min_samples": 4,
    },
    "threshold_pct": {
        "name": "Threshold Work %",
        "icon": "🔥",
        "lag_range": (14, 42),
        "positive_direction": 1,  # More quality = better
        "min_samples": 4,
    },
    "long_run_pct": {
        "name": "Long Run %",
        "icon": "🛤️",
        "lag_range": (21, 42),  # Long runs take longer to manifest
        "positive_direction": 1,
        "min_samples": 4,
    },
    "consistency": {
        "name": "Training Consistency",
        "icon": "📅",
        "lag_range": (14, 28),
        "positive_direction": 1,  # More consistent = better
        "min_samples": 4,
    },
    "acwr": {
        "name": "Training Load (ACWR)",
        "icon": "⚡",
        "lag_range": (7, 21),  # ACWR effects are medium-term
        "positive_direction": 0,  # Neutral - depends on context
        "min_samples": 4,
    },
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class TimeSeries:
    """A time series of values for a single variable."""
    name: str
    dates: List[date]
    values: List[float]
    
    def __len__(self):
        return len(self.values)
    
    def align_with(self, other: 'TimeSeries', lag: int = 0) -> Tuple[List[float], List[float]]:
        """
        Align this series with another, applying a lag.
        
        If lag > 0: self is shifted EARLIER (self causes other)
        Returns only overlapping pairs.
        """
        aligned_self = []
        aligned_other = []
        
        # Create date -> value maps
        self_map = dict(zip(self.dates, self.values))
        other_map = dict(zip(other.dates, other.values))
        
        for d, v in other_map.items():
            # Look for self value 'lag' days before this date
            lagged_date = d - timedelta(days=lag)
            if lagged_date in self_map:
                aligned_self.append(self_map[lagged_date])
                aligned_other.append(v)
        
        return aligned_self, aligned_other


@dataclass
class GrangerResult:
    """Result of Granger causality test."""
    input_name: str
    output_name: str
    optimal_lag: int
    f_statistic: float
    p_value: float
    is_significant: bool
    sample_size: int
    effect_direction: ImpactDirection
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_name": self.input_name,
            "output_name": self.output_name,
            "optimal_lag": self.optimal_lag,
            "f_statistic": round(self.f_statistic, 3),
            "p_value": round(self.p_value, 4),
            "is_significant": self.is_significant,
            "sample_size": self.sample_size,
            "effect_direction": self.effect_direction.value,
        }


@dataclass
class LeadingIndicator:
    """A discovered leading indicator (causal relationship)."""
    input_key: str
    input_name: str
    icon: str
    loop: FrequencyLoop
    
    # The causal finding
    lag_days: int
    effect_direction: ImpactDirection
    
    # Statistical backing
    granger_p: float
    correlation_r: float
    sample_size: int
    confidence: CausalConfidence
    
    # Human-readable insight (sparse, forensic)
    insight: str
    
    # Raw data for verification
    granger_result: Optional[GrangerResult] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_key": self.input_key,
            "input_name": self.input_name,
            "icon": self.icon,
            "loop": self.loop.value,
            "lag_days": self.lag_days,
            "effect_direction": self.effect_direction.value,
            "granger_p": round(self.granger_p, 4),
            "correlation_r": round(self.correlation_r, 3),
            "sample_size": self.sample_size,
            "confidence": self.confidence.value,
            "insight": self.insight,
        }


@dataclass
class CausalAnalysisResult:
    """Complete result of causal attribution analysis."""
    athlete_id: str
    analysis_date: date
    analysis_period_days: int
    
    # Dual-frequency results
    readiness_indicators: List[LeadingIndicator]
    fitness_indicators: List[LeadingIndicator]
    
    # Combined top indicators
    top_indicators: List[LeadingIndicator]
    
    # Data quality
    data_quality_score: float
    data_quality_notes: List[str]
    
    # Context block for GPT injection
    context_block: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "athlete_id": self.athlete_id,
            "analysis_date": self.analysis_date.isoformat(),
            "analysis_period_days": self.analysis_period_days,
            "readiness_indicators": [i.to_dict() for i in self.readiness_indicators],
            "fitness_indicators": [i.to_dict() for i in self.fitness_indicators],
            "top_indicators": [i.to_dict() for i in self.top_indicators],
            "data_quality_score": round(self.data_quality_score, 2),
            "data_quality_notes": self.data_quality_notes,
            "context_block": self.context_block,
        }


# =============================================================================
# STATISTICAL FUNCTIONS
# =============================================================================

def pearson_correlation(x: List[float], y: List[float]) -> Tuple[float, float]:
    """
    Calculate Pearson correlation coefficient and p-value.
    
    Returns (r, p_value)
    """
    n = len(x)
    if n < 5:
        return 0.0, 1.0
    
    # Calculate means
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    
    # Calculate correlation
    numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    sum_sq_x = sum((xi - mean_x) ** 2 for xi in x)
    sum_sq_y = sum((yi - mean_y) ** 2 for yi in y)
    
    denominator = math.sqrt(sum_sq_x * sum_sq_y)
    if denominator == 0:
        return 0.0, 1.0
    
    r = numerator / denominator
    
    # Calculate t-statistic for p-value
    if abs(r) >= 1.0:
        return r, 0.0 if abs(r) == 1.0 else 1.0
    
    t_stat = r * math.sqrt((n - 2) / (1 - r ** 2))
    
    # Approximate p-value using t-distribution
    # Using a simple approximation for the CDF
    df = n - 2
    p_value = _t_to_pvalue(abs(t_stat), df)
    
    return r, p_value


def _t_to_pvalue(t: float, df: int) -> float:
    """
    Approximate two-tailed p-value from t-statistic.
    Uses a simple approximation that's reasonably accurate for df > 5.
    """
    # Approximation for t-distribution p-value
    # More accurate than a simple formula, less complex than scipy
    x = df / (df + t * t)
    
    # Beta function approximation
    if x > 0.5:
        # Use reflection
        p = 1.0 - 0.5 * _beta_incomplete(df / 2, 0.5, 1 - x)
    else:
        p = 0.5 * _beta_incomplete(df / 2, 0.5, x)
    
    return 2 * min(p, 1 - p)  # Two-tailed


def _beta_incomplete(a: float, b: float, x: float) -> float:
    """
    Incomplete beta function approximation.
    """
    if x < 0 or x > 1:
        return 0.0
    
    # Simple continued fraction approximation
    # Sufficient for our p-value needs
    if x > (a + 1) / (a + b + 2):
        return 1.0 - _beta_incomplete(b, a, 1 - x)
    
    # Continued fraction
    result = 0.0
    term = 1.0
    
    for n in range(1, 100):  # Max iterations
        if n == 1:
            num = 1.0
        elif n % 2 == 0:
            m = n // 2
            num = m * (b - m) * x / ((a + 2 * m - 1) * (a + 2 * m))
        else:
            m = (n - 1) // 2
            num = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
        
        term *= num
        result += term
        
        if abs(term) < 1e-10:
            break
    
    # Normalize
    beta_factor = math.exp(
        a * math.log(x) + b * math.log(1 - x) - 
        math.log(a) - _log_beta(a, b)
    )
    
    return beta_factor * (1 + result)


def _log_beta(a: float, b: float) -> float:
    """Log of beta function using gamma function."""
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def granger_causality_test(
    cause: List[float], 
    effect: List[float], 
    lag: int
) -> Tuple[float, float, bool]:
    """
    Simplified Granger causality test.
    
    Tests if 'cause' at time t-lag helps predict 'effect' at time t,
    beyond just using effect's own history.
    
    Returns (F-statistic, p-value, is_significant)
    """
    n = len(effect)
    if n < lag + 5:  # Need enough data points
        return 0.0, 1.0, False
    
    # Create lagged series
    # effect[t] predicted by: effect[t-1], effect[t-2], ..., effect[t-lag]
    # and optionally: cause[t-1], cause[t-2], ..., cause[t-lag]
    
    # Restricted model: effect ~ effect_history
    # Unrestricted model: effect ~ effect_history + cause_history
    
    y = effect[lag:]  # Target
    n_obs = len(y)
    
    if n_obs < 5:
        return 0.0, 1.0, False
    
    # Build lagged features
    effect_lags = []
    cause_lags = []
    
    for i in range(1, lag + 1):
        effect_lags.append(effect[lag - i: n - i])
        cause_lags.append(cause[lag - i: n - i])
    
    # Calculate RSS for restricted model (effect history only)
    # Using simple linear regression approximation
    rss_restricted = _calculate_rss(y, effect_lags)
    
    # Calculate RSS for unrestricted model (effect + cause history)
    all_lags = effect_lags + cause_lags
    rss_unrestricted = _calculate_rss(y, all_lags)
    
    # F-test
    # F = ((RSS_r - RSS_u) / q) / (RSS_u / (n - k))
    q = lag  # Number of additional parameters (cause lags)
    k = 2 * lag + 1  # Total parameters in unrestricted model
    
    if rss_unrestricted == 0 or n_obs <= k:
        return 0.0, 1.0, False
    
    f_stat = ((rss_restricted - rss_unrestricted) / q) / (rss_unrestricted / (n_obs - k))
    
    if f_stat < 0:
        f_stat = 0
    
    # P-value from F-distribution
    p_value = _f_to_pvalue(f_stat, q, n_obs - k)
    
    is_significant = p_value < 0.05
    
    return f_stat, p_value, is_significant


def _calculate_rss(y: List[float], x_features: List[List[float]]) -> float:
    """
    Calculate Residual Sum of Squares for OLS regression.
    Simple implementation for our needs.
    """
    if not x_features or not y:
        return float('inf')
    
    n = len(y)
    
    # Simple approach: use mean as baseline prediction
    # Then adjust based on correlation with each feature
    
    mean_y = sum(y) / n
    
    # Start with baseline prediction
    predictions = [mean_y] * n
    
    # Add contribution from each feature (simple linear combination)
    for feature in x_features:
        if len(feature) != n:
            continue
        
        mean_f = sum(feature) / n
        var_f = sum((f - mean_f) ** 2 for f in feature)
        
        if var_f == 0:
            continue
        
        cov = sum((f - mean_f) * (yi - mean_y) for f, yi in zip(feature, y))
        beta = cov / var_f
        
        # Update predictions
        for i in range(n):
            predictions[i] += beta * (feature[i] - mean_f) / len(x_features)
    
    # Calculate RSS
    rss = sum((yi - pred) ** 2 for yi, pred in zip(y, predictions))
    
    return rss


def _f_to_pvalue(f: float, df1: int, df2: int) -> float:
    """
    Approximate p-value from F-statistic.
    """
    if f <= 0 or df1 <= 0 or df2 <= 0:
        return 1.0
    
    # Use beta function approximation
    x = df2 / (df2 + df1 * f)
    p = _beta_incomplete(df2 / 2, df1 / 2, x)
    
    return min(1.0, max(0.0, p))


# =============================================================================
# CAUSAL ATTRIBUTION ENGINE
# =============================================================================

class CausalAttributionEngine:
    """
    The Causal Attribution Engine.
    
    Discovers time-lagged causal relationships between inputs and performance.
    Uses Granger causality testing with dual-frequency analysis.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def analyze(
        self,
        athlete_id: UUID,
        analysis_days: int = 90,
        output_metric: str = "efficiency",  # "efficiency" or "pace"
    ) -> CausalAnalysisResult:
        """
        Main entry point: Discover leading indicators for this athlete.
        
        Args:
            athlete_id: The athlete to analyze
            analysis_days: How many days of history to analyze
            output_metric: Which performance output to explain
            
        Returns:
            CausalAnalysisResult with discovered leading indicators
        """
        analysis_date = date.today()
        start_date = analysis_date - timedelta(days=analysis_days)
        
        # 1. Collect output time series (the thing we're trying to predict)
        output_series = self._get_output_series(
            athlete_id, start_date, analysis_date, output_metric
        )
        
        if len(output_series) < 10:
            return self._empty_result(athlete_id, analysis_date, analysis_days,
                                      "Insufficient activity data for causal analysis.")
        
        # 2. Analyze Readiness Loop (0-7 day lags)
        readiness_indicators = self._analyze_loop(
            athlete_id, start_date, analysis_date, 
            output_series, READINESS_INPUTS, FrequencyLoop.READINESS
        )
        
        # 3. Analyze Fitness Loop (14-42 day lags)
        fitness_indicators = self._analyze_loop(
            athlete_id, start_date, analysis_date,
            output_series, FITNESS_INPUTS, FrequencyLoop.FITNESS
        )
        
        # 4. Combine and rank top indicators
        all_indicators = readiness_indicators + fitness_indicators
        all_indicators.sort(key=lambda x: x.granger_p)
        top_indicators = [i for i in all_indicators if i.confidence != CausalConfidence.INSUFFICIENT][:5]
        
        # 5. Calculate data quality
        data_quality, quality_notes = self._calculate_data_quality(
            athlete_id, start_date, analysis_date
        )
        
        # 6. Generate context block for GPT
        context_block = self._build_context_block(
            readiness_indicators, fitness_indicators, top_indicators
        )
        
        return CausalAnalysisResult(
            athlete_id=str(athlete_id),
            analysis_date=analysis_date,
            analysis_period_days=analysis_days,
            readiness_indicators=readiness_indicators,
            fitness_indicators=fitness_indicators,
            top_indicators=top_indicators,
            data_quality_score=data_quality,
            data_quality_notes=quality_notes,
            context_block=context_block,
        )
    
    def analyze_trend(
        self,
        athlete_id: UUID,
        trend_name: str,
        trend_direction: str,  # "up" or "down"
        trend_magnitude_pct: float,
        recent_days: int = 28,
    ) -> List[LeadingIndicator]:
        """
        Answer "Why This Trend?" for a specific trend.
        
        Example: Efficiency up 12% over last 28 days. What preceded this?
        
        Returns leading indicators that may explain the trend.
        """
        analysis_date = date.today()
        start_date = analysis_date - timedelta(days=recent_days + 42)  # Need history before trend
        
        # Get output series
        output_series = self._get_output_series(
            athlete_id, start_date, analysis_date, "efficiency"
        )
        
        if len(output_series) < 10:
            return []
        
        # Analyze both loops
        readiness_indicators = self._analyze_loop(
            athlete_id, start_date, analysis_date,
            output_series, READINESS_INPUTS, FrequencyLoop.READINESS
        )
        
        fitness_indicators = self._analyze_loop(
            athlete_id, start_date, analysis_date,
            output_series, FITNESS_INPUTS, FrequencyLoop.FITNESS
        )
        
        # Filter for indicators that match trend direction
        relevant_indicators = []
        trend_positive = trend_direction == "up"
        
        for indicator in readiness_indicators + fitness_indicators:
            if indicator.confidence == CausalConfidence.INSUFFICIENT:
                continue
            
            # Match direction
            if trend_positive and indicator.effect_direction == ImpactDirection.POSITIVE:
                relevant_indicators.append(indicator)
            elif not trend_positive and indicator.effect_direction == ImpactDirection.NEGATIVE:
                relevant_indicators.append(indicator)
        
        # Sort by significance
        relevant_indicators.sort(key=lambda x: x.granger_p)
        
        return relevant_indicators[:3]  # Top 3 explanations
    
    def _get_output_series(
        self,
        athlete_id: UUID,
        start_date: date,
        end_date: date,
        metric: str,
    ) -> TimeSeries:
        """Get the performance output time series."""
        activities = self.db.query(
            func.date(Activity.start_time).label("activity_date"),
            Activity.duration_s,
            Activity.distance_m,
            Activity.avg_hr,
        ).filter(
            Activity.athlete_id == athlete_id,
            func.date(Activity.start_time) >= start_date,
            func.date(Activity.start_time) <= end_date,
            Activity.sport.ilike("run"),
            Activity.duration_s.isnot(None),
            Activity.distance_m.isnot(None),
        ).order_by(func.date(Activity.start_time)).all()
        
        dates = []
        values = []
        
        for a in activities:
            if not a.duration_s or not a.distance_m or a.distance_m == 0:
                continue
            
            pace_per_km = a.duration_s / (a.distance_m / 1000)
            
            if metric == "efficiency" and a.avg_hr and a.avg_hr > 0:
                # Efficiency = pace / HR (lower is better)
                efficiency = pace_per_km / a.avg_hr
                dates.append(a.activity_date)
                values.append(efficiency)
            elif metric == "pace":
                dates.append(a.activity_date)
                values.append(pace_per_km)
        
        return TimeSeries(name=metric, dates=dates, values=values)
    
    def _analyze_loop(
        self,
        athlete_id: UUID,
        start_date: date,
        end_date: date,
        output_series: TimeSeries,
        input_config: Dict,
        loop: FrequencyLoop,
    ) -> List[LeadingIndicator]:
        """Analyze a single frequency loop (Readiness or Fitness)."""
        indicators = []
        
        for input_key, config in input_config.items():
            # Get input time series
            input_series = self._get_input_series(
                athlete_id, start_date, end_date, input_key
            )
            
            if len(input_series) < config["min_samples"]:
                continue
            
            # Test Granger causality at different lags
            min_lag, max_lag = config["lag_range"]
            best_result = None
            best_lag = min_lag
            
            for lag in range(min_lag, max_lag + 1, max(1, (max_lag - min_lag) // 7)):
                # Align series with lag
                x_aligned, y_aligned = input_series.align_with(output_series, lag)
                
                if len(x_aligned) < 5:
                    continue
                
                # Test Granger causality
                f_stat, p_value, is_sig = granger_causality_test(
                    x_aligned, y_aligned, min(lag, 3)  # Use smaller AR order
                )
                
                if best_result is None or p_value < best_result[1]:
                    best_result = (f_stat, p_value, is_sig)
                    best_lag = lag
            
            if best_result is None:
                continue
            
            f_stat, p_value, is_significant = best_result
            
            # Also calculate correlation at best lag
            x_aligned, y_aligned = input_series.align_with(output_series, best_lag)
            corr_r, corr_p = pearson_correlation(x_aligned, y_aligned)
            
            # Determine effect direction
            pos_dir = config["positive_direction"]
            if pos_dir == 0:
                effect_direction = ImpactDirection.NEUTRAL
            elif (corr_r > 0 and pos_dir > 0) or (corr_r < 0 and pos_dir < 0):
                # Positive input -> negative correlation with efficiency (lower = better)
                effect_direction = ImpactDirection.POSITIVE
            else:
                effect_direction = ImpactDirection.NEGATIVE
            
            # Determine confidence
            if p_value < 0.01 and abs(corr_r) >= 0.4:
                confidence = CausalConfidence.HIGH
            elif p_value < 0.05:
                confidence = CausalConfidence.MODERATE
            elif p_value < 0.10:
                confidence = CausalConfidence.SUGGESTIVE
            else:
                confidence = CausalConfidence.INSUFFICIENT
            
            # Generate insight
            insight = self._generate_insight(
                config["name"], best_lag, effect_direction, 
                p_value, corr_r, loop, confidence
            )
            
            indicators.append(LeadingIndicator(
                input_key=input_key,
                input_name=config["name"],
                icon=config["icon"],
                loop=loop,
                lag_days=best_lag,
                effect_direction=effect_direction,
                granger_p=p_value,
                correlation_r=corr_r,
                sample_size=len(x_aligned),
                confidence=confidence,
                insight=insight,
                granger_result=GrangerResult(
                    input_name=input_key,
                    output_name=output_series.name,
                    optimal_lag=best_lag,
                    f_statistic=f_stat,
                    p_value=p_value,
                    is_significant=is_significant,
                    sample_size=len(x_aligned),
                    effect_direction=effect_direction,
                ),
            ))
        
        return indicators
    
    def _get_input_series(
        self,
        athlete_id: UUID,
        start_date: date,
        end_date: date,
        input_key: str,
    ) -> TimeSeries:
        """Get input time series based on key."""
        
        # Readiness inputs from DailyCheckin
        if input_key == "sleep_hours":
            data = self.db.query(
                DailyCheckin.date,
                DailyCheckin.sleep_h,
            ).filter(
                DailyCheckin.athlete_id == athlete_id,
                DailyCheckin.date >= start_date,
                DailyCheckin.date <= end_date,
                DailyCheckin.sleep_h.isnot(None),
            ).order_by(DailyCheckin.date).all()
            
            dates = [d.date for d in data]
            values = [float(d.sleep_h) for d in data]
            return TimeSeries(name=input_key, dates=dates, values=values)
        
        elif input_key == "hrv_rmssd":
            data = self.db.query(
                DailyCheckin.date,
                DailyCheckin.hrv_rmssd,
            ).filter(
                DailyCheckin.athlete_id == athlete_id,
                DailyCheckin.date >= start_date,
                DailyCheckin.date <= end_date,
                DailyCheckin.hrv_rmssd.isnot(None),
            ).order_by(DailyCheckin.date).all()
            
            dates = [d.date for d in data]
            values = [float(d.hrv_rmssd) for d in data]
            return TimeSeries(name=input_key, dates=dates, values=values)
        
        elif input_key == "stress":
            data = self.db.query(
                DailyCheckin.date,
                DailyCheckin.stress_1_5,
            ).filter(
                DailyCheckin.athlete_id == athlete_id,
                DailyCheckin.date >= start_date,
                DailyCheckin.date <= end_date,
                DailyCheckin.stress_1_5.isnot(None),
            ).order_by(DailyCheckin.date).all()
            
            dates = [d.date for d in data]
            values = [float(d.stress_1_5) for d in data]
            return TimeSeries(name=input_key, dates=dates, values=values)
        
        elif input_key == "soreness":
            data = self.db.query(
                DailyCheckin.date,
                DailyCheckin.soreness_1_5,
            ).filter(
                DailyCheckin.athlete_id == athlete_id,
                DailyCheckin.date >= start_date,
                DailyCheckin.date <= end_date,
                DailyCheckin.soreness_1_5.isnot(None),
            ).order_by(DailyCheckin.date).all()
            
            dates = [d.date for d in data]
            values = [float(d.soreness_1_5) for d in data]
            return TimeSeries(name=input_key, dates=dates, values=values)
        
        elif input_key == "resting_hr":
            data = self.db.query(
                DailyCheckin.date,
                DailyCheckin.resting_hr,
            ).filter(
                DailyCheckin.athlete_id == athlete_id,
                DailyCheckin.date >= start_date,
                DailyCheckin.date <= end_date,
                DailyCheckin.resting_hr.isnot(None),
            ).order_by(DailyCheckin.date).all()
            
            dates = [d.date for d in data]
            values = [float(d.resting_hr) for d in data]
            return TimeSeries(name=input_key, dates=dates, values=values)
        
        # Fitness inputs from Activity aggregation
        elif input_key == "weekly_volume_km":
            return self._get_weekly_volume_series(athlete_id, start_date, end_date)
        
        elif input_key == "threshold_pct":
            return self._get_workout_type_series(athlete_id, start_date, end_date, "threshold")
        
        elif input_key == "long_run_pct":
            return self._get_workout_type_series(athlete_id, start_date, end_date, "long")
        
        elif input_key == "consistency":
            return self._get_consistency_series(athlete_id, start_date, end_date)
        
        elif input_key == "acwr":
            return self._get_acwr_series(athlete_id, start_date, end_date)
        
        # Default empty series
        return TimeSeries(name=input_key, dates=[], values=[])
    
    def _get_weekly_volume_series(
        self, 
        athlete_id: UUID, 
        start_date: date, 
        end_date: date
    ) -> TimeSeries:
        """Calculate rolling 7-day volume for each day."""
        activities = self.db.query(
            func.date(Activity.start_time).label("activity_date"),
            Activity.distance_m,
        ).filter(
            Activity.athlete_id == athlete_id,
            func.date(Activity.start_time) >= start_date - timedelta(days=7),
            func.date(Activity.start_time) <= end_date,
            Activity.sport.ilike("run"),
        ).all()
        
        # Build date -> distance map
        distance_map: Dict[date, float] = {}
        for a in activities:
            d = a.activity_date
            distance_map[d] = distance_map.get(d, 0) + (a.distance_m or 0)
        
        # Calculate rolling 7-day volume
        dates = []
        values = []
        
        current = start_date
        while current <= end_date:
            vol_7d = sum(
                distance_map.get(current - timedelta(days=i), 0) 
                for i in range(7)
            ) / 1000  # Convert to km
            
            dates.append(current)
            values.append(vol_7d)
            current += timedelta(days=1)
        
        return TimeSeries(name="weekly_volume_km", dates=dates, values=values)
    
    def _get_workout_type_series(
        self,
        athlete_id: UUID,
        start_date: date,
        end_date: date,
        workout_category: str,
    ) -> TimeSeries:
        """Calculate rolling % of volume in a workout category."""
        type_keywords = {
            "threshold": ["tempo", "threshold", "cruise"],
            "long": ["long", "endurance"],
            "easy": ["easy", "recovery", "aerobic"],
            "interval": ["interval", "vo2", "speed", "track", "fartlek"],
        }
        
        keywords = type_keywords.get(workout_category, [workout_category])
        
        activities = self.db.query(
            func.date(Activity.start_time).label("activity_date"),
            Activity.distance_m,
            Activity.workout_type,
        ).filter(
            Activity.athlete_id == athlete_id,
            func.date(Activity.start_time) >= start_date - timedelta(days=28),
            func.date(Activity.start_time) <= end_date,
            Activity.sport.ilike("run"),
        ).all()
        
        # Build date -> (category_distance, total_distance) map
        daily_data: Dict[date, Tuple[float, float]] = {}
        
        for a in activities:
            d = a.activity_date
            dist = a.distance_m or 0
            wt = (a.workout_type or "").lower()
            
            is_category = any(kw in wt for kw in keywords)
            cat_dist = dist if is_category else 0
            
            if d not in daily_data:
                daily_data[d] = (0, 0)
            
            daily_data[d] = (
                daily_data[d][0] + cat_dist,
                daily_data[d][1] + dist,
            )
        
        # Calculate rolling 28-day percentage
        dates = []
        values = []
        
        current = start_date
        while current <= end_date:
            cat_sum = 0
            total_sum = 0
            
            for i in range(28):
                day = current - timedelta(days=i)
                if day in daily_data:
                    cat_sum += daily_data[day][0]
                    total_sum += daily_data[day][1]
            
            pct = (cat_sum / total_sum * 100) if total_sum > 0 else 0
            dates.append(current)
            values.append(pct)
            current += timedelta(days=1)
        
        return TimeSeries(name=f"{workout_category}_pct", dates=dates, values=values)
    
    def _get_consistency_series(
        self,
        athlete_id: UUID,
        start_date: date,
        end_date: date,
    ) -> TimeSeries:
        """Calculate rolling consistency (runs per week)."""
        activities = self.db.query(
            func.date(Activity.start_time).label("activity_date"),
        ).filter(
            Activity.athlete_id == athlete_id,
            func.date(Activity.start_time) >= start_date - timedelta(days=7),
            func.date(Activity.start_time) <= end_date,
            Activity.sport.ilike("run"),
        ).all()
        
        run_dates = set(a.activity_date for a in activities)
        
        dates = []
        values = []
        
        current = start_date
        while current <= end_date:
            runs_7d = sum(
                1 for i in range(7)
                if (current - timedelta(days=i)) in run_dates
            )
            
            dates.append(current)
            values.append(runs_7d)
            current += timedelta(days=1)
        
        return TimeSeries(name="consistency", dates=dates, values=values)
    
    def _get_acwr_series(
        self,
        athlete_id: UUID,
        start_date: date,
        end_date: date,
    ) -> TimeSeries:
        """Calculate daily ACWR (Acute:Chronic Workload Ratio)."""
        activities = self.db.query(
            func.date(Activity.start_time).label("activity_date"),
            Activity.distance_m,
        ).filter(
            Activity.athlete_id == athlete_id,
            func.date(Activity.start_time) >= start_date - timedelta(days=28),
            func.date(Activity.start_time) <= end_date,
            Activity.sport.ilike("run"),
        ).all()
        
        # Build date -> distance map
        distance_map: Dict[date, float] = {}
        for a in activities:
            d = a.activity_date
            distance_map[d] = distance_map.get(d, 0) + (a.distance_m or 0)
        
        dates = []
        values = []
        
        current = start_date
        while current <= end_date:
            # Acute: last 7 days
            acute = sum(
                distance_map.get(current - timedelta(days=i), 0)
                for i in range(7)
            ) / 1000
            
            # Chronic: last 28 days weekly average
            chronic_total = sum(
                distance_map.get(current - timedelta(days=i), 0)
                for i in range(28)
            ) / 1000
            chronic_weekly = chronic_total / 4
            
            acwr = acute / chronic_weekly if chronic_weekly > 0 else 1.0
            
            dates.append(current)
            values.append(acwr)
            current += timedelta(days=1)
        
        return TimeSeries(name="acwr", dates=dates, values=values)
    
    def _generate_insight(
        self,
        input_name: str,
        lag_days: int,
        direction: ImpactDirection,
        p_value: float,
        correlation: float,
        loop: FrequencyLoop,
        confidence: CausalConfidence,
    ) -> str:
        """Generate sparse, forensic insight text."""
        
        if confidence == CausalConfidence.INSUFFICIENT:
            return f"{input_name}: More data needed."
        
        # Lag description
        if lag_days == 0:
            lag_str = "same day"
        elif lag_days == 1:
            lag_str = "1 day prior"
        else:
            lag_str = f"{lag_days} days prior"
        
        # Direction description
        if direction == ImpactDirection.POSITIVE:
            effect = "preceded better performance"
        elif direction == ImpactDirection.NEGATIVE:
            effect = "preceded worse performance"
        else:
            effect = "had unclear effect"
        
        # Confidence qualifier
        if confidence == CausalConfidence.HIGH:
            qualifier = "Data strongly suggests"
        elif confidence == CausalConfidence.MODERATE:
            qualifier = "Data hints"
        else:
            qualifier = "Weak signal"
        
        # Build insight
        insight = f"{qualifier}: {input_name} changes {lag_str} {effect}."
        
        # Add statistical backing for high/moderate confidence
        if confidence in [CausalConfidence.HIGH, CausalConfidence.MODERATE]:
            insight += f" (Granger p={p_value:.3f})"
        
        if confidence == CausalConfidence.SUGGESTIVE:
            insight += " Test it."
        
        return insight
    
    def _calculate_data_quality(
        self,
        athlete_id: UUID,
        start_date: date,
        end_date: date,
    ) -> Tuple[float, List[str]]:
        """Calculate overall data quality score and notes."""
        notes = []
        scores = []
        
        total_days = (end_date - start_date).days
        
        # Activity coverage
        activity_count = self.db.query(func.count(Activity.id)).filter(
            Activity.athlete_id == athlete_id,
            func.date(Activity.start_time) >= start_date,
            func.date(Activity.start_time) <= end_date,
            Activity.sport.ilike("run"),
        ).scalar() or 0
        
        activity_density = activity_count / (total_days / 7)  # Runs per week
        activity_score = min(1.0, activity_density / 4)  # 4+ runs/week = full score
        scores.append(activity_score)
        
        if activity_density < 3:
            notes.append(f"Low run frequency ({activity_density:.1f}/week). More data improves accuracy.")
        
        # Check-in coverage
        checkin_count = self.db.query(func.count(DailyCheckin.id)).filter(
            DailyCheckin.athlete_id == athlete_id,
            DailyCheckin.date >= start_date,
            DailyCheckin.date <= end_date,
        ).scalar() or 0
        
        checkin_density = checkin_count / total_days
        checkin_score = min(1.0, checkin_density)
        scores.append(checkin_score)
        
        if checkin_density < 0.5:
            notes.append("Limited daily check-in data. Log more for readiness insights.")
        
        # Sleep data
        sleep_count = self.db.query(func.count(DailyCheckin.id)).filter(
            DailyCheckin.athlete_id == athlete_id,
            DailyCheckin.date >= start_date,
            DailyCheckin.date <= end_date,
            DailyCheckin.sleep_h.isnot(None),
        ).scalar() or 0
        
        sleep_score = min(1.0, sleep_count / (total_days * 0.7))
        scores.append(sleep_score)
        
        if sleep_count < 20:
            notes.append("Limited sleep data. Sleep logging improves causal detection.")
        
        # HRV data
        hrv_count = self.db.query(func.count(DailyCheckin.id)).filter(
            DailyCheckin.athlete_id == athlete_id,
            DailyCheckin.date >= start_date,
            DailyCheckin.date <= end_date,
            DailyCheckin.hrv_rmssd.isnot(None),
        ).scalar() or 0
        
        hrv_score = min(1.0, hrv_count / (total_days * 0.5))
        scores.append(hrv_score)
        
        if hrv_count < 15:
            notes.append("Limited HRV data. Consider wearable integration.")
        
        overall = sum(scores) / len(scores)
        
        if not notes:
            notes.append("Good data coverage for causal analysis.")
        
        return overall, notes
    
    def _build_context_block(
        self,
        readiness_indicators: List[LeadingIndicator],
        fitness_indicators: List[LeadingIndicator],
        top_indicators: List[LeadingIndicator],
    ) -> str:
        """Build context block for GPT injection."""
        lines = [
            "=== CAUSAL ATTRIBUTION CONTEXT ===",
            "",
            "DISCOVERED LEADING INDICATORS:",
            "(What PRECEDES performance changes for this athlete)",
            "",
        ]
        
        if top_indicators:
            for i, ind in enumerate(top_indicators, 1):
                confidence_emoji = {
                    CausalConfidence.HIGH: "🟢",
                    CausalConfidence.MODERATE: "🟡",
                    CausalConfidence.SUGGESTIVE: "🟠",
                    CausalConfidence.INSUFFICIENT: "⚪",
                }[ind.confidence]
                
                direction_str = {
                    ImpactDirection.POSITIVE: "↑ HELPS",
                    ImpactDirection.NEGATIVE: "↓ HURTS",
                    ImpactDirection.NEUTRAL: "→ NEUTRAL",
                }[ind.effect_direction]
                
                lines.append(
                    f"{i}. {confidence_emoji} {ind.input_name} ({ind.lag_days}d lag): "
                    f"{direction_str} | p={ind.granger_p:.3f}"
                )
        else:
            lines.append("No statistically significant leading indicators found yet.")
            lines.append("More data needed for causal inference.")
        
        lines.append("")
        lines.append("INTERPRETATION:")
        lines.append("- Leading indicators show what PRECEDED performance changes")
        lines.append("- Lower p-value = stronger statistical confidence")
        lines.append("- Lag = how many days before the effect appeared")
        lines.append("")
        lines.append("=== END CAUSAL CONTEXT ===")
        
        return "\n".join(lines)
    
    def _empty_result(
        self,
        athlete_id: UUID,
        analysis_date: date,
        analysis_days: int,
        reason: str,
    ) -> CausalAnalysisResult:
        """Return empty result with explanation."""
        return CausalAnalysisResult(
            athlete_id=str(athlete_id),
            analysis_date=analysis_date,
            analysis_period_days=analysis_days,
            readiness_indicators=[],
            fitness_indicators=[],
            top_indicators=[],
            data_quality_score=0.0,
            data_quality_notes=[reason],
            context_block=f"=== CAUSAL ATTRIBUTION CONTEXT ===\n\n{reason}\n\n=== END ===",
        )
