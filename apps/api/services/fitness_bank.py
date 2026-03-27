"""
Fitness Bank Framework (ADR-030)

The Fitness Bank tracks an athlete's PROVEN capabilities, not just current state.
This enables plans that target peak performance for experienced athletes 
returning from injury or reduced training.

Key Principle: The athlete's history IS the data. Generic plans fail because
they ignore what the athlete has already proven they can do.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from typing import List, Dict, Optional, Tuple
from uuid import UUID
import logging

from sqlalchemy.orm import Session
from services.mileage_aggregation import (
    compute_peak_and_current_weekly_miles,
    compute_recent_weekly_band,
    get_canonical_run_activities,
)
from services.race_signal_contract import (
    activity_is_authoritative_race,
    normalize_distance_alias,
)

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
    rpi: float
    conditions: Optional[str] = None  # "limping", "hot", "hilly", "perfect"
    confidence: float = 1.0           # Weight for this performance
    name: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "date": self.date.isoformat(),
            "distance": self.distance,
            "finish_time": self.finish_time_seconds,
            "pace_per_mile": round(self.pace_per_mile, 2),
            "rpi": round(self.rpi, 1),
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
    best_rpi: float
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
    recent_quality_sessions_28d: int = 0
    recent_8w_median_weekly_miles: float = 0.0
    recent_16w_p90_weekly_miles: float = 0.0
    recent_8w_p75_long_run_miles: float = 0.0
    recent_16w_p50_long_run_miles: float = 0.0
    recent_16w_run_count: int = 0
    last_complete_week_miles: float = 0.0
    peak_confidence: str = "medium"
    
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
                "avg_long_run": round(self.average_long_run_miles, 1),
                "quality_sessions_28d": int(self.recent_quality_sessions_28d),
            },
            "best_rpi": round(self.best_rpi, 1) if self.best_rpi is not None else None,
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
            },
            "volume_contract": {
                "recent_8w_median_weekly_miles": round(self.recent_8w_median_weekly_miles, 1),
                "recent_16w_p90_weekly_miles": round(self.recent_16w_p90_weekly_miles, 1),
                "recent_8w_p75_long_run_miles": round(self.recent_8w_p75_long_run_miles, 1),
                "recent_16w_p50_long_run_miles": round(self.recent_16w_p50_long_run_miles, 1),
                "recent_16w_run_count": int(self.recent_16w_run_count),
                "last_complete_week_miles": round(self.last_complete_week_miles, 1),
                "peak_confidence": self.peak_confidence,
            }
        }


# =============================================================================
# RPI CALCULATION
# =============================================================================

def calculate_rpi(distance_m: float, time_seconds: int) -> float:
    """
    Calculate RPI from race performance.
    
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
    
    # RPI = VO2 / %VO2max
    if pct_vo2max > 0:
        rpi = vo2 / pct_vo2max
    else:
        rpi = 0.0
    
    return max(20.0, min(85.0, rpi))  # Clamp to reasonable range


def rpi_equivalent_time(rpi: float, distance_m: float) -> int:
    """Calculate equivalent time for a distance given RPI."""
    
    # Binary search for time that gives this RPI at this distance
    low, high = 60, 36000  # 1 min to 10 hours
    
    for _ in range(50):
        mid = (low + high) // 2
        calc_rpi = calculate_rpi(distance_m, mid)
        
        if abs(calc_rpi - rpi) < 0.1:
            return mid
        elif calc_rpi > rpi:
            low = mid
        else:
            high = mid
    
    return mid


# =============================================================================
# CACHE ROUND-TRIP HELPERS
# =============================================================================

