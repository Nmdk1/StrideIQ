"""
Fitness Bank Framework (ADR-030)

The Fitness Bank tracks an athlete's PROVEN capabilities, not just current state.
This enables plans that target peak performance for experienced athletes 
returning from injury or reduced training.

Key Principle: The athlete's history IS the data. Generic plans fail because
they ignore what the athlete has already proven they can do.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import List, Dict, Optional, Tuple
from uuid import UUID
import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# =============================================================================
# MODELS
# =============================================================================

@dataclass
class RacePerformance:
    """A proven race result - ground truth for fitness."""
    date: date
    distance: str                     # "5k", "10k", "10_mile", "half", "marathon"
    distance_m: float
    finish_time_seconds: int
    pace_per_mile: float
    vdot: float
    conditions: Optional[str] = None  # "limping", "hot", "hilly", "perfect"
    confidence: float = 1.0           # Weight for this performance
    name: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "date": self.date.isoformat(),
            "distance": self.distance,
            "finish_time": self.finish_time_seconds,
            "pace_per_mile": round(self.pace_per_mile, 2),
            "vdot": round(self.vdot, 1),
            "conditions": self.conditions
        }


class ConstraintType(Enum):
    NONE = "none"
    INJURY = "injury"
    TIME = "time"
    DETRAINED = "detrained"


class ExperienceLevel(Enum):
    BEGINNER = "beginner"         # < 30 mpw, < 10 races
    INTERMEDIATE = "intermediate" # 30-50 mpw, some races
    EXPERIENCED = "experienced"   # 50-70 mpw, many races
    ELITE = "elite"               # 70+ mpw, competitive races


@dataclass
class FitnessBank:
    """
    Athlete's proven fitness capabilities.
    
    This is NOT current fitness - it's PEAK PROVEN capability.
    An injured athlete still has their fitness banked.
    """
    athlete_id: str
    
    # Peak capabilities (from history)
    peak_weekly_miles: float
    peak_monthly_miles: float
    peak_long_run_miles: float
    peak_mp_long_run_miles: float     # Longest MP portion in a long run
    peak_threshold_miles: float       # Longest threshold session
    peak_ctl: float
    
    # Proven race performances
    race_performances: List[RacePerformance]
    best_vdot: float
    best_race: Optional[RacePerformance]
    
    # Current state
    current_weekly_miles: float
    current_ctl: float
    current_atl: float
    weeks_since_peak: int
    
    # N=1 Long Run Data (ADR-038)
    # Used for progressive long run calculation
    current_long_run_miles: float         # Max long run in last 4 weeks
    average_long_run_miles: float         # Average of all long runs >= 10mi
    
    # Individual response characteristics
    tau1: float
    tau2: float
    experience_level: ExperienceLevel
    
    # Constraint analysis
    constraint_type: ConstraintType
    constraint_details: Optional[str]
    is_returning_from_break: bool
    
    # Training patterns detected
    typical_long_run_day: Optional[int]   # 0=Mon, 6=Sun
    typical_quality_day: Optional[int]
    typical_rest_days: List[int]
    
    # Projections
    weeks_to_80pct_ctl: int              # Weeks to recover 80% of peak CTL
    weeks_to_race_ready: int             # Weeks to be competitive
    sustainable_peak_weekly: float        # What they can sustain for 4+ weeks
    
    def to_dict(self) -> Dict:
        return {
            "athlete_id": self.athlete_id,
            "peak": {
                "weekly_miles": round(self.peak_weekly_miles, 1),
                "monthly_miles": round(self.peak_monthly_miles, 0),
                "long_run": round(self.peak_long_run_miles, 1),
                "mp_long_run": round(self.peak_mp_long_run_miles, 1),
                "ctl": round(self.peak_ctl, 0)
            },
            "current": {
                "weekly_miles": round(self.current_weekly_miles, 1),
                "ctl": round(self.current_ctl, 0),
                "atl": round(self.current_atl, 0),
                "long_run": round(self.current_long_run_miles, 1),
                "avg_long_run": round(self.average_long_run_miles, 1)
            },
            "best_vdot": round(self.best_vdot, 1),
            "races": [r.to_dict() for r in self.race_performances[:5]],
            "tau1": round(self.tau1, 1),
            "tau2": round(self.tau2, 1),
            "experience": self.experience_level.value,
            "constraint": {
                "type": self.constraint_type.value,
                "details": self.constraint_details,
                "returning": self.is_returning_from_break
            },
            "projections": {
                "weeks_to_80pct": self.weeks_to_80pct_ctl,
                "weeks_to_race_ready": self.weeks_to_race_ready,
                "sustainable_peak": round(self.sustainable_peak_weekly, 0)
            }
        }


# =============================================================================
# VDOT CALCULATION
# =============================================================================

def calculate_vdot(distance_m: float, time_seconds: int) -> float:
    """
    Calculate VDOT from race performance.
    
    Uses Daniels' formula approximation.
    """
    if time_seconds <= 0 or distance_m <= 0:
        return 0.0
    
    # Time in minutes
    t = time_seconds / 60.0
    
    # Distance in meters
    d = distance_m
    
    # Velocity in m/min
    v = d / t
    
    # Oxygen cost (ml/kg/min)
    # VO2 = -4.60 + 0.182258*v + 0.000104*v^2
    vo2 = -4.60 + 0.182258 * v + 0.000104 * (v ** 2)
    
    # Percent of VO2max for given time
    # %VO2max = 0.8 + 0.1894393*e^(-0.012778*t) + 0.2989558*e^(-0.1932605*t)
    import math
    pct_vo2max = 0.8 + 0.1894393 * math.exp(-0.012778 * t) + 0.2989558 * math.exp(-0.1932605 * t)
    
    # VDOT = VO2 / %VO2max
    if pct_vo2max > 0:
        vdot = vo2 / pct_vo2max
    else:
        vdot = 0.0
    
    return max(20.0, min(85.0, vdot))  # Clamp to reasonable range


def vdot_equivalent_time(vdot: float, distance_m: float) -> int:
    """Calculate equivalent time for a distance given VDOT."""
    import math
    
    # Binary search for time that gives this VDOT at this distance
    low, high = 60, 36000  # 1 min to 10 hours
    
    for _ in range(50):
        mid = (low + high) // 2
        calc_vdot = calculate_vdot(distance_m, mid)
        
        if abs(calc_vdot - vdot) < 0.1:
            return mid
        elif calc_vdot > vdot:
            low = mid
        else:
            high = mid
    
    return mid


# =============================================================================
# FITNESS BANK CALCULATOR
# =============================================================================

class FitnessBankCalculator:
    """
    Calculate athlete's fitness bank from full training history.
    
    This looks at ALL available data to understand:
    1. What has the athlete PROVEN they can do?
    2. What is their current state?
    3. What constraints are limiting them?
    4. How fast do they respond to training?
    """
    
    DISTANCE_METERS = {
        "5k": 5000,
        "10k": 10000,
        "10_mile": 16093,
        "15k": 15000,
        "half": 21097,
        "half_marathon": 21097,
        "marathon": 42195
    }
    
    def __init__(self, db: Session):
        self.db = db
    
    def calculate(self, athlete_id: UUID) -> FitnessBank:
        """
        Build complete fitness bank from athlete history.
        """
        from models import Activity
        from services.individual_performance_model import get_or_calibrate_model
        from services.training_load import TrainingLoadCalculator
        
        # Get all running activities (full history)
        activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.sport.ilike("run")
        ).order_by(Activity.start_time.desc()).all()
        
        if not activities:
            return self._default_fitness_bank(str(athlete_id))
        
        # Get calibrated model for τ values
        try:
            model = get_or_calibrate_model(athlete_id, self.db)
            tau1 = model.tau1
            tau2 = model.tau2
        except Exception as e:
            logger.warning(f"Could not get model: {e}")
            tau1, tau2 = 42.0, 7.0
        
        # Get current CTL/ATL
        try:
            load_calc = TrainingLoadCalculator(self.db)
            current_load = load_calc.calculate_training_load(athlete_id)
            current_ctl = current_load.current_ctl
            current_atl = current_load.current_atl
        except Exception as e:
            logger.warning(f"Could not get current load: {e}")
            current_ctl, current_atl = 50.0, 40.0
        
        # Calculate peak capabilities
        peaks = self._calculate_peak_capabilities(activities)
        
        # Extract race performances
        races = self._extract_race_performances(activities)
        best_vdot, best_race = self._find_best_race(races)
        
        # Calculate current weekly volume
        current_weekly = self._calculate_current_weekly(activities)
        
        # Determine experience level
        experience = self._determine_experience(peaks, races)
        
        # Detect constraints
        constraint_type, constraint_details, is_returning = self._detect_constraint(
            peaks, current_weekly, activities
        )
        
        # Detect training patterns
        patterns = self._detect_training_patterns(activities)
        
        # Calculate projections
        weeks_to_80pct = self._project_recovery_time(
            current_ctl, peaks["peak_ctl"], tau1, 0.8
        )
        weeks_to_race = self._project_race_readiness(
            current_ctl, peaks["peak_ctl"], tau1, experience
        )
        
        # Sustainable peak (can maintain for 4+ weeks)
        sustainable = peaks["peak_weekly"] * 0.92
        
        # Find weeks since peak
        weeks_since_peak = self._weeks_since_peak(activities, peaks["peak_weekly"])
        
        # Calculate current and average long run (ADR-038: N=1 long run progression)
        current_long, average_long = self._calculate_current_long_run(activities)
        
        return FitnessBank(
            athlete_id=str(athlete_id),
            peak_weekly_miles=peaks["peak_weekly"],
            peak_monthly_miles=peaks["peak_monthly"],
            peak_long_run_miles=peaks["peak_long_run"],
            peak_mp_long_run_miles=peaks["peak_mp_long_run"],
            peak_threshold_miles=peaks["peak_threshold"],
            peak_ctl=peaks["peak_ctl"],
            race_performances=races,
            best_vdot=best_vdot,
            best_race=best_race,
            current_weekly_miles=current_weekly,
            current_ctl=current_ctl,
            current_atl=current_atl,
            weeks_since_peak=weeks_since_peak,
            current_long_run_miles=current_long,
            average_long_run_miles=average_long,
            tau1=tau1,
            tau2=tau2,
            experience_level=experience,
            constraint_type=constraint_type,
            constraint_details=constraint_details,
            is_returning_from_break=is_returning,
            typical_long_run_day=patterns.get("long_run_day"),
            typical_quality_day=patterns.get("quality_day"),
            typical_rest_days=patterns.get("rest_days", []),
            weeks_to_80pct_ctl=weeks_to_80pct,
            weeks_to_race_ready=weeks_to_race,
            sustainable_peak_weekly=sustainable
        )
    
    def _calculate_peak_capabilities(self, activities: List) -> Dict:
        """Calculate peak capabilities from all activities."""
        
        weekly_miles = {}
        monthly_miles = {}
        long_runs = []
        mp_long_runs = []
        threshold_sessions = []
        weekly_tss = {}
        
        for a in activities:
            miles = (a.distance_m or 0) / 1609.344
            week_start = a.start_time.date() - timedelta(days=a.start_time.weekday())
            month_key = a.start_time.strftime("%Y-%m")
            
            # Weekly volume
            if week_start not in weekly_miles:
                weekly_miles[week_start] = 0
            weekly_miles[week_start] += miles
            
            # Monthly volume
            if month_key not in monthly_miles:
                monthly_miles[month_key] = 0
            monthly_miles[month_key] += miles
            
            # Weekly TSS (estimate CTL)
            if week_start not in weekly_tss:
                weekly_tss[week_start] = 0
            # Rough TSS estimate: miles * 10 for easy, * 15 for hard
            weekly_tss[week_start] += miles * 10
            
            # Long runs (13+ miles)
            if miles >= 13:
                long_runs.append(miles)
                
                # Check for MP work
                name_lower = (a.name or "").lower()
                if any(kw in name_lower for kw in ["mp", "marathon pace", "race pace"]):
                    mp_long_runs.append(miles)
            
            # Threshold sessions
            name_lower = (a.name or "").lower()
            workout_type = (a.workout_type or "").lower()
            if any(kw in name_lower for kw in ["threshold", "tempo", "@ t"]) or \
               workout_type in ("tempo", "threshold"):
                threshold_sessions.append(miles)
        
        # Calculate peaks
        peak_weekly = max(weekly_miles.values()) if weekly_miles else 40.0
        peak_monthly = max(monthly_miles.values()) if monthly_miles else 160.0
        peak_long = max(long_runs) if long_runs else 15.0
        peak_mp_long = max(mp_long_runs) if mp_long_runs else 0.0
        peak_threshold = max(threshold_sessions) if threshold_sessions else 6.0
        
        # Peak CTL (approximate from TSS)
        if weekly_tss:
            sorted_tss = sorted(weekly_tss.values(), reverse=True)
            # Use average of top 4 weeks as peak CTL
            top_weeks = sorted_tss[:4]
            peak_ctl = sum(top_weeks) / len(top_weeks) / 7  # Daily average
        else:
            peak_ctl = 50.0
        
        return {
            "peak_weekly": peak_weekly,
            "peak_monthly": peak_monthly,
            "peak_long_run": peak_long,
            "peak_mp_long_run": peak_mp_long,
            "peak_threshold": peak_threshold,
            "peak_ctl": peak_ctl
        }
    
    def _extract_race_performances(self, activities: List) -> List[RacePerformance]:
        """Extract all race performances from activities."""
        races = []
        
        for a in activities:
            miles = (a.distance_m or 0) / 1609.344
            duration_sec = a.duration_s or 0
            
            if duration_sec <= 0 or miles <= 0:
                continue
            
            pace = (duration_sec / 60) / miles
            name_lower = (a.name or "").lower()
            
            # Detect race by various signals
            is_race = False
            distance_type = None
            conditions = None
            
            # By exact distance
            if 3.0 <= miles <= 3.2:
                is_race = True
                distance_type = "5k"
            elif 6.0 <= miles <= 6.4 and pace < 8.0:
                is_race = True
                distance_type = "10k"
            elif 9.8 <= miles <= 10.2 and pace < 8.0:
                is_race = True
                distance_type = "10_mile"
            elif 13.0 <= miles <= 13.3:
                is_race = True
                distance_type = "half"
            elif 26.0 <= miles <= 26.5:
                is_race = True
                distance_type = "marathon"
            
            # By name keywords
            if any(kw in name_lower for kw in ["race", "pr", "pb", "record"]):
                is_race = True
                if not distance_type:
                    distance_type = self._infer_distance_type(miles)
            
            # By workout type
            if a.workout_type and "race" in a.workout_type.lower():
                is_race = True
                if not distance_type:
                    distance_type = self._infer_distance_type(miles)
            
            # Check for condition notes
            if "limp" in name_lower or "injured" in name_lower:
                conditions = "limping"
            elif "hot" in name_lower or "heat" in name_lower:
                conditions = "hot"
            elif "hill" in name_lower:
                conditions = "hilly"
            
            if is_race and distance_type:
                vdot = calculate_vdot(a.distance_m, duration_sec)
                
                # Adjust confidence based on conditions
                confidence = 1.0
                if conditions == "limping":
                    confidence = 1.2  # Actually MORE impressive
                elif conditions == "hot":
                    confidence = 1.1
                elif conditions == "hilly":
                    confidence = 1.05
                
                races.append(RacePerformance(
                    date=a.start_time.date(),
                    distance=distance_type,
                    distance_m=a.distance_m,
                    finish_time_seconds=duration_sec,
                    pace_per_mile=pace,
                    vdot=vdot,
                    conditions=conditions,
                    confidence=confidence,
                    name=a.name
                ))
        
        # Sort by date (most recent first)
        races.sort(key=lambda x: x.date, reverse=True)
        
        return races
    
    def _infer_distance_type(self, miles: float) -> str:
        """Infer race distance from miles."""
        if miles < 4:
            return "5k"
        elif miles < 7:
            return "10k"
        elif miles < 11:
            return "10_mile"
        elif miles < 15:
            return "half"
        else:
            return "marathon"
    
    def _find_best_race(self, races: List[RacePerformance]) -> Tuple[float, Optional[RacePerformance]]:
        """Find best VDOT from races, weighted by confidence and recency."""
        if not races:
            return 45.0, None
        
        # Weight by recency and confidence
        today = date.today()
        weighted_races = []
        
        for r in races:
            days_ago = (today - r.date).days
            recency_weight = max(0.5, 1.0 - (days_ago / 365))  # Decay over year
            
            # Adjust VDOT by confidence (limping = actual fitness higher)
            adjusted_vdot = r.vdot * r.confidence
            
            weighted_races.append((adjusted_vdot * recency_weight, r))
        
        # Sort by weighted VDOT
        weighted_races.sort(key=lambda x: x[0], reverse=True)
        
        best_race = weighted_races[0][1]
        
        # Return the actual (unadjusted) best VDOT from recent good races
        return best_race.vdot * best_race.confidence, best_race
    
    def _calculate_current_weekly(self, activities: List) -> float:
        """Calculate current weekly mileage (last 4 weeks average)."""
        today = date.today()
        four_weeks_ago = today - timedelta(days=28)
        
        weekly_miles = {}
        for a in activities:
            if a.start_time.date() >= four_weeks_ago:
                week_start = a.start_time.date() - timedelta(days=a.start_time.weekday())
                if week_start not in weekly_miles:
                    weekly_miles[week_start] = 0
                weekly_miles[week_start] += (a.distance_m or 0) / 1609.344
        
        if not weekly_miles:
            return 0.0
        
        return sum(weekly_miles.values()) / len(weekly_miles)
    
    def _calculate_current_long_run(self, activities: List) -> Tuple[float, float]:
        """
        Calculate current and average long run from activity data.
        
        ADR-038: N=1 Long Run Progression
        
        Uses athlete's actual data, not population formulas.
        
        Returns:
            Tuple of (current_long_run, average_long_run):
            - current_long_run: Max long run in last 4 weeks
            - average_long_run: Average of all long runs >= 10mi (or 90+ min)
        """
        today = date.today()
        four_weeks_ago = today - timedelta(days=28)
        
        recent_long_runs = []
        all_long_runs = []
        
        for a in activities:
            miles = (a.distance_m or 0) / 1609.344
            duration_min = (a.duration_s or 0) / 60
            
            # Long run threshold: 10+ miles OR 90+ minutes
            # This catches long runs at any pace
            is_long_run = miles >= 10 or duration_min >= 90
            
            if is_long_run:
                all_long_runs.append(miles)
                
                # Recent long runs (last 4 weeks)
                if a.start_time.date() >= four_weeks_ago:
                    recent_long_runs.append(miles)
        
        # Current: max of recent long runs (what they can do NOW)
        current = max(recent_long_runs) if recent_long_runs else 0.0
        
        # Average: mean of all long runs (their typical long run)
        average = sum(all_long_runs) / len(all_long_runs) if all_long_runs else 0.0
        
        logger.info(
            f"N=1 Long Run Data: current={current:.1f}mi (from {len(recent_long_runs)} recent), "
            f"average={average:.1f}mi (from {len(all_long_runs)} total)"
        )
        
        return current, average
    
    def _determine_experience(self, peaks: Dict, races: List[RacePerformance]) -> ExperienceLevel:
        """Determine experience level from history."""
        peak_weekly = peaks["peak_weekly"]
        num_races = len(races)
        peak_long = peaks["peak_long_run"]
        
        if peak_weekly >= 70 or (num_races >= 10 and peaks["peak_mp_long_run"] >= 16):
            return ExperienceLevel.ELITE
        elif peak_weekly >= 50 or (num_races >= 5 and peak_long >= 20):
            return ExperienceLevel.EXPERIENCED
        elif peak_weekly >= 30 or num_races >= 3:
            return ExperienceLevel.INTERMEDIATE
        else:
            return ExperienceLevel.BEGINNER
    
    def _detect_constraint(self, peaks: Dict, current_weekly: float, 
                          activities: List) -> Tuple[ConstraintType, Optional[str], bool]:
        """Detect what's limiting the athlete."""
        peak_weekly = peaks["peak_weekly"]
        
        if current_weekly < 0.1:
            # No recent running at all
            return ConstraintType.INJURY, "no recent activity", True
        
        ratio = current_weekly / peak_weekly if peak_weekly > 0 else 1.0
        
        if ratio >= 0.8:
            # Running at or near peak
            return ConstraintType.NONE, None, False
        
        # Check how fast the drop happened
        today = date.today()
        
        # Find last week at near-peak volume
        weekly_miles = {}
        for a in activities:
            week_start = a.start_time.date() - timedelta(days=a.start_time.weekday())
            if week_start not in weekly_miles:
                weekly_miles[week_start] = 0
            weekly_miles[week_start] += (a.distance_m or 0) / 1609.344
        
        last_peak_week = None
        for week, miles in sorted(weekly_miles.items(), reverse=True):
            if miles >= peak_weekly * 0.8:
                last_peak_week = week
                break
        
        if last_peak_week:
            weeks_since = (today - last_peak_week).days // 7
            
            if weeks_since <= 8 and ratio < 0.5:
                # Sharp drop recently = likely injury
                return ConstraintType.INJURY, "sharp volume drop", True
            elif weeks_since > 12:
                # Long time since peak = detrained
                return ConstraintType.DETRAINED, "extended break", True
        
        if ratio < 0.6:
            return ConstraintType.INJURY, "reduced volume", True
        
        return ConstraintType.TIME, "moderate reduction", False
    
    def _detect_training_patterns(self, activities: List) -> Dict:
        """Detect typical training patterns (which days for what)."""
        day_counts = {i: {"long": 0, "quality": 0, "runs": 0} for i in range(7)}
        
        for a in activities:
            day = a.start_time.weekday()
            miles = (a.distance_m or 0) / 1609.344
            name_lower = (a.name or "").lower()
            
            day_counts[day]["runs"] += 1
            
            if miles >= 15:
                day_counts[day]["long"] += 1
            
            if any(kw in name_lower for kw in ["tempo", "threshold", "interval", "speed"]):
                day_counts[day]["quality"] += 1
        
        # Find most common long run day
        long_day = max(range(7), key=lambda d: day_counts[d]["long"])
        quality_day = max(range(7), key=lambda d: day_counts[d]["quality"])
        
        # Find rest days (days with fewest runs)
        run_counts = [(d, day_counts[d]["runs"]) for d in range(7)]
        run_counts.sort(key=lambda x: x[1])
        rest_days = [d for d, c in run_counts[:2] if c < run_counts[3][1] * 0.5]
        
        return {
            "long_run_day": long_day if day_counts[long_day]["long"] >= 5 else None,
            "quality_day": quality_day if day_counts[quality_day]["quality"] >= 5 else None,
            "rest_days": rest_days
        }
    
    def _project_recovery_time(self, current_ctl: float, peak_ctl: float, 
                              tau1: float, target_pct: float) -> int:
        """Project weeks to recover target percentage of peak CTL."""
        if current_ctl >= peak_ctl * target_pct:
            return 0
        
        target_ctl = peak_ctl * target_pct
        gap = target_ctl - current_ctl
        
        # CTL builds at roughly (1 - e^(-t/τ1)) of the gap per week
        # Solve for t: target = current + gap * (1 - e^(-t/τ1))
        # Simplification: assume linear-ish recovery at rate gap/τ1 per week
        
        import math
        
        # Weeks = τ1 * ln((peak - current) / (peak - target))
        if peak_ctl > target_ctl and peak_ctl > current_ctl:
            weeks = tau1 / 7 * math.log((peak_ctl - current_ctl) / (peak_ctl - target_ctl))
            return max(1, int(weeks))
        
        return int(gap / (peak_ctl / tau1 * 7))
    
    def _project_race_readiness(self, current_ctl: float, peak_ctl: float,
                                tau1: float, experience: ExperienceLevel) -> int:
        """Project weeks to be race-ready."""
        # Race readiness depends on experience
        # Experienced athletes can race at 70% of peak CTL
        # Beginners need closer to 90%
        
        thresholds = {
            ExperienceLevel.ELITE: 0.70,
            ExperienceLevel.EXPERIENCED: 0.75,
            ExperienceLevel.INTERMEDIATE: 0.80,
            ExperienceLevel.BEGINNER: 0.85
        }
        
        return self._project_recovery_time(
            current_ctl, peak_ctl, tau1, thresholds[experience]
        )
    
    def _weeks_since_peak(self, activities: List, peak_weekly: float) -> int:
        """Find weeks since last peak-volume week."""
        today = date.today()
        
        weekly_miles = {}
        for a in activities:
            week_start = a.start_time.date() - timedelta(days=a.start_time.weekday())
            if week_start not in weekly_miles:
                weekly_miles[week_start] = 0
            weekly_miles[week_start] += (a.distance_m or 0) / 1609.344
        
        for week in sorted(weekly_miles.keys(), reverse=True):
            if weekly_miles[week] >= peak_weekly * 0.9:
                return (today - week).days // 7
        
        return 52  # Default to a year if no peak found
    
    def _default_fitness_bank(self, athlete_id: str) -> FitnessBank:
        """Return default fitness bank for athlete with no data."""
        return FitnessBank(
            athlete_id=athlete_id,
            peak_weekly_miles=30.0,
            peak_monthly_miles=120.0,
            peak_long_run_miles=12.0,
            peak_mp_long_run_miles=0.0,
            peak_threshold_miles=5.0,
            peak_ctl=40.0,
            race_performances=[],
            best_vdot=40.0,
            best_race=None,
            current_weekly_miles=0.0,
            current_ctl=30.0,
            current_atl=25.0,
            weeks_since_peak=0,
            current_long_run_miles=0.0,
            average_long_run_miles=0.0,
            tau1=42.0,
            tau2=7.0,
            experience_level=ExperienceLevel.BEGINNER,
            constraint_type=ConstraintType.NONE,
            constraint_details=None,
            is_returning_from_break=False,
            typical_long_run_day=6,
            typical_quality_day=3,
            typical_rest_days=[0, 4],
            weeks_to_80pct_ctl=0,
            weeks_to_race_ready=0,
            sustainable_peak_weekly=25.0
        )


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def get_fitness_bank(athlete_id: UUID, db: Session) -> FitnessBank:
    """Get athlete's fitness bank."""
    calculator = FitnessBankCalculator(db)
    return calculator.calculate(athlete_id)
