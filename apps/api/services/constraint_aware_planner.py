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
from typing import List, Dict, Optional, Any
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
    WeekTheme,
    WeekThemePlan
)
from services.workout_prescription import (
    WorkoutPrescriptionGenerator,
    WeekPlan,
    DayPlan
)
from services.plan_framework.load_context import build_load_context, history_anchor_date
from services.plan_framework.phase_builder import PhaseBuilder
from services.plan_framework.volume_tiers import VolumeTierClassifier
from services.plan_framework.mp_progression import MPProgressionPlanner, MPWeek
from services.plan_framework.week_generator import generate_plan_week
from services.race_signal_contract import normalize_distance_alias

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level helpers for GeneratedWorkout → WeekPlan conversion (T3)
# ---------------------------------------------------------------------------

_INTENSITY_MAP: Dict[str, str] = {
    "easy": "easy",
    "recovery": "easy",
    "rest": "rest",
    "easy_strides": "easy",
    "long": "easy",
    "long_run": "easy",
    "easy_long": "easy",
    "long_mp": "moderate",
    "long_hmp": "moderate",
    "medium_long": "easy",
    "medium_long_mp": "moderate",
    "quality": "hard",
    "threshold": "threshold",
    "threshold_intervals": "threshold",
    "threshold_continuous": "threshold",
    "intervals": "hard",
    "vo2max": "hard",
    "strides": "easy",
    "hills": "hard",
}


def _workout_intensity(workout_type: Optional[str]) -> str:
    return _INTENSITY_MAP.get(workout_type or "rest", "easy")


