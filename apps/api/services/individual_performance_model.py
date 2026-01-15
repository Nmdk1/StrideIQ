"""
Individual Performance Model (IPM)

THE DIFFERENTIATOR: Calibrates performance model parameters from athlete's OWN data.

Standard approaches use fixed constants:
- τ1 = 42 days (fitness decay)
- τ2 = 7 days (fatigue decay)

But these are INDIVIDUAL. Some athletes:
- Adapt faster (τ1 = 35 days)
- Recover slower (τ2 = 10 days)
- Have different fitness/fatigue ratios

This service:
1. Fits τ1, τ2, k1, k2 from athlete's historical data
2. Predicts performance given training load
3. Calculates optimal load trajectory
4. Provides confidence metrics

ADR-022: Individual Performance Model for Plan Generation
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional, Tuple
from uuid import UUID
from enum import Enum
import math
import statistics
import logging

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from models import Activity, Athlete

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

class ModelConfidence(str, Enum):
    """Confidence level in calibrated model."""
    HIGH = "high"           # 5+ races, good fit
    MODERATE = "moderate"   # 3-4 races, acceptable fit
    LOW = "low"             # <3 races or poor fit, using defaults
    UNCALIBRATED = "uncalibrated"  # No data, pure defaults


# Population defaults (Banister)
DEFAULT_TAU1 = 42.0  # Fitness decay (days)
DEFAULT_TAU2 = 7.0   # Fatigue decay (days)
DEFAULT_K1 = 1.0     # Fitness scaling
DEFAULT_K2 = 2.0     # Fatigue scaling (typically 2x fitness)

# Parameter bounds for optimization
TAU1_BOUNDS = (25.0, 70.0)
TAU2_BOUNDS = (4.0, 18.0)
K1_BOUNDS = (0.1, 5.0)
K2_BOUNDS = (0.2, 10.0)

# Minimum data requirements
MIN_TRAINING_DAYS = 60
MIN_PERFORMANCE_MARKERS = 3
MIN_ACTIVITIES = 30


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class BanisterModel:
    """Calibrated Banister impulse-response model."""
    athlete_id: str
    tau1: float  # Fitness decay time constant (days)
    tau2: float  # Fatigue decay time constant (days)
    k1: float    # Fitness scaling factor
    k2: float    # Fatigue scaling factor
    p0: float    # Baseline performance
    
    # Fit quality
    fit_error: float  # Sum of squared errors
    r_squared: float  # Coefficient of determination
    n_performance_markers: int
    n_training_days: int
    
    # Confidence
    confidence: ModelConfidence
    confidence_notes: List[str] = field(default_factory=list)
    
    # Calibration metadata
    calibrated_at: datetime = field(default_factory=datetime.now)
    valid_until: Optional[date] = None  # Recalibrate after new race
    
    def to_dict(self) -> Dict:
        return {
            "athlete_id": self.athlete_id,
            "parameters": {
                "tau1": round(self.tau1, 1),
                "tau2": round(self.tau2, 1),
                "k1": round(self.k1, 3),
                "k2": round(self.k2, 3),
                "p0": round(self.p0, 2)
            },
            "fit_quality": {
                "r_squared": round(self.r_squared, 3),
                "fit_error": round(self.fit_error, 2),
                "n_performance_markers": self.n_performance_markers,
                "n_training_days": self.n_training_days
            },
            "confidence": self.confidence.value,
            "confidence_notes": self.confidence_notes,
            "calibrated_at": self.calibrated_at.isoformat(),
            "insights": self._generate_insights()
        }
    
    def _generate_insights(self) -> List[str]:
        """Generate human-readable insights from model parameters."""
        insights = []
        
        # Compare to population defaults
        if self.confidence in [ModelConfidence.HIGH, ModelConfidence.MODERATE]:
            if self.tau1 < DEFAULT_TAU1 - 5:
                insights.append(f"You adapt faster than average (τ1={self.tau1:.0f} vs typical 42 days).")
            elif self.tau1 > DEFAULT_TAU1 + 5:
                insights.append(f"You adapt slower than average (τ1={self.tau1:.0f} vs typical 42 days).")
            
            if self.tau2 < DEFAULT_TAU2 - 2:
                insights.append(f"You recover from fatigue faster than average (τ2={self.tau2:.0f} vs typical 7 days).")
            elif self.tau2 > DEFAULT_TAU2 + 2:
                insights.append(f"You need more recovery time than average (τ2={self.tau2:.0f} vs typical 7 days).")
            
            # Optimal taper insight
            optimal_taper = self.calculate_optimal_taper_days()
            insights.append(f"Your optimal taper length: {optimal_taper} days.")
        
        return insights
    
    def calculate_optimal_taper_days(self) -> int:
        """
        Calculate optimal taper length based on individual parameters.
        
        Taper should be long enough for fatigue to clear,
        but short enough that fitness doesn't decay too much.
        
        Heuristic: ~2-3 × τ2 gives significant fatigue reduction
        while CTL loss is ~(1 - e^(-taper/τ1)) which is small for taper << τ1
        """
        # Target: 80% fatigue reduction, <10% fitness loss
        # Fatigue at time t: ATL(0) * e^(-t/τ2)
        # For 80% reduction: e^(-t/τ2) = 0.2 → t = -τ2 * ln(0.2) = 1.6 * τ2
        
        # Fitness at time t: CTL(0) * e^(-t/τ1)
        # For 10% loss: e^(-t/τ1) = 0.9 → t = -τ1 * ln(0.9) = 0.105 * τ1
        
        # Balance: ~2 * τ2 is usually good
        taper_days = int(2.0 * self.tau2)
        
        # Bound to reasonable range
        return max(7, min(21, taper_days))


@dataclass
class PerformanceMarker:
    """A performance data point for model calibration."""
    date: date
    performance_value: float  # VDOT or normalized efficiency
    source: str  # "race", "time_trial", "efficiency_trend"
    weight: float = 1.0  # Weight in fitting (races > efficiency)


@dataclass
class TrainingDay:
    """A day's training stress for model calibration."""
    date: date
    tss: float  # Training Stress Score


