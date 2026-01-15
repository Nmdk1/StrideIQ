"""
Optimal Load Calculator

Calculates optimal training load trajectory to maximize race-day fitness.

Given:
- Current fitness (CTL) and fatigue (ATL)
- Race date
- Target race-day form (TSB)
- Individual model parameters (τ1, τ2)
- Athlete's sustainable load range

Outputs:
- Week-by-week TSS targets
- Personalized taper structure
- Predicted race-day state

ADR-022: Individual Performance Model for Plan Generation
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional, Tuple
from uuid import UUID
from enum import Enum
import math
import logging

from sqlalchemy.orm import Session

from services.individual_performance_model import (
    BanisterModel, 
    get_or_calibrate_model,
    ModelConfidence,
    DEFAULT_TAU1,
    DEFAULT_TAU2
)

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

class TrainingPhase(str, Enum):
    """Training phases for load prescription."""
    BASE = "base"
    BUILD = "build"
    PEAK = "peak"
    TAPER = "taper"


# Default targets
DEFAULT_TARGET_TSB = 15.0  # Race-ready form
DEFAULT_MIN_TSS_PCT = 0.3  # Minimum as % of max sustainable
DEFAULT_CUTBACK_FREQUENCY = 4  # Every Nth week
DEFAULT_CUTBACK_REDUCTION = 0.70  # 30% reduction


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class WeeklyLoadTarget:
    """Target training load for a single week."""
    week_number: int
    start_date: date
    end_date: date
    target_tss: float
    phase: TrainingPhase
    is_cutback: bool = False
    notes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "week_number": self.week_number,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "target_tss": round(self.target_tss, 0),
            "phase": self.phase.value,
            "is_cutback": self.is_cutback,
            "notes": self.notes
        }


@dataclass
class LoadTrajectory:
    """Complete training load trajectory to race."""
    athlete_id: str
    race_date: date
    weeks: List[WeeklyLoadTarget]
    
    # Projections
    projected_race_day_ctl: float
    projected_race_day_atl: float
    projected_race_day_tsb: float
    
    # Model used
    model_confidence: ModelConfidence
    tau1: float
    tau2: float
    
    # Totals
    total_weeks: int
    total_planned_tss: float
    taper_start_week: int
    
    def to_dict(self) -> Dict:
        return {
            "athlete_id": self.athlete_id,
            "race_date": self.race_date.isoformat(),
            "weeks": [w.to_dict() for w in self.weeks],
            "projections": {
                "race_day_ctl": round(self.projected_race_day_ctl, 1),
                "race_day_atl": round(self.projected_race_day_atl, 1),
                "race_day_tsb": round(self.projected_race_day_tsb, 1)
            },
            "model": {
                "confidence": self.model_confidence.value,
                "tau1": round(self.tau1, 1),
                "tau2": round(self.tau2, 1)
            },
            "summary": {
                "total_weeks": self.total_weeks,
                "total_planned_tss": round(self.total_planned_tss, 0),
                "taper_start_week": self.taper_start_week
            }
        }


@dataclass
class TaperPlan:
    """Personalized taper plan from pre-race fingerprint."""
    taper_start_date: date
    race_date: date
    taper_days: int
    last_hard_workout_date: date
    
    # Weekly structure
    weeks: List[WeeklyLoadTarget]
    
    # Targets from fingerprint
    target_tsb: float
    target_days_rest: int
    
    # Counter-conventional notes
    notes: List[str] = field(default_factory=list)
    
    # Confidence
    fingerprint_confidence: str = "moderate"
    
    def to_dict(self) -> Dict:
        return {
            "taper_start_date": self.taper_start_date.isoformat(),
            "race_date": self.race_date.isoformat(),
            "taper_days": self.taper_days,
            "last_hard_workout_date": self.last_hard_workout_date.isoformat(),
            "weeks": [w.to_dict() for w in self.weeks],
            "targets": {
                "tsb": round(self.target_tsb, 1),
                "days_rest": self.target_days_rest
            },
            "notes": self.notes,
            "fingerprint_confidence": self.fingerprint_confidence
        }


# =============================================================================
# OPTIMAL LOAD CALCULATOR
# =============================================================================

class OptimalLoadCalculator:
    """
    Calculates optimal training load trajectory.
    
    Uses individual model parameters to prescribe week-by-week TSS
    that maximizes race-day fitness while hitting target form.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def calculate_trajectory(
        self,
        athlete_id: UUID,
        race_date: date,
        current_ctl: float,
        current_atl: float,
        target_tsb: Optional[float] = None,
        max_weekly_tss: Optional[float] = None,
        min_weekly_tss: Optional[float] = None
    ) -> LoadTrajectory:
        """
        Calculate optimal load trajectory to race day.
        
        Args:
            athlete_id: Athlete UUID
            race_date: Target race date
            current_ctl: Current Chronic Training Load
            current_atl: Current Acute Training Load
            target_tsb: Target race-day TSB (from fingerprint or default)
            max_weekly_tss: Maximum sustainable weekly TSS
            min_weekly_tss: Minimum weekly TSS for maintenance
            
        Returns:
            LoadTrajectory with week-by-week targets
        """
        # Get calibrated model
        model = get_or_calibrate_model(athlete_id, self.db)
        
        # Set defaults if not provided
        if target_tsb is None:
            target_tsb = self._get_target_tsb_from_fingerprint(athlete_id)
        
        if max_weekly_tss is None:
            max_weekly_tss = self._estimate_max_sustainable_tss(athlete_id)
        
        if min_weekly_tss is None:
            min_weekly_tss = max_weekly_tss * DEFAULT_MIN_TSS_PCT
        
        # Calculate weeks to race
        today = date.today()
        days_to_race = (race_date - today).days
        weeks_to_race = max(1, days_to_race // 7)
        
        if weeks_to_race < 2:
            # Too close to race - minimal plan
            return self._create_minimal_trajectory(
                athlete_id, model, race_date, current_ctl, current_atl
            )
        
        # Calculate taper length from model
        taper_weeks = self._calculate_taper_weeks(model, current_ctl, current_atl, target_tsb)
        
        # Build phase weeks
        build_weeks = max(1, weeks_to_race - taper_weeks)
        
        # ========================================
        # CRITICAL: Calculate weeks BACKWARDS from race date
        # The race must fall on the final day (Sunday) of the last week
        # ========================================
        # Find what day of week race_date falls on (0 = Monday, 6 = Sunday)
        race_day_of_week = race_date.weekday()
        
        # Race week should start on Monday before race
        # If race is Sunday (6), week starts 6 days before
        # If race is Saturday (5), week starts 5 days before, etc.
        race_week_start = race_date - timedelta(days=race_day_of_week)
        
        # Calculate first week start by going back (weeks_to_race - 1) weeks from race week
        first_week_start = race_week_start - timedelta(weeks=weeks_to_race - 1)
        
        # Ensure first week starts on or after today
        if first_week_start < today:
            first_week_start = today - timedelta(days=today.weekday())  # Start of current week
        
        # Generate week-by-week targets
        weeks = []
        week_start = first_week_start
        ctl = current_ctl
        atl = current_atl
        
        # Build phase
        for week_num in range(1, build_weeks + 1):
            is_cutback = (week_num % DEFAULT_CUTBACK_FREQUENCY == 0)
            
            if is_cutback:
                weekly_tss = max_weekly_tss * DEFAULT_CUTBACK_REDUCTION
                phase = TrainingPhase.BUILD
                notes = ["Cutback week: absorb accumulated training"]
            else:
                # Progressive build toward peak
                progression = min(1.0, 0.8 + 0.05 * week_num)
                weekly_tss = max_weekly_tss * progression
                phase = TrainingPhase.BUILD if week_num > 2 else TrainingPhase.BASE
                notes = []
            
            week_end = week_start + timedelta(days=6)
            
            weeks.append(WeeklyLoadTarget(
                week_number=week_num,
                start_date=week_start,
                end_date=week_end,
                target_tss=weekly_tss,
                phase=phase,
                is_cutback=is_cutback,
                notes=notes
            ))
            
            # Update CTL/ATL projection
            ctl, atl = self._project_week(ctl, atl, weekly_tss, model)
            week_start = week_end + timedelta(days=1)
        
        # Peak week (if time allows)
        if build_weeks >= 3:
            weeks[-1].phase = TrainingPhase.PEAK
            weeks[-1].notes.append("Peak week: maintain volume, sharpen")
        
        # Taper phase
        taper_trajectory = self._generate_taper(
            model, ctl, atl, target_tsb, taper_weeks, week_start, build_weeks
        )
        weeks.extend(taper_trajectory)
        
        # Final projections
        for week in taper_trajectory:
            ctl, atl = self._project_week(ctl, atl, week.target_tss, model)
        
        # Calculate totals
        total_tss = sum(w.target_tss for w in weeks)
        
        return LoadTrajectory(
            athlete_id=str(athlete_id),
            race_date=race_date,
            weeks=weeks,
            projected_race_day_ctl=ctl,
            projected_race_day_atl=atl,
            projected_race_day_tsb=ctl - atl,
            model_confidence=model.confidence,
            tau1=model.tau1,
            tau2=model.tau2,
            total_weeks=len(weeks),
            total_planned_tss=total_tss,
            taper_start_week=build_weeks + 1
        )
    
    def calculate_personalized_taper(
        self,
        athlete_id: UUID,
        race_date: date,
        current_ctl: float,
        current_atl: float
    ) -> TaperPlan:
        """
        Calculate personalized taper from pre-race fingerprint.
        
        Uses athlete's optimal pre-race state to calculate exact taper.
        """
        from services.pre_race_fingerprinting import generate_readiness_profile
        
        # Get calibrated model
        model = get_or_calibrate_model(athlete_id, self.db)
        
        # Get pre-race fingerprint
        try:
            fingerprint = generate_readiness_profile(str(athlete_id), self.db)
            target_tsb = self._extract_target_tsb(fingerprint)
            target_days_rest = self._extract_target_days_rest(fingerprint)
            counter_notes = self._extract_counter_conventional_notes(fingerprint)
            fp_confidence = fingerprint.confidence_level
        except Exception as e:
            logger.warning(f"Could not get fingerprint for {athlete_id}: {e}")
            target_tsb = DEFAULT_TARGET_TSB
            target_days_rest = 3
            counter_notes = []
            fp_confidence = "low"
        
        # Calculate taper days needed
        taper_days = model.calculate_optimal_taper_days()
        
        # Adjust based on target TSB
        days_needed = self._calculate_days_to_target_tsb(
            model, current_ctl, current_atl, target_tsb
        )
        taper_days = max(taper_days, days_needed)
        
        # Calculate dates
        taper_start = race_date - timedelta(days=taper_days)
        last_hard = race_date - timedelta(days=target_days_rest)
        
        # Generate taper week structure
        taper_weeks = (taper_days + 6) // 7
        weeks = self._generate_taper(
            model, current_ctl, current_atl, target_tsb, 
            taper_weeks, taper_start, week_offset=0
        )
        
        notes = [
            f"Taper designed to hit TSB {target_tsb:.0f} by race day.",
            f"Last hard workout: {last_hard.strftime('%B %d')} ({target_days_rest} days before race)."
        ]
        notes.extend(counter_notes)
        
        return TaperPlan(
            taper_start_date=taper_start,
            race_date=race_date,
            taper_days=taper_days,
            last_hard_workout_date=last_hard,
            weeks=weeks,
            target_tsb=target_tsb,
            target_days_rest=target_days_rest,
            notes=notes,
            fingerprint_confidence=fp_confidence
        )
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _get_target_tsb_from_fingerprint(self, athlete_id: UUID) -> float:
        """Get target TSB from pre-race fingerprint if available."""
        try:
            from services.pre_race_fingerprinting import generate_readiness_profile
            fingerprint = generate_readiness_profile(str(athlete_id), self.db)
            return self._extract_target_tsb(fingerprint)
        except Exception:
            return DEFAULT_TARGET_TSB
    
    def _extract_target_tsb(self, fingerprint) -> float:
        """Extract target TSB from fingerprint optimal ranges."""
        if hasattr(fingerprint, 'optimal_ranges') and 'TSB' in fingerprint.optimal_ranges:
            tsb_range = fingerprint.optimal_ranges['TSB']
            return (tsb_range[0] + tsb_range[1]) / 2
        return DEFAULT_TARGET_TSB
    
    def _extract_target_days_rest(self, fingerprint) -> int:
        """Extract target days since hard workout from fingerprint."""
        if hasattr(fingerprint, 'optimal_ranges'):
            if 'Days Since Hard Workout' in fingerprint.optimal_ranges:
                range_ = fingerprint.optimal_ranges['Days Since Hard Workout']
                return int((range_[0] + range_[1]) / 2)
        return 3  # Default
    
    def _extract_counter_conventional_notes(self, fingerprint) -> List[str]:
        """Extract counter-conventional findings from fingerprint."""
        notes = []
        if hasattr(fingerprint, 'features'):
            for feature in fingerprint.features:
                if feature.is_significant and feature.pattern_type.value == 'inverted':
                    notes.append(f"Your data shows: {feature.insight_text}")
        return notes
    
    def _estimate_max_sustainable_tss(self, athlete_id: UUID) -> float:
        """
        Estimate max sustainable weekly TSS from training history.
        
        CRITICAL: Look at ESTABLISHED baseline (8-12 months), not just recent weeks.
        An injured athlete returning has low recent volume but high baseline.
        
        Strategy:
        1. Look back 12 months for established baseline
        2. Also check recent 4-6 weeks for current state
        3. If recent << baseline: athlete is returning from injury/break
        4. Target should be the BASELINE, not the current reduced state
        """
        from models import Activity, Athlete
        from services.training_load import TrainingLoadCalculator

        end_date = date.today()
        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        
        if not athlete:
            return 400  # Default moderate TSS

        calculator = TrainingLoadCalculator(self.db)

        # ========================================
        # Get FULL YEAR of training history
        # ========================================
        full_year_start = end_date - timedelta(days=365)
        
        all_activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= datetime.combine(full_year_start, datetime.min.time()),
            Activity.sport.ilike("run")
        ).all()

        if not all_activities:
            return 400

        # Calculate weekly TSS for entire year
        weekly_tss = {}
        for activity in all_activities:
            week_start = activity.start_time.date() - timedelta(days=activity.start_time.weekday())
            try:
                stress = calculator.calculate_workout_tss(activity, athlete)
                if week_start not in weekly_tss:
                    weekly_tss[week_start] = 0
                weekly_tss[week_start] += stress.tss
            except Exception:
                continue

        if not weekly_tss:
            return 400

        # ========================================
        # Split into BASELINE (3-12 months ago) vs RECENT (last 6 weeks)
        # ========================================
        recent_cutoff = end_date - timedelta(days=42)  # 6 weeks
        baseline_start = end_date - timedelta(days=365)
        baseline_end = end_date - timedelta(days=90)  # 3-12 months ago

        baseline_weeks = []
        recent_weeks = []

        for week_start, tss in weekly_tss.items():
            if baseline_start <= week_start <= baseline_end:
                baseline_weeks.append(tss)
            elif week_start >= recent_cutoff:
                recent_weeks.append(tss)

        # ========================================
        # Determine ESTABLISHED baseline
        # ========================================
        if baseline_weeks:
            # Use 75th percentile of baseline - their "normal" heavy weeks
            baseline_weeks_sorted = sorted(baseline_weeks)
            p75_idx = int(len(baseline_weeks_sorted) * 0.75)
            established_baseline = baseline_weeks_sorted[min(p75_idx, len(baseline_weeks_sorted) - 1)]
        else:
            # No baseline data - use all available data
            all_weeks_sorted = sorted(weekly_tss.values())
            p75_idx = int(len(all_weeks_sorted) * 0.75)
            established_baseline = all_weeks_sorted[min(p75_idx, len(all_weeks_sorted) - 1)]

        # ========================================
        # Detect injury/break and adjust target
        # ========================================
        if recent_weeks:
            recent_avg = sum(recent_weeks) / len(recent_weeks)
            
            # If recent is <50% of baseline, athlete is returning from break
            if recent_avg < established_baseline * 0.5:
                logger.info(
                    f"Athlete {athlete_id} returning from break: "
                    f"recent avg {recent_avg:.0f} TSS vs baseline {established_baseline:.0f} TSS"
                )
                # Target is the BASELINE (what they CAN do), not current (what they're doing)
                # Plan will build back up to this
                return established_baseline
            else:
                # Training consistently - use current sustainable level
                return max(recent_avg, established_baseline * 0.8)
        
        return established_baseline
    
    def _calculate_taper_weeks(
        self,
        model: BanisterModel,
        current_ctl: float,
        current_atl: float,
        target_tsb: float
    ) -> int:
        """Calculate taper weeks needed."""
        taper_days = model.calculate_optimal_taper_days()
        days_to_target = self._calculate_days_to_target_tsb(
            model, current_ctl, current_atl, target_tsb
        )
        return max(2, (max(taper_days, days_to_target) + 6) // 7)
    
    def _calculate_days_to_target_tsb(
        self,
        model: BanisterModel,
        current_ctl: float,
        current_atl: float,
        target_tsb: float
    ) -> int:
        """Calculate days of zero TSS needed to hit target TSB."""
        ctl = current_ctl
        atl = current_atl
        
        decay1 = math.exp(-1.0 / model.tau1)
        decay2 = math.exp(-1.0 / model.tau2)
        
        for days in range(1, 35):
            ctl = ctl * decay1
            atl = atl * decay2
            if ctl - atl >= target_tsb:
                return days
        
        return 21  # Max reasonable taper
    
    def _project_week(
        self,
        current_ctl: float,
        current_atl: float,
        weekly_tss: float,
        model: BanisterModel
    ) -> Tuple[float, float]:
        """Project CTL/ATL after a week of training."""
        daily_tss = weekly_tss / 7
        
        decay1 = math.exp(-1.0 / model.tau1)
        decay2 = math.exp(-1.0 / model.tau2)
        
        ctl = current_ctl
        atl = current_atl
        
        for _ in range(7):
            ctl = ctl * decay1 + daily_tss * (1 - decay1)
            atl = atl * decay2 + daily_tss * (1 - decay2)
        
        return ctl, atl
    
    def _generate_taper(
        self,
        model: BanisterModel,
        start_ctl: float,
        start_atl: float,
        target_tsb: float,
        taper_weeks: int,
        taper_start: date,
        week_offset: int
    ) -> List[WeeklyLoadTarget]:
        """Generate taper week structure."""
        weeks = []
        
        # Calculate TSS reduction per week
        # Week 1: 60% of normal
        # Week 2: 40% of normal
        # Week 3 (if exists): 25% of normal
        
        # Estimate "normal" from current load
        current_weekly = (start_ctl + start_atl) / 2 * 7  # Rough estimate
        
        reductions = [0.60, 0.40, 0.25]  # Progressive reduction
        
        for i in range(taper_weeks):
            week_num = week_offset + i + 1
            week_start = taper_start + timedelta(days=i * 7)
            week_end = week_start + timedelta(days=6)
            
            reduction = reductions[min(i, len(reductions) - 1)]
            weekly_tss = current_weekly * reduction
            
            notes = []
            if i == 0:
                notes.append("Taper begins: reduce volume, maintain some intensity")
            elif i == taper_weeks - 1:
                notes.append("Race week: minimal training, stay sharp")
            
            weeks.append(WeeklyLoadTarget(
                week_number=week_num,
                start_date=week_start,
                end_date=week_end,
                target_tss=weekly_tss,
                phase=TrainingPhase.TAPER,
                is_cutback=False,
                notes=notes
            ))
        
        return weeks
    
    def _create_minimal_trajectory(
        self,
        athlete_id: UUID,
        model: BanisterModel,
        race_date: date,
        current_ctl: float,
        current_atl: float
    ) -> LoadTrajectory:
        """Create minimal trajectory when race is very close."""
        today = date.today()
        days_to_race = (race_date - today).days
        
        # Just taper
        week = WeeklyLoadTarget(
            week_number=1,
            start_date=today,
            end_date=race_date,
            target_tss=(current_ctl + current_atl) / 2 * 0.4,  # Light week
            phase=TrainingPhase.TAPER,
            is_cutback=False,
            notes=["Race imminent: light training only"]
        )
        
        return LoadTrajectory(
            athlete_id=str(athlete_id),
            race_date=race_date,
            weeks=[week],
            projected_race_day_ctl=current_ctl * 0.95,  # Slight decay
            projected_race_day_atl=current_atl * 0.7,   # Faster fatigue decay
            projected_race_day_tsb=current_ctl * 0.95 - current_atl * 0.7,
            model_confidence=model.confidence,
            tau1=model.tau1,
            tau2=model.tau2,
            total_weeks=1,
            total_planned_tss=week.target_tss,
            taper_start_week=1
        )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def calculate_optimal_trajectory(
    athlete_id: UUID,
    race_date: date,
    db: Session
) -> LoadTrajectory:
    """Calculate optimal load trajectory for athlete."""
    from services.training_load import TrainingLoadCalculator
    
    # Get current load
    calculator = TrainingLoadCalculator(db)
    current_load = calculator.calculate_training_load(athlete_id)
    
    # Calculate trajectory
    load_calc = OptimalLoadCalculator(db)
    return load_calc.calculate_trajectory(
        athlete_id=athlete_id,
        race_date=race_date,
        current_ctl=current_load.current_ctl,
        current_atl=current_load.current_atl
    )


def calculate_taper(
    athlete_id: UUID,
    race_date: date,
    db: Session
) -> TaperPlan:
    """Calculate personalized taper for athlete."""
    from services.training_load import TrainingLoadCalculator
    
    # Get current load
    calculator = TrainingLoadCalculator(db)
    current_load = calculator.calculate_training_load(athlete_id)
    
    # Calculate taper
    load_calc = OptimalLoadCalculator(db)
    return load_calc.calculate_personalized_taper(
        athlete_id=athlete_id,
        race_date=race_date,
        current_ctl=current_load.current_ctl,
        current_atl=current_load.current_atl
    )
