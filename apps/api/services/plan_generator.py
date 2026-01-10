"""
Archetype-Based Training Plan Generator

Generates periodized training plans from carefully designed archetypes.

Philosophy:
- Plans are built from tested archetypes, not generic algorithms
- Individual paces come from Training Pace Calculator (VDOT-based)
- Athlete data informs archetype selection, not the structure itself
- Easy must be easy. Structure must be respected.

Archetypes exist for:
- Marathon: mid-mileage (40-55 mpw), 6 days/week, 18 weeks
- (More to be added: Half, 10K, 5K, various volumes)

Each archetype contains:
- Phase definitions with focus areas
- Week-by-week workout structure
- T-block progressions
- Long run progressions with MP work
- Cutback placement
"""

from datetime import date, timedelta
from typing import List, Dict, Optional
from uuid import UUID, uuid4
from pathlib import Path
import json
import os

from sqlalchemy.orm import Session
from sqlalchemy import func

from models import (
    Athlete, Activity, TrainingPlan, PlannedWorkout, 
    PersonalBest
)


# Path to archetypes - relative to api directory
ARCHETYPES_DIR = Path(__file__).parent.parent.parent.parent / "plans" / "archetypes"


class ArchetypePlanGenerator:
    """
    Generates training plans from archetype JSON files.
    
    The archetype contains the full structure - we just:
    1. Map dates to the structure
    2. Apply athlete-specific paces
    3. Create PlannedWorkout records
    """
    
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
        archetype_name: Optional[str] = None,
    ) -> TrainingPlan:
        """
        Generate a training plan from an archetype.
        
        Args:
            athlete_id: The athlete's ID
            goal_race_name: Name of the goal race
            goal_race_date: Date of the goal race (should be a Sunday)
            goal_race_distance_m: Race distance in meters
            goal_time_seconds: Target finish time (optional)
            plan_start_date: When to start (default: calculated from archetype)
            archetype_name: Specific archetype to use (auto-selected if None)
        
        Returns:
            TrainingPlan with all PlannedWorkouts created
        """
        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            raise ValueError(f"Athlete {athlete_id} not found")
        
        # Select appropriate archetype
        if archetype_name:
            archetype = self._load_archetype(archetype_name)
        else:
            archetype = self._select_archetype(athlete, goal_race_distance_m)
        
        meta = archetype["meta"]
        
        # Calculate plan dates
        # Race should be on Sunday (end of final week)
        # Plan starts on Monday, 18 weeks before race Sunday
        duration_weeks = meta["duration_weeks"]
        
        if plan_start_date is None:
            # Race is on goal_race_date (should be Sunday)
            # Plan starts Monday, duration_weeks before
            # Find the Monday that starts the plan
            days_before_race = (duration_weeks * 7) - 1  # -1 because race is on Sunday
            plan_start_date = goal_race_date - timedelta(days=days_before_race)
            
            # Adjust to Monday if needed
            while plan_start_date.weekday() != 0:  # 0 = Monday
                plan_start_date -= timedelta(days=1)
        
        plan_end_date = goal_race_date
        
        # Get athlete's baseline fitness
        baseline_vdot = athlete.vdot or self._estimate_vdot(athlete_id)
        baseline_volume = self._get_recent_weekly_volume(athlete_id)
        
        # Calculate training paces from VDOT
        paces = self._calculate_training_paces(baseline_vdot)
        
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
            total_weeks=duration_weeks,
            baseline_vdot=baseline_vdot,
            baseline_weekly_volume_km=baseline_volume,
            plan_type=meta["distance"],
            generation_method="archetype",
        )
        
        self.db.add(plan)
        self.db.flush()  # Get the plan ID
        
        # Generate workouts from archetype weeks
        workouts = self._generate_workouts_from_archetype(
            plan=plan,
            archetype=archetype,
            paces=paces,
            start_date=plan_start_date,
        )
        
        for workout in workouts:
            self.db.add(workout)
        
        self.db.commit()
        
        return plan
    
    def _load_archetype(self, name: str) -> Dict:
        """Load an archetype JSON file."""
        filepath = ARCHETYPES_DIR / f"{name}.json"
        if not filepath.exists():
            raise ValueError(f"Archetype {name} not found at {filepath}")
        
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _select_archetype(self, athlete: Athlete, distance_m: int) -> Dict:
        """
        Select the appropriate archetype based on athlete profile and race distance.
        
        For now, we have:
        - marathon_mid_6d_18w: Mid-mileage marathon (40-55 mpw, 6 days/week)
        
        Future: Add more archetypes and selection logic.
        """
        # Determine distance type
        if distance_m >= 40000:
            distance_type = "marathon"
        elif distance_m >= 20000:
            distance_type = "half"
        elif distance_m >= 9000:
            distance_type = "10k"
        else:
            distance_type = "5k"
        
        # For now, we only have the marathon mid archetype
        # Future: Select based on athlete's weekly volume, days available, etc.
        if distance_type == "marathon":
            # Default to mid-mileage, 6 day, 18 week
            return self._load_archetype("marathon_mid_6d_18w")
        
        # Fallback to generating a basic plan if no archetype exists
        raise ValueError(f"No archetype available for {distance_type}. Using fallback.")
    
    def _estimate_vdot(self, athlete_id: UUID) -> float:
        """Estimate VDOT from recent race times."""
        recent_pb = self.db.query(PersonalBest).filter(
            PersonalBest.athlete_id == athlete_id
        ).order_by(PersonalBest.achieved_at.desc()).first()
        
        if recent_pb and recent_pb.distance_meters and recent_pb.time_seconds:
            # Use Daniels' VDOT estimation
            # This is simplified - real implementation uses full tables
            distance_km = recent_pb.distance_meters / 1000
            time_min = recent_pb.time_seconds / 60
            
            # Rough estimation
            if 5 <= distance_km <= 42.195:
                velocity_km_min = distance_km / time_min
                # Very simplified VDOT approximation
                vdot = velocity_km_min * 25 + 10
                return min(max(vdot, 30), 80)
        
        return 45.0  # Default moderate fitness
    
    def _get_recent_weekly_volume(self, athlete_id: UUID, weeks: int = 4) -> float:
        """Get athlete's average weekly volume over recent weeks."""
        cutoff = date.today() - timedelta(weeks=weeks)
        
        total_distance = self.db.query(func.sum(Activity.distance_m)).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= cutoff,
            Activity.sport == 'run'
        ).scalar() or 0
        
        return (total_distance / 1000) / weeks  # km per week
    
    def _calculate_training_paces(self, vdot: float) -> Dict[str, int]:
        """
        Calculate training paces based on VDOT.
        Returns pace per km in seconds.
        
        Based on Daniels' Running Formula zones.
        """
        # These are approximations of Daniels' tables
        # VDOT 40 ≈ 6:00/km easy, 5:15/km marathon, 4:50/km threshold
        # VDOT 50 ≈ 5:00/km easy, 4:25/km marathon, 4:05/km threshold
        # VDOT 60 ≈ 4:15/km easy, 3:45/km marathon, 3:25/km threshold
        
        # Linear interpolation (simplified)
        # Easy pace
        if vdot <= 40:
            easy = 360  # 6:00/km
        elif vdot >= 60:
            easy = 255  # 4:15/km
        else:
            easy = 360 - ((vdot - 40) * 5.25)  # ~5.25 sec/km per VDOT point
        
        # Marathon pace (roughly 88% of easy effort, actually uses race prediction)
        marathon = easy * 0.88
        
        # Threshold pace (roughly 83% of easy)
        threshold = easy * 0.82
        
        # Interval pace (roughly 75% of easy)
        interval = easy * 0.75
        
        return {
            'easy': int(easy),
            'long': int(easy * 1.02),  # Slightly slower than easy
            'marathon': int(marathon),
            'threshold': int(threshold),
            'interval': int(interval),
            'recovery': int(easy * 1.10),  # Slower than easy
            'strides': int(threshold * 0.85),  # Fast but controlled
        }
    
    def _generate_workouts_from_archetype(
        self,
        plan: TrainingPlan,
        archetype: Dict,
        paces: Dict[str, int],
        start_date: date,
    ) -> List[PlannedWorkout]:
        """
        Generate PlannedWorkout records from archetype week definitions.
        """
        workouts = []
        weeks = archetype.get("weeks", [])
        
        # Day mapping: archetype uses monday-sunday, we start on monday (weekday 0)
        day_order = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        
        for week_def in weeks:
            week_num = week_def["week"]
            phase = week_def["phase"]
            focus = week_def.get("focus", "")
            week_workouts = week_def.get("workouts", {})
            total_miles = week_def.get("total_miles", 0)
            
            # Calculate week start date
            week_start = start_date + timedelta(weeks=week_num - 1)
            
            for day_offset, day_name in enumerate(day_order):
                workout_date = week_start + timedelta(days=day_offset)
                workout_def = week_workouts.get(day_name, {})
                
                if not workout_def:
                    continue
                
                workout_type = workout_def.get("type", "easy")
                miles = workout_def.get("miles", 0)
                description = workout_def.get("description", "")
                
                # Determine title
                title = self._get_workout_title(workout_type, description)
                
                # Get target pace
                target_pace = self._get_target_pace(workout_type, paces)
                
                # Calculate duration from distance and pace
                distance_km = miles * 1.60934
                duration_minutes = None
                if distance_km > 0 and target_pace > 0:
                    duration_minutes = int((distance_km * target_pace) / 60)
                
                # Check if this is race day
                is_race = (workout_date == plan.goal_race_date or workout_type == "race")
                
                # Convert Python weekday (0=Mon) to our model (0=Sun)
                day_of_week_model = (workout_date.weekday() + 1) % 7
                
                workout = PlannedWorkout(
                    id=uuid4(),
                    plan_id=plan.id,
                    athlete_id=plan.athlete_id,
                    scheduled_date=workout_date,
                    week_number=week_num,
                    day_of_week=day_of_week_model,
                    workout_type=workout_type,
                    title=f"🏁 {plan.goal_race_name}" if is_race else title,
                    description=self._enhance_description(description, workout_type, paces) if not is_race else "RACE DAY! Trust the work.",
                    phase=phase,
                    phase_week=self._get_phase_week(archetype, week_num, phase),
                    target_duration_minutes=duration_minutes,
                    target_distance_km=round(distance_km, 1) if distance_km > 0 else None,
                    target_pace_per_km_seconds=target_pace if workout_type not in ["rest", "gym", "race"] else None,
                )
                
                workouts.append(workout)
        
        return workouts
    
    def _get_workout_title(self, workout_type: str, description: str) -> str:
        """Generate a clean title from workout type."""
        titles = {
            "easy": "Easy Run",
            "easy_strides": "Easy + Strides",
            "long": "Long Run",
            "long_mp": "Long Run w/ Marathon Pace",
            "medium_long": "Medium-Long Run",
            "medium_long_mp": "Medium-Long w/ MP",
            "threshold": "Threshold Session",
            "threshold_light": "Light Threshold",
            "tempo": "Tempo Run",
            "intervals": "Interval Session",
            "rest": "Rest Day",
            "gym": "Strength + Mobility",
            "recovery": "Recovery Run",
            "strides": "Strides",
            "race": "Race Day",
            "shakeout_strides": "Shakeout + Strides",
        }
        return titles.get(workout_type, workout_type.replace("_", " ").title())
    
    def _get_target_pace(self, workout_type: str, paces: Dict[str, int]) -> int:
        """Get appropriate pace for workout type."""
        mapping = {
            "easy": "easy",
            "easy_strides": "easy",
            "easy_hills": "easy",
            "long": "long",
            "long_mp": "marathon",
            "medium_long": "easy",
            "medium_long_mp": "marathon",
            "threshold": "threshold",
            "threshold_light": "threshold",
            "threshold_short": "threshold",
            "tempo": "threshold",
            "tempo_short": "threshold",
            "intervals": "interval",
            "recovery": "recovery",
            "strides": "strides",
            "shakeout_strides": "easy",
        }
        pace_type = mapping.get(workout_type, "easy")
        return paces.get(pace_type, paces["easy"])
    
    def _get_phase_week(self, archetype: Dict, week_num: int, phase: str) -> int:
        """Determine which week within the phase this is."""
        phases = archetype.get("phases", [])
        for p in phases:
            if p["name"] == phase and week_num in p.get("weeks", []):
                return p["weeks"].index(week_num) + 1
        return 1
    
    def _enhance_description(self, description: str, workout_type: str, paces: Dict[str, int]) -> str:
        """Enhance workout description with pace information."""
        if not description:
            description = self._get_default_description(workout_type)
        
        # Add pace guidance if relevant
        if workout_type in ["easy", "easy_strides", "easy_hills", "long", "medium_long"]:
            easy_pace = paces.get("easy", 360)
            pace_str = f"{easy_pace // 60}:{easy_pace % 60:02d}/km"
            if "easy" in description.lower() and "/km" not in description:
                description += f" Target: {pace_str} or slower."
        
        elif workout_type in ["threshold", "threshold_light", "threshold_short", "tempo"]:
            t_pace = paces.get("threshold", 300)
            pace_str = f"{t_pace // 60}:{t_pace % 60:02d}/km"
            if "/km" not in description:
                description += f" Threshold pace: ~{pace_str}."
        
        elif workout_type in ["long_mp", "medium_long_mp"]:
            mp = paces.get("marathon", 330)
            pace_str = f"{mp // 60}:{mp % 60:02d}/km"
            if "/km" not in description:
                description += f" MP segments: ~{pace_str}."
        
        return description
    
    def _get_default_description(self, workout_type: str) -> str:
        """Get default description for workout type."""
        defaults = {
            "easy": "Easy, conversational pace. If you can't talk, slow down.",
            "easy_strides": "Easy run finishing with 4-6 x 20s strides. Smooth acceleration, not sprints.",
            "long": "Long run building aerobic endurance. Start easy, stay relaxed. The Engine.",
            "long_mp": "Long run with marathon pace segments. Practice race effort.",
            "medium_long": "Medium-long run. Steady aerobic effort.",
            "medium_long_mp": "Medium-long with marathon pace work. Building race-specific fitness.",
            "threshold": "Threshold work at 'comfortably hard' pace. Should be sustainable for ~60 min in a race.",
            "threshold_light": "Light threshold session. Maintain quality, shorter duration.",
            "rest": "Full rest. Recovery is when adaptation happens.",
            "gym": "Strength and mobility work. No running.",
            "recovery": "Recovery run. Extremely easy.",
            "strides": "Short accelerations to activate fast-twitch fibers.",
        }
        return defaults.get(workout_type, "Complete as prescribed.")


# Backwards compatibility - PlanGenerator alias
class PlanGenerator(ArchetypePlanGenerator):
    """Alias for backwards compatibility."""
    pass


def get_plan_generator(db: Session) -> PlanGenerator:
    """Factory function for dependency injection."""
    return PlanGenerator(db)