def _fitness_bank_to_dict(bank: "FitnessBank") -> dict:
    """Serialize FitnessBank to a JSON-safe dict for Redis caching."""
    def _race(r: "RacePerformance") -> dict:
        return {
            "date": r.date.isoformat() if r.date else None,
            "distance": r.distance,
            "distance_m": r.distance_m,
            "finish_time_seconds": r.finish_time_seconds,
            "pace_per_mile": r.pace_per_mile,
            "rpi": r.rpi,
            "conditions": r.conditions,
            "confidence": r.confidence,
            "name": r.name,
        }

    return {
        "athlete_id": bank.athlete_id,
        "peak_weekly_miles": bank.peak_weekly_miles,
        "peak_monthly_miles": bank.peak_monthly_miles,
        "peak_long_run_miles": bank.peak_long_run_miles,
        "peak_mp_long_run_miles": bank.peak_mp_long_run_miles,
        "peak_threshold_miles": bank.peak_threshold_miles,
        "peak_ctl": bank.peak_ctl,
        "race_performances": [_race(r) for r in bank.race_performances],
        "best_rpi": bank.best_rpi,
        "best_race": _race(bank.best_race) if bank.best_race else None,
        "current_weekly_miles": bank.current_weekly_miles,
        "current_ctl": bank.current_ctl,
        "current_atl": bank.current_atl,
        "weeks_since_peak": bank.weeks_since_peak,
        "current_long_run_miles": bank.current_long_run_miles,
        "average_long_run_miles": bank.average_long_run_miles,
        "tau1": bank.tau1,
        "tau2": bank.tau2,
        "experience_level": bank.experience_level.value,
        "constraint_type": bank.constraint_type.value,
        "constraint_details": bank.constraint_details,
        "is_returning_from_break": bank.is_returning_from_break,
        "typical_long_run_day": bank.typical_long_run_day,
        "typical_quality_day": bank.typical_quality_day,
        "typical_rest_days": bank.typical_rest_days,
        "weeks_to_80pct_ctl": bank.weeks_to_80pct_ctl,
        "weeks_to_race_ready": bank.weeks_to_race_ready,
        "sustainable_peak_weekly": bank.sustainable_peak_weekly,
        "recent_quality_sessions_28d": bank.recent_quality_sessions_28d,
        "recent_8w_median_weekly_miles": bank.recent_8w_median_weekly_miles,
        "recent_16w_p90_weekly_miles": bank.recent_16w_p90_weekly_miles,
        "recent_8w_p75_long_run_miles": bank.recent_8w_p75_long_run_miles,
        "recent_16w_p50_long_run_miles": bank.recent_16w_p50_long_run_miles,
        "recent_16w_run_count": bank.recent_16w_run_count,
        "last_complete_week_miles": bank.last_complete_week_miles,
        "peak_confidence": bank.peak_confidence,
    }


