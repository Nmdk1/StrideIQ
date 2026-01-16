"""
Workout Classification Service

Automatically classifies runs into workout types based on training methodology.

PHILOSOPHY NOTE:
We deliberately avoid exposing "zone" terminology to athletes.
The body operates on a continuous spectrum, not discrete zones.
WorkoutZone is used INTERNALLY for grouping similar workout types,
not to imply physiological buckets.

See: _AI_CONTEXT_/KNOWLEDGE_BASE/01_INTENSITY_PHILOSOPHY.md

Key principles:
- Workout TYPE describes structure/intent (tempo run, intervals, progression)
- Intensity SCORE is a continuous 0-100 spectrum (honest about the continuum)
- WorkoutZone is for internal categorization only (never shown as "Zone X")

This service looks at:
- Average pace vs known race paces
- Heart rate patterns (continuous, not discrete zones)
- Pace variability (steady vs intervals)
- Duration
- Elevation profile
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import math

from models import Activity, Athlete
import re


def _matches_keyword(keyword: str, text: str) -> bool:
    """
    Check if keyword matches text as a whole word (word boundary matching).
    
    This avoids false positives like:
    - "skipped intervals" matching "interval" (negated context)
    - "easy workout" matching "workout" (different type)
    - "recovery workout" matching "workout"
    
    For multi-word keywords, uses substring matching.
    For single words, uses word boundary regex with optional plural.
    """
    text_lower = text.lower()
    keyword_lower = keyword.lower()
    
    # For multi-word keywords, substring match is fine
    if ' ' in keyword:
        return keyword_lower in text_lower
    
    # For single words, use word boundary with optional 's' for plurals
    # e.g., 'interval' matches 'interval' or 'intervals'
    pattern = r'\b' + re.escape(keyword_lower) + r's?\b'
    return bool(re.search(pattern, text_lower))


def _has_negation_context(keyword: str, text: str) -> bool:
    """
    Check if keyword appears in a negated context.
    
    Examples:
    - "skipped intervals" - negated
    - "no tempo today" - negated  
    - "cancelled track workout" - negated
    """
    text_lower = text.lower()
    keyword_lower = keyword.lower()
    
    # Negation words that typically appear before the keyword
    negation_patterns = [
        f"skip(ped|ping)? {keyword_lower}",
        f"no {keyword_lower}",
        f"cancel(led|ling)? {keyword_lower}",
        f"missed {keyword_lower}",
        f"didn'?t do {keyword_lower}",
        f"instead of {keyword_lower}",
        f"not a {keyword_lower}",
    ]
    
    for pattern in negation_patterns:
        if re.search(pattern, text_lower):
            return True
    
    return False


class WorkoutZone(str, Enum):
    """
    INTERNAL effort categories - NOT exposed to athletes as "zones".
    
    These are used for grouping similar workout types, NOT to imply
    that the body has discrete physiological "zones".
    
    See: _AI_CONTEXT_/KNOWLEDGE_BASE/01_INTENSITY_PHILOSOPHY.md
    
    When displaying to athletes, use effort descriptions:
    - RECOVERY -> "Very Easy"
    - ENDURANCE -> "Easy / Aerobic"  
    - STAMINA -> "Moderate / Threshold"
    - SPEED -> "Hard / High Intensity"
    - SPRINT -> "Very Hard / Maximum"
    - RACE_SPECIFIC -> "Race Effort"
    - MIXED -> "Variable"
    """
    RECOVERY = "recovery"
    ENDURANCE = "endurance"
    STAMINA = "stamina"  # Threshold region
    SPEED = "speed"  # High intensity
    SPRINT = "sprint"  # Maximum
    RACE_SPECIFIC = "race_specific"
    MIXED = "mixed"  # Progression, fartlek


class WorkoutType(str, Enum):
    """Specific workout classifications"""
    # Zone 1: Recovery/Easy
    RECOVERY_RUN = "recovery_run"
    EASY_RUN = "easy_run"
    SHAKEOUT = "shakeout"
    
    # Zone 2: Endurance
    LONG_RUN = "long_run"
    MEDIUM_LONG_RUN = "medium_long_run"
    AEROBIC_RUN = "aerobic_run"
    
    # Zone 3: Stamina/Threshold
    TEMPO_RUN = "tempo_run"
    TEMPO_INTERVALS = "tempo_intervals"
    CRUISE_INTERVALS = "cruise_intervals"
    THRESHOLD_RUN = "threshold_run"
    
    # Zone 4: Speed/VO2max
    VO2MAX_INTERVALS = "vo2max_intervals"
    FARTLEK = "fartlek"
    TRACK_WORKOUT = "track_workout"
    
    # Zone 5: Sprint/Anaerobic
    REPETITIONS = "repetitions"
    STRIDES = "strides"
    HILL_SPRINTS = "hill_sprints"
    HILL_REPETITIONS = "hill_repetitions"
    
    # Zone 6: Race-Specific
    MARATHON_PACE = "marathon_pace"
    HALF_MARATHON_PACE = "half_marathon_pace"
    GOAL_PACE_RUN = "goal_pace_run"
    RACE_SIMULATION = "race_simulation"
    TUNE_UP_RACE = "tune_up_race"
    RACE = "race"
    
    # Zone 7: Progression/Mixed
    PROGRESSION_RUN = "progression_run"
    FAST_FINISH_LONG = "fast_finish_long_run"
    NEGATIVE_SPLIT_RUN = "negative_split_run"
    
    # Unknown
    UNCLASSIFIED = "unclassified"


@dataclass
class WorkoutClassification:
    """Result of workout classification"""
    workout_type: WorkoutType
    workout_zone: WorkoutZone
    confidence: float  # 0-1
    reasoning: str
    detected_intervals: bool
    detected_progression: bool
    avg_hr_zone: Optional[int]  # 1-5 (internal use only)
    intensity_score: float  # 0-100 (objective, from data)
    expected_rpe_range: Optional[Tuple[int, int]] = None  # Expected RPE (Rate of Perceived Exertion, 1-10 scale)
    work_segments: int = 0  # Number of work intervals (if detected)
    avg_work_duration_min: float = 0.0  # Average work segment duration


@dataclass
class AthleteThresholds:
    """Known thresholds for an athlete"""
    max_hr: Optional[int]
    resting_hr: Optional[int]
    threshold_hr: Optional[int]
    threshold_pace_per_km: Optional[float]  # seconds per km
    vdot: Optional[float]
    marathon_pace_per_km: Optional[float]
    easy_pace_per_km: Optional[float]


class WorkoutClassifierService:
    """
    Classifies workouts based on objective data.
    
    Uses a hierarchical approach:
    1. Check for race indicators
    2. Check for interval patterns
    3. Check for progression patterns
    4. Classify by average pace/HR
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def classify_activity(
        self, 
        activity: Activity,
        athlete_thresholds: Optional[AthleteThresholds] = None
    ) -> WorkoutClassification:
        """
        Classify an activity into a workout type.
        """
        # Get athlete thresholds if not provided
        if athlete_thresholds is None:
            athlete_thresholds = self._get_athlete_thresholds(activity.athlete_id)
        
        # Extract key metrics
        duration_min = (activity.duration_s or 0) / 60
        distance_km = (activity.distance_m or 0) / 1000
        avg_pace_per_km = activity.duration_s / distance_km if distance_km > 0 else None
        avg_hr = activity.avg_hr
        
        # Check for race
        if activity.is_race_candidate or activity.user_verified_race:
            return self._classify_race(activity, athlete_thresholds)
        
        # =====================================================================
        # NAME-BASED CLASSIFICATION (user-provided signal is strong)
        # =====================================================================
        # Athletes often name workouts descriptively - trust this signal
        name_classification = self._classify_from_name(activity, athlete_thresholds, duration_min)
        if name_classification:
            return name_classification
        
        # Check for intervals (requires splits or lap data)
        intervals_detected, num_intervals, avg_interval_duration = self._detect_intervals(activity)
        
        # Check for progression pattern
        progression_detected = self._detect_progression(activity)
        
        # Check for hard finish (high max_hr vs avg_hr)
        hard_finish_detected = self._detect_hard_finish(activity)

        # Get HR zone if available
        hr_zone = self._calculate_hr_zone(avg_hr, athlete_thresholds)

        # Calculate intensity score (now includes max_hr consideration)
        intensity_score = self._calculate_intensity(
            avg_pace_per_km,
            avg_hr,
            athlete_thresholds,
            max_hr=activity.max_hr
        )
        
        # If progression or hard finish detected, ensure intensity reflects it
        if (progression_detected or hard_finish_detected) and intensity_score < 50:
            # Boost intensity to at least "moderate" for structured efforts
            intensity_score = max(intensity_score, 55)
        
        # Classify based on patterns and metrics
        if intervals_detected:
            return self._classify_interval_workout(
                activity, athlete_thresholds, hr_zone, intensity_score,
                num_intervals, avg_interval_duration
            )
        
        if progression_detected:
            return self._classify_progression(
                activity, athlete_thresholds, hr_zone, intensity_score
            )
        
        # Steady-state classification based on intensity
        return self._classify_steady_state(
            activity, athlete_thresholds, hr_zone, intensity_score, duration_min
        )
    
    def _get_athlete_thresholds(self, athlete_id: UUID) -> AthleteThresholds:
        """Get known thresholds for an athlete"""
        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        
        if not athlete:
            return AthleteThresholds(
                max_hr=None, resting_hr=None, threshold_hr=None,
                threshold_pace_per_km=None, vdot=None,
                marathon_pace_per_km=None, easy_pace_per_km=None
            )
        
        # Calculate derived paces from VDOT if available
        easy_pace = None
        marathon_pace = None
        threshold_pace = athlete.threshold_pace_per_km
        
        if athlete.vdot:
            # Approximate paces from VDOT using Daniels formulas
            # E pace is typically 60-74% of vVO2max
            # These are rough approximations
            vdot = athlete.vdot
            easy_pace = 337.5 - 2.5 * vdot  # ~7:00/km for VDOT 30, ~5:00/km for VDOT 50
            marathon_pace = 290 - 2.8 * vdot
        
        return AthleteThresholds(
            max_hr=athlete.max_hr,
            resting_hr=athlete.resting_hr,
            threshold_hr=athlete.threshold_hr,
            threshold_pace_per_km=threshold_pace,
            vdot=athlete.vdot,
            marathon_pace_per_km=marathon_pace,
            easy_pace_per_km=easy_pace
        )
    
    def _classify_from_name(
        self,
        activity: Activity,
        thresholds: AthleteThresholds,
        duration_min: float
    ) -> Optional[WorkoutClassification]:
        """
        Classify based on activity name keywords.
        
        Athletes often name their workouts descriptively:
        - "35 minutes at threshold effort"
        - "5x1mi intervals"
        - "Tempo run"
        - "Long run with fast finish"
        
        This is a strong user signal that should be trusted.
        Returns None if no clear classification from name.
        """
        name = (activity.name or '').lower()
        
        if not name:
            return None
        
        # Keywords mapped to workout types
        # Order matters - more specific patterns first
        
        # Race indicators (strongest signal)
        race_keywords = ['race', 'marathon', '5k', '10k', 'half marathon', 'pr ', 'personal best', 
                        'time trial', 'tt ', 'pb ', 'new record']
        if any(kw in name for kw in race_keywords) and 'pace' not in name:
            # Avoid matching "marathon pace run"
            return WorkoutClassification(
                workout_type=WorkoutType.RACE,
                workout_zone=WorkoutZone.RACE_SPECIFIC,
                confidence=0.85,
                reasoning=f"Name indicates race/competition: '{activity.name}'",
                detected_intervals=False,
                detected_progression=False,
                avg_hr_zone=5,
                intensity_score=95.0,
                expected_rpe_range=self.get_expected_rpe(WorkoutType.RACE, duration_min)
            )
        
        # Threshold/Tempo (often named explicitly)
        threshold_keywords = ['threshold', 'tempo', 'lt run', 'lactate threshold', 'cruise']
        if any(_matches_keyword(kw, name) and not _has_negation_context(kw, name) 
               for kw in threshold_keywords):
            # Check if it mentions intervals
            is_intervals = any(x in name for x in ['interval', 'repeat', 'x ', ' x'])
            if is_intervals:
                wt = WorkoutType.CRUISE_INTERVALS
            else:
                wt = WorkoutType.THRESHOLD_RUN
            return WorkoutClassification(
                workout_type=wt,
                workout_zone=WorkoutZone.STAMINA,
                confidence=0.85,
                reasoning=f"Name indicates threshold work: '{activity.name}'",
                detected_intervals=is_intervals,
                detected_progression=False,
                avg_hr_zone=4,
                intensity_score=75.0,
                expected_rpe_range=self.get_expected_rpe(wt, duration_min, is_intervals=is_intervals)
            )
        
        # Intervals/Speed work
        # Removed 'workout' and 'speed' as they're too generic (false positives)
        # 'workout' could match "easy workout", "recovery workout"
        # 'speed' could match "speed bump road" or similar
        interval_keywords = ['interval', 'repeat', 'vo2', 'vo2max', 'track workout',
                            '400s', '800s', '1000s', '1200s', 'mile repeat', 'yasso', 
                            'speed work', 'speed session']
        # Check for keyword match AND ensure no negation context
        if any(_matches_keyword(kw, name) and not _has_negation_context(kw, name) 
               for kw in interval_keywords):
            return WorkoutClassification(
                workout_type=WorkoutType.VO2MAX_INTERVALS,
                workout_zone=WorkoutZone.SPEED,
                confidence=0.80,
                reasoning=f"Name indicates interval work: '{activity.name}'",
                detected_intervals=True,
                detected_progression=False,
                avg_hr_zone=4,
                intensity_score=80.0,
                expected_rpe_range=self.get_expected_rpe(WorkoutType.VO2MAX_INTERVALS, duration_min, is_intervals=True)
            )
        
        # Fartlek
        if 'fartlek' in name:
            return WorkoutClassification(
                workout_type=WorkoutType.FARTLEK,
                workout_zone=WorkoutZone.MIXED,
                confidence=0.90,
                reasoning=f"Name indicates fartlek: '{activity.name}'",
                detected_intervals=True,
                detected_progression=False,
                avg_hr_zone=3,
                intensity_score=65.0,
                expected_rpe_range=self.get_expected_rpe(WorkoutType.FARTLEK, duration_min)
            )
        
        # Progression
        progression_keywords = ['progression', 'negative split', 'build', 'fast finish']
        if any(kw in name for kw in progression_keywords):
            return WorkoutClassification(
                workout_type=WorkoutType.PROGRESSION_RUN,
                workout_zone=WorkoutZone.MIXED,
                confidence=0.85,
                reasoning=f"Name indicates progression: '{activity.name}'",
                detected_intervals=False,
                detected_progression=True,
                avg_hr_zone=3,
                intensity_score=60.0,
                expected_rpe_range=self.get_expected_rpe(WorkoutType.PROGRESSION_RUN, duration_min)
            )
        
        # Long run
        if 'long run' in name or 'long slow' in name or 'lsd' in name:
            return WorkoutClassification(
                workout_type=WorkoutType.LONG_RUN,
                workout_zone=WorkoutZone.ENDURANCE,
                confidence=0.85,
                reasoning=f"Name indicates long run: '{activity.name}'",
                detected_intervals=False,
                detected_progression=False,
                avg_hr_zone=2,
                intensity_score=45.0,
                expected_rpe_range=self.get_expected_rpe(WorkoutType.LONG_RUN, duration_min)
            )
        
        # Recovery
        # Use word boundary matching to avoid "easy" matching "uneasy" or similar
        recovery_keywords = ['recovery', 'easy run', 'easy jog', 'shake out', 'shakeout', 
                            'warm up', 'cool down', 'recovery run', 'easy effort']
        if any(_matches_keyword(kw, name) and not _has_negation_context(kw, name) 
               for kw in recovery_keywords):
            return WorkoutClassification(
                workout_type=WorkoutType.EASY_RUN,
                workout_zone=WorkoutZone.ENDURANCE,
                confidence=0.75,
                reasoning=f"Name indicates easy/recovery: '{activity.name}'",
                detected_intervals=False,
                detected_progression=False,
                avg_hr_zone=1,
                intensity_score=30.0,
                expected_rpe_range=self.get_expected_rpe(WorkoutType.EASY_RUN, duration_min)
            )
        
        # Marathon/race pace
        pace_keywords = ['marathon pace', 'mp run', 'race pace', 'goal pace', 'half marathon pace']
        if any(kw in name for kw in pace_keywords):
            return WorkoutClassification(
                workout_type=WorkoutType.MARATHON_PACE,
                workout_zone=WorkoutZone.RACE_SPECIFIC,
                confidence=0.80,
                reasoning=f"Name indicates race pace work: '{activity.name}'",
                detected_intervals=False,
                detected_progression=False,
                avg_hr_zone=3,
                intensity_score=65.0,
                expected_rpe_range=self.get_expected_rpe(WorkoutType.MARATHON_PACE, duration_min)
            )
        
        # No strong signal from name
        return None
    
    def _calculate_hr_zone(
        self, 
        avg_hr: Optional[int], 
        thresholds: AthleteThresholds
    ) -> Optional[int]:
        """
        Calculate approximate HR category (1-5) for INTERNAL use only.
        
        IMPORTANT: This is a rough categorization tool, NOT a physiological truth.
        The body operates on a continuous spectrum. These categories are for
        grouping similar efforts, not for athlete-facing "Zone X" displays.
        
        We use this internally to help classify workout types, not to tell
        athletes "you were in Zone 3".
        """
        if not avg_hr or not thresholds.max_hr:
            return None
        
        hr_pct = (avg_hr / thresholds.max_hr) * 100
        
        # Rough categories - remember these shift based on fatigue, heat, sleep, etc.
        if hr_pct < 72:
            return 1  # Very easy
        elif hr_pct < 81:
            return 2  # Easy/aerobic
        elif hr_pct < 88:
            return 3  # Moderate/threshold region
        elif hr_pct < 92:
            return 4  # Hard
        else:
            return 5  # Very hard
    
    def _calculate_intensity(
        self,
        avg_pace_per_km: Optional[float],
        avg_hr: Optional[int],
        thresholds: AthleteThresholds,
        max_hr: Optional[int] = None
    ) -> float:
        """
        Calculate intensity score 0-100.
        
        Now considers max_hr in addition to avg_hr:
        - High max_hr relative to avg_hr indicates hard efforts/finishes
        - This prevents runs with moderate avg_hr but hard efforts from being
          classified as "easy"
        """
        scores = []

        # HR-based intensity
        if avg_hr and thresholds.max_hr:
            hr_pct = (avg_hr / thresholds.max_hr) * 100
            # Map 60-100% HR to 0-100 intensity
            hr_intensity = max(0, min(100, (hr_pct - 60) * 2.5))
            scores.append(hr_intensity)
            
            # Boost intensity if max_hr significantly exceeds avg_hr
            # This catches progression runs, hard finishes, fartlek patterns
            if max_hr and avg_hr:
                hr_spread = (max_hr - avg_hr) / avg_hr if avg_hr > 0 else 0
                # If max_hr is 15%+ above avg, this wasn't a truly easy run
                if hr_spread > 0.15:  # e.g., avg 140, max 161+
                    # Add intensity boost based on how high max went
                    max_hr_pct = (max_hr / thresholds.max_hr) * 100
                    if max_hr_pct > 85:  # Max HR hit threshold zone
                        boost = min(20, (max_hr_pct - 85) * 2)  # Up to 20 point boost
                        hr_intensity = min(100, hr_intensity + boost)
                        scores[-1] = hr_intensity  # Update the HR intensity

        # Pace-based intensity (if we have threshold pace)
        if avg_pace_per_km and thresholds.threshold_pace_per_km:
            # Faster than threshold = higher intensity
            pace_ratio = avg_pace_per_km / thresholds.threshold_pace_per_km
            # Threshold = 70 intensity, Easy = 30, Race = 90+
            pace_intensity = 100 - (pace_ratio - 0.8) * 200
            pace_intensity = max(0, min(100, pace_intensity))
            scores.append(pace_intensity)

        return sum(scores) / len(scores) if scores else 50.0
    
    def _detect_hard_finish(self, activity: Activity) -> bool:
        """
        Detect if activity had a hard finish based on HR spread.
        
        A "hard finish" is when max_hr significantly exceeds avg_hr,
        indicating the athlete pushed hard at the end even if the
        overall average looks moderate.
        """
        if not activity.avg_hr or not activity.max_hr:
            return False
        
        avg_hr = activity.avg_hr
        max_hr = activity.max_hr
        
        # Calculate HR spread
        hr_spread = (max_hr - avg_hr) / avg_hr if avg_hr > 0 else 0
        
        # If max is 15%+ above average AND max > 160, it was a hard finish
        return hr_spread > 0.15 and max_hr > 160
    
    def _detect_intervals(self, activity: Activity) -> Tuple[bool, int, float]:
        """
        Detect if activity has interval pattern from splits data.
        
        Returns:
            (is_intervals, num_work_segments, avg_work_duration_min)
        """
        # Handle dynamic relationship - need to convert to list
        splits = list(activity.splits) if activity.splits else []
        if len(splits) < 4:
            return (False, 0, 0.0)
        
        # Get pace for each split
        # ActivitySplit uses: distance (meters), moving_time (seconds)
        paces = []
        for split in splits:
            distance = float(split.distance) if split.distance else None
            moving_time = split.moving_time or split.elapsed_time
            
            if distance and distance > 0 and moving_time:
                pace_per_km = (moving_time / distance) * 1000
                paces.append((pace_per_km, moving_time))
        
        if len(paces) < 4:
            return (False, 0, 0.0)
        
        # Calculate pace variance (coefficient of variation)
        pace_values = [p[0] for p in paces]
        mean_pace = sum(pace_values) / len(pace_values)
        variance = sum((p - mean_pace) ** 2 for p in pace_values) / len(pace_values)
        std_dev = math.sqrt(variance)
        cv = (std_dev / mean_pace) * 100 if mean_pace > 0 else 0
        
        # High variance suggests intervals (CV > 15%)
        if cv < 15:
            return (False, 0, 0.0)
        
        # Look for alternating fast/slow pattern
        # Fast = faster than mean, Slow = slower than mean
        work_segments = []
        current_work_duration = 0
        in_work = False
        
        for pace, duration in paces:
            is_fast = pace < mean_pace * 0.95  # 5% faster than mean
            
            if is_fast:
                if not in_work:
                    in_work = True
                    current_work_duration = duration
                else:
                    current_work_duration += duration
            else:
                if in_work:
                    work_segments.append(current_work_duration)
                    in_work = False
                    current_work_duration = 0
        
        # Don't forget last segment
        if in_work and current_work_duration > 0:
            work_segments.append(current_work_duration)
        
        # Need at least 3 work segments to call it intervals
        if len(work_segments) >= 3:
            avg_work_duration = sum(work_segments) / len(work_segments) / 60  # Convert to minutes
            return (True, len(work_segments), avg_work_duration)
        
        return (False, 0, 0.0)
    
    def _detect_progression(self, activity: Activity) -> bool:
        """
        Detect if activity has progression pattern (negative splits).

        Looks for consistently decreasing pace across the run.
        
        Enhanced detection for:
        1. "Each mile faster than the last" pattern
        2. Traditional negative split (last third faster than first)
        3. Hard finish pattern (significant acceleration in final splits)
        """
        # Handle dynamic relationship - need to convert to list
        splits = list(activity.splits) if activity.splits else []
        if len(splits) < 3:
            return False

        # Get pace for each split
        # ActivitySplit uses: distance (meters), moving_time (seconds)
        paces = []
        for split in splits:
            distance = float(split.distance) if split.distance else None
            moving_time = split.moving_time or split.elapsed_time

            if distance and distance > 0 and moving_time:
                pace_per_km = (moving_time / distance) * 1000
                paces.append(pace_per_km)

        if len(paces) < 3:
            return False

        # PATTERN 1: "Each mile faster" - strong progression
        # Count how many consecutive splits are faster than previous
        consecutive_faster = 0
        max_consecutive = 0
        for i in range(1, len(paces)):
            if paces[i] < paces[i-1]:
                consecutive_faster += 1
                max_consecutive = max(max_consecutive, consecutive_faster)
            else:
                consecutive_faster = 0
        
        # If most splits (70%+) are consecutively faster, it's a clear progression
        if max_consecutive >= len(paces) * 0.7:
            return True
        
        # PATTERN 2: Traditional negative split
        # Compare first third to last third
        third = len(paces) // 3
        if third < 1:
            third = 1

        first_third_avg = sum(paces[:third]) / third
        last_third_avg = sum(paces[-third:]) / third

        # Last third should be at least 5% faster than first third
        if last_third_avg < first_third_avg * 0.95:
            # Check for general downward trend
            decreasing_count = sum(1 for i in range(1, len(paces)) if paces[i] < paces[i-1])
            if decreasing_count >= len(paces) * 0.5:
                return True
        
        # PATTERN 3: Hard finish - last split(s) significantly faster
        # Even without overall progression, a big acceleration at end signals quality
        if len(paces) >= 3:
            last_pace = paces[-1]
            avg_early = sum(paces[:-1]) / (len(paces) - 1)
            # Last split 10%+ faster than rest = hard finish/progression
            if last_pace < avg_early * 0.90:
                return True

        return False
    
    def _classify_race(
        self, 
        activity: Activity, 
        thresholds: AthleteThresholds
    ) -> WorkoutClassification:
        """Classify a race activity"""
        duration_min = (activity.duration_s or 0) / 60
        expected_rpe = self.get_expected_rpe(WorkoutType.RACE, duration_min)
        
        return WorkoutClassification(
            workout_type=WorkoutType.RACE,
            workout_zone=WorkoutZone.RACE_SPECIFIC,
            confidence=0.9 if activity.user_verified_race else 0.7,
            reasoning="Activity marked as race" if activity.user_verified_race else "High effort race candidate",
            detected_intervals=False,
            detected_progression=False,
            avg_hr_zone=5,
            intensity_score=95.0,
            expected_rpe_range=expected_rpe
        )
    
    def _classify_interval_workout(
        self,
        activity: Activity,
        thresholds: AthleteThresholds,
        hr_zone: Optional[int],
        intensity_score: float,
        num_intervals: int = 0,
        avg_interval_duration: float = 0.0
    ) -> WorkoutClassification:
        """Classify an interval workout"""
        duration_min = (activity.duration_s or 0) / 60
        
        # Based on intensity and interval structure, classify type
        if intensity_score > 85:
            workout_type = WorkoutType.VO2MAX_INTERVALS
            zone = WorkoutZone.SPEED
        elif intensity_score > 70:
            workout_type = WorkoutType.TEMPO_INTERVALS
            zone = WorkoutZone.STAMINA
        else:
            workout_type = WorkoutType.FARTLEK
            zone = WorkoutZone.MIXED
        
        # Build reasoning with structure info
        if num_intervals > 0 and avg_interval_duration > 0:
            reasoning = f"Interval pattern detected: ~{num_intervals} × {avg_interval_duration:.1f} min"
        else:
            reasoning = f"Interval pattern detected, intensity {intensity_score:.0f}%"
        
        # Get expected RPE for this workout
        expected_rpe = self.get_expected_rpe(
            workout_type, duration_min, 
            is_intervals=True,
            num_intervals=num_intervals,
            avg_interval_duration=avg_interval_duration
        )
        
        return WorkoutClassification(
            workout_type=workout_type,
            workout_zone=zone,
            confidence=0.7,
            reasoning=reasoning,
            detected_intervals=True,
            detected_progression=False,
            avg_hr_zone=hr_zone,
            intensity_score=intensity_score,
            expected_rpe_range=expected_rpe,
            work_segments=num_intervals,
            avg_work_duration_min=avg_interval_duration
        )
    
    def _classify_progression(
        self,
        activity: Activity,
        thresholds: AthleteThresholds,
        hr_zone: Optional[int],
        intensity_score: float
    ) -> WorkoutClassification:
        """Classify a progression run"""
        distance_km = (activity.distance_m or 0) / 1000
        duration_min = (activity.duration_s or 0) / 60

        if distance_km > 25:
            workout_type = WorkoutType.FAST_FINISH_LONG
        else:
            workout_type = WorkoutType.PROGRESSION_RUN

        expected_rpe = self.get_expected_rpe(workout_type, duration_min)
        
        # Build reasoning with HR context
        reasoning = "Negative split pattern detected — pace increased throughout"
        
        # Add HR context if we have max vs avg spread
        if activity.avg_hr and activity.max_hr:
            hr_spread_pct = ((activity.max_hr - activity.avg_hr) / activity.avg_hr) * 100
            if hr_spread_pct > 15:
                reasoning += f" (max HR {activity.max_hr} vs avg {activity.avg_hr} shows hard finish)"

        return WorkoutClassification(
            workout_type=workout_type,
            workout_zone=WorkoutZone.MIXED,
            confidence=0.80,  # Higher confidence with enhanced detection
            reasoning=reasoning,
            detected_intervals=False,
            detected_progression=True,
            avg_hr_zone=hr_zone,
            intensity_score=intensity_score,
            expected_rpe_range=expected_rpe
        )
    
    def _classify_steady_state(
        self,
        activity: Activity,
        thresholds: AthleteThresholds,
        hr_zone: Optional[int],
        intensity_score: float,
        duration_min: float
    ) -> WorkoutClassification:
        """Classify a steady-state run based on intensity and duration"""
        distance_km = (activity.distance_m or 0) / 1000
        
        # Long run threshold (varies by fitness, but use 90+ min or 20+ km)
        is_long = duration_min > 90 or distance_km > 20
        is_medium_long = duration_min > 60 or distance_km > 14
        
        # Classification by intensity zones
        if intensity_score < 30:
            workout_type = WorkoutType.RECOVERY_RUN
            zone = WorkoutZone.RECOVERY
            reasoning = "Very low intensity recovery run"
        elif intensity_score < 45:
            if is_long:
                workout_type = WorkoutType.LONG_RUN
                zone = WorkoutZone.ENDURANCE
                reasoning = f"Long run at easy effort ({distance_km:.1f}km)"
            elif is_medium_long:
                workout_type = WorkoutType.MEDIUM_LONG_RUN
                zone = WorkoutZone.ENDURANCE
                reasoning = f"Medium-long run ({distance_km:.1f}km)"
            else:
                workout_type = WorkoutType.EASY_RUN
                zone = WorkoutZone.ENDURANCE
                reasoning = "Easy aerobic run"
        elif intensity_score < 60:
            if is_long:
                workout_type = WorkoutType.LONG_RUN
                zone = WorkoutZone.ENDURANCE
                reasoning = f"Long run at moderate effort ({distance_km:.1f}km)"
            else:
                workout_type = WorkoutType.AEROBIC_RUN
                zone = WorkoutZone.ENDURANCE
                reasoning = "Moderate aerobic run"
        elif intensity_score < 75:
            if duration_min > 40:
                workout_type = WorkoutType.MARATHON_PACE
                zone = WorkoutZone.RACE_SPECIFIC
                reasoning = "Sustained marathon pace effort"
            else:
                workout_type = WorkoutType.TEMPO_RUN
                zone = WorkoutZone.STAMINA
                reasoning = "Threshold/tempo effort"
        elif intensity_score < 85:
            workout_type = WorkoutType.THRESHOLD_RUN
            zone = WorkoutZone.STAMINA
            reasoning = "Hard threshold effort"
        else:
            workout_type = WorkoutType.TRACK_WORKOUT
            zone = WorkoutZone.SPEED
            reasoning = "High intensity speed workout"
        
        # Get expected RPE for this workout type and duration
        expected_rpe = self.get_expected_rpe(workout_type, duration_min, is_intervals=False)
        
        return WorkoutClassification(
            workout_type=workout_type,
            workout_zone=zone,
            confidence=0.6,  # Lower for steady-state (harder to distinguish)
            reasoning=reasoning,
            detected_intervals=False,
            detected_progression=False,
            avg_hr_zone=hr_zone,
            intensity_score=intensity_score,
            expected_rpe_range=expected_rpe
        )
    
    def get_workout_type_description(self, workout_type: WorkoutType) -> str:
        """Get human-readable description of workout type"""
        descriptions = {
            WorkoutType.RECOVERY_RUN: "Easy recovery run to promote blood flow",
            WorkoutType.EASY_RUN: "Comfortable aerobic run for base building",
            WorkoutType.LONG_RUN: "Extended endurance run for aerobic development",
            WorkoutType.MEDIUM_LONG_RUN: "Mid-week endurance builder",
            WorkoutType.TEMPO_RUN: "Sustained threshold effort",
            WorkoutType.TEMPO_INTERVALS: "Threshold intervals with short recovery",
            WorkoutType.VO2MAX_INTERVALS: "High intensity intervals for aerobic power",
            WorkoutType.FARTLEK: "Flexible speed play with varied efforts",
            WorkoutType.MARATHON_PACE: "Race-specific marathon pace practice",
            WorkoutType.PROGRESSION_RUN: "Run that builds from easy to fast",
            WorkoutType.FAST_FINISH_LONG: "Long run with race-pace finish",
            WorkoutType.RACE: "Competition or time trial",
        }
        return descriptions.get(workout_type, "Training run")
    
    @staticmethod
    def get_intensity_description(intensity_score: float) -> str:
        """
        Get athlete-friendly intensity description.
        
        This is what we show instead of "Zone X" - honest about the spectrum.
        """
        if intensity_score < 25:
            return "Very Easy"
        elif intensity_score < 45:
            return "Easy"
        elif intensity_score < 60:
            return "Moderate"
        elif intensity_score < 75:
            return "Moderately Hard"
        elif intensity_score < 85:
            return "Hard"
        elif intensity_score < 95:
            return "Very Hard"
        else:
            return "Maximum"
    
    @staticmethod
    def get_intensity_color(intensity_score: float) -> str:
        """Get color code for intensity display."""
        if intensity_score < 30:
            return "gray"
        elif intensity_score < 50:
            return "green"
        elif intensity_score < 70:
            return "orange"
        elif intensity_score < 85:
            return "red"
        else:
            return "purple"
    
    @staticmethod
    def get_expected_rpe(
        workout_type: WorkoutType,
        duration_min: float,
        is_intervals: bool = False,
        num_intervals: int = 0,
        avg_interval_duration: float = 0.0
    ) -> Tuple[int, int]:
        """
        Get expected RPE (Rate of Perceived Exertion) range (1-10) for a workout.
        
        RPE is the standard scale runners recognize for subjective effort.
        This models how hard a workout SHOULD feel based on type and structure.
        The gap between expected RPE and actual RPE is a training signal.
        
        Returns:
            (min_expected_rpe, max_expected_rpe)
        """
        # Recovery/Easy - should feel easy regardless of duration
        if workout_type in [WorkoutType.RECOVERY_RUN, WorkoutType.EASY_RUN, WorkoutType.SHAKEOUT]:
            return (2, 4)
        
        # Long runs - duration matters
        if workout_type in [WorkoutType.LONG_RUN, WorkoutType.MEDIUM_LONG_RUN]:
            if duration_min < 75:
                return (4, 5)
            elif duration_min < 100:
                return (5, 6)
            elif duration_min < 130:
                return (6, 7)
            else:
                return (7, 8)
        
        # Fast finish / progression long run
        if workout_type == WorkoutType.FAST_FINISH_LONG:
            return (7, 8)
        
        # Aerobic run
        if workout_type == WorkoutType.AEROBIC_RUN:
            return (4, 5)
        
        # Threshold/Tempo - structure matters A LOT
        if workout_type in [WorkoutType.TEMPO_RUN, WorkoutType.THRESHOLD_RUN]:
            if is_intervals:
                # Intervals are more manageable
                if avg_interval_duration < 5:
                    return (6, 7)
                elif avg_interval_duration < 10:
                    return (7, 8)
                else:
                    return (7, 9)
            else:
                # Continuous is much harder
                if duration_min < 20:
                    return (6, 7)
                elif duration_min < 30:
                    return (7, 8)
                elif duration_min < 40:
                    return (8, 9)
                else:
                    return (9, 10)  # Race-like
        
        if workout_type in [WorkoutType.TEMPO_INTERVALS, WorkoutType.CRUISE_INTERVALS]:
            if avg_interval_duration < 5:
                return (6, 7)
            elif avg_interval_duration < 8:
                return (6, 7)
            else:
                return (7, 8)
        
        # VO2max intervals
        if workout_type == WorkoutType.VO2MAX_INTERVALS:
            if avg_interval_duration < 2:
                return (6, 7)
            elif avg_interval_duration < 4:
                return (7, 8)
            else:
                return (8, 9)
        
        # Track/speed work
        if workout_type == WorkoutType.TRACK_WORKOUT:
            return (7, 8)
        
        # Repetitions (short, fast, full recovery)
        if workout_type in [WorkoutType.REPETITIONS, WorkoutType.STRIDES]:
            return (5, 6)
        
        # Hill work
        if workout_type in [WorkoutType.HILL_SPRINTS, WorkoutType.HILL_REPETITIONS]:
            return (7, 8)
        
        # Fartlek (variable)
        if workout_type == WorkoutType.FARTLEK:
            return (6, 7)
        
        # Marathon/race pace
        if workout_type in [WorkoutType.MARATHON_PACE, WorkoutType.HALF_MARATHON_PACE, WorkoutType.GOAL_PACE_RUN]:
            if duration_min < 30:
                return (5, 6)
            elif duration_min < 60:
                return (6, 7)
            else:
                return (7, 8)
        
        # Progression run
        if workout_type == WorkoutType.PROGRESSION_RUN:
            return (6, 7)
        
        # Race
        if workout_type in [WorkoutType.RACE, WorkoutType.TUNE_UP_RACE, WorkoutType.RACE_SIMULATION]:
            return (9, 10)
        
        # Default
        return (5, 6)
    
    @staticmethod
    def analyze_rpe_gap(
        actual_rpe: int,
        expected_rpe_range: Tuple[int, int]
    ) -> Tuple[str, str]:
        """
        Analyze the gap between actual and expected RPE (Rate of Perceived Exertion).
        
        Returns:
            (status, message)
            status: 'normal', 'harder_than_expected', 'easier_than_expected'
        """
        min_rpe, max_rpe = expected_rpe_range
        
        if actual_rpe <= max_rpe + 1 and actual_rpe >= min_rpe - 1:
            return ('normal', 'RPE matched expectations')
        
        if actual_rpe > max_rpe + 1:
            gap = actual_rpe - max_rpe
            if gap >= 3:
                return ('harder_than_expected', 
                    'This felt significantly harder than expected. Check: fatigue, stress, sleep, nutrition, illness.')
            else:
                return ('harder_than_expected',
                    'This felt harder than expected. You may be carrying some fatigue.')
        
        if actual_rpe < min_rpe - 1:
            gap = min_rpe - actual_rpe
            if gap >= 2:
                return ('easier_than_expected',
                    'This felt much easier than expected. Great sign of fitness improvement!')
            else:
                return ('easier_than_expected',
                    'This felt easier than expected. You were well recovered or conditions were favorable.')
        
        return ('normal', 'RPE within expected range')


