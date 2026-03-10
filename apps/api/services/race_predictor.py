"""
Race Time Predictor

Predicts race time from current fitness trajectory using individual model.

Uses:
1. Projected CTL on race day (from calibrated model)
2. Efficiency trend (from efficiency_trending.py)
3. Historical performance at this distance
4. Pre-race fingerprint match

No LLM/AI dependency - pure calculation.

ADR-022: Individual Performance Model for Plan Generation
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional, Tuple
from uuid import UUID
import math
import statistics
import logging

from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_

from models import Activity
from services.individual_performance_model import (
    get_or_calibrate_model,
    BanisterModel,
    ModelConfidence
)
from services.rpi_calculator import (
    calculate_rpi_from_race_time,
    calculate_race_time_from_rpi
)

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class RacePrediction:
    """Race time prediction with confidence."""
    predicted_time_seconds: int
    predicted_time_formatted: str
    
    # Confidence
    confidence_interval_seconds: int  # +/- this much
    confidence_interval_formatted: str
    prediction_confidence: str  # "high", "moderate", "low"
    
    # Underlying projections
    projected_rpi: float
    projected_ctl: float
    projected_tsb: float
    
    # Factors considered
    factors: List[str]
    notes: List[str]
    
    def to_dict(self) -> Dict:
        return {
            "prediction": {
                "time_seconds": self.predicted_time_seconds,
                "time_formatted": self.predicted_time_formatted,
                "confidence_interval_seconds": self.confidence_interval_seconds,
                "confidence_interval_formatted": self.confidence_interval_formatted,
                "confidence": self.prediction_confidence
            },
            "projections": {
                "rpi": round(self.projected_rpi, 1),
                "ctl": round(self.projected_ctl, 1),
                "tsb": round(self.projected_tsb, 1)
            },
            "factors": self.factors,
            "notes": self.notes
        }


@dataclass
class DistanceProfile:
    """Athlete's profile at a specific distance."""
    distance_m: float
    distance_name: str
    n_races: int
    best_time_seconds: int
    avg_time_seconds: int
    best_rpi: float
    avg_rpi: float
    trend: str  # "improving", "stable", "declining"


# =============================================================================
# CONSTANTS
# =============================================================================

DISTANCE_NAMES = {
    1609: "Mile",
    3000: "3K",
    5000: "5K",
    8000: "8K",
    10000: "10K",
    15000: "15K",
    16093: "10 Mile",
    21097: "Half Marathon",
    42195: "Marathon"
}

DISTANCE_TOLERANCE = 0.05  # 5% tolerance for distance matching


# =============================================================================
# RACE PREDICTOR
# =============================================================================

