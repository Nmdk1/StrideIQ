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
from services.week_theme_generator import WeekTheme

logger = logging.getLogger(__name__)


# =============================================================================
# PACE CALCULATION
# =============================================================================

def calculate_paces_from_vdot(vdot: float) -> Dict[str, float]:
    """
    Calculate training paces from VDOT.
    
    Returns paces in minutes per mile.
    """
    # VDOT to pace approximations (Daniels-based)
    # These are approximate formulas
    
    # Marathon pace (roughly VDOT race pace for marathon distance)
    # Higher VDOT = faster pace
    marathon_pace = 10.5 - (vdot * 0.07)  # ~6:50 at VDOT 52
    
    # Threshold pace (about 83-88% of VO2max, ~15-20 sec/mi faster than MP)
    threshold_pace = marathon_pace - 0.35
    
    # Interval pace (about 95-100% VO2max)
    interval_pace = threshold_pace - 0.45
    
    # Easy pace (about 65-75% VO2max, ~1:30-2:00/mi slower than MP)
    easy_pace = marathon_pace + 1.3
    
    # Long run pace (slightly slower than easy)
    long_pace = easy_pace + 0.15
    
    # Recovery pace (very easy)
    recovery_pace = easy_pace + 0.5
    
    return {
        "easy": round(easy_pace, 2),
        "long": round(long_pace, 2),
        "marathon": round(marathon_pace, 2),
        "threshold": round(threshold_pace, 2),
        "interval": round(interval_pace, 2),
        "recovery": round(recovery_pace, 2)
    }


