"""
Phase Builder

Constructs training phases based on:
- Goal distance
- Plan duration
- Volume tier
- Knowledge base principles

Usage:
    builder = PhaseBuilder()
    phases = builder.build_phases(
        distance="marathon",
        duration_weeks=18,
        tier="mid"
    )
"""

from typing import List, Dict, Any
from dataclasses import dataclass

from .constants import Distance, VolumeTier, Phase, TAPER_WEEKS


@dataclass
class TrainingPhase:
    """A single training phase."""
    name: str
    phase_type: Phase
    weeks: List[int]  # Week numbers (1-indexed)
    focus: str
    quality_sessions: int  # Per week
    volume_modifier: float  # Relative to peak (1.0 = peak)
    long_run_modifier: float  # Relative to peak long run
    allowed_workouts: List[str]
    key_sessions: List[str]  # Primary quality sessions for this phase


class PhaseBuilder:
    """
    Build training phases based on StrideIQ methodology.
    
    Core principle: Inverted Intensity Model
    - Speed work in base (when fresh)
    - Threshold in build
    - MP specificity in race prep
    - Light VO2max sharpening via racing (not intervals mid-build)
    """
    
    def build_phases(
        self,
        distance: str,
        duration_weeks: int,
        tier: str,
        taper_days: int = None,
    ) -> List[TrainingPhase]:
        """
        Build phase structure for a plan.
        
        Args:
            distance: Goal race distance
            duration_weeks: Total plan weeks
            tier: Volume tier
            taper_days: Personalized taper duration in days (Phase 1D).
                        If provided, overrides TAPER_WEEKS for this plan.
                        Converted to weeks via _taper_days_to_weeks().
            
        Returns:
            List of TrainingPhase objects
        """
        try:
            dist = Distance(distance)
        except ValueError:
            dist = Distance.MARATHON
        
        try:
            vol_tier = VolumeTier(tier)
        except ValueError:
            vol_tier = VolumeTier.MID
        
        # Get taper duration: use personalized days when provided,
        # otherwise fall back to the legacy TAPER_WEEKS constant.
        if taper_days is not None:
            taper_weeks = self._taper_days_to_weeks(taper_days)
        else:
            taper_weeks = TAPER_WEEKS.get(dist, 2)
        
        # Build phases based on distance
        if dist == Distance.MARATHON:
            return self._build_marathon_phases(duration_weeks, taper_weeks, vol_tier)
        elif dist == Distance.HALF_MARATHON:
            return self._build_half_marathon_phases(duration_weeks, taper_weeks, vol_tier)
        elif dist == Distance.TEN_K:
            return self._build_10k_phases(duration_weeks, taper_weeks, vol_tier)
        else:  # 5K
            return self._build_5k_phases(duration_weeks, taper_weeks, vol_tier)
    
    @staticmethod
    def _taper_days_to_weeks(taper_days: int) -> int:
        """
        Convert taper days to the week-based structure the phase builder uses.

        ADR-062 mapping:
          4-7 days  → 1 week  (race week absorbs taper)
          8-10 days → 1 week  (1 taper week + race week handled separately)
          11-14 days → 2 weeks
          15-21 days → 3 weeks
        """
        if taper_days <= 7:
            return 1
        elif taper_days <= 14:
            return 2
        else:
            return 3
    
    def _build_marathon_phases(
        self,
        duration_weeks: int,
        taper_weeks: int,
        tier: VolumeTier
    ) -> List[TrainingPhase]:
        """
        Build marathon-specific phases.
        
        StrideIQ Marathon Framework:
        1. Base + Speed (aerobic + strides/hills)
        2. Threshold Block (T-work progression)
        3. MP Introduction (add marathon pace)
        4. Race Specific (MP integration, race simulation)
        5. Taper
        """
        phases = []
        build_weeks = duration_weeks - taper_weeks
        race_week = duration_weeks
        
        # Phase allocation
        if build_weeks >= 16:
            base_weeks = 4
            threshold_weeks = 4
            mp_intro_weeks = 4
            race_specific_weeks = build_weeks - base_weeks - threshold_weeks - mp_intro_weeks
        elif build_weeks >= 12:
            base_weeks = 3
            threshold_weeks = 3
            mp_intro_weeks = 3
            race_specific_weeks = build_weeks - base_weeks - threshold_weeks - mp_intro_weeks
        elif build_weeks >= 8:
            base_weeks = 2
            threshold_weeks = 2
            mp_intro_weeks = 2
            race_specific_weeks = build_weeks - 6
        else:
            # Very short plan
            base_weeks = 1
            threshold_weeks = 2
            mp_intro_weeks = 1
            race_specific_weeks = build_weeks - 4
        
        current_week = 1
        
        # Phase 1: Base + Speed
        phases.append(TrainingPhase(
            name="Base + Speed Foundation",
            phase_type=Phase.BASE_SPEED,
            weeks=list(range(current_week, current_week + base_weeks)),
            focus="Build aerobic base, introduce speed while fresh",
            quality_sessions=1,  # Just strides/hills
            volume_modifier=0.75,
            long_run_modifier=0.7,
            allowed_workouts=["easy", "long", "strides", "hills", "recovery"],
            key_sessions=["strides", "hill_sprints"]
        ))
        current_week += base_weeks
        
        # Phase 2: Threshold Block
        phases.append(TrainingPhase(
            name="Threshold Block",
            phase_type=Phase.THRESHOLD,
            weeks=list(range(current_week, current_week + threshold_weeks)),
            focus="Build lactate threshold, T-block progression",
            quality_sessions=1,
            volume_modifier=0.85,
            long_run_modifier=0.8,
            allowed_workouts=["easy", "long", "threshold_intervals", "threshold", "recovery"],
            key_sessions=["threshold_intervals", "threshold"]
        ))
        current_week += threshold_weeks
        
        # Phase 3: MP Introduction
        phases.append(TrainingPhase(
            name="Marathon Pace Introduction",
            phase_type=Phase.MARATHON_SPECIFIC,
            weeks=list(range(current_week, current_week + mp_intro_weeks)),
            focus="Introduce marathon pace, build specificity",
            quality_sessions=2,  # T + MP in long run
            volume_modifier=0.95,
            long_run_modifier=0.9,
            allowed_workouts=["easy", "long", "long_mp", "threshold", "threshold_intervals", "medium_long_mp", "easy_strides"],
            key_sessions=["marathon_pace_long", "threshold"]
        ))
        current_week += mp_intro_weeks
        
        # Phase 4: Race Specific
        race_specific_weeks = max(1, race_specific_weeks)
        phases.append(TrainingPhase(
            name="Race Specific",
            phase_type=Phase.RACE_SPECIFIC,
            weeks=list(range(current_week, current_week + race_specific_weeks)),
            focus="Peak MP work, race simulation, peak fitness",
            quality_sessions=2,
            volume_modifier=1.0,  # Peak
            long_run_modifier=1.0,  # Peak
            allowed_workouts=["easy", "long", "long_mp", "threshold", "threshold_intervals", "race", "medium_long_mp", "easy_strides"],
            key_sessions=["dress_rehearsal", "continuous_mp"]
        ))
        current_week += race_specific_weeks
        
        # Phase 5: Taper — progressive volume reduction (ADR-062)
        # Volume drops progressively, intensity maintained with short touches.
        # 3-week taper: 70% → 50% → race week (30%)
        # 2-week taper: 50% → race week (30%)
        # 1-week taper: race week only (30%)
        taper_phase_weeks = taper_weeks - 1  # Exclude race week
        if taper_phase_weeks >= 2:
            # Early taper (higher volume, last real quality session)
            phases.append(TrainingPhase(
                name="Early Taper",
                phase_type=Phase.TAPER,
                weeks=[current_week],
                focus="Begin volume reduction, last quality session",
                quality_sessions=1,
                volume_modifier=0.70,
                long_run_modifier=0.6,
                allowed_workouts=["easy", "threshold", "threshold_short", "strides", "recovery"],
                key_sessions=["threshold", "strides"]
            ))
            current_week += 1
            # Main taper (sharper reduction, threshold touches only)
            remaining_taper = taper_phase_weeks - 1
            if remaining_taper > 0:
                phases.append(TrainingPhase(
                    name="Taper",
                    phase_type=Phase.TAPER,
                    weeks=list(range(current_week, current_week + remaining_taper)),
                    focus="Reduce volume, maintain intensity with short touches",
                    quality_sessions=1,
                    volume_modifier=0.50,
                    long_run_modifier=0.5,
                    allowed_workouts=["easy", "threshold_short", "strides", "recovery"],
                    key_sessions=["sharpening", "strides"]
                ))
                current_week += remaining_taper
        elif taper_phase_weeks == 1:
            phases.append(TrainingPhase(
                name="Taper",
                phase_type=Phase.TAPER,
                weeks=[current_week],
                focus="Reduce volume, maintain intensity, peak for race",
                quality_sessions=1,
                volume_modifier=0.50,
                long_run_modifier=0.5,
                allowed_workouts=["easy", "threshold_short", "strides", "recovery"],
                key_sessions=["sharpening", "strides"]
            ))
            current_week += 1
        
        # Race week (always separate)
        phases.append(TrainingPhase(
            name="Race Week",
            phase_type=Phase.RACE,
            weeks=[duration_weeks],
            focus="Race day - trust your training!",
            quality_sessions=0,
            volume_modifier=0.3,
            long_run_modifier=0.0,
            allowed_workouts=["easy", "strides", "rest", "race"],
            key_sessions=["race"]
        ))
        
        return phases
    
    def _build_half_marathon_phases(
        self,
        duration_weeks: int,
        taper_weeks: int,
        tier: VolumeTier
    ) -> List[TrainingPhase]:
        """Build half marathon phases."""
        phases = []
        build_weeks = duration_weeks - taper_weeks
        race_week = duration_weeks
        
        # Phase allocation
        if build_weeks >= 14:
            base_weeks = 4
            threshold_weeks = 5
            race_specific_weeks = build_weeks - 9
        elif build_weeks >= 10:
            base_weeks = 3
            threshold_weeks = 4
            race_specific_weeks = build_weeks - 7
        else:
            base_weeks = 2
            threshold_weeks = 3
            race_specific_weeks = build_weeks - 5
        
        current_week = 1
        
        # Base + Speed
        phases.append(TrainingPhase(
            name="Base + Speed",
            phase_type=Phase.BASE_SPEED,
            weeks=list(range(current_week, current_week + base_weeks)),
            focus="Aerobic foundation with speed development",
            quality_sessions=1,
            volume_modifier=0.75,
            long_run_modifier=0.7,
            allowed_workouts=["easy", "long", "strides", "hills", "fartlek"],
            key_sessions=["strides", "hill_sprints", "fartlek"]
        ))
        current_week += base_weeks
        
        # Threshold Development
        phases.append(TrainingPhase(
            name="Threshold Development",
            phase_type=Phase.THRESHOLD,
            weeks=list(range(current_week, current_week + threshold_weeks)),
            focus="Build lactate threshold and tempo endurance",
            quality_sessions=2,
            volume_modifier=0.9,
            long_run_modifier=0.85,
            allowed_workouts=["easy", "long", "threshold", "tempo", "intervals"],
            key_sessions=["threshold_intervals", "tempo", "vo2max_short"]
        ))
        current_week += threshold_weeks
        
        # Race Specific
        phases.append(TrainingPhase(
            name="Race Specific",
            phase_type=Phase.RACE_SPECIFIC,
            weeks=list(range(current_week, current_week + race_specific_weeks)),
            focus="Half marathon pace work and race simulation",
            quality_sessions=2,
            volume_modifier=1.0,
            long_run_modifier=1.0,
            allowed_workouts=["easy", "long", "tempo_long", "threshold", "race_pace"],
            key_sessions=["goal_pace_tempo", "race_simulation"]
        ))
        current_week += race_specific_weeks
        
        # Taper
        phases.append(TrainingPhase(
            name="Taper",
            phase_type=Phase.TAPER,
            weeks=list(range(current_week, current_week + taper_weeks)),
            focus="Sharpen and rest for race day",
            quality_sessions=1,
            volume_modifier=0.5,
            long_run_modifier=0.5,
            allowed_workouts=["easy", "strides", "threshold_short"],
            key_sessions=["sharpening"]
        ))
        current_week += taper_weeks
        
        # Race week
        phases.append(TrainingPhase(
            name="Race Week",
            phase_type=Phase.RACE,
            weeks=[race_week],
            focus="Race day!",
            quality_sessions=0,
            volume_modifier=0.3,
            long_run_modifier=0.0,
            allowed_workouts=["easy", "strides", "rest", "race"],
            key_sessions=["race"]
        ))
        
        return phases
    
    def _build_10k_phases(
        self,
        duration_weeks: int,
        taper_weeks: int,
        tier: VolumeTier
    ) -> List[TrainingPhase]:
        """Build 10K phases."""
        phases = []
        build_weeks = duration_weeks - taper_weeks
        race_week = duration_weeks
        
        if build_weeks >= 10:
            base_weeks = 3
            vo2max_weeks = 4
            race_specific_weeks = build_weeks - 7
        else:
            base_weeks = 2
            vo2max_weeks = 3
            race_specific_weeks = build_weeks - 5
        
        current_week = 1
        
        # Base + Speed
        phases.append(TrainingPhase(
            name="Base + Speed",
            phase_type=Phase.BASE_SPEED,
            weeks=list(range(current_week, current_week + base_weeks)),
            focus="Aerobic base with speed development",
            quality_sessions=2,
            volume_modifier=0.8,
            long_run_modifier=0.75,
            allowed_workouts=["easy", "long", "strides", "fartlek", "hills"],
            key_sessions=["strides", "fartlek"]
        ))
        current_week += base_weeks
        
        # VO2max Development
        phases.append(TrainingPhase(
            name="VO2max Development",
            phase_type=Phase.THRESHOLD,
            weeks=list(range(current_week, current_week + vo2max_weeks)),
            focus="Build aerobic power through intervals",
            quality_sessions=2,
            volume_modifier=0.95,
            long_run_modifier=0.9,
            allowed_workouts=["easy", "long", "intervals", "threshold", "tempo"],
            key_sessions=["vo2max_intervals", "threshold"]
        ))
        current_week += vo2max_weeks
        
        # Race Specific
        phases.append(TrainingPhase(
            name="Race Specific",
            phase_type=Phase.RACE_SPECIFIC,
            weeks=list(range(current_week, current_week + race_specific_weeks)),
            focus="10K pace work and race simulation",
            quality_sessions=2,
            volume_modifier=1.0,
            long_run_modifier=1.0,
            allowed_workouts=["easy", "long", "race_pace", "intervals", "tempo"],
            key_sessions=["race_pace_intervals", "tempo"]
        ))
        current_week += race_specific_weeks
        
        # Taper
        phases.append(TrainingPhase(
            name="Taper",
            phase_type=Phase.TAPER,
            weeks=list(range(current_week, current_week + taper_weeks)),
            focus="Sharpen for race",
            quality_sessions=1,
            volume_modifier=0.6,
            long_run_modifier=0.5,
            allowed_workouts=["easy", "strides", "short_intervals"],
            key_sessions=["sharpening"]
        ))
        current_week += taper_weeks
        
        # Race
        phases.append(TrainingPhase(
            name="Race Week",
            phase_type=Phase.RACE,
            weeks=[race_week],
            focus="Race day!",
            quality_sessions=0,
            volume_modifier=0.3,
            long_run_modifier=0.0,
            allowed_workouts=["easy", "strides", "rest", "race"],
            key_sessions=["race"]
        ))
        
        return phases
    
    def _build_5k_phases(
        self,
        duration_weeks: int,
        taper_weeks: int,
        tier: VolumeTier
    ) -> List[TrainingPhase]:
        """Build 5K phases."""
        phases = []
        build_weeks = duration_weeks - taper_weeks
        race_week = duration_weeks
        
        if build_weeks >= 10:
            base_weeks = 3
            speed_weeks = 4
            race_specific_weeks = build_weeks - 7
        else:
            base_weeks = 2
            speed_weeks = 3
            race_specific_weeks = build_weeks - 5
        
        current_week = 1
        
        # Base + Speed
        phases.append(TrainingPhase(
            name="Base + Speed",
            phase_type=Phase.BASE_SPEED,
            weeks=list(range(current_week, current_week + base_weeks)),
            focus="Build base with strides and short repeats",
            quality_sessions=2,
            volume_modifier=0.8,
            long_run_modifier=0.75,
            allowed_workouts=["easy", "long", "strides", "hills", "fartlek"],
            key_sessions=["strides", "hill_sprints"]
        ))
        current_week += base_weeks
        
        # Speed Development
        phases.append(TrainingPhase(
            name="Speed Development",
            phase_type=Phase.THRESHOLD,
            weeks=list(range(current_week, current_week + speed_weeks)),
            focus="Develop speed and VO2max",
            quality_sessions=2,
            volume_modifier=0.95,
            long_run_modifier=0.9,
            allowed_workouts=["easy", "long", "intervals", "repetitions", "threshold"],
            key_sessions=["vo2max_intervals", "fast_reps"]
        ))
        current_week += speed_weeks
        
        # Race Specific
        phases.append(TrainingPhase(
            name="Race Specific",
            phase_type=Phase.RACE_SPECIFIC,
            weeks=list(range(current_week, current_week + race_specific_weeks)),
            focus="5K pace work and sharpening",
            quality_sessions=2,
            volume_modifier=1.0,
            long_run_modifier=1.0,
            allowed_workouts=["easy", "long", "race_pace", "intervals", "tempo"],
            key_sessions=["race_pace_reps", "tempo"]
        ))
        current_week += race_specific_weeks
        
        # Taper
        phases.append(TrainingPhase(
            name="Taper",
            phase_type=Phase.TAPER,
            weeks=list(range(current_week, current_week + taper_weeks)),
            focus="Rest and sharpen",
            quality_sessions=1,
            volume_modifier=0.6,
            long_run_modifier=0.5,
            allowed_workouts=["easy", "strides"],
            key_sessions=["strides"]
        ))
        current_week += taper_weeks
        
        # Race
        phases.append(TrainingPhase(
            name="Race Week",
            phase_type=Phase.RACE,
            weeks=[race_week],
            focus="Race day!",
            quality_sessions=0,
            volume_modifier=0.3,
            long_run_modifier=0.0,
            allowed_workouts=["easy", "strides", "rest", "race"],
            key_sessions=["race"]
        ))
        
        return phases
    
    def get_phase_for_week(
        self,
        phases: List[TrainingPhase],
        week: int
    ) -> TrainingPhase:
        """Get the phase for a specific week."""
        for phase in phases:
            if week in phase.weeks:
                return phase
        return phases[-1]  # Default to last phase
