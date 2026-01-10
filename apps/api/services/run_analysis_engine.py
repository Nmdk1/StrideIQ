"""
Run Analysis Engine

The core intelligence layer that contextualizes every run against:
- All inputs (sleep, nutrition, stress, HRV, load, life factors)
- Historical context (week, cycle, month, build, year, career)
- Similar/same workouts (how did this type of run go before?)
- Other run types (cross-reference performance patterns)
- Trend detection (signal vs noise)
- Root cause analysis (when trends appear, why?)

Design Principles:
- Look at EVERYTHING against each new run
- Don't react to one bad workout - identify trends
- Only flag outliers or major red flags for immediate attention
- Root cause analysis when patterns emerge
- Suit analysis to athlete, not athlete to analysis
"""

from datetime import datetime, timedelta, date, timezone
from typing import List, Dict, Optional, Tuple, Any
from uuid import UUID
from enum import Enum
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
import statistics
import logging

from models import Activity, Athlete, DailyCheckin, NutritionEntry

logger = logging.getLogger(__name__)


class WorkoutType(Enum):
    """Workout classification based on effort distribution"""
    EASY = "easy"
    MODERATE = "moderate"  # Between easy and tempo
    TEMPO = "tempo"
    INTERVAL = "interval"
    LONG_RUN = "long_run"
    LONG_RUN_WITH_QUALITY = "long_run_quality"  # Long run with race pace segments
    RACE = "race"
    RECOVERY = "recovery"
    UNKNOWN = "unknown"


class TimeScale(Enum):
    """Time scales for historical context"""
    THIS_WEEK = "this_week"
    THIS_CYCLE = "this_cycle"  # ~4 week training block
    THIS_MONTH = "this_month"
    THIS_BUILD = "this_build"  # ~12-16 week macro cycle
    THIS_YEAR = "this_year"
    CAREER = "career"


class TrendDirection(Enum):
    """Trend direction for metrics"""
    IMPROVING = "improving"
    DECLINING = "declining"
    STABLE = "stable"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass
class InputSnapshot:
    """All inputs leading up to a run"""
    # Sleep
    sleep_last_night: Optional[float] = None
    sleep_3_day_avg: Optional[float] = None
    sleep_7_day_avg: Optional[float] = None
    
    # Subjective
    stress_today: Optional[int] = None
    stress_3_day_avg: Optional[float] = None
    soreness_today: Optional[int] = None
    soreness_3_day_avg: Optional[float] = None
    
    # Physiological
    hrv_today: Optional[float] = None
    hrv_7_day_avg: Optional[float] = None
    resting_hr_today: Optional[int] = None
    resting_hr_7_day_avg: Optional[float] = None
    
    # Training load
    atl: Optional[float] = None  # Acute Training Load (7-day)
    ctl: Optional[float] = None  # Chronic Training Load (42-day)
    tsb: Optional[float] = None  # Training Stress Balance (CTL - ATL)
    
    # Life factors
    days_since_last_run: Optional[int] = None
    runs_this_week: Optional[int] = None
    volume_this_week_km: Optional[float] = None


@dataclass
class WorkoutContext:
    """Historical context for a workout"""
    # Classification
    workout_type: WorkoutType
    confidence: float  # 0-1 confidence in classification
    
    # This specific workout
    efficiency_score: Optional[float] = None  # Pace / HR ratio normalized
    performance_vs_expected: Optional[float] = None  # % above/below expected
    
    # Historical comparisons
    similar_workouts_count: int = 0
    percentile_vs_similar: Optional[float] = None  # Where this ranks vs similar efforts
    trend_vs_similar: Optional[TrendDirection] = None
    
    # Time scale context
    context_this_week: Optional[Dict] = None
    context_this_month: Optional[Dict] = None
    context_this_year: Optional[Dict] = None


