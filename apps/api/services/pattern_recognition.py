"""
Pattern Recognition Engine

PHILOSOPHY:
We do NOT impose external research findings as truth.
We discover patterns from THIS ATHLETE's data.

If the athlete's PRs correlate with low sleep and low HRV,
that's the pattern we surface - even if it contradicts
population-level research.

The athlete IS the sample. N=1, but it's the only N that matters.

External research informs our QUESTIONS, not our ANSWERS:
- Research says sleep matters → so we LOOK at sleep
- But we don't assume direction → we let the data speak
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
from enum import Enum
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
import statistics

from models import Activity, DailyCheckin, BodyComposition


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class PatternDirection(str, Enum):
    """Direction of a pattern relative to the athlete's norm."""
    HIGHER = "higher"
    LOWER = "lower"
    SIMILAR = "similar"
    UNKNOWN = "unknown"


class PatternType(str, Enum):
    """Type of pattern identified."""
    PREREQUISITE = "prerequisite"  # True for ≥80% of comparison runs
    COMMON_FACTOR = "common_factor"  # True for 60-79% of comparison runs
    DEVIATION = "deviation"  # Current run differs from pattern
    CORRELATION = "correlation"  # Input correlates with performance


class ConfidenceLevel(str, Enum):
    """Confidence in the pattern based on data quality."""
    HIGH = "high"  # Dense data, strong signal
    MODERATE = "moderate"  # Some gaps, clear trend
    LOW = "low"  # Sparse data, weak signal
    INSUFFICIENT = "insufficient"  # Not enough data


@dataclass
class TrailingContext:
    """
    The trailing context for a single run.
    Captures what happened in the 28 days before this run.
    """
    activity_id: str
    activity_date: datetime
    activity_name: str
    
    # Performance (the output we're trying to explain)
    pace_per_km: Optional[float]
    avg_hr: Optional[int]
    efficiency: Optional[float]  # pace / HR
    
    # Volume Metrics (trailing 28 days)
    trailing_volume_km: float
    trailing_run_count: int
    trailing_avg_weekly_km: float
    
    # Intensity Distribution (trailing 28 days)
    easy_run_pct: float
    tempo_run_pct: float
    long_run_pct: float
    interval_pct: float
    
    # ACWR (Acute:Chronic Workload Ratio)
    acwr: float
    acwr_interpretation: str  # "fresh", "steady", "heavy", "overreaching"
    
    # Sleep (if available)
    avg_sleep_hours: Optional[float]
    sleep_data_points: int
    
    # HRV (if available)
    avg_hrv: Optional[float]
    hrv_data_points: int
    
    # Readiness/Mood (if available)
    avg_readiness: Optional[float]
    readiness_data_points: int
    
    # Body Composition (if available)
    weight_at_time: Optional[float]
    weight_trend: Optional[str]  # "stable", "increasing", "decreasing"
    
    def data_quality_score(self) -> float:
        """0-1 score of how much data we have for this context."""
        scores = []
        # Volume data is always available if we have activities
        scores.append(1.0 if self.trailing_run_count >= 4 else self.trailing_run_count / 4)
        # Check-in data
        scores.append(min(1.0, self.sleep_data_points / 7))  # Ideal: 7+ days
        scores.append(min(1.0, self.hrv_data_points / 7))
        scores.append(min(1.0, self.readiness_data_points / 7))
        return sum(scores) / len(scores)


