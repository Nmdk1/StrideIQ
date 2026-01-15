"""
Model-Driven Plan Generator

Generates training plans from individual performance model.

NOT templates. NOT LLM-dependent. Pure calculation.

Flow:
1. Calibrate individual model (τ1, τ2, k1, k2)
2. Calculate optimal load trajectory (week-by-week TSS)
3. Calculate personalized taper (from fingerprint)
4. Convert TSS to mileage/intensity distribution
5. Apply decay profile (specific workout prescriptions)
6. Output: Personalized plan with predictions

ADR-022: Individual Performance Model for Plan Generation
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional, Any
from uuid import UUID
from enum import Enum
import math
import logging

from sqlalchemy.orm import Session

from services.individual_performance_model import (
    get_or_calibrate_model,
    BanisterModel,
    ModelConfidence
)
from services.optimal_load_calculator import (
    OptimalLoadCalculator,
    LoadTrajectory,
    TaperPlan,
    WeeklyLoadTarget,
    TrainingPhase
)
from services.race_predictor import (
    RacePredictor,
    RacePrediction
)
from services.vdot_calculator import calculate_training_paces

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

RACE_DISTANCES = {
    "5k": 5000,
    "10k": 10000,
    "half_marathon": 21097,
    "marathon": 42195
}

# TSS to mileage conversion (rough)
# Based on: 1 hour easy run ≈ 50 TSS, ~6-8 miles
TSS_TO_MILES_EASY = 0.14  # ~7 miles per 50 TSS
TSS_TO_MILES_QUALITY = 0.10  # Quality miles "cost" more TSS

# Distance-specific long run caps (miles)
# Source: PLAN_GENERATION_FRAMEWORK.md Rule B1, TRAINING_PHILOSOPHY.md Long Run
LONG_RUN_CAPS = {
    "5k": {"min": 6, "max": 12, "peak": 10},
    "10k": {"min": 8, "max": 14, "peak": 12},
    "half_marathon": {"min": 10, "max": 16, "peak": 14},
    "marathon": {"min": 14, "max": 22, "peak": 20}
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class DayPlan:
    """A single day's training plan."""
    date: date
    day_of_week: str
    workout_type: str
    name: str
    description: str
    target_tss: float
    target_miles: Optional[float] = None
    target_pace: Optional[str] = None
    intensity: str = "easy"
    notes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "date": self.date.isoformat(),
            "day_of_week": self.day_of_week,
            "workout_type": self.workout_type,
            "name": self.name,
            "description": self.description,
            "target_tss": round(self.target_tss, 0),
            "target_miles": round(self.target_miles, 1) if self.target_miles else None,
            "target_pace": self.target_pace,
            "intensity": self.intensity,
            "notes": self.notes
        }


@dataclass
class WeekPlan:
    """A week's training plan."""
    week_number: int
    start_date: date
    end_date: date
    phase: str
    target_tss: float
    target_miles: float
    days: List[DayPlan]
    is_cutback: bool = False
    notes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "week_number": self.week_number,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "phase": self.phase,
            "target_tss": round(self.target_tss, 0),
            "target_miles": round(self.target_miles, 1),
            "days": [d.to_dict() for d in self.days],
            "is_cutback": self.is_cutback,
            "notes": self.notes
        }


@dataclass
class ModelDrivenPlan:
    """Complete model-driven training plan."""
    # Identification
    id: str
    athlete_id: str
    created_at: datetime
    
    # Race details
    race_date: date
    race_distance: str
    race_distance_m: int
    
    # Plan structure
    weeks: List[WeekPlan]
    total_weeks: int
    total_miles: float
    total_tss: float
    
    # Predictions
    prediction: RacePrediction
    
    # Model info
    model_confidence: str
    tau1: float
    tau2: float
    
    # Personalization
    taper_start_week: int
    counter_conventional_notes: List[str]
    personalization_summary: str
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "athlete_id": self.athlete_id,
            "created_at": self.created_at.isoformat(),
            "race": {
                "date": self.race_date.isoformat(),
                "distance": self.race_distance,
                "distance_m": self.race_distance_m
            },
            "plan": {
                "weeks": [w.to_dict() for w in self.weeks],
                "total_weeks": self.total_weeks,
                "total_miles": round(self.total_miles, 1),
                "total_tss": round(self.total_tss, 0),
                "taper_start_week": self.taper_start_week
            },
            "prediction": self.prediction.to_dict(),
            "model": {
                "confidence": self.model_confidence,
                "tau1": round(self.tau1, 1),
                "tau2": round(self.tau2, 1)
            },
            "personalization": {
                "counter_conventional_notes": self.counter_conventional_notes,
                "summary": self.personalization_summary
            }
        }


# =============================================================================
# MODEL-DRIVEN PLAN GENERATOR
# =============================================================================

