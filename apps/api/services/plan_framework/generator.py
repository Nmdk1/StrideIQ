"""
Plan Generator

Main orchestrator for plan generation.
Coordinates all components to produce complete training plans.

Usage:
    generator = PlanGenerator(db)
    
    # Generate standard plan
    plan = generator.generate_standard(
        distance="marathon",
        duration_weeks=18,
        tier="mid",
        days_per_week=6
    )
    
    # Generate semi-custom plan
    plan = generator.generate_semi_custom(
        athlete_goal=goal,
        training_paces=paces
    )
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import date, timedelta
from uuid import UUID
from dataclasses import dataclass

from sqlalchemy.orm import Session

from .constants import VolumeTier, PlanTier
from .volume_tiers import VolumeTierClassifier
from .phase_builder import PhaseBuilder, TrainingPhase
from .workout_scaler import WorkoutScaler
from .workout_variant_dispatch import resolve_workout_variant_id
from .pace_engine import PaceEngine, TrainingPaces
from .cache import PlanCacheService
from .load_context import (
    build_load_context,
    compute_d4_long_run_override_and_stats,
    easy_long_floor_miles_from_l30,
    effective_starting_weekly_miles_semi_custom,
    history_anchor_date,
)

logger = logging.getLogger(__name__)

# P2: weighted easy fill — quality/long neighbors (docs/specs/PLAN_COACHED_OUTPUT_AND_LOAD_CONTRACT.md).
_EASY_FILL_QUALITY_TYPES = frozenset({
    "threshold", "threshold_intervals", "intervals",
    "long_mp", "long_hmp", "mp_touch", "hills", "repetitions", "tempo",
})
_EASY_FILL_LONG_TYPES = frozenset({"long", "long_mp", "long_hmp"})


def _easy_fill_adjacency_weight(day: int, by_day: Dict[int, Any]) -> float:
    """
    Relative share weight for an easy slot (same calendar week, Mon=0).
    Lower = recovery / pre-long compression; higher = standalone aerobic day.
    """
    prev_w = by_day.get(day - 1)
    next_w = by_day.get(day + 1)
    after_quality = bool(
        prev_w is not None
        and (prev_w.workout_type or "") in _EASY_FILL_QUALITY_TYPES
    )
    before_long = bool(
        next_w is not None
        and (next_w.workout_type or "") in _EASY_FILL_LONG_TYPES
    )
    if after_quality and before_long:
        return 0.56  # 0.7 * 0.8
    if after_quality:
        return 0.7
    if before_long:
        return 0.8
    return 1.2


@dataclass
class GeneratedWorkout:
    """A single workout in the generated plan."""
    week: int
    day: int  # 0=Monday, 6=Sunday
    day_name: str
    date: Optional[date]
    
    workout_type: str
    title: str
    description: str
    
    phase: str
    phase_name: str
    
    distance_miles: Optional[float]
    duration_minutes: Optional[int]
    
    pace_description: str
    segments: Optional[List[Dict[str, Any]]]
    
    # Option A/B
    option: str
    workout_variant_id: Optional[str] = None
    option_b: Optional['GeneratedWorkout'] = None


def _extract_mp_miles_from_long_mp(workout: GeneratedWorkout) -> Optional[int]:
    """MP miles from option A segments (single marathon_pace block)."""
    if workout.workout_type != "long_mp" or not workout.segments:
        return None
    for seg in workout.segments:
        if not isinstance(seg, dict) or seg.get("type") != "marathon_pace":
            continue
        dm = seg.get("distance_miles")
        if dm is None:
            return None
        return int(round(float(dm)))
    return None


def _extract_threshold_continuous_minutes(workout: GeneratedWorkout) -> Optional[int]:
    if workout.workout_type != "threshold" or not workout.segments:
        return None
    for seg in workout.segments:
        if not isinstance(seg, dict) or seg.get("type") != "threshold":
            continue
        dm = seg.get("duration_min")
        if dm is None:
            return None
        return int(dm)
    return None


def _extract_threshold_intervals_shape(workout: GeneratedWorkout) -> Optional[Tuple[int, int]]:
    if workout.workout_type != "threshold_intervals" or not workout.segments:
        return None
    for seg in workout.segments:
        if not isinstance(seg, dict) or seg.get("type") != "intervals":
            continue
        r, d = seg.get("reps"), seg.get("duration_min")
        if r is None or d is None:
            return None
        return (int(r), int(d))
    return None


@dataclass
class GeneratedPlan:
    """Complete generated training plan."""
    
    # Identification
    plan_tier: PlanTier
    distance: str
    duration_weeks: int
    volume_tier: str
    days_per_week: int
    
    # Athlete info (if personalized)
    athlete_id: Optional[UUID]
    rpi: Optional[float]
    
    # Plan dates
    start_date: Optional[date]
    end_date: Optional[date]
    race_date: Optional[date]
    
    # Structure
    phases: List[TrainingPhase]
    workouts: List[GeneratedWorkout]
    
    # Volume progression
    weekly_volumes: List[float]
    peak_volume: float
    
    # Summary
    total_miles: float
    total_quality_sessions: int
    
    def get_week(self, week_num: int) -> List[GeneratedWorkout]:
        """Get all workouts for a specific week."""
        return [w for w in self.workouts if w.week == week_num]
    
    def get_phase_weeks(self, phase: str) -> List[int]:
        """Get week numbers for a phase."""
        for p in self.phases:
            if p.name.lower() == phase.lower() or p.phase_type.value == phase:
                return p.weeks
        return []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "plan_tier": self.plan_tier.value,
            "distance": self.distance,
            "duration_weeks": self.duration_weeks,
            "volume_tier": self.volume_tier,
            "days_per_week": self.days_per_week,
            "athlete_id": str(self.athlete_id) if self.athlete_id else None,
            "rpi": self.rpi,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "race_date": self.race_date.isoformat() if self.race_date else None,
            "phases": [
                {
                    "name": p.name,
                    "phase_type": p.phase_type.value,
                    "weeks": p.weeks,
                    "focus": p.focus,
                }
                for p in self.phases
            ],
            "workouts": [
                {
                    "week": w.week,
                    "day": w.day,
                    "day_name": w.day_name,
                    "date": w.date.isoformat() if w.date else None,
                    "workout_type": w.workout_type,
                    "title": w.title,
                    "description": w.description,
                    "phase": w.phase,
                    "phase_name": w.phase_name,
                    "distance_miles": w.distance_miles,
                    "duration_minutes": w.duration_minutes,
                    "pace_description": w.pace_description,
                    "segments": w.segments,
                    "option": w.option,
                    "workout_variant_id": w.workout_variant_id,
                    "has_option_b": w.option_b is not None,
                }
                for w in self.workouts
            ],
            "weekly_volumes": self.weekly_volumes,
            "peak_volume": self.peak_volume,
            "total_miles": self.total_miles,
            "total_quality_sessions": self.total_quality_sessions,
        }


class PlanGenerator:
    """
    Main plan generator orchestrating all components.
    
    Follows StrideIQ methodology:
    - Inverted intensity (speed in base, threshold in build)
    - Volume-appropriate prescriptions
    - Option A/B for key workouts
    - Progressive overload with cutbacks
    """
    
    # Weekly structure by days per week
    # Maps day index (0=Monday, 6=Sunday) to workout type
    WEEKLY_STRUCTURES = {
        4: {
            0: "rest",           # Monday - rest
            1: "easy",           # Tuesday
            2: "rest",           # Wednesday - rest
            3: "quality",        # Thursday - quality session
            4: "rest",           # Friday - rest
            5: "easy_strides",   # Saturday - easy + strides
            6: "long",           # Sunday - long run
        },
        5: {
            0: "rest",           # Monday - rest
            1: "easy",           # Tuesday
            2: "easy",           # Wednesday
            3: "quality",        # Thursday - quality session
            4: "rest",           # Friday - rest
            5: "easy_strides",   # Saturday - easy + strides
            6: "long",           # Sunday - long run
        },
        6: {
            0: "rest",           # Monday - rest/gym (no running)
            1: "medium_long",    # Tuesday - medium-long (or MP work in build)
            2: "easy",           # Wednesday - easy
            3: "quality",        # Thursday - quality day (strides/T/hills)
            4: "easy",           # Friday - easy
            5: "easy_strides",   # Saturday - easy with strides
            6: "long",           # Sunday - long run
        },
        7: {
            0: "recovery",       # Monday - recovery
            1: "quality",        # Tuesday - quality session
            2: "easy",           # Wednesday
            3: "medium_long",    # Thursday - medium-long
            4: "easy_strides",   # Friday - easy + strides
            5: "quality_or_easy",# Saturday - quality OR easy
            6: "long",           # Sunday - long run
        },
    }
    
    DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    
    def __init__(self, db: Session = None, cache: PlanCacheService = None):
        self.db = db
        self.cache = cache
        self.tier_classifier = VolumeTierClassifier(db)
        self.phase_builder = PhaseBuilder()
        self.workout_scaler = WorkoutScaler()
        self.pace_engine = PaceEngine()

    def _ensure_pace_order_contract(self, paces: Optional[TrainingPaces]) -> Optional[TrainingPaces]:
        if paces is None:
            return None
        if hasattr(paces, "enforce_pace_order_contract"):
            paces.enforce_pace_order_contract()
        return paces
    
    def generate_standard(
        self,
        distance: str,
        duration_weeks: int,
        tier: str,
        days_per_week: int,
        start_date: date = None,
        recent_race_distance: str = None,
        recent_race_time_seconds: int = None,
        athlete_id: Optional[UUID] = None,
        use_history: bool = False,
    ) -> GeneratedPlan:
        """
        Generate a standard (free) training plan.
        
        If the athlete has race data (from signup or Strava), calculated
        training paces are injected.  Otherwise falls back to effort-based
        descriptions.  Paces are expected — they are not a differentiator.
        N=1 intelligence and daily adaptation are the paid differentiators.
        """
        logger.info(f"Generating standard plan: {distance} {duration_weeks}w {tier} {days_per_week}d")
        
        # Calculate paces from race data when available (Resolved Decision #1)
        paces = None
        rpi = None
        if recent_race_distance and recent_race_time_seconds:
            paces = self.pace_engine.calculate_from_race(
                distance=recent_race_distance,
                time_seconds=recent_race_time_seconds
            )
            paces = self._ensure_pace_order_contract(paces)
            if paces:
                rpi = paces.rpi
        
        # Get tier parameters
        tier_params = self.tier_classifier.get_tier_params(
            VolumeTier(tier),
            distance
        )

        starting_volume = float(tier_params["min_weekly_miles"])
        p4_floor: Optional[float] = None
        p4_ho: Optional[bool] = None
        std_athlete_id: Optional[UUID] = None
        if (
            use_history
            and athlete_id is not None
            and self.db is not None
        ):
            std_athlete_id = athlete_id
            try:
                lc = build_load_context(
                    athlete_id,
                    self.db,
                    history_anchor_date(start_date, self.db, athlete_id),
                )
                if lc.observed_recent_weekly_miles is not None:
                    obs = float(lc.observed_recent_weekly_miles)
                    raw = max(starting_volume, obs)
                    cap = min(
                        obs * 1.15,
                        float(tier_params["max_weekly_miles"]),
                    )
                    starting_volume = min(raw, cap)
                p4_floor = easy_long_floor_miles_from_l30(
                    lc.l30_max_easy_long_mi,
                    distance,
                    tier,
                    observed_recent_weekly_miles=lc.observed_recent_weekly_miles,
                )
                p4_ho = lc.history_override_easy_long
            except Exception as ex:
                logger.warning("P4 load_context (standard) failed, cold template: %s", ex)
        
        # Build phases
        phases = self.phase_builder.build_phases(
            distance=distance,
            duration_weeks=duration_weeks,
            tier=tier
        )
        
        # Calculate volume progression
        weekly_volumes = self.tier_classifier.calculate_volume_progression(
            tier=VolumeTier(tier),
            distance=distance,
            starting_volume=starting_volume,
            plan_weeks=duration_weeks,
            taper_weeks=2
        )
        
        # Generate workouts
        workouts = self._generate_workouts(
            distance=distance,
            duration_weeks=duration_weeks,
            days_per_week=days_per_week,
            tier=tier,
            phases=phases,
            weekly_volumes=weekly_volumes,
            start_date=start_date,
            paces=paces,
            athlete_id=std_athlete_id,
            current_weekly_miles=starting_volume if std_athlete_id else None,
            p4_easy_long_floor_mi=p4_floor,
            p4_history_override=p4_ho,
        )
        
        # Calculate totals
        total_miles = sum(w.distance_miles or 0 for w in workouts)
        quality_count = len([w for w in workouts if w.workout_type in [
            "threshold", "threshold_intervals", "intervals", "long_mp", "long_hmp",
            "mp_touch", "repetitions"
        ]])
        
        return GeneratedPlan(
            plan_tier=PlanTier.STANDARD,
            distance=distance,
            duration_weeks=duration_weeks,
            volume_tier=tier,
            days_per_week=days_per_week,
            athlete_id=None,
            rpi=rpi,
            start_date=start_date,
            end_date=start_date + timedelta(weeks=duration_weeks) if start_date else None,
            race_date=start_date + timedelta(weeks=duration_weeks - 1, days=6) if start_date else None,
            phases=phases,
            workouts=workouts,
            weekly_volumes=weekly_volumes,
            peak_volume=max(weekly_volumes),
            total_miles=round(total_miles, 1),
            total_quality_sessions=quality_count,
        )
    
    def generate_semi_custom(
        self,
        distance: str,
        duration_weeks: int,
        current_weekly_miles: float,
        days_per_week: int,
        race_date: date,
        recent_race_distance: str = None,
        recent_race_time_seconds: int = None,
        race_profile: str = None,
        athlete_id: UUID = None
    ) -> GeneratedPlan:
        """
        Generate a semi-custom plan with pace integration.
        
        Includes:
        - Personalized paces from Training Pace Calculator
        - Adjusted duration to fit race date
        - Environmental considerations
        """
        logger.info(f"Generating semi-custom plan: {distance} for {race_date}")

        start_date = race_date - timedelta(weeks=duration_weeks - 1, days=6)
        requested_mpw = float(current_weekly_miles)

        p4_floor: Optional[float] = None
        p4_ho: Optional[bool] = None
        load_ctx = None
        effective_mpw = requested_mpw
        tier: Optional[VolumeTier] = None

        if athlete_id is not None and self.db is not None:
            try:
                load_ctx = build_load_context(
                    athlete_id,
                    self.db,
                    history_anchor_date(start_date, self.db, athlete_id),
                )
            except Exception as ex:
                logger.warning("P4 load_context (semi-custom) snapshot failed: %s", ex)
                load_ctx = None

            if load_ctx is not None:
                obs = load_ctx.observed_recent_weekly_miles
                quick_mpw = (
                    max(requested_mpw, float(obs))
                    if obs is not None
                    else requested_mpw
                )
                tier_guess = self.tier_classifier.classify(
                    current_weekly_miles=quick_mpw,
                    goal_distance=distance,
                    athlete_id=None,
                    consider_history=False,
                )
                p4_floor = easy_long_floor_miles_from_l30(
                    load_ctx.l30_max_easy_long_mi,
                    distance,
                    tier_guess.value,
                    observed_recent_weekly_miles=load_ctx.observed_recent_weekly_miles,
                )
                p4_ho = load_ctx.history_override_easy_long
                try:
                    tmax = self.tier_classifier.get_tier_params(tier_guess, distance)[
                        "max_weekly_miles"
                    ]
                    effective_mpw = effective_starting_weekly_miles_semi_custom(
                        requested_mpw, load_ctx, float(tmax)
                    )
                    tier = self.tier_classifier.classify(
                        current_weekly_miles=effective_mpw,
                        goal_distance=distance,
                        athlete_id=None,
                        consider_history=False,
                    )
                    p4_floor = easy_long_floor_miles_from_l30(
                        load_ctx.l30_max_easy_long_mi,
                        distance,
                        tier.value,
                        observed_recent_weekly_miles=load_ctx.observed_recent_weekly_miles,
                    )
                except Exception as ex:
                    logger.warning("P4 semi-custom volume/tier merge failed: %s", ex)
                    tier = tier_guess
                    effective_mpw = requested_mpw

        if load_ctx is None:
            tier = self.tier_classifier.classify(
                current_weekly_miles=requested_mpw,
                goal_distance=distance,
                athlete_id=athlete_id,
            )
            effective_mpw = requested_mpw
            p4_floor = None
            p4_ho = None

        # Calculate paces if race time provided
        paces = None
        rpi = None
        if recent_race_distance and recent_race_time_seconds:
            paces = self.pace_engine.calculate_from_race(
                distance=recent_race_distance,
                time_seconds=recent_race_time_seconds
            )
            paces = self._ensure_pace_order_contract(paces)
            if paces:
                rpi = paces.rpi

        # Build phases
        phases = self.phase_builder.build_phases(
            distance=distance,
            duration_weeks=duration_weeks,
            tier=tier.value
        )

        # Calculate volume progression from effective start (P4 merge when present)
        weekly_volumes = self.tier_classifier.calculate_volume_progression(
            tier=tier,
            distance=distance,
            starting_volume=effective_mpw,
            plan_weeks=duration_weeks,
            taper_weeks=2
        )

        # Generate workouts
        workouts = self._generate_workouts(
            distance=distance,
            duration_weeks=duration_weeks,
            days_per_week=days_per_week,
            tier=tier.value,
            phases=phases,
            weekly_volumes=weekly_volumes,
            start_date=start_date,
            paces=paces,
            athlete_id=athlete_id,
            current_weekly_miles=effective_mpw,
            reported_weekly_miles=requested_mpw,
            p4_easy_long_floor_mi=p4_floor,
            p4_history_override=p4_ho,
        )
        
        # Calculate totals
        total_miles = sum(w.distance_miles or 0 for w in workouts)
        quality_count = len([w for w in workouts if w.workout_type in [
            "threshold", "threshold_intervals", "intervals", "long_mp", "long_hmp",
            "mp_touch", "repetitions"
        ]])
        
        return GeneratedPlan(
            plan_tier=PlanTier.SEMI_CUSTOM,
            distance=distance,
            duration_weeks=duration_weeks,
            volume_tier=tier.value,
            days_per_week=days_per_week,
            athlete_id=athlete_id,
            rpi=rpi,
            start_date=start_date,
            end_date=race_date,
            race_date=race_date,
            phases=phases,
            workouts=workouts,
            weekly_volumes=weekly_volumes,
            peak_volume=max(weekly_volumes),
            total_miles=round(total_miles, 1),
            total_quality_sessions=quality_count,
        )
    
    def generate_custom(
        self,
        distance: str,
        race_date: date,
        days_per_week: int,
        athlete_id: UUID,
        athlete_preferences: Dict[str, Any] = None,
        recent_race_distance: str = None,
        recent_race_time_seconds: int = None
    ) -> GeneratedPlan:
        """
        Generate a fully custom plan using all athlete data.
        
        Uses athlete_plan_profile (Phase 1C) to derive N=1 overrides:
        - Volume tier from actual training history (not questionnaire)
        - Long run baseline from duration-gated identification
        - Recovery half-life → cutback frequency
        - Quality session tolerance
        
        Falls back to tier defaults when data is insufficient (cold_start).
        Transparency: profile.disclosures tells the athlete what's estimated.
        
        Args:
            recent_race_distance: User-provided race distance (e.g., "5k", "half_marathon")
            recent_race_time_seconds: User-provided race time in seconds
        """
        logger.info(f"Generating custom plan for athlete {athlete_id}: {distance} for {race_date}")
        
        if not self.db:
            raise ValueError("Database session required for custom plan generation")
        
        from models import Activity, Athlete
        from datetime import timedelta as td
        from services.athlete_plan_profile import AthletePlanProfileService
        
        # Get athlete
        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            raise ValueError(f"Athlete not found: {athlete_id}")
        
        # --- N=1 Profile Derivation (Phase 1C) ---
        profile_service = AthletePlanProfileService()
        profile = profile_service.derive_profile(
            athlete_id=athlete_id,
            db=self.db,
            goal_distance=distance,
        )
        
        current_weekly_miles = profile.current_weekly_miles or 30
        tier = profile.volume_tier
        
        logger.info(
            f"N=1 profile: {profile.data_sufficiency} data, "
            f"tier={tier.value}, volume={current_weekly_miles:.1f}mpw, "
            f"LR confidence={profile.long_run_confidence:.2f}"
        )
        
        # Calculate paces with priority:
        # 1. User-provided race time (allows aspirational paces)
        # 2. Strava race activities
        # 3. Strava training estimate (conservative)
        rpi = None
        paces = None
        pace_source = None
        
        # Priority 1: User-provided race time
        if recent_race_distance and recent_race_time_seconds:
            paces = self.pace_engine.calculate_from_race(
                distance=recent_race_distance,
                time_seconds=recent_race_time_seconds
            )
            paces = self._ensure_pace_order_contract(paces)
            if paces:
                rpi = paces.rpi
                pace_source = "user_input"
                logger.info(f"Calculated RPI from user input: {rpi:.1f}")
        
        # Priority 2: Strava race activities
        if not paces:
            race_activities = self.db.query(Activity).filter(
                Activity.athlete_id == athlete_id,
                Activity.workout_type == 'Race',
                Activity.start_time >= race_date - td(weeks=26)  # Last 6 months
            ).order_by(Activity.start_time.desc()).all()
            
            if race_activities:
                best_race = race_activities[0]
                race_dist_miles = best_race.distance_m / 1609.344
                race_time = best_race.moving_time_s
                
                if race_dist_miles and race_time:
                    paces = self.pace_engine.calculate_from_race(
                        distance=self._distance_to_code(race_dist_miles),
                        time_seconds=race_time
                    )
                    paces = self._ensure_pace_order_contract(paces)
                    if paces:
                        rpi = paces.rpi
                        pace_source = "strava_race"
                        logger.info(f"Calculated RPI from Strava race: {rpi:.1f}")
        
        # Priority 3: Strava training estimate (conservative)
        recent_activities = []
        best_run = None  # scoped here; only set if activities exist
        if not paces:
            if self.db is not None:
                recent_activities = (
                    self.db.query(Activity)
                    .filter(
                        Activity.athlete_id == athlete_id,
                        Activity.sport.ilike("run"),
                        Activity.start_time >= race_date - td(weeks=12),
                    )
                    .order_by(Activity.start_time.desc())
                    .limit(20)
                    .all()
                )
            else:
                recent_activities = []
        if not paces and recent_activities:
            best_run = max(recent_activities, key=lambda a: (a.distance_m or 0) / (a.moving_time_s or 1))
            if best_run.distance_m and best_run.moving_time_s:
                paces = self.pace_engine.calculate_from_race(
                    distance=self._distance_to_code(best_run.distance_m / 1609.344),
                    time_seconds=best_run.moving_time_s
                )
                paces = self._ensure_pace_order_contract(paces)
                if paces:
                    rpi = paces.rpi * 0.95  # Conservative estimate from training
                    pace_source = "strava_training"
                    logger.info(f"Estimated RPI from Strava training: {rpi:.1f}")
        
        if pace_source:
            logger.info(f"Pace source for plan: {pace_source}")
        
        # Calculate duration
        days_to_race = (race_date - date.today()).days
        weeks_to_race = days_to_race // 7
        duration_weeks = min(18, max(8, weeks_to_race))
        
        # Calculate start date
        start_date = race_date - td(weeks=duration_weeks - 1, days=6)
        
        # --- Personalized Taper (Phase 1D) ---
        from services.taper_calculator import TaperCalculator
        from services.pre_race_fingerprinting import derive_pre_race_taper_pattern
        from services.individual_performance_model import get_or_calibrate_model

        taper_calc = TaperCalculator()

        # Gather taper signals
        observed_taper = None
        banister_model_obj = None

        try:
            # Signal 1: Observed taper history from race data
            all_activities = self.db.query(Activity).filter(
                Activity.athlete_id == athlete_id,
                Activity.start_time >= race_date - td(days=730),  # 2 years
            ).order_by(Activity.start_time).all()

            from sqlalchemy import or_
            race_activities = self.db.query(Activity).filter(
                Activity.athlete_id == athlete_id,
                or_(
                    Activity.user_verified_race,
                    Activity.workout_type == 'race',
                    Activity.is_race_candidate,
                ),
            ).order_by(Activity.start_time).all()

            if race_activities:
                observed_taper = derive_pre_race_taper_pattern(
                    activities=all_activities,
                    races=race_activities,
                )

            # Signal 3: Banister model (if calibrated)
            banister_model_obj = get_or_calibrate_model(athlete_id, self.db)
        except Exception as e:
            logger.warning(f"Non-critical: taper signal gathering failed: {e}")

        taper_rec = taper_calc.calculate(
            distance=distance,
            profile=profile,
            banister_model=banister_model_obj,
            observed_taper=observed_taper,
        )

        taper_days = taper_rec.taper_days
        taper_weeks_for_vol = self.phase_builder._taper_days_to_weeks(taper_days)

        logger.info(
            f"Taper recommendation: {taper_days} days ({taper_rec.source}, "
            f"confidence={taper_rec.confidence:.2f})"
        )

        # Build phases with personalized taper
        phases = self.phase_builder.build_phases(
            distance=distance,
            duration_weeks=duration_weeks,
            tier=tier.value,
            taper_days=taper_days,
        )
        
        # Calculate volume progression with N=1 cutback frequency
        weekly_volumes = self.tier_classifier.calculate_volume_progression(
            tier=tier,
            distance=distance,
            starting_volume=current_weekly_miles,
            plan_weeks=duration_weeks,
            taper_weeks=taper_weeks_for_vol,
            cutback_frequency_override=(
                profile.suggested_cutback_frequency
                if profile.recovery_confidence >= 0.4 else None
            ),
        )
        
        # Generate workouts
        workouts = self._generate_workouts(
            distance=distance,
            duration_weeks=duration_weeks,
            days_per_week=days_per_week,
            tier=tier.value,
            phases=phases,
            weekly_volumes=weekly_volumes,
            start_date=start_date,
            paces=paces,
            athlete_id=athlete_id,
            current_weekly_miles=current_weekly_miles,
        )
        
        # Calculate totals
        total_miles = sum(w.distance_miles or 0 for w in workouts)
        quality_count = len([w for w in workouts if w.workout_type in [
            "threshold", "threshold_intervals", "intervals", "long_mp", "long_hmp",
            "mp_touch", "repetitions"
        ]])
        
        return GeneratedPlan(
            plan_tier=PlanTier.CUSTOM,
            distance=distance,
            duration_weeks=duration_weeks,
            volume_tier=tier.value,
            days_per_week=days_per_week,
            athlete_id=athlete_id,
            rpi=rpi,
            start_date=start_date,
            end_date=race_date,
            race_date=race_date,
            phases=phases,
            workouts=workouts,
            weekly_volumes=weekly_volumes,
            peak_volume=max(weekly_volumes),
            total_miles=round(total_miles, 1),
            total_quality_sessions=quality_count,
        )
    
    def _distance_to_code(self, miles: float) -> str:
        """Convert miles to distance code."""
        if miles < 4:
            return "5k"
        elif miles < 8:
            return "10k"
        elif miles < 16:
            return "half_marathon"
        else:
            return "marathon"
    
    def _generate_workouts(
        self,
        distance: str,
        duration_weeks: int,
        days_per_week: int,
        tier: str,
        phases: List[TrainingPhase],
        weekly_volumes: List[float],
        start_date: Optional[date],
        paces: Optional[TrainingPaces],
        athlete_id: Optional[UUID] = None,
        current_weekly_miles: Optional[float] = None,
        reported_weekly_miles: Optional[float] = None,
        p4_easy_long_floor_mi: Optional[float] = None,
        p4_history_override: Optional[bool] = None,
    ) -> List[GeneratedWorkout]:
        """Generate all workouts for the plan."""
        workouts = []

        raw_plan_start = start_date
        start_date if start_date is not None else date.today()
        d4_reference_date = history_anchor_date(
            raw_plan_start,
            self.db if athlete_id else None,
            athlete_id,
        )

        # Lightweight athlete context for rule-based personalization.
        athlete_ctx = {"experienced_high_volume": False, "age_years": None}
        if athlete_id and self.db:
            try:
                from models import Athlete, Activity
                from sqlalchemy import func
                from datetime import datetime as dt

                athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
                age_years = None
                if athlete and getattr(athlete, "birthdate", None):
                    today = date.today()
                    bd = athlete.birthdate
                    age_years = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
                athlete_ctx["age_years"] = age_years

                # Activity density proxy (experience) in last 120 days.
                cutoff = dt.utcnow() - timedelta(days=120)
                run_count = (
                    self.db.query(func.count(Activity.id))
                    .filter(Activity.athlete_id == athlete_id, Activity.sport.ilike("run"), Activity.start_time >= cutoff)
                    .scalar()
                    or 0
                )

                vol = float(current_weekly_miles or 0.0)
                rep = (
                    float(reported_weekly_miles)
                    if reported_weekly_miles is not None
                    else vol
                )
                ctx_vol_signal = max(vol, rep)
                athlete_ctx["quality_volume_signal"] = ctx_vol_signal
                athlete_ctx["experienced_high_volume"] = bool(
                    ctx_vol_signal >= 60
                    and (age_years is None or age_years < 50)
                    and run_count >= 40
                )
            except Exception:
                athlete_ctx = {"experienced_high_volume": False, "age_years": None}
        
        # Ensure start_date falls on Monday (day 0 in our structure)
        # The weekly structure assumes Monday=0, so we must align dates
        if start_date:
            weekday = start_date.weekday()  # 0=Monday, 6=Sunday
            if weekday != 0:
                # Adjust to previous Monday
                start_date = start_date - timedelta(days=weekday)
                logger.info(f"Adjusted start_date to Monday: {start_date}")
        
        # Get weekly structure — fall back to nearest available if exact key missing
        structure = self.WEEKLY_STRUCTURES.get(days_per_week, self.WEEKLY_STRUCTURES[6])

        # Trim excess slots to honour days_per_week.
        # Priority of removal (lowest to highest): easy_strides, easy, medium_long.
        # Never remove: long, quality, recovery, rest.
        TRIM_ORDER = ("easy_strides", "easy", "medium_long")
        non_rest_count = sum(1 for v in structure.values() if v != "rest")
        if non_rest_count > days_per_week:
            structure = dict(structure)  # copy — don't mutate class attribute
            excess = non_rest_count - days_per_week
            for trim_type in TRIM_ORDER:
                for day_idx in sorted(structure.keys(), reverse=True):
                    if excess <= 0:
                        break
                    if structure[day_idx] == trim_type:
                        structure[day_idx] = "rest"
                        excess -= 1
                if excess <= 0:
                    break
        
        # Track MP/HMP long run weeks for progressive loading
        mp_long_run_count = 0
        hmp_long_run_count = 0

        easy_long_state: Dict[str, Any] = {
            "previous_mi": None,
            "floor_mi": p4_easy_long_floor_mi,
            "floor_applied": False,
        }
        if p4_history_override is not None:
            history_override = bool(p4_history_override)
        elif athlete_id and self.db:
            history_override = compute_d4_long_run_override_and_stats(
                self.db, athlete_id, d4_reference_date
            )[0]
        else:
            history_override = False

        prev_mp_miles: Optional[int] = None
        prev_threshold_continuous_min: Optional[int] = None
        prev_threshold_intervals: Optional[Tuple[int, int]] = None

        # Phase-boundary cutback weeks (T2-4): last week of each build phase.
        cutback_weeks = self.phase_builder.get_cutback_weeks(phases)

        # T2-3: MP sequence for marathon plans — builds the alternating Structure A/B pattern
        # and designates which Structure A weeks get an MP medium-long touch.
        from .mp_progression import MPProgressionPlanner
        _mp_planner = MPProgressionPlanner()
        _mp_block_phases = {"marathon_specific", "race_specific"}
        _mp_block_weeks_list = [
            w for p in phases if p.phase_type.value in _mp_block_phases for w in p.weeks
        ]
        _total_mp_weeks = len(_mp_block_weeks_list) if distance == "marathon" else 0
        _mp_block_start = min(_mp_block_weeks_list) if _mp_block_weeks_list else 0
        _mp_sequence = (
            {mw.week_in_phase: mw for mw in _mp_planner.build_sequence(tier, _total_mp_weeks)}
            if _total_mp_weeks > 0 else {}
        )

        for week in range(1, duration_weeks + 1):
            # Get phase for this week
            phase = self.phase_builder.get_phase_for_week(phases, week)
            week_in_phase = week - phase.weeks[0] + 1
            
            # Get weekly volume target
            weekly_volume = weekly_volumes[week - 1] if week <= len(weekly_volumes) else weekly_volumes[-1]
            
            # Check if cutback week — use phase-boundary lookup (T2-4).
            # Cutbacks land on the last week of each build phase rather than
            # by arithmetic (week % freq). This prevents mid-block interruptions.
            is_cutback = week in cutback_weeks and week < duration_weeks - 2
            
            # NOTE: Do NOT multiply weekly_volume here — calculate_volume_progression()
            # already applies tier-specific cutback reductions for cutback weeks.
            # The is_cutback flag is used for INTENSITY decisions (easy long, no
            # secondary quality) but the VOLUME is already correct from the progression.
            
            # Check if this week will have an MP long run (marathon)
            # T2-3: Use MPProgressionPlanner sequence for marathon MP phases;
            #       fall back to the legacy alternation rule for other phases.
            if (
                distance == "marathon"
                and _mp_block_start > 0
                and phase.phase_type.value in ("marathon_specific", "race_specific")
            ):
                _mp_block_week = week - _mp_block_start + 1
                _mp_info = _mp_sequence.get(_mp_block_week)
                will_have_mp_long = bool(_mp_info and _mp_info.long_type == "long_mp")
                will_have_mp_medium_long = bool(
                    _mp_info and _mp_info.medium_long_type == "medium_long_mp"
                )
            else:
                will_have_mp_long = self._will_week_have_mp_long(
                    phase=phase,
                    week_in_phase=week_in_phase,
                    is_cutback=is_cutback,
                    distance=distance,
                )
                will_have_mp_medium_long = False
            
            # Check if this week will have an HMP long run (half marathon)
            will_have_hmp_long = self._will_week_have_hmp_long(
                phase=phase,
                week_in_phase=week_in_phase,
                is_cutback=is_cutback,
                distance=distance
            )
            
            if will_have_mp_long:
                mp_long_run_count += 1
            if will_have_hmp_long:
                hmp_long_run_count += 1
            
            # Generate each day
            week_workouts = self._generate_week(
                week=week,
                phase=phase,
                week_in_phase=week_in_phase,
                is_mp_long_week=will_have_mp_long,
                is_hmp_long_week=will_have_hmp_long,
                is_mp_medium_long_week=will_have_mp_medium_long,
                weekly_volume=weekly_volume,
                tier=tier,
                distance=distance,
                days_per_week=days_per_week,
                structure=structure,
                start_date=start_date,
                paces=paces,
                is_cutback=is_cutback,
                mp_week=mp_long_run_count,
                athlete_ctx=athlete_ctx,
                duration_weeks=duration_weeks,
                easy_long_state=easy_long_state,
                history_override=history_override,
                prev_mp_miles=prev_mp_miles,
                prev_threshold_continuous_min=prev_threshold_continuous_min,
                prev_threshold_intervals=prev_threshold_intervals,
            )
            
            workouts.extend(week_workouts)
            for w in week_workouts:
                extracted = _extract_mp_miles_from_long_mp(w)
                if extracted is not None:
                    prev_mp_miles = extracted
                tc = _extract_threshold_continuous_minutes(w)
                if tc is not None:
                    prev_threshold_continuous_min = tc
                ti = _extract_threshold_intervals_shape(w)
                if ti is not None:
                    prev_threshold_intervals = ti
        
        return workouts
    
    def _will_week_have_mp_long(
        self,
        phase: TrainingPhase,
        week_in_phase: int,
        is_cutback: bool,
        distance: str
    ) -> bool:
        """Determine if this week will have an MP long run.

        Cutback weeks in marathon_specific/race_specific phases KEEP their MP long run.
        The MP long run IS the appropriate stimulus for a cutback week — it's a shorter
        structured effort at reduced total distance. Cutback affects easy volume elsewhere.
        Source: BUILDER_INSTRUCTIONS_2026-03-22_PLAN_BRIDGE_ITEMS_1_THROUGH_5.md §Item3.
        """
        if distance != "marathon":
            return False

        phase_type = phase.phase_type.value

        if phase_type in ["marathon_specific", "race_specific"]:
            # Alternating: MP long, then easy long
            if week_in_phase % 2 == 1:
                return True

        return False

    def _will_week_have_hmp_long(
        self,
        phase: TrainingPhase,
        week_in_phase: int,
        is_cutback: bool,
        distance: str
    ) -> bool:
        """Determine if this week will have an HMP long run (half marathon).

        Same cutback rationale as _will_week_have_mp_long — HMP long on cutback weeks
        is the correct stimulus; volume reduction is absorbed by easy days.
        """
        if distance != "half_marathon":
            return False

        phase_type = phase.phase_type.value

        if phase_type == "race_specific":
            # Alternating: HMP long, then easy long
            if week_in_phase % 2 == 1:
                return True

        return False
    
    def _generate_week(
        self,
        week: int,
        phase: TrainingPhase,
        week_in_phase: int,
        is_mp_long_week: bool = False,
        is_hmp_long_week: bool = False,
        is_mp_medium_long_week: bool = False,
        weekly_volume: float = 0,
        tier: str = "mid",
        distance: str = "marathon",
        days_per_week: int = 6,
        structure: Dict[int, str] = None,
        start_date: Optional[date] = None,
        paces: Optional[TrainingPaces] = None,
        is_cutback: bool = False,
        mp_week: int = 1,
        athlete_ctx: Optional[Dict[str, Any]] = None,
        duration_weeks: int = 18,
        easy_long_state: Optional[Dict[str, Any]] = None,
        history_override: bool = False,
        prev_mp_miles: Optional[int] = None,
        prev_threshold_continuous_min: Optional[int] = None,
        prev_threshold_intervals: Optional[Tuple[int, int]] = None,
    ) -> List[GeneratedWorkout]:
        """Generate workouts for a single week."""
        week_workouts = []
        athlete_ctx = athlete_ctx or {"experienced_high_volume": False}
        easy_long_state = easy_long_state if easy_long_state is not None else {"previous_mi": None}
        structure = structure or {}
        
        for day in range(7):
            day_name = self.DAY_NAMES[day]
            
            # Calculate date if start_date provided
            workout_date = None
            if start_date:
                workout_date = start_date + timedelta(weeks=week - 1, days=day)
            
            # Get workout type from structure
            workout_type = structure.get(day, "rest")
            
            # Skip if rest day for this schedule
            if workout_type == "rest" and days_per_week < 7:
                week_workouts.append(GeneratedWorkout(
                    week=week,
                    day=day,
                    day_name=day_name,
                    date=workout_date,
                    workout_type="rest",
                    title="Rest Day",
                    description="Complete rest or light cross-training",
                    phase=phase.phase_type.value,
                    phase_name=phase.name,
                    distance_miles=0,
                    duration_minutes=0,
                    pace_description="",
                    segments=None,
                    option="A"
                ))
                continue
            
            # Map structure type to actual workout
            actual_workout_type = self._get_workout_for_day(
                structure_type=workout_type,
                phase=phase,
                week_in_phase=week_in_phase,
                is_cutback=is_cutback,
                is_mp_long_week=is_mp_long_week,
                is_hmp_long_week=is_hmp_long_week,
                week=week,
                distance=distance,
                weekly_volume=weekly_volume,
                athlete_ctx=athlete_ctx,
                tier=tier,
                is_mp_medium_long_week=is_mp_medium_long_week,
            )
            
            easy_long_floor_for: Optional[float] = None
            if (
                not easy_long_state.get("floor_applied")
                and easy_long_state.get("floor_mi") is not None
                and easy_long_state.get("previous_mi") is None
            ):
                easy_long_floor_for = easy_long_state.get("floor_mi")

            # Scale the workout
            scaled = self.workout_scaler.scale_workout(
                workout_type=actual_workout_type,
                weekly_volume=weekly_volume,
                tier=tier,
                phase=phase.phase_type.value,
                week_in_phase=week_in_phase,
                distance=distance,
                mp_week=mp_week,
                athlete_ctx=athlete_ctx,
                plan_week=week,
                duration_weeks=duration_weeks,
                total_phase_weeks=len(phase.weeks),
                is_cutback=is_cutback,
                previous_easy_long_mi=easy_long_state.get("previous_mi"),
                history_override=history_override,
                easy_long_floor_mi=easy_long_floor_for,
                prev_mp_miles=prev_mp_miles,
                prev_threshold_continuous_min=prev_threshold_continuous_min,
                prev_threshold_intervals=prev_threshold_intervals,
            )
            
            # Add pace description if paces available
            pace_desc = scaled.pace_description
            if paces and actual_workout_type not in ["rest", "recovery"]:
                pace_desc = paces.get_pace_description(actual_workout_type)
            
            # Create workout
            workout = GeneratedWorkout(
                week=week,
                day=day,
                day_name=day_name,
                date=workout_date,
                workout_type=actual_workout_type,
                title=scaled.title,
                description=scaled.description,
                phase=phase.phase_type.value,
                phase_name=phase.name,
                distance_miles=scaled.total_distance_miles,
                duration_minutes=scaled.duration_minutes,
                pace_description=pace_desc,
                segments=scaled.segments,
                option="A",
                workout_variant_id=resolve_workout_variant_id(
                    actual_workout_type, scaled.title, scaled.segments
                ),
            )
            
            # Add Option B if available
            if scaled.option_b:
                option_b_pace = scaled.option_b.pace_description
                if paces:
                    option_b_pace = paces.get_pace_description(scaled.option_b.workout_type)
                
                workout.option_b = GeneratedWorkout(
                    week=week,
                    day=day,
                    day_name=day_name,
                    date=workout_date,
                    workout_type=scaled.option_b.workout_type,
                    title=scaled.option_b.title,
                    description=scaled.option_b.description,
                    phase=phase.phase_type.value,
                    phase_name=phase.name,
                    distance_miles=scaled.option_b.total_distance_miles,
                    duration_minutes=scaled.option_b.duration_minutes,
                    pace_description=option_b_pace,
                    segments=scaled.option_b.segments,
                    option="B",
                    workout_variant_id=resolve_workout_variant_id(
                        scaled.option_b.workout_type,
                        scaled.option_b.title,
                        scaled.option_b.segments,
                    ),
                )
            
            week_workouts.append(workout)

            if actual_workout_type == "long":
                easy_long_state["previous_mi"] = float(workout.distance_miles or 0)
                easy_long_state["floor_applied"] = True
        
        # --- Volume Fill: weighted easy miles (P2) — same weekly total, textured days ---
        self._apply_weighted_easy_volume_fill(week_workouts, weekly_volume)

        # --- Invariant: medium_long must be < long run (post-fill enforcement) ---
        # Runs after volume fill because fill treats medium_long as an easy slot
        # and can re-inflate its distance. This is a hard contract — no phase/tier bypasses it.
        long_workout = next(
            (w for w in week_workouts if w.workout_type in ("long", "long_mp", "long_hmp")), None
        )
        ml_workout = next(
            (w for w in week_workouts if w.workout_type in ("medium_long", "medium_long_mp")), None
        )
        if long_workout and ml_workout:
            lr = float(long_workout.distance_miles or 0)
            ml = float(ml_workout.distance_miles or 0)
            if ml >= lr and lr > 0:
                capped = round(max(lr - 2.0, lr * 0.75), 1)
                ml_workout.distance_miles = capped
                ml_workout.title = f"Medium Long: {capped:.0f} mi"
        
        return week_workouts

    def _apply_weighted_easy_volume_fill(
        self,
        week_workouts: List[GeneratedWorkout],
        weekly_volume: float,
    ) -> None:
        """
        Distribute remaining weekly miles across easy / medium_long slots using
        adjacency weights (Vega): shorter after quality, moderate before long,
        longer on standalone easy days. Preserves total target when possible
        within per-slot [3, 12] mi caps.

        Medium_long is capped below the week's long run to enforce the
        medium_long < long invariant before the post-fill safety check.
        """
        easy_types = {"easy", "easy_strides", "recovery", "medium_long"}
        non_easy_miles = sum(
            w.distance_miles or 0 for w in week_workouts
            if w.workout_type not in easy_types
        )
        easy_workouts = [
            w for w in week_workouts
            if w.workout_type in easy_types and (w.distance_miles or 0) > 0
        ]
        if not easy_workouts:
            return

        # Find long run distance to cap medium_long below it
        long_run_miles = next(
            (float(w.distance_miles or 0) for w in week_workouts
             if w.workout_type in ("long", "long_mp", "long_hmp")),
            None,
        )

        by_day = {w.day: w for w in week_workouts}
        remaining = float(weekly_volume) - non_easy_miles
        n = len(easy_workouts)
        remaining = max(remaining, n * 3.0)

        easy_sorted = sorted(easy_workouts, key=lambda w: w.day)
        weights = [_easy_fill_adjacency_weight(w.day, by_day) for w in easy_sorted]
        sw = sum(weights) or 1.0
        raw = [remaining * (weights[i] / sw) for i in range(n)]

        def _slot_cap(wo: "GeneratedWorkout") -> float:
            if wo.workout_type in ("medium_long", "medium_long_mp") and long_run_miles:
                return max(3.0, long_run_miles - 1.0)
            return 12.0

        miles = [max(3.0, min(_slot_cap(easy_sorted[i]), round(raw[i], 1))) for i in range(n)]
        target = round(remaining, 1)
        delta = round(target - sum(miles), 1)

        idx = sorted(range(n), key=lambda i: weights[i], reverse=True)
        guard = 0
        while abs(delta) > 0.05 and guard < 300:
            guard += 1
            moved = False
            if delta > 0:
                for i in idx:
                    if delta <= 0:
                        break
                    room = _slot_cap(easy_sorted[i]) - miles[i]
                    if room >= 0.05:
                        d = min(delta, room, 1.0)
                        miles[i] = round(miles[i] + d, 1)
                        delta = round(target - sum(miles), 1)
                        moved = True
            else:
                for i in reversed(idx):
                    if delta >= 0:
                        break
                    room = miles[i] - 3.0
                    if room >= 0.05:
                        d = min(-delta, room, 1.0)
                        miles[i] = round(miles[i] - d, 1)
                        delta = round(target - sum(miles), 1)
                        moved = True
            if not moved:
                break

        for i, ew in enumerate(easy_sorted):
            ew.distance_miles = miles[i]
            ew.duration_minutes = int(miles[i] * 9.5)
    
    def _get_workout_for_day(
        self,
        structure_type: str,
        phase: TrainingPhase,
        week_in_phase: int,
        is_cutback: bool,
        is_mp_long_week: bool,
        is_hmp_long_week: bool,
        week: int,
        distance: str,
        weekly_volume: float,
        athlete_ctx: Dict[str, Any],
        tier: str = "mid",
        is_mp_medium_long_week: bool = False,
    ) -> str:
        """
        Determine actual workout type based on structure slot and phase.
        
        This is where StrideIQ methodology is applied:
        - Quality sessions vary by phase
        - Long runs get MP/HMP work in later phases
        - Cutback weeks reduce intensity
        - Alternation rule (marathon): MP-long weeks have NO threshold (KB Source B)
        - Half marathon: HMP long weeks KEEP threshold (HMP portion is moderate,
          threshold is the primary emphasis — removing it defeats the purpose)
        - Quality day limit: max 2 quality sessions per week
        """
        if structure_type == "rest":
            return "rest"
        
        if structure_type == "recovery":
            return "recovery"
        
        if structure_type == "easy":
            return "easy"
        
        if structure_type == "easy_strides":
            # Year-round: preserve easy volume but add strides.
            return "easy_strides"
        
        if structure_type == "medium_long":
            # Cutback + marathon specific: consolidation week — no MP *long*, but
            # mid/high (and elite) runners may keep a small MP block in a shorter
            # mid-week run so race pace doesn't go dormant (founder policy).
            if (
                is_cutback
                and distance == "marathon"
                and phase.phase_type.value in ("marathon_specific", "race_specific")
                and tier in ("mid", "high", "elite")
                and (
                    weekly_volume >= 50
                    or athlete_ctx.get("experienced_high_volume")
                )
            ):
                return "mp_touch"
            # T2-5: Structure B week (MP long run) — Tuesday is easy recovery, NOT
            # medium-long. The MP long IS the quality stimulus; a 11-13mi mid-week
            # run on top would be overloading.
            if is_mp_long_week:
                return "easy"
            # T2-3: MP touch in medium-long on select Structure A weeks
            # (is_mp_medium_long_week flag set by MPProgressionPlanner)
            if is_mp_medium_long_week:
                return "medium_long_mp"
            # If the phase calls for 2 quality sessions and the athlete can handle it,
            # convert the mid-week medium long to the "touch" session.
            # T2-5: Lower gate from 55 → 40mpw for race-specific phases,
            #        and to 25mpw for 5K/10K race-specific (experience proxy).
            # POLICY MONITOR: The 25mpw threshold for 5K/10K race-specific is a
            # meaningful coaching load increase for lower-mileage athletes.
            # Track via matrix test test_45mpw_10k_race_specific_gets_two_quality_sessions.
            # If injury signal emerges, raise back to 35mpw here first.
            if is_hmp_long_week:
                return "medium_long"
            _secondary_threshold = (
                25 if distance in ("5k", "10k") and phase.phase_type.value == "race_specific"
                else 40 if phase.phase_type.value in ("race_specific", "marathon_specific")
                else 55
            )
            if phase.quality_sessions >= 2 and not is_cutback and weekly_volume >= _secondary_threshold:
                raw_secondary = self._get_secondary_quality(phase, distance, week_in_phase, weekly_volume, athlete_ctx)
                return self._apply_phase_guard(raw_secondary, phase)
            return "medium_long"
        
        if structure_type == "long":
            # T2-3 source-of-truth fix: for marathon MP phases, is_mp_long_week is
            # already derived from MPProgressionPlanner (set in _generate_workouts loop).
            # Using it directly prevents desync when marathon_specific/race_specific
            # lengths are odd (phase boundary resets week_in_phase to 1, which flips
            # the local odd/even parity vs the planner's global sequence).
            if (
                distance == "marathon"
                and phase.phase_type.value in ("marathon_specific", "race_specific")
            ):
                return "long_mp" if is_mp_long_week else "long"
            return self._get_long_run_type(phase, week_in_phase, is_cutback, distance)
        
        if structure_type == "quality":
            # ALTERNATION RULE (Source B): On MP long run weeks, the MP long
            # IS the quality session.  The mid-week quality slot becomes
            # easy with strides (neuromuscular touch without adding load).
            if is_mp_long_week:
                return "easy_strides"
            # Half marathon HMP weeks: threshold STAYS as the quality session.
            # HMP long run is moderate, threshold is primary emphasis — don't kill it.
            return self._apply_phase_guard(
                self._get_quality_workout(phase, week_in_phase, is_cutback, distance, weekly_volume, athlete_ctx),
                phase,
            )
        
        if structure_type == "quality_or_easy":
            # ALTERNATION RULE: MP long run weeks already have quality via the MP long.
            # Don't add another quality session — keep this as easy.
            if is_mp_long_week:
                return "easy"
            # HMP long weeks already have 2 quality (threshold + HMP long).
            if is_hmp_long_week:
                return "easy"
            # Second quality only in certain phases
            if phase.quality_sessions >= 2 and not is_cutback:
                raw_secondary = self._get_secondary_quality(phase, distance, week_in_phase, weekly_volume, athlete_ctx)
                return self._apply_phase_guard(raw_secondary, phase)
            return "easy"
        
        return "easy"
    
    def _get_long_run_type(
        self,
        phase: TrainingPhase,
        week_in_phase: int,
        is_cutback: bool,
        distance: str
    ) -> str:
        """Determine long run type based on phase and goal distance.

        NOTE: For marathon plans in marathon_specific / race_specific phases,
        the caller (_get_workout_for_day) short-circuits before reaching this
        method and uses the MPProgressionPlanner-derived is_mp_long_week flag
        directly (T2-3 source-of-truth fix). This method therefore handles
        half-marathon HMP alternation and all other distances.
        """
        phase_type = phase.phase_type.value

        # --- Marathon: MP long runs in specific phases ---
        # Cutback weeks in marathon_specific/race_specific KEEP their MP long run.
        # The MP long IS the week's quality stimulus — just shorter due to reduced weekly volume.
        # Easy volume elsewhere absorbs the cutback reduction.
        if distance == "marathon":
            if phase_type in ["marathon_specific", "race_specific"]:
                if week_in_phase % 2 == 1:
                    return "long_mp"
            return "long"

        # --- Half marathon: HMP long runs in race-specific phase ---
        if distance == "half_marathon":
            if phase_type == "race_specific":
                if week_in_phase % 2 == 1:
                    return "long_hmp"
            return "long"

        # Non-specific phases and other distances: easy long on cutback
        if is_cutback:
            return "long"

        # --- 10K / 5K: easy long runs only (quality comes from intervals) ---
        return "long"
    
    def _apply_phase_guard(self, workout_type: str, phase: TrainingPhase) -> str:
        """
        Enforce that the selected quality workout is in phase.allowed_workouts.

        When the existing if/else logic proposes a type that falls outside the
        phase's declared boundaries (e.g., 'intervals' in a base phase that
        only allows 'strides/hills'), this guard falls back to the first key
        session that IS in allowed_workouts, keeping phase integrity intact.
        """
        allowed = set(phase.allowed_workouts)
        if workout_type in allowed:
            return workout_type
        # Prefer the phase's declared key sessions as fallback
        for ks in phase.key_sessions:
            if ks in allowed:
                return ks
        # Last resort: any non-volume workout that is allowed
        non_volume = {"strides", "easy_strides", "hills", "recovery", "easy"}
        for candidate in non_volume:
            if candidate in allowed:
                return candidate
        return "easy_strides"

    def _get_quality_workout(
        self,
        phase: TrainingPhase,
        week_in_phase: int,
        is_cutback: bool,
        distance: str,
        weekly_volume: float,
        athlete_ctx: Dict[str, Any],
    ) -> str:
        """Determine quality workout based on phase and distance."""
        phase_type = phase.phase_type.value
        
        if is_cutback:
            # Lighter quality on cutback
            if phase_type == "base_speed":
                return "strides"
            # 5K cutback: reps maintain neuromuscular pattern without aerobic load.
            if distance == "5k":
                return "repetitions"
            # 10K cutback: strides for neuromuscular touch without adding quality load.
            if distance == "10k":
                return "strides"
            # Marathon / half: consolidation — easy + strides, no threshold on cutback.
            if distance in ("marathon", "half_marathon"):
                return "easy_strides"
            return "threshold"
        
        if phase_type == "base_speed":
            # --- 5K / 10K base: strides, hills, AND reps (inverted model) ---
            # Speed/neuromuscular work on fresh legs, low injury risk.
            # Reps here are neuromuscular tool-building, not race simulation.
            if distance in ("5k", "10k"):
                cycle = week_in_phase % 3
                if cycle == 0:
                    return "repetitions"  # neuromuscular reps on fresh legs
                elif cycle == 2:
                    return "hills"
                return "easy_strides"
            # Marathon / Half marathon base: strides/hills.
            # For high-mileage, experienced athletes, include periodic VO2 touches early.
            qv = float(athlete_ctx.get("quality_volume_signal") or weekly_volume)
            if athlete_ctx.get("experienced_high_volume") and qv >= 60 and week_in_phase % 2 == 0:
                return "intervals"
            return "hills" if week_in_phase % 2 == 0 else "easy_strides"
        
        if phase_type == "threshold":
            # --- Inverted model: threshold dominant in build for ALL distances ---
            # LT is the limiting factor for most runners (Source A).
            # Building the threshold floor first means the athlete clears lactate
            # faster between race-specific intervals, making VO2max phase more productive.
            # T-block progression: intervals format → continuous
            if week_in_phase <= 2:
                return "threshold_intervals"
            return "threshold"
        
        if phase_type in ["marathon_specific", "race_specific"]:
            # --- 5K race-specific: VO2max intervals arrive HERE ---
            # The threshold base is built. Now sharpen with 5K-pace work.
            if distance == "5k":
                return "intervals"
            # --- 10K race-specific: VO2max sharpening on threshold base ---
            # Structure closer to half marathon than 5K (Source A: LT #1 for >30 min).
            if distance == "10k":
                return "intervals"
            # --- Marathon / Half marathon: maintain threshold ---
            return "threshold_intervals" if week_in_phase % 2 == 0 else "threshold"
        
        if phase_type == "taper":
            return "strides"
        
        if phase_type == "race":
            return "strides"
        
        return "threshold_intervals"
    
    def _get_secondary_quality(
        self,
        phase: TrainingPhase,
        distance: str,
        week_in_phase: int,
        weekly_volume: float,
        athlete_ctx: Dict[str, Any],
    ) -> str:
        """
        Determine secondary quality workout (complement of primary).

        Only fires when quality_sessions >= 2 (race-specific phases).
        Build phases use quality_sessions=1 for 5K/10K (inverted model),
        so secondary is not called during the threshold-dominant build.
        """
        phase_type = phase.phase_type.value

        # --- 5K race-specific: reps alongside VO2max primary ---
        # Goal-pace reps practice the effort pattern under fatigue.
        # Occasional threshold for aerobic maintenance.
        if distance == "5k":
            if week_in_phase % 3 == 0:
                return "threshold"      # aerobic maintenance every 3rd week
            return "repetitions"        # goal-pace reps

        # --- 10K race-specific: threshold maintenance alongside VO2max primary ---
        # The threshold floor built in the build phase must be maintained
        # while VO2max sharpening takes the primary slot.
        if distance == "10k":
            return "threshold"

        # Half marathon: threshold is PRIMARY, so secondary is VO2max
        # (1000m/1200m intervals for economy — not primary VO2 development).
        if distance == "half_marathon":
            return "intervals"

        # For Marathon, secondary quality is usually a "touch" session.
        # Use VO2 touches early in the specific block for experienced high-volume athletes.
        qv = float(athlete_ctx.get("quality_volume_signal") or weekly_volume)
        if athlete_ctx.get("experienced_high_volume") and qv >= 60 and phase_type == "marathon_specific":
            # Every other week early in MP integration (touch only).
            if week_in_phase <= 2 and week_in_phase % 2 == 1:
                return "intervals"

        # Default touch: threshold format
        return "threshold"
