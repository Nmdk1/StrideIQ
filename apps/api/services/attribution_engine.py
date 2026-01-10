"""
Attribution Engine

The "WHY" behind performance changes.

This is the moat. Everyone else shows "what happened" (your pace improved).
We show "why it happened" (sleep up, threshold volume up, consistency up).

Architecture:
1. InputAnalyzers - Calculate trailing averages for each input category
2. AttributionScorer - Compare input deltas to performance deltas
3. ConfidenceCalculator - Only show attributions we can defend
4. InsightGenerator - Sparse, irreverent, manifesto-aligned language

Key Principle: "Data suggests X correlates with Y" not "X caused Y"
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from enum import Enum
from decimal import Decimal
import statistics
import math

from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from models import (
    Activity, 
    Athlete,
    DailyCheckin, 
    BodyComposition, 
    NutritionEntry,
)


# =============================================================================
# CONFIGURATION
# =============================================================================

class InputCategory(str, Enum):
    """Categories of inputs that can drive performance"""
    SLEEP = "sleep"
    RECOVERY = "recovery"  # HRV, stress, soreness
    BODY_COMPOSITION = "body_composition"
    VOLUME = "volume"
    CONSISTENCY = "consistency"
    TRAINING_MIX = "training_mix"
    NUTRITION = "nutrition"
    MINDSET = "mindset"


# Default trailing windows for each input type (evidence-based)
TRAILING_WINDOWS = {
    InputCategory.SLEEP: 7,           # Sleep affects next 1-7 days
    InputCategory.RECOVERY: 7,        # HRV/stress are short-term indicators
    InputCategory.BODY_COMPOSITION: 14,  # Weight trends matter over 2 weeks
    InputCategory.VOLUME: 28,         # Training volume effects over 4 weeks
    InputCategory.CONSISTENCY: 28,    # Consistency patterns over 4 weeks
    InputCategory.TRAINING_MIX: 28,   # Workout distribution over 4 weeks
    InputCategory.NUTRITION: 3,       # Glycogen/fueling is short-term
    InputCategory.MINDSET: 7,         # Mental state trailing 1 week
}

# Minimum data points required to make any attribution
MIN_DATA_POINTS = {
    InputCategory.SLEEP: 5,
    InputCategory.RECOVERY: 5,
    InputCategory.BODY_COMPOSITION: 2,
    InputCategory.VOLUME: 4,
    InputCategory.CONSISTENCY: 4,
    InputCategory.TRAINING_MIX: 4,
    InputCategory.NUTRITION: 3,
    InputCategory.MINDSET: 5,
}


# =============================================================================
# DATA MODELS
# =============================================================================

class Confidence(str, Enum):
    """Confidence level for attributions"""
    HIGH = "high"           # 80%+ correlation, good sample size
    MODERATE = "moderate"   # 60-80% correlation or smaller sample
    LOW = "low"             # 40-60% correlation, use carefully
    INSUFFICIENT = "insufficient"  # Not enough data


class DriverDirection(str, Enum):
    """Whether the driver helped or hurt performance"""
    POSITIVE = "positive"   # This input change likely helped
    NEGATIVE = "negative"   # This input change likely hurt
    NEUTRAL = "neutral"     # No significant change


@dataclass
class InputDelta:
    """Change in an input between current and baseline periods"""
    category: InputCategory
    name: str                    # Human-readable name
    icon: str                    # Emoji for UI
    current_value: Optional[float]
    baseline_value: Optional[float]
    delta: Optional[float]       # current - baseline
    delta_pct: Optional[float]   # Percentage change
    unit: str                    # "hours", "kg", "runs/week", etc.
    data_points_current: int     # How many data points in current period
    data_points_baseline: int    # How many in baseline period
    has_sufficient_data: bool    # Meets minimum threshold
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "name": self.name,
            "icon": self.icon,
            "current_value": round(self.current_value, 2) if self.current_value else None,
            "baseline_value": round(self.baseline_value, 2) if self.baseline_value else None,
            "delta": round(self.delta, 2) if self.delta else None,
            "delta_pct": round(self.delta_pct, 1) if self.delta_pct else None,
            "unit": self.unit,
            "data_points_current": self.data_points_current,
            "data_points_baseline": self.data_points_baseline,
            "has_sufficient_data": self.has_sufficient_data,
        }


@dataclass
class PerformanceDriver:
    """A factor that likely contributed to performance change"""
    category: InputCategory
    name: str
    icon: str
    direction: DriverDirection   # positive, negative, neutral
    magnitude: str               # "+45 min/night", "-2 runs/week"
    contribution_score: float    # 0-1, how much this explains the change
    confidence: Confidence
    insight: str                 # Sparse, manifesto-aligned language
    delta: InputDelta            # The underlying data
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "name": self.name,
            "icon": self.icon,
            "direction": self.direction.value,
            "magnitude": self.magnitude,
            "contribution_score": round(self.contribution_score, 2),
            "confidence": self.confidence.value,
            "insight": self.insight,
            "delta": self.delta.to_dict(),
        }


@dataclass
class AttributionResult:
    """Complete attribution analysis for a performance comparison"""
    # The performance change being explained
    performance_delta: float        # % change in performance
    performance_direction: str      # "improved", "declined", "stable"
    
    # All input deltas (what changed)
    input_deltas: List[InputDelta]
    
    # Top drivers (why it changed)
    key_drivers: List[PerformanceDriver]
    
    # Summary
    summary_positive: Optional[str]  # "Why you were faster: ..."
    summary_negative: Optional[str]  # "Potential drag factors: ..."
    overall_confidence: Confidence
    
    # Meta
    current_period: Tuple[date, date]
    baseline_period: Tuple[date, date]
    data_quality_score: float       # 0-1, how much data we had to work with
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "performance_delta": round(self.performance_delta, 1),
            "performance_direction": self.performance_direction,
            "input_deltas": [d.to_dict() for d in self.input_deltas],
            "key_drivers": [d.to_dict() for d in self.key_drivers],
            "summary_positive": self.summary_positive,
            "summary_negative": self.summary_negative,
            "overall_confidence": self.overall_confidence.value,
            "current_period": {
                "start": self.current_period[0].isoformat(),
                "end": self.current_period[1].isoformat(),
            },
            "baseline_period": {
                "start": self.baseline_period[0].isoformat(),
                "end": self.baseline_period[1].isoformat(),
            },
            "data_quality_score": round(self.data_quality_score, 2),
        }


# =============================================================================
# INPUT ANALYZERS
# =============================================================================

class InputAnalyzer:
    """Base class for analyzing input categories"""
    
    def __init__(self, db: Session, athlete_id: UUID):
        self.db = db
        self.athlete_id = athlete_id
    
    def analyze(
        self, 
        current_date: date, 
        baseline_dates: List[date],
        window_days: int
    ) -> List[InputDelta]:
        """
        Analyze inputs for both current and baseline periods.
        Returns list of InputDelta objects for this category.
        """
        raise NotImplementedError


class SleepAnalyzer(InputAnalyzer):
    """Analyze sleep patterns"""
    
    def analyze(
        self, 
        current_date: date, 
        baseline_dates: List[date],
        window_days: int = 7
    ) -> List[InputDelta]:
        
        # Current period: window_days before current_date
        current_start = current_date - timedelta(days=window_days)
        current_sleep = self._get_sleep_data(current_start, current_date)
        
        # Baseline period: average of windows before each baseline date
        baseline_sleep_values = []
        for bd in baseline_dates:
            bs_start = bd - timedelta(days=window_days)
            bs_data = self._get_sleep_data(bs_start, bd)
            if bs_data:
                baseline_sleep_values.extend(bs_data)
        
        # Calculate averages
        current_avg = statistics.mean(current_sleep) if current_sleep else None
        baseline_avg = statistics.mean(baseline_sleep_values) if baseline_sleep_values else None
        
        delta = None
        delta_pct = None
        if current_avg is not None and baseline_avg is not None and baseline_avg > 0:
            delta = current_avg - baseline_avg
            delta_pct = (delta / baseline_avg) * 100
        
        has_sufficient = (
            len(current_sleep) >= MIN_DATA_POINTS[InputCategory.SLEEP] and
            len(baseline_sleep_values) >= MIN_DATA_POINTS[InputCategory.SLEEP]
        )
        
        return [InputDelta(
            category=InputCategory.SLEEP,
            name="Sleep Duration",
            icon="😴",
            current_value=current_avg,
            baseline_value=baseline_avg,
            delta=delta,
            delta_pct=delta_pct,
            unit="hours/night",
            data_points_current=len(current_sleep),
            data_points_baseline=len(baseline_sleep_values),
            has_sufficient_data=has_sufficient,
        )]
    
    def _get_sleep_data(self, start: date, end: date) -> List[float]:
        """Get sleep hours for a date range"""
        checkins = self.db.query(DailyCheckin.sleep_h).filter(
            DailyCheckin.athlete_id == self.athlete_id,
            DailyCheckin.date >= start,
            DailyCheckin.date <= end,
            DailyCheckin.sleep_h.isnot(None),
        ).all()
        return [float(c.sleep_h) for c in checkins]


class RecoveryAnalyzer(InputAnalyzer):
    """Analyze HRV, stress, soreness metrics"""
    
    def analyze(
        self, 
        current_date: date, 
        baseline_dates: List[date],
        window_days: int = 7
    ) -> List[InputDelta]:
        deltas = []
        
        # Current period
        current_start = current_date - timedelta(days=window_days)
        current_data = self._get_recovery_data(current_start, current_date)
        
        # Baseline period
        baseline_data = {"stress": [], "soreness": [], "hrv": [], "rhr": []}
        for bd in baseline_dates:
            bs_start = bd - timedelta(days=window_days)
            bs_data = self._get_recovery_data(bs_start, bd)
            for key in baseline_data:
                baseline_data[key].extend(bs_data.get(key, []))
        
        # Stress (lower is better)
        if current_data.get("stress") or baseline_data.get("stress"):
            current_stress = statistics.mean(current_data["stress"]) if current_data["stress"] else None
            baseline_stress = statistics.mean(baseline_data["stress"]) if baseline_data["stress"] else None
            delta = None
            delta_pct = None
            if current_stress and baseline_stress and baseline_stress > 0:
                delta = current_stress - baseline_stress
                delta_pct = (delta / baseline_stress) * 100
            
            deltas.append(InputDelta(
                category=InputCategory.RECOVERY,
                name="Stress Level",
                icon="😤",
                current_value=current_stress,
                baseline_value=baseline_stress,
                delta=delta,
                delta_pct=delta_pct,
                unit="(1-5 scale)",
                data_points_current=len(current_data.get("stress", [])),
                data_points_baseline=len(baseline_data.get("stress", [])),
                has_sufficient_data=(
                    len(current_data.get("stress", [])) >= MIN_DATA_POINTS[InputCategory.RECOVERY] and
                    len(baseline_data.get("stress", [])) >= MIN_DATA_POINTS[InputCategory.RECOVERY]
                ),
            ))
        
        # Soreness (lower is better)
        if current_data.get("soreness") or baseline_data.get("soreness"):
            current_soreness = statistics.mean(current_data["soreness"]) if current_data["soreness"] else None
            baseline_soreness = statistics.mean(baseline_data["soreness"]) if baseline_data["soreness"] else None
            delta = None
            delta_pct = None
            if current_soreness and baseline_soreness and baseline_soreness > 0:
                delta = current_soreness - baseline_soreness
                delta_pct = (delta / baseline_soreness) * 100
            
            deltas.append(InputDelta(
                category=InputCategory.RECOVERY,
                name="Soreness",
                icon="🦵",
                current_value=current_soreness,
                baseline_value=baseline_soreness,
                delta=delta,
                delta_pct=delta_pct,
                unit="(1-5 scale)",
                data_points_current=len(current_data.get("soreness", [])),
                data_points_baseline=len(baseline_data.get("soreness", [])),
                has_sufficient_data=(
                    len(current_data.get("soreness", [])) >= MIN_DATA_POINTS[InputCategory.RECOVERY] and
                    len(baseline_data.get("soreness", [])) >= MIN_DATA_POINTS[InputCategory.RECOVERY]
                ),
            ))
        
        # HRV (higher is better)
        if current_data.get("hrv") or baseline_data.get("hrv"):
            current_hrv = statistics.mean(current_data["hrv"]) if current_data["hrv"] else None
            baseline_hrv = statistics.mean(baseline_data["hrv"]) if baseline_data["hrv"] else None
            delta = None
            delta_pct = None
            if current_hrv and baseline_hrv and baseline_hrv > 0:
                delta = current_hrv - baseline_hrv
                delta_pct = (delta / baseline_hrv) * 100
            
            deltas.append(InputDelta(
                category=InputCategory.RECOVERY,
                name="HRV",
                icon="💓",
                current_value=current_hrv,
                baseline_value=baseline_hrv,
                delta=delta,
                delta_pct=delta_pct,
                unit="ms (rMSSD)",
                data_points_current=len(current_data.get("hrv", [])),
                data_points_baseline=len(baseline_data.get("hrv", [])),
                has_sufficient_data=(
                    len(current_data.get("hrv", [])) >= MIN_DATA_POINTS[InputCategory.RECOVERY] and
                    len(baseline_data.get("hrv", [])) >= MIN_DATA_POINTS[InputCategory.RECOVERY]
                ),
            ))
        
        return deltas
    
    def _get_recovery_data(self, start: date, end: date) -> Dict[str, List[float]]:
        """Get recovery metrics for a date range"""
        checkins = self.db.query(
            DailyCheckin.stress_1_5,
            DailyCheckin.soreness_1_5,
            DailyCheckin.hrv_rmssd,
            DailyCheckin.resting_hr,
        ).filter(
            DailyCheckin.athlete_id == self.athlete_id,
            DailyCheckin.date >= start,
            DailyCheckin.date <= end,
        ).all()
        
        result = {"stress": [], "soreness": [], "hrv": [], "rhr": []}
        for c in checkins:
            if c.stress_1_5:
                result["stress"].append(float(c.stress_1_5))
            if c.soreness_1_5:
                result["soreness"].append(float(c.soreness_1_5))
            if c.hrv_rmssd:
                result["hrv"].append(float(c.hrv_rmssd))
            if c.resting_hr:
                result["rhr"].append(float(c.resting_hr))
        return result


class BodyCompositionAnalyzer(InputAnalyzer):
    """Analyze BMI and weight trends"""
    
    def analyze(
        self, 
        current_date: date, 
        baseline_dates: List[date],
        window_days: int = 14
    ) -> List[InputDelta]:
        deltas = []
        
        # Current period
        current_start = current_date - timedelta(days=window_days)
        current_data = self._get_body_data(current_start, current_date)
        
        # Baseline period
        baseline_bmi = []
        baseline_weight = []
        for bd in baseline_dates:
            bs_start = bd - timedelta(days=window_days)
            bs_data = self._get_body_data(bs_start, bd)
            baseline_bmi.extend(bs_data.get("bmi", []))
            baseline_weight.extend(bs_data.get("weight", []))
        
        # BMI
        if current_data.get("bmi") or baseline_bmi:
            current_bmi = statistics.mean(current_data["bmi"]) if current_data.get("bmi") else None
            baseline_bmi_avg = statistics.mean(baseline_bmi) if baseline_bmi else None
            delta = None
            delta_pct = None
            if current_bmi and baseline_bmi_avg and baseline_bmi_avg > 0:
                delta = current_bmi - baseline_bmi_avg
                delta_pct = (delta / baseline_bmi_avg) * 100
            
            deltas.append(InputDelta(
                category=InputCategory.BODY_COMPOSITION,
                name="BMI",
                icon="⚖️",
                current_value=current_bmi,
                baseline_value=baseline_bmi_avg,
                delta=delta,
                delta_pct=delta_pct,
                unit="",  # BMI is unitless
                data_points_current=len(current_data.get("bmi", [])),
                data_points_baseline=len(baseline_bmi),
                has_sufficient_data=(
                    len(current_data.get("bmi", [])) >= MIN_DATA_POINTS[InputCategory.BODY_COMPOSITION] and
                    len(baseline_bmi) >= MIN_DATA_POINTS[InputCategory.BODY_COMPOSITION]
                ),
            ))
        
        # Weight
        if current_data.get("weight") or baseline_weight:
            current_weight = statistics.mean(current_data["weight"]) if current_data.get("weight") else None
            baseline_weight_avg = statistics.mean(baseline_weight) if baseline_weight else None
            delta = None
            delta_pct = None
            if current_weight and baseline_weight_avg and baseline_weight_avg > 0:
                delta = current_weight - baseline_weight_avg
                delta_pct = (delta / baseline_weight_avg) * 100
            
            deltas.append(InputDelta(
                category=InputCategory.BODY_COMPOSITION,
                name="Weight",
                icon="🏋️",
                current_value=current_weight,
                baseline_value=baseline_weight_avg,
                delta=delta,
                delta_pct=delta_pct,
                unit="kg",
                data_points_current=len(current_data.get("weight", [])),
                data_points_baseline=len(baseline_weight),
                has_sufficient_data=(
                    len(current_data.get("weight", [])) >= MIN_DATA_POINTS[InputCategory.BODY_COMPOSITION] and
                    len(baseline_weight) >= MIN_DATA_POINTS[InputCategory.BODY_COMPOSITION]
                ),
            ))
        
        return deltas
    
    def _get_body_data(self, start: date, end: date) -> Dict[str, List[float]]:
        """Get body composition data for a date range"""
        records = self.db.query(
            BodyComposition.bmi,
            BodyComposition.weight_kg,
        ).filter(
            BodyComposition.athlete_id == self.athlete_id,
            BodyComposition.date >= start,
            BodyComposition.date <= end,
        ).all()
        
        result = {"bmi": [], "weight": []}
        for r in records:
            if r.bmi:
                result["bmi"].append(float(r.bmi))
            if r.weight_kg:
                result["weight"].append(float(r.weight_kg))
        return result


class VolumeAnalyzer(InputAnalyzer):
    """Analyze training volume (mileage)"""
    
    def analyze(
        self, 
        current_date: date, 
        baseline_dates: List[date],
        window_days: int = 28
    ) -> List[InputDelta]:
        
        # Current period
        current_start = current_date - timedelta(days=window_days)
        current_volume = self._get_volume_data(current_start, current_date, window_days)
        
        # Baseline period (average across all baseline windows)
        baseline_volumes = []
        for bd in baseline_dates:
            bs_start = bd - timedelta(days=window_days)
            bv = self._get_volume_data(bs_start, bd, window_days)
            if bv.get("weekly_km"):
                baseline_volumes.append(bv["weekly_km"])
        
        baseline_weekly_avg = statistics.mean(baseline_volumes) if baseline_volumes else None
        
        delta = None
        delta_pct = None
        if current_volume.get("weekly_km") and baseline_weekly_avg and baseline_weekly_avg > 0:
            delta = current_volume["weekly_km"] - baseline_weekly_avg
            delta_pct = (delta / baseline_weekly_avg) * 100
        
        return [InputDelta(
            category=InputCategory.VOLUME,
            name="Weekly Volume",
            icon="📏",
            current_value=current_volume.get("weekly_km"),
            baseline_value=baseline_weekly_avg,
            delta=delta,
            delta_pct=delta_pct,
            unit="km/week",
            data_points_current=current_volume.get("runs", 0),
            data_points_baseline=len(baseline_volumes) * current_volume.get("runs", 1),
            has_sufficient_data=(
                current_volume.get("runs", 0) >= MIN_DATA_POINTS[InputCategory.VOLUME] and
                len(baseline_volumes) >= 1
            ),
        )]
    
    def _get_volume_data(self, start: date, end: date, window_days: int) -> Dict[str, Any]:
        """Get volume metrics for a date range"""
        activities = self.db.query(
            func.sum(Activity.distance_m).label("total_distance"),
            func.count(Activity.id).label("run_count"),
        ).filter(
            Activity.athlete_id == self.athlete_id,
            func.date(Activity.start_time) >= start,
            func.date(Activity.start_time) <= end,
            Activity.activity_type == "Run",
        ).first()
        
        total_km = float(activities.total_distance) / 1000 if activities.total_distance else 0
        run_count = activities.run_count or 0
        weeks = max(1, window_days / 7)
        
        return {
            "total_km": total_km,
            "weekly_km": total_km / weeks,
            "runs": run_count,
        }


class ConsistencyAnalyzer(InputAnalyzer):
    """Analyze training consistency (runs per week)"""
    
    def analyze(
        self, 
        current_date: date, 
        baseline_dates: List[date],
        window_days: int = 28
    ) -> List[InputDelta]:
        
        # Current period
        current_start = current_date - timedelta(days=window_days)
        current_consistency = self._get_consistency_data(current_start, current_date, window_days)
        
        # Baseline period
        baseline_consistencies = []
        for bd in baseline_dates:
            bs_start = bd - timedelta(days=window_days)
            bc = self._get_consistency_data(bs_start, bd, window_days)
            if bc.get("runs_per_week") is not None:
                baseline_consistencies.append(bc["runs_per_week"])
        
        baseline_avg = statistics.mean(baseline_consistencies) if baseline_consistencies else None
        
        delta = None
        delta_pct = None
        if current_consistency.get("runs_per_week") and baseline_avg and baseline_avg > 0:
            delta = current_consistency["runs_per_week"] - baseline_avg
            delta_pct = (delta / baseline_avg) * 100
        
        return [InputDelta(
            category=InputCategory.CONSISTENCY,
            name="Consistency",
            icon="📅",
            current_value=current_consistency.get("runs_per_week"),
            baseline_value=baseline_avg,
            delta=delta,
            delta_pct=delta_pct,
            unit="runs/week",
            data_points_current=current_consistency.get("total_runs", 0),
            data_points_baseline=sum(1 for _ in baseline_consistencies),
            has_sufficient_data=(
                current_consistency.get("total_runs", 0) >= MIN_DATA_POINTS[InputCategory.CONSISTENCY] and
                len(baseline_consistencies) >= 1
            ),
        )]
    
    def _get_consistency_data(self, start: date, end: date, window_days: int) -> Dict[str, Any]:
        """Get consistency metrics for a date range"""
        run_count = self.db.query(func.count(Activity.id)).filter(
            Activity.athlete_id == self.athlete_id,
            func.date(Activity.start_time) >= start,
            func.date(Activity.start_time) <= end,
            Activity.activity_type == "Run",
        ).scalar() or 0
        
        weeks = max(1, window_days / 7)
        
        return {
            "total_runs": run_count,
            "runs_per_week": run_count / weeks,
        }


class TrainingMixAnalyzer(InputAnalyzer):
    """Analyze distribution of workout types"""
    
    WORKOUT_TYPES = {
        "threshold": ["tempo", "threshold", "tempo_run", "cruise_intervals"],
        "intervals": ["intervals", "vo2max", "speed", "track", "fartlek"],
        "long": ["long", "long_run", "endurance"],
        "easy": ["easy", "easy_run", "recovery", "base"],
    }
    
    def analyze(
        self, 
        current_date: date, 
        baseline_dates: List[date],
        window_days: int = 28
    ) -> List[InputDelta]:
        deltas = []
        
        # Current period
        current_start = current_date - timedelta(days=window_days)
        current_mix = self._get_mix_data(current_start, current_date)
        
        # Baseline period
        baseline_mixes = {k: [] for k in self.WORKOUT_TYPES}
        for bd in baseline_dates:
            bs_start = bd - timedelta(days=window_days)
            bm = self._get_mix_data(bs_start, bd)
            for wt in self.WORKOUT_TYPES:
                if bm.get(wt) is not None:
                    baseline_mixes[wt].append(bm[wt])
        
        # Calculate deltas for each workout type
        icons = {
            "threshold": "🔥",
            "intervals": "⚡",
            "long": "🛤️",
            "easy": "🚶",
        }
        names = {
            "threshold": "Threshold Work",
            "intervals": "Interval Work",
            "long": "Long Runs",
            "easy": "Easy Runs",
        }
        
        for wt in self.WORKOUT_TYPES:
            current_pct = current_mix.get(wt)
            baseline_pct = statistics.mean(baseline_mixes[wt]) if baseline_mixes[wt] else None
            
            delta = None
            delta_pct = None
            if current_pct is not None and baseline_pct is not None:
                delta = current_pct - baseline_pct
                # Delta is already in percentage points
                delta_pct = delta  # For mix, delta IS the percentage point change
            
            deltas.append(InputDelta(
                category=InputCategory.TRAINING_MIX,
                name=names[wt],
                icon=icons[wt],
                current_value=current_pct,
                baseline_value=baseline_pct,
                delta=delta,
                delta_pct=delta_pct,
                unit="% of volume",
                data_points_current=current_mix.get("total_runs", 0),
                data_points_baseline=len(baseline_mixes[wt]),
                has_sufficient_data=(
                    current_mix.get("total_runs", 0) >= MIN_DATA_POINTS[InputCategory.TRAINING_MIX] and
                    len(baseline_mixes[wt]) >= 1
                ),
            ))
        
        return deltas
    
    def _get_mix_data(self, start: date, end: date) -> Dict[str, Any]:
        """Get workout type distribution for a date range"""
        activities = self.db.query(
            Activity.workout_type,
            Activity.distance_m,
        ).filter(
            Activity.athlete_id == self.athlete_id,
            func.date(Activity.start_time) >= start,
            func.date(Activity.start_time) <= end,
            Activity.activity_type == "Run",
        ).all()
        
        if not activities:
            return {}
        
        total_distance = sum(a.distance_m or 0 for a in activities)
        if total_distance == 0:
            return {"total_runs": len(activities)}
        
        # Categorize each activity
        type_distances = {k: 0 for k in self.WORKOUT_TYPES}
        for a in activities:
            wt = (a.workout_type or "easy").lower()
            for category, keywords in self.WORKOUT_TYPES.items():
                if any(kw in wt for kw in keywords):
                    type_distances[category] += a.distance_m or 0
                    break
            else:
                type_distances["easy"] += a.distance_m or 0
        
        # Convert to percentages
        result = {"total_runs": len(activities)}
        for category, distance in type_distances.items():
            result[category] = (distance / total_distance) * 100
        
        return result


class MindsetAnalyzer(InputAnalyzer):
    """Analyze confidence and motivation"""
    
    def analyze(
        self, 
        current_date: date, 
        baseline_dates: List[date],
        window_days: int = 7
    ) -> List[InputDelta]:
        deltas = []
        
        # Current period
        current_start = current_date - timedelta(days=window_days)
        current_data = self._get_mindset_data(current_start, current_date)
        
        # Baseline period
        baseline_confidence = []
        baseline_motivation = []
        for bd in baseline_dates:
            bs_start = bd - timedelta(days=window_days)
            bd_data = self._get_mindset_data(bs_start, bd)
            baseline_confidence.extend(bd_data.get("confidence", []))
            baseline_motivation.extend(bd_data.get("motivation", []))
        
        # Confidence
        if current_data.get("confidence") or baseline_confidence:
            current_conf = statistics.mean(current_data["confidence"]) if current_data.get("confidence") else None
            baseline_conf = statistics.mean(baseline_confidence) if baseline_confidence else None
            delta = None
            delta_pct = None
            if current_conf and baseline_conf and baseline_conf > 0:
                delta = current_conf - baseline_conf
                delta_pct = (delta / baseline_conf) * 100
            
            deltas.append(InputDelta(
                category=InputCategory.MINDSET,
                name="Confidence",
                icon="💪",
                current_value=current_conf,
                baseline_value=baseline_conf,
                delta=delta,
                delta_pct=delta_pct,
                unit="(1-5 scale)",
                data_points_current=len(current_data.get("confidence", [])),
                data_points_baseline=len(baseline_confidence),
                has_sufficient_data=(
                    len(current_data.get("confidence", [])) >= MIN_DATA_POINTS[InputCategory.MINDSET] and
                    len(baseline_confidence) >= MIN_DATA_POINTS[InputCategory.MINDSET]
                ),
            ))
        
        # Motivation
        if current_data.get("motivation") or baseline_motivation:
            current_mot = statistics.mean(current_data["motivation"]) if current_data.get("motivation") else None
            baseline_mot = statistics.mean(baseline_motivation) if baseline_motivation else None
            delta = None
            delta_pct = None
            if current_mot and baseline_mot and baseline_mot > 0:
                delta = current_mot - baseline_mot
                delta_pct = (delta / baseline_mot) * 100
            
            deltas.append(InputDelta(
                category=InputCategory.MINDSET,
                name="Motivation",
                icon="🔥",
                current_value=current_mot,
                baseline_value=baseline_mot,
                delta=delta,
                delta_pct=delta_pct,
                unit="(1-5 scale)",
                data_points_current=len(current_data.get("motivation", [])),
                data_points_baseline=len(baseline_motivation),
                has_sufficient_data=(
                    len(current_data.get("motivation", [])) >= MIN_DATA_POINTS[InputCategory.MINDSET] and
                    len(baseline_motivation) >= MIN_DATA_POINTS[InputCategory.MINDSET]
                ),
            ))
        
        return deltas
    
    def _get_mindset_data(self, start: date, end: date) -> Dict[str, List[float]]:
        """Get mindset metrics for a date range"""
        checkins = self.db.query(
            DailyCheckin.confidence_1_5,
            DailyCheckin.motivation_1_5,
        ).filter(
            DailyCheckin.athlete_id == self.athlete_id,
            DailyCheckin.date >= start,
            DailyCheckin.date <= end,
        ).all()
        
        result = {"confidence": [], "motivation": []}
        for c in checkins:
            if c.confidence_1_5:
                result["confidence"].append(float(c.confidence_1_5))
            if c.motivation_1_5:
                result["motivation"].append(float(c.motivation_1_5))
        return result


class NutritionAnalyzer(InputAnalyzer):
    """Analyze nutrition patterns"""
    
    def analyze(
        self, 
        current_date: date, 
        baseline_dates: List[date],
        window_days: int = 3
    ) -> List[InputDelta]:
        deltas = []
        
        # Current period
        current_start = current_date - timedelta(days=window_days)
        current_data = self._get_nutrition_data(current_start, current_date)
        
        # Baseline period
        baseline_data = {"calories": [], "protein": [], "carbs": []}
        for bd in baseline_dates:
            bs_start = bd - timedelta(days=window_days)
            bd_data = self._get_nutrition_data(bs_start, bd)
            for key in baseline_data:
                baseline_data[key].extend(bd_data.get(key, []))
        
        # Daily calories
        if current_data.get("calories") or baseline_data.get("calories"):
            current_cal = statistics.mean(current_data["calories"]) if current_data.get("calories") else None
            baseline_cal = statistics.mean(baseline_data["calories"]) if baseline_data.get("calories") else None
            delta = None
            delta_pct = None
            if current_cal and baseline_cal and baseline_cal > 0:
                delta = current_cal - baseline_cal
                delta_pct = (delta / baseline_cal) * 100
            
            deltas.append(InputDelta(
                category=InputCategory.NUTRITION,
                name="Daily Calories",
                icon="🍽️",
                current_value=current_cal,
                baseline_value=baseline_cal,
                delta=delta,
                delta_pct=delta_pct,
                unit="kcal/day",
                data_points_current=len(current_data.get("calories", [])),
                data_points_baseline=len(baseline_data.get("calories", [])),
                has_sufficient_data=(
                    len(current_data.get("calories", [])) >= MIN_DATA_POINTS[InputCategory.NUTRITION] and
                    len(baseline_data.get("calories", [])) >= MIN_DATA_POINTS[InputCategory.NUTRITION]
                ),
            ))
        
        # Protein
        if current_data.get("protein") or baseline_data.get("protein"):
            current_prot = statistics.mean(current_data["protein"]) if current_data.get("protein") else None
            baseline_prot = statistics.mean(baseline_data["protein"]) if baseline_data.get("protein") else None
            delta = None
            delta_pct = None
            if current_prot and baseline_prot and baseline_prot > 0:
                delta = current_prot - baseline_prot
                delta_pct = (delta / baseline_prot) * 100
            
            deltas.append(InputDelta(
                category=InputCategory.NUTRITION,
                name="Protein Intake",
                icon="🥩",
                current_value=current_prot,
                baseline_value=baseline_prot,
                delta=delta,
                delta_pct=delta_pct,
                unit="g/day",
                data_points_current=len(current_data.get("protein", [])),
                data_points_baseline=len(baseline_data.get("protein", [])),
                has_sufficient_data=(
                    len(current_data.get("protein", [])) >= MIN_DATA_POINTS[InputCategory.NUTRITION] and
                    len(baseline_data.get("protein", [])) >= MIN_DATA_POINTS[InputCategory.NUTRITION]
                ),
            ))
        
        # Carbs
        if current_data.get("carbs") or baseline_data.get("carbs"):
            current_carb = statistics.mean(current_data["carbs"]) if current_data.get("carbs") else None
            baseline_carb = statistics.mean(baseline_data["carbs"]) if baseline_data.get("carbs") else None
            delta = None
            delta_pct = None
            if current_carb and baseline_carb and baseline_carb > 0:
                delta = current_carb - baseline_carb
                delta_pct = (delta / baseline_carb) * 100
            
            deltas.append(InputDelta(
                category=InputCategory.NUTRITION,
                name="Carb Intake",
                icon="🍞",
                current_value=current_carb,
                baseline_value=baseline_carb,
                delta=delta,
                delta_pct=delta_pct,
                unit="g/day",
                data_points_current=len(current_data.get("carbs", [])),
                data_points_baseline=len(baseline_data.get("carbs", [])),
                has_sufficient_data=(
                    len(current_data.get("carbs", [])) >= MIN_DATA_POINTS[InputCategory.NUTRITION] and
                    len(baseline_data.get("carbs", [])) >= MIN_DATA_POINTS[InputCategory.NUTRITION]
                ),
            ))
        
        return deltas
    
    def _get_nutrition_data(self, start: date, end: date) -> Dict[str, List[float]]:
        """Get nutrition data for a date range (daily totals)"""
        # Sum nutrition per day
        daily_totals = self.db.query(
            NutritionEntry.date,
            func.sum(NutritionEntry.calories).label("calories"),
            func.sum(NutritionEntry.protein_g).label("protein"),
            func.sum(NutritionEntry.carbs_g).label("carbs"),
        ).filter(
            NutritionEntry.athlete_id == self.athlete_id,
            NutritionEntry.date >= start,
            NutritionEntry.date <= end,
        ).group_by(NutritionEntry.date).all()
        
        result = {"calories": [], "protein": [], "carbs": []}
        for day in daily_totals:
            if day.calories:
                result["calories"].append(float(day.calories))
            if day.protein:
                result["protein"].append(float(day.protein))
            if day.carbs:
                result["carbs"].append(float(day.carbs))
        return result


# =============================================================================
# ATTRIBUTION SCORER
# =============================================================================

class AttributionScorer:
    """
    Score which input deltas most likely drove the performance change.
    
    Uses a simple but defensible approach:
    1. Rank by magnitude of change (what changed most?)
    2. Weight by direction alignment (does direction match performance direction?)
    3. Adjust by known physiological relationships
    """
    
    # Weights for different input categories (based on sports science evidence)
    # Higher = more likely to impact short-term performance
    CATEGORY_WEIGHTS = {
        InputCategory.SLEEP: 0.9,           # Sleep is huge for recovery
        InputCategory.RECOVERY: 0.85,        # HRV/stress are leading indicators
        InputCategory.TRAINING_MIX: 0.8,     # Training specificity matters
        InputCategory.VOLUME: 0.75,          # Volume drives fitness
        InputCategory.CONSISTENCY: 0.7,      # Consistency is key
        InputCategory.BODY_COMPOSITION: 0.6, # Weight affects running economy
        InputCategory.MINDSET: 0.55,         # Mental state affects effort
        InputCategory.NUTRITION: 0.5,        # Fueling has acute effects
    }
    
    # For each input, positive delta is good (+1) or bad (-1)?
    # e.g., more sleep (+) is good (+1), more stress (+) is bad (-1)
    POSITIVE_DIRECTION = {
        "Sleep Duration": 1,      # More sleep = better
        "Stress Level": -1,       # Less stress = better
        "Soreness": -1,           # Less soreness = better
        "HRV": 1,                  # Higher HRV = better
        "BMI": -1,                 # Lower BMI = better (for running)
        "Weight": -1,             # Lower weight = better (for running)
        "Weekly Volume": 1,       # More volume = better (generally)
        "Consistency": 1,         # More consistent = better
        "Threshold Work": 1,      # More quality = better
        "Interval Work": 1,       # More quality = better
        "Long Runs": 1,           # More endurance = better
        "Easy Runs": 0,           # Neutral - depends on context
        "Confidence": 1,          # Higher confidence = better
        "Motivation": 1,          # Higher motivation = better
        "Daily Calories": 0,      # Neutral - could go either way
        "Protein Intake": 1,      # More protein = better recovery
        "Carb Intake": 0,         # Neutral - depends on timing
    }
    
    def score_drivers(
        self,
        input_deltas: List[InputDelta],
        performance_delta: float,  # Positive = improved
    ) -> List[PerformanceDriver]:
        """
        Score each input delta and convert to PerformanceDriver.
        """
        drivers = []
        
        for delta in input_deltas:
            if not delta.has_sufficient_data:
                continue
            if delta.delta is None or delta.delta == 0:
                continue
            
            # Calculate contribution score
            contribution = self._calculate_contribution(delta, performance_delta)
            
            # Determine direction
            direction = self._determine_direction(delta, performance_delta)
            
            # Calculate confidence
            confidence = self._calculate_confidence(delta, contribution)
            
            # Generate insight
            insight = self._generate_insight(delta, direction, confidence)
            
            # Format magnitude
            magnitude = self._format_magnitude(delta)
            
            drivers.append(PerformanceDriver(
                category=delta.category,
                name=delta.name,
                icon=delta.icon,
                direction=direction,
                magnitude=magnitude,
                contribution_score=contribution,
                confidence=confidence,
                insight=insight,
                delta=delta,
            ))
        
        # Sort by contribution score
        drivers.sort(key=lambda d: d.contribution_score, reverse=True)
        
        return drivers
    
    def _calculate_contribution(
        self, 
        delta: InputDelta, 
        performance_delta: float
    ) -> float:
        """
        Calculate how much this input likely contributed to the performance change.
        
        Score = |delta_pct| * category_weight * direction_alignment
        """
        if delta.delta_pct is None:
            return 0.0
        
        # Base: magnitude of change
        magnitude = min(abs(delta.delta_pct) / 100, 1.0)  # Cap at 100%
        
        # Category weight
        cat_weight = self.CATEGORY_WEIGHTS.get(delta.category, 0.5)
        
        # Direction alignment: does the input change direction match performance direction?
        pos_dir = self.POSITIVE_DIRECTION.get(delta.name, 0)
        if pos_dir != 0:
            # Input says positive delta should improve performance
            input_helps = (delta.delta > 0 and pos_dir > 0) or (delta.delta < 0 and pos_dir < 0)
            perf_improved = performance_delta > 0
            
            # If input and performance align, boost score
            if input_helps == perf_improved:
                alignment = 1.2
            else:
                alignment = 0.5
        else:
            alignment = 1.0  # Neutral inputs
        
        score = magnitude * cat_weight * alignment
        return min(score, 1.0)
    
    def _determine_direction(
        self, 
        delta: InputDelta, 
        performance_delta: float
    ) -> DriverDirection:
        """Determine if this input helped or hurt performance."""
        if delta.delta is None:
            return DriverDirection.NEUTRAL
        
        pos_dir = self.POSITIVE_DIRECTION.get(delta.name, 0)
        
        if pos_dir == 0:
            return DriverDirection.NEUTRAL
        
        # Did the input move in a "good" direction?
        input_improved = (delta.delta > 0 and pos_dir > 0) or (delta.delta < 0 and pos_dir < 0)
        
        if input_improved:
            return DriverDirection.POSITIVE
        else:
            return DriverDirection.NEGATIVE
    
    def _calculate_confidence(
        self, 
        delta: InputDelta, 
        contribution: float
    ) -> Confidence:
        """Calculate confidence level for this attribution."""
        # Factors: data points, magnitude, known relationship
        
        data_score = min(delta.data_points_current, delta.data_points_baseline) / 10
        magnitude_score = min(abs(delta.delta_pct or 0) / 50, 1.0)
        
        combined = (data_score * 0.4) + (contribution * 0.4) + (magnitude_score * 0.2)
        
        if combined > 0.7:
            return Confidence.HIGH
        elif combined > 0.4:
            return Confidence.MODERATE
        elif combined > 0.2:
            return Confidence.LOW
        else:
            return Confidence.INSUFFICIENT
    
    def _generate_insight(
        self, 
        delta: InputDelta, 
        direction: DriverDirection, 
        confidence: Confidence
    ) -> str:
        """Generate sparse, manifesto-aligned insight text."""
        magnitude = self._format_magnitude(delta)
        
        if confidence == Confidence.INSUFFICIENT:
            return f"{delta.name} changed but needs more data."
        
        # Sparse, data-first language
        if direction == DriverDirection.POSITIVE:
            templates = [
                f"{delta.name} {magnitude}. Data pattern: positive.",
                f"{magnitude} on {delta.name.lower()}. Correlates with improvement.",
                f"{delta.name}: {magnitude}. Probably helped.",
            ]
        elif direction == DriverDirection.NEGATIVE:
            templates = [
                f"{delta.name} {magnitude}. Worth investigating.",
                f"{magnitude} on {delta.name.lower()}. May have been a drag.",
                f"{delta.name}: {magnitude}. Potential limiter.",
            ]
        else:
            templates = [
                f"{delta.name} {magnitude}. Impact unclear.",
                f"{magnitude} on {delta.name.lower()}. Neutral correlation.",
            ]
        
        # Pick based on hash for consistency
        idx = hash(delta.name) % len(templates)
        return templates[idx]
    
    def _format_magnitude(self, delta: InputDelta) -> str:
        """Format the magnitude of change for display."""
        if delta.delta is None:
            return "no change"
        
        sign = "+" if delta.delta > 0 else ""
        
        # Format based on unit
        if delta.unit in ["hours/night", "km/week"]:
            return f"{sign}{delta.delta:.1f} {delta.unit}"
        elif delta.unit == "runs/week":
            return f"{sign}{delta.delta:.1f} {delta.unit}"
        elif delta.unit == "% of volume":
            return f"{sign}{delta.delta:.0f} percentage points"
        elif delta.unit in ["(1-5 scale)"]:
            return f"{sign}{delta.delta:.1f} on 5-point scale"
        elif delta.unit == "kg":
            return f"{sign}{delta.delta:.1f}kg"
        elif delta.unit == "":  # BMI
            return f"{sign}{delta.delta:.1f}"
        elif delta.unit == "kcal/day":
            return f"{sign}{delta.delta:.0f} kcal/day"
        elif delta.unit in ["g/day"]:
            return f"{sign}{delta.delta:.0f}g/day"
        elif delta.unit == "ms (rMSSD)":
            return f"{sign}{delta.delta:.1f}ms HRV"
        else:
            return f"{sign}{delta.delta:.1f} {delta.unit}"


# =============================================================================
# MAIN SERVICE
# =============================================================================

class AttributionEngineService:
    """
    The core Attribution Engine.
    
    Analyzes trailing inputs to explain why performance changed.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.scorer = AttributionScorer()
    
    def analyze_performance_drivers(
        self,
        current_activity_id: UUID,
        baseline_activity_ids: List[UUID],
        athlete_id: UUID,
        performance_delta: Optional[float] = None,
    ) -> AttributionResult:
        """
        Main entry point: analyze what drove the performance change.
        
        Args:
            current_activity_id: The run we're analyzing
            baseline_activity_ids: The comparison runs (ghost set)
            athlete_id: The athlete
            performance_delta: Optional pre-calculated performance difference (%)
        
        Returns:
            Complete attribution analysis
        """
        # Get activity dates
        current_activity = self.db.query(Activity).filter(
            Activity.id == current_activity_id,
            Activity.athlete_id == athlete_id,
        ).first()
        
        if not current_activity:
            raise ValueError("Current activity not found")
        
        baseline_activities = self.db.query(Activity).filter(
            Activity.id.in_(baseline_activity_ids),
            Activity.athlete_id == athlete_id,
        ).all()
        
        if not baseline_activities:
            raise ValueError("No baseline activities found")
        
        current_date = current_activity.start_time.date()
        baseline_dates = [a.start_time.date() for a in baseline_activities]
        
        # Calculate performance delta if not provided
        if performance_delta is None:
            performance_delta = self._calculate_performance_delta(
                current_activity, baseline_activities
            )
        
        # Run all analyzers
        all_deltas = []
        analyzers = [
            (SleepAnalyzer, TRAILING_WINDOWS[InputCategory.SLEEP]),
            (RecoveryAnalyzer, TRAILING_WINDOWS[InputCategory.RECOVERY]),
            (BodyCompositionAnalyzer, TRAILING_WINDOWS[InputCategory.BODY_COMPOSITION]),
            (VolumeAnalyzer, TRAILING_WINDOWS[InputCategory.VOLUME]),
            (ConsistencyAnalyzer, TRAILING_WINDOWS[InputCategory.CONSISTENCY]),
            (TrainingMixAnalyzer, TRAILING_WINDOWS[InputCategory.TRAINING_MIX]),
            (MindsetAnalyzer, TRAILING_WINDOWS[InputCategory.MINDSET]),
            (NutritionAnalyzer, TRAILING_WINDOWS[InputCategory.NUTRITION]),
        ]
        
        for analyzer_cls, window in analyzers:
            analyzer = analyzer_cls(self.db, athlete_id)
            try:
                deltas = analyzer.analyze(current_date, baseline_dates, window)
                all_deltas.extend(deltas)
            except Exception as e:
                # Log but don't fail
                print(f"Warning: {analyzer_cls.__name__} failed: {e}")
                continue
        
        # Score drivers
        key_drivers = self.scorer.score_drivers(all_deltas, performance_delta)
        
        # Generate summaries
        summary_positive, summary_negative = self._generate_summaries(key_drivers)
        
        # Calculate data quality
        data_quality = self._calculate_data_quality(all_deltas)
        
        # Overall confidence
        if key_drivers:
            high_conf = sum(1 for d in key_drivers[:3] if d.confidence in [Confidence.HIGH, Confidence.MODERATE])
            if high_conf >= 2:
                overall_confidence = Confidence.MODERATE
            elif high_conf >= 1:
                overall_confidence = Confidence.LOW
            else:
                overall_confidence = Confidence.INSUFFICIENT
        else:
            overall_confidence = Confidence.INSUFFICIENT
        
        # Determine performance direction
        if performance_delta > 3:
            perf_direction = "improved"
        elif performance_delta < -3:
            perf_direction = "declined"
        else:
            perf_direction = "stable"
        
        # Calculate period bounds
        max_window = max(TRAILING_WINDOWS.values())
        current_period = (
            current_date - timedelta(days=max_window),
            current_date,
        )
        baseline_period = (
            min(baseline_dates) - timedelta(days=max_window),
            max(baseline_dates),
        )
        
        return AttributionResult(
            performance_delta=performance_delta,
            performance_direction=perf_direction,
            input_deltas=all_deltas,
            key_drivers=key_drivers[:5],  # Top 5 drivers
            summary_positive=summary_positive,
            summary_negative=summary_negative,
            overall_confidence=overall_confidence,
            current_period=current_period,
            baseline_period=baseline_period,
            data_quality_score=data_quality,
        )
    
    def _calculate_performance_delta(
        self,
        current: Activity,
        baselines: List[Activity],
    ) -> float:
        """Calculate % difference in pace between current and baseline avg."""
        if not current.distance_m or not current.duration_s:
            return 0.0
        
        current_pace = current.duration_s / (current.distance_m / 1000)  # sec/km
        
        baseline_paces = []
        for b in baselines:
            if b.distance_m and b.duration_s:
                baseline_paces.append(b.duration_s / (b.distance_m / 1000))
        
        if not baseline_paces:
            return 0.0
        
        baseline_avg = statistics.mean(baseline_paces)
        
        # Negative pace delta = faster = improvement
        pace_delta_pct = ((current_pace - baseline_avg) / baseline_avg) * 100
        
        # Invert so positive = improvement
        return -pace_delta_pct
    
    def _generate_summaries(
        self,
        drivers: List[PerformanceDriver],
    ) -> Tuple[Optional[str], Optional[str]]:
        """Generate sparse summary sentences."""
        positive = [d for d in drivers if d.direction == DriverDirection.POSITIVE and d.confidence != Confidence.INSUFFICIENT]
        negative = [d for d in drivers if d.direction == DriverDirection.NEGATIVE and d.confidence != Confidence.INSUFFICIENT]
        
        summary_positive = None
        summary_negative = None
        
        if positive:
            top_positive = positive[:2]
            names = [f"{d.name} ({d.magnitude})" for d in top_positive]
            if len(names) == 1:
                summary_positive = f"Data suggests {names[0]} helped."
            else:
                summary_positive = f"Data suggests {names[0]} and {names[1]} helped."
        
        if negative:
            top_negative = negative[:2]
            names = [f"{d.name} ({d.magnitude})" for d in top_negative]
            if len(names) == 1:
                summary_negative = f"Potential drag: {names[0]}."
            else:
                summary_negative = f"Potential drags: {names[0]} and {names[1]}."
        
        return summary_positive, summary_negative
    
    def _calculate_data_quality(self, deltas: List[InputDelta]) -> float:
        """Calculate overall data quality score (0-1)."""
        if not deltas:
            return 0.0
        
        sufficient = sum(1 for d in deltas if d.has_sufficient_data)
        return sufficient / len(deltas)
