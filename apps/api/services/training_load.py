"""
Training Load Calculator

Calculates training stress metrics:
- TSS (Training Stress Score) per workout
- ATL (Acute Training Load) - fatigue (7-day rolling)
- CTL (Chronic Training Load) - fitness (42-day rolling)
- TSB (Training Stress Balance) - form (CTL - ATL)

These metrics help understand:
- Is the athlete building fitness?
- Are they accumulating too much fatigue?
- Are they fresh enough for a race?

Design Philosophy:
- Use data we have (HR, pace, duration) rather than requiring power data
- Reasonable defaults when data is incomplete
- Transparent about assumptions

ADR-010: Training Stress Balance Enhancement
"""

from datetime import datetime, timedelta, date
from typing import List, Dict, Optional
from uuid import UUID
from dataclasses import dataclass
from enum import Enum
from sqlalchemy.orm import Session
import math
import logging

from models import Activity, Athlete

logger = logging.getLogger(__name__)


class TSBZone(str, Enum):
    """Training Stress Balance zones for actionable insights."""
    RACE_READY = "race_ready"           # Fresh & fit - personalized threshold
    RECOVERING = "recovering"            # Final taper zone
    OPTIMAL_TRAINING = "optimal_training"  # Normal productive training
    OVERREACHING = "overreaching"        # High fatigue FOR THIS ATHLETE
    OVERTRAINING_RISK = "overtraining_risk"  # Unusual fatigue - red zone


@dataclass
class TSBZoneInfo:
    """Information about a TSB zone."""
    zone: TSBZone
    label: str
    description: str
    color: str  # For UI display
    is_race_window: bool