def _workouts_to_week_plan(
    workouts: List[Any],
    week_num: int,
    phase: Any,
    week_start: date,
    is_cutback: bool = False,
) -> WeekPlan:
    """Convert List[GeneratedWorkout] → WeekPlan.

    T3-3: sets ``theme`` to the phase name (a plain string) instead of a
    ``WeekTheme`` enum value, eliminating ``[?]`` display in clients.
    """
    days = []
    for wo in workouts:
        days.append(DayPlan(
            day_of_week=wo.day,
            workout_type=wo.workout_type or "rest",
            name=wo.title or wo.workout_type or "",
            description=wo.description or "",
            target_miles=float(wo.distance_miles or 0),
            intensity=_workout_intensity(wo.workout_type),
            paces={"default": wo.pace_description} if wo.pace_description else {},
            notes=[],
        ))
    total = sum(d.target_miles for d in days)
    return WeekPlan(
        week_number=week_num,
        theme=phase.phase_type.value,  # T3-3: phase_type string (e.g. "race_specific")
        start_date=week_start,
        days=days,
        total_miles=round(total, 1),
        is_cutback=is_cutback,
    )


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
        
        # 2. Build phase structure and volume progression via framework engine (T3-1)
        horizon_weeks = max(4, (race_date - date.today()).days // 7)

        tier_classifier = VolumeTierClassifier()

        # Tier classification: use the athlete's DOCUMENTED HISTORY, not their
        # current (potentially depressed post-race/injury) mileage.
        # A 35mpw post-marathon athlete who has averaged 65mpw for months is HIGH
        # tier — their current mileage is a recovery artifact, not their capability.
        # Use bank.peak_weekly_miles (what they've DEMONSTRATED) for tier structure;
        # applied_peak drives volume targets only.
        # Exception: injured athletes need conservative structure regardless of history.
        applied_peak = volume_contract.get("applied_peak") or bank.current_weekly_miles
        history_peak = bank.peak_weekly_miles or bank.current_weekly_miles or 0.0
        if bank.constraint_type == ConstraintType.INJURY:
            # Injured: structure must match current safe capacity, not prior history.
            effective_tier_volume = bank.current_weekly_miles
        else:
            effective_tier_volume = max(bank.current_weekly_miles, history_peak)
        tier = tier_classifier.classify(effective_tier_volume, race_distance)

        phase_builder = PhaseBuilder()
        phases = phase_builder.build_phases(
            distance=race_distance,
            duration_weeks=horizon_weeks,
            tier=tier.value,
        )

        if not phases:
            logger.warning("No phases generated - race date too soon?")
            return self._generate_minimal_plan(bank, race_date, race_distance)

        volumes = tier_classifier.calculate_volume_progression(
            tier=tier,
            distance=race_distance,
            starting_volume=bank.current_weekly_miles,
            plan_weeks=horizon_weeks,
            peak_volume_override=applied_peak,
        )
        cutback_weeks_set = phase_builder.get_cutback_weeks(phases)

        # Days per week: infer from bank rest pattern.
        # Cap at 6 for constraint-aware plans — the 7-day structure puts a
        # second quality session on Saturday (day 5), the day before the long
        # run. The 6-day structure keeps Saturday as easy_strides.
        days_per_week = max(3, min(6, 7 - len(bank.typical_rest_days or [])))

        # Easy-long floor: prefer L30 max seed from load_ctx, fall back to bank's
        # current long run miles (more recent than the average), then average.
        # Take the MAX of both sources: test/sparse DB data should not REDUCE the
        # floor below the athlete's bank-established long run capability.
        l30_from_ctx = (load_ctx.l30_max_easy_long_mi if load_ctx is not None else None) or 0.0
        bank_known = (
            getattr(bank, "current_long_run_miles", None)
            or getattr(bank, "average_long_run_miles", None)
            or 0.0
        )
        l30_floor: Optional[float] = max(l30_from_ctx, float(bank_known)) or None

        # Marathon MP block — compute per-week long/medium-long types
        mp_sequence: Dict[int, MPWeek] = {}
        mp_block_start_week = 0
        if race_distance == "marathon":
            mp_phase_weeks = [
                w for p in phases
                if p.phase_type.value in ("marathon_specific", "race_specific")
                for w in p.weeks
            ]
            if mp_phase_weeks:
                mp_block_start_week = min(mp_phase_weeks)
                mp_tier = tier.value if tier.value in ("low", "mid", "high", "elite") else "mid"
                sequence = MPProgressionPlanner().build_sequence(mp_tier, len(mp_phase_weeks))
                mp_sequence = {s.week_in_phase: s for s in sequence}

        # Plan start = Monday of week 1.
        # race_date - N weeks may land on any day; normalise to Monday so all
        # week.start_date values are Mondays and date arithmetic in the save
        # function is consistent.
        raw_start = race_date - timedelta(weeks=horizon_weeks)
        plan_start = raw_start - timedelta(days=raw_start.weekday())
        # After normalization plan_start may be up to 6 days earlier than raw_start,
        # so the race might now be in week N+1.  Recompute horizon_weeks using
        # ceiling division so the last generated week always contains the race.
        # ceil_div trick: -(-a // b) == math.ceil(a / b) without float conversion.
        horizon_weeks = max(4, -(-((race_date - plan_start).days) // 7))  # P0-GATE: GREEN

        # 3. Generate each week via the public framework interface (T3-2)
        weeks: List[WeekPlan] = []
        easy_long_state: Dict[str, Any] = {
            "previous_mi": None,
            "floor_mi": l30_floor,
            "floor_applied": False,
        }
        mp_long_run_count = 0

        # Simultaneous-ramp guard state.
        # Rule: build volume first, then add intensity.  If volume is climbing
        # this week, freeze quality work at the prior week's level — don't reduce
        # it, just don't escalate it.  Once volume stabilises, intensity resumes.
        prev_week_volume: float = 0.0
        prev_threshold_continuous_min: Optional[int] = None
        prev_threshold_intervals: Optional[tuple] = None

        for phase in phases:
            for week_num in phase.weeks:
                if week_num > horizon_weeks:
                    continue

                week_idx = week_num - 1
                week_volume = float(
                    volumes[week_idx] if week_idx < len(volumes) else volumes[-1]
                )
                week_volume = self._apply_volume_contract_bounds(week_volume, volume_contract)

                # Injury return: conservatively cap early weeks
                if bank.constraint_type == ConstraintType.INJURY and week_num <= 4:
                    safe_max = self._calculate_safe_weekly(
                        bank.current_weekly_miles, week_num, bank.tau1, bank.peak_weekly_miles
                    )
                    week_volume = min(week_volume, safe_max)

                week_in_phase = week_num - phase.weeks[0] + 1
                is_cutback = week_num in cutback_weeks_set

                # MP / HMP flags
                will_have_mp_long = False
                will_have_mp_medium_long = False
                will_have_hmp_long = False
                if (
                    race_distance == "marathon"
                    and phase.phase_type.value in ("marathon_specific", "race_specific")
                    and tier.value != "builder"
                ):
                    mp_block_week = week_num - mp_block_start_week + 1
                    mp_info = mp_sequence.get(mp_block_week)
                    if mp_info:
                        will_have_mp_long = mp_info.long_type == "long_mp"
                        will_have_mp_medium_long = mp_info.medium_long_type == "medium_long_mp"
                elif race_distance == "half_marathon" and tier.value != "builder":
                    from services.plan_framework.generator import PlanGenerator as _PG
                    will_have_hmp_long = _PG().will_week_have_hmp_long(
                        phase=phase,
                        week_in_phase=week_in_phase,
                        is_cutback=is_cutback,
                        distance=race_distance,
                    )

                if will_have_mp_long:
                    mp_long_run_count += 1

                week_start = plan_start + timedelta(weeks=week_idx)
                week_easy_long_state = dict(easy_long_state)

                # Simultaneous-ramp guard: if this week's volume is climbing
                # above last week's, freeze quality at the established level.
                # Already-established intensity is kept; only escalation is blocked.
                volume_building = (
                    prev_week_volume > 0
                    and week_volume > prev_week_volume * 1.05
                )
                freeze_threshold_continuous = prev_threshold_continuous_min if volume_building else None
                freeze_threshold_intervals = prev_threshold_intervals if volume_building else None

                workouts = generate_plan_week(
                    week=week_num,
                    phase=phase,
                    week_in_phase=week_in_phase,
                    weekly_volume=week_volume,
                    days_per_week=days_per_week,
                    distance=race_distance,
                    tier=tier.value,
                    duration_weeks=horizon_weeks,
                    is_cutback=is_cutback,
                    is_mp_long_week=will_have_mp_long,
                    is_hmp_long_week=will_have_hmp_long,
                    is_mp_medium_long_week=will_have_mp_medium_long,
                    mp_week=mp_long_run_count,
                    easy_long_state=week_easy_long_state,
                    start_date=week_start,
                    prev_threshold_continuous_min=freeze_threshold_continuous,
                    prev_threshold_intervals=freeze_threshold_intervals,
                )

                # Update simultaneous-ramp guard state for next week.
                prev_week_volume = week_volume
                for wo in workouts:
                    if wo.workout_type == "threshold" and wo.segments:
                        for seg in wo.segments:
                            if isinstance(seg, dict) and seg.get("type") == "threshold":
                                dm = seg.get("duration_min")
                                if dm is not None:
                                    prev_threshold_continuous_min = int(dm)
                                    break
                    if wo.workout_type == "threshold_intervals" and wo.segments:
                        for seg in wo.segments:
                            if isinstance(seg, dict) and seg.get("type") == "intervals":
                                r, d = seg.get("reps"), seg.get("duration_min")
                                if r is not None and d is not None:
                                    prev_threshold_intervals = (int(r), int(d))
                                    break

                # Track long run for next week's easy_long_state
                for wo in workouts:
                    if (
                        wo.workout_type in {"long", "long_run", "long_mp", "long_hmp"}
                        and (wo.distance_miles or 0) > 0
                    ):
                        easy_long_state["previous_mi"] = wo.distance_miles
                        easy_long_state["floor_mi"] = None
                        easy_long_state["floor_applied"] = True

                # W1 long run cap.
                # Primary rule (Substack: "Forget the 10% Rule", Takeaway 1):
                #   First long run = L30_non_race_max + 1 mile.  This respects
                #   the athlete's actual recent training baseline without spiking.
                # Fallback (no L30 data): current_weekly_miles / days * 2.
                # Hard ceiling: median * 0.40 (never exceed 40% of a typical week).
                # Distance ceiling: 10K/5K plans cap long run at 37% of W1 volume
                #   so the "tenk_long_run_dominance" quality gate (40% ratio) is not
                #   breached when L30+1 gives a large value after a marathon race.
                if week_num == 1 and bank.current_weekly_miles:
                    if l30_floor and l30_floor > 0:
                        # L30 floor is already the non-race max; +1 is the safe first step.
                        w1_long_cap = float(l30_floor) + 1.0
                    else:
                        w1_long_cap = bank.current_weekly_miles / max(1, days_per_week) * 2.0
                    if bank.recent_8w_median_weekly_miles:
                        w1_long_cap = min(w1_long_cap, bank.recent_8w_median_weekly_miles * 0.40)
                    long_types = {"long", "long_run", "long_mp", "long_hmp", "easy_long"}
                    for wo in workouts:
                        if wo.workout_type in long_types and (wo.distance_miles or 0) > w1_long_cap:
                            wo.distance_miles = round(w1_long_cap, 1)

                    # For short-race plans the long run must not dominate the week.
                    # The quality gate checks ratio = long / actual_total_miles (not
                    # long / target volume), so we must cap against the actual total
                    # after prescription, not the planned week_volume.
                    if race_distance in ("10k", "5k"):
                        actual_total_w1 = sum(
                            (wo.distance_miles or 0) for wo in workouts
                        )
                        if actual_total_w1 > 0:
                            dominance_cap = actual_total_w1 * 0.37
                            for wo in workouts:
                                if wo.workout_type in long_types and (wo.distance_miles or 0) > dominance_cap:
                                    wo.distance_miles = round(dominance_cap, 1)

                    # After applying W1 cap, update easy_long_state to the reduced
                    # value so subsequent weeks compute their progressions from the
                    # actual prescription, not the pre-cap baseline.
                    for wo in workouts:
                        if wo.workout_type in {"long", "long_run", "long_mp", "long_hmp"} and (wo.distance_miles or 0) > 0:
                            easy_long_state["previous_mi"] = wo.distance_miles
                            break

                # Convert List[GeneratedWorkout] → WeekPlan (T3-3: theme = phase name)
                week_start_date = plan_start + timedelta(weeks=week_idx)
                week_plan = _workouts_to_week_plan(workouts, week_num, phase, week_start_date, is_cutback=is_cutback)
                weeks.append(week_plan)
        
        # 5. Inject race day: the last day of the last week is the goal race.
        if weeks:
            last_week = weeks[-1]
            race_day_of_week = race_date.weekday()  # 0=Mon … 6=Sun
            race_day = DayPlan(
                day_of_week=race_day_of_week,
                workout_type="race",
                name=f"Race Day — {race_distance.replace('_', ' ').title()}",
                description="Goal race. Warm up well, execute your plan.",
                target_miles=0.0,
                intensity="race",
                paces={},
                notes=[],
            )
            # Replace any existing day on that day-of-week, or append.
            existing = [d for d in last_week.days if d.day_of_week != race_day_of_week]
            last_week.days = sorted(existing + [race_day], key=lambda d: d.day_of_week)

        # 7. Insert tune-up race specifics
        if tune_up_races:
            weeks = self._insert_tune_up_details(weeks, tune_up_races, bank)
        
        # 8. Generate counter-conventional notes
        notes = self._generate_insights(bank, weeks, tune_up_races)
        
        # 9. Calculate predictions
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
                        name = tune_up.get("name") or f"{distance} tune-up"
                        
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
                          weeks_or_themes: Any,
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
