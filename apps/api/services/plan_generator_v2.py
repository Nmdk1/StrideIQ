"""
Training Plan Generator v2

Generates complete training plans from archetypes and workout templates.
Designed for review before production deployment.

Philosophy:
- Templates define structure, generator fills content
- Paces are calculated from athlete VDOT or defaults
- Age adjustments apply to paces, not structure (until 60+)
- 80/20 intensity distribution is sacred
"""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from typing import List, Dict, Optional, Any
from enum import Enum
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================

PLANS_DIR = Path(__file__).parent.parent.parent.parent / "plans"
ARCHETYPES_DIR = PLANS_DIR / "archetypes"
WORKOUTS_DIR = PLANS_DIR / "workouts"
GENERATED_DIR = PLANS_DIR / "generated"


class MileageLevel(str, Enum):
    LOW = "low"
    MID = "mid"
    HIGH = "high"
    MONSTER = "monster"


class RaceDistance(str, Enum):
    FIVE_K = "5k"
    TEN_K = "10k"
    HALF = "half_marathon"
    FULL = "marathon"


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class TrainingPaces:
    """Training paces in min/mile"""
    easy: float          # e.g., 9.5 = 9:30/mile
    recovery: float
    long_run: float
    marathon: float
    tempo: float
    threshold: float
    interval: float
    
    @classmethod
    def from_vdot(cls, vdot: float) -> "TrainingPaces":
        """Calculate training paces from VDOT."""
        # Daniels' formulas (simplified)
        # These are approximate - real implementation uses lookup tables
        
        # Easy: ~65-75% VO2max
        easy = 14.5 - (vdot * 0.1)
        recovery = easy + 0.5
        long_run = easy + 0.25
        
        # Marathon: ~80% VO2max
        marathon = 12.5 - (vdot * 0.1)
        
        # Tempo/Threshold: ~88% VO2max
        tempo = 11.0 - (vdot * 0.1)
        threshold = tempo - 0.15
        
        # Interval: ~95-100% VO2max
        interval = 9.5 - (vdot * 0.1)
        
        return cls(
            easy=max(6.0, min(15.0, easy)),
            recovery=max(6.5, min(16.0, recovery)),
            long_run=max(6.0, min(15.0, long_run)),
            marathon=max(5.5, min(14.0, marathon)),
            tempo=max(5.0, min(12.0, tempo)),
            threshold=max(5.0, min(12.0, threshold)),
            interval=max(4.5, min(10.0, interval)),
        )
    
    @classmethod
    def default_by_mileage(cls, level: MileageLevel) -> "TrainingPaces":
        """Default paces based on mileage level (no athlete data)."""
        defaults = {
            MileageLevel.LOW: cls(easy=11.0, recovery=11.5, long_run=11.0, marathon=10.0, tempo=9.0, threshold=8.5, interval=7.5),
            MileageLevel.MID: cls(easy=9.5, recovery=10.0, long_run=9.5, marathon=8.5, tempo=7.5, threshold=7.0, interval=6.5),
            MileageLevel.HIGH: cls(easy=8.5, recovery=9.0, long_run=8.5, marathon=7.5, tempo=6.5, threshold=6.0, interval=5.5),
            MileageLevel.MONSTER: cls(easy=7.5, recovery=8.0, long_run=7.5, marathon=6.5, tempo=5.5, threshold=5.0, interval=4.75),
        }
        return defaults[level]
    
    def format_pace(self, minutes: float) -> str:
        """Format pace as MM:SS."""
        mins = int(minutes)
        secs = int((minutes - mins) * 60)
        return f"{mins}:{secs:02d}"
    
    def to_dict(self) -> Dict[str, str]:
        return {
            "easy": self.format_pace(self.easy),
            "recovery": self.format_pace(self.recovery),
            "long_run": self.format_pace(self.long_run),
            "marathon": self.format_pace(self.marathon),
            "tempo": self.format_pace(self.tempo),
            "threshold": self.format_pace(self.threshold),
            "interval": self.format_pace(self.interval),
        }


@dataclass
class Workout:
    """A single workout in the plan."""
    day_of_week: str
    workout_type: str
    name: str
    description: str
    target_distance_miles: Optional[float] = None
    target_duration_minutes: Optional[int] = None
    target_pace: Optional[str] = None
    intensity: str = "easy"
    notes: Optional[str] = None