@dataclass
class ProjectedState:
    """Projected fitness/fatigue state at a future date."""
    date: date
    ctl: float  # Chronic Training Load (fitness)
    atl: float  # Acute Training Load (fatigue)
    tsb: float  # Training Stress Balance (form)
    predicted_performance: float  # From model


# =============================================================================
# MODEL CALIBRATION ENGINE
# =============================================================================

class IndividualPerformanceModel:
    """
    Calibrates and applies individual performance model.
    
    Core algorithm: Banister Impulse-Response Model
    
    Performance(t) = p0 + k1*CTL(t) - k2*ATL(t)
    
    where:
    - CTL(t) = fitness accumulated with decay τ1
    - ATL(t) = fatigue accumulated with decay τ2
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def calibrate(
        self,
        athlete_id: UUID,
        lookback_days: int = 365
    ) -> BanisterModel:
        """
        Calibrate model from athlete's historical data.
        
        Args:
            athlete_id: Athlete to calibrate
            lookback_days: How far back to look for data
            
        Returns:
            Calibrated BanisterModel
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=lookback_days)
        
        # Collect training data
        training_days = self._get_training_days(athlete_id, start_date, end_date)
        
        # Collect performance markers
        performance_markers = self._get_performance_markers(athlete_id, start_date, end_date)
        
        # Check data sufficiency
        if len(training_days) < MIN_TRAINING_DAYS:
            return self._create_default_model(
                athlete_id, 
                len(training_days), 
                len(performance_markers),
                "Insufficient training history"
            )
        
        if len(performance_markers) < MIN_PERFORMANCE_MARKERS:
            return self._create_default_model(
                athlete_id, 
                len(training_days), 
                len(performance_markers),
                "Insufficient performance markers (need 3+ races)"
            )
        
        # Fit model
        model = self._fit_model(
            str(athlete_id), training_days, performance_markers
        )
        
        return model
    
    def _get_training_days(
        self,
        athlete_id: UUID,
        start_date: date,
        end_date: date
    ) -> List[TrainingDay]:
        """Get daily TSS values from training history."""
        from services.training_load import TrainingLoadCalculator
        
        # Get all activities in range
        activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            func.date(Activity.start_time) >= start_date,
            func.date(Activity.start_time) <= end_date,
            Activity.sport.ilike("run")
        ).order_by(Activity.start_time).all()
        
        # Get athlete for TSS calculation
        athlete = self.db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            return []
        
        # Calculate TSS per day
        calculator = TrainingLoadCalculator(self.db)
        daily_tss = {}
        
        for activity in activities:
            activity_date = activity.start_time.date()
            try:
                stress = calculator.calculate_workout_tss(activity, athlete)
                if activity_date not in daily_tss:
                    daily_tss[activity_date] = 0
                daily_tss[activity_date] += stress.tss
            except Exception as e:
                logger.warning(f"Failed to calculate TSS for activity {activity.id}: {e}")
                continue
        
        # Convert to list, filling in rest days with 0
        training_days = []
        current = start_date
        while current <= end_date:
            training_days.append(TrainingDay(
                date=current,
                tss=daily_tss.get(current, 0)
            ))
            current += timedelta(days=1)
        
        return training_days
    
    def _get_performance_markers(
        self,
        athlete_id: UUID,
        start_date: date,
        end_date: date
    ) -> List[PerformanceMarker]:
        """Get performance markers from races and time trials."""
        from services.vdot_calculator import calculate_vdot_from_race_time
        
        # Get races - use multiple signals to identify races
        # 1. user_verified_race = True (explicit confirmation)
        # 2. workout_type = 'race'
        # 3. is_race_candidate = True with high confidence
        from sqlalchemy import or_
        
        races = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            func.date(Activity.start_time) >= start_date,
            func.date(Activity.start_time) <= end_date,
            or_(
                Activity.user_verified_race == True,
                Activity.workout_type == 'race',
                and_(
                    Activity.is_race_candidate == True,
                    Activity.race_confidence >= 0.7
                )
            )
        ).order_by(Activity.start_time).all()
        
        markers = []
        
        for race in races:
            if not race.distance_m or not race.duration_s:
                continue
            
            # Calculate VDOT from race
            vdot = calculate_vdot_from_race_time(race.distance_m, race.duration_s)
            if vdot:
                markers.append(PerformanceMarker(
                    date=race.start_time.date(),
                    performance_value=vdot,
                    source="race",
                    weight=1.5  # Higher weight for races
                ))
        
        # If insufficient races, try to get efficiency trend data
        if len(markers) < MIN_PERFORMANCE_MARKERS:
            efficiency_markers = self._get_efficiency_markers(
                athlete_id, start_date, end_date
            )
            markers.extend(efficiency_markers)
        
        return markers
    
    def _get_efficiency_markers(
        self,
        athlete_id: UUID,
        start_date: date,
        end_date: date
    ) -> List[PerformanceMarker]:
        """
        Get performance markers from efficiency trend.
        
        Used as fallback when insufficient race data.
        """
        # Get monthly efficiency averages as proxy for performance
        activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            func.date(Activity.start_time) >= start_date,
            func.date(Activity.start_time) <= end_date,
            Activity.sport.ilike("run"),
            Activity.avg_hr.isnot(None),
            Activity.duration_s.isnot(None),
            Activity.distance_m.isnot(None)
        ).order_by(Activity.start_time).all()
        
        # Calculate efficiency per activity
        efficiencies = []
        for a in activities:
            if a.distance_m and a.duration_s and a.avg_hr and a.avg_hr > 0:
                pace_per_km = a.duration_s / (a.distance_m / 1000)
                ef = pace_per_km / a.avg_hr
                efficiencies.append((a.start_time.date(), ef))
        
        if not efficiencies:
            return []
        
        # Calculate monthly averages
        monthly = {}
        for d, ef in efficiencies:
            month_key = (d.year, d.month)
            if month_key not in monthly:
                monthly[month_key] = []
            monthly[month_key].append(ef)
        
        markers = []
        for (year, month), efs in monthly.items():
            if len(efs) >= 5:  # Need enough samples
                avg_ef = statistics.mean(efs)
                # Convert EF to pseudo-VDOT (lower EF = better = higher VDOT)
                # This is a rough normalization
                pseudo_vdot = 80 - (avg_ef * 10)  # Rough scaling
                
                mid_month = date(year, month, 15)
                markers.append(PerformanceMarker(
                    date=mid_month,
                    performance_value=pseudo_vdot,
                    source="efficiency_trend",
                    weight=0.5  # Lower weight than races
                ))
        
        return markers
    
    def _fit_model(
        self,
        athlete_id: str,
        training_days: List[TrainingDay],
        performance_markers: List[PerformanceMarker]
    ) -> BanisterModel:
        """
        Fit Banister model parameters using optimization.
        
        Uses Nelder-Mead simplex algorithm to minimize weighted squared error.
        """
        # Convert to numpy-like structures for calculation
        tss_by_date = {td.date: td.tss for td in training_days}
        
        def calculate_ctl_atl_series(tau1: float, tau2: float) -> Dict[date, Tuple[float, float]]:
            """Calculate CTL and ATL for each date given tau parameters."""
            result = {}
            ctl = 0.0
            atl = 0.0
            
            decay1 = math.exp(-1.0 / tau1)
            decay2 = math.exp(-1.0 / tau2)
            
            for td in training_days:
                tss = tss_by_date.get(td.date, 0)
                ctl = ctl * decay1 + tss * (1 - decay1)
                atl = atl * decay2 + tss * (1 - decay2)
                result[td.date] = (ctl, atl)
            
            return result
        
        def objective(params: List[float]) -> float:
            """Objective function: weighted sum of squared errors."""
            tau1, tau2, k1, k2, p0 = params
            
            # Enforce bounds
            if not (TAU1_BOUNDS[0] <= tau1 <= TAU1_BOUNDS[1]):
                return 1e10
            if not (TAU2_BOUNDS[0] <= tau2 <= TAU2_BOUNDS[1]):
                return 1e10
            if not (K1_BOUNDS[0] <= k1 <= K1_BOUNDS[1]):
                return 1e10
            if not (K2_BOUNDS[0] <= k2 <= K2_BOUNDS[1]):
                return 1e10
            
            # Additional constraint: tau1 > tau2 (fitness decays slower than fatigue)
            if tau1 <= tau2:
                return 1e10
            
            # Calculate CTL/ATL series
            ctl_atl = calculate_ctl_atl_series(tau1, tau2)
            
            # Calculate weighted squared error
            total_error = 0.0
            for pm in performance_markers:
                if pm.date not in ctl_atl:
                    continue
                
                ctl, atl = ctl_atl[pm.date]
                predicted = p0 + k1 * ctl - k2 * atl
                error = (predicted - pm.performance_value) ** 2
                total_error += pm.weight * error
            
            return total_error
        
        # Use simple grid search + local refinement (no scipy dependency)
        best_params = self._grid_search_optimize(objective, performance_markers)
        
        # Calculate fit quality
        tau1, tau2, k1, k2, p0 = best_params
        ctl_atl = calculate_ctl_atl_series(tau1, tau2)
        
        # Calculate R-squared
        actuals = [pm.performance_value for pm in performance_markers if pm.date in ctl_atl]
        predictions = []
        for pm in performance_markers:
            if pm.date in ctl_atl:
                ctl, atl = ctl_atl[pm.date]
                predictions.append(p0 + k1 * ctl - k2 * atl)
        
        r_squared = self._calculate_r_squared(actuals, predictions)
        fit_error = objective(best_params)
        
        # Determine confidence
        confidence, notes = self._assess_confidence(
            len(performance_markers), r_squared, fit_error, 
            len(training_days)
        )
        
        return BanisterModel(
            athlete_id=athlete_id,
            tau1=tau1,
            tau2=tau2,
            k1=k1,
            k2=k2,
            p0=p0,
            fit_error=fit_error,
            r_squared=r_squared,
            n_performance_markers=len(performance_markers),
            n_training_days=len(training_days),
            confidence=confidence,
            confidence_notes=notes
        )
    
    def _grid_search_optimize(
        self,
        objective: callable,
        performance_markers: List[PerformanceMarker]
    ) -> List[float]:
        """
        Grid search optimization with local refinement.
        
        No external optimizer dependency.
        """
        # Estimate p0 from performance markers
        p0_estimate = statistics.mean([pm.performance_value for pm in performance_markers])
        
        # Grid search over tau1, tau2
        best_error = float('inf')
        best_params = [DEFAULT_TAU1, DEFAULT_TAU2, DEFAULT_K1, DEFAULT_K2, p0_estimate]
        
        for tau1 in [30, 35, 40, 45, 50, 55, 60]:
            for tau2 in [5, 6, 7, 8, 9, 10, 12]:
                if tau1 <= tau2:
                    continue
                
                # Grid search over k1, k2
                for k1 in [0.5, 0.8, 1.0, 1.2, 1.5]:
                    for k2 in [1.0, 1.5, 2.0, 2.5, 3.0]:
                        params = [tau1, tau2, k1, k2, p0_estimate]
                        error = objective(params)
                        
                        if error < best_error:
                            best_error = error
                            best_params = params
        
        # Local refinement around best
        refined_params = self._local_refine(objective, best_params)
        
        return refined_params
    
    def _local_refine(
        self,
        objective: callable,
        initial: List[float],
        iterations: int = 50
    ) -> List[float]:
        """Simple local refinement using coordinate descent."""
        params = initial.copy()
        step_sizes = [2.0, 0.5, 0.1, 0.2, 1.0]  # For tau1, tau2, k1, k2, p0
        
        for _ in range(iterations):
            improved = False
            for i in range(len(params)):
                current_error = objective(params)
                
                # Try increasing
                params[i] += step_sizes[i]
                if objective(params) < current_error:
                    improved = True
                    continue
                params[i] -= step_sizes[i]  # Revert
                
                # Try decreasing
                params[i] -= step_sizes[i]
                if objective(params) < current_error:
                    improved = True
                    continue
                params[i] += step_sizes[i]  # Revert
            
            if not improved:
                # Reduce step sizes
                step_sizes = [s * 0.7 for s in step_sizes]
        
        return params
    
    def _calculate_r_squared(
        self,
        actuals: List[float],
        predictions: List[float]
    ) -> float:
        """Calculate coefficient of determination."""
        if len(actuals) < 2:
            return 0.0
        
        mean_actual = statistics.mean(actuals)
        
        ss_tot = sum((a - mean_actual) ** 2 for a in actuals)
        ss_res = sum((a - p) ** 2 for a, p in zip(actuals, predictions))
        
        if ss_tot == 0:
            return 0.0
        
        return 1 - (ss_res / ss_tot)
    
    def _assess_confidence(
        self,
        n_markers: int,
        r_squared: float,
        fit_error: float,
        n_days: int
    ) -> Tuple[ModelConfidence, List[str]]:
        """Assess confidence in calibrated model."""
        notes = []
        
        if n_markers >= 5 and r_squared >= 0.7 and n_days >= 180:
            confidence = ModelConfidence.HIGH
            notes.append("Good data coverage and model fit.")
        elif n_markers >= 3 and r_squared >= 0.5 and n_days >= 90:
            confidence = ModelConfidence.MODERATE
            if n_markers < 5:
                notes.append(f"More races ({n_markers}/5) will improve accuracy.")
            if r_squared < 0.7:
                notes.append("Model fit is acceptable but not optimal.")
        else:
            confidence = ModelConfidence.LOW
            if n_markers < 3:
                notes.append(f"Need more race data ({n_markers}/3 minimum).")
            if r_squared < 0.5:
                notes.append("Model fit is poor - predictions may be unreliable.")
            if n_days < 90:
                notes.append("Need more training history.")
        
        return confidence, notes
    
    def _create_default_model(
        self,
        athlete_id: UUID,
        n_training_days: int,
        n_markers: int,
        reason: str
    ) -> BanisterModel:
        """Create model with population defaults when calibration not possible."""
        return BanisterModel(
            athlete_id=str(athlete_id),
            tau1=DEFAULT_TAU1,
            tau2=DEFAULT_TAU2,
            k1=DEFAULT_K1,
            k2=DEFAULT_K2,
            p0=50.0,  # Arbitrary baseline
            fit_error=0.0,
            r_squared=0.0,
            n_performance_markers=n_markers,
            n_training_days=n_training_days,
            confidence=ModelConfidence.UNCALIBRATED,
            confidence_notes=[reason, "Using population defaults."]
        )
    
    # =========================================================================
    # PROJECTION AND PREDICTION
    # =========================================================================
    
    def project_state(
        self,
        model: BanisterModel,
        current_ctl: float,
        current_atl: float,
        future_date: date,
        planned_tss: List[Tuple[date, float]]  # (date, tss) pairs
    ) -> ProjectedState:
        """
        Project CTL/ATL/TSB at a future date given planned training.
        
        Args:
            model: Calibrated model
            current_ctl: Current CTL
            current_atl: Current ATL
            future_date: Date to project to
            planned_tss: Planned daily TSS values
        
        Returns:
            Projected state
        """
        ctl = current_ctl
        atl = current_atl
        
        decay1 = math.exp(-1.0 / model.tau1)
        decay2 = math.exp(-1.0 / model.tau2)
        
        tss_by_date = {d: tss for d, tss in planned_tss}
        
        current = date.today()
        while current <= future_date:
            tss = tss_by_date.get(current, 0)
            ctl = ctl * decay1 + tss * (1 - decay1)
            atl = atl * decay2 + tss * (1 - decay2)
            current += timedelta(days=1)
        
        tsb = ctl - atl
        predicted_performance = model.p0 + model.k1 * ctl - model.k2 * atl
        
        return ProjectedState(
            date=future_date,
            ctl=ctl,
            atl=atl,
            tsb=tsb,
            predicted_performance=predicted_performance
        )
    
    def calculate_taper_days_needed(
        self,
        model: BanisterModel,
        current_ctl: float,
        current_atl: float,
        target_tsb: float
    ) -> int:
        """
        Calculate how many taper days needed to hit target TSB.
        
        Assumes TSS = 0 during taper (simplified).
        """
        ctl = current_ctl
        atl = current_atl
        
        decay1 = math.exp(-1.0 / model.tau1)
        decay2 = math.exp(-1.0 / model.tau2)
        
        for days in range(1, 35):  # Max 35 days taper
            ctl = ctl * decay1
            atl = atl * decay2
            tsb = ctl - atl
            
            if tsb >= target_tsb:
                return days
        
        return 21  # Default if can't reach target


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_or_calibrate_model(
    athlete_id: UUID,
    db: Session,
    force_recalibrate: bool = False
) -> BanisterModel:
    """
    Get cached model or calibrate new one.
    
    TODO: Add model caching to database
    """
    engine = IndividualPerformanceModel(db)
    return engine.calibrate(athlete_id)


def get_model_insights(athlete_id: UUID, db: Session) -> Dict:
    """Get human-readable insights from athlete's model."""
    model = get_or_calibrate_model(athlete_id, db)
    return model.to_dict()