class RacePredictor:
    """
    Predicts race times from individual performance model.
    
    Combines:
    1. Individual model (τ1, τ2) for fitness projection
    2. RPI for race time conversion
    3. Historical performance for distance-specific adjustment
    4. Efficiency trend for fitness trajectory
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def predict(
        self,
        athlete_id: UUID,
        race_date: date,
        distance_m: float,
        planned_weekly_tss: Optional[List[float]] = None
    ) -> RacePrediction:
        """
        Predict race time.
        
        Args:
            athlete_id: Athlete UUID
            race_date: Target race date
            distance_m: Race distance in meters
            planned_weekly_tss: Optional planned weekly TSS leading up to race
            
        Returns:
            RacePrediction with time and confidence
        """
        factors = []
        notes = []
        
        # Get calibrated model
        model = get_or_calibrate_model(athlete_id, self.db)
        factors.append(f"Individual model (τ1={model.tau1:.0f}, τ2={model.tau2:.0f})")
        
        # Get current state
        current_rpi = self._get_current_rpi(athlete_id)
        if current_rpi:
            factors.append(f"Current RPI: {current_rpi:.1f}")
        else:
            current_rpi = self._estimate_rpi_from_training(athlete_id)
            if current_rpi:
                factors.append(f"Estimated RPI: {current_rpi:.1f}")
                notes.append("RPI estimated from training - race data would improve accuracy")
            else:
                return self._create_insufficient_data_prediction(distance_m)
        
        # Project fitness on race day
        projected_ctl, projected_atl = self._project_race_day_fitness(
            athlete_id, race_date, model, planned_weekly_tss
        )
        projected_tsb = projected_ctl - projected_atl
        factors.append(f"Projected race-day CTL: {projected_ctl:.0f}")
        factors.append(f"Projected race-day TSB: {projected_tsb:.0f}")
        
        # Calculate projected RPI based on fitness change
        current_ctl = self._get_current_ctl(athlete_id)
        if current_ctl and current_ctl > 0:
            ctl_change_pct = (projected_ctl - current_ctl) / current_ctl
            # Rough conversion: 10% CTL increase ≈ 1 RPI point
            rpi_adjustment = ctl_change_pct * 10
            projected_rpi = current_rpi + rpi_adjustment
        else:
            projected_rpi = current_rpi
        
        # Adjust for distance-specific performance
        distance_adjustment = self._get_distance_adjustment(athlete_id, distance_m)
        if distance_adjustment != 0:
            projected_rpi += distance_adjustment
            notes.append(f"Distance adjustment: {distance_adjustment:+.1f} RPI")
        
        # Adjust for TSB (form)
        tsb_adjustment = self._calculate_tsb_adjustment(projected_tsb)
        projected_rpi += tsb_adjustment
        if abs(tsb_adjustment) > 0.3:
            notes.append(f"Form adjustment: {tsb_adjustment:+.1f} RPI")
        
        # Convert RPI to race time
        predicted_seconds = calculate_race_time_from_rpi(projected_rpi, distance_m)
        if not predicted_seconds:
            return self._create_insufficient_data_prediction(distance_m)
        
        # Calculate confidence interval
        confidence_seconds = self._calculate_confidence_interval(
            model, projected_rpi, distance_m
        )
        
        # Determine overall confidence
        prediction_confidence = self._assess_prediction_confidence(
            model, len(notes), distance_m, athlete_id
        )
        
        return RacePrediction(
            predicted_time_seconds=predicted_seconds,
            predicted_time_formatted=self._format_time(predicted_seconds),
            confidence_interval_seconds=confidence_seconds,
            confidence_interval_formatted=f"±{self._format_time(confidence_seconds)}",
            prediction_confidence=prediction_confidence,
            projected_rpi=projected_rpi,
            projected_ctl=projected_ctl,
            projected_tsb=projected_tsb,
            factors=factors,
            notes=notes
        )
    
    def get_distance_profile(
        self,
        athlete_id: UUID,
        distance_m: float
    ) -> Optional[DistanceProfile]:
        """Get athlete's historical performance at a distance."""
        tolerance = distance_m * DISTANCE_TOLERANCE
        
        # Use race detection fields (is_race_candidate, user_verified_race, workout_type)
        races = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            or_(
                Activity.user_verified_race == True,
                Activity.workout_type == 'race',
                and_(Activity.is_race_candidate == True, Activity.race_confidence >= 0.7)
            ),
            Activity.distance_m >= distance_m - tolerance,
            Activity.distance_m <= distance_m + tolerance,
            Activity.duration_s.isnot(None)
        ).order_by(Activity.start_time.desc()).limit(20).all()
        
        if not races:
            return None
        
        times = [r.duration_s for r in races]
        rpis = []
        for r in races:
            v = calculate_rpi_from_race_time(r.distance_m, r.duration_s)
            if v:
                rpis.append(v)
        
        if not rpis:
            return None
        
        # Determine trend
        if len(rpis) >= 3:
            recent = statistics.mean(rpis[:3])
            older = statistics.mean(rpis[-3:])
            if recent > older + 0.5:
                trend = "improving"
            elif recent < older - 0.5:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"
        
        distance_name = self._get_distance_name(distance_m)
        
        return DistanceProfile(
            distance_m=distance_m,
            distance_name=distance_name,
            n_races=len(races),
            best_time_seconds=min(times),
            avg_time_seconds=int(statistics.mean(times)),
            best_rpi=max(rpis),
            avg_rpi=statistics.mean(rpis),
            trend=trend
        )
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _get_current_rpi(self, athlete_id: UUID) -> Optional[float]:
        """Get athlete's current RPI from recent races."""
        # Get recent races (last 6 months)
        cutoff = datetime.now() - timedelta(days=180)
        
        # Use race detection fields
        races = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            or_(
                Activity.user_verified_race == True,
                Activity.workout_type == 'race',
                and_(Activity.is_race_candidate == True, Activity.race_confidence >= 0.7)
            ),
            Activity.start_time >= cutoff,
            Activity.duration_s.isnot(None),
            Activity.distance_m.isnot(None)
        ).order_by(Activity.start_time.desc()).limit(5).all()
        
        if not races:
            return None
        
        rpis = []
        for race in races:
            v = calculate_rpi_from_race_time(race.distance_m, race.duration_s)
            if v:
                rpis.append(v)
        
        if not rpis:
            return None
        
        # Weight recent races more heavily
        if len(rpis) == 1:
            return rpis[0]
        elif len(rpis) == 2:
            return rpis[0] * 0.7 + rpis[1] * 0.3
        else:
            return rpis[0] * 0.5 + rpis[1] * 0.3 + statistics.mean(rpis[2:]) * 0.2
    
    def _estimate_rpi_from_training(self, athlete_id: UUID) -> Optional[float]:
        """Estimate RPI from training data when no race data available."""
        # This is a rough estimate based on training paces
        # Get threshold workouts
        cutoff = datetime.now() - timedelta(days=90)
        
        threshold_workouts = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time >= cutoff,
            Activity.workout_type.in_(['tempo', 'threshold']),
            Activity.duration_s.isnot(None),
            Activity.distance_m.isnot(None)
        ).order_by(Activity.start_time.desc()).limit(10).all()
        
        if not threshold_workouts:
            return None
        
        # Threshold pace approximates 1-hour race pace
        paces = []
        for w in threshold_workouts:
            if w.distance_m and w.distance_m > 0:
                pace_per_km = w.duration_s / (w.distance_m / 1000)
                paces.append(pace_per_km)
        
        if not paces:
            return None
        
        avg_threshold_pace = statistics.mean(paces)
        
        # Convert threshold pace to estimated 10K time, then to RPI
        estimated_10k_pace = avg_threshold_pace * 1.03  # Slightly slower than threshold
        estimated_10k_time = estimated_10k_pace * 10  # 10K = 10km
        
        return calculate_rpi_from_race_time(10000, estimated_10k_time)
    
    def _get_current_ctl(self, athlete_id: UUID) -> Optional[float]:
        """Get athlete's current CTL."""
        from services.training_load import TrainingLoadCalculator
        
        try:
            calculator = TrainingLoadCalculator(self.db)
            load = calculator.calculate_training_load(athlete_id)
            return load.current_ctl
        except Exception:
            return None
    
    def _project_race_day_fitness(
        self,
        athlete_id: UUID,
        race_date: date,
        model: BanisterModel,
        planned_weekly_tss: Optional[List[float]]
    ) -> Tuple[float, float]:
        """Project CTL and ATL on race day."""
        from services.training_load import TrainingLoadCalculator
        
        # Get current state
        try:
            calculator = TrainingLoadCalculator(self.db)
            current_load = calculator.calculate_training_load(athlete_id)
            current_ctl = current_load.current_ctl
            current_atl = current_load.current_atl
        except Exception:
            current_ctl = 50  # Default
            current_atl = 40
        
        # If no planned TSS, assume maintenance
        days_to_race = (race_date - date.today()).days
        weeks_to_race = max(1, days_to_race // 7)
        
        if not planned_weekly_tss:
            # Assume maintenance for build, then taper
            build_weeks = max(0, weeks_to_race - 3)
            maintenance_tss = current_ctl * 7  # Maintain current load
            planned_weekly_tss = [maintenance_tss] * build_weeks
            # Add taper
            planned_weekly_tss.extend([
                maintenance_tss * 0.6,
                maintenance_tss * 0.4,
                maintenance_tss * 0.25
            ])
        
        # Project forward
        ctl = current_ctl
        atl = current_atl
        
        decay1 = math.exp(-1.0 / model.tau1)
        decay2 = math.exp(-1.0 / model.tau2)
        
        for weekly_tss in planned_weekly_tss[:weeks_to_race]:
            daily_tss = weekly_tss / 7
            for _ in range(7):
                ctl = ctl * decay1 + daily_tss * (1 - decay1)
                atl = atl * decay2 + daily_tss * (1 - decay2)
        
        return ctl, atl
    
    def _get_distance_adjustment(self, athlete_id: UUID, distance_m: float) -> float:
        """
        Adjust RPI based on athlete's distance-specific performance.
        
        Some athletes are better at shorter or longer distances relative to RPI.
        """
        # Get performance at multiple distances
        profiles = {}
        for dist in [5000, 10000, 21097, 42195]:
            profile = self.get_distance_profile(athlete_id, dist)
            if profile and profile.n_races >= 2:
                profiles[dist] = profile
        
        if len(profiles) < 2:
            return 0  # Not enough data for adjustment
        
        # Calculate RPI variance across distances
        rpis = {d: p.best_rpi for d, p in profiles.items()}
        mean_rpi = statistics.mean(rpis.values())
        
        # Check if target distance has data
        closest_dist = min(profiles.keys(), key=lambda d: abs(d - distance_m))
        
        if abs(closest_dist - distance_m) < distance_m * 0.1:
            # Have data at this distance - check if athlete over/underperforms
            distance_rpi = profiles[closest_dist].best_rpi
            adjustment = distance_rpi - mean_rpi
            return adjustment * 0.5  # Partial adjustment
        
        return 0
    
    def _calculate_tsb_adjustment(self, tsb: float) -> float:
        """
        Adjust RPI based on form (TSB).
        
        Optimal TSB for racing is typically +10 to +20.
        """
        if tsb >= 10 and tsb <= 20:
            # Optimal range - small positive adjustment
            return 0.5
        elif tsb > 20:
            # Too fresh - might be undertrained
            excess = tsb - 20
            return 0.5 - (excess * 0.05)  # Decrease for being too fresh
        elif tsb >= 0:
            # Slightly fatigued
            deficit = 10 - tsb
            return 0.5 - (deficit * 0.03)
        else:
            # Fatigued
            return -0.5 - (abs(tsb) * 0.02)
    
    def _calculate_confidence_interval(
        self,
        model: BanisterModel,
        rpi: float,
        distance_m: float
    ) -> int:
        """Calculate confidence interval in seconds."""
        # Base confidence from model
        if model.confidence == ModelConfidence.HIGH:
            base_pct = 0.015  # ±1.5%
        elif model.confidence == ModelConfidence.MODERATE:
            base_pct = 0.025  # ±2.5%
        else:
            base_pct = 0.04  # ±4%
        
        # Calculate base time
        base_time = calculate_race_time_from_rpi(rpi, distance_m) or 0
        
        return int(base_time * base_pct)
    
    def _assess_prediction_confidence(
        self,
        model: BanisterModel,
        n_adjustments: int,
        distance_m: float,
        athlete_id: UUID
    ) -> str:
        """Assess overall prediction confidence."""
        # Start with model confidence
        if model.confidence == ModelConfidence.HIGH:
            score = 3
        elif model.confidence == ModelConfidence.MODERATE:
            score = 2
        else:
            score = 1
        
        # Adjust for number of adjustments made
        score -= n_adjustments * 0.3
        
        # Adjust for distance-specific data
        profile = self.get_distance_profile(athlete_id, distance_m)
        if profile and profile.n_races >= 3:
            score += 0.5
        
        if score >= 2.5:
            return "high"
        elif score >= 1.5:
            return "moderate"
        else:
            return "low"
    
    def _get_distance_name(self, distance_m: float) -> str:
        """Get human-readable distance name."""
        # Find closest standard distance
        for std_dist, name in DISTANCE_NAMES.items():
            if abs(std_dist - distance_m) < std_dist * 0.05:
                return name
        
        # Custom distance
        if distance_m < 1000:
            return f"{distance_m:.0f}m"
        else:
            return f"{distance_m/1000:.1f}K"
    
    def _format_time(self, seconds: int) -> str:
        """Format seconds as HH:MM:SS or MM:SS."""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
    
    def _create_insufficient_data_prediction(self, distance_m: float) -> RacePrediction:
        """Create prediction indicating insufficient data."""
        distance_name = self._get_distance_name(distance_m)
        
        return RacePrediction(
            predicted_time_seconds=0,
            predicted_time_formatted="N/A",
            confidence_interval_seconds=0,
            confidence_interval_formatted="N/A",
            prediction_confidence="insufficient_data",
            projected_rpi=0,
            projected_ctl=0,
            projected_tsb=0,
            factors=[],
            notes=[
                f"Insufficient data to predict {distance_name} time.",
                "Add race results or time trials to enable predictions."
            ]
        )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def predict_race_time(
    athlete_id: UUID,
    race_date: date,
    distance_m: float,
    db: Session
) -> RacePrediction:
    """Predict race time for athlete."""
    predictor = RacePredictor(db)
    return predictor.predict(athlete_id, race_date, distance_m)


def get_race_time_range(
    athlete_id: UUID,
    race_date: date,
    distance_m: float,
    db: Session
) -> Dict[str, str]:
    """Get predicted race time range (best case / likely / worst case)."""
    prediction = predict_race_time(athlete_id, race_date, distance_m, db)
    
    if prediction.predicted_time_seconds == 0:
        return {"error": "Insufficient data for prediction"}
    
    best = prediction.predicted_time_seconds - prediction.confidence_interval_seconds
    worst = prediction.predicted_time_seconds + prediction.confidence_interval_seconds
    
    def format_time(s: int) -> str:
        h, m, sec = s // 3600, (s % 3600) // 60, s % 60
        if h > 0:
            return f"{h}:{m:02d}:{sec:02d}"
        return f"{m}:{sec:02d}"
    
    return {
        "best_case": format_time(best),
        "likely": prediction.predicted_time_formatted,
        "worst_case": format_time(worst),
        "confidence": prediction.prediction_confidence
    }