@dataclass
class TrainingWeek:
    """A week of training."""
    week_number: int
    phase: str
    total_miles: float
    workouts: List[Workout] = field(default_factory=list)
    focus: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class GeneratedPlan:
    """A complete generated training plan."""
    id: str
    name: str
    distance: str
    mileage_level: str
    days_per_week: int
    duration_weeks: int
    total_miles: float
    race_date: Optional[str] = None
    paces: Optional[Dict[str, str]] = None
    weeks: List[TrainingWeek] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "distance": self.distance,
            "mileage_level": self.mileage_level,
            "days_per_week": self.days_per_week,
            "duration_weeks": self.duration_weeks,
            "total_miles": round(self.total_miles, 1),
            "race_date": self.race_date,
            "paces": self.paces,
            "weeks": [asdict(w) for w in self.weeks],
            "meta": self.meta,
        }


# =============================================================================
# PLAN GENERATOR
# =============================================================================

class PlanGenerator:
    """
    Generates complete training plans from archetypes.
    """
    
    def __init__(self):
        self.archetypes: Dict[str, Dict] = {}
        self.workouts: Dict[str, Dict] = {}
        self._load_templates()
    
    def _load_templates(self):
        """Load all archetype and workout templates."""
        # Load archetypes
        if ARCHETYPES_DIR.exists():
            for f in ARCHETYPES_DIR.glob("*.json"):
                with open(f) as file:
                    data = json.load(file)
                    self.archetypes[data["id"]] = data
        
        # Load workouts
        if WORKOUTS_DIR.exists():
            for f in WORKOUTS_DIR.glob("*.json"):
                with open(f) as file:
                    data = json.load(file)
                    self.workouts[data["id"]] = data
    
    def generate(
        self,
        distance: str,
        mileage_level: str,
        days_per_week: int,
        duration_weeks: int,
        target_weekly_miles: Optional[float] = None,
        vdot: Optional[float] = None,
        race_date: Optional[date] = None,
        athlete_age: Optional[int] = None,
    ) -> GeneratedPlan:
        """
        Generate a complete training plan.
        
        Args:
            distance: Race distance (5k, 10k, half_marathon, marathon)
            mileage_level: low, mid, high, monster
            days_per_week: 4, 5, 6, or 7
            duration_weeks: 12 or 18
            target_weekly_miles: Peak weekly mileage (optional)
            vdot: Athlete's VDOT for pace calculation (optional)
            race_date: Target race date (optional)
            athlete_age: For recovery adjustments (optional)
        """
        # Find archetype
        archetype_id = f"{distance}_{mileage_level}"
        if archetype_id not in self.archetypes:
            raise ValueError(f"No archetype found for {archetype_id}")
        
        archetype = self.archetypes[archetype_id]
        
        # Validate days_per_week
        if days_per_week not in archetype["supported_days_per_week"]:
            supported = archetype["supported_days_per_week"]
            raise ValueError(f"{archetype_id} supports {supported} days/week, not {days_per_week}")
        
        # Validate duration
        if duration_weeks not in archetype["supported_durations_weeks"]:
            supported = archetype["supported_durations_weeks"]
            raise ValueError(f"{archetype_id} supports {supported} week plans, not {duration_weeks}")
        
        # Calculate paces
        if vdot:
            paces = TrainingPaces.from_vdot(vdot)
        else:
            paces = TrainingPaces.default_by_mileage(MileageLevel(mileage_level))
        
        # Determine target weekly miles
        if target_weekly_miles is None:
            low, high = archetype["weekly_mileage_range"]
            target_weekly_miles = (low + high) / 2
        
        # Get phase structure
        phase_key = f"{duration_weeks}_week"
        phases = archetype["phases"][phase_key]
        
        # Get week template
        week_template = archetype["week_templates"][f"{days_per_week}_days"]
        
        # Generate weeks
        weeks = []
        total_miles = 0
        quality_rotation_idx = 0
        
        for week_num in range(1, duration_weeks + 1):
            # Find current phase
            current_phase = None
            volume_pct = 100
            
            for phase_name, phase_data in phases.items():
                if week_num in phase_data["weeks"]:
                    current_phase = phase_name
                    week_idx = phase_data["weeks"].index(week_num)
                    volume_pct = phase_data["volume_pct"][week_idx]
                    break
            
            # Calculate week's mileage
            week_miles = target_weekly_miles * (volume_pct / 100)
            
            # Get long run for this week
            long_run_data = archetype["long_run_progression"][phase_key].get(str(week_num), {"miles": 10, "type": "easy"})
            long_run_miles = long_run_data["miles"]
            long_run_type = long_run_data["type"]
            
            # Generate workouts
            workouts = self._generate_week_workouts(
                week_template=week_template,
                week_miles=week_miles,
                long_run_miles=long_run_miles,
                long_run_type=long_run_type,
                paces=paces,
                phase=current_phase,
                archetype=archetype,
                quality_idx=quality_rotation_idx,
            )
            
            week = TrainingWeek(
                week_number=week_num,
                phase=current_phase,
                total_miles=round(week_miles, 1),
                workouts=workouts,
                focus=phases[current_phase]["focus"] if current_phase else None,
            )
            
            weeks.append(week)
            total_miles += week_miles
            quality_rotation_idx += 1
        
        # Build plan
        plan = GeneratedPlan(
            id=f"{distance}_{mileage_level}_{days_per_week}d_{duration_weeks}w",
            name=f"{distance.replace('_', ' ').title()} - {mileage_level.title()} Mileage ({days_per_week} days/week, {duration_weeks} weeks)",
            distance=distance,
            mileage_level=mileage_level,
            days_per_week=days_per_week,
            duration_weeks=duration_weeks,
            total_miles=total_miles,
            race_date=race_date.isoformat() if race_date else None,
            paces=paces.to_dict(),
            weeks=weeks,
            meta={
                "generated_at": date.today().isoformat(),
                "archetype": archetype_id,
                "vdot": vdot,
                "target_weekly_miles": target_weekly_miles,
            }
        )
        
        return plan
    
    def _generate_week_workouts(
        self,
        week_template: Dict,
        week_miles: float,
        long_run_miles: float,
        long_run_type: str,
        paces: TrainingPaces,
        phase: str,
        archetype: Dict,
        quality_idx: int,
    ) -> List[Workout]:
        """Generate individual workouts for a week."""
        
        pattern = week_template["pattern"]
        volume_dist = week_template["volume_distribution"]
        q1_rotation = week_template["quality_1_rotation"]
        q2_rotation = week_template["quality_2_rotation"]
        
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        workouts = []
        
        for i, (day, workout_type, pct) in enumerate(zip(days, pattern, volume_dist)):
            if workout_type == "rest":
                workouts.append(Workout(
                    day_of_week=day,
                    workout_type="rest",
                    name="Rest Day",
                    description="Complete rest or light cross-training.",
                    intensity="rest",
                ))
                continue
            
            # Calculate distance for this workout
            if workout_type == "long":
                distance = long_run_miles
            else:
                distance = (week_miles * pct / 100)
            
            # Build workout based on type
            if workout_type == "easy":
                workouts.append(Workout(
                    day_of_week=day,
                    workout_type="easy",
                    name="Easy Run",
                    description=f"Easy pace run. Keep it conversational.",
                    target_distance_miles=round(distance, 1),
                    target_pace=paces.format_pace(paces.easy),
                    intensity="easy",
                ))
            
            elif workout_type == "recovery":
                workouts.append(Workout(
                    day_of_week=day,
                    workout_type="recovery",
                    name="Recovery Run",
                    description="Very easy. Slower than normal easy pace.",
                    target_distance_miles=round(distance, 1),
                    target_pace=paces.format_pace(paces.recovery),
                    intensity="recovery",
                ))
            
            elif workout_type == "long":
                desc = self._get_long_run_description(long_run_type, paces)
                workouts.append(Workout(
                    day_of_week=day,
                    workout_type="long_run",
                    name=f"Long Run ({long_run_type.replace('_', ' ').title()})",
                    description=desc,
                    target_distance_miles=round(distance, 1),
                    target_pace=paces.format_pace(paces.long_run),
                    intensity="moderate" if long_run_type != "easy" else "easy",
                ))
            
            elif workout_type == "quality_1":
                q_type = q1_rotation[quality_idx % len(q1_rotation)]
                workout = self._build_quality_workout(q_type, distance, paces, phase, archetype, day)
                workouts.append(workout)
            
            elif workout_type == "quality_2":
                q_type = q2_rotation[quality_idx % len(q2_rotation)]
                workout = self._build_quality_workout(q_type, distance, paces, phase, archetype, day)
                workouts.append(workout)
        
        return workouts
    
    def _get_long_run_description(self, run_type: str, paces: TrainingPaces) -> str:
        """Get description for long run based on type."""
        descriptions = {
            "easy": f"Steady effort at {paces.format_pace(paces.long_run)}/mile. Focus on time on feet.",
            "progression": f"Start easy ({paces.format_pace(paces.easy)}), finish last 20-30% at {paces.format_pace(paces.marathon)}/mile.",
            "mp_finish": f"Easy for first half, then finish final 4-6 miles at marathon pace ({paces.format_pace(paces.marathon)}/mile).",
            "dress_rehearsal": f"Practice race day nutrition. Run at marathon pace ({paces.format_pace(paces.marathon)}/mile) for middle portion.",
            "race_week_shakeout": f"Short and easy. Just loosen up the legs before race day.",
        }
        return descriptions.get(run_type, "Easy effort throughout.")
    
    def _build_quality_workout(
        self,
        workout_type: str,
        total_distance: float,
        paces: TrainingPaces,
        phase: str,
        archetype: Dict,
        day: str,
    ) -> Workout:
        """Build a quality workout (tempo, intervals, etc)."""
        
        # Get progression level based on phase
        if phase in ["base", "base_1"]:
            level = "base"
        elif phase in ["build", "build_1", "build_2"]:
            level = "build"
        else:
            level = "peak"
        
        progressions = archetype.get("quality_progressions", {})
        
        if workout_type == "tempo":
            main = progressions.get("tempo", {}).get(level, "20 min steady")
            return Workout(
                day_of_week=day,
                workout_type="tempo",
                name="Tempo Run",
                description=f"Warm up 15 min easy, then {main} at tempo pace ({paces.format_pace(paces.tempo)}/mile), cool down 10 min.",
                target_distance_miles=round(total_distance, 1),
                target_pace=paces.format_pace(paces.tempo),
                intensity="hard",
            )
        
        elif workout_type == "threshold":
            main = progressions.get("threshold", {}).get(level, "3x1mile")
            return Workout(
                day_of_week=day,
                workout_type="threshold",
                name="Threshold Intervals",
                description=f"Warm up 15 min, {main} at threshold pace ({paces.format_pace(paces.threshold)}/mile) with 1 min jog recovery, cool down 10 min.",
                target_distance_miles=round(total_distance, 1),
                target_pace=paces.format_pace(paces.threshold),
                intensity="hard",
            )
        
        elif workout_type == "intervals":
            main = progressions.get("intervals", {}).get(level, "6x800m")
            return Workout(
                day_of_week=day,
                workout_type="intervals",
                name="VO2max Intervals",
                description=f"Warm up 15 min + strides, {main} at interval pace ({paces.format_pace(paces.interval)}/mile) with equal jog recovery, cool down 10 min.",
                target_distance_miles=round(total_distance, 1),
                target_pace=paces.format_pace(paces.interval),
                intensity="very_hard",
            )
        
        elif workout_type == "marathon_pace":
            miles = progressions.get("marathon_pace", {}).get(level, "4-5 miles")
            return Workout(
                day_of_week=day,
                workout_type="marathon_pace",
                name="Marathon Pace Run",
                description=f"Warm up 10 min easy, {miles} at marathon pace ({paces.format_pace(paces.marathon)}/mile), cool down 10 min. Practice race nutrition.",
                target_distance_miles=round(total_distance, 1),
                target_pace=paces.format_pace(paces.marathon),
                intensity="moderate",
            )
        
        elif workout_type == "hills":
            return Workout(
                day_of_week=day,
                workout_type="hills",
                name="Hill Repeats",
                description="Warm up 15 min, 6-8 x 60-90 sec uphill at hard effort, jog down recovery, cool down 10 min.",
                target_distance_miles=round(total_distance, 1),
                target_pace="effort-based",
                intensity="hard",
            )
        
        else:
            # Fallback to easy
            return Workout(
                day_of_week=day,
                workout_type="easy",
                name="Easy Run",
                description="Easy effort.",
                target_distance_miles=round(total_distance, 1),
                target_pace=paces.format_pace(paces.easy),
                intensity="easy",
            )
    
    def save_preview(self, plan: GeneratedPlan, filename: Optional[str] = None) -> Path:
        """Save plan to generated folder for review."""
        if filename is None:
            filename = f"preview_{plan.id}.json"
        
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)
        path = GENERATED_DIR / filename
        
        with open(path, "w") as f:
            json.dump(plan.to_dict(), f, indent=2)
        
        return path


# =============================================================================
# CLI FOR PREVIEW GENERATION
# =============================================================================

def generate_preview():
    """Generate a preview plan for review."""
    generator = PlanGenerator()
    
    # Generate the example plan
    plan = generator.generate(
        distance="marathon",
        mileage_level="mid",
        days_per_week=5,
        duration_weeks=18,
        target_weekly_miles=50,
    )
    
    # Save for review
    path = generator.save_preview(plan)
    print(f"Generated plan saved to: {path}")
    print(f"Total miles: {plan.total_miles:.1f}")
    print(f"Peak week: Week {max(w.week_number for w in plan.weeks if w.total_miles == max(wk.total_miles for wk in plan.weeks))}")
    
    return plan


if __name__ == "__main__":
    generate_preview()