@dataclass
class TrendAnalysis:
    """Analysis of trends over time"""
    metric: str
    direction: TrendDirection
    magnitude: Optional[float] = None  # % change
    confidence: float = 0.0  # Statistical confidence
    data_points: int = 0
    period_days: int = 0
    is_significant: bool = False  # Statistically significant trend


@dataclass
class RootCauseHypothesis:
    """Hypothesis for why a trend is occurring"""
    factor: str  # e.g., "sleep", "training_load", "stress"
    correlation_strength: float  # -1 to 1
    direction: str  # "positive" or "negative"
    confidence: float
    explanation: str


@dataclass
class RunAnalysis:
    """Complete analysis of a single run"""
    activity_id: UUID
    athlete_id: UUID
    analysis_timestamp: datetime
    
    # Input state
    inputs: InputSnapshot
    
    # Workout context
    context: WorkoutContext
    
    # Trends
    efficiency_trend: TrendAnalysis
    performance_trend: TrendAnalysis
    
    # Flags
    is_outlier: bool = False
    outlier_reason: Optional[str] = None
    is_red_flag: bool = False
    red_flag_reason: Optional[str] = None
    
    # Root cause (if declining trend)
    root_cause_hypotheses: List[RootCauseHypothesis] = None
    
    # Insights
    insights: List[str] = None