@dataclass
class PatternInsight:
    """A single pattern discovered from the data."""
    input_name: str  # e.g., "trailing_volume_km", "avg_sleep_hours"
    display_name: str  # e.g., "Weekly Volume", "Sleep"
    icon: str
    
    pattern_type: PatternType
    direction: PatternDirection
    
    # The pattern itself
    pattern_value: str  # e.g., "> 40km/week", "< 6 hours"
    current_value: str  # e.g., "22km/week", "5.2 hours"
    
    # How consistent is this pattern?
    consistency: float  # 0-1, what % of comparison runs showed this
    consistency_str: str  # e.g., "4/5 runs", "All runs"
    
    # Correlation with performance
    correlation_direction: str  # "positive", "negative", "none"
    
    # Confidence
    confidence: ConfidenceLevel
    
    # Natural language insight
    insight: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_name": self.input_name,
            "display_name": self.display_name,
            "icon": self.icon,
            "pattern_type": self.pattern_type.value,
            "direction": self.direction.value,
            "pattern_value": self.pattern_value,
            "current_value": self.current_value,
            "consistency": round(self.consistency, 2),
            "consistency_str": self.consistency_str,
            "correlation_direction": self.correlation_direction,
            "confidence": self.confidence.value,
            "insight": self.insight,
        }


@dataclass
class FatigueContext:
    """Understanding of where the athlete is in their training cycle."""
    acwr: float
    phase: str  # "taper", "recovery", "steady", "build", "overreaching"
    
    acute_load_km: float  # Last 7 days
    chronic_load_km: float  # Last 28 days avg per week
    
    explanation: str
    
    # Comparison to baseline runs
    current_is_fresher: bool
    current_is_more_fatigued: bool
    fatigue_delta: str  # e.g., "You're in a heavier block than 4/5 comparison runs"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "acwr": round(self.acwr, 2),
            "phase": self.phase,
            "acute_load_km": round(self.acute_load_km, 1),
            "chronic_load_km": round(self.chronic_load_km, 1),
            "explanation": self.explanation,
            "current_is_fresher": self.current_is_fresher,
            "current_is_more_fatigued": self.current_is_more_fatigued,
            "fatigue_delta": self.fatigue_delta,
        }


@dataclass 
class PatternAnalysisResult:
    """Complete result of pattern analysis."""
    # The runs analyzed
    current_run: TrailingContext
    comparison_runs: List[TrailingContext]
    
    # Discovered patterns
    prerequisites: List[PatternInsight]  # ≥80% consistency
    common_factors: List[PatternInsight]  # 60-79% consistency
    deviations: List[PatternInsight]  # Current differs from pattern
    
    # Fatigue context
    fatigue: FatigueContext
    
    # Data quality
    overall_data_quality: float  # 0-1
    data_quality_notes: List[str]
    
    # Summary for GPT injection
    context_block: str  # Structured text for prompt injection
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_run": {
                "id": self.current_run.activity_id,
                "name": self.current_run.activity_name,
                "date": self.current_run.activity_date.isoformat(),
            },
            "comparison_run_count": len(self.comparison_runs),
            "prerequisites": [p.to_dict() for p in self.prerequisites],
            "common_factors": [p.to_dict() for p in self.common_factors],
            "deviations": [p.to_dict() for p in self.deviations],
            "fatigue": self.fatigue.to_dict(),
            "overall_data_quality": round(self.overall_data_quality, 2),
            "data_quality_notes": self.data_quality_notes,
            "context_block": self.context_block,
        }


# =============================================================================
# PATTERN RECOGNITION ENGINE
# =============================================================================