class ModelDrivenPlanGenerator:
    """
    Generates training plans from individual performance model.
    
    No templates. No LLM. Pure calculation from athlete's data.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def generate(
        self,
        athlete_id: UUID,
        race_date: date,
        race_distance: str,
        goal_time_seconds: Optional[int] = None,
        tune_up_races: Optional[List[Dict]] = None
    ) -> ModelDrivenPlan:
        """
        Generate personalized training plan.
        
        Args:
            athlete_id: Athlete UUID
            race_date: Target race date
            race_distance: Race distance key (e.g., "marathon")
            goal_time_seconds: Optional goal time (for pace calculation)
            tune_up_races: List of tune-up races with date, distance, purpose
            
        Returns:
            ModelDrivenPlan with week-by-week structure
        """
        import uuid
        
        plan_id = str(uuid.uuid4())
        race_distance_m = RACE_DISTANCES.get(race_distance.lower(), 42195)
        
        # Step 1: Get or calibrate individual model
        model = get_or_calibrate_model(athlete_id, self.db)
        logger.info(f"Model calibrated: τ1={model.tau1:.1f}, τ2={model.tau2:.1f}, confidence={model.confidence.value}")
        
        # Step 2: Get current training state
        current_ctl, current_atl = self._get_current_state(athlete_id)
        
        # Step 2.5: Get ESTABLISHED baseline volume (8-12 months, not just recent weeks)
        baseline = self._get_established_baseline(athlete_id)
        logger.info(
            f"Baseline: {baseline['weekly_miles']:.1f}mpw, "
            f"long run: {baseline['long_run_miles']:.1f}mi, "
            f"injury recovery: {baseline['is_returning_from_injury']}"
        )

        # Step 3: Calculate optimal load trajectory
        load_calc = OptimalLoadCalculator(self.db)
        trajectory = load_calc.calculate_trajectory(
            athlete_id=athlete_id,
            race_date=race_date,
            current_ctl=current_ctl,
            current_atl=current_atl
        )

        # Step 4: Get training paces
        paces = self._get_training_paces(athlete_id, goal_time_seconds, race_distance_m)

        # Step 5: Convert trajectory to week plans (using baseline for scaling)
        weeks = self._convert_trajectory_to_weeks(
            trajectory, race_distance, paces, athlete_id, baseline
        )
        
        # Step 6: Apply decay-specific interventions
        weeks = self._apply_decay_interventions(weeks, athlete_id, race_distance)
        
        # Step 6.5: Insert tune-up races if provided
        if tune_up_races:
            weeks = self._insert_tune_up_races(weeks, tune_up_races, paces, race_date)
        
        # Step 7: Predict race time
        predictor = RacePredictor(self.db)
        prediction = predictor.predict(
            athlete_id=athlete_id,
            race_date=race_date,
            distance_m=race_distance_m,
            planned_weekly_tss=[w.target_tss for w in trajectory.weeks]
        )
        
        # Step 8: Get counter-conventional notes (pass model for fallback insights)
        counter_notes = self._get_counter_conventional_notes(athlete_id, model)
        
        # Add tune-up race notes if applicable
        if tune_up_races:
            for tr in tune_up_races:
                days_before = (race_date - tr["date"]).days
                purpose = tr.get("purpose", "tune_up")
                if purpose == "threshold":
                    counter_notes.append(
                        f"Your {tr['distance']} on {tr['date'].strftime('%b %d')} serves as your final threshold effort. "
                        f"Race it hard - the {days_before} day recovery is enough for marathon."
                    )
                elif purpose == "sharpening":
                    counter_notes.append(
                        f"The {tr['distance']} race on {tr['date'].strftime('%b %d')} is a sharpening effort - "
                        f"run controlled, don't leave your race there."
                    )
        
        # Step 9: Generate personalization summary
        personalization = self._generate_personalization_summary(model, trajectory, prediction)
        
        # Calculate totals
        total_miles = sum(w.target_miles for w in weeks)
        total_tss = sum(w.target_tss for w in weeks)
        
        return ModelDrivenPlan(
            id=plan_id,
            athlete_id=str(athlete_id),
            created_at=datetime.now(),
            race_date=race_date,
            race_distance=race_distance,
            race_distance_m=race_distance_m,
            weeks=weeks,
            total_weeks=len(weeks),
            total_miles=total_miles,
            total_tss=total_tss,
            prediction=prediction,
            model_confidence=model.confidence.value,
            tau1=model.tau1,
            tau2=model.tau2,
            taper_start_week=trajectory.taper_start_week,
            counter_conventional_notes=counter_notes,
            personalization_summary=personalization
        )
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _get_current_state(self, athlete_id: UUID) -> tuple:
        """Get current CTL and ATL."""
        from services.training_load import TrainingLoadCalculator

        try:
            calculator = TrainingLoadCalculator(self.db)
            load = calculator.calculate_training_load(athlete_id)
            return load.current_ctl, load.current_atl
        except Exception as e:
            logger.warning(f"Could not get current state: {e}")
            return 50.0, 40.0  # Reasonable defaults

    def _get_established_baseline(self, athlete_id: UUID) -> Dict:
        """
        Get athlete's ESTABLISHED training baseline from full 12-month history.
        
        CRITICAL: Look at ALL training in past year, not just old data.
        An athlete who did 60-70 mpw with 18mi @ MP runs 2 months ago
        is an EXPERIENCED marathoner, not a beginner.
        
        Returns:
            Dict with:
            - weekly_miles: Peak sustainable volume (what they CAN do)
            - long_run_miles: Typical long run distance
            - peak_long_run_miles: Longest run they've done
            - peak_weekly_miles: Highest week
            - mp_long_run_miles: Longest MP-portion long run (marathon-specific)
            - experience_level: "beginner", "intermediate", "experienced", "elite"
            - training_patterns: detected patterns (e.g., "interval_saturday", "long_sunday")
            - is_returning_from_injury: Whether recent volume is much lower
        """
        from models import Activity
        from datetime import datetime
        
        end_date = date.today()
        year_ago = end_date - timedelta(days=365)
        
        activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= datetime.combine(year_ago, datetime.min.time()),
            Activity.sport.ilike("run")
        ).order_by(Activity.start_time.desc()).all()
        
        if not activities:
            return self._get_default_baseline()
        
        # ========================================
        # Analyze ALL training data
        # ========================================
        weekly_miles = {}
        long_runs = []  # All runs >= 13 miles
        mp_long_runs = []  # Long runs with marathon pace work
        interval_days = {}  # Day of week -> count
        long_run_days = {}  # Day of week -> count
        
        for activity in activities:
            week_start = activity.start_time.date() - timedelta(days=activity.start_time.weekday())
            day_of_week = activity.start_time.weekday()
            miles = (activity.distance_m or 0) / 1609.344
            duration_min = (activity.duration_s or 0) / 60
            
            # Weekly volume
            if week_start not in weekly_miles:
                weekly_miles[week_start] = 0
            weekly_miles[week_start] += miles
            
            # Long runs (13+ miles for experienced, 10+ for detection)
            if miles >= 13:
                long_runs.append({
                    "miles": miles,
                    "date": activity.start_time.date(),
                    "day_of_week": day_of_week
                })
                # Track long run day patterns
                long_run_days[day_of_week] = long_run_days.get(day_of_week, 0) + 1
                
                # Detect MP long runs from workout type or name
                name_lower = (activity.name or "").lower()
                workout_type = (activity.workout_type or "").lower()
                if any(mp in name_lower for mp in ["mp", "marathon pace", "race pace", "goal pace"]):
                    mp_long_runs.append(miles)
                elif workout_type in ("tempo", "race_pace", "threshold"):
                    mp_long_runs.append(miles)
            elif miles >= 10 or duration_min >= 90:
                # Shorter long runs for newer runners
                long_runs.append({
                    "miles": miles,
                    "date": activity.start_time.date(),
                    "day_of_week": day_of_week
                })
            
            # Detect interval/quality days
            workout_type = (activity.workout_type or "").lower()
            name_lower = (activity.name or "").lower()
            if workout_type in ("interval", "tempo", "threshold", "speed", "track") or \
               any(w in name_lower for w in ["interval", "tempo", "track", "repeat", "fartlek"]):
                interval_days[day_of_week] = interval_days.get(day_of_week, 0) + 1
        
        if not weekly_miles:
            return self._get_default_baseline()
        
        # ========================================
        # Calculate PEAK capabilities (what they CAN do)
        # Not P75 - use their actual demonstrated ability
        # ========================================
        all_weeks = sorted(weekly_miles.values())
        
        # For experienced runners, use P90 (their solid peak weeks)
        # For beginners, use P75 (more conservative)
        peak_weekly = max(all_weeks)
        
        if len(all_weeks) >= 8:
            # Use P90 for established baseline - their REAL capability
            p90_idx = int(len(all_weeks) * 0.90)
            established_weekly = all_weeks[min(p90_idx, len(all_weeks) - 1)]
        else:
            established_weekly = peak_weekly * 0.85
        
        # ========================================
        # Determine experience level
        # ========================================
        if peak_weekly >= 70 or (mp_long_runs and max(mp_long_runs) >= 16):
            experience = "elite"
        elif peak_weekly >= 55 or (long_runs and max(r["miles"] for r in long_runs) >= 20):
            experience = "experienced"
        elif peak_weekly >= 35 or len(long_runs) >= 10:
            experience = "intermediate"
        else:
            experience = "beginner"
        
        # ========================================
        # Long run analysis
        # ========================================
        if long_runs:
            long_run_miles = [r["miles"] for r in long_runs]
            typical_long = sorted(long_run_miles)[int(len(long_run_miles) * 0.75)]
            peak_long = max(long_run_miles)
        else:
            typical_long = established_weekly * 0.28
            peak_long = established_weekly * 0.35
        
        # MP long run capability
        peak_mp_long = max(mp_long_runs) if mp_long_runs else 0
        
        # ========================================
        # Detect training patterns
        # ========================================
        patterns = []
        if interval_days:
            most_common_interval_day = max(interval_days, key=interval_days.get)
            day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            if interval_days[most_common_interval_day] >= 5:
                patterns.append(f"intervals_{day_names[most_common_interval_day]}")
        
        if long_run_days:
            most_common_long_day = max(long_run_days, key=long_run_days.get)
            day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            if long_run_days[most_common_long_day] >= 5:
                patterns.append(f"long_{day_names[most_common_long_day]}")
        
        # ========================================
        # Detect injury/break (compare last 4 weeks to prior 8 weeks)
        # ========================================
        recent_cutoff = end_date - timedelta(days=28)
        prior_start = end_date - timedelta(days=84)
        
        recent_weeks = [m for ws, m in weekly_miles.items() if ws >= recent_cutoff]
        prior_weeks = [m for ws, m in weekly_miles.items() if prior_start <= ws < recent_cutoff]
        
        is_returning = False
        if recent_weeks and prior_weeks:
            recent_avg = sum(recent_weeks) / len(recent_weeks)
            prior_avg = sum(prior_weeks) / len(prior_weeks)
            
            if recent_avg < prior_avg * 0.5:
                is_returning = True
                logger.info(
                    f"Athlete returning from break: "
                    f"recent {recent_avg:.1f}mpw vs prior {prior_avg:.1f}mpw"
                )
        
        baseline = {
            "weekly_miles": established_weekly,
            "long_run_miles": typical_long,
            "peak_long_run_miles": peak_long,
            "peak_weekly_miles": peak_weekly,
            "mp_long_run_miles": peak_mp_long,
            "experience_level": experience,
            "training_patterns": patterns,
            "is_returning_from_injury": is_returning
        }
        
        logger.info(
            f"Athlete baseline: {experience} level, "
            f"{established_weekly:.0f}mpw (peak {peak_weekly:.0f}), "
            f"long run {peak_long:.0f}mi, MP long {peak_mp_long:.0f}mi, "
            f"patterns: {patterns}"
        )
        
        return baseline
    
    def _get_default_baseline(self) -> Dict:
        """Default baseline for athletes with no history."""
        return {
            "weekly_miles": 30,
            "long_run_miles": 10,
            "peak_long_run_miles": 12,
            "peak_weekly_miles": 40,
            "mp_long_run_miles": 0,
            "experience_level": "beginner",
            "training_patterns": [],
            "is_returning_from_injury": False
        }

    def _get_training_paces(
        self,
        athlete_id: UUID,
        goal_time: Optional[int],
        distance_m: int
    ) -> Dict[str, str]:
        """Get training paces from VDOT or goal time."""
        from services.vdot_calculator import calculate_vdot_from_race_time
        
        if goal_time:
            vdot = calculate_vdot_from_race_time(distance_m, goal_time)
        else:
            # Estimate from recent races
            predictor = RacePredictor(self.db)
            current_vdot = predictor._get_current_vdot(athlete_id)
            vdot = current_vdot if current_vdot else 45.0  # Default
        
        paces = calculate_training_paces(vdot)
        return paces if paces else self._default_paces()
    
    def _default_paces(self) -> Dict[str, str]:
        """Return default training paces."""
        return {
            "e_pace": "9:00/mi",
            "m_pace": "8:00/mi",
            "t_pace": "7:15/mi",
            "i_pace": "6:30/mi",
            "r_pace": "6:00/mi"
        }
    
    def _convert_trajectory_to_weeks(
        self,
        trajectory: LoadTrajectory,
        race_distance: str,
        paces: Dict[str, str],
        athlete_id: UUID,
        baseline: Dict = None
    ) -> List[WeekPlan]:
        """Convert TSS trajectory to detailed week plans."""
        if baseline is None:
            baseline = {
                "weekly_miles": 40,
                "long_run_miles": 15,
                "peak_weekly_miles": 50,
                "is_returning_from_injury": False
            }
        
        weeks = []
        total_weeks = len(trajectory.weeks)

        for i, week_target in enumerate(trajectory.weeks):
            # Last week is race week
            is_race_week = (i == total_weeks - 1)

            # Create week plan (with baseline for proper scaling)
            week = self._create_week_plan(
                week_target=week_target,
                race_distance=race_distance,
                paces=paces,
                is_race_week=is_race_week,
                baseline=baseline,
                total_weeks=total_weeks
            )
            weeks.append(week)

        return weeks
    
    def _create_week_plan(
        self,
        week_target: WeeklyLoadTarget,
        race_distance: str,
        paces: Dict[str, str],
        is_race_week: bool = False,
        baseline: Dict = None,
        total_weeks: int = 16
    ) -> WeekPlan:
        """Create a single week's plan from TSS target."""
        if baseline is None:
            baseline = {"weekly_miles": 40, "long_run_miles": 15}
        
        # Determine weekly structure based on phase
        if is_race_week:
            structure = self._get_race_week_structure()
        elif week_target.phase == TrainingPhase.TAPER:
            structure = self._get_taper_week_structure()
        elif week_target.phase == TrainingPhase.PEAK:
            structure = self._get_peak_week_structure()
        elif week_target.phase == TrainingPhase.BUILD:
            structure = self._get_build_week_structure()
        else:  # BASE
            structure = self._get_base_week_structure()

        # Distribute TSS across days (using baseline for scaling)
        days = self._distribute_tss_to_days(
            week_start=week_target.start_date,
            total_tss=week_target.target_tss,
            structure=structure,
            paces=paces,
            race_distance=race_distance,
            phase=week_target.phase,
            baseline=baseline,
            week_number=week_target.week_number,
            total_weeks=total_weeks
        )
        
        # Calculate total miles
        total_miles = sum(d.target_miles or 0 for d in days)
        
        return WeekPlan(
            week_number=week_target.week_number,
            start_date=week_target.start_date,
            end_date=week_target.end_date,
            phase=week_target.phase.value,
            target_tss=week_target.target_tss,
            target_miles=total_miles,
            days=days,
            is_cutback=week_target.is_cutback,
            notes=week_target.notes
        )
    
    def _get_base_week_structure(self) -> List[Dict]:
        """
        Get base phase week structure.
        
        80/20 Distribution Target:
        - Easy: 80% (rest, easy, easy long run without workout)
        - Quality: 20% (in base: strides only, no threshold)
        
        Source: TRAINING_PHILOSOPHY.md - Base phase has NO threshold
        """
        return [
            {"day": 0, "type": "rest", "tss_pct": 0},       # Rest (Monday)
            {"day": 1, "type": "easy", "tss_pct": 0.14},    # Easy (Tuesday)
            {"day": 2, "type": "easy", "tss_pct": 0.14},    # Easy (Wednesday) 
            {"day": 3, "type": "easy_strides", "tss_pct": 0.12},  # Easy + strides (Thursday) - NOT threshold
            {"day": 4, "type": "easy", "tss_pct": 0.12},    # Easy (Friday)
            {"day": 5, "type": "easy", "tss_pct": 0.18},    # Medium-long easy (Saturday)
            {"day": 6, "type": "long", "tss_pct": 0.30},    # Long run easy (Sunday) - 30% max
        ]
    
    def _get_build_week_structure(self) -> List[Dict]:
        """
        Get build phase week structure.
        
        80/20 Distribution Target:
        - Easy: ~75-80% (includes easy long run)
        - Quality: ~20-25% (threshold work)
        
        Source: TRAINING_PHILOSOPHY.md - T-work in build, max 1-2 quality sessions
        Source: PLAN_GENERATION_FRAMEWORK.md Rule A3 - Never 3 hard days
        """
        return [
            {"day": 0, "type": "rest", "tss_pct": 0},       # Rest (Monday)
            {"day": 1, "type": "easy", "tss_pct": 0.14},    # Easy (Tuesday)
            {"day": 2, "type": "easy", "tss_pct": 0.14},    # Easy (Wednesday)
            {"day": 3, "type": "quality", "tss_pct": 0.14}, # Threshold (Thursday) - single quality
            {"day": 4, "type": "easy", "tss_pct": 0.12},    # Easy (Friday)
            {"day": 5, "type": "easy", "tss_pct": 0.16},    # Medium-long easy (Saturday)
            {"day": 6, "type": "long", "tss_pct": 0.30},    # Long run (Sunday) - can have MP finish
        ]
    
    def _get_peak_week_structure(self) -> List[Dict]:
        """
        Get peak phase week structure.
        
        80/20 Distribution Target:
        - Easy: ~75% (long run with MP counts partially as quality)
        - Quality: ~25% (race-specific + MP in long)
        
        Source: TRAINING_PHILOSOPHY.md - MP work placed inside long runs
        """
        return [
            {"day": 0, "type": "rest", "tss_pct": 0},       # Rest (Monday)
            {"day": 1, "type": "easy", "tss_pct": 0.14},    # Easy (Tuesday)
            {"day": 2, "type": "easy", "tss_pct": 0.14},    # Easy (Wednesday)
            {"day": 3, "type": "quality", "tss_pct": 0.14}, # Race pace (Thursday)
            {"day": 4, "type": "easy", "tss_pct": 0.12},    # Easy (Friday)
            {"day": 5, "type": "easy", "tss_pct": 0.16},    # Medium easy (Saturday)
            {"day": 6, "type": "long", "tss_pct": 0.30},    # Long run with MP (Sunday)
        ]
    
    def _get_taper_week_structure(self) -> List[Dict]:
        """
        Get taper phase week structure.
        
        Distribution: Mostly easy with light sharpening
        
        Source: TRAINING_PHILOSOPHY.md - Taper maintains some intensity, reduces volume
        """
        return [
            {"day": 0, "type": "rest", "tss_pct": 0},       # Rest (Monday)
            {"day": 1, "type": "easy", "tss_pct": 0.18},    # Easy (Tuesday)
            {"day": 2, "type": "sharpening", "tss_pct": 0.18},  # Light sharpening (Wednesday)
            {"day": 3, "type": "easy", "tss_pct": 0.16},    # Easy (Thursday)
            {"day": 4, "type": "easy", "tss_pct": 0.16},    # Easy (Friday)
            {"day": 5, "type": "rest", "tss_pct": 0},       # Rest (Saturday)
            {"day": 6, "type": "long", "tss_pct": 0.32},    # Reduced long (Sunday)
        ]
    
    def _get_race_week_structure(self) -> List[Dict]:
        """
        Get race week structure - ends with race day.
        
        Race week is almost entirely easy/rest leading to race.
        
        Source: Standard taper protocol
        """
        return [
            {"day": 0, "type": "rest", "tss_pct": 0},       # Rest (Monday)
            {"day": 1, "type": "easy", "tss_pct": 0.10},    # Short shake-out (Tuesday)
            {"day": 2, "type": "sharpening", "tss_pct": 0.10},  # Light strides (Wednesday)
            {"day": 3, "type": "easy", "tss_pct": 0.08},    # Easy short (Thursday)
            {"day": 4, "type": "rest", "tss_pct": 0},       # Rest (Friday)
            {"day": 5, "type": "shakeout", "tss_pct": 0.05},  # Optional shakeout (Saturday)
            {"day": 6, "type": "race", "tss_pct": 0.67},    # RACE DAY (Sunday)
        ]
    
    def _distribute_tss_to_days(
        self,
        week_start: date,
        total_tss: float,
        structure: List[Dict],
        paces: Dict[str, str],
        race_distance: str,
        phase: TrainingPhase,
        baseline: Dict = None,
        week_number: int = 1,
        total_weeks: int = 16
    ) -> List[DayPlan]:
        """Distribute weekly TSS to individual days."""
        if baseline is None:
            baseline = {"weekly_miles": 40, "long_run_miles": 15}
        
        days = []
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        for s in structure:
            day_date = week_start + timedelta(days=s["day"])
            day_tss = total_tss * s["tss_pct"]
            workout_type = s["type"]

            # Create day plan based on workout type (using baseline for scaling)
            day = self._create_day_plan(
                date=day_date,
                day_of_week=weekdays[s["day"]],
                workout_type=workout_type,
                target_tss=day_tss,
                paces=paces,
                race_distance=race_distance,
                phase=phase,
                baseline=baseline,
                week_number=week_number,
                total_weeks=total_weeks
            )
            days.append(day)

        return days
    
    def _create_day_plan(
        self,
        date: date,
        day_of_week: str,
        workout_type: str,
        target_tss: float,
        paces: Dict[str, str],
        race_distance: str,
        phase: TrainingPhase,
        baseline: Dict = None,
        week_number: int = 1,
        total_weeks: int = 16
    ) -> DayPlan:
        """Create a single day's workout plan."""
        if baseline is None:
            baseline = {"weekly_miles": 40, "long_run_miles": 15}
        
        if workout_type == "rest":
            return DayPlan(
                date=date,
                day_of_week=day_of_week,
                workout_type="rest",
                name="Rest Day",
                description="Complete rest or light cross-training.",
                target_tss=0,
                target_miles=0,
                intensity="rest"
            )
        
        elif workout_type == "easy":
            miles = target_tss * TSS_TO_MILES_EASY
            return DayPlan(
                date=date,
                day_of_week=day_of_week,
                workout_type="easy",
                name="Easy Run",
                description=f"Easy aerobic run at {paces.get('e_pace', 'easy pace')}.",
                target_tss=target_tss,
                target_miles=miles,
                target_pace=paces.get('e_pace'),
                intensity="easy"
            )
        
        elif workout_type == "easy_strides":
            # Easy run with strides at end - base phase speed work
            # Source: TRAINING_PHILOSOPHY.md - Strides in base phase for neuromuscular
            miles = target_tss * TSS_TO_MILES_EASY
            return DayPlan(
                date=date,
                day_of_week=day_of_week,
                workout_type="easy",  # Counts as easy for 80/20
                name="Easy Run + Strides",
                description=f"Easy run at {paces.get('e_pace', 'easy pace')}, then 4-6 × 20s strides (fast but relaxed).",
                target_tss=target_tss,
                target_miles=miles,
                target_pace=paces.get('e_pace'),
                intensity="easy",
                notes=["Strides: 20 seconds fast, walk back recovery", "Not sprinting - smooth and relaxed"]
            )
        
        elif workout_type == "quality":
            miles = target_tss * TSS_TO_MILES_QUALITY
            if phase == TrainingPhase.BUILD:
                return DayPlan(
                    date=date,
                    day_of_week=day_of_week,
                    workout_type="threshold",
                    name="Threshold Workout",
                    description=f"Warm up, then tempo at {paces.get('t_pace', 'threshold pace')}.",
                    target_tss=target_tss,
                    target_miles=miles,
                    target_pace=paces.get('t_pace'),
                    intensity="hard"
                )
            else:  # PEAK
                return DayPlan(
                    date=date,
                    day_of_week=day_of_week,
                    workout_type="race_pace",
                    name="Race Pace Work",
                    description=f"Race-specific work at {paces.get('m_pace', 'marathon pace')}.",
                    target_tss=target_tss,
                    target_miles=miles,
                    target_pace=paces.get('m_pace'),
                    intensity="moderate"
                )
        
        elif workout_type == "sharpening":
            miles = target_tss * TSS_TO_MILES_QUALITY
            return DayPlan(
                date=date,
                day_of_week=day_of_week,
                workout_type="sharpening",
                name="Sharpening",
                description=f"Short, sharp efforts at {paces.get('i_pace', 'interval pace')}.",
                target_tss=target_tss,
                target_miles=miles,
                target_pace=paces.get('i_pace'),
                intensity="hard",
                notes=["Keep volume low, intensity crisp"]
            )
        
        elif workout_type == "long":
            # ========================================
            # CRITICAL: Use athlete's ACTUAL baseline, not fixed caps
            # A 55-70 mpw runner should do 18-22 mile long runs, not 10-15!
            # ========================================
            
            # Get distance-specific caps as FALLBACK only
            caps = LONG_RUN_CAPS.get(race_distance, LONG_RUN_CAPS["marathon"])
            
            # Use athlete's established long run distances
            athlete_typical_long = baseline.get("long_run_miles", caps["peak"])
            athlete_peak_long = baseline.get("peak_long_run_miles", athlete_typical_long)
            athlete_weekly = baseline.get("weekly_miles", 40)
            
            # Long run target based on weekly volume (25-30% for most, up to 35% for marathon)
            # For a 53 mpw runner: 15-19 miles typical
            # For a 70 mpw runner: 18-24 miles
            calculated_typical = athlete_weekly * 0.30
            calculated_peak = athlete_weekly * 0.38  # Peak week can be higher
            
            # For BUILD phase: use typical long run
            typical_long_target = max(athlete_typical_long, calculated_typical)
            
            # For PEAK phase: use the athlete's actual PEAK capability
            # This ensures experienced marathoners get appropriate 20+ mile runs
            peak_long_target = max(athlete_peak_long, calculated_peak)
            
            # Apply distance-appropriate maximum
            typical_long_target = min(typical_long_target, caps["max"])
            peak_long_target = min(peak_long_target, caps["max"])
            
            # Apply phase-based scaling using athlete's actual history
            # Use week_number and total_weeks for PROGRESSIVE long runs
            
            # Calculate progression factor (0.0 at start, 1.0 at peak)
            # Reserve last 3 weeks for taper
            build_weeks = total_weeks - 3
            if build_weeks > 0:
                progress = min(1.0, (week_number - 1) / build_weeks)
            else:
                progress = 0.5
            
            if phase == TrainingPhase.BASE:
                # Base phase: 60-70% of typical, slight progression
                base_pct = 0.60 + (0.10 * progress)
                miles = typical_long_target * base_pct
            elif phase == TrainingPhase.BUILD:
                # Build phase: PROGRESSIVE from 75% to 95% of typical
                # This ensures long runs BUILD UP, not stay flat
                build_pct = 0.75 + (0.20 * progress)
                miles = typical_long_target * build_pct
            elif phase == TrainingPhase.PEAK:
                # Peak phase: use athlete's PEAK capability
                # This is the key - experienced marathoners hit 20+ miles
                miles = peak_long_target
            elif phase == TrainingPhase.TAPER:
                # Taper: 50-60% of typical
                miles = typical_long_target * 0.55
            else:
                miles = typical_long_target * 0.80
            
            # Apply minimum floor
            miles = max(miles, caps["min"])
            
            if phase == TrainingPhase.BUILD and race_distance in ("marathon", "half_marathon"):
                # ========================================
                # MP PORTION SCALES WITH EXPERIENCE
                # Someone who's done 18@MP doesn't need 4@MP - that's useless
                # ========================================
                experience = baseline.get("experience_level", "intermediate")
                proven_mp = baseline.get("mp_long_run_miles", 0)
                
                if race_distance == "half_marathon":
                    # HM: 2-5 miles @ HMP
                    if experience == "elite":
                        mp_miles = 5
                    elif experience == "experienced":
                        mp_miles = 4
                    else:
                        mp_miles = 3
                else:
                    # Marathon: Scale based on what they've PROVEN they can do
                    if proven_mp >= 14:
                        # They've done 14+ @ MP - give them 8-12 in build
                        mp_miles = min(12, int(proven_mp * 0.65))
                    elif proven_mp >= 10:
                        # Done 10-14 @ MP - give them 6-10
                        mp_miles = min(10, int(proven_mp * 0.70))
                    elif experience == "elite":
                        mp_miles = 10
                    elif experience == "experienced":
                        mp_miles = 8
                    elif experience == "intermediate":
                        mp_miles = 6
                    else:
                        mp_miles = 4
                
                return DayPlan(
                    date=date,
                    day_of_week=day_of_week,
                    workout_type="long_run",
                    name=f"Long Run with {mp_miles}mi @ MP",
                    description=f"Start easy, finish last {mp_miles} miles at {paces.get('m_pace', 'marathon pace')}.",
                    target_tss=target_tss,
                    target_miles=miles,
                    target_pace=paces.get('e_pace'),
                    intensity="moderate"
                )
            elif phase == TrainingPhase.PEAK and race_distance in ("marathon", "half_marathon"):
                # ========================================
                # PEAK WEEK: Full race simulation
                # If they've done 18@MP, peak should be 14-16@MP in a 22mi run
                # ========================================
                experience = baseline.get("experience_level", "intermediate")
                proven_mp = baseline.get("mp_long_run_miles", 0)
                
                if race_distance == "half_marathon":
                    if experience in ("elite", "experienced"):
                        mp_miles = 6
                    else:
                        mp_miles = 5
                else:
                    # Marathon peak: This is the dress rehearsal
                    if proven_mp >= 16:
                        # They've done 16+ @ MP - match or slightly exceed
                        mp_miles = min(16, int(proven_mp * 0.90))
                    elif proven_mp >= 12:
                        mp_miles = min(14, int(proven_mp * 0.95))
                    elif experience == "elite":
                        mp_miles = 14
                    elif experience == "experienced":
                        mp_miles = 12
                    elif experience == "intermediate":
                        mp_miles = 10
                    else:
                        mp_miles = 8
                
                return DayPlan(
                    date=date,
                    day_of_week=day_of_week,
                    workout_type="long_run",
                    name=f"Long Run with {mp_miles}mi @ MP",
                    description=f"Build to {paces.get('m_pace', 'marathon pace')} for middle or finish portion. Race simulation.",
                    target_tss=target_tss,
                    target_miles=miles,
                    target_pace=paces.get('e_pace'),
                    intensity="moderate"
                )
            elif phase == TrainingPhase.TAPER:
                return DayPlan(
                    date=date,
                    day_of_week=day_of_week,
                    workout_type="long_run",
                    name="Reduced Long Run",
                    description="Easy effort, reduced distance for recovery.",
                    target_tss=target_tss,
                    target_miles=miles,
                    target_pace=paces.get('e_pace'),
                    intensity="easy"
                )
            else:
                return DayPlan(
                    date=date,
                    day_of_week=day_of_week,
                    workout_type="long_run",
                    name="Long Run",
                    description=f"Steady aerobic effort at {paces.get('e_pace', 'easy pace')}.",
                    target_tss=target_tss,
                    target_miles=miles,
                    target_pace=paces.get('e_pace'),
                    intensity="easy"
                )
        
        elif workout_type == "race":
            # Race day! Distance is the race distance
            distance_miles = {
                "5k": 3.1,
                "10k": 6.2,
                "half_marathon": 13.1,
                "marathon": 26.2
            }.get(race_distance, 26.2)
            
            return DayPlan(
                date=date,
                day_of_week=day_of_week,
                workout_type="race",
                name=f"RACE DAY: {race_distance.replace('_', ' ').title()}",
                description=f"Execute your race. Target pace: {paces.get('m_pace', 'goal pace')}. Trust your training.",
                target_tss=target_tss,
                target_miles=distance_miles,
                target_pace=paces.get('m_pace'),
                intensity="race",
                notes=["Race day! Stay relaxed first half, execute second half.", 
                       "Nutrition: as practiced in training."]
            )
        
        elif workout_type == "shakeout":
            return DayPlan(
                date=date,
                day_of_week=day_of_week,
                workout_type="shakeout",
                name="Pre-Race Shakeout",
                description="Optional 10-20 min very easy jog. Skip if you feel tired.",
                target_tss=target_tss,
                target_miles=target_tss * TSS_TO_MILES_EASY,
                target_pace=paces.get('e_pace'),
                intensity="easy",
                notes=["Optional - listen to your body"]
            )
        
        else:
            # Fallback
            return DayPlan(
                date=date,
                day_of_week=day_of_week,
                workout_type="easy",
                name="Easy Run",
                description="Easy effort.",
                target_tss=target_tss,
                target_miles=target_tss * TSS_TO_MILES_EASY,
                intensity="easy"
            )
    
    def _apply_decay_interventions(
        self,
        weeks: List[WeekPlan],
        athlete_id: UUID,
        race_distance: str
    ) -> List[WeekPlan]:
        """Apply decay-specific workout interventions."""
        try:
            from services.pace_decay import get_athlete_decay_profile
            
            decay_profile = get_athlete_decay_profile(str(athlete_id), self.db)
            
            if not decay_profile or decay_profile.overall_avg_decay < 5:
                return weeks  # Good pacing, no intervention needed
            
            # For high decay athletes, add specific interventions
            for week in weeks:
                if week.phase == "build" and race_distance == "marathon":
                    for day in week.days:
                        if day.workout_type == "long_run":
                            day.notes.append(
                                f"Your data shows {decay_profile.overall_avg_decay:.0f}% pace fade. "
                                "Practice race nutrition and negative split pacing."
                            )
            
            return weeks
            
        except Exception as e:
            logger.warning(f"Could not apply decay interventions: {e}")
            return weeks
    
    def _insert_tune_up_races(
        self,
        weeks: List[WeekPlan],
        tune_up_races: List[Dict],
        paces: Dict[str, str],
        goal_race_date: date
    ) -> List[WeekPlan]:
        """
        Insert tune-up races into the plan.
        
        A tune-up race replaces the workout on that day and adjusts surrounding days.
        For a race 8 days before marathon (like 10-mile as final threshold), we:
        - Replace that day with the tune-up race
        - Ensure proper recovery/shakeout before and after
        - Mark the purpose (threshold, sharpening, etc.)
        """
        TUNE_UP_DISTANCES = {
            "5k": 5000,
            "10k": 10000,
            "10_mile": 16093,
            "10_miles": 16093,
            "15k": 15000,
            "half_marathon": 21097
        }
        
        for tune_up in tune_up_races:
            tr_date = tune_up["date"]
            tr_distance = tune_up["distance"].lower()
            tr_name = tune_up.get("name", f"{tr_distance.upper()} Tune-Up")
            tr_purpose = tune_up.get("purpose", "tune_up")
            
            # Find which week contains this tune-up
            for week in weeks:
                for i, day in enumerate(week.days):
                    if day.date == tr_date:
                        # Calculate race distance in miles
                        distance_m = TUNE_UP_DISTANCES.get(tr_distance, 10000)
                        distance_miles = distance_m / 1609.344
                        
                        # Determine effort description based on purpose
                        if tr_purpose == "threshold":
                            description = (
                                f"Race this HARD - it's your final threshold before the marathon. "
                                f"This is your last quality effort. Run for a PR."
                            )
                            intensity = "race"
                        elif tr_purpose == "sharpening":
                            description = (
                                f"Controlled effort - stay relaxed, don't empty the tank. "
                                f"Use as a dress rehearsal for race day routines."
                            )
                            intensity = "moderate"
                        else:  # tune_up, fitness_check
                            description = (
                                f"Tune-up race. Run comfortably hard but save something. "
                                f"Focus on feeling good, not crushing it."
                            )
                            intensity = "moderate"
                        
                        # Replace with tune-up race
                        week.days[i] = DayPlan(
                            date=tr_date,
                            day_of_week=day.day_of_week,
                            workout_type="tune_up_race",
                            name=tr_name,
                            description=description,
                            target_tss=distance_miles * 12,  # Harder effort TSS
                            target_miles=distance_miles,
                            target_pace=paces.get('t_pace'),  # Threshold or race pace
                            intensity=intensity,
                            notes=[
                                f"Purpose: {tr_purpose.replace('_', ' ').title()}",
                                f"Days to goal race: {(goal_race_date - tr_date).days}"
                            ]
                        )
                        
                        # Adjust surrounding days if needed
                        days_to_goal = (goal_race_date - tr_date).days
                        
                        # Day before tune-up should be easy/rest
                        if i > 0:
                            prev_day = week.days[i - 1]
                            if prev_day.workout_type not in ("rest", "shakeout"):
                                week.days[i - 1] = DayPlan(
                                    date=prev_day.date,
                                    day_of_week=prev_day.day_of_week,
                                    workout_type="easy",
                                    name="Pre-Race Easy",
                                    description="Very easy shakeout before tomorrow's tune-up race.",
                                    target_tss=20,
                                    target_miles=3.0,
                                    target_pace=paces.get('e_pace'),
                                    intensity="easy"
                                )
                        
                        # Day after tune-up should be recovery (especially for 8-day gap)
                        if i < len(week.days) - 1:
                            next_day = week.days[i + 1]
                            if days_to_goal <= 10:  # Close to goal race
                                week.days[i + 1] = DayPlan(
                                    date=next_day.date,
                                    day_of_week=next_day.day_of_week,
                                    workout_type="rest",
                                    name="Post-Race Recovery",
                                    description="Complete rest after tune-up. Marathon is soon.",
                                    target_tss=0,
                                    target_miles=0,
                                    intensity="rest"
                                )
                        
                        logger.info(
                            f"Inserted tune-up race: {tr_name} on {tr_date}, "
                            f"purpose={tr_purpose}, {days_to_goal} days before goal"
                        )
                        break
        
        return weeks
    
    def _get_counter_conventional_notes(self, athlete_id: UUID, model: 'BanisterModel' = None) -> List[str]:
        """
        Get counter-conventional findings from fingerprint OR generate from model.
        
        Source: TRAINING_PHILOSOPHY.md - "The athlete is the blueprint"
        These notes should be specific, data-driven, and actionable.
        """
        notes = []
        
        # Try to get from fingerprint service
        try:
            from services.pre_race_fingerprinting import generate_readiness_profile

            fingerprint = generate_readiness_profile(str(athlete_id), self.db)

            if fingerprint.has_counter_conventional_findings:
                for feature in fingerprint.features:
                    if feature.is_significant and feature.pattern_type.value == 'inverted':
                        notes.append(feature.insight_text)

        except Exception as e:
            logger.debug(f"Fingerprint not available: {e}")
        
        # Add model-based insights if we have model data
        if model and not notes:
            # τ1 insights (fitness time constant)
            if model.tau1 < 35:
                notes.append(
                    f"Your τ1 of {model.tau1:.0f} days indicates rapid fitness absorption. "
                    f"You can handle aggressive loading but need vigilant recovery."
                )
            elif model.tau1 > 50:
                notes.append(
                    f"Your τ1 of {model.tau1:.0f} days suggests patient adaptation. "
                    f"Hold peak weeks longer than standard plans prescribe."
                )
            else:
                notes.append(
                    f"Your τ1 of {model.tau1:.0f} days is well-calibrated for standard periodization."
                )
            
            # τ2 insights (fatigue time constant)
            if model.tau2 < 5:
                notes.append(
                    f"Quick fatigue clearance (τ2={model.tau2:.0f}d) means you can train more frequently. "
                    f"Consider 6 days/week if not already."
                )
            elif model.tau2 > 10:
                notes.append(
                    f"Slower fatigue clearance (τ2={model.tau2:.0f}d) requires extra recovery. "
                    f"Prioritize sleep and easy day pacing."
                )
            
            # Confidence-based note
            if model.confidence.value == "low":
                notes.append(
                    "Limited training history means predictions are wider. "
                    "Treat pace targets as guides, not absolutes."
                )
        
        # Ensure we always have at least one note
        if not notes:
            notes.append(
                "Plan personalization based on population models. "
                "More training data will unlock individual insights."
            )
        
        return notes
    
    def _generate_personalization_summary(
        self,
        model: BanisterModel,
        trajectory: LoadTrajectory,
        prediction: RacePrediction
    ) -> str:
        """Generate human-readable personalization summary."""
        parts = []
        
        # Model insights
        if model.confidence in [ModelConfidence.HIGH, ModelConfidence.MODERATE]:
            if model.tau1 < 40:
                parts.append("You adapt faster than average")
            elif model.tau1 > 45:
                parts.append("You benefit from longer training blocks")
            
            if model.tau2 < 6:
                parts.append("you recover quickly from fatigue")
            elif model.tau2 > 8:
                parts.append("you need extra recovery time")
        
        # Taper insight
        optimal_taper = model.calculate_optimal_taper_days()
        parts.append(f"your optimal taper is {optimal_taper} days")
        
        if parts:
            return "Based on your data: " + ", ".join(parts) + "."
        else:
            return "Plan generated from your training history."


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def generate_model_driven_plan(
    athlete_id: UUID,
    race_date: date,
    race_distance: str,
    db: Session,
    goal_time_seconds: Optional[int] = None,
    tune_up_races: Optional[List[Dict]] = None
) -> ModelDrivenPlan:
    """Generate model-driven training plan.
    
    Args:
        tune_up_races: List of tune-up races before goal race, each with:
            - date: Race date
            - distance: "5k", "10k", "10_mile", "half_marathon"
            - name: Optional race name
            - purpose: "tune_up", "threshold", "sharpening", "fitness_check"
    """
    generator = ModelDrivenPlanGenerator(db)
    return generator.generate(
        athlete_id=athlete_id,
        race_date=race_date,
        race_distance=race_distance,
        goal_time_seconds=goal_time_seconds,
        tune_up_races=tune_up_races
    )
