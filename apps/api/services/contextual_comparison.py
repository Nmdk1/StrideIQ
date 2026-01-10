"""
Contextual Comparison Engine

The differentiator: "Context vs Context" comparison, not just "Distance vs Distance."

This engine:
1. Finds truly similar runs using a weighted similarity algorithm
2. Creates a "Ghost Average" baseline from those similar runs
3. Calculates a Performance Score comparing the current run to the baseline
4. Generates contextual insights that explain WHY performance differed

No other platform offers this level of contextual analysis.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
import math
from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from models import Activity, ActivitySplit, Athlete


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class SimilarityFactors:
    """Breakdown of why an activity is similar"""
    duration_score: float  # 0-1, how close in duration
    intensity_score: float  # 0-1, how close in intensity
    type_score: float  # 0-1, same workout type
    conditions_score: float  # 0-1, similar conditions
    elevation_score: float  # 0-1, similar elevation profile
    total_score: float  # Weighted combination


@dataclass
class ContextFactor:
    """A single contextual factor explaining performance difference"""
    name: str  # e.g., "Temperature"
    icon: str  # e.g., "🌡️"
    this_run_value: str  # e.g., "85°F"
    baseline_value: str  # e.g., "65°F"
    difference: str  # e.g., "+20°F"
    impact: str  # 'positive', 'negative', 'neutral'
    explanation: str  # e.g., "Heat typically reduces efficiency by 2-3% per 10°F above 55°F"


@dataclass
class GhostAverage:
    """The baseline 'ghost' created from averaging similar runs"""
    num_runs_averaged: int
    avg_pace_per_km: Optional[float]
    avg_hr: Optional[float]
    avg_efficiency: Optional[float]
    avg_duration_s: Optional[float]
    avg_distance_m: Optional[float]
    avg_elevation_gain: Optional[float]
    avg_temperature_f: Optional[float]
    avg_intensity_score: Optional[float]
    # Splits for overlay
    avg_splits: List[Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "num_runs_averaged": self.num_runs_averaged,
            "avg_pace_per_km": self.avg_pace_per_km,
            "avg_pace_formatted": self._format_pace(self.avg_pace_per_km),
            "avg_hr": self.avg_hr,
            "avg_efficiency": self.avg_efficiency,
            "avg_duration_s": self.avg_duration_s,
            "avg_duration_formatted": self._format_duration(self.avg_duration_s),
            "avg_distance_m": self.avg_distance_m,
            "avg_distance_km": self.avg_distance_m / 1000 if self.avg_distance_m else None,
            "avg_elevation_gain": self.avg_elevation_gain,
            "avg_temperature_f": self.avg_temperature_f,
            "avg_intensity_score": self.avg_intensity_score,
            "avg_splits": self.avg_splits,
        }
    
    def _format_pace(self, seconds_per_km: Optional[float]) -> Optional[str]:
        if not seconds_per_km:
            return None
        minutes = int(seconds_per_km // 60)
        secs = int(seconds_per_km % 60)
        return f"{minutes}:{secs:02d}/km"
    
    def _format_duration(self, seconds: Optional[float]) -> Optional[str]:
        if not seconds:
            return None
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"


@dataclass
class PerformanceScore:
    """How the current run compares to the ghost average"""
    score: float  # 0-100, where 50 = average, >50 = better than average
    rating: str  # 'exceptional', 'strong', 'solid', 'average', 'below', 'struggling'
    percentile: float  # What percentile this run is vs similar runs
    
    # Component scores
    pace_vs_baseline: float  # % faster/slower than baseline
    efficiency_vs_baseline: float  # % more/less efficient than baseline
    hr_vs_baseline: float  # % higher/lower HR than baseline
    
    # Age-graded context (if available)
    age_graded_performance: Optional[float]  # WMA age-graded %
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": round(self.score, 1),
            "rating": self.rating,
            "percentile": round(self.percentile, 1),
            "pace_vs_baseline": round(self.pace_vs_baseline, 1),
            "efficiency_vs_baseline": round(self.efficiency_vs_baseline, 1),
            "hr_vs_baseline": round(self.hr_vs_baseline, 1),
            "age_graded_performance": self.age_graded_performance,
        }


@dataclass
class SimilarRun:
    """A run that's similar to the target run"""
    id: str
    date: datetime
    name: str
    workout_type: Optional[str]
    distance_m: int
    duration_s: int
    pace_per_km: Optional[float]
    avg_hr: Optional[int]
    efficiency: Optional[float]
    intensity_score: Optional[float]
    elevation_gain: Optional[float]
    temperature_f: Optional[float]
    similarity_score: float
    similarity_factors: SimilarityFactors
    splits: List[Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "date": self.date.isoformat(),
            "name": self.name,
            "workout_type": self.workout_type,
            "distance_m": self.distance_m,
            "distance_km": self.distance_m / 1000 if self.distance_m else 0,
            "duration_s": self.duration_s,
            "pace_per_km": self.pace_per_km,
            "pace_formatted": self._format_pace(self.pace_per_km),
            "avg_hr": self.avg_hr,
            "efficiency": self.efficiency,
            "intensity_score": self.intensity_score,
            "elevation_gain": self.elevation_gain,
            "temperature_f": self.temperature_f,
            "similarity_score": round(self.similarity_score, 2),
            "similarity_breakdown": {
                "duration": round(self.similarity_factors.duration_score, 2),
                "intensity": round(self.similarity_factors.intensity_score, 2),
                "type": round(self.similarity_factors.type_score, 2),
                "conditions": round(self.similarity_factors.conditions_score, 2),
                "elevation": round(self.similarity_factors.elevation_score, 2),
            },
            "splits": self.splits,
        }
    
    def _format_pace(self, seconds_per_km: Optional[float]) -> Optional[str]:
        if not seconds_per_km:
            return None
        minutes = int(seconds_per_km // 60)
        secs = int(seconds_per_km % 60)
        return f"{minutes}:{secs:02d}/km"


@dataclass
class ContextualComparisonResult:
    """Complete result of a contextual comparison"""
    # The run being analyzed
    target_run: Dict[str, Any]
    
    # Similar runs found
    similar_runs: List[SimilarRun]
    
    # The ghost average baseline
    ghost_average: GhostAverage
    
    # Performance score
    performance_score: PerformanceScore
    
    # Contextual factors explaining the difference
    context_factors: List[ContextFactor]
    
    # Plain-language headline
    headline: str
    
    # Key insight (the "BUT" explanation)
    key_insight: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_run": self.target_run,
            "similar_runs": [r.to_dict() for r in self.similar_runs],
            "ghost_average": self.ghost_average.to_dict(),
            "performance_score": self.performance_score.to_dict(),
            "context_factors": [
                {
                    "name": f.name,
                    "icon": f.icon,
                    "this_run_value": f.this_run_value,
                    "baseline_value": f.baseline_value,
                    "difference": f.difference,
                    "impact": f.impact,
                    "explanation": f.explanation,
                }
                for f in self.context_factors
            ],
            "headline": self.headline,
            "key_insight": self.key_insight,
        }


