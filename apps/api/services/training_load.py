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
"""

from datetime import datetime, timedelta, date
from typing import List, Dict, Optional, Tuple
from uuid import UUID
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
import math
import logging

from models import Activity, Athlete, DailyCheckin

logger = logging.getLogger(__name__)


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
    # ATL / CTL / TSB CALCULATION
    # =========================================================================
    
    def calculate_training_load(
        self, 
        athlete_id: UUID, 
        target_date: Optional[date] = None
    ) -> LoadSummary:
        """
        Calculate current training load metrics for an athlete.
        """
        if target_date is None:
            target_date = date.today()
        
        # Get athlete
        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            raise ValueError(f"Athlete {athlete_id} not found")
        
        # Get last 60 days of activities (need history for CTL)
        lookback_days = 60
        start_date = target_date - timedelta(days=lookback_days)
        
        activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= datetime.combine(start_date, datetime.min.time()),
            Activity.start_time < datetime.combine(target_date + timedelta(days=1), datetime.min.time())
        ).order_by(Activity.start_time).all()
        
        # Calculate TSS for each activity
        daily_tss: Dict[date, float] = {}
        for activity in activities:
            stress = self.calculate_workout_tss(activity, athlete)
            activity_date = stress.date
            daily_tss[activity_date] = daily_tss.get(activity_date, 0) + stress.tss
        
        # Calculate ATL and CTL using exponential weighted average
        atl_history = []
        ctl_history = []
        
        current_atl = 0.0
        current_ctl = 0.0
        
        atl_decay = 2 / (self.ATL_DECAY_DAYS + 1)  # EMA alpha for ATL
        ctl_decay = 2 / (self.CTL_DECAY_DAYS + 1)  # EMA alpha for CTL
        
        # Iterate through each day
        for day_offset in range(lookback_days):
            current_date = start_date + timedelta(days=day_offset)
            day_tss = daily_tss.get(current_date, 0)
            
            # Exponential moving average update
            current_atl = current_atl * (1 - atl_decay) + day_tss * atl_decay
            current_ctl = current_ctl * (1 - ctl_decay) + day_tss * ctl_decay
            
            atl_history.append(current_atl)
            ctl_history.append(current_ctl)
        
        # Current TSB
        current_tsb = current_ctl - current_atl
        
        # Calculate trends (last 7 days vs previous 7 days)
        atl_trend = self._calculate_trend(atl_history[-14:-7], atl_history[-7:])
        ctl_trend = self._calculate_trend(ctl_history[-14:-7], ctl_history[-7:])
        
        # TSB trend from ATL/CTL trends
        if atl_trend == "rising" and ctl_trend != "rising":
            tsb_trend = "falling"
        elif atl_trend == "falling" and ctl_trend != "falling":
            tsb_trend = "rising"
        else:
            tsb_trend = "stable"
        
        # Determine training phase
        training_phase = self._determine_training_phase(
            current_atl, current_ctl, current_tsb, atl_trend, ctl_trend
        )
        
        # Generate recommendation
        recommendation = self._generate_recommendation(
            current_atl, current_ctl, current_tsb, training_phase
        )
        
        return LoadSummary(
            current_atl=round(current_atl, 1),
            current_ctl=round(current_ctl, 1),
            current_tsb=round(current_tsb, 1),
            atl_trend=atl_trend,
            ctl_trend=ctl_trend,
            tsb_trend=tsb_trend,
            training_phase=training_phase,
            recommendation=recommendation
        )
    
    def get_load_history(
        self,
        athlete_id: UUID,
        days: int = 60
    ) -> List[DailyLoad]:
        """
        Get daily training load history for charting.
        """
        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            return []
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= datetime.combine(start_date, datetime.min.time()),
            Activity.start_time < datetime.combine(end_date + timedelta(days=1), datetime.min.time())
        ).order_by(Activity.start_time).all()
        
        # Calculate TSS per activity
        daily_tss: Dict[date, Tuple[float, int]] = {}  # date -> (total_tss, count)
        for activity in activities:
            stress = self.calculate_workout_tss(activity, athlete)
            activity_date = stress.date
            if activity_date in daily_tss:
                daily_tss[activity_date] = (
                    daily_tss[activity_date][0] + stress.tss,
                    daily_tss[activity_date][1] + 1
                )
            else:
                daily_tss[activity_date] = (stress.tss, 1)
        
        # Build daily load history
        history: List[DailyLoad] = []
        current_atl = 0.0
        current_ctl = 0.0
        
        atl_decay = 2 / (self.ATL_DECAY_DAYS + 1)
        ctl_decay = 2 / (self.CTL_DECAY_DAYS + 1)
        
        for day_offset in range(days):
            current_date = start_date + timedelta(days=day_offset)
            tss_data = daily_tss.get(current_date, (0, 0))
            day_tss, workout_count = tss_data
            
            # Update EMAs
            current_atl = current_atl * (1 - atl_decay) + day_tss * atl_decay
            current_ctl = current_ctl * (1 - ctl_decay) + day_tss * ctl_decay
            current_tsb = current_ctl - current_atl
            
            history.append(DailyLoad(
                date=current_date,
                total_tss=round(day_tss, 1),
                workout_count=workout_count,
                atl=round(current_atl, 1),
                ctl=round(current_ctl, 1),
                tsb=round(current_tsb, 1)
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