@dataclass
class PersonalTSBProfile:
    """
    Athlete's personalized TSB distribution.
    
    This is true N=1: zones are defined relative to this athlete's
    historical TSB, not population norms.
    
    A marathoner who routinely trains at TSB -20 has different
    "overreaching" threshold than a casual runner at TSB +5.
    """
    athlete_id: UUID
    mean_tsb: float
    std_tsb: float
    min_tsb: float
    max_tsb: float
    sample_days: int  # Number of days with data
    
    # Personalized zone thresholds (calculated from distribution)
    threshold_fresh: float      # Above this = unusually fresh (mean + 1.5 SD)
    threshold_recovering: float # Above this = fresher than normal (mean + 0.75 SD)
    threshold_normal_low: float # Below this = more fatigued than normal (mean - 1 SD)
    threshold_danger: float     # Below this = unusually fatigued (mean - 2 SD)
    
    is_sufficient_data: bool    # >= 56 days (8 weeks) of history
    
    @classmethod
    def from_tsb_history(
        cls,
        athlete_id: UUID,
        tsb_values: List[float],
        min_days: int = 56,  # 8 weeks minimum for reliable stats
        trim_percentile: float = 5.0  # Trim top/bottom 5% for outlier resistance
    ) -> "PersonalTSBProfile":
        """
        Calculate personal TSB profile from historical TSB values.

        Zone definitions (relative to personal distribution):
        - RACE_READY: > mean + 1.5 SD (unusually fresh for you)
        - RECOVERING: mean + 0.75 SD to mean + 1.5 SD (fresher than normal)
        - OPTIMAL_TRAINING: mean - 1 SD to mean + 0.75 SD (your normal range)
        - OVERREACHING: mean - 2 SD to mean - 1 SD (more fatigued than usual)
        - OVERTRAINING_RISK: < mean - 2 SD (unusually fatigued - investigate)
        
        Uses TRIMMED mean and SD to reduce sensitivity to outliers
        (e.g., injury recovery periods, extended rest).
        """
        n = len(tsb_values)

        if n < min_days:
            # Insufficient data - return profile with population defaults
            return cls(
                athlete_id=athlete_id,
                mean_tsb=-5.0,  # Population average
                std_tsb=15.0,   # Population SD estimate
                min_tsb=-30.0,
                max_tsb=25.0,
                sample_days=n,
                threshold_fresh=17.5,      # -5 + 1.5*15 = 17.5
                threshold_recovering=6.25, # -5 + 0.75*15 = 6.25
                threshold_normal_low=-20.0, # -5 - 1*15 = -20
                threshold_danger=-35.0,    # -5 - 2*15 = -35
                is_sufficient_data=False
            )

        # Use trimmed mean/SD for outlier resistance
        # Sort values and exclude top/bottom 5%
        sorted_values = sorted(tsb_values)
        trim_count = max(1, int(n * trim_percentile / 100))
        
        if n > 2 * trim_count:
            # Enough data to trim
            trimmed_values = sorted_values[trim_count:-trim_count]
        else:
            # Not enough data to trim, use all values
            trimmed_values = sorted_values
        
        # Calculate trimmed statistics
        trimmed_n = len(trimmed_values)
        mean = sum(trimmed_values) / trimmed_n
        variance = sum((x - mean) ** 2 for x in trimmed_values) / trimmed_n
        std = math.sqrt(variance) if variance > 0 else 10.0

        # Enforce minimum SD to avoid overly narrow zones
        std = max(std, 8.0)
        
        return cls(
            athlete_id=athlete_id,
            mean_tsb=round(mean, 1),
            std_tsb=round(std, 1),
            min_tsb=round(min(tsb_values), 1),
            max_tsb=round(max(tsb_values), 1),
            sample_days=n,
            threshold_fresh=round(mean + 1.5 * std, 1),
            threshold_recovering=round(mean + 0.75 * std, 1),
            threshold_normal_low=round(mean - 1.0 * std, 1),
            threshold_danger=round(mean - 2.0 * std, 1),
            is_sufficient_data=True
        )
    
    def get_zone(self, tsb: float) -> TSBZone:
        """
        Classify a TSB value into a zone based on THIS athlete's personal thresholds.
        """
        if tsb >= self.threshold_fresh:
            return TSBZone.RACE_READY
        elif tsb >= self.threshold_recovering:
            return TSBZone.RECOVERING
        elif tsb >= self.threshold_normal_low:
            return TSBZone.OPTIMAL_TRAINING
        elif tsb >= self.threshold_danger:
            return TSBZone.OVERREACHING
        else:
            return TSBZone.OVERTRAINING_RISK
    
    def get_zone_info(self, tsb: float) -> TSBZoneInfo:
        """
        Get full zone info with personalized description.
        """
        zone = self.get_zone(tsb)
        
        # Calculate how many SDs from mean
        sds_from_mean = (tsb - self.mean_tsb) / self.std_tsb if self.std_tsb > 0 else 0
        
        if zone == TSBZone.RACE_READY:
            return TSBZoneInfo(
                zone=zone,
                label="Fresh for You",
                description=f"TSB {tsb:+.0f} is unusually fresh (>{self.threshold_fresh:+.0f} is your race-ready zone)",
                color="green",
                is_race_window=True
            )
        elif zone == TSBZone.RECOVERING:
            return TSBZoneInfo(
                zone=zone,
                label="Recovering",
                description=f"TSB {tsb:+.0f} — fresher than your typical training state",
                color="blue",
                is_race_window=False
            )
        elif zone == TSBZone.OPTIMAL_TRAINING:
            return TSBZoneInfo(
                zone=zone,
                label="Normal Training",
                description=f"TSB {tsb:+.0f} — within your typical training range ({self.threshold_normal_low:+.0f} to {self.threshold_recovering:+.0f})",
                color="yellow",
                is_race_window=False
            )
        elif zone == TSBZone.OVERREACHING:
            return TSBZoneInfo(
                zone=zone,
                label="Fatigued for You",
                description=f"TSB {tsb:+.0f} is below your normal range — more fatigued than usual",
                color="orange",
                is_race_window=False
            )
        else:  # OVERTRAINING_RISK
            return TSBZoneInfo(
                zone=zone,
                label="Unusually Fatigued",
                description=f"TSB {tsb:+.0f} is {abs(sds_from_mean):.1f} SDs below your mean — investigate",
                color="red",
                is_race_window=False
            )


@dataclass
class RaceReadiness:
    """Race readiness assessment."""
    score: float  # 0-100
    tsb: float
    tsb_zone: TSBZone
    tsb_trend: str
    days_since_hard_workout: Optional[int]
    recommendation: str
    is_race_window: bool


@dataclass
class WorkoutStress:
    """Stress score for a single workout"""
    activity_id: UUID
    date: date
    tss: float  # Training Stress Score (0-300+ typical range)
    duration_minutes: float
    intensity_factor: float  # Relative intensity (0-1.2+)
    calculation_method: str  # "hrTSS", "rTSS", "estimated"


@dataclass
class DailyLoad:
    """Daily training load summary"""
    date: date
    total_tss: float
    workout_count: int
    atl: float  # Acute Training Load (fatigue)
    ctl: float  # Chronic Training Load (fitness)
    tsb: float  # Training Stress Balance (form)


@dataclass
class LoadSummary:
    """Training load summary for an athlete"""
    current_atl: float
    current_ctl: float
    current_tsb: float
    atl_trend: str  # "rising", "falling", "stable"
    ctl_trend: str
    tsb_trend: str
    training_phase: str  # "building", "maintaining", "tapering", "recovering"
    recommendation: str


