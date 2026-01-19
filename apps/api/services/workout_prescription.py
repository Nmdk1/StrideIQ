"""
Workout Prescription Generator (ADR-031)

Generates specific workout prescriptions with:
- Exact structures ("2x3mi @ T" not "threshold work")
- Personal paces from VDOT
- Appropriate progression based on week theme

Tone: Sparse, precise, no motivational BS.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import List, Dict, Optional, Tuple
import logging
import random

from services.fitness_bank import FitnessBank, ExperienceLevel
from services.vdot_calculator import calculate_training_paces
from services.week_theme_generator import WeekTheme

logger = logging.getLogger(__name__)


# =============================================================================
# PACE CALCULATION
# =============================================================================

def _parse_pace_str_to_seconds_per_mile(pace_str: Optional[str]) -> Optional[int]:
    """
    Parse a pace string into seconds per mile.

    Accepts "M:SS" (or "H:MM:SS") and returns total seconds per mile.
    """
    if not pace_str or not isinstance(pace_str, str):
        return None

    parts = pace_str.strip().split(":")
    if len(parts) == 2:
        mins_str, secs_str = parts
        hrs = 0
    elif len(parts) == 3:
        hrs_str, mins_str, secs_str = parts
        try:
            hrs = int(hrs_str)
        except ValueError:
            return None
    else:
        return None

    try:
        mins = int(mins_str)
        secs = int(secs_str)
    except ValueError:
        return None

    if mins < 0 or secs < 0 or secs >= 60:
        return None

    return hrs * 3600 + mins * 60 + secs


def _calculate_paces_from_training_paces(vdot: float) -> Dict[str, float]:
    """
    Unified pace source (ADR-040).

    Uses Daniels/Gilbert physics from `services.vdot_calculator.calculate_training_paces()`
    and adapts its output into this generator's expected format:

        {"threshold": 6.53, ...}  # float minutes per mile

    Notes:
    - `vdot_calculator` doesn't provide explicit "long" or "recovery" paces; we derive them
      conservatively from easy pace (+9s and +30s respectively) to preserve existing keys.
    """
    raw = calculate_training_paces(vdot)

    def seconds_for(zone: str) -> Optional[int]:
        zone_val = raw.get(zone)
        if isinstance(zone_val, dict):
            return _parse_pace_str_to_seconds_per_mile(zone_val.get("mi"))
        return None

    easy_sec = seconds_for("easy")
    marathon_sec = seconds_for("marathon")
    threshold_sec = seconds_for("threshold")
    interval_sec = seconds_for("interval")

    if easy_sec is None or marathon_sec is None or threshold_sec is None or interval_sec is None:
        logger.warning(
            "Could not derive training paces from vdot_calculator output; "
            f"vdot={vdot}, raw_keys={list(raw.keys())}"
        )
        # Fail-safe: keep generator functional with conservative defaults rather than crashing.
        # (Should not happen for valid VDOTs.)
        easy_sec = easy_sec or 540  # 9:00
        marathon_sec = marathon_sec or 480  # 8:00
        threshold_sec = threshold_sec or 450  # 7:30
        interval_sec = interval_sec or 405  # 6:45

    # Preserve existing keys expected across plan generation logic.
    long_sec = easy_sec + 9
    recovery_sec = easy_sec + 30

    return {
        "easy": easy_sec / 60.0,
        "long": long_sec / 60.0,
        "marathon": marathon_sec / 60.0,
        "threshold": threshold_sec / 60.0,
        "interval": interval_sec / 60.0,
        "recovery": recovery_sec / 60.0,
    }


# Backward-compatible public API used elsewhere (planner, tests, scripts).
def calculate_paces_from_vdot(vdot: float) -> Dict[str, float]:
    return _calculate_paces_from_training_paces(vdot)


def format_pace(pace_minutes: float) -> str:
    """Format pace as M:SS."""
    total_seconds = int(round(pace_minutes * 60))
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def format_pace_range(pace_minutes: float, range_sec: int = 10) -> str:
    """Format pace as range (e.g., 6:45-6:55)."""
    low = pace_minutes - (range_sec / 120)
    high = pace_minutes + (range_sec / 120)
    return f"{format_pace(low)}-{format_pace(high)}"


# =============================================================================
# WORKOUT STRUCTURES
# =============================================================================

@dataclass
class WorkoutStructure:
    """A specific workout structure."""
    name: str
    description: str
    total_miles: float
    quality_miles: float
    workout_type: str
    intensity: str
    tss_multiplier: float = 1.0


# Threshold workout structures by experience
THRESHOLD_STRUCTURES = {
    ExperienceLevel.ELITE: [
        WorkoutStructure("2x4mi @ T", "{warm}E + 2x4mi @ {t_pace} w/ 3min jog + {cool}E", 14, 8, "threshold", "hard", 1.3),
        WorkoutStructure("3x3mi @ T", "{warm}E + 3x3mi @ {t_pace} w/ 2min jog + {cool}E", 13, 9, "threshold", "hard", 1.3),
        WorkoutStructure("10mi @ T straight", "{warm}E + 10mi @ {t_pace} + {cool}E", 14, 10, "threshold", "hard", 1.4),
        WorkoutStructure("8mi @ T straight", "{warm}E + 8mi @ {t_pace} + {cool}E", 12, 8, "threshold", "hard", 1.35),
    ],
    ExperienceLevel.EXPERIENCED: [
        WorkoutStructure("2x3mi @ T", "{warm}E + 2x3mi @ {t_pace} w/ 2min jog + {cool}E", 10, 6, "threshold", "hard", 1.25),
        WorkoutStructure("3x2mi @ T", "{warm}E + 3x2mi @ {t_pace} w/ 2min jog + {cool}E", 10, 6, "threshold", "hard", 1.25),
        WorkoutStructure("6mi @ T straight", "{warm}E + 6mi @ {t_pace} + {cool}E", 10, 6, "threshold", "hard", 1.3),
    ],
    ExperienceLevel.INTERMEDIATE: [
        WorkoutStructure("2x15min @ T", "{warm}E + 2x15min @ {t_pace} w/ 3min jog + {cool}E", 8, 4, "threshold", "hard", 1.2),
        WorkoutStructure("3x10min @ T", "{warm}E + 3x10min @ {t_pace} w/ 2min jog + {cool}E", 8, 4, "threshold", "hard", 1.2),
        WorkoutStructure("20min @ T", "{warm}E + 20min @ {t_pace} + {cool}E", 7, 3, "threshold", "hard", 1.2),
    ],
    ExperienceLevel.BEGINNER: [
        WorkoutStructure("2x10min @ T", "{warm}E + 2x10min @ {t_pace} w/ 3min jog + {cool}E", 6, 2.5, "threshold", "moderate", 1.15),
        WorkoutStructure("3x8min @ T", "{warm}E + 3x8min @ {t_pace} w/ 2min jog + {cool}E", 6, 3, "threshold", "moderate", 1.15),
    ]
}

# MP long run structures
MP_LONG_RUN_STRUCTURES = [
    # (name, description_template, mp_portion_ratio, phase)
    ("MP finish", "{total}mi with last {mp}mi @ MP ({mp_pace})", 0.30, "early"),
    ("MP middle", "{total}mi with middle {mp}mi @ MP ({mp_pace})", 0.40, "mid"),
    ("MP progression", "{total}mi: {easy}E easy + {mp}mi @ MP ({mp_pace})", 0.50, "mid"),
    ("Race simulation", "{total}mi with {mp}mi @ MP ({mp_pace}) - race simulation", 0.70, "peak"),
]

# Interval structures
INTERVAL_STRUCTURES = {
    ExperienceLevel.ELITE: [
        WorkoutStructure("6x1000m", "{warm}E + 6x1000m @ {i_pace} w/ 400m jog + {cool}E", 10, 4, "intervals", "very_hard", 1.4),
        WorkoutStructure("5x1200m", "{warm}E + 5x1200m @ {i_pace} w/ 400m jog + {cool}E", 10, 4, "intervals", "very_hard", 1.4),
        WorkoutStructure("12x400m", "{warm}E + 12x400m @ {i_pace} w/ 200m jog + {cool}E", 9, 3, "intervals", "very_hard", 1.35),
    ],
    ExperienceLevel.EXPERIENCED: [
        WorkoutStructure("5x1000m", "{warm}E + 5x1000m @ {i_pace} w/ 400m jog + {cool}E", 8, 3, "intervals", "very_hard", 1.35),
        WorkoutStructure("4x1200m", "{warm}E + 4x1200m @ {i_pace} w/ 400m jog + {cool}E", 8, 3, "intervals", "very_hard", 1.35),
    ],
    ExperienceLevel.INTERMEDIATE: [
        WorkoutStructure("4x800m", "{warm}E + 4x800m @ {i_pace} w/ 400m jog + {cool}E", 6, 2, "intervals", "hard", 1.25),
        WorkoutStructure("6x600m", "{warm}E + 6x600m @ {i_pace} w/ 300m jog + {cool}E", 6, 2.5, "intervals", "hard", 1.25),
    ],
    ExperienceLevel.BEGINNER: [
        WorkoutStructure("4x400m", "{warm}E + 4x400m @ {i_pace} w/ 400m jog + {cool}E", 5, 1, "intervals", "moderate", 1.15),
        WorkoutStructure("3x600m", "{warm}E + 3x600m @ {i_pace} w/ 400m jog + {cool}E", 5, 1.2, "intervals", "moderate", 1.15),
    ]
}


# =============================================================================
# DAY PLAN DATA CLASS
# =============================================================================

@dataclass
class DayPlan:
    """A single day's workout plan."""
    day_of_week: int                      # 0=Mon, 6=Sun
    workout_type: str                     # easy, long, threshold, intervals, rest, race
    name: str                             # "2x3mi @ T"
    description: str                      # Full description with paces
    target_miles: float
    intensity: str                        # easy, moderate, hard, very_hard, race
    paces: Dict[str, str]                 # {zone: "M:SS"}
    notes: List[str] = field(default_factory=list)
    tss_estimate: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "day_of_week": self.day_of_week,
            "workout_type": self.workout_type,
            "name": self.name,
            "description": self.description,
            "target_miles": self.target_miles,
            "intensity": self.intensity,
            "paces": self.paces,
            "notes": self.notes,
            "tss": round(self.tss_estimate, 0)
        }


