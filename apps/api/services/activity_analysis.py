"""
Activity Analysis Service

Core efficiency calculations and meaningful signal detection.
Implements the manifesto's "Master Signal": pace improvement at constant HR,
HR reduction at constant pace, and efficiency trends.

Key principles:
- Only flag meaningful improvements (2-3% confirmed over multiple runs, not single run)
- Multiple baseline types (PRs, last race, training phases/blocks, run type averages)
- No noise - only statistically significant changes
- Research-backed thresholds: 2-3% improvement represents real fitness gains

Based on exercise physiology research:
- Running economy improvements of 2-3% are meaningful and represent real adaptations
- Heart rate at constant pace, pace at constant HR are key efficiency indicators
- Trends must be confirmed over multiple runs to filter out noise
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import logging
from statistics import mean, stdev

from models import Activity, Athlete, PersonalBest, ActivitySplit
from services.performance_engine import calculate_age_at_date
from services.efficiency_calculation import calculate_activity_efficiency_with_decoupling

logger = logging.getLogger(__name__)

# Research-backed thresholds
MIN_IMPROVEMENT_PCT = 2.0  # Minimum improvement to be considered meaningful
CONFIRMED_IMPROVEMENT_PCT = 2.5  # Threshold for confirmed trend (between 2-3%)
TREND_CONFIRMATION_RUNS = 3  # Number of runs needed to confirm a trend
MIN_BASELINE_SAMPLES = 3  # Minimum samples for baseline to be meaningful


class EfficiencyMetrics:
    """Container for efficiency metrics."""
    
    def __init__(
        self,
        pace_per_mile: Optional[float] = None,
        avg_heart_rate: Optional[int] = None,
        efficiency_score: Optional[float] = None,  # pace_per_mile / avg_hr (lower is better)
        distance_m: Optional[int] = None
    ):
        self.pace_per_mile = pace_per_mile
        self.avg_heart_rate = avg_heart_rate
        self.efficiency_score = efficiency_score
        self.distance_m = distance_m
    
    def is_complete(self) -> bool:
        """Check if we have both pace and HR for efficiency calculation."""
        return self.pace_per_mile is not None and self.avg_heart_rate is not None
    
    def calculate_efficiency_score(self) -> Optional[float]:
        """
        Calculate efficiency score: pace_per_mile / avg_hr
        
        Lower score = more efficient (faster pace at same HR, or same pace at lower HR)
        """
        if not self.is_complete():
            return None
        
        # Avoid division by zero
        if self.avg_heart_rate <= 0:
            return None
        
        return self.pace_per_mile / self.avg_heart_rate


class Baseline:
    """Represents a baseline for comparison."""
    
    def __init__(
        self,
        baseline_type: str,  # 'pr', 'last_race', 'current_block', 'run_type_average'
        pace_per_mile: float,
        avg_heart_rate: int,
        distance_m: Optional[int] = None,
        run_type: Optional[str] = None,  # 'easy', 'tempo', 'interval', 'long_run', 'race'
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
        sample_size: int = 1
    ):
        self.baseline_type = baseline_type
        self.pace_per_mile = pace_per_mile
        self.avg_heart_rate = avg_heart_rate
        self.distance_m = distance_m
        self.run_type = run_type
        self.period_start = period_start
        self.period_end = period_end
        self.sample_size = sample_size
        self.efficiency_score = pace_per_mile / avg_heart_rate if avg_heart_rate > 0 else None


class ActivityAnalysis:
    """Analyzes an activity and compares it to baselines."""
    
    def __init__(self, activity: Activity, athlete: Athlete, db: Session):
        self.activity = activity
        self.athlete = athlete
        self.db = db
        self.metrics = self._extract_metrics()
    
    def _extract_metrics(self) -> EfficiencyMetrics:
        """Extract efficiency metrics from activity."""
        pace = self.activity.pace_per_mile
        hr = self.activity.avg_hr
        
        return EfficiencyMetrics(
            pace_per_mile=float(pace) if pace else None,
            avg_heart_rate=hr,
            distance_m=self.activity.distance_m
        )
    
    def get_all_baselines(self) -> List[Baseline]:
        """
        Get all relevant baselines for this activity.
        
        Returns multiple baseline types:
        1. PR for this distance (if race)
        2. Last race for this distance
        3. Current block average (last 4-6 weeks)
        4. Run type average (easy runs, tempo runs, etc.)
        """
        baselines = []
        
        if not self.metrics.is_complete():
            return baselines
        
        # Determine run type
        run_type = self._classify_run_type()
        
        # 1. PR baseline (if this is a race or race-like effort)
        pr_baseline = self._get_pr_baseline()
        if pr_baseline:
            baselines.append(pr_baseline)
        
        # 2. Last race baseline (for this distance)
        last_race_baseline = self._get_last_race_baseline()
        if last_race_baseline:
            baselines.append(last_race_baseline)
        
        # 3. Current block average (last 4-6 weeks, same run type)
        block_baseline = self._get_current_block_baseline(run_type)
        if block_baseline:
            baselines.append(block_baseline)
        
        # 4. Run type average (all time, same run type)
        run_type_baseline = self._get_run_type_baseline(run_type)
        if run_type_baseline:
            baselines.append(run_type_baseline)
        
        return baselines
    
    def _classify_run_type(self) -> Optional[str]:
        """
        Classify run type based on pace, HR, distance, and effort.
        
        Uses exercise physiology principles:
        - Easy: 60-70% max HR, conversational pace
        - Tempo: 70-80% max HR, comfortably hard
        - Threshold: 80-90% max HR, hard but sustainable
        - Interval/VO2max: 90-100% max HR, very hard
        - Long run: Extended duration (>90 min or >10 miles), easy-moderate effort
        - Race: Marked as race or very high effort
        """
        if not self.metrics.is_complete():
            return None
        
        # Race detection (highest priority)
        if self.activity.is_race_candidate or self.activity.user_verified_race:
            return "race"
        
        # Get athlete's max HR estimate (220 - age, or use actual if available)
        age = calculate_age_at_date(self.athlete.birthdate, self.activity.start_time) if self.athlete.birthdate else None
        max_hr_estimate = (220 - age) if age else 200
        
        hr_percent = (self.metrics.avg_heart_rate / max_hr_estimate) * 100 if max_hr_estimate else None
        
        # Long run detection (distance-based, typically easy-moderate effort)
        distance_miles = (self.metrics.distance_m / 1609.34) if self.metrics.distance_m else 0
        duration_hours = (self.activity.duration_s / 3600) if self.activity.duration_s else 0
        
        is_long_run = (distance_miles >= 10) or (duration_hours >= 1.5)
        
        if is_long_run and hr_percent and hr_percent <= 80:
            return "long_run"
        
        # High intensity (intervals/VO2max)
        if hr_percent and hr_percent >= 90:
            return "interval"
        
        # Threshold (hard but sustainable)
        if hr_percent and 80 <= hr_percent < 90:
            return "threshold"
        
        # Tempo (comfortably hard)
        if hr_percent and 70 <= hr_percent < 80:
            return "tempo"
        
        # Easy (conversational pace)
        if hr_percent and hr_percent < 70:
            return "easy"
        
        return None
    
    def _get_pr_baseline(self) -> Optional[Baseline]:
        """Get PR baseline for this distance."""
        if not self.metrics.distance_m:
            return None
        
        # Find PR for this distance (within ~5% distance tolerance)
        distance_tolerance = self.metrics.distance_m * 0.05
        min_distance = self.metrics.distance_m - distance_tolerance
        max_distance = self.metrics.distance_m + distance_tolerance
        
        # PersonalBest uses distance_category, not distance_m
        # We need to map distance_m to category and get HR from linked activity
        prs = self.db.query(PersonalBest).filter(
            PersonalBest.athlete_id == self.athlete.id
        ).all()
        
        # Find closest PR by distance
        closest_pr = None
        closest_activity = None
        min_distance_diff = float('inf')
        
        # Map distance_category to approximate meters
        category_distances = {
            "5k": 5000,
            "10k": 10000,
            "half_marathon": 21100,
            "marathon": 42195,
            "mile": 1609,
            "1500m": 1500,
            "3000m": 3000,
            "400m": 400,
            "800m": 800,
            "2mile": 3218,
            "15k": 15000,
            "25k": 25000,
            "30k": 30000,
            "50k": 50000,
            "100k": 100000
        }
        
        for pr in prs:
            pr_distance = category_distances.get(pr.distance_category.lower(), pr.distance_meters)
            distance_diff = abs(pr_distance - self.metrics.distance_m)
            
            if distance_diff < min_distance_diff and distance_diff <= distance_tolerance:
                # Get the activity that set this PR to get HR
                activity = self.db.query(Activity).filter(Activity.id == pr.activity_id).first()
                if activity and activity.avg_hr:
                    min_distance_diff = distance_diff
                    closest_pr = pr
                    closest_activity = activity
        
        if not closest_pr or not closest_activity or not closest_activity.avg_hr:
            return None
        
        return Baseline(
            baseline_type="pr",
            pace_per_mile=float(closest_pr.pace_per_mile) if closest_pr.pace_per_mile else None,
            avg_heart_rate=closest_activity.avg_hr,
            distance_m=category_distances.get(closest_pr.distance_category.lower(), closest_pr.distance_meters),
            run_type="race",
            sample_size=1
        )
    
    def _get_last_race_baseline(self) -> Optional[Baseline]:
        """Get last race baseline for this distance."""
        if not self.metrics.distance_m:
            return None
        
        distance_tolerance = self.metrics.distance_m * 0.05
        min_distance = self.metrics.distance_m - distance_tolerance
        max_distance = self.metrics.distance_m + distance_tolerance
        
        # Find last race before this activity
        last_race = self.db.query(Activity).filter(
            Activity.athlete_id == self.athlete.id,
            Activity.start_time < self.activity.start_time,
            Activity.distance_m >= min_distance,
            Activity.distance_m <= max_distance,
            or_(
                Activity.user_verified_race == True,
                Activity.is_race_candidate == True
            ),
            Activity.avg_hr.isnot(None),
            Activity.pace_per_mile.isnot(None)
        ).order_by(Activity.start_time.desc()).first()
        
        if not last_race:
            return None
        
        return Baseline(
            baseline_type="last_race",
            pace_per_mile=float(last_race.pace_per_mile),
            avg_heart_rate=last_race.avg_hr,
            distance_m=last_race.distance_m,
            run_type="race",
            period_start=last_race.start_time,
            sample_size=1
        )
    
    def _get_current_block_baseline(self, run_type: Optional[str]) -> Optional[Baseline]:
        """
        Get current training block baseline (last 4-6 weeks).
        
        Prioritizes activities of same run type if available, otherwise uses all activities.
        Uses multiple time windows to detect training phases.
        """
        # Try multiple block windows: 4 weeks, 6 weeks, 8 weeks
        # Use the one with most data and same run type if possible
        block_windows = [4, 6, 8]
        best_baseline = None
        best_score = 0
        
        for weeks in block_windows:
            block_start = self.activity.start_time - timedelta(weeks=weeks)
            
            query = self.db.query(Activity).filter(
                Activity.athlete_id == self.athlete.id,
                Activity.start_time >= block_start,
                Activity.start_time < self.activity.start_time,
                Activity.avg_hr.isnot(None),
                Activity.pace_per_mile.isnot(None)
            )
            
            activities = query.all()
            
            if len(activities) < MIN_BASELINE_SAMPLES:
                continue
            
            # Try to match run type if we have classification
            if run_type:
                # Classify each activity and filter by run type
                matching_activities = []
                for act in activities:
                    act_analysis = ActivityAnalysis(act, self.athlete, self.db)
                    act_run_type = act_analysis._classify_run_type()
                    if act_run_type == run_type:
                        matching_activities.append(act)
                
                # Use matching activities if we have enough, otherwise use all
                if len(matching_activities) >= MIN_BASELINE_SAMPLES:
                    activities = matching_activities
            
            # Calculate average pace and HR
            paces = [float(a.pace_per_mile) for a in activities if a.pace_per_mile]
            hrs = [a.avg_hr for a in activities if a.avg_hr]
            
            if not paces or not hrs:
                continue
            
            avg_pace = mean(paces)
            avg_hr = int(mean(hrs))
            
            # Score: prioritize same run type matches and larger sample sizes
            score = len(activities)
            if run_type and all(ActivityAnalysis(a, self.athlete, self.db)._classify_run_type() == run_type for a in activities):
                score *= 2
            
            if score > best_score:
                best_score = score
                best_baseline = Baseline(
                    baseline_type="current_block",
                    pace_per_mile=avg_pace,
                    avg_heart_rate=avg_hr,
                    run_type=run_type,
                    period_start=block_start,
                    period_end=self.activity.start_time,
                    sample_size=len(activities)
                )
        
        return best_baseline
    
    def _get_run_type_baseline(self, run_type: Optional[str]) -> Optional[Baseline]:
        """
        Get all-time average for this run type.
        
        Classifies historical activities to match run type.
        """
        query = self.db.query(Activity).filter(
            Activity.athlete_id == self.athlete.id,
            Activity.start_time < self.activity.start_time,
            Activity.avg_hr.isnot(None),
            Activity.pace_per_mile.isnot(None)
        )
        
        all_activities = query.all()
        
        if len(all_activities) < 5:  # Need at least 5 runs for meaningful baseline
            return None
        
        # If we have run type, try to match it
        if run_type:
            matching_activities = []
            for act in all_activities:
                act_analysis = ActivityAnalysis(act, self.athlete, self.db)
                act_run_type = act_analysis._classify_run_type()
                if act_run_type == run_type:
                    matching_activities.append(act)
            
            # Use matching if we have enough, otherwise use all
            if len(matching_activities) >= MIN_BASELINE_SAMPLES:
                activities = matching_activities
            else:
                activities = all_activities
        else:
            activities = all_activities
        
        paces = [float(a.pace_per_mile) for a in activities if a.pace_per_mile]
        hrs = [a.avg_hr for a in activities if a.avg_hr]
        
        if not paces or not hrs:
            return None
        
        avg_pace = mean(paces)
        avg_hr = int(mean(hrs))
        
        return Baseline(
            baseline_type="run_type_average",
            pace_per_mile=avg_pace,
            avg_heart_rate=avg_hr,
            run_type=run_type,
            sample_size=len(activities)
        )
    
    def _check_trend_confirmation(self, baseline: Baseline) -> Tuple[bool, Optional[float]]:
        """
        Check if improvement is confirmed over multiple runs (not just single run).
        
        Returns:
            (is_confirmed, average_improvement_pct)
        """
        if not self.metrics.is_complete() or not baseline.efficiency_score:
            return (False, None)
        
        current_efficiency = self.metrics.calculate_efficiency_score()
        if not current_efficiency:
            return (False, None)
        
        # Get recent activities of same run type (last 2-4 weeks)
        lookback_start = self.activity.start_time - timedelta(weeks=4)
        
        query = self.db.query(Activity).filter(
            Activity.athlete_id == self.athlete.id,
            Activity.start_time >= lookback_start,
            Activity.start_time <= self.activity.start_time,
            Activity.avg_hr.isnot(None),
            Activity.pace_per_mile.isnot(None)
        )
        
        # Filter by run type if available
        if baseline.run_type:
            activities = []
            for act in query.all():
                act_analysis = ActivityAnalysis(act, self.athlete, self.db)
                if act_analysis._classify_run_type() == baseline.run_type:
                    activities.append(act)
        else:
            activities = query.all()
        
        # Need at least TREND_CONFIRMATION_RUNS runs to confirm trend
        if len(activities) < TREND_CONFIRMATION_RUNS:
            return (False, None)
        
        # Calculate efficiency for each recent run
        recent_efficiencies = []
        for act in activities:
            act_metrics = EfficiencyMetrics(
                pace_per_mile=float(act.pace_per_mile) if act.pace_per_mile else None,
                avg_heart_rate=act.avg_hr,
                distance_m=act.distance_m
            )
            if act_metrics.is_complete():
                eff = act_metrics.calculate_efficiency_score()
                if eff:
                    recent_efficiencies.append(eff)
        
        if len(recent_efficiencies) < TREND_CONFIRMATION_RUNS:
            return (False, None)
        
        # Calculate average improvement over recent runs
        improvements = [
            ((baseline.efficiency_score - eff) / baseline.efficiency_score) * 100
            for eff in recent_efficiencies
        ]
        
        avg_improvement = mean(improvements)
        
        # Confirm trend if average improvement meets threshold
        is_confirmed = avg_improvement >= CONFIRMED_IMPROVEMENT_PCT
        
        return (is_confirmed, avg_improvement)
    
    def analyze(self) -> Dict:
        """
        Analyze activity and return insights.
        
        Key: Only flags improvements that are confirmed over multiple runs (2-3% threshold).
        Single-run improvements are noted but not flagged as "meaningful" unless trend is confirmed.
        
        Returns:
            {
                "has_meaningful_insight": bool,
                "insights": List[str],
                "metrics": {
                    "pace_per_mile": float,
                    "avg_heart_rate": int,
                    "efficiency_score": float
                },
                "comparisons": [
                    {
                        "baseline_type": str,
                        "improvement_pct": float,
                        "is_meaningful": bool,
                        "is_confirmed_trend": bool,
                        "trend_avg_improvement": Optional[float],
                        "sample_size": int
                    }
                ]
            }
        """
        if not self.metrics.is_complete():
            # Still calculate decoupling even if metrics incomplete
            splits = self.db.query(ActivitySplit).filter(
                ActivitySplit.activity_id == self.activity.id
            ).order_by(ActivitySplit.split_number).all()
            
            decoupling_data = calculate_activity_efficiency_with_decoupling(
                activity=self.activity,
                splits=splits,
                max_hr=None
            )
            
            return {
                "has_meaningful_insight": False,
                "insights": [],
                "metrics": {
                    "pace_per_mile": self.metrics.pace_per_mile,
                    "avg_heart_rate": self.metrics.avg_heart_rate,
                    "efficiency_score": None
                },
                "comparisons": [],
                "decoupling": {
                    "decoupling_percent": decoupling_data.get("decoupling_percent"),
                    "decoupling_status": decoupling_data.get("decoupling_status"),
                    "first_half_ef": decoupling_data.get("first_half_ef"),
                    "second_half_ef": decoupling_data.get("second_half_ef"),
                    "efficiency_factor": decoupling_data.get("efficiency_factor")
                }
            }
        
        # Calculate efficiency score
        efficiency_score = self.metrics.calculate_efficiency_score()
        
        # Calculate decoupling using GAP
        splits = self.db.query(ActivitySplit).filter(
            ActivitySplit.activity_id == self.activity.id
        ).order_by(ActivitySplit.split_number).all()
        
        decoupling_data = calculate_activity_efficiency_with_decoupling(
            activity=self.activity,
            splits=splits,
            max_hr=None  # Could extract from athlete profile if stored
        )
        
        # Get all baselines
        baselines = self.get_all_baselines()
        
        # Compare against each baseline
        comparisons = []
        insights = []
        has_meaningful_insight = False
        
        for baseline in baselines:
            if not baseline.efficiency_score:
                continue
            
            # Calculate improvement percentage for this single run
            improvement_pct = ((baseline.efficiency_score - efficiency_score) / baseline.efficiency_score) * 100
            
            # Check if improvement meets minimum threshold
            meets_threshold = improvement_pct >= MIN_IMPROVEMENT_PCT
            
            # For PR/race comparisons, single-run improvement can be meaningful
            # For block/run type averages, need trend confirmation
            is_meaningful = False
            is_confirmed_trend = False
            trend_avg_improvement = None
            
            if baseline.baseline_type in ["pr", "last_race"]:
                # PR/race: single-run improvement >= 2% is meaningful
                is_meaningful = meets_threshold
            else:
                # Block/run type: need trend confirmation over multiple runs
                if meets_threshold and baseline.sample_size >= MIN_BASELINE_SAMPLES:
                    is_confirmed, avg_improvement = self._check_trend_confirmation(baseline)
                    is_confirmed_trend = is_confirmed
                    trend_avg_improvement = avg_improvement
                    is_meaningful = is_confirmed
            
            if is_meaningful:
                has_meaningful_insight = True
                message = self._format_improvement_message(
                    baseline, 
                    trend_avg_improvement if trend_avg_improvement else improvement_pct,
                    is_confirmed_trend
                )
                insights.append(message)
            
            comparisons.append({
                "baseline_type": baseline.baseline_type,
                "baseline_pace": baseline.pace_per_mile,
                "baseline_hr": baseline.avg_heart_rate,
                "improvement_pct": round(improvement_pct, 2),
                "is_meaningful": is_meaningful,
                "is_confirmed_trend": is_confirmed_trend,
                "trend_avg_improvement": round(trend_avg_improvement, 2) if trend_avg_improvement else None,
                "sample_size": baseline.sample_size
            })
        
        return {
            "has_meaningful_insight": has_meaningful_insight,
            "insights": insights,
            "metrics": {
                "pace_per_mile": self.metrics.pace_per_mile,
                "avg_heart_rate": self.metrics.avg_heart_rate,
                "efficiency_score": round(efficiency_score, 4) if efficiency_score else None
            },
            "comparisons": comparisons,
            "decoupling": {
                "decoupling_percent": decoupling_data.get("decoupling_percent"),
                "decoupling_status": decoupling_data.get("decoupling_status"),
                "first_half_ef": decoupling_data.get("first_half_ef"),
                "second_half_ef": decoupling_data.get("second_half_ef"),
                "efficiency_factor": decoupling_data.get("efficiency_factor")
            }
        }
    
    def _format_improvement_message(
        self, 
        baseline: Baseline, 
        improvement_pct: float,
        is_confirmed_trend: bool = False
    ) -> str:
        """Format improvement message based on baseline type."""
        trend_note = " (confirmed trend)" if is_confirmed_trend else ""
        
        if baseline.baseline_type == "pr":
            return f"PR efficiency: {improvement_pct:.1f}% improvement vs your best{trend_note}"
        elif baseline.baseline_type == "last_race":
            return f"Race efficiency: {improvement_pct:.1f}% improvement vs your last race{trend_note}"
        elif baseline.baseline_type == "current_block":
            return f"Block efficiency: {improvement_pct:.1f}% improvement vs your recent training{trend_note}"
        elif baseline.baseline_type == "run_type_average":
            run_type_str = f" ({baseline.run_type})" if baseline.run_type else ""
            return f"Efficiency trend{run_type_str}: {improvement_pct:.1f}% improvement vs your average{trend_note}"
        else:
            return f"Efficiency improvement: {improvement_pct:.1f}%{trend_note}"


def analyze_activity(activity_id: str, db: Session) -> Dict:
    """
    Analyze an activity and return insights.
    
    Main entry point for activity analysis.
    """
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        raise ValueError(f"Activity {activity_id} not found")
    
    athlete = db.query(Athlete).filter(Athlete.id == activity.athlete_id).first()
    if not athlete:
        raise ValueError(f"Athlete {activity.athlete_id} not found")
    
    analysis = ActivityAnalysis(activity, athlete, db)
    return analysis.analyze()

