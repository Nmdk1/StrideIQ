"""
Training Plan Generator

Generates periodized training plans based on:
- Goal race (distance, date, target time)
- Athlete's current fitness (VDOT, recent volume)
- Training availability
- Coaching methodology principles

Philosophy: The plan is a starting point. The athlete owns it, adjusts it,
and learns from it. We provide structure, not rigid prescription.
"""

from datetime import date, timedelta
from typing import List, Dict, Optional, Tuple
from uuid import UUID, uuid4
from sqlalchemy.orm import Session
from sqlalchemy import func

from models import (
    Athlete, Activity, TrainingPlan, PlannedWorkout, 
    TrainingAvailability, PersonalBest
)


class PlanGenerator:
    """
    Generates periodized training plans.
    
    Supports:
    - Marathon, Half Marathon, 10K, 5K plans
    - Base building plans
    - Periodization: Base → Build → Peak → Taper
    """
    
    # Standard race distances in meters
    RACE_DISTANCES = {
        '5k': 5000,
        '10k': 10000,
        'half_marathon': 21097,
        'marathon': 42195,
    }
    
    # Default phase distributions (as % of total plan)
    PHASE_DISTRIBUTIONS = {
        'marathon': {'base': 0.30, 'build': 0.40, 'peak': 0.15, 'taper': 0.15},
        'half_marathon': {'base': 0.25, 'build': 0.45, 'peak': 0.15, 'taper': 0.15},
        '10k': {'base': 0.20, 'build': 0.50, 'peak': 0.15, 'taper': 0.15},
        '5k': {'base': 0.20, 'build': 0.50, 'peak': 0.15, 'taper': 0.15},
    }
    
    # Minimum weeks for each plan type
    MIN_WEEKS = {
        'marathon': 16,
        'half_marathon': 12,
        '10k': 8,
        '5k': 6,
    }
    
    def __init__(self, db: Session):
        self.db = db
    
    def generate_plan(
        self,
        athlete_id: UUID,
        goal_race_name: str,
        goal_race_date: date,
        goal_race_distance_m: int,
        goal_time_seconds: Optional[int] = None,
        plan_start_date: Optional[date] = None,
    ) -> TrainingPlan:
        """
        Generate a complete training plan.
        
        Args:
            athlete_id: The athlete's ID
            goal_race_name: Name of the goal race
            goal_race_date: Date of the goal race
            goal_race_distance_m: Race distance in meters
            goal_time_seconds: Target finish time (optional)
            plan_start_date: When to start the plan (default: next Monday)
        
        Returns:
            TrainingPlan with all PlannedWorkouts created
        """
        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            raise ValueError(f"Athlete {athlete_id} not found")
        
        # Determine plan type
        plan_type = self._determine_plan_type(goal_race_distance_m)
        
        # Calculate plan dates
        if plan_start_date is None:
            # Start next Monday
            today = date.today()
            days_until_monday = (7 - today.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            plan_start_date = today + timedelta(days=days_until_monday)
        
        plan_end_date = goal_race_date
        total_days = (plan_end_date - plan_start_date).days
        total_weeks = max(total_days // 7, self.MIN_WEEKS.get(plan_type, 8))
        
        # Adjust start date if needed to ensure minimum weeks
        min_weeks = self.MIN_WEEKS.get(plan_type, 8)
        if total_weeks < min_weeks:
            plan_start_date = goal_race_date - timedelta(weeks=min_weeks)
            total_weeks = min_weeks
        
        # Get athlete's baseline fitness
        baseline_vdot = athlete.vdot or self._estimate_vdot(athlete_id)
        baseline_volume = self._get_recent_weekly_volume(athlete_id)
        
        # Create the plan
        plan = TrainingPlan(
            id=uuid4(),
            athlete_id=athlete_id,
            name=f"{goal_race_name} Training Plan",
            status="active",
            goal_race_name=goal_race_name,
            goal_race_date=goal_race_date,
            goal_race_distance_m=goal_race_distance_m,
            goal_time_seconds=goal_time_seconds,
            plan_start_date=plan_start_date,
            plan_end_date=plan_end_date,
            total_weeks=total_weeks,
            baseline_vdot=baseline_vdot,
            baseline_weekly_volume_km=baseline_volume,
            plan_type=plan_type,
            generation_method="ai",
        )
        
        self.db.add(plan)
        self.db.flush()  # Get the plan ID
        
        # Generate weekly structure
        weeks = self._generate_week_structure(plan, athlete)
        
        # Generate individual workouts
        workouts = self._generate_workouts(plan, weeks, athlete)
        
        for workout in workouts:
            self.db.add(workout)
        
        self.db.commit()
        
        return plan
    
    def _determine_plan_type(self, distance_m: int) -> str:
        """Determine plan type based on race distance."""
        if distance_m >= 40000:
            return 'marathon'
        elif distance_m >= 20000:
            return 'half_marathon'
        elif distance_m >= 9000:
            return '10k'
        else:
            return '5k'
    
    def _estimate_vdot(self, athlete_id: UUID) -> Optional[float]:
        """Estimate VDOT from recent activities if not set."""
        # Look for recent race or time trial
        recent_pb = self.db.query(PersonalBest).filter(
            PersonalBest.athlete_id == athlete_id
        ).order_by(PersonalBest.achieved_at.desc()).first()
        
        if recent_pb:
            # Simple VDOT estimation from race time
            # Using Daniels' formula approximation
            distance_km = recent_pb.distance_meters / 1000
            time_min = recent_pb.time_seconds / 60
            
            # Rough VDOT estimation
            if distance_km >= 5 and distance_km <= 42.195:
                # Very simplified - real calculation is more complex
                vdot = 30 + (distance_km / time_min) * 10
                return min(max(vdot, 25), 85)  # Clamp to reasonable range
        
        return 40.0  # Default moderate fitness
    
    def _get_recent_weekly_volume(self, athlete_id: UUID, weeks: int = 4) -> float:
        """Get athlete's average weekly volume over recent weeks."""
        cutoff = date.today() - timedelta(weeks=weeks)
        
        total_distance = self.db.query(func.sum(Activity.distance_m)).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= cutoff,
            Activity.sport == 'run'
        ).scalar() or 0
        
        return (total_distance / 1000) / weeks  # km per week
    
    def _generate_week_structure(
        self, 
        plan: TrainingPlan, 
        athlete: Athlete
    ) -> List[Dict]:
        """
        Generate the week-by-week structure with phases.
        
        Returns list of week definitions with:
        - week_number
        - phase
        - phase_week
        - volume_factor (relative to peak)
        - intensity_focus
        """
        weeks = []
        phase_dist = self.PHASE_DISTRIBUTIONS.get(plan.plan_type, self.PHASE_DISTRIBUTIONS['half_marathon'])
        
        total_weeks = plan.total_weeks
        base_weeks = int(total_weeks * phase_dist['base'])
        build_weeks = int(total_weeks * phase_dist['build'])
        peak_weeks = int(total_weeks * phase_dist['peak'])
        taper_weeks = total_weeks - base_weeks - build_weeks - peak_weeks
        
        week_num = 1
        
        # Base phase - building aerobic foundation
        for i in range(base_weeks):
            weeks.append({
                'week_number': week_num,
                'phase': 'base',
                'phase_week': i + 1,
                'volume_factor': 0.6 + (0.2 * i / max(base_weeks - 1, 1)),  # 60% → 80%
                'intensity_focus': 'easy',
                'key_workouts': ['long', 'easy', 'easy'],
            })
            week_num += 1
        
        # Build phase - increasing intensity
        for i in range(build_weeks):
            weeks.append({
                'week_number': week_num,
                'phase': 'build',
                'phase_week': i + 1,
                'volume_factor': 0.8 + (0.2 * i / max(build_weeks - 1, 1)),  # 80% → 100%
                'intensity_focus': 'threshold' if i % 2 == 0 else 'intervals',
                'key_workouts': ['long', 'tempo', 'intervals'] if plan.plan_type != '5k' else ['long', 'intervals', 'tempo'],
            })
            week_num += 1
        
        # Peak phase - race-specific work
        for i in range(peak_weeks):
            weeks.append({
                'week_number': week_num,
                'phase': 'peak',
                'phase_week': i + 1,
                'volume_factor': 0.95 - (0.1 * i / max(peak_weeks - 1, 1)),  # 95% → 85%
                'intensity_focus': 'race_pace',
                'key_workouts': ['long_with_pace', 'race_pace', 'easy'],
            })
            week_num += 1
        
        # Taper phase - reducing load
        for i in range(taper_weeks):
            is_race_week = (i == taper_weeks - 1)
            weeks.append({
                'week_number': week_num,
                'phase': 'taper',
                'phase_week': i + 1,
                'volume_factor': 0.7 - (0.3 * i / max(taper_weeks - 1, 1)),  # 70% → 40%
                'intensity_focus': 'sharpening',
                'key_workouts': ['race'] if is_race_week else ['easy', 'strides', 'rest'],
            })
            week_num += 1
        
        return weeks
    
    def _generate_workouts(
        self,
        plan: TrainingPlan,
        weeks: List[Dict],
        athlete: Athlete
    ) -> List[PlannedWorkout]:
        """
        Generate individual workout prescriptions for each day.
        """
        workouts = []
        current_date = plan.plan_start_date
        
        # Get athlete's training availability
        availability = self._get_availability(athlete.id)
        
        for week in weeks:
            week_workouts = self._generate_week_workouts(
                plan=plan,
                week=week,
                start_date=current_date,
                athlete=athlete,
                availability=availability,
            )
            workouts.extend(week_workouts)
            current_date += timedelta(days=7)
        
        return workouts
    
    def _get_availability(self, athlete_id: UUID) -> Dict[int, str]:
        """
        Get athlete's preferred training days.
        Returns dict of day_of_week -> preferred time.
        """
        availability = self.db.query(TrainingAvailability).filter(
            TrainingAvailability.athlete_id == athlete_id,
            TrainingAvailability.status.in_(['available', 'preferred'])
        ).all()
        
        if not availability:
            # Default: available every day
            return {i: 'morning' for i in range(7)}
        
        result = {}
        for a in availability:
            if a.day_of_week not in result or a.status == 'preferred':
                result[a.day_of_week] = a.time_block
        
        return result
    
    def _generate_week_workouts(
        self,
        plan: TrainingPlan,
        week: Dict,
        start_date: date,
        athlete: Athlete,
        availability: Dict[int, str],
    ) -> List[PlannedWorkout]:
        """
        Generate workouts for a single week.
        
        Standard week structure:
        - Sunday: Long run
        - Monday: Rest or easy
        - Tuesday: Quality workout
        - Wednesday: Easy or recovery
        - Thursday: Quality workout #2
        - Friday: Rest
        - Saturday: Easy or moderate
        """
        workouts = []
        
        # Get target paces based on VDOT
        paces = self._calculate_training_paces(plan.baseline_vdot or 40)
        
        # Week template based on phase
        if week['phase'] == 'base':
            template = self._get_base_week_template()
        elif week['phase'] == 'build':
            template = self._get_build_week_template(plan.plan_type)
        elif week['phase'] == 'peak':
            template = self._get_peak_week_template(plan.plan_type)
        else:  # taper
            template = self._get_taper_week_template(week['phase_week'], plan.plan_type)
        
        # Check if this is race week
        is_race_week = (start_date + timedelta(days=6) >= plan.goal_race_date)
        
        for day_offset, workout_def in enumerate(template):
            workout_date = start_date + timedelta(days=day_offset)
            
            # If race week and this is race day
            if is_race_week and workout_date == plan.goal_race_date:
                workout = self._create_race_workout(plan, week, workout_date)
            else:
                workout = self._create_workout(
                    plan=plan,
                    week=week,
                    workout_date=workout_date,
                    workout_def=workout_def,
                    paces=paces,
                    volume_factor=week['volume_factor'],
                )
            
            if workout:
                workouts.append(workout)
        
        return workouts
    
    def _calculate_training_paces(self, vdot: float) -> Dict[str, int]:
        """
        Calculate training paces based on VDOT.
        Returns pace per km in seconds.
        
        Uses Daniels' training zones:
        - Easy: 59-74% VO2max
        - Marathon: 75-84% VO2max
        - Threshold: 83-88% VO2max
        - Interval: 95-100% VO2max
        - Repetition: 105-120% VO2max
        """
        # Simplified pace calculations
        # Real implementation would use full Daniels tables
        
        # Base pace from VDOT (very simplified)
        # VDOT 40 ≈ 5:30/km easy, VDOT 50 ≈ 4:45/km easy
        base_easy_pace = 420 - (vdot - 40) * 6  # seconds per km
        
        return {
            'easy': int(base_easy_pace),
            'long': int(base_easy_pace * 1.05),
            'marathon': int(base_easy_pace * 0.88),
            'threshold': int(base_easy_pace * 0.82),
            'interval': int(base_easy_pace * 0.72),
            'repetition': int(base_easy_pace * 0.65),
            'recovery': int(base_easy_pace * 1.15),
        }
    
    def _get_base_week_template(self) -> List[Dict]:
        """Base phase week template - focus on easy volume."""
        return [
            {'type': 'long', 'title': 'Long Run', 'duration_factor': 1.5},
            {'type': 'rest', 'title': 'Rest Day', 'duration_factor': 0},
            {'type': 'easy', 'title': 'Easy Run', 'duration_factor': 0.8},
            {'type': 'easy', 'title': 'Easy Run', 'duration_factor': 0.8},
            {'type': 'easy_strides', 'title': 'Easy Run with Strides', 'duration_factor': 0.9},
            {'type': 'rest', 'title': 'Rest Day', 'duration_factor': 0},
            {'type': 'easy', 'title': 'Easy Run', 'duration_factor': 0.7},
        ]
    
    def _get_build_week_template(self, plan_type: str) -> List[Dict]:
        """Build phase week template - increasing quality."""
        if plan_type in ['marathon', 'half_marathon']:
            return [
                {'type': 'long', 'title': 'Long Run', 'duration_factor': 1.8},
                {'type': 'rest', 'title': 'Rest Day', 'duration_factor': 0},
                {'type': 'tempo', 'title': 'Tempo Run', 'duration_factor': 1.0},
                {'type': 'easy', 'title': 'Easy Run', 'duration_factor': 0.7},
                {'type': 'intervals', 'title': 'Interval Session', 'duration_factor': 1.0},
                {'type': 'rest', 'title': 'Rest Day', 'duration_factor': 0},
                {'type': 'easy', 'title': 'Easy Run', 'duration_factor': 0.8},
            ]
        else:  # 5k, 10k
            return [
                {'type': 'long', 'title': 'Long Run', 'duration_factor': 1.4},
                {'type': 'rest', 'title': 'Rest Day', 'duration_factor': 0},
                {'type': 'intervals', 'title': 'Interval Session', 'duration_factor': 1.0},
                {'type': 'easy', 'title': 'Easy Run', 'duration_factor': 0.7},
                {'type': 'tempo', 'title': 'Tempo Run', 'duration_factor': 1.0},
                {'type': 'rest', 'title': 'Rest Day', 'duration_factor': 0},
                {'type': 'easy_strides', 'title': 'Easy Run with Strides', 'duration_factor': 0.8},
            ]
    
    def _get_peak_week_template(self, plan_type: str) -> List[Dict]:
        """Peak phase week template - race-specific work."""
        return [
            {'type': 'long_pace', 'title': 'Long Run with Goal Pace', 'duration_factor': 1.6},
            {'type': 'rest', 'title': 'Rest Day', 'duration_factor': 0},
            {'type': 'race_pace', 'title': 'Race Pace Session', 'duration_factor': 1.0},
            {'type': 'easy', 'title': 'Easy Run', 'duration_factor': 0.6},
            {'type': 'threshold', 'title': 'Threshold Run', 'duration_factor': 0.9},
            {'type': 'rest', 'title': 'Rest Day', 'duration_factor': 0},
            {'type': 'easy', 'title': 'Easy Run', 'duration_factor': 0.7},
        ]
    
    def _get_taper_week_template(self, taper_week: int, plan_type: str) -> List[Dict]:
        """Taper phase week template - reducing volume, maintaining intensity."""
        if taper_week == 1:
            return [
                {'type': 'long', 'title': 'Moderate Long Run', 'duration_factor': 1.2},
                {'type': 'rest', 'title': 'Rest Day', 'duration_factor': 0},
                {'type': 'tempo_short', 'title': 'Short Tempo', 'duration_factor': 0.7},
                {'type': 'easy', 'title': 'Easy Run', 'duration_factor': 0.5},
                {'type': 'strides', 'title': 'Easy with Strides', 'duration_factor': 0.6},
                {'type': 'rest', 'title': 'Rest Day', 'duration_factor': 0},
                {'type': 'easy', 'title': 'Shakeout Run', 'duration_factor': 0.4},
            ]
        else:  # Final week
            return [
                {'type': 'easy', 'title': 'Easy Run', 'duration_factor': 0.5},
                {'type': 'rest', 'title': 'Rest Day', 'duration_factor': 0},
                {'type': 'strides', 'title': 'Easy with Strides', 'duration_factor': 0.4},
                {'type': 'rest', 'title': 'Rest Day', 'duration_factor': 0},
                {'type': 'shakeout', 'title': 'Pre-Race Shakeout', 'duration_factor': 0.3},
                {'type': 'rest', 'title': 'Rest Day', 'duration_factor': 0},
                {'type': 'race', 'title': 'RACE DAY', 'duration_factor': 0},
            ]
    
    def _create_workout(
        self,
        plan: TrainingPlan,
        week: Dict,
        workout_date: date,
        workout_def: Dict,
        paces: Dict[str, int],
        volume_factor: float,
    ) -> Optional[PlannedWorkout]:
        """Create a single PlannedWorkout from template."""
        
        workout_type = workout_def['type']
        
        # Skip rest days
        if workout_type == 'rest':
            return PlannedWorkout(
                id=uuid4(),
                plan_id=plan.id,
                athlete_id=plan.athlete_id,
                scheduled_date=workout_date,
                week_number=week['week_number'],
                day_of_week=workout_date.weekday(),
                workout_type='rest',
                title='Rest Day',
                description='Full rest. Recovery is when adaptation happens.',
                phase=week['phase'],
                phase_week=week['phase_week'],
            )
        
        # Calculate duration based on base duration and volume factor
        base_duration = 45  # Base easy run in minutes
        duration = int(base_duration * workout_def['duration_factor'] * volume_factor)
        
        # Get appropriate pace
        pace_key = self._get_pace_key(workout_type)
        target_pace = paces.get(pace_key, paces['easy'])
        
        # Calculate distance from duration and pace
        target_distance = (duration * 60) / target_pace  # km
        
        # Generate description
        description = self._generate_workout_description(workout_type, duration, target_pace, plan.plan_type)
        
        return PlannedWorkout(
            id=uuid4(),
            plan_id=plan.id,
            athlete_id=plan.athlete_id,
            scheduled_date=workout_date,
            week_number=week['week_number'],
            day_of_week=workout_date.weekday(),
            workout_type=workout_type,
            title=workout_def['title'],
            description=description,
            phase=week['phase'],
            phase_week=week['phase_week'],
            target_duration_minutes=duration,
            target_distance_km=round(target_distance, 1),
            target_pace_per_km_seconds=target_pace,
            target_pace_per_km_seconds_max=int(target_pace * 1.1),  # 10% slower allowed
        )
    
    def _create_race_workout(
        self,
        plan: TrainingPlan,
        week: Dict,
        workout_date: date,
    ) -> PlannedWorkout:
        """Create the race day workout."""
        return PlannedWorkout(
            id=uuid4(),
            plan_id=plan.id,
            athlete_id=plan.athlete_id,
            scheduled_date=workout_date,
            week_number=week['week_number'],
            day_of_week=workout_date.weekday(),
            workout_type='race',
            title=f'🏁 {plan.goal_race_name}',
            description=f'RACE DAY! Trust your training. Execute your plan. Enjoy the moment.',
            phase='race',
            phase_week=1,
            target_distance_km=plan.goal_race_distance_m / 1000,
            target_duration_minutes=plan.goal_time_seconds // 60 if plan.goal_time_seconds else None,
        )
    
    def _get_pace_key(self, workout_type: str) -> str:
        """Map workout type to pace zone."""
        mapping = {
            'easy': 'easy',
            'easy_strides': 'easy',
            'long': 'long',
            'long_pace': 'marathon',
            'tempo': 'threshold',
            'tempo_short': 'threshold',
            'threshold': 'threshold',
            'intervals': 'interval',
            'race_pace': 'marathon',
            'strides': 'repetition',
            'shakeout': 'easy',
            'recovery': 'recovery',
        }
        return mapping.get(workout_type, 'easy')
    
    def _generate_workout_description(
        self,
        workout_type: str,
        duration: int,
        target_pace: int,
        plan_type: str,
    ) -> str:
        """Generate human-readable workout description."""
        pace_str = f"{target_pace // 60}:{target_pace % 60:02d}/km"
        
        descriptions = {
            'easy': f"Easy run at conversational pace. Target: {pace_str} or slower. "
                    "This should feel comfortable - if you can't hold a conversation, slow down.",
            
            'long': f"Long run building aerobic endurance. Start easy ({pace_str}), stay relaxed. "
                    "Focus on time on feet, not pace. Fuel and hydrate.",
            
            'long_pace': f"Long run with goal pace segments. Start easy for 40%, then run "
                         f"the middle portion at goal race pace, finish easy. Stay controlled.",
            
            'tempo': f"Threshold run at 'comfortably hard' pace (~{pace_str}). "
                     "You should be able to speak in short sentences but not hold a conversation.",
            
            'tempo_short': f"Short tempo at threshold pace (~{pace_str}). "
                          "Maintain form and rhythm throughout.",
            
            'intervals': f"Interval session: warmup, then 4-6 x (3-5 min hard / 2-3 min easy), cooldown. "
                        f"Hard efforts around {pace_str}. Full recovery between.",
            
            'race_pace': f"Race pace practice. Run extended segments at your goal race pace. "
                        "Focus on rhythm and perceived effort at this pace.",
            
            'strides': "Easy run with 4-6 strides (20-30 sec accelerations) at the end. "
                      "Strides should be smooth and controlled, not sprints.",
            
            'easy_strides': "Easy run finishing with 4-6 strides. "
                           "Keep the easy portion truly easy, then add strides for neuromuscular activation.",
            
            'shakeout': "Pre-race shakeout. Very easy, short run to stay loose. "
                       "Don't overthink it - just get the legs moving.",
            
            'recovery': "Recovery run. Extremely easy pace. If in doubt, go slower.",
        }
        
        return descriptions.get(workout_type, f"Run at {pace_str} pace for {duration} minutes.")


def get_plan_generator(db: Session) -> PlanGenerator:
    """Factory function for dependency injection."""
    return PlanGenerator(db)
