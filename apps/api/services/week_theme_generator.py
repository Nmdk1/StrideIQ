"""
Week Theme Generator (ADR-031)

Generates week-by-week training emphasis based on Fitness Bank data.

Key Principles:
- Alternate quality focus (T → MP → T)
- Insert recovery every 3-4 weeks based on τ1
- Respect injury constraints with rebuild phases
- Handle dual race scenarios
"""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from typing import List, Dict, Optional
import logging

from services.fitness_bank import FitnessBank, ConstraintType, ExperienceLevel

logger = logging.getLogger(__name__)


class WeekTheme(Enum):
    """Training emphasis for a week."""
    
    # Rebuild phases (injury/break return)
    REBUILD_EASY = "rebuild_easy"           # Easy only, no intensity
    REBUILD_STRIDES = "rebuild_strides"     # Add strides, still easy base
    
    # Build phases
    BUILD_T_EMPHASIS = "build_t"            # Threshold as primary quality
    BUILD_MP_EMPHASIS = "build_mp"          # Marathon pace as primary quality
    BUILD_MIXED = "build_mixed"             # Both quality types
    
    # Special weeks
    RECOVERY = "recovery"                   # 40% volume reduction
    PEAK = "peak"                           # Maximum quality + volume
    SHARPEN = "sharpen"                     # Race-specific sharpening
    
    # Taper phases
    TAPER_1 = "taper_1"                     # 30% reduction, maintain intensity
    TAPER_2 = "taper_2"                     # 50% reduction, sharpening only
    
    # Race weeks
    TUNE_UP_RACE = "tune_up"                # Secondary race week
    RACE = "race"                           # Goal race week


@dataclass
class WeekThemePlan:
    """A single week's theme assignment."""
    week_number: int
    theme: WeekTheme
    start_date: date
    target_volume_pct: float              # % of peak weekly
    notes: List[str]
    
    def to_dict(self) -> Dict:
        return {
            "week": self.week_number,
            "theme": self.theme.value,
            "start_date": self.start_date.isoformat(),
            "volume_pct": self.target_volume_pct,
            "notes": self.notes
        }


@dataclass
class ThemeConstraints:
    """Constraints affecting theme generation."""
    is_injury_return: bool
    injury_weeks: int                      # Weeks since injury started
    weeks_to_race: int
    tune_up_races: List[Dict]              # [{date, distance, purpose}]
    tau1: float
    experience: ExperienceLevel
    current_volume_pct: float              # Current as % of peak
    
    @property
    def needs_rebuild(self) -> bool:
        """True if athlete needs rebuild phase."""
        return self.is_injury_return and self.current_volume_pct < 0.5
    
    @property
    def recovery_frequency(self) -> int:
        """How often to insert recovery week."""
        # Fast adapters (τ1 < 30): every 4 weeks
        # Slow adapters (τ1 > 45): every 3 weeks
        if self.tau1 < 30:
            return 4
        elif self.tau1 > 45:
            return 3
        else:
            return 3  # Default to conservative