# =============================================================================
# SIMILARITY ALGORITHM
# =============================================================================

class SimilarityScorer:
    """
    Scores how similar two activities are using multiple weighted factors.
    
    The goal: Find runs that are truly comparable, not just "same distance."
    """
    
    # Weight configuration (sum to 1.0)
    WEIGHTS = {
        "duration": 0.30,  # Similar duration is very important
        "intensity": 0.25,  # Similar effort level
        "type": 0.20,  # Same workout type is a bonus
        "conditions": 0.15,  # Temperature, weather
        "elevation": 0.10,  # Similar elevation profile
    }
    
    def score(
        self,
        target: Activity,
        candidate: Activity,
    ) -> Tuple[float, SimilarityFactors]:
        """
        Calculate similarity score between target and candidate activity.
        Returns: (total_score, factor_breakdown)
        """
        duration_score = self._score_duration(target.duration_s, candidate.duration_s)
        intensity_score = self._score_intensity(target, candidate)
        type_score = self._score_type(target.workout_type, candidate.workout_type)
        conditions_score = self._score_conditions(target, candidate)
        elevation_score = self._score_elevation(target, candidate)
        
        # Weighted total
        total = (
            duration_score * self.WEIGHTS["duration"] +
            intensity_score * self.WEIGHTS["intensity"] +
            type_score * self.WEIGHTS["type"] +
            conditions_score * self.WEIGHTS["conditions"] +
            elevation_score * self.WEIGHTS["elevation"]
        )
        
        factors = SimilarityFactors(
            duration_score=duration_score,
            intensity_score=intensity_score,
            type_score=type_score,
            conditions_score=conditions_score,
            elevation_score=elevation_score,
            total_score=total,
        )
        
        return total, factors
    
    def _score_duration(
        self, 
        target_duration: Optional[int], 
        candidate_duration: Optional[int]
    ) -> float:
        """
        Gaussian decay: runs with similar duration score higher.
        
        - Same duration = 1.0
        - 5 min difference = ~0.9
        - 15 min difference = ~0.5
        - 30 min difference = ~0.1
        """
        if not target_duration or not candidate_duration:
            return 0.5  # Neutral if missing
        
        diff_minutes = abs(target_duration - candidate_duration) / 60
        
        # Gaussian decay with sigma = 10 minutes
        sigma = 10
        return math.exp(-(diff_minutes ** 2) / (2 * sigma ** 2))
    
    def _score_intensity(self, target: Activity, candidate: Activity) -> float:
        """
        Compare intensity using:
        1. Intensity score (0-100) if available
        2. Heart rate as fallback
        """
        # Prefer intensity_score
        if target.intensity_score and candidate.intensity_score:
            diff = abs(target.intensity_score - candidate.intensity_score)
            # 10 points difference = ~0.6 score
            return max(0, 1 - (diff / 30))
        
        # Fall back to HR
        if target.avg_hr and candidate.avg_hr:
            diff = abs(target.avg_hr - candidate.avg_hr)
            # 10 bpm difference = ~0.8 score
            return max(0, 1 - (diff / 40))
        
        return 0.5  # Neutral if missing
    
    def _score_type(
        self, 
        target_type: Optional[str], 
        candidate_type: Optional[str]
    ) -> float:
        """
        Same workout type = 1.0, similar = 0.6, different = 0.3
        """
        if not target_type or not candidate_type:
            return 0.5
        
        if target_type == candidate_type:
            return 1.0
        
        # Group similar types
        type_groups = {
            "easy": ["easy_run", "recovery_run", "aerobic_run"],
            "tempo": ["tempo_run", "tempo_intervals", "threshold_run"],
            "long": ["long_run", "medium_long_run", "fast_finish_long_run"],
            "speed": ["vo2max_intervals", "track_workout", "fartlek"],
            "race": ["race"],
        }
        
        target_group = None
        candidate_group = None
        
        for group_name, types in type_groups.items():
            if target_type in types:
                target_group = group_name
            if candidate_type in types:
                candidate_group = group_name
        
        if target_group and target_group == candidate_group:
            return 0.7  # Same category
        
        return 0.3  # Different category
    
    def _score_conditions(self, target: Activity, candidate: Activity) -> float:
        """
        Compare environmental conditions (temperature, humidity).
        """
        scores = []
        
        # Temperature
        if target.temperature_f and candidate.temperature_f:
            diff = abs(target.temperature_f - candidate.temperature_f)
            # 10°F difference = ~0.8, 30°F difference = ~0.3
            temp_score = max(0, 1 - (diff / 40))
            scores.append(temp_score)
        
        # Humidity
        if target.humidity_pct and candidate.humidity_pct:
            diff = abs(target.humidity_pct - candidate.humidity_pct)
            humidity_score = max(0, 1 - (diff / 50))
            scores.append(humidity_score)
        
        if scores:
            return sum(scores) / len(scores)
        return 0.5  # Neutral if no conditions data
    
    def _score_elevation(self, target: Activity, candidate: Activity) -> float:
        """
        Compare elevation profiles.
        """
        if not target.total_elevation_gain or not candidate.total_elevation_gain:
            return 0.5
        
        target_elev = float(target.total_elevation_gain)
        candidate_elev = float(candidate.total_elevation_gain)
        
        # Relative difference
        if max(target_elev, candidate_elev) > 0:
            ratio = min(target_elev, candidate_elev) / max(target_elev, candidate_elev)
            return ratio
        
        return 1.0  # Both flat


