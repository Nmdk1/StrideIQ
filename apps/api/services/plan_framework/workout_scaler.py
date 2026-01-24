"""
Workout Scaler

Scales workout prescriptions based on:
- Athlete volume tier
- Weekly mileage
- Phase context
- Source B limits (10% threshold, 8% interval, etc.)

Usage:
    scaler = WorkoutScaler()
    
    workout = scaler.scale_threshold_intervals(
        weekly_volume=55,
        tier="mid",
        phase="threshold",
        week_in_phase=2
    )
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .constants import (
    VolumeTier, 
    Phase, 
    WorkoutCategory,
    WORKOUT_LIMITS,
    LONG_RUN_PEAKS,
    Distance
)


@dataclass
class ScaledWorkout:
    """A workout scaled to athlete capacity."""
    workout_type: str
    category: WorkoutCategory
    title: str
    description: str
    
    # Volume
    total_distance_miles: Optional[float]
    duration_minutes: Optional[int]
    
    # Structure (for intervals, etc.)
    segments: Optional[List[Dict[str, Any]]]
    
    # Pace target (if known)
    pace_description: str
    
    # Option A/B variant
    option: str  # "A" or "B"
    option_b: Optional['ScaledWorkout'] = None


class WorkoutScaler:
    """
    Scale workouts to athlete capacity using knowledge base principles.
    
    Key rules (Source B):
    - Max 10% of weekly volume in one threshold session
    - Max 8% of weekly volume in one interval session  
    - Max 5% of weekly volume in repetition work
    - Long run targets 30% of weekly volume
    - MP work capped at 18 miles continuous
    """
    
    def __init__(self):
        self.limits = WORKOUT_LIMITS
    
    def scale_workout(
        self,
        workout_type: str,
        weekly_volume: float,
        tier: str,
        phase: str,
        week_in_phase: int = 1,
        distance: str = "marathon",
        mp_week: int = 1  # For tracking MP long run progression
    ) -> ScaledWorkout:
        """
        Scale any workout type to athlete capacity.
        
        Args:
            workout_type: Type of workout to scale
            weekly_volume: Athlete's weekly mileage
            tier: Volume tier
            phase: Current training phase
            week_in_phase: Week number within phase (for progression)
            distance: Goal race distance
            
        Returns:
            ScaledWorkout with appropriate prescription
        """
        # Route to specific scaler
        if workout_type in ["easy", "recovery", "easy_run"]:
            return self._scale_easy(weekly_volume, workout_type)

        # Easy run with strides appended (neuromuscular touch; NOT a "quality session")
        elif workout_type in ["easy_strides"]:
            return self._scale_easy_with_strides(weekly_volume)
        
        elif workout_type in ["long", "long_run"]:
            return self._scale_long_run(weekly_volume, tier, distance)
        
        elif workout_type in ["threshold_intervals", "t_intervals"]:
            return self._scale_threshold_intervals(weekly_volume, tier, week_in_phase)
        
        # Canonical: "threshold" is the Training Pace Calculator threshold (T pace).
        # We treat continuous threshold runs as workout_type="threshold" (not "tempo").
        # Back-compat: accept "tempo" as an alias but DO NOT emit it.
        elif workout_type in ["threshold", "t_run", "tempo"]:
            return self._scale_threshold_continuous(weekly_volume, tier, week_in_phase)
        
        elif workout_type in ["long_mp", "marathon_pace_long"]:
            return self._scale_mp_long_run(weekly_volume, tier, distance, week_in_phase, mp_week)
        
        elif workout_type in ["medium_long", "medium_long_mp"]:
            return self._scale_medium_long(weekly_volume, tier, week_in_phase)
        
        elif workout_type in ["interval", "intervals", "vo2max"]:
            return self._scale_intervals(weekly_volume, tier, phase)
        
        elif workout_type in ["strides"]:
            return self._scale_strides()
        
        elif workout_type in ["hills", "hill_sprints"]:
            return self._scale_hills(tier)
        
        elif workout_type == "rest":
            return self._scale_rest()
        
        else:
            # Default to easy
            return self._scale_easy(weekly_volume, workout_type)
    
    def _scale_easy(
        self,
        weekly_volume: float,
        workout_type: str
    ) -> ScaledWorkout:
        """Scale easy run."""
        # Easy runs fill remaining volume after quality
        # Typically 5-8 miles depending on volume
        if weekly_volume >= 70:
            distance = 8
        elif weekly_volume >= 50:
            distance = 7
        elif weekly_volume >= 35:
            distance = 6
        else:
            distance = 5
        
        return ScaledWorkout(
            workout_type=workout_type,
            category=WorkoutCategory.EASY,
            title="Easy Run",
            description="Conversational pace. Focus on relaxed form.",
            total_distance_miles=distance,
            duration_minutes=int(distance * 9.5),  # ~9:30 pace
            segments=None,
            pace_description="conversational, relaxed effort",
            option="A"
        )
    
    def _scale_long_run(
        self,
        weekly_volume: float,
        tier: str,
        distance: str
    ) -> ScaledWorkout:
        """Scale easy long run (no workout component)."""
        try:
            dist = Distance(distance)
            vol_tier = VolumeTier(tier)
        except ValueError:
            dist = Distance.MARATHON
            vol_tier = VolumeTier.MID
        
        # Get peak long run for this tier/distance
        peak = LONG_RUN_PEAKS.get(dist, {}).get(vol_tier, 18)
        
        # Long run target (default): ~28% of weekly.
        # For high-volume marathon training, allow slightly higher by default
        # (durability requirement), but still cap by tier/distance peak.
        pct = 0.28
        if (distance or "").strip().lower() in ("marathon",) and weekly_volume >= 60:
            pct = 0.30
        target = min(weekly_volume * pct, peak)
        target = max(target, 10)  # Minimum 10 miles
        
        return ScaledWorkout(
            workout_type="long_run",
            category=WorkoutCategory.LONG,
            title="Long Run",
            description="Easy effort throughout. Build endurance through time on feet.",
            total_distance_miles=round(target, 0),
            duration_minutes=int(target * 9.5),
            segments=None,
            pace_description="easy conversational pace, 60-90 sec slower than marathon pace",
            option="A"
        )
    
    def _scale_threshold_intervals(
        self,
        weekly_volume: float,
        tier: str,
        week_in_phase: int
    ) -> ScaledWorkout:
        """
        Scale threshold intervals with progression.
        
        T-block progression:
        Week 1: 4x5 min
        Week 2: 5x5 min
        Week 3: 4x7 min or 3x10 min
        Week 4: 4x10 min or 35 min continuous
        """
        # Max threshold volume per session (10%)
        max_t_miles = weekly_volume * self.limits["threshold_pct"]
        max_t_minutes = max_t_miles * 6  # ~6 min/mile at T
        
        # Progress through T-block
        if week_in_phase <= 1:
            reps, duration = 4, 5
        elif week_in_phase == 2:
            reps, duration = 5, 5
        elif week_in_phase == 3:
            reps, duration = 3, 10
        else:
            reps, duration = 4, 10
        
        total_t_time = reps * duration
        
        # Cap at 10% rule
        if total_t_time > max_t_minutes:
            # Reduce volume
            reps = max(2, int(max_t_minutes / duration))
        
        segments = [
            {"type": "warmup", "distance_miles": 2, "pace": "easy"},
            {"type": "intervals", "reps": reps, "duration_min": duration, "rest_min": 2, "pace": "threshold"},
            {"type": "cooldown", "distance_miles": 1.5, "pace": "easy"},
        ]
        
        return ScaledWorkout(
            workout_type="threshold_intervals",
            category=WorkoutCategory.THRESHOLD,
            title=f"Threshold Intervals: {reps}x{duration} min",
            description=f"{reps}x{duration} min at threshold pace with 2 min jog recovery",
            total_distance_miles=round(3.5 + (reps * duration * 0.17), 1),
            duration_minutes=int(25 + reps * (duration + 2)),
            segments=segments,
            pace_description="comfortably hard - can speak in short sentences",
            option="A"
        )
    
    def _scale_threshold_continuous(
        self,
        weekly_volume: float,
        tier: str,
        week_in_phase: int
    ) -> ScaledWorkout:
        """Scale continuous threshold run (T pace)."""
        # Max threshold volume
        max_t_miles = weekly_volume * self.limits["threshold_pct"]
        max_t_minutes = max_t_miles * 6
        
        # Progress: 15 → 20 → 25 → 30+ min
        base = 15
        progression = min(week_in_phase * 5, 20)  # Max +20 min
        tempo_duration = min(base + progression, max_t_minutes)
        tempo_duration = max(tempo_duration, 15)  # Min 15 min
        
        total_distance = 3 + (tempo_duration * 0.17)  # WU/CD + tempo
        
        return ScaledWorkout(
            workout_type="threshold",
            category=WorkoutCategory.THRESHOLD,
            title=f"Threshold Run: {int(tempo_duration)} min",
            description=f"Continuous {int(tempo_duration)} min at threshold pace",
            total_distance_miles=round(total_distance, 1),
            duration_minutes=int(25 + tempo_duration),
            segments=[
                {"type": "warmup", "distance_miles": 2, "pace": "easy"},
                {"type": "threshold", "duration_min": int(tempo_duration), "pace": "threshold"},
                {"type": "cooldown", "distance_miles": 1, "pace": "easy"},
            ],
            pace_description="comfortably hard, sustainable for the full duration",
            option="A"
        )
    
    def _scale_mp_long_run(
        self,
        weekly_volume: float,
        tier: str,
        distance: str,
        week_in_phase: int,
        mp_week: int = 1  # Overall MP workout number (1, 2, 3, 4...)
    ) -> ScaledWorkout:
        """
        Scale marathon pace long run with progression.
        
        MP progression (based on mp_week, not phase):
        MP Week 1: 6 miles (2x3 mi MP intervals)
        MP Week 2: 8 miles continuous at MP
        MP Week 3: 10-12 miles continuous at MP
        MP Week 4+: 14-16 miles continuous at MP (dress rehearsal)
        """
        try:
            dist = Distance(distance)
            vol_tier = VolumeTier(tier)
        except ValueError:
            dist = Distance.MARATHON
            vol_tier = VolumeTier.MID
        
        # Get peak long run
        peak_long = LONG_RUN_PEAKS.get(dist, {}).get(vol_tier, 22)
        
        # MP volume limits (Source B)
        max_mp_miles = min(self.limits["mp_max_miles"], peak_long * 0.75)
        
        # Progress MP work based on total MP workout count
        if mp_week <= 1:
            mp_miles = 6
            mp_structure = "2x3 miles at MP with 1 mile easy between"
        elif mp_week == 2:
            mp_miles = 8
            mp_structure = "8 miles continuous at MP"
        elif mp_week == 3:
            mp_miles = 12
            mp_structure = "12 miles continuous at MP"
        elif mp_week == 4:
            mp_miles = min(14, max_mp_miles)
            mp_structure = f"{int(mp_miles)} miles continuous at MP"
        else:
            mp_miles = min(16, max_mp_miles)
            mp_structure = f"{int(mp_miles)} miles continuous at MP (dress rehearsal)"
        
        # Total run length
        total_miles = min(mp_miles + 6, peak_long)  # MP + warmup/cooldown
        
        return ScaledWorkout(
            workout_type="long_mp",
            category=WorkoutCategory.RACE_PACE,
            title=f"Long Run with MP: {mp_structure}",
            description=f"{int(total_miles)} miles total with {mp_structure}",
            total_distance_miles=total_miles,
            duration_minutes=int(total_miles * 8.5),
            segments=[
                {"type": "warmup", "distance_miles": 3, "pace": "easy"},
                {"type": "marathon_pace", "distance_miles": mp_miles, "pace": "MP"},
                {"type": "cooldown", "distance_miles": total_miles - mp_miles - 3, "pace": "easy"},
            ],
            pace_description="goal marathon race pace",
            option="A",
            option_b=self._create_mp_option_b(mp_miles, total_miles)
        )
    
    def _create_mp_option_b(
        self,
        mp_miles: float,
        total_miles: float
    ) -> 'ScaledWorkout':
        """Create Option B for MP long run (intervals instead of continuous)."""
        # Break continuous MP into intervals
        if mp_miles <= 8:
            reps = int(mp_miles / 2)
            rep_distance = 2
        else:
            reps = int(mp_miles / 4)
            rep_distance = 4
        
        return ScaledWorkout(
            workout_type="long_mp_intervals",
            category=WorkoutCategory.RACE_PACE,
            title=f"Long Run with MP: {reps}x{rep_distance} mi at MP",
            description=f"{int(total_miles)} miles total with {reps}x{rep_distance} mi at MP, 1 mi easy between",
            total_distance_miles=total_miles,
            duration_minutes=int(total_miles * 8.5),
            segments=[
                {"type": "warmup", "distance_miles": 3, "pace": "easy"},
                {"type": "intervals", "reps": reps, "distance_miles": rep_distance, "rest_miles": 1, "pace": "MP"},
                {"type": "cooldown", "distance_miles": 2, "pace": "easy"},
            ],
            pace_description="goal marathon race pace with recovery between",
            option="B"
        )
    
    def _scale_medium_long(
        self,
        weekly_volume: float,
        tier: str,
        week_in_phase: int
    ) -> ScaledWorkout:
        """Scale medium-long run (mid-week endurance)."""
        # Typically 10-15 miles
        if weekly_volume >= 70:
            distance = 15
        elif weekly_volume >= 55:
            distance = 13
        elif weekly_volume >= 40:
            distance = 11
        else:
            distance = 10
        
        return ScaledWorkout(
            workout_type="medium_long",
            category=WorkoutCategory.LONG,
            # Avoid the phrase "Long Run" in the title (tests/UI treat "Long Run" as the weekly anchor).
            title=f"Medium Long: {distance} mi",
            description="Steady aerobic effort. Builds endurance between long runs.",
            total_distance_miles=distance,
            duration_minutes=int(distance * 9),
            segments=None,
            pace_description="easy to steady, slightly quicker than long run pace",
            option="A"
        )
    
    def _scale_intervals(
        self,
        weekly_volume: float,
        tier: str,
        phase: str
    ) -> ScaledWorkout:
        """Scale VO2max intervals."""
        # Max interval volume (8%)
        max_i_miles = weekly_volume * self.limits["interval_pct"]

        phase_norm = (phase or "").strip().lower()

        # For high-volume contexts early in cycle, short reps are a safer VO2 “touch”
        # while still delivering meaningful ceiling work.
        if phase_norm in ("base_speed", "base") and weekly_volume >= 60:
            rep_miles = 400 / 1609.344  # 400m in miles
            reps = int(max_i_miles / rep_miles) if rep_miles > 0 else 12
            reps = max(10, min(16, reps))

            return ScaledWorkout(
                workout_type="intervals",
                category=WorkoutCategory.INTERVAL,
                title=f"Intervals: {reps}x400m",
                description=f"{reps}x400m at VO2max pace with 200m jog recovery",
                total_distance_miles=round(3 + reps * 0.35, 1),
                duration_minutes=int(30 + reps * 2),
                segments=[
                    {"type": "warmup", "distance_miles": 2, "pace": "easy"},
                    {"type": "intervals", "reps": reps, "distance_m": 400, "rest_m": 200, "pace": "interval"},
                    {"type": "cooldown", "distance_miles": 1, "pace": "easy"},
                ],
                pace_description="hard effort, controlled — smooth mechanics, not a sprint",
                option="A",
            )

        # Default: 1K reps (classic VO2)
        reps = min(6, max(4, int(max_i_miles / 0.62)))  # 1km = 0.62 mi
        return ScaledWorkout(
            workout_type="intervals",
            category=WorkoutCategory.INTERVAL,
            title=f"Intervals: {reps}x1000m",
            description=f"{reps}x1000m at VO2max pace with 2-3 min jog recovery",
            total_distance_miles=round(3 + reps * 0.8, 1),
            duration_minutes=int(30 + reps * 6),
            segments=[
                {"type": "warmup", "distance_miles": 2, "pace": "easy"},
                {"type": "intervals", "reps": reps, "distance_m": 1000, "rest_min": 2.5, "pace": "interval"},
                {"type": "cooldown", "distance_miles": 1, "pace": "easy"},
            ],
            pace_description="hard effort, controlled - NOT all-out",
            option="A",
        )
    
    def _scale_strides(self) -> ScaledWorkout:
        """Scale strides workout."""
        return ScaledWorkout(
            workout_type="strides",
            category=WorkoutCategory.SPEED,
            title="Easy + Strides",
            description="Easy run with 6-8x20-30 sec strides at the end",
            total_distance_miles=6,
            duration_minutes=55,
            segments=[
                {"type": "easy", "distance_miles": 5, "pace": "easy"},
                {"type": "strides", "reps": 6, "duration_sec": 25, "rest_sec": 60, "pace": "fast_controlled"},
            ],
            pace_description="strides: quick turnover, controlled, focus on form",
            option="A"
        )

    def _scale_easy_with_strides(self, weekly_volume: float) -> ScaledWorkout:
        """
        Easy run with strides appended.

        Preserves weekly volume targets while adding a low-fatigue neuromuscular touch.
        """
        base = self._scale_easy(weekly_volume, "easy")
        distance = base.total_distance_miles or 6
        easy_portion = max(0.0, distance - 0.5)  # leave room for strides + walk recovery
        segments = [
            {"type": "easy", "distance_miles": round(easy_portion, 1), "pace": "easy"},
            {"type": "strides", "reps": 6, "duration_sec": 25, "rest_sec": 60, "pace": "fast_controlled"},
        ]
        return ScaledWorkout(
            workout_type="easy_strides",
            category=WorkoutCategory.EASY,
            title="Easy + Strides",
            description="Easy run, then 6×20–30s strides with full recovery. Stay relaxed.",
            total_distance_miles=distance,
            duration_minutes=base.duration_minutes,
            segments=segments,
            pace_description="easy + strides: relaxed, quick turnover (not hard breathing)",
            option="A",
        )
    
    def _scale_hills(self, tier: str) -> ScaledWorkout:
        """Scale hill sprints."""
        if tier in ["high", "elite"]:
            reps = 10
        elif tier == "mid":
            reps = 8
        else:
            reps = 6
        
        return ScaledWorkout(
            workout_type="hills",
            category=WorkoutCategory.SPEED,
            title=f"Easy + Hill Sprints: {reps}x10 sec",
            description=f"Easy run with {reps}x10 sec hill sprints",
            total_distance_miles=6,
            duration_minutes=55,
            segments=[
                {"type": "easy", "distance_miles": 5, "pace": "easy"},
                {"type": "hill_sprints", "reps": reps, "duration_sec": 10, "rest_sec": 90, "pace": "max"},
            ],
            pace_description="hills: FAST uphill, walk back recovery",
            option="A"
        )
    
    def _scale_rest(self) -> ScaledWorkout:
        """Rest day."""
        return ScaledWorkout(
            workout_type="rest",
            category=WorkoutCategory.REST,
            title="Rest Day",
            description="Complete rest or light cross-training. Recovery is when adaptation happens.",
            total_distance_miles=0,
            duration_minutes=0,
            segments=None,
            pace_description="no running",
            option="A"
        )