class WeekThemeGenerator:
    """
    Generate week themes from Fitness Bank data.
    
    Respects:
    - Individual τ1 (affects recovery frequency)
    - Injury status (triggers rebuild phases)
    - Dual races (coordinates tapers)
    - Experience level (affects theme intensity)
    """
    
    # Volume targets by theme (as % of peak)
    THEME_VOLUME = {
        WeekTheme.REBUILD_EASY: 0.40,
        WeekTheme.REBUILD_STRIDES: 0.55,
        WeekTheme.BUILD_T_EMPHASIS: 0.80,
        WeekTheme.BUILD_MP_EMPHASIS: 0.85,
        WeekTheme.BUILD_MIXED: 0.85,
        WeekTheme.RECOVERY: 0.55,
        WeekTheme.PEAK: 1.00,
        WeekTheme.SHARPEN: 0.75,
        WeekTheme.TAPER_1: 0.65,
        WeekTheme.TAPER_2: 0.45,
        WeekTheme.TUNE_UP_RACE: 0.45,
        WeekTheme.RACE: 0.60
    }
    
    def __init__(self):
        pass
    
    def generate(self, 
                bank: FitnessBank,
                race_date: date,
                race_distance: str,
                tune_up_races: Optional[List[Dict]] = None) -> List[WeekThemePlan]:
        """
        Generate week themes from now to race day.
        """
        today = date.today()
        
        # Calculate weeks INCLUDING the race week
        # Race week is the week containing the race date
        race_week_start = race_date - timedelta(days=race_date.weekday())
        current_week_start = today - timedelta(days=today.weekday())
        weeks_to_race = ((race_week_start - current_week_start).days // 7) + 1
        
        if weeks_to_race < 1:
            return []
        
        # Build constraints
        constraints = ThemeConstraints(
            is_injury_return=bank.constraint_type == ConstraintType.INJURY,
            injury_weeks=bank.weeks_since_peak,
            weeks_to_race=weeks_to_race,
            tune_up_races=tune_up_races or [],
            tau1=bank.tau1,
            experience=bank.experience_level,
            current_volume_pct=bank.current_weekly_miles / bank.peak_weekly_miles 
                               if bank.peak_weekly_miles > 0 else 0.5
        )
        
        # Generate base theme sequence
        themes = self._generate_base_sequence(weeks_to_race, race_distance, constraints)
        
        # Insert tune-up races
        if tune_up_races:
            themes = self._insert_tune_up_races(themes, race_date, tune_up_races)
        
        # Convert to WeekThemePlan objects with dates
        week_start = today - timedelta(days=today.weekday())  # Monday of current week
        
        result = []
        for i, (theme, notes) in enumerate(themes):
            volume_pct = self.THEME_VOLUME.get(theme, 0.75)
            
            # Adjust volume for injury rebuild
            if constraints.needs_rebuild and i < 3:
                # Progressive rebuild: 40% → 55% → 70%
                volume_pct = min(volume_pct, 0.40 + (i * 0.15))
            
            result.append(WeekThemePlan(
                week_number=i + 1,
                theme=theme,
                start_date=week_start + timedelta(weeks=i),
                target_volume_pct=volume_pct,
                notes=notes
            ))
        
        return result
    
    def _generate_base_sequence(self, 
                               weeks: int,
                               distance: str,
                               constraints: ThemeConstraints) -> List[tuple]:
        """Generate base theme sequence."""
        
        sequence = []
        
        # Determine taper length based on experience and τ1
        taper_weeks = self._calculate_taper_length(distance, constraints)
        
        # Build weeks = total - taper - race week
        build_weeks = weeks - taper_weeks - 1
        
        if build_weeks < 1:
            # Very short prep - just taper
            return self._generate_short_prep(weeks, constraints)
        
        # Generate build phase
        build_themes = self._generate_build_phase(build_weeks, constraints)
        sequence.extend(build_themes)
        
        # Generate taper phase
        taper_themes = self._generate_taper_phase(taper_weeks, distance, constraints)
        sequence.extend(taper_themes)
        
        # Add race week
        sequence.append((WeekTheme.RACE, [f"Goal race: {distance}"]))
        
        return sequence
    
    def _calculate_taper_length(self, distance: str, constraints: ThemeConstraints) -> int:
        """Calculate taper length based on distance and τ1."""
        base_taper = {
            "5k": 1,
            "10k": 1,
            "10_mile": 1,
            "half": 2,
            "half_marathon": 2,
            "marathon": 2
        }.get(distance, 2)
        
        # Fast adapters can taper shorter
        if constraints.tau1 < 30:
            return max(1, base_taper)
        elif constraints.tau1 > 45:
            return base_taper + 1
        
        return base_taper
    
    def _generate_build_phase(self, weeks: int, constraints: ThemeConstraints) -> List[tuple]:
        """Generate build phase with alternating themes."""
        themes = []
        
        # Injury rebuild first
        rebuild_weeks = 0
        if constraints.needs_rebuild:
            # 2-3 weeks rebuild based on how reduced they are
            if constraints.current_volume_pct < 0.3:
                rebuild_weeks = 3
            else:
                rebuild_weeks = 2
            
            themes.append((WeekTheme.REBUILD_EASY, ["Gentle return - easy only"]))
            if rebuild_weeks >= 2:
                themes.append((WeekTheme.REBUILD_STRIDES, ["Add strides, maintain easy base"]))
            if rebuild_weeks >= 3:
                themes.append((WeekTheme.REBUILD_STRIDES, ["Building back carefully"]))
        
        remaining = weeks - rebuild_weeks
        if remaining <= 0:
            return themes
        
        # Alternate T and MP emphasis
        recovery_freq = constraints.recovery_frequency
        quality_count = 0  # Track quality weeks since last recovery
        use_t_next = True  # Alternate flag
        
        for i in range(remaining):
            quality_count += 1
            
            # Check if recovery needed
            if quality_count >= recovery_freq:
                themes.append((WeekTheme.RECOVERY, ["Absorb adaptation"]))
                quality_count = 0
                continue
            
            # Check if peak week (last build week before taper)
            if i == remaining - 1:
                themes.append((WeekTheme.PEAK, ["Maximum quality + volume"]))
                continue
            
            # Alternate T and MP
            if use_t_next:
                themes.append((WeekTheme.BUILD_T_EMPHASIS, ["Threshold focus"]))
            else:
                themes.append((WeekTheme.BUILD_MP_EMPHASIS, ["Marathon pace focus"]))
            
            use_t_next = not use_t_next
        
        return themes
    
    def _generate_taper_phase(self, weeks: int, distance: str, 
                             constraints: ThemeConstraints) -> List[tuple]:
        """Generate taper phase."""
        themes = []
        
        if weeks >= 2:
            themes.append((WeekTheme.TAPER_1, ["Reduce volume, maintain intensity"]))
            themes.append((WeekTheme.TAPER_2, ["Final sharpening"]))
        elif weeks == 1:
            themes.append((WeekTheme.TAPER_2, ["Race week prep"]))
        
        return themes
    
    def _generate_short_prep(self, weeks: int, constraints: ThemeConstraints) -> List[tuple]:
        """Generate themes for very short prep (< 4 weeks)."""
        themes = []
        
        if weeks == 1:
            themes.append((WeekTheme.RACE, ["Race week"]))
        elif weeks == 2:
            themes.append((WeekTheme.SHARPEN, ["Final sharpening"]))
            themes.append((WeekTheme.RACE, ["Race week"]))
        elif weeks == 3:
            themes.append((WeekTheme.BUILD_MIXED, ["Quality maintenance"]))
            themes.append((WeekTheme.SHARPEN, ["Final sharpening"]))
            themes.append((WeekTheme.RACE, ["Race week"]))
        
        return themes
    
    def _insert_tune_up_races(self, 
                             themes: List[tuple],
                             goal_race_date: date,
                             tune_up_races: List[Dict]) -> List[tuple]:
        """Insert tune-up race weeks into theme sequence."""
        
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        
        for tune_up in tune_up_races:
            tune_date = tune_up["date"]
            if isinstance(tune_date, str):
                tune_date = date.fromisoformat(tune_date)
            
            # Find which week this falls in
            days_to_tune = (tune_date - week_start).days
            week_idx = days_to_tune // 7
            
            if 0 <= week_idx < len(themes):
                purpose = tune_up.get("purpose", "sharpening")
                distance = tune_up.get("distance", "race")
                name = tune_up.get("name", f"{distance} tune-up")
                
                note = f"{name}"
                if purpose == "threshold":
                    note += " - race it HARD, final threshold effort"
                elif purpose == "sharpening":
                    note += " - controlled effort, save legs"
                
                themes[week_idx] = (WeekTheme.TUNE_UP_RACE, [note])
        
        return themes


def generate_week_themes(bank: FitnessBank,
                        race_date: date,
                        race_distance: str,
                        tune_up_races: Optional[List[Dict]] = None) -> List[WeekThemePlan]:
    """Convenience function to generate week themes."""
    generator = WeekThemeGenerator()
    return generator.generate(bank, race_date, race_distance, tune_up_races)