# =============================================================================
# CONTEXTUAL COMPARISON SERVICE
# =============================================================================

class ContextualComparisonService:
    """
    The core service for contextual activity comparison.
    
    Key capabilities:
    1. Find similar runs using weighted similarity
    2. Calculate ghost average baseline
    3. Score performance vs baseline
    4. Generate contextual insights
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.scorer = SimilarityScorer()
    
    def find_similar_runs(
        self,
        activity_id: UUID,
        athlete_id: UUID,
        max_results: int = 10,
        min_similarity: float = 0.3,
        days_back: int = 365,
    ) -> ContextualComparisonResult:
        """
        Find the most similar runs to a target activity and build comparison.
        
        Args:
            activity_id: The target activity to compare
            athlete_id: The athlete's ID
            max_results: Maximum number of similar runs to return (default 10)
            min_similarity: Minimum similarity score to include (0-1)
            days_back: How far back to look for similar runs
        
        Returns:
            Complete contextual comparison result
        """
        # Get target activity
        target = self.db.query(Activity).filter(
            Activity.id == activity_id,
            Activity.athlete_id == athlete_id,
        ).first()
        
        if not target:
            raise ValueError("Activity not found")
        
        # Get candidate activities
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        candidates = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.id != activity_id,
            Activity.start_time >= cutoff,
            Activity.distance_m >= 1000,  # At least 1km
            Activity.duration_s.isnot(None),
        ).all()
        
        # Score each candidate
        scored_candidates: List[Tuple[Activity, float, SimilarityFactors]] = []
        for candidate in candidates:
            score, factors = self.scorer.score(target, candidate)
            if score >= min_similarity:
                scored_candidates.append((candidate, score, factors))
        
        # Sort by score and take top N
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        top_similar = scored_candidates[:max_results]
        
        # Build SimilarRun objects
        similar_runs = []
        for activity, score, factors in top_similar:
            pace = activity.duration_s / (activity.distance_m / 1000) if activity.distance_m and activity.duration_s else None
            speed = (activity.distance_m / 1000) / (activity.duration_s / 3600) if activity.distance_m and activity.duration_s else None
            efficiency = speed / activity.avg_hr if speed and activity.avg_hr else None
            
            # Get splits
            splits = self._get_activity_splits(activity.id)
            
            similar_runs.append(SimilarRun(
                id=str(activity.id),
                date=activity.start_time,
                name=activity.name or f"Run on {activity.start_time.strftime('%b %d')}",
                workout_type=activity.workout_type,
                distance_m=activity.distance_m or 0,
                duration_s=activity.duration_s or 0,
                pace_per_km=pace,
                avg_hr=activity.avg_hr,
                efficiency=efficiency,
                intensity_score=activity.intensity_score,
                elevation_gain=float(activity.total_elevation_gain) if activity.total_elevation_gain else None,
                temperature_f=activity.temperature_f,
                similarity_score=score,
                similarity_factors=factors,
                splits=splits,
            ))
        
        # Calculate ghost average
        ghost_average = self._calculate_ghost_average(similar_runs)
        
        # Calculate performance score
        target_pace = target.duration_s / (target.distance_m / 1000) if target.distance_m and target.duration_s else None
        target_speed = (target.distance_m / 1000) / (target.duration_s / 3600) if target.distance_m and target.duration_s else None
        target_efficiency = target_speed / target.avg_hr if target_speed and target.avg_hr else None
        
        performance_score = self._calculate_performance_score(
            target_pace=target_pace,
            target_efficiency=target_efficiency,
            target_hr=target.avg_hr,
            ghost=ghost_average,
            similar_runs=similar_runs,
            age_graded=target.performance_percentage,
        )
        
        # Generate context factors
        context_factors = self._generate_context_factors(target, ghost_average)
        
        # Generate headline and key insight
        headline = self._generate_headline(performance_score, target)
        key_insight = self._generate_key_insight(performance_score, context_factors)
        
        # Build target run dict
        target_run = {
            "id": str(target.id),
            "date": target.start_time.isoformat(),
            "name": target.name or f"Run on {target.start_time.strftime('%b %d')}",
            "workout_type": target.workout_type,
            "distance_m": target.distance_m,
            "distance_km": target.distance_m / 1000 if target.distance_m else 0,
            "duration_s": target.duration_s,
            "pace_per_km": target_pace,
            "pace_formatted": self._format_pace(target_pace),
            "avg_hr": target.avg_hr,
            "efficiency": target_efficiency,
            "intensity_score": target.intensity_score,
            "elevation_gain": float(target.total_elevation_gain) if target.total_elevation_gain else None,
            "temperature_f": target.temperature_f,
            "humidity_pct": target.humidity_pct,
            "performance_percentage": target.performance_percentage,
            "splits": self._get_activity_splits(target.id),
        }
        
        return ContextualComparisonResult(
            target_run=target_run,
            similar_runs=similar_runs,
            ghost_average=ghost_average,
            performance_score=performance_score,
            context_factors=context_factors,
            headline=headline,
            key_insight=key_insight,
        )
    
    def compare_selected_runs(
        self,
        activity_ids: List[UUID],
        athlete_id: UUID,
        baseline_id: Optional[UUID] = None,
    ) -> ContextualComparisonResult:
        """
        Compare user-selected runs with contextual analysis.
        
        If baseline_id is provided, that run is the "target" being compared.
        Otherwise, the most recent run is the target.
        """
        if len(activity_ids) < 2:
            raise ValueError("Need at least 2 activities to compare")
        if len(activity_ids) > 10:
            raise ValueError("Maximum 10 activities for comparison")
        
        # Fetch all activities
        activities = self.db.query(Activity).filter(
            Activity.athlete_id == athlete_id,
            Activity.id.in_(activity_ids),
        ).all()
        
        if len(activities) != len(activity_ids):
            raise ValueError("One or more activities not found")
        
        # Sort by date
        activities.sort(key=lambda a: a.start_time, reverse=True)
        
        # Determine target (baseline)
        if baseline_id:
            target = next((a for a in activities if a.id == baseline_id), activities[0])
        else:
            target = activities[0]  # Most recent
        
        # Others become "similar runs"
        others = [a for a in activities if a.id != target.id]
        
        # Build SimilarRun objects (with similarity score based on comparison to target)
        similar_runs = []
        for activity in others:
            score, factors = self.scorer.score(target, activity)
            
            pace = activity.duration_s / (activity.distance_m / 1000) if activity.distance_m and activity.duration_s else None
            speed = (activity.distance_m / 1000) / (activity.duration_s / 3600) if activity.distance_m and activity.duration_s else None
            efficiency = speed / activity.avg_hr if speed and activity.avg_hr else None
            
            splits = self._get_activity_splits(activity.id)
            
            similar_runs.append(SimilarRun(
                id=str(activity.id),
                date=activity.start_time,
                name=activity.name or f"Run on {activity.start_time.strftime('%b %d')}",
                workout_type=activity.workout_type,
                distance_m=activity.distance_m or 0,
                duration_s=activity.duration_s or 0,
                pace_per_km=pace,
                avg_hr=activity.avg_hr,
                efficiency=efficiency,
                intensity_score=activity.intensity_score,
                elevation_gain=float(activity.total_elevation_gain) if activity.total_elevation_gain else None,
                temperature_f=activity.temperature_f,
                similarity_score=score,
                similarity_factors=factors,
                splits=splits,
            ))
        
        # Calculate ghost average from the comparison runs
        ghost_average = self._calculate_ghost_average(similar_runs)
        
        # Calculate performance score for target
        target_pace = target.duration_s / (target.distance_m / 1000) if target.distance_m and target.duration_s else None
        target_speed = (target.distance_m / 1000) / (target.duration_s / 3600) if target.distance_m and target.duration_s else None
        target_efficiency = target_speed / target.avg_hr if target_speed and target.avg_hr else None
        
        performance_score = self._calculate_performance_score(
            target_pace=target_pace,
            target_efficiency=target_efficiency,
            target_hr=target.avg_hr,
            ghost=ghost_average,
            similar_runs=similar_runs,
            age_graded=target.performance_percentage,
        )
        
        # Generate context factors
        context_factors = self._generate_context_factors(target, ghost_average)
        
        # Generate headline and key insight
        headline = self._generate_headline(performance_score, target)
        key_insight = self._generate_key_insight(performance_score, context_factors)
        
        # Build target run dict
        target_run = {
            "id": str(target.id),
            "date": target.start_time.isoformat(),
            "name": target.name or f"Run on {target.start_time.strftime('%b %d')}",
            "workout_type": target.workout_type,
            "distance_m": target.distance_m,
            "distance_km": target.distance_m / 1000 if target.distance_m else 0,
            "duration_s": target.duration_s,
            "pace_per_km": target_pace,
            "pace_formatted": self._format_pace(target_pace),
            "avg_hr": target.avg_hr,
            "efficiency": target_efficiency,
            "intensity_score": target.intensity_score,
            "elevation_gain": float(target.total_elevation_gain) if target.total_elevation_gain else None,
            "temperature_f": target.temperature_f,
            "humidity_pct": target.humidity_pct,
            "performance_percentage": target.performance_percentage,
            "splits": self._get_activity_splits(target.id),
        }
        
        return ContextualComparisonResult(
            target_run=target_run,
            similar_runs=similar_runs,
            ghost_average=ghost_average,
            performance_score=performance_score,
            context_factors=context_factors,
            headline=headline,
            key_insight=key_insight,
        )
    
    def _get_activity_splits(self, activity_id: UUID) -> List[Dict[str, Any]]:
        """Get splits for an activity in chart-friendly format"""
        splits = self.db.query(ActivitySplit).filter(
            ActivitySplit.activity_id == activity_id
        ).order_by(ActivitySplit.split_number).all()
        
        result = []
        cumulative_distance = 0.0
        
        for split in splits:
            distance = float(split.distance) if split.distance else 1609.34
            cumulative_distance += distance
            elapsed = split.moving_time or split.elapsed_time or 0
            pace = elapsed / (distance / 1000) if distance > 0 and elapsed > 0 else None
            
            result.append({
                "split_number": split.split_number,
                "distance_m": distance,
                "elapsed_time_s": elapsed,
                "pace_per_km": pace,
                "avg_hr": split.average_heartrate,
                "cumulative_distance_m": cumulative_distance,
            })
        
        return result
    
    def _calculate_ghost_average(self, similar_runs: List[SimilarRun]) -> GhostAverage:
        """Calculate the ghost average baseline from similar runs"""
        if not similar_runs:
            return GhostAverage(
                num_runs_averaged=0,
                avg_pace_per_km=None,
                avg_hr=None,
                avg_efficiency=None,
                avg_duration_s=None,
                avg_distance_m=None,
                avg_elevation_gain=None,
                avg_temperature_f=None,
                avg_intensity_score=None,
                avg_splits=[],
            )
        
        # Calculate averages
        paces = [r.pace_per_km for r in similar_runs if r.pace_per_km]
        hrs = [r.avg_hr for r in similar_runs if r.avg_hr]
        effs = [r.efficiency for r in similar_runs if r.efficiency]
        durations = [r.duration_s for r in similar_runs if r.duration_s]
        distances = [r.distance_m for r in similar_runs if r.distance_m]
        elevations = [r.elevation_gain for r in similar_runs if r.elevation_gain]
        temps = [r.temperature_f for r in similar_runs if r.temperature_f]
        intensities = [r.intensity_score for r in similar_runs if r.intensity_score]
        
        # Calculate average splits
        avg_splits = self._calculate_average_splits(similar_runs)
        
        return GhostAverage(
            num_runs_averaged=len(similar_runs),
            avg_pace_per_km=sum(paces) / len(paces) if paces else None,
            avg_hr=sum(hrs) / len(hrs) if hrs else None,
            avg_efficiency=sum(effs) / len(effs) if effs else None,
            avg_duration_s=sum(durations) / len(durations) if durations else None,
            avg_distance_m=sum(distances) / len(distances) if distances else None,
            avg_elevation_gain=sum(elevations) / len(elevations) if elevations else None,
            avg_temperature_f=sum(temps) / len(temps) if temps else None,
            avg_intensity_score=sum(intensities) / len(intensities) if intensities else None,
            avg_splits=avg_splits,
        )
    
    def _calculate_average_splits(self, similar_runs: List[SimilarRun]) -> List[Dict[str, Any]]:
        """Calculate average splits across all similar runs for overlay"""
        if not similar_runs:
            return []
        
        # Find max number of splits
        max_splits = max(len(r.splits) for r in similar_runs) if similar_runs else 0
        
        avg_splits = []
        for i in range(max_splits):
            paces = []
            hrs = []
            
            for run in similar_runs:
                if i < len(run.splits):
                    split = run.splits[i]
                    if split.get("pace_per_km"):
                        paces.append(split["pace_per_km"])
                    if split.get("avg_hr"):
                        hrs.append(split["avg_hr"])
            
            avg_splits.append({
                "split_number": i + 1,
                "avg_pace_per_km": sum(paces) / len(paces) if paces else None,
                "avg_hr": sum(hrs) / len(hrs) if hrs else None,
                "num_runs_at_split": len(paces),
            })
        
        return avg_splits
    
    def _calculate_performance_score(
        self,
        target_pace: Optional[float],
        target_efficiency: Optional[float],
        target_hr: Optional[int],
        ghost: GhostAverage,
        similar_runs: List[SimilarRun],
        age_graded: Optional[float],
    ) -> PerformanceScore:
        """Calculate how the target run compares to the ghost average"""
        
        # Calculate component scores
        pace_vs_baseline = 0.0
        if target_pace and ghost.avg_pace_per_km:
            # Negative = faster (better)
            pace_vs_baseline = ((ghost.avg_pace_per_km - target_pace) / ghost.avg_pace_per_km) * 100
        
        efficiency_vs_baseline = 0.0
        if target_efficiency and ghost.avg_efficiency:
            efficiency_vs_baseline = ((target_efficiency - ghost.avg_efficiency) / ghost.avg_efficiency) * 100
        
        hr_vs_baseline = 0.0
        if target_hr and ghost.avg_hr:
            # Negative = lower HR (usually better for same pace)
            hr_vs_baseline = ((ghost.avg_hr - target_hr) / ghost.avg_hr) * 100
        
        # Calculate percentile
        percentile = 50.0  # Default
        if target_efficiency and similar_runs:
            effs = [r.efficiency for r in similar_runs if r.efficiency]
            if effs:
                better_count = sum(1 for e in effs if target_efficiency > e)
                percentile = (better_count / len(effs)) * 100
        
        # Calculate overall score (0-100 scale, 50 = average)
        score = 50.0
        
        # Pace contributes most (faster = higher score)
        if pace_vs_baseline:
            score += pace_vs_baseline * 0.5  # +5% faster = +2.5 points
        
        # Efficiency boost
        if efficiency_vs_baseline:
            score += efficiency_vs_baseline * 0.3
        
        # HR efficiency (lower HR for same work = better)
        if hr_vs_baseline:
            score += hr_vs_baseline * 0.2
        
        # Clamp to 0-100
        score = max(0, min(100, score))
        
        # Determine rating
        if score >= 80:
            rating = "exceptional"
        elif score >= 65:
            rating = "strong"
        elif score >= 55:
            rating = "solid"
        elif score >= 45:
            rating = "average"
        elif score >= 35:
            rating = "below"
        else:
            rating = "struggling"
        
        return PerformanceScore(
            score=score,
            rating=rating,
            percentile=percentile,
            pace_vs_baseline=pace_vs_baseline,
            efficiency_vs_baseline=efficiency_vs_baseline,
            hr_vs_baseline=hr_vs_baseline,
            age_graded_performance=age_graded,
        )
    
    def _generate_context_factors(
        self, 
        target: Activity, 
        ghost: GhostAverage
    ) -> List[ContextFactor]:
        """Generate contextual factors explaining performance differences"""
        factors = []
        
        # Temperature
        if target.temperature_f and ghost.avg_temperature_f:
            diff = target.temperature_f - ghost.avg_temperature_f
            if abs(diff) >= 5:  # Meaningful difference
                impact = "negative" if diff > 10 else ("positive" if diff < -10 else "neutral")
                
                # Heat impact explanation
                if diff > 0:
                    explanation = f"Heat typically reduces efficiency by 1-2% per 10°F above 55°F. This run was {diff:.0f}°F warmer than your average."
                else:
                    explanation = f"Cooler temperatures often improve performance. This run was {abs(diff):.0f}°F cooler than average."
                
                factors.append(ContextFactor(
                    name="Temperature",
                    icon="🌡️",
                    this_run_value=f"{target.temperature_f:.0f}°F",
                    baseline_value=f"{ghost.avg_temperature_f:.0f}°F",
                    difference=f"{'+' if diff > 0 else ''}{diff:.0f}°F",
                    impact=impact,
                    explanation=explanation,
                ))
        
        # Elevation
        target_elev = float(target.total_elevation_gain) if target.total_elevation_gain else None
        if target_elev and ghost.avg_elevation_gain:
            diff = target_elev - ghost.avg_elevation_gain
            if abs(diff) >= 50:  # Meaningful difference (50m / ~165ft)
                impact = "negative" if diff > 100 else ("positive" if diff < -100 else "neutral")
                
                if diff > 0:
                    explanation = f"More climbing requires more effort. Expect ~10-15 sec/km slower per 100m extra elevation."
                else:
                    explanation = f"Less climbing typically means faster times. You gained {abs(diff):.0f}m less than usual."
                
                factors.append(ContextFactor(
                    name="Elevation",
                    icon="⛰️",
                    this_run_value=f"{target_elev:.0f}m",
                    baseline_value=f"{ghost.avg_elevation_gain:.0f}m",
                    difference=f"{'+' if diff > 0 else ''}{diff:.0f}m",
                    impact=impact,
                    explanation=explanation,
                ))
        
        # Duration (training load context)
        if target.duration_s and ghost.avg_duration_s:
            diff_min = (target.duration_s - ghost.avg_duration_s) / 60
            if abs(diff_min) >= 10:  # 10+ min difference
                impact = "neutral"  # Duration itself isn't good/bad
                
                if diff_min > 0:
                    explanation = f"This was a longer effort ({diff_min:.0f} min more). Expect some pace drop from fatigue."
                else:
                    explanation = f"This was shorter than usual ({abs(diff_min):.0f} min less). Should feel more sustainable."
                
                factors.append(ContextFactor(
                    name="Duration",
                    icon="⏱️",
                    this_run_value=self._format_duration(target.duration_s),
                    baseline_value=self._format_duration(ghost.avg_duration_s),
                    difference=f"{'+' if diff_min > 0 else ''}{diff_min:.0f} min",
                    impact=impact,
                    explanation=explanation,
                ))
        
        # Intensity context
        if target.intensity_score and ghost.avg_intensity_score:
            diff = target.intensity_score - ghost.avg_intensity_score
            if abs(diff) >= 5:
                impact = "neutral"
                
                if diff > 0:
                    explanation = f"Higher intensity ({diff:.0f} points). This was a harder effort than your similar runs."
                else:
                    explanation = f"Lower intensity ({abs(diff):.0f} points). More controlled effort than usual."
                
                factors.append(ContextFactor(
                    name="Intensity",
                    icon="💪",
                    this_run_value=f"{target.intensity_score:.0f}",
                    baseline_value=f"{ghost.avg_intensity_score:.0f}",
                    difference=f"{'+' if diff > 0 else ''}{diff:.0f}",
                    impact=impact,
                    explanation=explanation,
                ))
        
        return factors
    
    def _generate_headline(
        self, 
        score: PerformanceScore, 
        target: Activity
    ) -> str:
        """Generate the headline performance statement"""
        
        # Rating-based headlines
        headlines = {
            "exceptional": "🏆 Outstanding Performance",
            "strong": "💪 Strong Run",
            "solid": "✅ Solid Effort",
            "average": "📊 On Par",
            "below": "📉 Below Your Average",
            "struggling": "⚠️ Tough Day",
        }
        
        base = headlines.get(score.rating, "Run Analysis")
        
        # Add pace context if significant
        if abs(score.pace_vs_baseline) >= 3:
            if score.pace_vs_baseline > 0:
                return f"{base} — {score.pace_vs_baseline:.1f}% faster than your similar runs"
            else:
                return f"{base} — {abs(score.pace_vs_baseline):.1f}% slower than your similar runs"
        
        return base
    
    def _generate_key_insight(
        self, 
        score: PerformanceScore, 
        factors: List[ContextFactor]
    ) -> str:
        """Generate the key 'BUT' insight explaining the performance"""
        
        if not factors:
            if score.rating in ["exceptional", "strong"]:
                return "Great run with no significant external factors affecting performance."
            elif score.rating in ["below", "struggling"]:
                return "Performance was lower than usual. Consider recovery, sleep, or cumulative fatigue."
            return "Performance was close to your baseline for similar runs."
        
        # Find the most impactful factor
        negative_factors = [f for f in factors if f.impact == "negative"]
        positive_factors = [f for f in factors if f.impact == "positive"]
        
        if score.rating in ["below", "struggling"] and negative_factors:
            # Explain why performance was lower
            f = negative_factors[0]
            if score.pace_vs_baseline < -3:
                return f"You were {abs(score.pace_vs_baseline):.1f}% slower, BUT {f.explanation}"
            return f"Performance was affected: {f.explanation}"
        
        if score.rating in ["exceptional", "strong"] and positive_factors:
            f = positive_factors[0]
            return f"Great run! {f.explanation}"
        
        if score.rating in ["exceptional", "strong"] and negative_factors:
            f = negative_factors[0]
            return f"Impressive! Despite {f.name.lower()} being harder ({f.difference}), you still crushed it."
        
        if factors:
            f = factors[0]
            return f"{f.name} difference: {f.explanation}"
        
        return "Performance was close to your baseline for similar runs."
    
    def _format_pace(self, seconds_per_km: Optional[float]) -> Optional[str]:
        if not seconds_per_km:
            return None
        minutes = int(seconds_per_km // 60)
        secs = int(seconds_per_km % 60)
        return f"{minutes}:{secs:02d}/km"
    
    def _format_duration(self, seconds: Optional[float]) -> Optional[str]:
        if not seconds:
            return None
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"