def format_pace(pace_minutes: float) -> str:
    """Format pace as M:SS."""
    minutes = int(pace_minutes)
    seconds = int((pace_minutes - minutes) * 60)
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
    """
    
    def __init__(self, bank: FitnessBank):
        self.bank = bank
        self.paces = calculate_paces_from_vdot(bank.best_vdot)
        self.experience = bank.experience_level
        
        # Format paces for display
        self.pace_strs = {k: format_pace(v) for k, v in self.paces.items()}
    
    def generate_week(self,
                     theme: WeekTheme,
                     week_number: int,
                     total_weeks: int,
                     target_miles: float,
                     start_date: date) -> WeekPlan:
        """Generate a full week of workouts for given theme."""
        
        days = []
        
        # Get day assignments based on theme and patterns
        day_assignments = self._assign_days_by_theme(theme, target_miles)
        
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
    
    def _assign_days_by_theme(self, theme: WeekTheme, target_miles: float) -> Dict[int, Tuple[str, float]]:
        """Assign workout types and miles to days based on theme."""
        
        # Get preferred days from bank
        long_day = self.bank.typical_long_run_day if self.bank.typical_long_run_day is not None else 6
        quality_day = self.bank.typical_quality_day if self.bank.typical_quality_day is not None else 3
        rest_days = self.bank.typical_rest_days if self.bank.typical_rest_days else [0]
        
        assignments = {}
        
        # Rest day(s)
        primary_rest = rest_days[0] if rest_days else 0
        
        if theme == WeekTheme.REBUILD_EASY:
            # All easy, one rest
            available_days = [d for d in range(7) if d != primary_rest]
            miles_per_run = target_miles / len(available_days)
            for d in available_days:
                if d == long_day:
                    assignments[d] = ("easy_long", miles_per_run * 1.4)
                else:
                    assignments[d] = ("easy", miles_per_run * 0.9)
        
        elif theme == WeekTheme.REBUILD_STRIDES:
            # Easy with strides, one rest
            available_days = [d for d in range(7) if d != primary_rest]
            miles_per_run = target_miles / len(available_days)
            for d in available_days:
                if d == long_day:
                    assignments[d] = ("easy_long", miles_per_run * 1.4)
                elif d == quality_day:
                    assignments[d] = ("easy_strides", miles_per_run)
                else:
                    assignments[d] = ("easy", miles_per_run * 0.9)
        
        elif theme == WeekTheme.BUILD_T_EMPHASIS:
            # Threshold focus + long run
            self._assign_standard_week(assignments, target_miles, long_day, quality_day, 
                                      primary_rest, quality_type="threshold")
        
        elif theme == WeekTheme.BUILD_MP_EMPHASIS:
            # MP long run + secondary threshold
            self._assign_mp_week(assignments, target_miles, long_day, quality_day, primary_rest)
        
        elif theme == WeekTheme.BUILD_MIXED:
            # Both quality types
            self._assign_standard_week(assignments, target_miles, long_day, quality_day,
                                      primary_rest, quality_type="threshold", add_mp=True)
        
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
            self._assign_peak_week(assignments, target_miles, long_day, quality_day, primary_rest)
        
        elif theme == WeekTheme.SHARPEN:
            # Race-specific sharpening
            self._assign_sharpen_week(assignments, target_miles, long_day, quality_day, primary_rest)
        
        elif theme in (WeekTheme.TAPER_1, WeekTheme.TAPER_2):
            # Reduced volume, maintain some intensity
            self._assign_taper_week(assignments, target_miles, long_day, quality_day, 
                                   primary_rest, theme)
        
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
                             rest_day, quality_type, add_mp=False):
        """Assign a standard build week with quality + long."""
        # Long run: ~25-30% of weekly
        long_miles = target * 0.28
        
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
        
        easy_per_day = remaining / len(easy_days) if easy_days else 0
        
        assignments[long_day] = ("long", long_miles)
        assignments[quality_day] = (quality_type, quality_miles)
        
        if add_mp:
            assignments[secondary_day] = ("mp_medium", secondary_miles)
        
        for d in easy_days:
            assignments[d] = ("easy", easy_per_day)
    
    def _assign_mp_week(self, assignments, target, long_day, quality_day, rest_day):
        """Assign MP-emphasis week: MP long run + maintenance threshold."""
        # MP long run: ~30% of weekly
        long_miles = target * 0.30
        
        # Short threshold: ~10%
        threshold_miles = target * 0.10
        
        # Easy fills rest
        remaining = target - long_miles - threshold_miles
        easy_days = [d for d in range(7) if d not in [rest_day, long_day, quality_day]]
        easy_per_day = remaining / len(easy_days) if easy_days else 0
        
        assignments[long_day] = ("long_mp", long_miles)
        assignments[quality_day] = ("threshold", threshold_miles)
        
        for d in easy_days:
            assignments[d] = ("easy", easy_per_day)
    
    def _assign_peak_week(self, assignments, target, long_day, quality_day, rest_day):
        """Assign peak week: maximum quality."""
        # Peak MP long run: ~32%
        long_miles = target * 0.32
        
        # Full threshold: ~15%
        threshold_miles = target * 0.15
        
        # Easy + strides on one day
        strides_day = (quality_day - 2) % 7
        if strides_day == rest_day:
            strides_day = (strides_day + 1) % 7
        
        remaining = target - long_miles - threshold_miles
        easy_days = [d for d in range(7) if d not in [rest_day, long_day, quality_day, strides_day]]
        easy_per_day = remaining / (len(easy_days) + 1) if easy_days else remaining
        
        assignments[long_day] = ("long_mp", long_miles)
        assignments[quality_day] = ("threshold", threshold_miles)
        assignments[strides_day] = ("easy_strides", easy_per_day * 1.1)
        
        for d in easy_days:
            assignments[d] = ("easy", easy_per_day * 0.95)
    
    def _assign_sharpen_week(self, assignments, target, long_day, quality_day, rest_day):
        """Assign sharpening week: race-specific work."""
        # Shorter long run: ~22%
        long_miles = target * 0.22
        
        # Sharp intervals: ~10%
        interval_miles = target * 0.10
        
        # Strides day
        strides_day = (quality_day - 2) % 7
        if strides_day == rest_day:
            strides_day = (strides_day + 1) % 7
        
        remaining = target - long_miles - interval_miles
        easy_days = [d for d in range(7) if d not in [rest_day, long_day, quality_day, strides_day]]
        easy_per_day = remaining / (len(easy_days) + 1) if easy_days else remaining
        
        assignments[long_day] = ("long", long_miles)
        assignments[quality_day] = ("intervals", interval_miles)
        assignments[strides_day] = ("easy_strides", easy_per_day)
        
        for d in easy_days:
            assignments[d] = ("easy", easy_per_day)
    
    def _assign_taper_week(self, assignments, target, long_day, quality_day, rest_day, theme):
        """Assign taper week: reduced with maintained intensity."""
        # Reduced long run
        long_pct = 0.20 if theme == WeekTheme.TAPER_1 else 0.18
        long_miles = target * long_pct
        
        # Short quality maintenance
        quality_miles = target * 0.08
        
        # More rest in taper_2
        rest_days = [rest_day]
        if theme == WeekTheme.TAPER_2:
            rest_days.append((rest_day + 3) % 7)
        
        remaining = target - long_miles - quality_miles
        easy_days = [d for d in range(7) if d not in rest_days + [long_day, quality_day]]
        easy_per_day = remaining / len(easy_days) if easy_days else remaining
        
        assignments[long_day] = ("long", long_miles)
        assignments[quality_day] = ("threshold_short", quality_miles)
        
        for d in easy_days:
            # Add strides to one easy day
            if d == (long_day - 2) % 7:
                assignments[d] = ("easy_strides", easy_per_day)
            else:
                assignments[d] = ("easy", easy_per_day)
    
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
        easy_per_day = remaining / len(easy_days) if easy_days else 0
        
        assignments[race_day] = ("race", race_miles)
        assignments[pre_race_strides] = ("easy_strides", pre_race_miles)
        assignments[post_race_recovery] = ("recovery", post_race_miles)
        
        for d in easy_days:
            assignments[d] = ("easy", easy_per_day)
    
    def _assign_race_week(self, assignments, target, long_day, rest_day):
        """Assign goal race week."""
        # Race on Sunday typically
        race_day = 6
        
        # Shakeout day before
        shakeout_day = 5
        
        # Strides mid-week
        strides_day = 2 if rest_day != 2 else 3
        
        race_miles = 26.2  # Marathon
        shakeout_miles = 3
        strides_miles = 5
        
        remaining = target - race_miles - shakeout_miles - strides_miles
        easy_days = [d for d in range(7) if d not in [rest_day, race_day, shakeout_day, strides_day]]
        easy_per_day = remaining / len(easy_days) if easy_days else 0
        
        assignments[race_day] = ("race", race_miles)
        assignments[shakeout_day] = ("shakeout", shakeout_miles)
        assignments[strides_day] = ("easy_strides", strides_miles)
        
        for d in easy_days:
            assignments[d] = ("easy", easy_per_day)
    
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
        
        if not with_mp:
            long_pace = format_pace_range(self.paces["long"], 15)
            return DayPlan(
                day_of_week=day_idx,
                workout_type="long",
                name=f"{miles:.0f}mi long",
                description=f"{miles:.0f}mi @ {long_pace}",
                target_miles=miles,
                intensity="moderate",
                paces={"long": self.pace_strs["long"]},
                notes=[],
                tss_estimate=miles * 9
            )
        
        # MP long run - scale based on week and proven capability
        progress = week_number / total_weeks
        
        # Scale MP portion based on experience and proven capability
        proven_mp = self.bank.peak_mp_long_run_miles
        
        if self.experience == ExperienceLevel.ELITE and proven_mp >= 16:
            # Can handle 70% @ MP in peak
            mp_ratio = 0.40 + (0.30 * progress)  # 40% → 70%
        elif self.experience == ExperienceLevel.EXPERIENCED and proven_mp >= 12:
            mp_ratio = 0.35 + (0.25 * progress)  # 35% → 60%
        else:
            mp_ratio = 0.25 + (0.20 * progress)  # 25% → 45%
        
        mp_miles = min(round(miles * mp_ratio, 0), proven_mp if proven_mp > 0 else miles * 0.5)
        easy_miles = miles - mp_miles
        
        mp_pace = self.pace_strs["marathon"]
        easy_pace = self.pace_strs["long"]
        
        # Determine structure
        if progress > 0.8:
            # Peak - race simulation
            desc = f"{miles:.0f}mi with {mp_miles:.0f}mi @ MP ({mp_pace}) - race simulation"
            name = f"{miles:.0f}mi w/ {mp_miles:.0f}@MP"
        elif progress > 0.5:
            # Mid build - MP middle or finish
            desc = f"{miles:.0f}mi: {easy_miles:.0f}E + {mp_miles:.0f}mi @ MP ({mp_pace})"
            name = f"{miles:.0f}mi w/ {mp_miles:.0f}@MP"
        else:
            # Early - MP finish
            desc = f"{miles:.0f}mi with last {mp_miles:.0f}mi @ MP ({mp_pace})"
            name = f"{miles:.0f}mi, last {mp_miles:.0f}@MP"
        
        notes = []
        if mp_miles >= 16:
            notes.append(f"You've done {proven_mp:.0f}@MP before — this is your territory")
        
        return DayPlan(
            day_of_week=day_idx,
            workout_type="long_mp",
            name=name,
            description=desc,
            target_miles=miles,
            intensity="hard",
            paces={"marathon": mp_pace, "easy": easy_pace},
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