@dataclass
class WeekPlan:
    """A full week's workout plan."""
    week_number: int
    theme: WeekTheme
    start_date: date
    days: List[DayPlan]
    total_miles: float
    notes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "week": self.week_number,
            "theme": self.theme.value,
            "start_date": self.start_date.isoformat(),
            "days": [d.to_dict() for d in self.days],
            "total_miles": round(self.total_miles, 1),
            "notes": self.notes
        }


# =============================================================================
# WORKOUT PRESCRIPTION GENERATOR
# =============================================================================

class WorkoutPrescriptionGenerator:
    """
    Generate specific workout prescriptions.
    
    Outputs concrete workouts with structures and paces,
    not generic "threshold work" or "tempo run".
    
    N=1 Approach:
    - Long runs PROGRESS from current capability to race-appropriate peaks
    - Volume builds to support the long runs
    - τ1 informs recovery rhythm (fast adapters handle more aggressive cycles)
    - Quality focus varies by distance (VO2max for 5K, MP for marathon)
    - Variety in neuromuscular work (rotate strides, hills, drills)
    - Hill work is safe for ALL levels (scaled reps)
    """
    
    # Long run targets by race distance (where we need to GET TO, not cap)
    LONG_RUN_PEAK_TARGETS = {
        "5k": 14,           # Don't need 20 milers for 5K
        "10k": 16,
        "10_mile": 18,
        "half": 18,
        "half_marathon": 18,
        "marathon": 22      # Need to get to 20-22 for marathon
    }
    
    # Long run constraints (safety, not arbitrary caps)
    LONG_RUN_MAX_MINUTES = 180      # 3 hours is reasonable upper limit
    LONG_RUN_MAX_VOLUME_PCT = 0.35  # Single run shouldn't exceed 35% of weekly
    
    # Whether to include race-pace long runs for this distance
    USE_RACE_PACE_LONG_RUNS = {
        "5k": False,       # 5K doesn't need race-pace long runs
        "10k": False,      # 10K focuses on threshold/VO2
        "10_mile": True,   # Can benefit from tempo long runs
        "half": True,      # HMP long runs in late build
        "half_marathon": True,
        "marathon": True   # MP long runs are key
    }
    
    # Primary quality focus by distance
    QUALITY_FOCUS = {
        "5k": ["vo2max", "speed", "threshold"],
        "10k": ["threshold", "vo2max"],
        "10_mile": ["threshold", "mp"],
        "half": ["threshold", "mp"],
        "half_marathon": ["threshold", "mp"],
        "marathon": ["mp", "threshold"]
    }
    
    # Neuromuscular work types for variety rotation
    NEUROMUSCULAR_TYPES = [
        "strides",          # Flat strides, 6x100m
        "hill_sprints",     # 8-10x10sec max effort
        "hill_strides",     # 6x100m on gentle hill (power + form)
    ]
    
    def __init__(self, bank: FitnessBank, race_distance: str = "marathon"):
        self.bank = bank
        self.race_distance = race_distance.lower()
        self.paces = _calculate_paces_from_training_paces(bank.best_vdot)
        self.experience = bank.experience_level
        
        # =====================================================================
        # ADR-038: N=1 Long Run Progression
        # 
        # Start from CURRENT capability (what they're actually doing)
        # Progress to PEAK capability (what they've proven they can do)
        # =====================================================================
        
        # Current: use recent long run data, with fallbacks
        current_from_data = getattr(bank, 'current_long_run_miles', 0.0)
        average_from_data = getattr(bank, 'average_long_run_miles', 0.0)
        
        # Establish starting point using N=1 data
        if current_from_data > 0:
            # Best case: we have recent long run data
            self.long_run_current = current_from_data
        elif average_from_data > 0:
            # Fallback: use 70% of their average
            self.long_run_current = average_from_data * 0.70
        else:
            # Last resort: estimate from weekly volume (conservative)
            self.long_run_current = max(bank.current_weekly_miles * 0.25, 6.0)
        
        # Ensure minimum based on race distance
        distance_minimums = {
            "5k": 6.0, "10k": 8.0, "10_mile": 10.0,
            "half": 10.0, "half_marathon": 10.0, "marathon": 10.0
        }
        self.long_run_current = max(
            self.long_run_current,
            distance_minimums.get(self.race_distance, 8.0)
        )
        
        # Peak target: use proven capability but respect distance-specific appropriateness
        distance_peak_target = self.LONG_RUN_PEAK_TARGETS.get(self.race_distance, 18)
        proven_peak = bank.peak_long_run_miles
        
        # For shorter distances, cap peak at distance-appropriate level
        # A 5K runner doesn't need 22-mile long runs even if they've done them for marathons
        distance_max = distance_peak_target * 1.15  # Allow 15% above target max
        
        if proven_peak >= distance_peak_target * 0.9:
            # They've proven capability - use it but cap at distance-appropriate level
            self.long_run_peak = min(proven_peak, distance_max)
            self._proven_capability_used = True
        elif proven_peak > 0:
            # They have some history - allow stretch to target (max 4mi beyond proven)
            self.long_run_peak = min(distance_peak_target, proven_peak + 4)
            self._proven_capability_used = False
        else:
            # No history - use distance-appropriate target
            self.long_run_peak = distance_peak_target
            self._proven_capability_used = False
        
        # Legacy compatibility
        self.long_run_start = self.long_run_current  # Redirect old references
        self.long_run_peak_target = self.long_run_peak
        self.long_run_cap = self.long_run_peak
        
        self.use_mp_long_runs = self.USE_RACE_PACE_LONG_RUNS.get(self.race_distance, True)
        self.quality_focus = self.QUALITY_FOCUS.get(self.race_distance, ["threshold"])
        
        # Format paces for display
        self.pace_strs = {k: format_pace(v) for k, v in self.paces.items()}
        
        # Track recent neuromuscular work for variety
        self._recent_neuro_types: List[str] = []
        
        logger.info(
            f"N=1 Long Run Progression (ADR-038): "
            f"current={self.long_run_current:.1f}mi → "
            f"peak={self.long_run_peak:.1f}mi | "
            f"from_data={current_from_data:.1f}mi, avg={average_from_data:.1f}mi | "
            f"proven={proven_peak:.1f}mi, distance={self.race_distance}"
        )
    
    def calculate_long_run_for_week(self, week_number: int, total_weeks: int, 
                                     theme: WeekTheme) -> float:
        """
        Calculate long run distance using N=1 progression (ADR-038).
        
        Algorithm:
        1. Start from current capability (not peak)
        2. Progress linearly to peak over build weeks
        3. Apply phase-specific adjustments
        4. Respect safety constraints (max 2mi/week increase)
        
        This produces smooth progression like: 12 → 14 → 16 → 18 → 20 → 22
        Not dangerous jumps like: 10 → 22
        """
        # Taper/race/tune-up weeks: reduce from peak
        if theme in [WeekTheme.TAPER_1, WeekTheme.TAPER_2, WeekTheme.RACE, WeekTheme.TUNE_UP_RACE]:
            reduction_pct = {
                WeekTheme.TAPER_1: 0.70,       # 70% of peak
                WeekTheme.TAPER_2: 0.55,       # 55% of peak
                WeekTheme.TUNE_UP_RACE: 0.50,  # 50% - the race itself is the work
                WeekTheme.RACE: 0.40,          # 40% (shakeout)
            }
            return self.long_run_peak * reduction_pct.get(theme, 0.60)
        
        # Recovery weeks: mid-point between current and peak
        if theme == WeekTheme.RECOVERY:
            return self.long_run_current + (self.long_run_peak - self.long_run_current) * 0.5
        
        # Calculate build progression
        # Reserve last 3 weeks for taper
        build_weeks = max(1, total_weeks - 3)
        
        # Progress factor: 0.0 at week 1, 1.0 at peak week
        progress = min(1.0, (week_number - 1) / build_weeks)
        
        # Linear progression from current to peak
        target = self.long_run_current + (self.long_run_peak - self.long_run_current) * progress
        
        # Safety: max 2 miles increase per week
        # Calculate what last week's target would have been
        if week_number > 1:
            prev_progress = min(1.0, (week_number - 2) / build_weeks)
            prev_target = self.long_run_current + (self.long_run_peak - self.long_run_current) * prev_progress
            max_increase = 2.0  # miles per week
            target = min(target, prev_target + max_increase)
        
        # Apply time safety (3 hours max)
        long_pace = self.paces.get("long", 9.0)
        time_limit = self.LONG_RUN_MAX_MINUTES / long_pace
        target = min(target, time_limit)
        
        # Floor: never go below current capability
        target = max(target, self.long_run_current)
        
        # Audit logging for debugging
        logger.debug(
            f"Long run week {week_number}/{total_weeks} ({theme.value}): "
            f"target={target:.1f}mi, progress={progress:.2f}, "
            f"current={self.long_run_current:.1f}, peak={self.long_run_peak:.1f}"
        )
        
        return target
    
    def _select_neuromuscular_type(self) -> str:
        """
        Select neuromuscular work type with variety.
        
        Rotates through types to prevent staleness.
        All athletes get hill work - it's safe for everyone.
        """
        # Filter out recently used types
        available = [t for t in self.NEUROMUSCULAR_TYPES 
                    if t not in self._recent_neuro_types[-2:]]  # Avoid last 2
        
        if not available:
            available = self.NEUROMUSCULAR_TYPES
        
        # Random selection from available
        selected = random.choice(available)
        
        # Track for variety
        self._recent_neuro_types.append(selected)
        if len(self._recent_neuro_types) > 4:
            self._recent_neuro_types.pop(0)
        
        return selected
    
    def generate_week(self,
                     theme: WeekTheme,
                     week_number: int,
                     total_weeks: int,
                     target_miles: float,
                     start_date: date) -> WeekPlan:
        """Generate a full week of workouts for given theme."""
        
        days = []
        
        # Get day assignments based on theme, patterns, and progressive long run
        day_assignments = self._assign_days_by_theme(theme, target_miles, week_number, total_weeks)
        
        for day_idx in range(7):
            current_date = start_date + timedelta(days=day_idx)
            assignment = day_assignments.get(day_idx)
            
            if assignment is None:
                # Rest day
                days.append(DayPlan(
                    day_of_week=day_idx,
                    workout_type="rest",
                    name="Rest",
                    description="Full rest or cross-training",
                    target_miles=0,
                    intensity="rest",
                    paces={},
                    notes=[]
                ))
            else:
                workout_type, miles = assignment
                day_plan = self._generate_day_workout(
                    day_idx=day_idx,
                    workout_type=workout_type,
                    target_miles=miles,
                    theme=theme,
                    week_number=week_number,
                    total_weeks=total_weeks
                )
                days.append(day_plan)
        
        total = sum(d.target_miles for d in days)
        
        return WeekPlan(
            week_number=week_number,
            theme=theme,
            start_date=start_date,
            days=days,
            total_miles=total,
            notes=self._get_week_notes(theme, week_number, total_weeks)
        )
    
    def _assign_days_by_theme(self, theme: WeekTheme, target_miles: float,
                              week_number: int = 1, total_weeks: int = 12) -> Dict[int, Tuple[str, float]]:
        """
        Assign workout types and miles to days based on theme.
        
        Uses progressive long run calculation rather than fixed percentages.
        """
        
        # Get preferred days from bank
        long_day = self.bank.typical_long_run_day if self.bank.typical_long_run_day is not None else 6
        quality_day = self.bank.typical_quality_day if self.bank.typical_quality_day is not None else 3
        rest_days = self.bank.typical_rest_days if self.bank.typical_rest_days else [0]
        
        assignments = {}
        
        # Rest day(s)
        primary_rest = rest_days[0] if rest_days else 0
        
        # Progressive long run for this week (not fixed percentage)
        progressive_long = self.calculate_long_run_for_week(week_number, total_weeks, theme)
        
        if theme == WeekTheme.REBUILD_EASY:
            # All easy, one rest
            # ADR-038: Use progressive_long for long run, not volume-based calculation
            available_days = [d for d in range(7) if d != primary_rest]
            remaining_miles = target_miles - progressive_long
            easy_days = [d for d in available_days if d != long_day]
            miles_per_easy = remaining_miles / len(easy_days) if easy_days else 5.0
            
            for d in available_days:
                if d == long_day:
                    assignments[d] = ("easy_long", progressive_long)
                else:
                    assignments[d] = ("easy", miles_per_easy)
        
        elif theme == WeekTheme.REBUILD_STRIDES:
            # Easy with strides, one rest
            # ADR-038: Use progressive_long for long run, not volume-based calculation
            available_days = [d for d in range(7) if d != primary_rest]
            remaining_miles = target_miles - progressive_long
            easy_days = [d for d in available_days if d != long_day]
            miles_per_easy = remaining_miles / len(easy_days) if easy_days else 5.0
            
            for d in available_days:
                if d == long_day:
                    assignments[d] = ("easy_long", progressive_long)
                elif d == quality_day:
                    assignments[d] = ("easy_strides", miles_per_easy)
                else:
                    assignments[d] = ("easy", miles_per_easy * 0.95)
        
        elif theme == WeekTheme.BUILD_T_EMPHASIS:
            # Threshold focus + long run
            self._assign_standard_week(assignments, target_miles, long_day, quality_day, 
                                      primary_rest, quality_type="threshold", 
                                      progressive_long=progressive_long)
        
        elif theme == WeekTheme.BUILD_MP_EMPHASIS:
            # MP long run + secondary threshold
            self._assign_mp_week(assignments, target_miles, long_day, quality_day, primary_rest,
                                progressive_long=progressive_long)
        
        elif theme == WeekTheme.BUILD_MIXED:
            # Both quality types
            self._assign_standard_week(assignments, target_miles, long_day, quality_day,
                                      primary_rest, quality_type="threshold", add_mp=True,
                                      progressive_long=progressive_long)
        
        elif theme == WeekTheme.RECOVERY:
            # Easy only, extra rest
            second_rest = (primary_rest + 3) % 7
            available_days = [d for d in range(7) if d not in [primary_rest, second_rest]]
            miles_per_run = target_miles / len(available_days)
            for d in available_days:
                if d == long_day:
                    assignments[d] = ("easy_long", miles_per_run * 1.3)
                else:
                    assignments[d] = ("easy", miles_per_run * 0.9)
        
        elif theme == WeekTheme.PEAK:
            # Maximum quality
            self._assign_peak_week(assignments, target_miles, long_day, quality_day, primary_rest,
                                  progressive_long=progressive_long)
        
        elif theme == WeekTheme.SHARPEN:
            # Race-specific sharpening
            self._assign_sharpen_week(assignments, target_miles, long_day, quality_day, primary_rest,
                                     progressive_long=progressive_long)
        
        elif theme in (WeekTheme.TAPER_1, WeekTheme.TAPER_2):
            # Reduced volume, maintain some intensity
            self._assign_taper_week(assignments, target_miles, long_day, quality_day, 
                                   primary_rest, theme, progressive_long=progressive_long)
        
        elif theme == WeekTheme.TUNE_UP_RACE:
            # Race day with surrounding easy
            self._assign_tune_up_week(assignments, target_miles, long_day, quality_day, primary_rest)
        
        elif theme == WeekTheme.RACE:
            # Goal race week
            self._assign_race_week(assignments, target_miles, long_day, primary_rest)
        
        else:
            # Default to easy
            available_days = [d for d in range(7) if d != primary_rest]
            miles_per_run = target_miles / len(available_days)
            for d in available_days:
                assignments[d] = ("easy", miles_per_run)
        
        return assignments
    
    def _assign_standard_week(self, assignments, target, long_day, quality_day, 
                             rest_day, quality_type, add_mp=False, progressive_long=None):
        """
        Assign a standard build week with quality + long.
        
        ADR-037 Updated:
        - Neuromuscular work for ALL levels (rotates through types for variety)
        - Hill work is safe for everyone - scaled reps by experience
        - Variety prevents staleness (don't repeat same type week after week)
        """
        # Long run: Use progressive calculation (or fallback to 28% if not provided)
        long_miles = progressive_long if progressive_long is not None else target * 0.28
        
        # Quality: ~15% of weekly
        quality_miles = target * 0.15
        
        # Secondary quality if add_mp
        secondary_miles = target * 0.12 if add_mp else 0
        
        # Easy runs fill the rest
        remaining = target - long_miles - quality_miles - secondary_miles
        easy_days = [d for d in range(7) if d not in [rest_day, long_day, quality_day]]
        if add_mp:
            secondary_day = (quality_day + 2) % 7
            if secondary_day == rest_day:
                secondary_day = (secondary_day + 1) % 7
            easy_days = [d for d in easy_days if d != secondary_day]
        
        # ADR-037 Updated: Neuromuscular work for ALL levels with variety
        # Select 1-2 neuromuscular days based on available easy days
        neuro_days = []
        neuro_types = []
        
        if len(easy_days) >= 2:
            # First neuro day: day after quality (activation for recovery)
            day_after_quality = (quality_day + 1) % 7
            if day_after_quality in easy_days:
                neuro_days.append(day_after_quality)
            elif easy_days:
                neuro_days.append(easy_days[0])
            
            # Second neuro day: 2 days before long run (prime the legs)
            day_before_long = (long_day - 2) % 7
            if day_before_long in easy_days and day_before_long not in neuro_days:
                neuro_days.append(day_before_long)
            elif len(easy_days) > 1:
                for d in easy_days:
                    if d not in neuro_days:
                        neuro_days.append(d)
                        break
        
        # Select neuromuscular types with variety (rotate through options)
        for _ in neuro_days:
            neuro_type = self._select_neuromuscular_type()
            neuro_types.append(neuro_type)
        
        # Vary easy day distances - shortest before long run
        easy_miles_list = self._distribute_easy_miles(remaining, easy_days, quality_day, long_day)
        
        assignments[long_day] = ("long", long_miles)
        assignments[quality_day] = (quality_type, quality_miles)
        
        if add_mp:
            assignments[secondary_day] = ("mp_medium", secondary_miles)
        
        # Assign easy days with neuromuscular variety
        for i, d in enumerate(easy_days):
            miles = easy_miles_list[i]
            
            # Check if this is a neuromuscular day
            if d in neuro_days:
                neuro_idx = neuro_days.index(d)
                neuro_type = neuro_types[neuro_idx] if neuro_idx < len(neuro_types) else "strides"
                assignments[d] = (neuro_type, miles)
            else:
                assignments[d] = ("easy", miles)
    
    def _assign_mp_week(self, assignments, target, long_day, quality_day, rest_day,
                        progressive_long=None):
        """
        Assign MP-emphasis week: MP long run + threshold.
        
        Uses threshold work (NOT tempo - tempo is an ambiguous term).
        """
        # MP long run: Use progressive calculation
        long_miles = progressive_long if progressive_long is not None else target * 0.30
        
        # Threshold: ~10%
        threshold_miles = target * 0.10
        
        # Easy fills rest
        remaining = target - long_miles - threshold_miles
        easy_days = [d for d in range(7) if d not in [rest_day, long_day, quality_day]]
        
        # Neuromuscular work with variety
        neuro_days = easy_days[:2] if len(easy_days) >= 2 else easy_days[:1]
        neuro_types = [self._select_neuromuscular_type() for _ in neuro_days]
        
        easy_miles_list = self._distribute_easy_miles(remaining, easy_days, quality_day, long_day)
        
        assignments[long_day] = ("long_mp", long_miles)
        assignments[quality_day] = ("threshold", threshold_miles)
        
        for i, d in enumerate(easy_days):
            miles = easy_miles_list[i]
            if d in neuro_days:
                neuro_idx = neuro_days.index(d)
                neuro_type = neuro_types[neuro_idx] if neuro_idx < len(neuro_types) else "strides"
                assignments[d] = (neuro_type, miles)
            else:
                assignments[d] = ("easy", miles)
    
    def _assign_peak_week(self, assignments, target, long_day, quality_day, rest_day,
                         progressive_long=None):
        """Assign peak week: maximum quality."""
        # Peak long run: Use progressive calculation (peak should be longest)
        long_miles = progressive_long if progressive_long is not None else target * 0.32
        
        # Full threshold: ~15%
        threshold_miles = target * 0.15
        
        # Easy + strides on one day
        strides_day = (quality_day - 2) % 7
        if strides_day == rest_day:
            strides_day = (strides_day + 1) % 7
        
        remaining = target - long_miles - threshold_miles
        strides_miles = remaining * 0.22  # ~22% of remaining for strides day
        easy_remaining = remaining - strides_miles
        easy_days = [d for d in range(7) if d not in [rest_day, long_day, quality_day, strides_day]]
        easy_miles_list = self._distribute_easy_miles(easy_remaining, easy_days, quality_day, long_day)
        
        assignments[long_day] = ("long_mp", long_miles)
        assignments[quality_day] = ("threshold", threshold_miles)
        assignments[strides_day] = ("easy_strides", strides_miles)
        
        for i, d in enumerate(easy_days):
            assignments[d] = ("easy", easy_miles_list[i])
    
    def _assign_sharpen_week(self, assignments, target, long_day, quality_day, rest_day,
                            progressive_long=None):
        """Assign sharpening week: race-specific work."""
        # Sharpen long run: Use progressive calculation (typically reduced from peak)
        long_miles = progressive_long if progressive_long is not None else target * 0.22
        
        # Sharp intervals: ~10%
        interval_miles = target * 0.10
        
        # Strides day
        strides_day = (quality_day - 2) % 7
        if strides_day == rest_day:
            strides_day = (strides_day + 1) % 7
        
        remaining = target - long_miles - interval_miles
        strides_miles = remaining * 0.25  # ~25% of remaining for strides day
        easy_remaining = remaining - strides_miles
        easy_days = [d for d in range(7) if d not in [rest_day, long_day, quality_day, strides_day]]
        easy_miles_list = self._distribute_easy_miles(easy_remaining, easy_days, quality_day, long_day)
        
        assignments[long_day] = ("long", long_miles)
        assignments[quality_day] = ("intervals", interval_miles)
        assignments[strides_day] = ("easy_strides", strides_miles)
        
        for i, d in enumerate(easy_days):
            assignments[d] = ("easy", easy_miles_list[i])
    
    def _assign_taper_week(self, assignments, target, long_day, quality_day, rest_day, theme,
                          progressive_long=None):
        """Assign taper week: reduced with maintained intensity."""
        # Reduced long run: Use progressive calculation (already accounts for taper reduction)
        if progressive_long is not None:
            long_miles = progressive_long
        else:
            long_pct = 0.20 if theme == WeekTheme.TAPER_1 else 0.18
            long_miles = target * long_pct
        
        # Short quality maintenance
        quality_miles = target * 0.08
        
        # More rest in taper_2
        rest_days = [rest_day]
        if theme == WeekTheme.TAPER_2:
            rest_days.append((rest_day + 3) % 7)
        
        # Strides day
        strides_day = (long_day - 2) % 7
        if strides_day in rest_days:
            strides_day = (strides_day + 1) % 7
        
        remaining = target - long_miles - quality_miles
        strides_miles = remaining * 0.22
        easy_remaining = remaining - strides_miles
        easy_days = [d for d in range(7) if d not in rest_days + [long_day, quality_day, strides_day]]
        easy_miles_list = self._distribute_easy_miles(easy_remaining, easy_days, quality_day, long_day)
        
        assignments[long_day] = ("long", long_miles)
        assignments[quality_day] = ("threshold_short", quality_miles)
        assignments[strides_day] = ("easy_strides", strides_miles)
        
        for i, d in enumerate(easy_days):
            assignments[d] = ("easy", easy_miles_list[i])
    
    def _assign_tune_up_week(self, assignments, target, long_day, quality_day, rest_day):
        """Assign tune-up race week."""
        # Race on Saturday typically
        race_day = 5
        
        # Short runs around race
        pre_race_strides = race_day - 1
        post_race_recovery = long_day if long_day == 6 else (race_day + 1) % 7
        
        race_miles = 10  # Tune-up race
        pre_race_miles = 6
        post_race_miles = 4
        
        remaining = target - race_miles - pre_race_miles - post_race_miles
        easy_days = [d for d in range(7) if d not in [rest_day, race_day, pre_race_strides, post_race_recovery]]
        easy_miles_list = self._distribute_easy_miles(remaining, easy_days, quality_day)
        
        assignments[race_day] = ("race", race_miles)
        assignments[pre_race_strides] = ("easy_strides", pre_race_miles)
        assignments[post_race_recovery] = ("recovery", post_race_miles)
        
        for i, d in enumerate(easy_days):
            assignments[d] = ("easy", easy_miles_list[i])
    
    def _assign_race_week(self, assignments, target, long_day, rest_day):
        """Assign goal race week."""
        # Race on Sunday typically
        race_day = 6
        
        # Shakeout day before
        shakeout_day = 5
        
        # Strides mid-week
        strides_day = 2 if rest_day != 2 else 3
        
        # Distance-specific race miles
        race_miles_by_distance = {
            "5k": 3.1,
            "10k": 6.2,
            "10_mile": 10.0,
            "half": 13.1,
            "half_marathon": 13.1,
            "marathon": 26.2
        }
        race_miles = race_miles_by_distance.get(self.race_distance, 26.2)
        shakeout_miles = 3
        strides_miles = 5
        
        remaining = target - race_miles - shakeout_miles - strides_miles
        easy_days = [d for d in range(7) if d not in [rest_day, race_day, shakeout_day, strides_day]]
        easy_miles_list = self._distribute_easy_miles(remaining, easy_days, strides_day)
        
        assignments[race_day] = ("race", race_miles)
        assignments[shakeout_day] = ("shakeout", shakeout_miles)
        assignments[strides_day] = ("easy_strides", strides_miles)
        
        for i, d in enumerate(easy_days):
            assignments[d] = ("easy", easy_miles_list[i])
    
    def _distribute_easy_miles(self, total_miles: float, easy_days: List[int], 
                               quality_day: int, long_day: int = 6) -> List[float]:
        """
        Distribute easy miles with intentional variety.
        
        Pattern:
        - Day BEFORE long run: SHORTEST (recovery/pre-long)
        - Day AFTER quality: Short recovery
        - Other days: Varied medium to medium-long
        """
        if not easy_days:
            return []
        
        if len(easy_days) == 1:
            return [total_miles]
        
        avg = total_miles / len(easy_days)
        
        result = []
        for i, day in enumerate(easy_days):
            day_before_long = (day + 1) % 7 == long_day
            day_after_quality = (day - 1) % 7 == quality_day
            
            if day_before_long:
                # Day before long: SHORTEST - fresh legs for long run
                factor = 0.65
            elif day_after_quality:
                # Recovery after hard work: also short
                factor = 0.75
            elif i == 0:
                # Early in week: medium
                factor = 1.0
            else:
                # Other days: medium to medium-long
                factor = 1.10 + (i * 0.05)  # Progressive
            
            result.append(avg * factor)
        
        # Normalize to hit exact total
        current_total = sum(result)
        if current_total > 0:
            scale = total_miles / current_total
            result = [m * scale for m in result]
        
        return result
    
    def _generate_day_workout(self, day_idx: int, workout_type: str, target_miles: float,
                              theme: WeekTheme, week_number: int, total_weeks: int) -> DayPlan:
        """Generate specific workout for a day."""
        
        if workout_type == "easy":
            return self._generate_easy_run(day_idx, target_miles)
        
        elif workout_type == "easy_strides":
            return self._generate_easy_with_strides(day_idx, target_miles)
        
        elif workout_type == "easy_long":
            return self._generate_easy_long(day_idx, target_miles)
        
        elif workout_type == "long":
            return self._generate_long_run(day_idx, target_miles, with_mp=False)
        
        elif workout_type == "long_mp":
            return self._generate_long_run(day_idx, target_miles, with_mp=True,
                                          week_number=week_number, total_weeks=total_weeks)
        
        elif workout_type == "threshold":
            return self._generate_threshold(day_idx, target_miles)
        
        elif workout_type == "threshold_short":
            return self._generate_threshold(day_idx, target_miles, short=True)
        
        elif workout_type == "hill_sprints":
            return self._generate_hill_sprints(day_idx, target_miles)
        
        elif workout_type == "strides":
            return self._generate_easy_with_strides(day_idx, target_miles)
        
        elif workout_type == "hill_strides":
            return self._generate_hill_strides(day_idx, target_miles)
        
        elif workout_type == "intervals":
            return self._generate_intervals(day_idx, target_miles)
        
        elif workout_type == "mp_medium":
            return self._generate_mp_medium(day_idx, target_miles)
        
        elif workout_type == "recovery":
            return self._generate_recovery(day_idx, target_miles)
        
        elif workout_type == "shakeout":
            return self._generate_shakeout(day_idx, target_miles)
        
        elif workout_type == "race":
            return self._generate_race_day(day_idx, target_miles)
        
        else:
            return self._generate_easy_run(day_idx, target_miles)
    
    def _generate_easy_run(self, day_idx: int, miles: float) -> DayPlan:
        easy_pace = format_pace_range(self.paces["easy"])
        return DayPlan(
            day_of_week=day_idx,
            workout_type="easy",
            name=f"{miles:.0f}mi easy",
            description=f"{miles:.0f}mi easy @ {easy_pace}",
            target_miles=miles,
            intensity="easy",
            paces={"easy": self.pace_strs["easy"]},
            notes=[],
            tss_estimate=miles * 8
        )
    
    def _generate_easy_with_strides(self, day_idx: int, miles: float) -> DayPlan:
        easy_pace = format_pace_range(self.paces["easy"])
        return DayPlan(
            day_of_week=day_idx,
            workout_type="easy_strides",
            name=f"{miles:.0f}mi + strides",
            description=f"{miles:.0f}mi easy @ {easy_pace} + 6x100m strides",
            target_miles=miles,
            intensity="easy",
            paces={"easy": self.pace_strs["easy"]},
            notes=["Strides: controlled acceleration, not sprinting"],
            tss_estimate=miles * 9
        )
    
    def _generate_easy_long(self, day_idx: int, miles: float) -> DayPlan:
        long_pace = format_pace_range(self.paces["long"], 15)
        return DayPlan(
            day_of_week=day_idx,
            workout_type="long",
            name=f"{miles:.0f}mi long (easy)",
            description=f"{miles:.0f}mi @ {long_pace} - easy effort",
            target_miles=miles,
            intensity="easy",
            paces={"long": self.pace_strs["long"]},
            notes=[],
            tss_estimate=miles * 8
        )
    
    def _generate_long_run(self, day_idx: int, miles: float, with_mp: bool = False,
                          week_number: int = 1, total_weeks: int = 12) -> DayPlan:
        
        # Apply distance-specific cap
        capped_miles = min(miles, self.long_run_cap)
        if capped_miles < miles:
            logger.debug(f"Long run capped: {miles:.1f} -> {capped_miles:.1f} for {self.race_distance}")
        
        # Check if MP is appropriate for this distance
        if with_mp and not self.use_mp_long_runs:
            with_mp = False
            logger.debug(f"MP long runs disabled for {self.race_distance}")
        
        if not with_mp:
            long_pace = format_pace_range(self.paces["long"], 15)
            return DayPlan(
                day_of_week=day_idx,
                workout_type="long",
                name=f"{capped_miles:.0f}mi long",
                description=f"{capped_miles:.0f}mi @ {long_pace}",
                target_miles=capped_miles,
                intensity="moderate",
                paces={"long": self.pace_strs["long"]},
                notes=[],
                tss_estimate=capped_miles * 9
            )
        
        # MP long run - scale based on week and proven capability
        progress = week_number / total_weeks
        
        # Scale MP portion based on experience and proven capability
        proven_mp = self.bank.peak_mp_long_run_miles
        
        # For half marathon, use less MP work than full marathon
        if self.race_distance in ["half", "half_marathon"]:
            # Half marathon: lighter MP work, only in late build
            if progress < 0.6:
                # Early half training - just long runs without MP
                long_pace = format_pace_range(self.paces["long"], 15)
                return DayPlan(
                    day_of_week=day_idx,
                    workout_type="long",
                    name=f"{capped_miles:.0f}mi long",
                    description=f"{capped_miles:.0f}mi @ {long_pace}",
                    target_miles=capped_miles,
                    intensity="moderate",
                    paces={"long": self.pace_strs["long"]},
                    notes=[],
                    tss_estimate=capped_miles * 9
                )
            else:
                # Late half training: 20-30% @ HMP
                mp_ratio = 0.20 + (0.10 * ((progress - 0.6) / 0.4))  # 20% → 30%
        elif self.experience == ExperienceLevel.ELITE and proven_mp >= 16:
            # Can handle 70% @ MP in peak
            mp_ratio = 0.40 + (0.30 * progress)  # 40% → 70%
        elif self.experience == ExperienceLevel.EXPERIENCED and proven_mp >= 12:
            mp_ratio = 0.35 + (0.25 * progress)  # 35% → 60%
        else:
            mp_ratio = 0.25 + (0.20 * progress)  # 25% → 45%
        
        mp_miles = min(round(capped_miles * mp_ratio, 0), proven_mp if proven_mp > 0 else capped_miles * 0.5)
        easy_miles = capped_miles - mp_miles
        
        # Use appropriate pace label for distance
        if self.race_distance in ["half", "half_marathon"]:
            pace_label = "HMP"
            # Half marathon pace is faster than marathon pace
            hmp_pace = self.paces["marathon"] - 0.12
            mp_pace = format_pace(hmp_pace)
        else:
            pace_label = "MP"
            mp_pace = self.pace_strs["marathon"]
        easy_pace = self.pace_strs["long"]
        
        # Determine structure
        if progress > 0.8:
            # Peak - race simulation
            desc = f"{capped_miles:.0f}mi with {mp_miles:.0f}mi @ {pace_label} ({mp_pace}) - race simulation"
            name = f"{capped_miles:.0f}mi w/ {mp_miles:.0f}@{pace_label}"
        elif progress > 0.5:
            # Mid build - tempo finish
            desc = f"{capped_miles:.0f}mi: {easy_miles:.0f}E + {mp_miles:.0f}mi @ {pace_label} ({mp_pace})"
            name = f"{capped_miles:.0f}mi w/ {mp_miles:.0f}@{pace_label}"
        else:
            # Early - pace finish
            desc = f"{capped_miles:.0f}mi with last {mp_miles:.0f}mi @ {pace_label} ({mp_pace})"
            name = f"{capped_miles:.0f}mi, last {mp_miles:.0f}@{pace_label}"
        
        notes = []
        if mp_miles >= 16 and self.race_distance == "marathon":
            notes.append(f"You've done {proven_mp:.0f}@MP before — this is your territory")
        
        return DayPlan(
            day_of_week=day_idx,
            workout_type="long_mp",
            name=name,
            description=desc,
            target_miles=capped_miles,
            intensity="hard",
            paces={"race_pace": mp_pace, "easy": easy_pace},
            notes=notes,
            tss_estimate=easy_miles * 8 + mp_miles * 12
        )
    
    def _generate_threshold(self, day_idx: int, miles: float, short: bool = False) -> DayPlan:
        structures = THRESHOLD_STRUCTURES.get(self.experience, THRESHOLD_STRUCTURES[ExperienceLevel.INTERMEDIATE])
        
        if short:
            # Pick shortest structure
            structure = min(structures, key=lambda s: s.total_miles)
        else:
            # Pick one that fits target miles
            suitable = [s for s in structures if abs(s.total_miles - miles) < 3]
            structure = random.choice(suitable) if suitable else structures[0]
        
        # Fill in paces
        warm = 2
        cool = 2
        desc = structure.description.format(
            warm=warm,
            cool=cool,
            t_pace=self.pace_strs["threshold"]
        )
        
        return DayPlan(
            day_of_week=day_idx,
            workout_type="threshold",
            name=structure.name,
            description=desc,
            target_miles=structure.total_miles,
            intensity=structure.intensity,
            paces={"threshold": self.pace_strs["threshold"], "easy": self.pace_strs["easy"]},
            notes=[],
            tss_estimate=structure.total_miles * 10 * structure.tss_multiplier
        )
    
    def _generate_hill_sprints(self, day_idx: int, miles: float) -> DayPlan:
        """
        Generate hill sprint workout (ADR-037).
        
        Hill sprints are neuromuscular power work:
        - 8-10x 10-12 sec MAX effort up steep hill
        - Full recovery between reps
        - Done after easy running, not a standalone quality session
        """
        easy_pace = format_pace_range(self.paces["easy"])
        
        # Scale reps by experience
        reps = {
            ExperienceLevel.ELITE: 10,
            ExperienceLevel.EXPERIENCED: 8,
            ExperienceLevel.INTERMEDIATE: 6,
            ExperienceLevel.BEGINNER: 4
        }.get(self.experience, 6)
        
        return DayPlan(
            day_of_week=day_idx,
            workout_type="hill_sprints",
            name=f"{miles:.0f}mi + {reps}x hill sprints",
            description=f"{miles:.0f}mi easy @ {easy_pace} + {reps}x10sec hill sprints (MAX effort, full recovery)",
            target_miles=miles,
            intensity="moderate",
            paces={"easy": self.pace_strs["easy"]},
            notes=["Find steep hill. Sprint MAX effort 10sec. Walk down. Full recovery between reps."],
            tss_estimate=miles * 10
        )
    
    def _generate_hill_strides(self, day_idx: int, miles: float) -> DayPlan:
        """
        Generate hill strides (hybrid power + form work).
        
        Hill strides are:
        - 6-8x ~100m strides on gentle uphill (3-5% grade)
        - Controlled, smooth effort (not max sprint like hill sprints)
        - Focus on form: high knees, forward lean, arm drive
        - Develops power without maximal stress
        """
        easy_pace = format_pace_range(self.paces["easy"])
        
        # Scale reps by experience (everyone can do these)
        reps = {
            ExperienceLevel.ELITE: 8,
            ExperienceLevel.EXPERIENCED: 7,
            ExperienceLevel.INTERMEDIATE: 6,
            ExperienceLevel.BEGINNER: 5
        }.get(self.experience, 6)
        
        return DayPlan(
            day_of_week=day_idx,
            workout_type="hill_strides",
            name=f"{miles:.0f}mi + {reps}x hill strides",
            description=f"{miles:.0f}mi easy @ {easy_pace} + {reps}x100m hill strides (smooth, controlled)",
            target_miles=miles,
            intensity="easy",
            paces={"easy": self.pace_strs["easy"]},
            notes=["Find gentle uphill (3-5%). Smooth 100m strides with good form. Walk recovery."],
            tss_estimate=miles * 10
        )
    
    def _generate_intervals(self, day_idx: int, miles: float) -> DayPlan:
        structures = INTERVAL_STRUCTURES.get(self.experience, INTERVAL_STRUCTURES[ExperienceLevel.INTERMEDIATE])
        
        suitable = [s for s in structures if abs(s.total_miles - miles) < 3]
        structure = random.choice(suitable) if suitable else structures[0]
        
        warm = 2
        cool = 2
        desc = structure.description.format(
            warm=warm,
            cool=cool,
            i_pace=self.pace_strs["interval"]
        )
        
        return DayPlan(
            day_of_week=day_idx,
            workout_type="intervals",
            name=structure.name,
            description=desc,
            target_miles=structure.total_miles,
            intensity=structure.intensity,
            paces={"interval": self.pace_strs["interval"], "easy": self.pace_strs["easy"]},
            notes=[],
            tss_estimate=structure.total_miles * 11 * structure.tss_multiplier
        )
    
    def _generate_mp_medium(self, day_idx: int, miles: float) -> DayPlan:
        mp_miles = round(miles * 0.5, 0)
        easy_miles = miles - mp_miles
        
        return DayPlan(
            day_of_week=day_idx,
            workout_type="mp_medium",
            name=f"{miles:.0f}mi w/ {mp_miles:.0f}@MP",
            description=f"{miles:.0f}mi: {easy_miles:.0f}E + {mp_miles:.0f}mi @ MP ({self.pace_strs['marathon']})",
            target_miles=miles,
            intensity="hard",
            paces={"marathon": self.pace_strs["marathon"], "easy": self.pace_strs["easy"]},
            notes=[],
            tss_estimate=easy_miles * 8 + mp_miles * 12
        )
    
    def _generate_recovery(self, day_idx: int, miles: float) -> DayPlan:
        return DayPlan(
            day_of_week=day_idx,
            workout_type="recovery",
            name="Recovery",
            description=f"{miles:.0f}mi very easy @ {self.pace_strs['recovery']}+",
            target_miles=miles,
            intensity="easy",
            paces={"recovery": self.pace_strs["recovery"]},
            notes=["Slower is fine"],
            tss_estimate=miles * 6
        )
    
    def _generate_shakeout(self, day_idx: int, miles: float) -> DayPlan:
        return DayPlan(
            day_of_week=day_idx,
            workout_type="shakeout",
            name="Shakeout",
            description=f"{miles:.0f}mi easy + 4x100m strides",
            target_miles=miles,
            intensity="easy",
            paces={"easy": self.pace_strs["easy"]},
            notes=["Stay loose, save your legs"],
            tss_estimate=miles * 7
        )
    
    def _generate_race_day(self, day_idx: int, miles: float) -> DayPlan:
        return DayPlan(
            day_of_week=day_idx,
            workout_type="race",
            name="RACE DAY",
            description=f"{miles:.1f}mi @ race effort",
            target_miles=miles,
            intensity="race",
            paces={"race": self.pace_strs["marathon"]},
            notes=["Trust your training"],
            tss_estimate=miles * 15
        )
    
    def _get_week_notes(self, theme: WeekTheme, week_number: int, total_weeks: int) -> List[str]:
        """Generate sparse, relevant notes for the week."""
        notes = []
        
        if theme == WeekTheme.REBUILD_EASY:
            notes.append("Patience. Easy only.")
        elif theme == WeekTheme.REBUILD_STRIDES:
            notes.append("Building back. Strides keep legs sharp.")
        elif theme == WeekTheme.RECOVERY:
            notes.append("Absorb the work. Easy does it.")
        elif theme == WeekTheme.PEAK:
            notes.append("Peak week. Embrace the work.")
        elif theme == WeekTheme.TAPER_1:
            notes.append("Taper starts. Less volume, same intensity.")
        elif theme == WeekTheme.TAPER_2:
            notes.append("Final sharpening. Stay loose.")
        elif theme == WeekTheme.RACE:
            notes.append("Race week. You've done the work.")
        
        return notes