class RunAnalysisEngine:
    """
    Main engine for analyzing runs in context.
    
    Philosophy:
    - Look at EVERYTHING
    - Historical context at multiple time scales
    - Compare to similar workouts
    - Detect trends, not noise
    - Root cause analysis when trends emerge
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    # =========================================================================
    # WORKOUT CLASSIFICATION
    # =========================================================================
    
    def classify_workout(self, activity: Activity) -> Tuple[WorkoutType, float]:
        """
        Classify a workout based on pace, HR, duration, and effort distribution.
        Returns (WorkoutType, confidence).
        """
        if not activity.distance_m or not activity.duration_s:
            return WorkoutType.UNKNOWN, 0.0
        
        # Get athlete's baseline paces if available
        athlete = self.db.query(Athlete).filter(Athlete.id == activity.athlete_id).first()
        
        pace_per_km = activity.duration_s / (activity.distance_m / 1000) if activity.distance_m > 0 else None
        duration_minutes = activity.duration_s / 60
        distance_km = activity.distance_m / 1000
        avg_hr = activity.avg_hr
        max_hr = activity.max_hr
        
        # Race detection
        if activity.workout_type and 'race' in activity.workout_type.lower():
            return WorkoutType.RACE, 0.95
        
        # Long run detection (distance-based primarily)
        if distance_km >= 25:
            # Check if there were quality segments (would need splits analysis)
            return WorkoutType.LONG_RUN, 0.85
        elif distance_km >= 18:
            return WorkoutType.LONG_RUN, 0.75
        
        # HR-based classification if available
        if avg_hr and max_hr and athlete and athlete.max_hr:
            hr_percent = (avg_hr / athlete.max_hr) * 100
            
            if hr_percent < 70:
                return WorkoutType.EASY, 0.8
            elif hr_percent < 80:
                return WorkoutType.MODERATE, 0.7
            elif hr_percent < 88:
                return WorkoutType.TEMPO, 0.75
            else:
                return WorkoutType.INTERVAL, 0.7
        
        # Duration-based fallback
        if duration_minutes < 30:
            return WorkoutType.EASY, 0.5  # Short, probably recovery or easy
        elif duration_minutes < 60:
            return WorkoutType.MODERATE, 0.4  # Medium duration, unclear
        else:
            return WorkoutType.LONG_RUN, 0.5  # Long duration
        
        return WorkoutType.UNKNOWN, 0.0
    
    # =========================================================================
    # INPUT SNAPSHOT
    # =========================================================================
    
    def get_input_snapshot(self, athlete_id: UUID, run_date: date) -> InputSnapshot:
        """
        Gather all inputs leading up to a run.
        """
        snapshot = InputSnapshot()
        
        # Get check-ins for the past 7 days
        week_ago = run_date - timedelta(days=7)
        three_days_ago = run_date - timedelta(days=3)
        
        checkins = self.db.query(DailyCheckin).filter(
            DailyCheckin.athlete_id == athlete_id,
            DailyCheckin.date >= week_ago,
            DailyCheckin.date <= run_date
        ).order_by(DailyCheckin.date.desc()).all()
        
        if checkins:
            # Last night / today
            today_checkin = next((c for c in checkins if c.date == run_date), None)
            yesterday_checkin = next((c for c in checkins if c.date == run_date - timedelta(days=1)), None)
            
            if yesterday_checkin:
                snapshot.sleep_last_night = yesterday_checkin.sleep_h
            if today_checkin:
                snapshot.stress_today = today_checkin.stress_1_5
                snapshot.soreness_today = today_checkin.soreness_1_5
                snapshot.hrv_today = today_checkin.hrv_rmssd
                snapshot.resting_hr_today = today_checkin.resting_hr
            
            # 3-day averages
            recent_checkins = [c for c in checkins if c.date >= three_days_ago]
            if recent_checkins:
                sleep_vals = [c.sleep_h for c in recent_checkins if c.sleep_h]
                stress_vals = [c.stress_1_5 for c in recent_checkins if c.stress_1_5]
                soreness_vals = [c.soreness_1_5 for c in recent_checkins if c.soreness_1_5]
                
                if sleep_vals:
                    snapshot.sleep_3_day_avg = statistics.mean(sleep_vals)
                if stress_vals:
                    snapshot.stress_3_day_avg = statistics.mean(stress_vals)
                if soreness_vals:
                    snapshot.soreness_3_day_avg = statistics.mean(soreness_vals)
            
            # 7-day averages
            sleep_vals_7d = [c.sleep_h for c in checkins if c.sleep_h]
            hrv_vals_7d = [c.hrv_rmssd for c in checkins if c.hrv_rmssd]
            rhr_vals_7d = [c.resting_hr for c in checkins if c.resting_hr]
            
            if sleep_vals_7d:
                snapshot.sleep_7_day_avg = statistics.mean(sleep_vals_7d)
            if hrv_vals_7d:
                snapshot.hrv_7_day_avg = statistics.mean(hrv_vals_7d)
            if rhr_vals_7d:
                snapshot.resting_hr_7_day_avg = statistics.mean(rhr_vals_7d)
        
        # Training load (simplified - would need proper TSS calculation)
        activities_7d = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= datetime.combine(week_ago, datetime.min.time()),
            Activity.start_time < datetime.combine(run_date, datetime.min.time())
        ).all()
        
        snapshot.runs_this_week = len(activities_7d)
        snapshot.volume_this_week_km = sum(a.distance_m or 0 for a in activities_7d) / 1000
        
        if activities_7d:
            last_run = max(activities_7d, key=lambda a: a.start_time)
            snapshot.days_since_last_run = (run_date - last_run.start_time.date()).days
        
        return snapshot
    
    # =========================================================================
    # HISTORICAL CONTEXT
    # =========================================================================
    
    def get_historical_context(
        self, 
        athlete_id: UUID, 
        activity: Activity,
        workout_type: WorkoutType
    ) -> WorkoutContext:
        """
        Build historical context for a workout at multiple time scales.
        """
        context = WorkoutContext(
            workout_type=workout_type,
            confidence=0.0
        )
        
        run_date = activity.start_time.date()
        
        # Find similar workouts (same type)
        similar = self._find_similar_workouts(athlete_id, workout_type, run_date, limit=20)
        context.similar_workouts_count = len(similar)
        
        if similar and activity.avg_hr and activity.distance_m:
            # Calculate efficiency score for this run
            pace_per_km = activity.duration_s / (activity.distance_m / 1000)
            context.efficiency_score = activity.avg_hr / pace_per_km if pace_per_km > 0 else None
            
            # Compare to similar workouts
            similar_efficiencies = []
            for s in similar:
                if s.avg_hr and s.distance_m and s.duration_s:
                    s_pace = s.duration_s / (s.distance_m / 1000)
                    if s_pace > 0:
                        similar_efficiencies.append(s.avg_hr / s_pace)
            
            if similar_efficiencies and context.efficiency_score:
                # Lower HR/pace ratio = better efficiency
                better_count = sum(1 for e in similar_efficiencies if e > context.efficiency_score)
                context.percentile_vs_similar = (better_count / len(similar_efficiencies)) * 100
                
                # Trend analysis for similar workouts
                context.trend_vs_similar = self._calculate_trend_direction(
                    similar_efficiencies[-5:] if len(similar_efficiencies) >= 5 else similar_efficiencies
                )
        
        # Time-scale contexts
        context.context_this_week = self._get_week_context(athlete_id, run_date)
        context.context_this_month = self._get_month_context(athlete_id, run_date)
        context.context_this_year = self._get_year_context(athlete_id, run_date)
        
        return context
    
    def _find_similar_workouts(
        self, 
        athlete_id: UUID, 
        workout_type: WorkoutType,
        before_date: date,
        limit: int = 20
    ) -> List[Activity]:
        """Find similar workout types from history"""
        # Get recent activities
        activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time < datetime.combine(before_date, datetime.min.time())
        ).order_by(Activity.start_time.desc()).limit(100).all()
        
        # Filter to same workout type
        similar = []
        for a in activities:
            a_type, _ = self.classify_workout(a)
            if a_type == workout_type:
                similar.append(a)
                if len(similar) >= limit:
                    break
        
        return similar
    
    def _get_week_context(self, athlete_id: UUID, run_date: date) -> Dict:
        """Get context for the current week"""
        week_start = run_date - timedelta(days=run_date.weekday())
        
        activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= datetime.combine(week_start, datetime.min.time()),
            Activity.start_time < datetime.combine(run_date + timedelta(days=1), datetime.min.time())
        ).all()
        
        return {
            "runs_so_far": len(activities),
            "volume_km": sum(a.distance_m or 0 for a in activities) / 1000,
            "avg_efficiency": self._calculate_avg_efficiency(activities)
        }
    
    def _get_month_context(self, athlete_id: UUID, run_date: date) -> Dict:
        """Get context for the current month"""
        month_start = run_date.replace(day=1)
        
        activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= datetime.combine(month_start, datetime.min.time()),
            Activity.start_time < datetime.combine(run_date + timedelta(days=1), datetime.min.time())
        ).all()
        
        return {
            "runs_so_far": len(activities),
            "volume_km": sum(a.distance_m or 0 for a in activities) / 1000,
            "avg_efficiency": self._calculate_avg_efficiency(activities)
        }
    
    def _get_year_context(self, athlete_id: UUID, run_date: date) -> Dict:
        """Get context for the current year"""
        year_start = run_date.replace(month=1, day=1)
        
        activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= datetime.combine(year_start, datetime.min.time()),
            Activity.start_time < datetime.combine(run_date + timedelta(days=1), datetime.min.time())
        ).all()
        
        return {
            "runs_so_far": len(activities),
            "volume_km": sum(a.distance_m or 0 for a in activities) / 1000,
            "avg_efficiency": self._calculate_avg_efficiency(activities)
        }
    
    def _calculate_avg_efficiency(self, activities: List[Activity]) -> Optional[float]:
        """Calculate average efficiency (HR/pace) for a list of activities"""
        efficiencies = []
        for a in activities:
            if a.avg_hr and a.distance_m and a.duration_s:
                pace = a.duration_s / (a.distance_m / 1000)
                if pace > 0:
                    efficiencies.append(a.avg_hr / pace)
        
        return statistics.mean(efficiencies) if efficiencies else None
    
    # =========================================================================
    # TREND DETECTION
    # =========================================================================
    
    def detect_trend(
        self, 
        athlete_id: UUID,
        metric: str,
        days: int = 30,
        min_data_points: int = 5
    ) -> TrendAnalysis:
        """
        Detect trends in a metric over time.
        Uses statistical analysis to distinguish signal from noise.
        """
        analysis = TrendAnalysis(
            metric=metric,
            direction=TrendDirection.INSUFFICIENT_DATA,
            period_days=days
        )
        
        # Get data based on metric type
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        if metric == "efficiency":
            data_points = self._get_efficiency_data_points(athlete_id, start_date)
        elif metric == "volume":
            data_points = self._get_volume_data_points(athlete_id, start_date)
        else:
            return analysis
        
        if len(data_points) < min_data_points:
            return analysis
        
        analysis.data_points = len(data_points)
        
        # Simple linear regression for trend
        values = [d[1] for d in data_points]
        n = len(values)
        
        if n < 2:
            return analysis
        
        # Calculate trend using least squares
        x_mean = (n - 1) / 2
        y_mean = statistics.mean(values)
        
        numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            analysis.direction = TrendDirection.STABLE
            return analysis
        
        slope = numerator / denominator
        
        # Determine direction and magnitude
        relative_change = (slope * n) / y_mean if y_mean != 0 else 0
        analysis.magnitude = relative_change * 100  # As percentage
        
        # Significance threshold (5% change over period)
        if abs(relative_change) < 0.03:
            analysis.direction = TrendDirection.STABLE
        elif relative_change > 0:
            # For efficiency (HR/pace), increasing = declining performance
            analysis.direction = TrendDirection.DECLINING if metric == "efficiency" else TrendDirection.IMPROVING
        else:
            analysis.direction = TrendDirection.IMPROVING if metric == "efficiency" else TrendDirection.DECLINING
        
        # Calculate confidence based on R-squared
        y_pred = [y_mean + slope * (i - x_mean) for i in range(n)]
        ss_res = sum((values[i] - y_pred[i]) ** 2 for i in range(n))
        ss_tot = sum((v - y_mean) ** 2 for v in values)
        
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        analysis.confidence = max(0, min(1, r_squared))
        analysis.is_significant = analysis.confidence > 0.3 and abs(relative_change) > 0.05
        
        return analysis
    
    def _get_efficiency_data_points(
        self, 
        athlete_id: UUID, 
        start_date: datetime
    ) -> List[Tuple[date, float]]:
        """Get efficiency data points for trend analysis"""
        activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= start_date,
            Activity.avg_hr.isnot(None),
            Activity.distance_m > 0,
            Activity.duration_s > 0
        ).order_by(Activity.start_time).all()
        
        data_points = []
        for a in activities:
            pace = a.duration_s / (a.distance_m / 1000)
            if pace > 0:
                efficiency = a.avg_hr / pace
                data_points.append((a.start_time.date(), efficiency))
        
        return data_points
    
    def _get_volume_data_points(
        self,
        athlete_id: UUID,
        start_date: datetime
    ) -> List[Tuple[date, float]]:
        """Get weekly volume data points"""
        activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= start_date,
            Activity.distance_m > 0
        ).order_by(Activity.start_time).all()
        
        # Group by week
        weekly_volume = {}
        for a in activities:
            week_start = a.start_time.date() - timedelta(days=a.start_time.weekday())
            weekly_volume[week_start] = weekly_volume.get(week_start, 0) + (a.distance_m / 1000)
        
        return sorted(weekly_volume.items())
    
    def _calculate_trend_direction(self, values: List[float]) -> TrendDirection:
        """Simple trend direction from a list of values"""
        if len(values) < 3:
            return TrendDirection.INSUFFICIENT_DATA
        
        first_half = statistics.mean(values[:len(values)//2])
        second_half = statistics.mean(values[len(values)//2:])
        
        change = (second_half - first_half) / first_half if first_half != 0 else 0
        
        if abs(change) < 0.03:
            return TrendDirection.STABLE
        elif change > 0:
            return TrendDirection.DECLINING  # Higher HR/pace = worse
        else:
            return TrendDirection.IMPROVING
    
    # =========================================================================
    # ROOT CAUSE ANALYSIS
    # =========================================================================
    
    def analyze_root_causes(
        self,
        athlete_id: UUID,
        declining_metric: str,
        days: int = 30
    ) -> List[RootCauseHypothesis]:
        """
        When a declining trend is detected, analyze potential root causes.
        """
        hypotheses = []
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Get the metric trend data
        if declining_metric == "efficiency":
            metric_data = self._get_efficiency_data_points(athlete_id, start_date)
        else:
            return hypotheses
        
        if len(metric_data) < 5:
            return hypotheses
        
        # Analyze correlations with potential causes
        causes_to_check = [
            ("sleep", self._get_sleep_data_points),
            ("stress", self._get_stress_data_points),
            ("soreness", self._get_soreness_data_points),
            ("volume", self._get_volume_data_points),
        ]
        
        for cause_name, data_func in causes_to_check:
            cause_data = data_func(athlete_id, start_date)
            if len(cause_data) < 3:
                continue
            
            # Simple correlation (would use proper statistical methods in production)
            correlation = self._simple_correlation(metric_data, cause_data)
            
            if abs(correlation) > 0.3:  # Meaningful correlation threshold
                direction = "positive" if correlation > 0 else "negative"
                
                # Generate explanation
                if cause_name == "sleep" and correlation < 0:
                    explanation = f"Decreased sleep correlates with declining efficiency"
                elif cause_name == "stress" and correlation > 0:
                    explanation = f"Increased stress correlates with declining efficiency"
                elif cause_name == "soreness" and correlation > 0:
                    explanation = f"Increased soreness correlates with declining efficiency"
                elif cause_name == "volume" and correlation > 0:
                    explanation = f"Volume increase may be exceeding adaptation capacity"
                else:
                    explanation = f"{cause_name.title()} shows correlation with efficiency changes"
                
                hypotheses.append(RootCauseHypothesis(
                    factor=cause_name,
                    correlation_strength=correlation,
                    direction=direction,
                    confidence=abs(correlation),
                    explanation=explanation
                ))
        
        # Sort by correlation strength
        hypotheses.sort(key=lambda h: abs(h.correlation_strength), reverse=True)
        
        return hypotheses
    
    def _get_sleep_data_points(
        self, 
        athlete_id: UUID, 
        start_date: datetime
    ) -> List[Tuple[date, float]]:
        """Get sleep data points"""
        checkins = self.db.query(DailyCheckin).filter(
            DailyCheckin.athlete_id == athlete_id,
            DailyCheckin.date >= start_date.date(),
            DailyCheckin.sleep_h.isnot(None)
        ).order_by(DailyCheckin.date).all()
        
        return [(c.date, c.sleep_h) for c in checkins]
    
    def _get_stress_data_points(
        self,
        athlete_id: UUID,
        start_date: datetime
    ) -> List[Tuple[date, float]]:
        """Get stress data points"""
        checkins = self.db.query(DailyCheckin).filter(
            DailyCheckin.athlete_id == athlete_id,
            DailyCheckin.date >= start_date.date(),
            DailyCheckin.stress_1_5.isnot(None)
        ).order_by(DailyCheckin.date).all()
        
        return [(c.date, c.stress_1_5) for c in checkins]
    
    def _get_soreness_data_points(
        self,
        athlete_id: UUID,
        start_date: datetime
    ) -> List[Tuple[date, float]]:
        """Get soreness data points"""
        checkins = self.db.query(DailyCheckin).filter(
            DailyCheckin.athlete_id == athlete_id,
            DailyCheckin.date >= start_date.date(),
            DailyCheckin.soreness_1_5.isnot(None)
        ).order_by(DailyCheckin.date).all()
        
        return [(c.date, c.soreness_1_5) for c in checkins]
    
    def _simple_correlation(
        self,
        data1: List[Tuple[date, float]],
        data2: List[Tuple[date, float]]
    ) -> float:
        """Calculate simple Pearson correlation between two time series"""
        # Align by date
        d1_dict = {d: v for d, v in data1}
        d2_dict = {d: v for d, v in data2}
        
        common_dates = set(d1_dict.keys()) & set(d2_dict.keys())
        if len(common_dates) < 3:
            return 0.0
        
        x = [d1_dict[d] for d in sorted(common_dates)]
        y = [d2_dict[d] for d in sorted(common_dates)]
        
        n = len(x)
        x_mean = statistics.mean(x)
        y_mean = statistics.mean(y)
        
        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denom_x = sum((xi - x_mean) ** 2 for xi in x) ** 0.5
        denom_y = sum((yi - y_mean) ** 2 for yi in y) ** 0.5
        
        if denom_x == 0 or denom_y == 0:
            return 0.0
        
        return numerator / (denom_x * denom_y)
    
    # =========================================================================
    # OUTLIER & RED FLAG DETECTION
    # =========================================================================
    
    def check_for_outliers_and_flags(
        self,
        activity: Activity,
        context: WorkoutContext,
        inputs: InputSnapshot
    ) -> Tuple[bool, Optional[str], bool, Optional[str]]:
        """
        Check if a run is an outlier or raises red flags.
        
        Returns: (is_outlier, outlier_reason, is_red_flag, red_flag_reason)
        """
        is_outlier = False
        outlier_reason = None
        is_red_flag = False
        red_flag_reason = None
        
        # Outlier detection: Performance way outside normal range
        if context.percentile_vs_similar is not None:
            if context.percentile_vs_similar < 5:  # Bottom 5%
                is_outlier = True
                outlier_reason = "Performance significantly below recent similar workouts"
            elif context.percentile_vs_similar > 95:  # Top 5%
                is_outlier = True
                outlier_reason = "Performance significantly above recent similar workouts"
        
        # Red flag detection
        red_flags = []
        
        # Extremely high HR for the pace
        if activity.avg_hr and activity.max_hr:
            athlete = self.db.query(Athlete).filter(Athlete.id == activity.athlete_id).first()
            if athlete and athlete.max_hr:
                hr_percent = (activity.avg_hr / athlete.max_hr) * 100
                if hr_percent > 95:
                    red_flags.append("HR near maximum for extended period")
        
        # Very poor sleep before hard effort
        if inputs.sleep_last_night and inputs.sleep_last_night < 5:
            if context.workout_type in [WorkoutType.TEMPO, WorkoutType.INTERVAL, WorkoutType.RACE]:
                red_flags.append("Quality session on minimal sleep (<5h)")
        
        # High stress + high soreness + hard workout
        if (inputs.stress_today and inputs.stress_today >= 4 and
            inputs.soreness_today and inputs.soreness_today >= 4):
            if context.workout_type in [WorkoutType.TEMPO, WorkoutType.INTERVAL, WorkoutType.LONG_RUN]:
                red_flags.append("Hard effort with high stress and soreness")
        
        if red_flags:
            is_red_flag = True
            red_flag_reason = "; ".join(red_flags)
        
        return is_outlier, outlier_reason, is_red_flag, red_flag_reason
    
    # =========================================================================
    # MAIN ANALYSIS ENTRY POINT
    # =========================================================================
    
    def analyze_run(self, activity_id: UUID) -> RunAnalysis:
        """
        Complete analysis of a single run.
        This is the main entry point.
        """
        activity = self.db.query(Activity).filter(Activity.id == activity_id).first()
        if not activity:
            raise ValueError(f"Activity {activity_id} not found")
        
        athlete_id = activity.athlete_id
        run_date = activity.start_time.date()
        
        # 1. Classify the workout
        workout_type, type_confidence = self.classify_workout(activity)
        
        # 2. Get all inputs leading up to this run
        inputs = self.get_input_snapshot(athlete_id, run_date)
        
        # 3. Get historical context
        context = self.get_historical_context(athlete_id, activity, workout_type)
        context.confidence = type_confidence
        
        # 4. Detect trends
        efficiency_trend = self.detect_trend(athlete_id, "efficiency", days=30)
        performance_trend = self.detect_trend(athlete_id, "volume", days=30)
        
        # 5. Check for outliers and red flags
        is_outlier, outlier_reason, is_red_flag, red_flag_reason = \
            self.check_for_outliers_and_flags(activity, context, inputs)
        
        # 6. Root cause analysis if declining
        root_causes = []
        if efficiency_trend.direction == TrendDirection.DECLINING and efficiency_trend.is_significant:
            root_causes = self.analyze_root_causes(athlete_id, "efficiency", days=30)
        
        # 7. Generate insights
        insights = self._generate_insights(
            activity, context, inputs, efficiency_trend, 
            is_outlier, is_red_flag, root_causes
        )
        
        return RunAnalysis(
            activity_id=activity_id,
            athlete_id=athlete_id,
            analysis_timestamp=datetime.now(timezone.utc),
            inputs=inputs,
            context=context,
            efficiency_trend=efficiency_trend,
            performance_trend=performance_trend,
            is_outlier=is_outlier,
            outlier_reason=outlier_reason,
            is_red_flag=is_red_flag,
            red_flag_reason=red_flag_reason,
            root_cause_hypotheses=root_causes,
            insights=insights
        )
    
    def _generate_insights(
        self,
        activity: Activity,
        context: WorkoutContext,
        inputs: InputSnapshot,
        efficiency_trend: TrendAnalysis,
        is_outlier: bool,
        is_red_flag: bool,
        root_causes: List[RootCauseHypothesis]
    ) -> List[str]:
        """Generate human-readable insights from the analysis"""
        insights = []
        
        # Workout type context
        insights.append(
            f"This was classified as a {context.workout_type.value} "
            f"({int(context.confidence * 100)}% confidence)"
        )
        
        # Comparison to similar workouts
        if context.percentile_vs_similar is not None:
            percentile = context.percentile_vs_similar
            if percentile > 75:
                insights.append(
                    f"Better than {int(percentile)}% of your recent {context.workout_type.value} runs"
                )
            elif percentile < 25:
                insights.append(
                    f"Below {int(100 - percentile)}% of your recent {context.workout_type.value} runs"
                )
        
        # Trend information
        if efficiency_trend.is_significant:
            if efficiency_trend.direction == TrendDirection.IMPROVING:
                insights.append(
                    f"Efficiency trend improving ({abs(efficiency_trend.magnitude):.1f}% over {efficiency_trend.period_days} days)"
                )
            elif efficiency_trend.direction == TrendDirection.DECLINING:
                insights.append(
                    f"Efficiency trend declining ({abs(efficiency_trend.magnitude):.1f}% over {efficiency_trend.period_days} days)"
                )
        
        # Root causes
        if root_causes:
            top_cause = root_causes[0]
            insights.append(f"Possible factor: {top_cause.explanation}")
        
        # Input observations
        if inputs.sleep_last_night and inputs.sleep_7_day_avg:
            if inputs.sleep_last_night < inputs.sleep_7_day_avg - 1:
                insights.append(
                    f"Sleep last night ({inputs.sleep_last_night:.1f}h) was below your average ({inputs.sleep_7_day_avg:.1f}h)"
                )
        
        return insights


