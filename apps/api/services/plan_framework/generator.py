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
from typing import Optional, List, Dict, Any
from datetime import date, timedelta
from uuid import UUID
from dataclasses import dataclass

from sqlalchemy.orm import Session

from .constants import Distance, VolumeTier, PlanTier
from .volume_tiers import VolumeTierClassifier
from .phase_builder import PhaseBuilder, TrainingPhase
from .workout_scaler import WorkoutScaler, ScaledWorkout
from .pace_engine import PaceEngine, TrainingPaces
from .cache import PlanCacheService

logger = logging.getLogger(__name__)


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
    option_b: Optional['GeneratedWorkout'] = None


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
    vdot: Optional[float]
    
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
            "vdot": self.vdot,
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
        5: {
            0: "rest",           # Monday - rest
            1: "easy",           # Tuesday
            2: "easy",           # Wednesday
            3: "quality",        # Thursday - quality session
            4: "rest",           # Friday - rest
            5: "easy",           # Saturday
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
            4: "easy",           # Friday
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
    
    def generate_standard(
        self,
        distance: str,
        duration_weeks: int,
        tier: str,
        days_per_week: int,
        start_date: date = None
    ) -> GeneratedPlan:
        """
        Generate a standard (free) training plan.
        
        No personalization - uses effort descriptions, not paces.
        """
        logger.info(f"Generating standard plan: {distance} {duration_weeks}w {tier} {days_per_week}d")
        
        # Get tier parameters
        tier_params = self.tier_classifier.get_tier_params(
            VolumeTier(tier),
            distance
        )
        
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
            starting_volume=tier_params["min_weekly_miles"],
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
            paces=None  # No paces for standard plans
        )
        
        # Calculate totals
        total_miles = sum(w.distance_miles or 0 for w in workouts)
        quality_count = len([w for w in workouts if w.workout_type in [
            "threshold_intervals", "tempo", "intervals", "long_mp"
        ]])
        
        return GeneratedPlan(
            plan_tier=PlanTier.STANDARD,
            distance=distance,
            duration_weeks=duration_weeks,
            volume_tier=tier,
            days_per_week=days_per_week,
            athlete_id=None,
            vdot=None,
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
        
        # Classify volume tier
        tier = self.tier_classifier.classify(
            current_weekly_miles=current_weekly_miles,
            goal_distance=distance,
            athlete_id=athlete_id
        )
        
        # Calculate paces if race time provided
        paces = None
        vdot = None
        if recent_race_distance and recent_race_time_seconds:
            paces = self.pace_engine.calculate_from_race(
                distance=recent_race_distance,
                time_seconds=recent_race_time_seconds
            )
            if paces:
                vdot = paces.vdot
        
        # Calculate start date from race date
        start_date = race_date - timedelta(weeks=duration_weeks - 1, days=6)
        
        # Build phases
        phases = self.phase_builder.build_phases(
            distance=distance,
            duration_weeks=duration_weeks,
            tier=tier.value
        )
        
        # Calculate volume progression from current
        weekly_volumes = self.tier_classifier.calculate_volume_progression(
            tier=tier,
            distance=distance,
            starting_volume=current_weekly_miles,
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
            paces=paces
        )
        
        # Calculate totals
        total_miles = sum(w.distance_miles or 0 for w in workouts)
        quality_count = len([w for w in workouts if w.workout_type in [
            "threshold_intervals", "tempo", "intervals", "long_mp"
        ]])
        
        return GeneratedPlan(
            plan_tier=PlanTier.SEMI_CUSTOM,
            distance=distance,
            duration_weeks=duration_weeks,
            volume_tier=tier.value,
            days_per_week=days_per_week,
            athlete_id=athlete_id,
            vdot=vdot,
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
        
        This is the premium tier - uses:
        - User-provided race time (priority 1) OR auto-detected from Strava
        - Auto-detected volume from Strava history
        - Training history patterns
        - Athlete preferences
        - Dynamic adaptation capability
        
        Args:
            recent_race_distance: User-provided race distance (e.g., "5k", "half_marathon")
            recent_race_time_seconds: User-provided race time in seconds
        """
        logger.info(f"Generating custom plan for athlete {athlete_id}: {distance} for {race_date}")
        
        if not self.db:
            raise ValueError("Database session required for custom plan generation")
        
        from models import Activity, Athlete
        from sqlalchemy import func
        from datetime import timedelta as td
        
        # Get athlete
        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            raise ValueError(f"Athlete not found: {athlete_id}")
        
        # Auto-detect current weekly volume from last 4 weeks
        four_weeks_ago = race_date - td(weeks=30)  # Look back further for baseline
        recent_activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.distance_m >= 1000,  # At least 1km - filters out non-runs
            Activity.start_time >= four_weeks_ago
        ).all()
        
        # Calculate average weekly miles over last 4 complete weeks
        weekly_totals = {}
        for activity in recent_activities:
            week_start = activity.start_time.date() - td(days=activity.start_time.weekday())
            week_key = week_start.isoformat()
            if week_key not in weekly_totals:
                weekly_totals[week_key] = 0
            weekly_totals[week_key] += (activity.distance_m or 0) / 1609.344
        
        if weekly_totals:
            # Use median of last 4 weeks for stability
            recent_volumes = sorted(weekly_totals.values())[-4:]
            current_weekly_miles = sum(recent_volumes) / len(recent_volumes) if recent_volumes else 30
        else:
            current_weekly_miles = 30  # Default if no data
        
        logger.info(f"Detected weekly volume: {current_weekly_miles:.1f} miles")
        
        # Classify tier
        tier = self.tier_classifier.classify(
            current_weekly_miles=current_weekly_miles,
            goal_distance=distance,
            athlete_id=athlete_id
        )
        
        # Calculate paces with priority:
        # 1. User-provided race time (allows aspirational paces)
        # 2. Strava race activities
        # 3. Strava training estimate (conservative)
        vdot = None
        paces = None
        pace_source = None
        
        # Priority 1: User-provided race time
        if recent_race_distance and recent_race_time_seconds:
            paces = self.pace_engine.calculate_from_race(
                distance=recent_race_distance,
                time_seconds=recent_race_time_seconds
            )
            if paces:
                vdot = paces.vdot
                pace_source = "user_input"
                logger.info(f"Calculated VDOT from user input: {vdot:.1f}")
        
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
                    if paces:
                        vdot = paces.vdot
                        pace_source = "strava_race"
                        logger.info(f"Calculated VDOT from Strava race: {vdot:.1f}")
        
        # Priority 3: Strava training estimate (conservative)
        if not paces and recent_activities:
            best_run = max(recent_activities, key=lambda a: (a.distance_m or 0) / (a.moving_time_s or 1))
            if best_run.distance_m and best_run.moving_time_s:
                paces = self.pace_engine.calculate_from_race(
                    distance=self._distance_to_code(best_run.distance_m / 1609.344),
                    time_seconds=best_run.moving_time_s
                )
                if paces:
                    vdot = paces.vdot * 0.95  # Conservative estimate from training
                    pace_source = "strava_training"
                    logger.info(f"Estimated VDOT from Strava training: {vdot:.1f}")
        
        if pace_source:
            logger.info(f"Pace source for plan: {pace_source}")
        
        # Calculate duration
        days_to_race = (race_date - date.today()).days
        weeks_to_race = days_to_race // 7
        duration_weeks = min(18, max(8, weeks_to_race))
        
        # Calculate start date
        start_date = race_date - td(weeks=duration_weeks - 1, days=6)
        
        # Build phases
        phases = self.phase_builder.build_phases(
            distance=distance,
            duration_weeks=duration_weeks,
            tier=tier.value
        )
        
        # Calculate volume progression
        weekly_volumes = self.tier_classifier.calculate_volume_progression(
            tier=tier,
            distance=distance,
            starting_volume=current_weekly_miles,
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
            paces=paces
        )
        
        # Calculate totals
        total_miles = sum(w.distance_miles or 0 for w in workouts)
        quality_count = len([w for w in workouts if w.workout_type in [
            "threshold_intervals", "tempo", "intervals", "long_mp"
        ]])
        
        return GeneratedPlan(
            plan_tier=PlanTier.CUSTOM,
            distance=distance,
            duration_weeks=duration_weeks,
            volume_tier=tier.value,
            days_per_week=days_per_week,
            athlete_id=athlete_id,
            vdot=vdot,
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
        paces: Optional[TrainingPaces]
    ) -> List[GeneratedWorkout]:
        """Generate all workouts for the plan."""
        workouts = []
        
        # Ensure start_date falls on Monday (day 0 in our structure)
        # The weekly structure assumes Monday=0, so we must align dates
        if start_date:
            weekday = start_date.weekday()  # 0=Monday, 6=Sunday
            if weekday != 0:
                # Adjust to previous Monday
                start_date = start_date - timedelta(days=weekday)
                logger.info(f"Adjusted start_date to Monday: {start_date}")
        
        # Get weekly structure
        structure = self.WEEKLY_STRUCTURES.get(days_per_week, self.WEEKLY_STRUCTURES[6])
        
        # Track MP long run weeks for progressive loading
        mp_long_run_count = 0
        
        for week in range(1, duration_weeks + 1):
            # Get phase for this week
            phase = self.phase_builder.get_phase_for_week(phases, week)
            week_in_phase = week - phase.weeks[0] + 1
            
            # Get weekly volume target
            weekly_volume = weekly_volumes[week - 1] if week <= len(weekly_volumes) else weekly_volumes[-1]
            
            # Check if cutback week
            tier_enum = VolumeTier(tier)
            cutback_freq = self.tier_classifier.get_tier_params(tier_enum, distance).get("cutback_frequency", 4)
            is_cutback = week % cutback_freq == 0 and week < duration_weeks - 2
            
            if is_cutback:
                weekly_volume *= 0.75  # Reduce volume for cutback
            
            # Check if this week will have an MP long run (for tracking)
            will_have_mp_long = self._will_week_have_mp_long(
                phase=phase,
                week_in_phase=week_in_phase,
                is_cutback=is_cutback,
                distance=distance
            )
            
            if will_have_mp_long:
                mp_long_run_count += 1
            
            # Generate each day
            week_workouts = self._generate_week(
                week=week,
                phase=phase,
                week_in_phase=week_in_phase,
                weekly_volume=weekly_volume,
                tier=tier,
                distance=distance,
                days_per_week=days_per_week,
                structure=structure,
                start_date=start_date,
                paces=paces,
                is_cutback=is_cutback,
                mp_week=mp_long_run_count
            )
            
            workouts.extend(week_workouts)
        
        return workouts
    
    def _will_week_have_mp_long(
        self,
        phase: TrainingPhase,
        week_in_phase: int,
        is_cutback: bool,
        distance: str
    ) -> bool:
        """Determine if this week will have an MP long run."""
        if is_cutback:
            return False
        
        if distance != "marathon":
            return False
        
        phase_type = phase.phase_type.value
        
        if phase_type in ["marathon_specific", "race_specific"]:
            # Alternating: MP long, then easy long
            if week_in_phase % 2 == 1:
                return True
        
        return False
    
    def _generate_week(
        self,
        week: int,
        phase: TrainingPhase,
        week_in_phase: int,
        weekly_volume: float,
        tier: str,
        distance: str,
        days_per_week: int,
        structure: Dict[int, str],
        start_date: Optional[date],
        paces: Optional[TrainingPaces],
        is_cutback: bool,
        mp_week: int = 1
    ) -> List[GeneratedWorkout]:
        """Generate workouts for a single week."""
        week_workouts = []
        
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
                week=week,
                distance=distance
            )
            
            # Scale the workout
            scaled = self.workout_scaler.scale_workout(
                workout_type=actual_workout_type,
                weekly_volume=weekly_volume,
                tier=tier,
                phase=phase.phase_type.value,
                week_in_phase=week_in_phase,
                distance=distance,
                mp_week=mp_week
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
                option="A"
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
                    option="B"
                )
            
            week_workouts.append(workout)
        
        return week_workouts
    
    def _get_workout_for_day(
        self,
        structure_type: str,
        phase: TrainingPhase,
        week_in_phase: int,
        is_cutback: bool,
        week: int,
        distance: str
    ) -> str:
        """
        Determine actual workout type based on structure slot and phase.
        
        This is where StrideIQ methodology is applied:
        - Quality sessions vary by phase
        - Long runs get MP work in later phases
        - Cutback weeks reduce intensity
        """
        if structure_type == "rest":
            return "rest"
        
        if structure_type == "recovery":
            return "recovery"
        
        if structure_type == "easy":
            return "easy"
        
        if structure_type == "easy_strides":
            # Strides in base, easy in later phases
            if phase.phase_type.value in ["base_speed", "base"]:
                return "strides"
            return "easy"
        
        if structure_type == "medium_long":
            # Medium-long stays easy - MP work goes in long runs only
            return "medium_long"
        
        if structure_type == "long":
            return self._get_long_run_type(phase, week_in_phase, is_cutback, distance)
        
        if structure_type == "quality":
            return self._get_quality_workout(phase, week_in_phase, is_cutback, distance)
        
        if structure_type == "quality_or_easy":
            # Second quality only in certain phases
            if phase.quality_sessions >= 2 and not is_cutback:
                return self._get_secondary_quality(phase, distance)
            return "easy"
        
        return "easy"
    
    def _get_long_run_type(
        self,
        phase: TrainingPhase,
        week_in_phase: int,
        is_cutback: bool,
        distance: str
    ) -> str:
        """Determine long run type based on phase."""
        if is_cutback:
            return "long"  # Easy long run on cutback
        
        if distance != "marathon":
            return "long"  # Non-marathon distances don't need MP longs
        
        phase_type = phase.phase_type.value
        
        if phase_type == "base_speed":
            return "long"
        
        if phase_type == "threshold":
            # Occasional easy long run
            return "long"
        
        if phase_type in ["marathon_specific", "race_specific"]:
            # Alternating: MP long, then easy long
            if week_in_phase % 2 == 1:
                return "long_mp"
            return "long"
        
        if phase_type == "taper":
            return "long"  # Easy in taper
        
        return "long"
    
    def _get_quality_workout(
        self,
        phase: TrainingPhase,
        week_in_phase: int,
        is_cutback: bool,
        distance: str
    ) -> str:
        """Determine quality workout based on phase."""
        phase_type = phase.phase_type.value
        
        if is_cutback:
            # Lighter quality on cutback
            return "strides" if phase_type == "base_speed" else "tempo"
        
        if phase_type == "base_speed":
            # Strides and hills
            if week_in_phase % 2 == 1:
                return "strides"
            return "hills"
        
        if phase_type == "threshold":
            # T-block progression
            if week_in_phase <= 2:
                return "threshold_intervals"
            return "tempo"
        
        if phase_type in ["marathon_specific", "race_specific"]:
            # Maintain threshold
            return "threshold_intervals" if week_in_phase % 2 == 0 else "tempo"
        
        if phase_type == "taper":
            return "strides"
        
        if phase_type == "race":
            return "strides"
        
        return "threshold_intervals"
    
    def _get_secondary_quality(
        self,
        phase: TrainingPhase,
        distance: str
    ) -> str:
        """Determine secondary quality workout."""
        if distance in ["5k", "10k"]:
            return "intervals"
        return "tempo"
