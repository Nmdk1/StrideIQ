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
from typing import List, Dict, Optional, Tuple, Any
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
from services.plan_framework.load_context import build_load_context, history_anchor_date
from services.race_signal_contract import normalize_distance_alias

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

    @property
    def distance(self) -> str:
        """Alias for race_distance — satisfies PlanValidator interface."""
        return self.race_distance
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
    prediction_scenarios: Dict[str, Dict[str, str]]
    prediction_rationale_tags: List[str]
    prediction_uncertainty_reason: Optional[str]
    volume_contract: Dict[str, Any] = field(default_factory=dict)
    quality_gate_fallback: bool = False
    quality_gate_reasons: List[str] = field(default_factory=list)
    
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
                "ci": self.prediction_ci,
                "uncertainty_reason": self.prediction_uncertainty_reason,
                "rationale_tags": self.prediction_rationale_tags,
                "scenarios": self.prediction_scenarios,
            },
            "volume_contract": self.volume_contract,
            "quality_gate_fallback": self.quality_gate_fallback,
            "quality_gate_reasons": self.quality_gate_reasons,
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
                     tune_up_races: Optional[List[Dict]] = None,
                     target_peak_weekly_miles: Optional[float] = None,
                     target_peak_weekly_range: Optional[Dict[str, float]] = None,
                     quality_gate_fallback: bool = False,
                     quality_gate_reasons: Optional[List[str]] = None) -> ConstraintAwarePlan:
        """
        Generate a complete constraint-aware plan.
        """
        logger.info(f"Generating constraint-aware plan for athlete {athlete_id}")
        race_distance = normalize_distance_alias(race_distance)
        
        # 1. Get Fitness Bank
        bank = get_fitness_bank(athlete_id, self.db)
        logger.info(f"Fitness Bank: peak={bank.peak_weekly_miles:.0f}mpw, "
                   f"current={bank.current_weekly_miles:.0f}mpw, "
                   f"constraint={bank.constraint_type.value}")
        rationale_tags: List[str] = []
        volume_contract = self._build_volume_contract(
            bank=bank,
            race_distance=race_distance,
            target_peak_weekly_miles=target_peak_weekly_miles,
            target_peak_weekly_range=target_peak_weekly_range,
        )
        if volume_contract.get("source") == "trusted_recent_band":
            rationale_tags.append("untrusted_peak_suppressed")

        # Optional P5 bridge: bring the same L30/D4 context used in semi-custom
        # into constraint-aware generation so experienced athletes get a sane week-1
        # easy-long seed and history override behavior.
        load_ctx = None
        try:
            if self.db is not None:
                try:
                    reference_date = history_anchor_date(None, self.db, athlete_id)
                except Exception:
                    reference_date = date.today()
                load_ctx = build_load_context(
                    athlete_id,
                    self.db,
                    reference_date,
                )
                if load_ctx.history_override_easy_long:
                    rationale_tags.append("d4_history_override")
        except Exception as ex:
            logger.warning("constraint-aware load_context unavailable, continuing with fitness-bank only: %s", ex)
        
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
        workout_generator = WorkoutPrescriptionGenerator(
            bank,
            race_distance=race_distance,
            load_easy_long_floor_mi=(load_ctx.l30_max_easy_long_mi if load_ctx is not None else None),
            load_history_override_easy_long=bool(load_ctx.history_override_easy_long) if load_ctx is not None else False,
            load_count_long_15plus=int(load_ctx.count_long_15plus) if load_ctx is not None else 0,
            load_count_long_18plus=int(load_ctx.count_long_18plus) if load_ctx is not None else 0,
            load_recency_last_18plus_days=load_ctx.recency_last_18plus_days if load_ctx is not None else None,
        )
        weeks = []
        
        for theme_plan in themes:
            target_miles = theme_plan.target_volume_pct * float(volume_contract.get("applied_peak", bank.peak_weekly_miles))
            target_miles = self._apply_volume_contract_bounds(target_miles, volume_contract)
            
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
        predicted, ci, scenarios, prediction_rationale_tags, uncertainty_reason = self._predict_race(
            bank,
            race_distance,
            goal_time,
        )
        prediction_rationale_tags = list(dict.fromkeys(prediction_rationale_tags + rationale_tags))
        
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
            prediction_ci=ci,
            prediction_scenarios=scenarios,
            prediction_rationale_tags=prediction_rationale_tags,
            prediction_uncertainty_reason=uncertainty_reason,
            volume_contract=volume_contract,
            quality_gate_fallback=quality_gate_fallback,
            quality_gate_reasons=quality_gate_reasons or [],
        )

    def _is_peak_plausible(self, peak: float, band_min: float, band_max: float, peak_confidence: str) -> bool:
        if peak <= 0:
            return False
        if peak_confidence == "low":
            return False
        if band_max <= 0:
            return True
        return peak <= band_max * 1.35

    def _build_volume_contract(
        self,
        *,
        bank: FitnessBank,
        race_distance: str,
        target_peak_weekly_miles: Optional[float],
        target_peak_weekly_range: Optional[Dict[str, float]],
    ) -> Dict[str, Any]:
        band_center = bank.recent_8w_median_weekly_miles or bank.current_weekly_miles or bank.peak_weekly_miles
        band_max = bank.recent_16w_p90_weekly_miles or max(band_center, bank.current_weekly_miles)
        if band_max <= 0:
            band_max = max(25.0, bank.current_weekly_miles or 0.0, bank.peak_weekly_miles * 0.8)
        band_min = max(10.0, min(band_center, band_max) * 0.9)
        requested_peak = None
        if target_peak_weekly_miles is not None:
            requested_peak = float(target_peak_weekly_miles)
        elif target_peak_weekly_range:
            rmin = float(target_peak_weekly_range.get("min", 0) or 0)
            rmax = float(target_peak_weekly_range.get("max", 0) or 0)
            if rmin > 0 and rmax > 0:
                requested_peak = (rmin + rmax) / 2.0
            elif rmax > 0:
                requested_peak = rmax
            elif rmin > 0:
                requested_peak = rmin

        peak_plausible = self._is_peak_plausible(
            bank.peak_weekly_miles,
            band_min,
            band_max,
            bank.peak_confidence,
        )
        source = "trusted_peak" if peak_plausible else "trusted_recent_band"
        applied_peak = bank.peak_weekly_miles if peak_plausible else band_max

        clamped = False
        clamp_reason = None
        if requested_peak is not None:
            source = "athlete_override"
            override_floor = max(10.0, band_min * 0.8)
            override_ceiling = max(override_floor, band_max * 1.2)
            applied_peak = max(override_floor, min(override_ceiling, requested_peak))
            clamped = abs(applied_peak - requested_peak) > 1e-6
            if clamped:
                clamp_reason = (
                    f"Requested peak {requested_peak:.1f}mpw outside safety band "
                    f"{override_floor:.1f}-{override_ceiling:.1f}mpw."
                )

        # 10K plans can remain high-mileage; only soften extreme long-distance spillover.
        if race_distance.lower() == "10k" and source != "athlete_override":
            applied_peak = min(applied_peak, max(band_max, band_center))

        return {
            "band_min": round(band_min, 1),
            "band_max": round(band_max, 1),
            "source": source,
            "peak_confidence": bank.peak_confidence,
            "requested_peak": round(requested_peak, 1) if requested_peak is not None else None,
            "applied_peak": round(applied_peak, 1),
            "clamped": clamped,
            "clamp_reason": clamp_reason,
        }

    def _apply_volume_contract_bounds(self, target_miles: float, volume_contract: Dict[str, Any]) -> float:
        band_min = float(volume_contract.get("band_min", 0) or 0)
        band_max = float(volume_contract.get("band_max", 0) or 0)
        if band_max <= 0:
            return target_miles
        lower = max(8.0, band_min * 0.75)
        upper = max(lower, band_max * 1.10)
        return max(lower, min(upper, target_miles))
    
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
                        distance = normalize_distance_alias(tune_up.get("distance", "10_mile"))
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
                            "5k": 3.1,
                            "10k": 6.2,
                            "10_mile": 10.0,
                            "half_marathon": 13.1,
                            "marathon": 26.2,
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
        """Estimate race pace for a distance from RPI."""
        from services.workout_prescription import calculate_paces_from_rpi, format_pace
        
        distance = normalize_distance_alias(distance)
        paces = calculate_paces_from_rpi(bank.best_rpi)
        
        # Shorter distances = faster than marathon pace
        adjustments = {
            "5k": -0.45,
            "10k": -0.30,
            "10_mile": -0.20,
            "half_marathon": -0.12,
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
                f"proves RPI {bank.best_rpi:.0f}. Paces are based on YOUR data."
            )
        
        return notes
    
    def _format_time_seconds(self, total_seconds: int) -> str:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    def _scenario_confidence(
        self,
        *,
        races_count: int,
        quality_sessions_28d: int,
        is_injury_return: bool,
    ) -> str:
        """
        Confidence is monotonic with quality continuity: if quality continuity
        decreases while other factors are unchanged, confidence cannot increase.
        """
        race_score = 2 if races_count >= 3 else (1 if races_count >= 1 else 0)
        quality_score = 2 if quality_sessions_28d >= 6 else (1 if quality_sessions_28d >= 3 else 0)
        injury_penalty = 1 if is_injury_return else 0
        score = min(race_score, quality_score) - injury_penalty
        if score >= 2:
            return "high"
        if score >= 1:
            return "medium"
        return "low"

    def _predict_race(self, bank: FitnessBank, distance: str, goal_time: Optional[str]) -> tuple:
        """Predict race time using conservative/base/aggressive scenarios."""
        from services.fitness_bank import rpi_equivalent_time

        distance = normalize_distance_alias(distance)
        distance_m = {
            "5k": 5000,
            "10k": 10000,
            "10_mile": 16093,
            "half_marathon": 21097,
            "marathon": 42195,
        }.get(distance, 42195)

        races_count = len(bank.race_performances)
        is_injury_return = bank.constraint_type == ConstraintType.INJURY
        quality_sessions_28d = int(getattr(bank, "recent_quality_sessions_28d", 0) or 0)
        current_ratio = (
            bank.current_weekly_miles / bank.peak_weekly_miles
            if bank.peak_weekly_miles > 0
            else 1.0
        )

        rationale_tags: List[str] = ["proven_peak"]
        if races_count > 0:
            rationale_tags.append("recent_form")
        if is_injury_return:
            rationale_tags.append("injury_return")
        if quality_sessions_28d < 3:
            rationale_tags.append("quality_gap")

        base_rpi = bank.best_rpi
        if base_rpi is None:
            # No race history — use a conservative estimate from volume
            base_rpi = max(25.0, min(45.0, 30.0 + bank.current_weekly_miles * 0.20))
            rationale_tags.append("no_race_history")
        if is_injury_return:
            base_rpi -= 1.0
        if current_ratio < 0.6:
            base_rpi -= 0.8
        elif current_ratio < 0.75:
            base_rpi -= 0.4

        if quality_sessions_28d == 0:
            base_rpi -= 1.5
        elif quality_sessions_28d <= 2:
            base_rpi -= 0.9
        elif quality_sessions_28d <= 4:
            base_rpi -= 0.4

        conservative_rpi = base_rpi - (1.0 if is_injury_return else 0.5)
        aggressive_rpi = max(base_rpi + (0.5 if quality_sessions_28d >= 3 else 0.15), (bank.best_rpi or base_rpi) - 0.2)

        # Keep ranges sane.
        conservative_rpi = max(20.0, conservative_rpi)
        base_rpi = max(20.0, base_rpi)
        aggressive_rpi = min(85.0, aggressive_rpi)

        conservative_sec = rpi_equivalent_time(conservative_rpi, distance_m)
        base_sec = rpi_equivalent_time(base_rpi, distance_m)
        aggressive_sec = rpi_equivalent_time(aggressive_rpi, distance_m)

        scenarios = {
            "conservative": {
                "time": self._format_time_seconds(conservative_sec),
                "confidence": self._scenario_confidence(
                    races_count=races_count,
                    quality_sessions_28d=max(0, quality_sessions_28d - 1),
                    is_injury_return=is_injury_return,
                ),
            },
            "base": {
                "time": self._format_time_seconds(base_sec),
                "confidence": self._scenario_confidence(
                    races_count=races_count,
                    quality_sessions_28d=quality_sessions_28d,
                    is_injury_return=is_injury_return,
                ),
            },
            "aggressive": {
                "time": self._format_time_seconds(aggressive_sec),
                "confidence": self._scenario_confidence(
                    races_count=races_count,
                    quality_sessions_28d=quality_sessions_28d,
                    is_injury_return=is_injury_return,
                ),
            },
        }

        predicted = scenarios["base"]["time"]
        ci_minutes_low = max(1, int((base_sec - conservative_sec) / 60))
        ci_minutes_high = max(1, int((aggressive_sec - base_sec) / 60))
        ci = f"-{ci_minutes_low}/+{ci_minutes_high} min"

        uncertainty_reason = None
        if is_injury_return and quality_sessions_28d < 3:
            uncertainty_reason = "Return-from-injury with limited recent quality continuity."
        elif quality_sessions_28d < 3:
            uncertainty_reason = "Limited recent quality continuity increases uncertainty."
        elif races_count < 2:
            uncertainty_reason = "Limited race-history depth increases uncertainty."

        return predicted, ci, scenarios, rationale_tags, uncertainty_reason
    
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
        workout_gen = WorkoutPrescriptionGenerator(bank, race_distance=race_distance)
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
            prediction_ci=None,
            prediction_scenarios={
                "conservative": {"time": "N/A", "confidence": "low"},
                "base": {"time": "N/A", "confidence": "low"},
                "aggressive": {"time": "N/A", "confidence": "low"},
            },
            prediction_rationale_tags=["insufficient_data"],
            prediction_uncertainty_reason="Very short prep window; prediction not reliable.",
            volume_contract={
                "band_min": 20.0,
                "band_max": 40.0,
                "source": "trusted_recent_band",
                "peak_confidence": bank.peak_confidence,
                "requested_peak": None,
                "applied_peak": 40.0,
                "clamped": False,
                "clamp_reason": None,
            },
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
    tune_up_races: Optional[List[Dict]] = None,
    target_peak_weekly_miles: Optional[float] = None,
    target_peak_weekly_range: Optional[Dict[str, float]] = None,
    quality_gate_fallback: bool = False,
    quality_gate_reasons: Optional[List[str]] = None,
) -> ConstraintAwarePlan:
    """Generate a constraint-aware plan for an athlete."""
    
    planner = ConstraintAwarePlanner(db)
    return planner.generate_plan(
        athlete_id=athlete_id,
        race_date=race_date,
        race_distance=race_distance,
        goal_time=goal_time,
        tune_up_races=tune_up_races,
        target_peak_weekly_miles=target_peak_weekly_miles,
        target_peak_weekly_range=target_peak_weekly_range,
        quality_gate_fallback=quality_gate_fallback,
        quality_gate_reasons=quality_gate_reasons,
    )