def _fitness_bank_from_dict(d: dict) -> "FitnessBank":
    """Reconstruct FitnessBank from a cached dict."""
    def _race(r: dict) -> "RacePerformance":
        raw_date = r.get("date")
        race_date = date.fromisoformat(raw_date) if raw_date else date.today()
        return RacePerformance(
            date=race_date,
            distance=r.get("distance", ""),
            distance_m=float(r.get("distance_m", 0)),
            finish_time_seconds=int(r.get("finish_time_seconds", 0)),
            pace_per_mile=float(r.get("pace_per_mile", 0)),
            rpi=float(r.get("rpi", 0)),
            conditions=r.get("conditions"),
            confidence=float(r.get("confidence", 1.0)),
            name=r.get("name"),
        )

    return FitnessBank(
        athlete_id=d["athlete_id"],
        peak_weekly_miles=float(d["peak_weekly_miles"]),
        peak_monthly_miles=float(d["peak_monthly_miles"]),
        peak_long_run_miles=float(d["peak_long_run_miles"]),
        peak_mp_long_run_miles=float(d["peak_mp_long_run_miles"]),
        peak_threshold_miles=float(d["peak_threshold_miles"]),
        peak_ctl=float(d["peak_ctl"]),
        race_performances=[_race(r) for r in d.get("race_performances", [])],
        best_rpi=float(d["best_rpi"]),
        best_race=_race(d["best_race"]) if d.get("best_race") else None,
        current_weekly_miles=float(d["current_weekly_miles"]),
        current_ctl=float(d["current_ctl"]),
        current_atl=float(d["current_atl"]),
        weeks_since_peak=int(d["weeks_since_peak"]),
        current_long_run_miles=float(d["current_long_run_miles"]),
        average_long_run_miles=float(d["average_long_run_miles"]),
        tau1=float(d["tau1"]),
        tau2=float(d["tau2"]),
        experience_level=ExperienceLevel(d["experience_level"]),
        constraint_type=ConstraintType(d["constraint_type"]),
        constraint_details=d.get("constraint_details"),
        is_returning_from_break=bool(d["is_returning_from_break"]),
        typical_long_run_day=d.get("typical_long_run_day"),
        typical_quality_day=d.get("typical_quality_day"),
        typical_rest_days=d.get("typical_rest_days", []),
        weeks_to_80pct_ctl=int(d["weeks_to_80pct_ctl"]),
        weeks_to_race_ready=int(d["weeks_to_race_ready"]),
        sustainable_peak_weekly=float(d["sustainable_peak_weekly"]),
        recent_quality_sessions_28d=int(d.get("recent_quality_sessions_28d", 0)),
        recent_8w_median_weekly_miles=float(d.get("recent_8w_median_weekly_miles", 0.0)),
        recent_16w_p90_weekly_miles=float(d.get("recent_16w_p90_weekly_miles", 0.0)),
        recent_8w_p75_long_run_miles=float(d.get("recent_8w_p75_long_run_miles", 0.0)),
        recent_16w_p50_long_run_miles=float(d.get("recent_16w_p50_long_run_miles", 0.0)),
        recent_16w_run_count=int(d.get("recent_16w_run_count", 0)),
        last_complete_week_miles=float(d.get("last_complete_week_miles", 0.0)),
        peak_confidence=str(d.get("peak_confidence", "medium")),
    )


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
        Cached in Redis for 15 minutes. Invalidated on activity write.
        """
        from core.cache import get_cache, set_cache
        _cache_key = f"fitness_bank:{athlete_id}"
        _cached = get_cache(_cache_key)
        if _cached is not None:
            try:
                return _fitness_bank_from_dict(_cached)
            except Exception:
                pass  # Cache corruption — recompute

        from services.individual_performance_model import get_or_calibrate_model
        from services.training_load import TrainingLoadCalculator

        # Use trusted DB duplicate flags.  The retroactive scanner (duplicate_scanner.py)
        # and the live ingestion path (strava_tasks.py / garmin tasks) both maintain
        # is_duplicate correctly with an 8-hour cross-provider window.
        activities, dedupe_meta = get_canonical_run_activities(
            athlete_id,
            self.db,
            require_trusted_duplicate_flags=True,
        )
        if dedupe_meta.get("dedupe_pairs_collapsed", 0) > 0:
            logger.warning(
                "FitnessBank fallback dedupe used for athlete %s: collapsed=%s source=%s output=%s",
                athlete_id,
                dedupe_meta["dedupe_pairs_collapsed"],
                dedupe_meta["source_count"],
                dedupe_meta["output_count"],
            )
        
        if not activities:
            return self._default_fitness_bank(str(athlete_id))
        
        # Get calibrated model for τ values
        try:
            model = get_or_calibrate_model(athlete_id, self.db)
            tau1 = model.tau1
            tau2 = model.tau2
        except Exception as e:
            # Important: if the DB raised (e.g. missing table), the SQLAlchemy
            # session is left in an aborted transaction state until rollback.
            try:
                self.db.rollback()
            except Exception:
                pass
            logger.warning(f"Could not get model: {e}")
            tau1, tau2 = 42.0, 7.0
        
        # Get current CTL/ATL
        try:
            load_calc = TrainingLoadCalculator(self.db)
            current_load = load_calc.calculate_training_load(athlete_id)
            current_ctl = current_load.current_ctl
            current_atl = current_load.current_atl
        except Exception as e:
            # Same rule: DB exceptions require rollback before any further queries.
            try:
                self.db.rollback()
            except Exception:
                pass
            logger.warning(f"Could not get current load: {e}")
            current_ctl, current_atl = 50.0, 40.0
        
        # Calculate peak capabilities
        peaks = self._calculate_peak_capabilities(activities)
        canonical_peak_weekly, canonical_current_weekly, last_complete_week = compute_peak_and_current_weekly_miles(activities)
        recent_8w_median, recent_16w_p90 = compute_recent_weekly_band(activities)
        if canonical_peak_weekly > 0:
            peaks["peak_weekly"] = canonical_peak_weekly
        peak_confidence = self._assess_peak_confidence(
            peak_weekly=peaks["peak_weekly"],
            recent_8w_median=recent_8w_median,
            recent_16w_p90=recent_16w_p90,
            dedupe_meta=dedupe_meta,
        )
        
        # Extract race performances
        self._sync_anchor_from_authoritative_race_signals(athlete_id=athlete_id, activities=activities)
        races = self._extract_race_performances(activities)
        best_rpi, best_race = self._find_best_race(races)
        
        # Calculate current weekly volume from canonical utility
        current_weekly = canonical_current_weekly
        
        # Determine experience level
        experience = self._determine_experience(peaks, races)
        
        # Detect constraints
        constraint_type, constraint_details, is_returning = self._detect_constraint(
            peaks, current_weekly, activities, races
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
        p75_long_8w, p50_long_16w, run_count_16w = self._calculate_recent_long_run_floor_metrics(activities)
        recent_quality_sessions = self._calculate_recent_quality_sessions(activities)
        
        result = FitnessBank(
            athlete_id=str(athlete_id),
            peak_weekly_miles=peaks["peak_weekly"],
            peak_monthly_miles=peaks["peak_monthly"],
            peak_long_run_miles=peaks["peak_long_run"],
            peak_mp_long_run_miles=peaks["peak_mp_long_run"],
            peak_threshold_miles=peaks["peak_threshold"],
            peak_ctl=peaks["peak_ctl"],
            race_performances=races,
            best_rpi=best_rpi,
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
            sustainable_peak_weekly=sustainable,
            recent_quality_sessions_28d=recent_quality_sessions,
            recent_8w_median_weekly_miles=recent_8w_median,
            recent_16w_p90_weekly_miles=recent_16w_p90,
            recent_8w_p75_long_run_miles=p75_long_8w,
            recent_16w_p50_long_run_miles=p50_long_16w,
            recent_16w_run_count=run_count_16w,
            last_complete_week_miles=last_complete_week,
            peak_confidence=peak_confidence,
        )

        # Apply athlete overrides.  These take absolute precedence —
        # the athlete knows context the algorithm can't see.
        result = self._apply_overrides(athlete_id, result)

        try:
            set_cache(_cache_key, _fitness_bank_to_dict(result), ttl=900)
        except Exception:
            pass  # Non-critical — cache write failure must not break the response
        return result

    def _apply_overrides(self, athlete_id: UUID, bank: FitnessBank) -> FitnessBank:
        """Apply athlete-specified overrides to the computed fitness bank."""
        try:
            from models import AthleteOverride
            row = self.db.query(AthleteOverride).filter(
                AthleteOverride.athlete_id == athlete_id
            ).first()
            if row is None:
                return bank
            if row.peak_weekly_miles is not None:
                logger.info("Override: peak_weekly_miles %.1f → %.1f", bank.peak_weekly_miles, row.peak_weekly_miles)
                bank.peak_weekly_miles = row.peak_weekly_miles
            if row.peak_long_run_miles is not None:
                logger.info("Override: peak_long_run_miles %.1f → %.1f", bank.peak_long_run_miles, row.peak_long_run_miles)
                bank.peak_long_run_miles = row.peak_long_run_miles
            if row.rpi is not None:
                logger.info("Override: best_rpi %.2f → %.2f", bank.best_rpi, row.rpi)
                bank.best_rpi = row.rpi
        except Exception as ex:
            logger.warning("Could not apply athlete overrides: %s", ex)
        return bank

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
        """Extract race performances from authoritative race signals only."""
        races = []
        
        for a in activities:
            miles = (a.distance_m or 0) / 1609.344
            duration_sec = a.duration_s or 0
            
            if duration_sec <= 0 or miles <= 0:
                continue
            
            if not activity_is_authoritative_race(a):
                continue

            pace = (duration_sec / 60) / miles
            name_lower = (a.name or "").lower()
            distance_type = self._infer_distance_type(miles)
            conditions = None

            # Check for condition notes
            if "limp" in name_lower or "injured" in name_lower:
                conditions = "limping"
            elif "hot" in name_lower or "heat" in name_lower:
                conditions = "hot"
            elif "hill" in name_lower:
                conditions = "hilly"
            
            if distance_type:
                rpi = calculate_rpi(a.distance_m, duration_sec)
                
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
                    rpi=rpi,
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
        """
        Return the athlete's peak proven RPI and the race that established it.

        Uses the highest confidence-adjusted RPI from races in the last 24 months.
        Recency is NOT used to select or downgrade peak RPI — we want to know what
        the athlete has proven they can do, not what they did most recently.

        Races with confidence < 0.5 (e.g., race-day anomalies flagged by the system)
        or RPI < 35 (clearly not a race effort) are excluded from consideration.
        """
        if not races:
            return 45.0, None

        today = date.today()
        cutoff = today - timedelta(days=730)  # 24-month window

        valid = [
            r for r in races
            if r.rpi >= 35.0
            and r.confidence >= 0.5
            and r.date >= cutoff
        ]

        if not valid:
            # No valid races in window — fall back to any race above threshold
            valid = [r for r in races if r.rpi >= 35.0 and r.confidence >= 0.5]

        if not valid:
            return 45.0, None

        # Best race = highest confidence-adjusted RPI
        best_race = max(valid, key=lambda r: r.rpi * r.confidence)
        return best_race.rpi, best_race

    def _sync_anchor_from_authoritative_race_signals(self, athlete_id: UUID, activities: List) -> None:
        """
        Upsert one AthleteRaceResultAnchor row per distance key from authoritative races.

        WS-A spec: store the best result for each distance independently (10K, HM, marathon, etc.)
        so that pace prescriptions for each distance use the athlete's actual PR for that distance.

        Selection policy (per-distance schema):
        1) for each distance_key, prefer the fastest (lowest time_seconds) authoritative result,
        2) tie-break by confidence, then most recent date,
        3) never replace user/admin-entered anchors unless new evidence is strictly better.
        """
        from models import AthleteRaceResultAnchor

        candidates: Dict[str, list] = {}
        for a in activities:
            if not activity_is_authoritative_race(a):
                continue
            duration_sec = int(getattr(a, "duration_s", 0) or 0)
            distance_m = int(getattr(a, "distance_m", 0) or 0)
            if duration_sec <= 0 or distance_m <= 0:
                continue
            miles = distance_m / 1609.344
            distance_key = normalize_distance_alias(self._infer_distance_type(miles))
            race_date = a.start_time.date() if getattr(a, "start_time", None) is not None else None
            confidence = self._anchor_candidate_confidence(a)
            rpi = calculate_rpi(distance_m, duration_sec)
            candidates.setdefault(distance_key, []).append(
                {
                    "distance_key": distance_key,
                    "distance_meters": distance_m,
                    "time_seconds": duration_sec,
                    "race_date": race_date,
                    "confidence": confidence,
                    "rpi": rpi,
                }
            )

        if not candidates:
            return

        existing_rows = {
            r.distance_key: r
            for r in self.db.query(AthleteRaceResultAnchor)
            .filter(AthleteRaceResultAnchor.athlete_id == athlete_id)
            .all()
        }

        for distance_key, dist_candidates in candidates.items():
            qualified = [c for c in dist_candidates if c["confidence"] >= 0.7]
            if not qualified:
                continue
            best = sorted(
                qualified,
                key=lambda c: (
                    c["time_seconds"],          # fastest time is best (ascending)
                    -(c["confidence"]),          # higher confidence breaks ties (descending)
                ),
            )[0]

            current = existing_rows.get(distance_key)
            if current is None:
                new_row = AthleteRaceResultAnchor(
                    athlete_id=athlete_id,
                    distance_key=best["distance_key"],
                    distance_meters=best["distance_meters"],
                    time_seconds=best["time_seconds"],
                    race_date=best["race_date"],
                    source="import",
                )
                self.db.add(new_row)
            elif self._should_replace_existing_anchor(current, best):
                current.distance_key = best["distance_key"]
                current.distance_meters = best["distance_meters"]
                current.time_seconds = best["time_seconds"]
                current.race_date = best["race_date"]
                if current.source not in ("user", "admin"):
                    current.source = "import"

        self.db.flush()

    def _anchor_candidate_confidence(self, activity) -> float:
        if bool(getattr(activity, "user_verified_race", False)):
            return 1.0
        if str(getattr(activity, "workout_type", "") or "").strip().lower() in ("race", "race_effort"):
            return max(0.8, float(getattr(activity, "race_confidence", 0.0) or 0.0))
        return float(getattr(activity, "race_confidence", 0.0) or 0.0)

    def _should_replace_existing_anchor(self, existing, candidate: Dict[str, object]) -> bool:
        existing_distance_m = int(getattr(existing, "distance_meters", 0) or 0)
        existing_time = int(getattr(existing, "time_seconds", 0) or 0)
        if existing_distance_m <= 0 or existing_time <= 0:
            return True

        existing_rpi = calculate_rpi(existing_distance_m, existing_time)
        candidate_rpi = float(candidate["rpi"])
        existing_source = str(getattr(existing, "source", "") or "").strip().lower()
        if existing_source in ("user", "admin"):
            return candidate_rpi > existing_rpi + 0.15
        return candidate_rpi >= existing_rpi - 0.1
    
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
            - current_long_run: Max long run in last 4 weeks (non-race, ≤24mi)
            - average_long_run: Average of all long runs >= 10mi (or 90+ min)
        """
        today = date.today()
        four_weeks_ago = today - timedelta(days=28)
        
        recent_long_runs = []
        all_long_runs = []
        
        for a in activities:
            # Exclude race activities — a goal race is not a training long run.
            # Parity with load_context.py:is_activity_excluded_as_race_for_p4.
            wt = str(getattr(a, "workout_type", None) or "").lower()
            if wt == "race" or getattr(a, "is_race_candidate", False):
                continue
            miles = (a.distance_m or 0) / 1609.344
            # Any activity over 24 miles is not a training long run (our KB cap is
            # 22mi for marathon HIGH tier; 24mi for elite).  26+ mile activities are
            # almost always races (marathon / ultra) that were not tagged correctly.
            # Including them would inflate l30_floor and set an unreachable floor
            # for the athlete's next training block.
            if miles > 24.0:
                continue

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

    def _calculate_recent_long_run_floor_metrics(self, activities: List) -> Tuple[float, float, int]:
        """
        Return:
        - recent_8w_p75_long_run_miles
        - recent_16w_p50_long_run_miles
        - recent_16w_run_count
        """
        today = date.today()
        cutoff_8w = today - timedelta(weeks=8)
        cutoff_16w = today - timedelta(weeks=16)

        long_runs_8w: List[float] = []
        long_runs_16w: List[float] = []
        run_count_16w = 0

        for activity in activities:
            # Exclude race activities — goal races should not anchor the training floor.
            # Parity with load_context.py:is_activity_excluded_as_race_for_p4.
            wt = str(getattr(activity, "workout_type", None) or "").lower()
            if wt == "race" or getattr(activity, "is_race_candidate", False):
                continue

            activity_date = activity.start_time.date()
            miles = (activity.distance_m or 0) / 1609.344
            duration_min = (activity.duration_s or 0) / 60.0
            # Exclude >24-mile activities regardless of label (untagged marathon/ultra races).
            if miles > 24.0:
                continue
            if activity_date < cutoff_16w:
                continue
            run_count_16w += 1
            is_long_run = miles >= 10 or duration_min >= 90
            if is_long_run:
                long_runs_16w.append(miles)
                if activity_date >= cutoff_8w:
                    long_runs_8w.append(miles)

        def _percentile(values: List[float], pct: float) -> float:
            if not values:
                return 0.0
            s = sorted(values)
            if len(s) == 1:
                return s[0]
            idx = int(round((len(s) - 1) * pct))
            idx = max(0, min(len(s) - 1, idx))
            return s[idx]

        p75_8w = _percentile(long_runs_8w, 0.75)
        p50_16w = _percentile(long_runs_16w, 0.50)
        return p75_8w, p50_16w, run_count_16w

    def _calculate_recent_quality_sessions(self, activities: List) -> int:
        """Count quality sessions in the trailing 28 days."""
        today = date.today()
        cutoff = today - timedelta(days=28)
        count = 0
        for a in activities:
            if a.start_time.date() < cutoff:
                continue
            workout_type = (a.workout_type or "").lower()
            name_lower = (a.name or "").lower()
            if workout_type in ("interval", "intervals", "tempo", "threshold", "race_pace", "speed"):
                count += 1
                continue
            if any(k in name_lower for k in ("interval", "tempo", "threshold", "@ mp", "marathon pace", "track", "fartlek", "race")):
                count += 1
        return count
    
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
    
    def _has_recent_race(self, races: List[RacePerformance], days: int = 21) -> bool:
        cutoff = date.today() - timedelta(days=days)
        return any(r.date >= cutoff for r in races)

    def _detect_constraint(self, peaks: Dict, current_weekly: float,
                          activities: List, races: List[RacePerformance]) -> Tuple[ConstraintType, Optional[str], bool]:
        """Detect what's limiting the athlete."""
        peak_weekly = peaks["peak_weekly"]

        # Post-race recovery should never be misclassified as injury/detraining.
        if self._has_recent_race(races, days=21):
            return ConstraintType.NONE, None, False

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
            best_rpi=40.0,
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
            sustainable_peak_weekly=25.0,
            recent_quality_sessions_28d=0,
            recent_8w_median_weekly_miles=0.0,
            recent_16w_p90_weekly_miles=0.0,
            recent_8w_p75_long_run_miles=0.0,
            recent_16w_p50_long_run_miles=0.0,
            recent_16w_run_count=0,
            last_complete_week_miles=0.0,
            peak_confidence="low",
        )

    def _assess_peak_confidence(
        self,
        *,
        peak_weekly: float,
        recent_8w_median: float,
        recent_16w_p90: float,
        dedupe_meta: Dict[str, int],
    ) -> str:
        """
        Confidence heuristic for whether historical peak should drive planning.
        """
        if peak_weekly <= 0:
            return "low"

        if recent_16w_p90 <= 0 or recent_8w_median <= 0:
            return "medium"

        # Plausibility against recent operating band.
        if peak_weekly > recent_16w_p90 * 1.8:
            return "low"

        # If fallback dedupe still collapses many rows, reduce trust in raw peak.
        collapsed = int(dedupe_meta.get("dedupe_pairs_collapsed", 0) or 0)
        if collapsed >= 10 and peak_weekly > recent_16w_p90 * 1.4:
            return "low"

        if peak_weekly > recent_16w_p90 * 1.35:
            return "medium"

        return "high"


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def get_fitness_bank(athlete_id: UUID, db: Session) -> FitnessBank:
    """Get athlete's fitness bank."""
    calculator = FitnessBankCalculator(db)
    return calculator.calculate(athlete_id)


def sync_race_anchors_for_activities(
    athlete_id: UUID,
    activities: List,
    db: Session,
) -> None:
    """
    Public hook: sync AthleteRaceResultAnchor rows from a list of activities.

    Call this after any batch of activities is imported for an athlete so that
    race anchors are populated without requiring a full FitnessBank rebuild.
    Silently no-ops if no authoritative races are found in the list.
    """
    calc = FitnessBankCalculator(db)
    calc._sync_anchor_from_authoritative_race_signals(
        athlete_id=athlete_id,
        activities=activities,
    )