class TrainingLoadCalculator:
    """
    Calculates training load metrics using available data.
    
    Prioritizes:
    1. Heart Rate TSS (hrTSS) if HR data available
    2. Running TSS (rTSS) if pace and threshold pace known
    3. Estimated TSS based on duration/intensity heuristics
    """
    
    # Constants for exponential decay
    ATL_DECAY_DAYS = 7  # Acute (fatigue) - short term
    CTL_DECAY_DAYS = 42  # Chronic (fitness) - long term
    
    def __init__(self, db: Session):
        self.db = db
    
    # =========================================================================
    # TSS CALCULATION
    # =========================================================================
    
    def calculate_workout_tss(
        self, 
        activity: Activity, 
        athlete: Athlete
    ) -> WorkoutStress:
        """
        Calculate TSS for a single workout.
        Uses best available method based on data.
        """
        duration_s = activity.duration_s or 0
        duration_minutes = duration_s / 60
        
        if duration_minutes < 5:
            return WorkoutStress(
                activity_id=activity.id,
                date=activity.start_time.date(),
                tss=0,
                duration_minutes=duration_minutes,
                intensity_factor=0,
                calculation_method="too_short"
            )
        
        # Try hrTSS first (most accurate for running)
        # Use N=1 observed peak + resting HR from effort thresholds when athlete.max_hr is missing
        from services.effort_classification import get_effort_thresholds
        et = get_effort_thresholds(str(athlete.id), self.db)
        peak = et.get("observed_peak_hr")
        resting = et.get("resting_hr")
        can_hr_tss = activity.avg_hr and peak and resting and et.get("tier") == "hrr"
        if can_hr_tss:
            return self._calculate_hr_tss_from_thresholds(activity, peak, resting, duration_minutes)
        if activity.avg_hr and athlete.max_hr and athlete.resting_hr:
            return self._calculate_hr_tss(activity, athlete, duration_minutes)
        
        # Try rTSS if we have pace data
        if (activity.distance_m and activity.distance_m > 0 and 
            duration_s > 0 and athlete.threshold_pace_per_km):
            return self._calculate_running_tss(activity, athlete, duration_minutes)
        
        # Fall back to estimated TSS
        return self._estimate_tss(activity, athlete, duration_minutes)
    
    def _calculate_hr_tss(
        self, 
        activity: Activity, 
        athlete: Athlete,
        duration_minutes: float
    ) -> WorkoutStress:
        """
        Calculate HR-based TSS (hrTSS).
        
        Formula:
        hrTSS = (duration_min * TRIMP) / (60 * LTHR_TRIMP)
        
        Where TRIMP = duration * HR_zone_factor
        """
        avg_hr = activity.avg_hr
        max_hr = athlete.max_hr
        resting_hr = athlete.resting_hr
        
        # Calculate HR Reserve percentage
        hr_reserve = (avg_hr - resting_hr) / (max_hr - resting_hr)
        hr_reserve = max(0, min(1.1, hr_reserve))  # Cap at 110%
        
        # TRIMP-based intensity factor (exponential weighting for higher HR)
        # Male: 0.64 * e^(1.92 * HRR), Female: 0.86 * e^(1.67 * HRR)
        # Using average for simplicity
        trimp_factor = 0.75 * math.exp(1.8 * hr_reserve)
        
        # Normalized to threshold HR (assume threshold at ~88% HRR)
        threshold_trimp = 0.75 * math.exp(1.8 * 0.88)
        
        # TSS calculation
        intensity_factor = trimp_factor / threshold_trimp
        tss = (duration_minutes * intensity_factor ** 2) / 60 * 100
        
        return WorkoutStress(
            activity_id=activity.id,
            date=activity.start_time.date(),
            tss=round(tss, 1),
            duration_minutes=duration_minutes,
            intensity_factor=round(intensity_factor, 3),
            calculation_method="hrTSS"
        )
    
    def _calculate_hr_tss_from_thresholds(
        self,
        activity: Activity,
        observed_peak: int,
        resting_hr: int,
        duration_minutes: float
    ) -> WorkoutStress:
        """hrTSS using N=1 observed peak and resting HR instead of athlete.max_hr."""
        avg_hr = activity.avg_hr
        hr_reserve = (avg_hr - resting_hr) / (observed_peak - resting_hr)
        hr_reserve = max(0, min(1.1, hr_reserve))
        trimp_factor = 0.75 * math.exp(1.8 * hr_reserve)
        threshold_trimp = 0.75 * math.exp(1.8 * 0.88)
        intensity_factor = trimp_factor / threshold_trimp
        tss = (duration_minutes * intensity_factor ** 2) / 60 * 100
        return WorkoutStress(
            activity_id=activity.id,
            date=activity.start_time.date(),
            tss=round(tss, 1),
            duration_minutes=duration_minutes,
            intensity_factor=round(intensity_factor, 3),
            calculation_method="hrTSS_n1"
        )

    def _calculate_running_tss(
        self, 
        activity: Activity, 
        athlete: Athlete,
        duration_minutes: float
    ) -> WorkoutStress:
        """
        Calculate running TSS (rTSS) based on pace.
        
        Formula:
        rTSS = (duration_sec * NGP * IF) / (FTP * 36)
        
        Where:
        - NGP = Normalized Graded Pace (accounting for elevation)
        - IF = Intensity Factor = NGP / Threshold Pace
        - FTP = Functional Threshold Pace
        """
        # Calculate actual pace (sec/km)
        distance_km = activity.distance_m / 1000
        pace_per_km = (activity.duration_s or 0) / distance_km
        
        # Simple NGP (would need grade adjustment for hills)
        ngp = pace_per_km
        
        # Get threshold pace (sec/km)
        threshold_pace = athlete.threshold_pace_per_km
        
        # Intensity factor (inverted since lower pace = faster = harder)
        # IF = threshold / actual (so faster = higher IF)
        intensity_factor = threshold_pace / ngp if ngp > 0 else 0
        intensity_factor = max(0.5, min(1.5, intensity_factor))  # Reasonable bounds
        
        # rTSS calculation
        tss = (duration_minutes * intensity_factor ** 2) / 60 * 100
        
        return WorkoutStress(
            activity_id=activity.id,
            date=activity.start_time.date(),
            tss=round(tss, 1),
            duration_minutes=duration_minutes,
            intensity_factor=round(intensity_factor, 3),
            calculation_method="rTSS"
        )
    
    def _estimate_tss(
        self, 
        activity: Activity, 
        athlete: Athlete,
        duration_minutes: float
    ) -> WorkoutStress:
        """
        Estimate TSS when we lack HR or pace data.
        Uses duration and rough intensity heuristics.
        """
        # Default intensity assumptions
        # Easy run: IF ~0.7, Moderate: IF ~0.85, Hard: IF ~0.95
        
        # Use workout name or default to moderate
        workout_type = getattr(activity, 'workout_type', '') or ""
        name = getattr(activity, 'name', '') or ""
        workout_type = workout_type.lower()
        name = name.lower()
        
        if any(word in name for word in ["race", "competition", "pr", "pb"]):
            intensity_factor = 1.0
        elif any(word in name for word in ["tempo", "threshold", "hard"]):
            intensity_factor = 0.9
        elif any(word in name for word in ["interval", "speed", "track"]):
            intensity_factor = 0.95
        elif any(word in name for word in ["easy", "recovery", "jog"]):
            intensity_factor = 0.65
        elif any(word in name for word in ["long run", "long"]):
            intensity_factor = 0.75
        else:
            # Default moderate
            intensity_factor = 0.78
        
        # TSS estimate
        tss = (duration_minutes * intensity_factor ** 2) / 60 * 100
        
        return WorkoutStress(
            activity_id=activity.id,
            date=activity.start_time.date(),
            tss=round(tss, 1),
            duration_minutes=duration_minutes,
            intensity_factor=round(intensity_factor, 3),
            calculation_method="estimated"
        )
    
    # =========================================================================
    # ATL / CTL / TSB CALCULATION — SINGLE-PASS EMA
    # =========================================================================

    def compute_training_state_history(
        self,
        athlete_id: UUID,
        target_dates: Optional[List[date]] = None,
    ) -> Dict[date, LoadSummary]:
        """
        Single-pass EMA from athlete's first activity to last.

        Walks all activities chronologically, computes daily TSS,
        applies ATL/CTL EMA on every day (including rest days).
        Returns LoadSummary at each requested target_date.

        If target_dates is None, returns values at every day
        (useful for charting full history).

        Excludes duplicate activities (is_duplicate == True).
        """

        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            raise ValueError(f"Athlete {athlete_id} not found")

        activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.is_duplicate == False,  # noqa: E712
        ).order_by(Activity.start_time).all()

        if not activities:
            if target_dates:
                return {d: self._empty_load_summary() for d in target_dates}
            return {}

        first_date = activities[0].start_time.date()
        last_date = activities[-1].start_time.date()

        target_set = set(target_dates) if target_dates else None
        end_date = date.today()
        if target_set:
            end_date = max(end_date, max(target_set))
        end_date = max(end_date, last_date)

        daily_tss: Dict[date, float] = {}
        daily_counts: Dict[date, int] = {}
        for act in activities:
            stress = self.calculate_workout_tss(act, athlete)
            d = stress.date
            daily_tss[d] = daily_tss.get(d, 0) + stress.tss
            daily_counts[d] = daily_counts.get(d, 0) + 1

        atl_alpha = 2 / (self.ATL_DECAY_DAYS + 1)
        ctl_alpha = 2 / (self.CTL_DECAY_DAYS + 1)

        current_atl = 0.0
        current_ctl = 0.0
        results: Dict[date, LoadSummary] = {}

        atl_history: List[float] = []
        ctl_history: List[float] = []

        total_days = (end_date - first_date).days + 1
        for i in range(total_days):
            current_date = first_date + timedelta(days=i)
            day_tss = daily_tss.get(current_date, 0)

            current_atl = current_atl * (1 - atl_alpha) + day_tss * atl_alpha
            current_ctl = current_ctl * (1 - ctl_alpha) + day_tss * ctl_alpha

            atl_history.append(current_atl)
            ctl_history.append(current_ctl)

            if target_set is None or current_date in target_set:
                current_tsb = current_ctl - current_atl

                atl_trend = self._calculate_trend(
                    atl_history[-14:-7] if len(atl_history) >= 14 else [],
                    atl_history[-7:] if len(atl_history) >= 7 else [],
                )
                ctl_trend = self._calculate_trend(
                    ctl_history[-14:-7] if len(ctl_history) >= 14 else [],
                    ctl_history[-7:] if len(ctl_history) >= 7 else [],
                )

                if atl_trend == "rising" and ctl_trend != "rising":
                    tsb_trend = "falling"
                elif atl_trend == "falling" and ctl_trend != "falling":
                    tsb_trend = "rising"
                else:
                    tsb_trend = "stable"

                training_phase = self._determine_training_phase(
                    current_atl, current_ctl, current_tsb, atl_trend, ctl_trend
                )
                recommendation = self._generate_recommendation(
                    current_atl, current_ctl, current_tsb, training_phase
                )

                results[current_date] = LoadSummary(
                    current_atl=round(current_atl, 1),
                    current_ctl=round(current_ctl, 1),
                    current_tsb=round(current_tsb, 1),
                    atl_trend=atl_trend,
                    ctl_trend=ctl_trend,
                    tsb_trend=tsb_trend,
                    training_phase=training_phase,
                    recommendation=recommendation,
                )

        return results

    def _empty_load_summary(self) -> LoadSummary:
        return LoadSummary(
            current_atl=0.0, current_ctl=0.0, current_tsb=0.0,
            atl_trend="stable", ctl_trend="stable", tsb_trend="stable",
            training_phase="recovering", recommendation="No data available.",
        )

    def calculate_training_load(
        self,
        athlete_id: UUID,
        target_date: Optional[date] = None
    ) -> LoadSummary:
        """
        Calculate current training load metrics for an athlete.
        Delegates to compute_training_state_history (full-history EMA).
        """
        from core.cache import get_cache, set_cache
        from dataclasses import asdict

        if target_date is None:
            target_date = date.today()
        _cache_key = f"training_load:{athlete_id}:{target_date.isoformat()}"
        _cached = get_cache(_cache_key)
        if _cached is not None:
            return LoadSummary(**_cached)

        results = self.compute_training_state_history(
            athlete_id, target_dates=[target_date]
        )
        result = results.get(target_date, self._empty_load_summary())
        set_cache(_cache_key, asdict(result), ttl=300)
        return result

    def get_load_history(
        self,
        athlete_id: UUID,
        days: int = 60
    ) -> List[DailyLoad]:
        """
        Get daily training load history for charting.
        Delegates to compute_training_state_history (full-history EMA).
        """
        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            return []

        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        target_dates = [start_date + timedelta(days=i) for i in range(days)]
        state = self.compute_training_state_history(athlete_id, target_dates=target_dates)

        activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.is_duplicate == False,  # noqa: E712
            Activity.start_time >= datetime.combine(start_date, datetime.min.time()),
            Activity.start_time < datetime.combine(end_date + timedelta(days=1), datetime.min.time()),
        ).order_by(Activity.start_time).all()

        daily_counts: Dict[date, int] = {}
        daily_tss_sums: Dict[date, float] = {}
        for act in activities:
            stress = self.calculate_workout_tss(act, athlete)
            d = stress.date
            daily_counts[d] = daily_counts.get(d, 0) + 1
            daily_tss_sums[d] = daily_tss_sums.get(d, 0) + stress.tss

        history: List[DailyLoad] = []
        for d in target_dates:
            load = state.get(d)
            if load:
                history.append(DailyLoad(
                    date=d,
                    total_tss=round(daily_tss_sums.get(d, 0), 1),
                    workout_count=daily_counts.get(d, 0),
                    atl=load.current_atl,
                    ctl=load.current_ctl,
                    tsb=load.current_tsb,
                ))
            else:
                history.append(DailyLoad(
                    date=d, total_tss=0, workout_count=0,
                    atl=0, ctl=0, tsb=0,
                ))

        return history
    
    def _calculate_trend(
        self, 
        old_values: List[float], 
        new_values: List[float]
    ) -> str:
        """Determine trend direction from two periods"""
        if not old_values or not new_values:
            return "stable"
        
        old_avg = sum(old_values) / len(old_values)
        new_avg = sum(new_values) / len(new_values)
        
        if old_avg == 0:
            return "rising" if new_avg > 0 else "stable"
        
        change_pct = (new_avg - old_avg) / old_avg
        
        if change_pct > 0.1:  # >10% increase
            return "rising"
        elif change_pct < -0.1:  # >10% decrease
            return "falling"
        else:
            return "stable"
    
    def _determine_training_phase(
        self,
        atl: float,
        ctl: float,
        tsb: float,
        atl_trend: str,
        ctl_trend: str
    ) -> str:
        """Determine current training phase"""
        # High fatigue, fitness building
        if atl_trend == "rising" and ctl_trend == "rising":
            return "building"
        
        # Low fatigue, high fitness, positive TSB
        if tsb > 10 and atl_trend != "rising":
            return "tapering"
        
        # Low everything
        if atl < 20 and ctl < 30:
            return "recovering"
        
        # Stable load
        if atl_trend == "stable" and ctl_trend == "stable":
            return "maintaining"
        
        return "building"  # Default
    
    def _generate_recommendation(
        self,
        atl: float,
        ctl: float,
        tsb: float,
        phase: str
    ) -> str:
        """Generate context-aware training recommendation"""
        # Note: These are observations, not prescriptions (manifesto compliance)
        
        if tsb < -20:
            return "High fatigue accumulation. Body may need recovery time."
        
        if tsb > 25 and phase == "tapering":
            return "Fresh and rested. Good window for a goal effort."
        
        if tsb > 15:
            return "Positive form. Could handle a harder session if planned."
        
        if atl > ctl * 1.3:
            return "Acute load significantly exceeds chronic. Monitor recovery closely."
        
        if phase == "building":
            return "Building phase. Fitness accumulating alongside fatigue."
        
        if phase == "recovering":
            return "Recovery phase. Base building opportunity if ready."
        
        return "Training load appears balanced."
    
    # =========================================================================
    # TSB ZONES AND RACE READINESS (ADR-010)
    # N=1 INDIVIDUALIZED ZONES
    # =========================================================================
    
    def get_personal_tsb_profile(
        self,
        athlete_id: UUID,
        lookback_days: int = 180  # 6 months of history
    ) -> PersonalTSBProfile:
        """
        Calculate athlete's personal TSB profile from their history.

        This is true N=1: zones are defined based on THIS athlete's
        historical TSB distribution, not population norms.

        Args:
            athlete_id: Athlete UUID
            lookback_days: How far back to look (default 6 months)

        Returns:
            PersonalTSBProfile with personalized zone thresholds
        """
        # Get load history
        history = self.get_load_history(athlete_id, days=lookback_days)

        if not history:
            # No history - return default profile
            logger.info(
                f"Personal TSB profile for {athlete_id}: No history, using population defaults"
            )
            return PersonalTSBProfile.from_tsb_history(athlete_id, [])

        # Extract TSB values
        tsb_values = [day.tsb for day in history]
        profile = PersonalTSBProfile.from_tsb_history(athlete_id, tsb_values)
        
        # Log the calculated profile for observability
        if profile.is_sufficient_data:
            logger.info(
                f"Personal TSB profile for {athlete_id}: "
                f"mean={profile.mean_tsb:+.1f}, SD={profile.std_tsb:.1f}, "
                f"thresholds=[fresh>{profile.threshold_fresh:+.1f}, "
                f"recovering>{profile.threshold_recovering:+.1f}, "
                f"normal>{profile.threshold_normal_low:+.1f}, "
                f"danger>{profile.threshold_danger:+.1f}] "
                f"(sample_days={profile.sample_days})"
            )
        else:
            logger.info(
                f"Personal TSB profile for {athlete_id}: "
                f"Insufficient data ({profile.sample_days} days < 56), using population defaults"
            )
        
        return profile
    
    def get_tsb_zone(
        self,
        tsb: float,
        athlete_id: Optional[UUID] = None
    ) -> TSBZoneInfo:
        """
        Classify TSB into actionable zones.
        
        If athlete_id provided: Uses personalized thresholds based on
        this athlete's historical TSB distribution (N=1).
        
        If no athlete_id: Falls back to population-based thresholds
        (legacy behavior for backwards compatibility).
        
        N=1 Philosophy:
        - "Overreaching" means fatigued FOR THIS ATHLETE, not a generic threshold
        - A marathoner at TSB -15 might be normal; for a casual runner it's deep fatigue
        - Zones are defined relative to personal mean ± standard deviations
        """
        # Use personal profile if athlete_id provided
        if athlete_id:
            profile = self.get_personal_tsb_profile(athlete_id)
            return profile.get_zone_info(tsb)
        
        # Fallback: population-based thresholds (for backwards compatibility)
        return self._get_population_tsb_zone(tsb)
    
    @staticmethod
    def _get_population_tsb_zone(tsb: float) -> TSBZoneInfo:
        """
        Population-based TSB zones (legacy/fallback).
        
        NOTE: These are NOT individualized. Used only when we don't
        have athlete-specific data or for backwards compatibility.
        
        Thresholds based on TrainingPeaks methodology.
        """
        if tsb >= 15:
            return TSBZoneInfo(
                zone=TSBZone.RACE_READY,
                label="Race Ready",
                description="Fresh and fit - ideal race window (population norm)",
                color="green",
                is_race_window=True
            )
        elif tsb >= 5:
            return TSBZoneInfo(
                zone=TSBZone.RECOVERING,
                label="Recovering",
                description="Final taper zone (population norm)",
                color="blue",
                is_race_window=False
            )
        elif tsb >= -10:
            return TSBZoneInfo(
                zone=TSBZone.OPTIMAL_TRAINING,
                label="Optimal Training",
                description="Productive overload (population norm)",
                color="yellow",
                is_race_window=False
            )
        elif tsb >= -30:
            return TSBZoneInfo(
                zone=TSBZone.OVERREACHING,
                label="Overreaching",
                description="High fatigue (population norm)",
                color="orange",
                is_race_window=False
            )
        else:
            return TSBZoneInfo(
                zone=TSBZone.OVERTRAINING_RISK,
                label="Overtraining Risk",
                description="Red zone (population norm)",
                color="red",
                is_race_window=False
            )
    
    def calculate_race_readiness(
        self,
        athlete_id: UUID,
        target_date: Optional[date] = None
    ) -> RaceReadiness:
        """
        Calculate race readiness score combining multiple factors.
        
        Score 0-100 based on:
        - TSB value (40% weight)
        - TSB trend (20% weight)
        - Days since hard workout (20% weight)
        - CTL level (20% weight)
        """
        if target_date is None:
            target_date = date.today()
        
        # Get current load summary
        load = self.calculate_training_load(athlete_id, target_date)
        
        # Get TSB zone (personalized for this athlete)
        zone_info = self.get_tsb_zone(load.current_tsb, athlete_id=athlete_id)
        
        # Score components
        
        # 1. TSB score (40%): Map TSB to 0-100
        # Optimal race TSB is +15 to +25
        if load.current_tsb >= 15 and load.current_tsb <= 25:
            tsb_score = 100
        elif load.current_tsb > 25:
            # Too fresh - might be undertrained
            tsb_score = max(70, 100 - (load.current_tsb - 25) * 2)
        elif load.current_tsb >= 5:
            # Approaching race ready
            tsb_score = 70 + (load.current_tsb - 5) * 3
        elif load.current_tsb >= -10:
            # Training zone - not ideal for racing
            tsb_score = 40 + (load.current_tsb + 10) * 3
        elif load.current_tsb >= -30:
            # Fatigued
            tsb_score = max(10, 40 + (load.current_tsb + 10) * 1.5)
        else:
            # Danger zone
            tsb_score = 10
        
        # 2. TSB trend score (20%)
        if load.tsb_trend == "rising":
            trend_score = 100
        elif load.tsb_trend == "stable":
            trend_score = 70
        else:  # falling
            trend_score = 40
        
        # 3. Days since hard workout (20%)
        days_since_hard = self._get_days_since_hard_workout(athlete_id, target_date)
        if days_since_hard is None:
            rest_score = 50  # Unknown
        elif days_since_hard >= 3 and days_since_hard <= 7:
            rest_score = 100  # Ideal pre-race rest
        elif days_since_hard >= 2:
            rest_score = 80
        elif days_since_hard >= 1:
            rest_score = 60
        else:
            rest_score = 30  # Hard workout today
        
        # 4. CTL level (20%) - need adequate fitness base
        if load.current_ctl >= 60:
            ctl_score = 100
        elif load.current_ctl >= 40:
            ctl_score = 80
        elif load.current_ctl >= 25:
            ctl_score = 60
        elif load.current_ctl >= 15:
            ctl_score = 40
        else:
            ctl_score = 20
        
        # Weighted total
        total_score = (
            tsb_score * 0.40 +
            trend_score * 0.20 +
            rest_score * 0.20 +
            ctl_score * 0.20
        )
        
        # Generate recommendation
        recommendation = self._generate_race_recommendation(
            total_score, load.current_tsb, zone_info, days_since_hard
        )
        
        return RaceReadiness(
            score=round(total_score, 1),
            tsb=load.current_tsb,
            tsb_zone=zone_info.zone,
            tsb_trend=load.tsb_trend,
            days_since_hard_workout=days_since_hard,
            recommendation=recommendation,
            is_race_window=zone_info.is_race_window
        )
    
    def _get_days_since_hard_workout(
        self,
        athlete_id: UUID,
        target_date: date
    ) -> Optional[int]:
        """Find days since last hard workout."""
        hard_types = ['tempo', 'threshold', 'interval', 'race', 'vo2max', 'speed',
                      'tempo_run', 'threshold_run', 'vo2max_intervals', 'track_workout']
        
        last_hard = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time < datetime.combine(target_date, datetime.min.time()),
            Activity.workout_type.in_(hard_types)
        ).order_by(Activity.start_time.desc()).first()
        
        if not last_hard:
            return None
        
        return (target_date - last_hard.start_time.date()).days
    
    def _generate_race_recommendation(
        self,
        score: float,
        tsb: float,
        zone_info: TSBZoneInfo,
        days_since_hard: Optional[int]
    ) -> str:
        """Generate race-specific recommendation."""
        if score >= 85:
            return "Excellent race readiness. Peak condition for goal effort."
        elif score >= 70:
            return "Good race readiness. Should perform well in competition."
        elif score >= 55:
            if tsb < 0:
                return "Moderate readiness. Consider extra recovery for best performance."
            else:
                return "Moderate readiness. Fine for training race or B-race."
        elif score >= 40:
            if zone_info.zone == TSBZone.OVERREACHING:
                return "Fatigue elevated. Racing now may compromise recovery."
            return "Low readiness. Better suited for training than racing."
        else:
            return "Not recommended for racing. Focus on recovery."
    
    def project_tsb(
        self,
        athlete_id: UUID,
        days_ahead: int = 14,
        planned_tss_per_day: Optional[List[float]] = None
    ) -> List[Dict]:
        """
        Project future TSB based on planned training.
        
        Args:
            athlete_id: Athlete UUID
            days_ahead: Number of days to project
            planned_tss_per_day: Optional list of planned daily TSS
                                 If None, assumes rest (TSS=0)
        
        Returns:
            List of projected daily TSB values
        """
        today = date.today()
        
        # Get current state
        load = self.calculate_training_load(athlete_id, today)
        current_atl = load.current_atl
        current_ctl = load.current_ctl
        
        atl_decay = 2 / (self.ATL_DECAY_DAYS + 1)
        ctl_decay = 2 / (self.CTL_DECAY_DAYS + 1)
        
        projections = []
        
        for day_offset in range(1, days_ahead + 1):
            target_date = today + timedelta(days=day_offset)
            
            # Get planned TSS for this day
            if planned_tss_per_day and day_offset <= len(planned_tss_per_day):
                day_tss = planned_tss_per_day[day_offset - 1]
            else:
                day_tss = 0  # Assume rest
            
            # Update EMAs
            current_atl = current_atl * (1 - atl_decay) + day_tss * atl_decay
            current_ctl = current_ctl * (1 - ctl_decay) + day_tss * ctl_decay
            current_tsb = current_ctl - current_atl
            
            zone = self.get_tsb_zone(current_tsb, athlete_id=athlete_id)
            
            projections.append({
                "date": target_date.isoformat(),
                "day_offset": day_offset,
                "projected_tss": day_tss,
                "atl": round(current_atl, 1),
                "ctl": round(current_ctl, 1),
                "tsb": round(current_tsb, 1),
                "zone": zone.zone.value,
                "is_race_window": zone.is_race_window
            })
        
        return projections


