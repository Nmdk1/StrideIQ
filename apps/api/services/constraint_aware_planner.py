"""
Constraint-Aware Planner (ADR-031)

Orchestrates plan generation:
1. Get Fitness Bank
2. Apply constraint overrides
3. Generate week themes
4. Fill workouts via WorkoutPrescriptionGenerator
5. Inject counter-conventional notes

Produces exceptional, personalized plans from N=1 data.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Dict, Optional
from uuid import UUID
import logging

from sqlalchemy.orm import Session

from services.fitness_bank import (
    FitnessBank, 
    get_fitness_bank, 
    ConstraintType, 
    ExperienceLevel
)
from services.week_theme_generator import (
    WeekThemeGenerator, 
    WeekTheme, 
    WeekThemePlan,
    generate_week_themes
)
from services.workout_prescription import (
    WorkoutPrescriptionGenerator,
    WeekPlan,
    DayPlan
)

logger = logging.getLogger(__name__)


@dataclass
class ConstraintAwarePlan:
    """A complete plan with all metadata."""
    
    # Core plan data
    weeks: List[WeekPlan]
    total_weeks: int
    total_miles: float
    
    # Race info
    race_date: date
    race_distance: str
    tune_up_races: List[Dict]
    
    # Fitness Bank data
    fitness_bank: Dict
    
    # Model parameters
    tau1: float
    tau2: float
    model_confidence: str
    
    # Personalized insights
    counter_conventional_notes: List[str]
    
    # Predicted outcomes
    predicted_time: Optional[str]
    prediction_ci: Optional[str]
    
    def to_dict(self) -> Dict:
        return {
            "weeks": [w.to_dict() for w in self.weeks],
            "total_weeks": self.total_weeks,
            "total_miles": round(self.total_miles, 1),
            "race_date": self.race_date.isoformat(),
            "race_distance": self.race_distance,
            "tune_up_races": self.tune_up_races,
            "fitness_bank": self.fitness_bank,
            "model": {
                "tau1": round(self.tau1, 1),
                "tau2": round(self.tau2, 1),
                "confidence": self.model_confidence
            },
            "insights": self.counter_conventional_notes,
            "prediction": {
                "time": self.predicted_time,
                "ci": self.prediction_ci
            }
        }


class ConstraintAwarePlanner:
    """
    Orchestrates constraint-aware plan generation.
    
    Sequence:
    1. Get Fitness Bank (proven capabilities + constraints)
    2. Apply constraint overrides (injury ramp, dual races)
    3. Generate week themes (alternating T/MP/Recovery)
    4. Fill workouts (specific prescriptions)
    5. Inject counter-conventional notes
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.theme_generator = WeekThemeGenerator()
    
    def generate_plan(self,
                     athlete_id: UUID,
                     race_date: date,
                     race_distance: str,
                     goal_time: Optional[str] = None,
                     tune_up_races: Optional[List[Dict]] = None) -> ConstraintAwarePlan:
        """
        Generate a complete constraint-aware plan.
        """
        logger.info(f"Generating constraint-aware plan for athlete {athlete_id}")
        
        # 1. Get Fitness Bank
        bank = get_fitness_bank(athlete_id, self.db)
        logger.info(f"Fitness Bank: peak={bank.peak_weekly_miles:.0f}mpw, "
                   f"current={bank.current_weekly_miles:.0f}mpw, "
                   f"constraint={bank.constraint_type.value}")
        
        # 2. Generate week themes
        themes = self.theme_generator.generate(
            bank=bank,
            race_date=race_date,
            race_distance=race_distance,
            tune_up_races=tune_up_races
        )
        
        if not themes:
            logger.warning("No themes generated - race date too soon?")
            return self._generate_minimal_plan(bank, race_date, race_distance)
        
        # 3. Apply constraint overrides
        themes = self._apply_constraint_overrides(themes, bank, tune_up_races)
        
        # 4. Fill workouts for each week
        workout_generator = WorkoutPrescriptionGenerator(bank)
        weeks = []
        
        for theme_plan in themes:
            target_miles = theme_plan.target_volume_pct * bank.peak_weekly_miles
            
            # Only clamp early weeks if injury return - allow progression to peak
            if bank.constraint_type == ConstraintType.INJURY and theme_plan.week_number <= 4:
                max_weekly = self._calculate_safe_weekly(
                    bank.current_weekly_miles,
                    theme_plan.week_number,
                    bank.tau1,
                    bank.peak_weekly_miles
                )
                target_miles = min(target_miles, max_weekly)
            
            week_plan = workout_generator.generate_week(
                theme=theme_plan.theme,
                week_number=theme_plan.week_number,
                total_weeks=len(themes),
                target_miles=target_miles,
                start_date=theme_plan.start_date
            )
            
            # Add theme notes to week
            week_plan.notes.extend(theme_plan.notes)
            
            weeks.append(week_plan)
        
        # 5. Insert tune-up race specifics
        if tune_up_races:
            weeks = self._insert_tune_up_details(weeks, tune_up_races, bank)
        
        # 6. Generate counter-conventional notes
        notes = self._generate_insights(bank, themes, tune_up_races)
        
        # 7. Calculate predictions
        predicted, ci = self._predict_race(bank, race_distance, goal_time)
        
        total_miles = sum(w.total_miles for w in weeks)
        
        return ConstraintAwarePlan(
            weeks=weeks,
            total_weeks=len(weeks),
            total_miles=total_miles,
            race_date=race_date,
            race_distance=race_distance,
            tune_up_races=tune_up_races or [],
            fitness_bank=bank.to_dict(),
            tau1=bank.tau1,
            tau2=bank.tau2,
            model_confidence=self._assess_confidence(bank),
            counter_conventional_notes=notes,
            predicted_time=predicted,
            prediction_ci=ci
        )
    
    def _apply_constraint_overrides(self,
                                   themes: List[WeekThemePlan],
                                   bank: FitnessBank,
                                   tune_up_races: Optional[List[Dict]]) -> List[WeekThemePlan]:
        """Apply constraint-specific modifications."""
        
        # Injury: ensure proper rebuild progression
        if bank.constraint_type == ConstraintType.INJURY:
            current_pct = bank.current_weekly_miles / bank.peak_weekly_miles
            
            if current_pct < 0.3:
                # Very reduced - force 3 weeks rebuild
                for i in range(min(3, len(themes))):
                    if themes[i].theme not in (WeekTheme.REBUILD_EASY, WeekTheme.REBUILD_STRIDES):
                        if i == 0:
                            themes[i].theme = WeekTheme.REBUILD_EASY
                            themes[i].target_volume_pct = 0.40
                            themes[i].notes = ["Gentle return - easy only"]
                        elif i <= 2:
                            themes[i].theme = WeekTheme.REBUILD_STRIDES
                            themes[i].target_volume_pct = 0.50 + (i * 0.10)
                            themes[i].notes = ["Building back with strides"]
            
            elif current_pct < 0.5:
                # Moderately reduced - 2 weeks rebuild
                for i in range(min(2, len(themes))):
                    if themes[i].theme not in (WeekTheme.REBUILD_EASY, WeekTheme.REBUILD_STRIDES):
                        if i == 0:
                            themes[i].theme = WeekTheme.REBUILD_EASY
                            themes[i].target_volume_pct = 0.50
                        else:
                            themes[i].theme = WeekTheme.REBUILD_STRIDES
                            themes[i].target_volume_pct = 0.65
        
        # Dual race protection
        if tune_up_races and len(tune_up_races) > 0:
            # Find tune-up week and ensure recovery after
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
            
            for tune_up in tune_up_races:
                tune_date = tune_up["date"]
                if isinstance(tune_date, str):
                    tune_date = date.fromisoformat(tune_date)
                
                days_to_tune = (tune_date - week_start).days
                tune_week_idx = days_to_tune // 7
                
                # Week after tune-up should be easier
                if tune_week_idx + 1 < len(themes):
                    next_theme = themes[tune_week_idx + 1]
                    if next_theme.theme not in (WeekTheme.RACE, WeekTheme.TAPER_2):
                        # Don't override race week, but reduce other weeks
                        next_theme.target_volume_pct *= 0.85
                        next_theme.notes.append("Recovery from tune-up race")
        
        return themes
    
    def _calculate_safe_weekly(self, current: float, week_num: int, tau1: float, 
                               peak: float) -> float:
        """Calculate safe weekly mileage for injury return.
        
        Key insight: Experienced athletes with banked fitness can ramp faster.
        We don't start from current volume - we ramp towards peak.
        """
        # For experienced athletes, start from a floor (not current)
        # They have the aerobic base, just need to rebuild carefully
        floor = max(current, peak * 0.35)  # At least 35% of peak
        
        # Faster adapters (low τ1) can handle steeper ramps
        if tau1 < 30:
            increase_rate = 0.20  # 20% per week
        elif tau1 > 45:
            increase_rate = 0.12  # 12% per week
        else:
            increase_rate = 0.15  # 15% per week
        
        # Calculate safe max for this week
        safe_max = floor * (1 + increase_rate) ** week_num
        
        # Cap at peak - never exceed proven capability
        return min(safe_max, peak)
    
    def _insert_tune_up_details(self,
                               weeks: List[WeekPlan],
                               tune_up_races: List[Dict],
                               bank: FitnessBank) -> List[WeekPlan]:
        """Insert specific tune-up race details into week plans."""
        
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        
        for tune_up in tune_up_races:
            tune_date = tune_up["date"]
            if isinstance(tune_date, str):
                tune_date = date.fromisoformat(tune_date)
            
            days_to_tune = (tune_date - week_start).days
            week_idx = days_to_tune // 7
            day_idx = tune_date.weekday()
            
            if 0 <= week_idx < len(weeks):
                week = weeks[week_idx]
                
                # Find and update the race day
                for i, day in enumerate(week.days):
                    if day.day_of_week == day_idx:
                        # Replace with tune-up race
                        purpose = tune_up.get("purpose", "sharpening")
                        distance = tune_up.get("distance", "10_mile")
                        name = tune_up.get("name", f"{distance} tune-up")
                        
                        if purpose == "threshold":
                            intensity = "very_hard"
                            notes = [
                                "Race this HARD",
                                "Final threshold effort before goal race"
                            ]
                        else:
                            intensity = "hard"
                            notes = ["Controlled effort, save something for goal race"]
                        
                        # Estimate miles from distance
                        dist_miles = {
                            "5k": 3.1, "10k": 6.2, "10_mile": 10.0,
                            "half": 13.1, "marathon": 26.2
                        }.get(distance, 10.0)
                        
                        week.days[i] = DayPlan(
                            day_of_week=day_idx,
                            workout_type="tune_up_race",
                            name=name,
                            description=f"RACE: {name}",
                            target_miles=dist_miles,
                            intensity=intensity,
                            paces={"race": self._estimate_race_pace(bank, distance)},
                            notes=notes,
                            tss_estimate=dist_miles * 15
                        )
                        break
                
                # Update day before to pre-race
                pre_race_day = (day_idx - 1) % 7
                for i, day in enumerate(week.days):
                    if day.day_of_week == pre_race_day:
                        week.days[i] = DayPlan(
                            day_of_week=pre_race_day,
                            workout_type="pre_race",
                            name="Pre-race easy",
                            description="4-6mi easy + 4x100m strides",
                            target_miles=5.0,
                            intensity="easy",
                            paces={},
                            notes=["Stay loose, save your legs"],
                            tss_estimate=40
                        )
                        break
        
        return weeks
    
    def _estimate_race_pace(self, bank: FitnessBank, distance: str) -> str:
        """Estimate race pace for a distance from VDOT."""
        from services.workout_prescription import calculate_paces_from_vdot, format_pace
        
        paces = calculate_paces_from_vdot(bank.best_vdot)
        
        # Shorter distances = faster than marathon pace
        adjustments = {
            "5k": -0.45,
            "10k": -0.30,
            "10_mile": -0.20,
            "half": -0.12,
            "marathon": 0.0
        }
        
        adj = adjustments.get(distance, 0.0)
        race_pace = paces["marathon"] + adj
        
        return format_pace(race_pace)
    
    def _generate_insights(self,
                          bank: FitnessBank,
                          themes: List[WeekThemePlan],
                          tune_up_races: Optional[List[Dict]]) -> List[str]:
        """Generate counter-conventional notes based on individual data."""
        
        notes = []
        
        # τ1 insights
        if bank.tau1 < 30:
            notes.append(
                f"Your τ1={bank.tau1:.0f}d means faster adaptation than typical runners — "
                f"you can handle steeper ramps and shorter tapers."
            )
        elif bank.tau1 > 45:
            notes.append(
                f"Your τ1={bank.tau1:.0f}d indicates patient fitness building — "
                f"consistency over intensity."
            )
        
        # Experience insight
        if bank.experience_level == ExperienceLevel.ELITE:
            notes.append(
                f"Peak capability: {bank.peak_weekly_miles:.0f}mpw, "
                f"{bank.peak_long_run_miles:.0f}mi long, {bank.peak_mp_long_run_miles:.0f}@MP. "
                f"This plan targets that level."
            )
        
        # Constraint insight
        if bank.constraint_type == ConstraintType.INJURY:
            notes.append(
                f"Returning from {bank.constraint_details}. "
                f"Plan protects first {2 if bank.current_weekly_miles/bank.peak_weekly_miles > 0.3 else 3} weeks, "
                f"then progressive build."
            )
        
        # Dual race insight
        if tune_up_races:
            for tune_up in tune_up_races:
                name = tune_up.get("name", "Tune-up")
                purpose = tune_up.get("purpose", "sharpening")
                
                if purpose == "threshold":
                    notes.append(
                        f"{name}: Race this HARD. "
                        f"It's your final threshold effort — the 8-day recovery is enough."
                    )
                else:
                    notes.append(
                        f"{name}: Controlled effort. Save legs for goal race."
                    )
        
        # Race performance insight
        if bank.best_race:
            r = bank.best_race
            cond = f" ({r.conditions})" if r.conditions else ""
            notes.append(
                f"Your {r.distance} at {int(r.pace_per_mile)}:{int((r.pace_per_mile % 1) * 60):02d}/mi{cond} "
                f"proves VDOT {bank.best_vdot:.0f}. Paces are based on YOUR data."
            )
        
        return notes
    
    def _predict_race(self, bank: FitnessBank, distance: str, 
                      goal_time: Optional[str]) -> tuple:
        """Predict race time based on fitness bank."""
        
        from services.fitness_bank import vdot_equivalent_time
        
        distance_m = {
            "5k": 5000, "10k": 10000, "10_mile": 16093,
            "half": 21097, "marathon": 42195
        }.get(distance, 42195)
        
        # Predict from best VDOT
        predicted_sec = vdot_equivalent_time(bank.best_vdot, distance_m)
        
        hours = predicted_sec // 3600
        minutes = (predicted_sec % 3600) // 60
        seconds = predicted_sec % 60
        
        if hours > 0:
            predicted = f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            predicted = f"{minutes}:{seconds:02d}"
        
        # Confidence interval based on data quality
        if bank.constraint_type == ConstraintType.INJURY:
            ci = "±5-8 min (injury recovery uncertainty)"
        elif len(bank.race_performances) >= 3:
            ci = "±2-3 min"
        else:
            ci = "±4-5 min"
        
        return predicted, ci
    
    def _assess_confidence(self, bank: FitnessBank) -> str:
        """Assess model confidence based on data."""
        
        if len(bank.race_performances) >= 5 and bank.weeks_since_peak < 12:
            return "high"
        elif len(bank.race_performances) >= 2:
            return "medium"
        else:
            return "low"
    
    def _generate_minimal_plan(self, bank: FitnessBank, race_date: date, 
                              race_distance: str) -> ConstraintAwarePlan:
        """Generate minimal plan when race is very soon."""
        
        # Just race week
        workout_gen = WorkoutPrescriptionGenerator(bank)
        week = workout_gen.generate_week(
            theme=WeekTheme.RACE,
            week_number=1,
            total_weeks=1,
            target_miles=40,
            start_date=race_date - timedelta(days=race_date.weekday())
        )
        
        return ConstraintAwarePlan(
            weeks=[week],
            total_weeks=1,
            total_miles=week.total_miles,
            race_date=race_date,
            race_distance=race_distance,
            tune_up_races=[],
            fitness_bank=bank.to_dict(),
            tau1=bank.tau1,
            tau2=bank.tau2,
            model_confidence="low",
            counter_conventional_notes=["Very short prep — trust your banked fitness."],
            predicted_time=None,
            prediction_ci=None
        )


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def generate_constraint_aware_plan(
    athlete_id: UUID,
    race_date: date,
    race_distance: str,
    db: Session,
    goal_time: Optional[str] = None,
    tune_up_races: Optional[List[Dict]] = None
) -> ConstraintAwarePlan:
    """Generate a constraint-aware plan for an athlete."""
    
    planner = ConstraintAwarePlanner(db)
    return planner.generate_plan(
        athlete_id=athlete_id,
        race_date=race_date,
        race_distance=race_distance,
        goal_time=goal_time,
        tune_up_races=tune_up_races
    )