class PatternRecognitionEngine:
    """
    Analyzes patterns across multiple runs to identify what drives performance.
    
    Key principle: We learn from the athlete's data, not external research.
    If their PRs come after poor sleep, that's the pattern we surface.
    """
    
    # Trailing window sizes
    TRAILING_DAYS = 28
    ACUTE_DAYS = 7
    
    # Pattern thresholds
    PREREQUISITE_THRESHOLD = 0.8  # ≥80% of runs
    COMMON_FACTOR_THRESHOLD = 0.6  # 60-79% of runs
    
    # ACWR interpretation thresholds
    ACWR_TAPER = 0.8
    ACWR_STEADY_LOW = 0.9
    ACWR_STEADY_HIGH = 1.1
    ACWR_BUILD = 1.3
    # > 1.3 = overreaching
    
    def __init__(self, db: Session):
        self.db = db
    
    def analyze(
        self,
        current_activity_id: UUID,
        comparison_activity_ids: List[UUID],
        athlete_id: UUID,
    ) -> PatternAnalysisResult:
        """
        Main entry point: Analyze patterns between current run and comparison runs.
        
        Args:
            current_activity_id: The run we're trying to understand
            comparison_activity_ids: Runs to compare against (user-selected or auto-similar)
            athlete_id: The athlete
            
        Returns:
            PatternAnalysisResult with discovered patterns
        """
        # 1. Build trailing context for EACH run
        current_context = self._build_trailing_context(current_activity_id, athlete_id)
        comparison_contexts = [
            self._build_trailing_context(aid, athlete_id) 
            for aid in comparison_activity_ids
        ]
        
        # Filter out any that couldn't be built
        comparison_contexts = [c for c in comparison_contexts if c is not None]
        
        if not current_context or len(comparison_contexts) < 2:
            return self._empty_result(current_context)
        
        # 2. Identify patterns
        all_patterns = self._identify_patterns(current_context, comparison_contexts)
        
        # 3. Classify patterns by consistency
        prerequisites = [p for p in all_patterns if p.pattern_type == PatternType.PREREQUISITE]
        common_factors = [p for p in all_patterns if p.pattern_type == PatternType.COMMON_FACTOR]
        deviations = [p for p in all_patterns if p.pattern_type == PatternType.DEVIATION]
        
        # 4. Build fatigue context
        fatigue = self._build_fatigue_context(current_context, comparison_contexts)
        
        # 5. Calculate data quality
        all_contexts = [current_context] + comparison_contexts
        data_quality = sum(c.data_quality_score() for c in all_contexts) / len(all_contexts)
        data_quality_notes = self._get_data_quality_notes(all_contexts)
        
        # 6. Build context block for GPT
        context_block = self._build_context_block(
            current_context, comparison_contexts,
            prerequisites, common_factors, deviations, fatigue
        )
        
        return PatternAnalysisResult(
            current_run=current_context,
            comparison_runs=comparison_contexts,
            prerequisites=prerequisites,
            common_factors=common_factors,
            deviations=deviations,
            fatigue=fatigue,
            overall_data_quality=data_quality,
            data_quality_notes=data_quality_notes,
            context_block=context_block,
        )
    
    def _build_trailing_context(
        self, 
        activity_id: UUID, 
        athlete_id: UUID
    ) -> Optional[TrailingContext]:
        """Build the complete trailing context for a single run."""
        # Get the activity
        activity = self.db.query(Activity).filter(
            Activity.id == activity_id,
            Activity.athlete_id == athlete_id,
        ).first()
        
        if not activity:
            return None
        
        activity_date = activity.start_time
        trailing_start = activity_date - timedelta(days=self.TRAILING_DAYS)
        acute_start = activity_date - timedelta(days=self.ACUTE_DAYS)
        
        # Get trailing activities (excluding this one)
        trailing_activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= trailing_start,
            Activity.start_time < activity_date,
            Activity.sport.ilike("run"),
        ).all()
        
        # Calculate volume metrics
        trailing_volume_m = sum(a.distance_m or 0 for a in trailing_activities)
        trailing_volume_km = trailing_volume_m / 1000
        trailing_run_count = len(trailing_activities)
        trailing_avg_weekly_km = trailing_volume_km / 4  # 28 days = 4 weeks
        
        # Calculate ACWR
        acute_activities = [a for a in trailing_activities if a.start_time >= acute_start]
        acute_volume_km = sum(a.distance_m or 0 for a in acute_activities) / 1000
        chronic_weekly_km = trailing_avg_weekly_km if trailing_avg_weekly_km > 0 else 1
        acwr = acute_volume_km / chronic_weekly_km if chronic_weekly_km > 0 else 1.0
        acwr_interpretation = self._interpret_acwr(acwr)
        
        # Calculate intensity distribution
        intensity_dist = self._calculate_intensity_distribution(trailing_activities)
        
        # Get check-in data
        checkins = self.db.query(DailyCheckin).filter(
            DailyCheckin.athlete_id == athlete_id,
            DailyCheckin.date >= trailing_start.date(),
            DailyCheckin.date < activity_date.date(),
        ).all()
        
        sleep_values = [c.sleep_hours for c in checkins if c.sleep_hours]
        hrv_values = [c.hrv for c in checkins if c.hrv]
        readiness_values = [c.readiness_score for c in checkins if c.readiness_score]
        
        # Get body composition
        body_comp = self.db.query(BodyComposition).filter(
            BodyComposition.athlete_id == athlete_id,
            BodyComposition.date <= activity_date.date(),
        ).order_by(BodyComposition.date.desc()).first()
        
        weight_trend = self._calculate_weight_trend(athlete_id, activity_date)
        
        # Calculate efficiency (pace / HR - lower is better efficiency)
        pace = activity.duration_s / (activity.distance_m / 1000) if activity.distance_m else None
        efficiency = pace / activity.avg_hr if pace and activity.avg_hr else None
        
        return TrailingContext(
            activity_id=str(activity_id),
            activity_date=activity_date,
            activity_name=activity.name or f"Run on {activity_date.strftime('%b %d')}",
            pace_per_km=pace,
            avg_hr=activity.avg_hr,
            efficiency=efficiency,
            trailing_volume_km=trailing_volume_km,
            trailing_run_count=trailing_run_count,
            trailing_avg_weekly_km=trailing_avg_weekly_km,
            easy_run_pct=intensity_dist.get("easy", 0),
            tempo_run_pct=intensity_dist.get("tempo", 0),
            long_run_pct=intensity_dist.get("long", 0),
            interval_pct=intensity_dist.get("interval", 0),
            acwr=acwr,
            acwr_interpretation=acwr_interpretation,
            avg_sleep_hours=statistics.mean(sleep_values) if sleep_values else None,
            sleep_data_points=len(sleep_values),
            avg_hrv=statistics.mean(hrv_values) if hrv_values else None,
            hrv_data_points=len(hrv_values),
            avg_readiness=statistics.mean(readiness_values) if readiness_values else None,
            readiness_data_points=len(readiness_values),
            weight_at_time=body_comp.weight_kg if body_comp else None,
            weight_trend=weight_trend,
        )
    
    def _interpret_acwr(self, acwr: float) -> str:
        """Interpret ACWR value into training phase."""
        if acwr < self.ACWR_TAPER:
            return "taper"
        elif acwr < self.ACWR_STEADY_LOW:
            return "recovery"
        elif acwr <= self.ACWR_STEADY_HIGH:
            return "steady"
        elif acwr <= self.ACWR_BUILD:
            return "build"
        else:
            return "overreaching"
    
    def _calculate_intensity_distribution(
        self, 
        activities: List[Activity]
    ) -> Dict[str, float]:
        """Calculate % of runs by workout type."""
        if not activities:
            return {"easy": 0, "tempo": 0, "long": 0, "interval": 0}
        
        type_map = {
            "easy_run": "easy",
            "recovery_run": "easy",
            "aerobic_run": "easy",
            "tempo_run": "tempo",
            "threshold_run": "tempo",
            "tempo_intervals": "tempo",
            "long_run": "long",
            "medium_long_run": "long",
            "vo2max_intervals": "interval",
            "track_workout": "interval",
            "fartlek": "interval",
        }
        
        counts = {"easy": 0, "tempo": 0, "long": 0, "interval": 0, "other": 0}
        for a in activities:
            category = type_map.get(a.workout_type, "other")
            counts[category] = counts.get(category, 0) + 1
        
        total = len(activities)
        return {
            "easy": counts["easy"] / total,
            "tempo": counts["tempo"] / total,
            "long": counts["long"] / total,
            "interval": counts["interval"] / total,
        }
    
    def _calculate_weight_trend(
        self, 
        athlete_id: UUID, 
        before_date: datetime
    ) -> Optional[str]:
        """Calculate weight trend over last 4 weeks."""
        four_weeks_ago = before_date - timedelta(days=28)
        
        weights = self.db.query(BodyComposition).filter(
            BodyComposition.athlete_id == athlete_id,
            BodyComposition.date >= four_weeks_ago.date(),
            BodyComposition.date <= before_date.date(),
        ).order_by(BodyComposition.date).all()
        
        if len(weights) < 2:
            return None
        
        first_weight = weights[0].weight_kg
        last_weight = weights[-1].weight_kg
        
        pct_change = (last_weight - first_weight) / first_weight * 100
        
        if pct_change > 1:
            return "increasing"
        elif pct_change < -1:
            return "decreasing"
        else:
            return "stable"
    
    def _identify_patterns(
        self,
        current: TrailingContext,
        comparisons: List[TrailingContext],
    ) -> List[PatternInsight]:
        """
        Identify patterns by comparing current run's context to comparison runs.
        
        Key insight: We don't assume direction. We observe what correlates
        with better/worse performance in THIS athlete's data.
        """
        patterns = []
        
        # Define inputs to analyze
        inputs = [
            ("trailing_volume_km", "Weekly Volume", "📊", lambda c: c.trailing_avg_weekly_km),
            ("trailing_run_count", "Run Frequency", "🏃", lambda c: c.trailing_run_count),
            ("acwr", "Training Load", "⚡", lambda c: c.acwr),
            ("easy_run_pct", "Easy Running %", "🐢", lambda c: c.easy_run_pct * 100),
            ("tempo_run_pct", "Tempo Work %", "🔥", lambda c: c.tempo_run_pct * 100),
            ("interval_pct", "Interval Work %", "⚡", lambda c: c.interval_pct * 100),
        ]
        
        # Add optional inputs if we have data
        if current.sleep_data_points >= 3:
            inputs.append(("avg_sleep_hours", "Sleep", "😴", lambda c: c.avg_sleep_hours))
        if current.hrv_data_points >= 3:
            inputs.append(("avg_hrv", "HRV", "💓", lambda c: c.avg_hrv))
        if current.readiness_data_points >= 3:
            inputs.append(("avg_readiness", "Readiness", "✨", lambda c: c.avg_readiness))
        
        for input_name, display_name, icon, getter in inputs:
            pattern = self._analyze_single_input(
                input_name, display_name, icon, getter,
                current, comparisons
            )
            if pattern:
                patterns.append(pattern)
        
        return patterns
    
    def _analyze_single_input(
        self,
        input_name: str,
        display_name: str,
        icon: str,
        getter,
        current: TrailingContext,
        comparisons: List[TrailingContext],
    ) -> Optional[PatternInsight]:
        """Analyze a single input for patterns."""
        current_value = getter(current)
        comparison_values = [getter(c) for c in comparisons if getter(c) is not None]
        
        if current_value is None or len(comparison_values) < 2:
            return None
        
        # Calculate statistics from comparison runs
        comp_mean = statistics.mean(comparison_values)
        comp_stdev = statistics.stdev(comparison_values) if len(comparison_values) > 1 else comp_mean * 0.1
        
        # Avoid division by zero
        if comp_stdev == 0:
            comp_stdev = comp_mean * 0.1 if comp_mean > 0 else 1
        
        # Calculate how current compares
        z_score = (current_value - comp_mean) / comp_stdev
        
        # Determine direction
        if z_score > 0.5:
            direction = PatternDirection.HIGHER
        elif z_score < -0.5:
            direction = PatternDirection.LOWER
        else:
            direction = PatternDirection.SIMILAR
        
        # Check consistency in comparison runs
        # What % had values in a similar range?
        threshold_high = comp_mean + comp_stdev * 0.5
        threshold_low = comp_mean - comp_stdev * 0.5
        
        high_count = sum(1 for v in comparison_values if v >= threshold_high)
        low_count = sum(1 for v in comparison_values if v <= threshold_low)
        middle_count = len(comparison_values) - high_count - low_count
        
        # Find the dominant pattern
        total = len(comparison_values)
        high_pct = high_count / total
        low_pct = low_count / total
        
        # Determine pattern type
        pattern_type = None
        pattern_value = None
        consistency = 0
        correlation_direction = "none"
        
        if high_pct >= self.PREREQUISITE_THRESHOLD:
            pattern_type = PatternType.PREREQUISITE
            pattern_value = f"> {self._format_value(input_name, threshold_high)}"
            consistency = high_pct
            correlation_direction = "positive" if direction == PatternDirection.HIGHER else "none"
            
        elif low_pct >= self.PREREQUISITE_THRESHOLD:
            pattern_type = PatternType.PREREQUISITE
            pattern_value = f"< {self._format_value(input_name, threshold_low)}"
            consistency = low_pct
            correlation_direction = "positive" if direction == PatternDirection.LOWER else "none"
            
        elif high_pct >= self.COMMON_FACTOR_THRESHOLD:
            pattern_type = PatternType.COMMON_FACTOR
            pattern_value = f"> {self._format_value(input_name, threshold_high)}"
            consistency = high_pct
            
        elif low_pct >= self.COMMON_FACTOR_THRESHOLD:
            pattern_type = PatternType.COMMON_FACTOR
            pattern_value = f"< {self._format_value(input_name, threshold_low)}"
            consistency = low_pct
        
        # Check if current run deviates from pattern
        if pattern_type:
            current_in_pattern = False
            if ">" in pattern_value and current_value >= threshold_high:
                current_in_pattern = True
            elif "<" in pattern_value and current_value <= threshold_low:
                current_in_pattern = True
            
            if not current_in_pattern:
                # Current run deviates from the pattern
                deviation = PatternInsight(
                    input_name=input_name,
                    display_name=display_name,
                    icon=icon,
                    pattern_type=PatternType.DEVIATION,
                    direction=direction,
                    pattern_value=pattern_value,
                    current_value=self._format_value(input_name, current_value),
                    consistency=consistency,
                    consistency_str=f"{int(consistency * total)}/{total} runs",
                    correlation_direction=correlation_direction,
                    confidence=self._calculate_confidence(len(comparison_values), consistency),
                    insight=self._generate_deviation_insight(
                        display_name, pattern_value, current_value, input_name,
                        direction, consistency, total
                    ),
                )
                return deviation
        
        # Return the pattern if significant
        if pattern_type and consistency >= self.COMMON_FACTOR_THRESHOLD:
            return PatternInsight(
                input_name=input_name,
                display_name=display_name,
                icon=icon,
                pattern_type=pattern_type,
                direction=direction,
                pattern_value=pattern_value,
                current_value=self._format_value(input_name, current_value),
                consistency=consistency,
                consistency_str=f"{int(consistency * total)}/{total} runs",
                correlation_direction=correlation_direction,
                confidence=self._calculate_confidence(len(comparison_values), consistency),
                insight=self._generate_pattern_insight(
                    display_name, pattern_value, current_value, input_name,
                    pattern_type, consistency, total
                ),
            )
        
        return None
    
    def _format_value(self, input_name: str, value: float) -> str:
        """Format a value for display."""
        if "volume" in input_name or "km" in input_name.lower():
            return f"{value:.1f}km"
        elif "pct" in input_name:
            return f"{value:.0f}%"
        elif "sleep" in input_name:
            return f"{value:.1f}hrs"
        elif "acwr" in input_name:
            return f"{value:.2f}"
        elif "count" in input_name:
            return f"{int(value)} runs"
        else:
            return f"{value:.1f}"
    
    def _calculate_confidence(self, n_samples: int, consistency: float) -> ConfidenceLevel:
        """Calculate confidence based on sample size and consistency."""
        if n_samples < 3:
            return ConfidenceLevel.INSUFFICIENT
        elif n_samples >= 5 and consistency >= 0.8:
            return ConfidenceLevel.HIGH
        elif n_samples >= 3 and consistency >= 0.6:
            return ConfidenceLevel.MODERATE
        else:
            return ConfidenceLevel.LOW
    
    def _generate_pattern_insight(
        self,
        display_name: str,
        pattern_value: str,
        current_value: float,
        input_name: str,
        pattern_type: PatternType,
        consistency: float,
        total: int,
    ) -> str:
        """Generate natural language insight for a pattern."""
        n_runs = int(consistency * total)
        
        if pattern_type == PatternType.PREREQUISITE:
            return f"In {n_runs}/{total} of these runs, {display_name} was {pattern_value}. Today: {self._format_value(input_name, current_value)}."
        else:
            return f"{display_name} was {pattern_value} in {n_runs}/{total} comparison runs."
    
    def _generate_deviation_insight(
        self,
        display_name: str,
        pattern_value: str,
        current_value: float,
        input_name: str,
        direction: PatternDirection,
        consistency: float,
        total: int,
    ) -> str:
        """Generate insight for when current run deviates from pattern."""
        n_runs = int(consistency * total)
        current_str = self._format_value(input_name, current_value)
        
        return f"Pattern: {display_name} was {pattern_value} in {n_runs}/{total} runs. Today: {current_str}. This is a notable deviation."
    
    def _build_fatigue_context(
        self,
        current: TrailingContext,
        comparisons: List[TrailingContext],
    ) -> FatigueContext:
        """Build fatigue context comparing current ACWR to comparison runs."""
        comparison_acwrs = [c.acwr for c in comparisons]
        avg_comparison_acwr = statistics.mean(comparison_acwrs) if comparison_acwrs else 1.0
        
        # Interpret current phase
        phase = current.acwr_interpretation
        
        # Compare to comparison runs
        fresher_count = sum(1 for c in comparisons if c.acwr > current.acwr)
        more_fatigued_count = sum(1 for c in comparisons if c.acwr < current.acwr)
        
        current_is_fresher = fresher_count > len(comparisons) / 2
        current_is_more_fatigued = more_fatigued_count > len(comparisons) / 2
        
        if current_is_fresher:
            fatigue_delta = f"You're fresher than {fresher_count}/{len(comparisons)} comparison runs."
        elif current_is_more_fatigued:
            fatigue_delta = f"You're carrying more load than {more_fatigued_count}/{len(comparisons)} comparison runs."
        else:
            fatigue_delta = "Training load is similar to comparison runs."
        
        # Generate explanation
        if phase == "taper":
            explanation = "You're in a taper/recovery phase. Legs should be fresh."
        elif phase == "recovery":
            explanation = "Light training load. Building back or recovering."
        elif phase == "steady":
            explanation = "Consistent training load. Sustainable rhythm."
        elif phase == "build":
            explanation = "Heavy training block. Some fatigue expected."
        else:
            explanation = "Very high acute load. Risk of overreaching."
        
        return FatigueContext(
            acwr=current.acwr,
            phase=phase,
            acute_load_km=current.trailing_volume_km * (7/28),  # Approximate
            chronic_load_km=current.trailing_avg_weekly_km,
            explanation=explanation,
            current_is_fresher=current_is_fresher,
            current_is_more_fatigued=current_is_more_fatigued,
            fatigue_delta=fatigue_delta,
        )
    
    def _get_data_quality_notes(self, contexts: List[TrailingContext]) -> List[str]:
        """Generate notes about data quality/availability."""
        notes = []
        
        # Check sleep data
        sleep_coverage = sum(1 for c in contexts if c.sleep_data_points >= 3) / len(contexts)
        if sleep_coverage < 0.5:
            notes.append("Limited sleep data. Log more check-ins for better insights.")
        
        # Check HRV data
        hrv_coverage = sum(1 for c in contexts if c.hrv_data_points >= 3) / len(contexts)
        if hrv_coverage < 0.5:
            notes.append("Limited HRV data available.")
        
        # Check volume data
        low_volume_runs = sum(1 for c in contexts if c.trailing_run_count < 4)
        if low_volume_runs > len(contexts) / 2:
            notes.append("Some runs have limited trailing activity data.")
        
        if not notes:
            notes.append("Good data coverage across all analyzed runs.")
        
        return notes
    
    def _build_context_block(
        self,
        current: TrailingContext,
        comparisons: List[TrailingContext],
        prerequisites: List[PatternInsight],
        common_factors: List[PatternInsight],
        deviations: List[PatternInsight],
        fatigue: FatigueContext,
    ) -> str:
        """
        Build a structured context block for GPT prompt injection.
        This is the 'athlete dossier' that makes AI responses smarter.
        """
        lines = [
            "=== ATHLETE CONTEXT (Pattern Analysis) ===",
            "",
            f"CURRENT RUN: {current.activity_name}",
            f"Date: {current.activity_date.strftime('%b %d, %Y')}",
            f"Pace: {self._format_value('pace', current.pace_per_km) if current.pace_per_km else 'N/A'}",
            f"Compared against: {len(comparisons)} similar runs",
            "",
            "TRAINING LOAD:",
            f"- ACWR: {fatigue.acwr:.2f} ({fatigue.phase})",
            f"- Acute (7d): {fatigue.acute_load_km:.1f}km",
            f"- Chronic (weekly avg): {fatigue.chronic_load_km:.1f}km",
            f"- {fatigue.fatigue_delta}",
            "",
        ]
        
        if prerequisites:
            lines.append("PREREQUISITES (True for ≥80% of comparison runs):")
            for p in prerequisites:
                lines.append(f"- {p.display_name}: {p.pattern_value} ({p.consistency_str})")
            lines.append("")
        
        if deviations:
            lines.append("DEVIATIONS (Current run differs from pattern):")
            for d in deviations:
                lines.append(f"- {d.display_name}: Pattern was {d.pattern_value}, today is {d.current_value}")
            lines.append("")
        
        if common_factors:
            lines.append("COMMON FACTORS (True for 60-80% of comparison runs):")
            for c in common_factors:
                lines.append(f"- {c.display_name}: {c.pattern_value} ({c.consistency_str})")
            lines.append("")
        
        lines.append("=== END CONTEXT ===")
        
        return "\n".join(lines)
    
    def _empty_result(self, current: Optional[TrailingContext]) -> PatternAnalysisResult:
        """Return empty result when we can't analyze."""
        if not current:
            # Create minimal context
            current = TrailingContext(
                activity_id="",
                activity_date=datetime.now(timezone.utc),
                activity_name="Unknown",
                pace_per_km=None,
                avg_hr=None,
                efficiency=None,
                trailing_volume_km=0,
                trailing_run_count=0,
                trailing_avg_weekly_km=0,
                easy_run_pct=0,
                tempo_run_pct=0,
                long_run_pct=0,
                interval_pct=0,
                acwr=1.0,
                acwr_interpretation="unknown",
                avg_sleep_hours=None,
                sleep_data_points=0,
                avg_hrv=None,
                hrv_data_points=0,
                avg_readiness=None,
                readiness_data_points=0,
                weight_at_time=None,
                weight_trend=None,
            )
        
        return PatternAnalysisResult(
            current_run=current,
            comparison_runs=[],
            prerequisites=[],
            common_factors=[],
            deviations=[],
            fatigue=FatigueContext(
                acwr=1.0,
                phase="unknown",
                acute_load_km=0,
                chronic_load_km=0,
                explanation="Insufficient data for fatigue analysis.",
                current_is_fresher=False,
                current_is_more_fatigued=False,
                fatigue_delta="",
            ),
            overall_data_quality=0,
            data_quality_notes=["Insufficient data for pattern analysis. Need at least 2 comparison runs."],
            context_block="",
        )
