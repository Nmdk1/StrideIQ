"""
Run Analysis Router

Exposes the Run Analysis Engine via API endpoints.
Provides contextual analysis for every run.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel

from core.database import get_db
from core.auth import get_current_athlete
from models import Athlete, Activity
from services.run_analysis_engine import (
    RunAnalysisEngine,
    RunAnalysis,
    WorkoutType,
    TrendDirection,
    TrendAnalysis,
    RootCauseHypothesis
)

router = APIRouter(prefix="/v1/run-analysis", tags=["Run Analysis"])


# ============ Response Models ============

class InputSnapshotResponse(BaseModel):
    sleep_last_night: Optional[float] = None
    sleep_3_day_avg: Optional[float] = None
    sleep_7_day_avg: Optional[float] = None
    stress_today: Optional[int] = None
    stress_3_day_avg: Optional[float] = None
    soreness_today: Optional[int] = None
    soreness_3_day_avg: Optional[float] = None
    hrv_today: Optional[float] = None
    hrv_7_day_avg: Optional[float] = None
    resting_hr_today: Optional[int] = None
    resting_hr_7_day_avg: Optional[float] = None
    days_since_last_run: Optional[int] = None
    runs_this_week: Optional[int] = None
    volume_this_week_km: Optional[float] = None


class WorkoutContextResponse(BaseModel):
    workout_type: str
    confidence: float
    efficiency_score: Optional[float] = None
    similar_workouts_count: int = 0
    percentile_vs_similar: Optional[float] = None
    trend_vs_similar: Optional[str] = None
    context_this_week: Optional[dict] = None
    context_this_month: Optional[dict] = None
    context_this_year: Optional[dict] = None


class TrendAnalysisResponse(BaseModel):
    metric: str
    direction: str
    magnitude: Optional[float] = None
    confidence: float = 0.0
    data_points: int = 0
    period_days: int = 0
    is_significant: bool = False


class RootCauseResponse(BaseModel):
    factor: str
    correlation_strength: float
    direction: str
    confidence: float
    explanation: str


class RunAnalysisResponse(BaseModel):
    activity_id: str
    athlete_id: str
    analysis_timestamp: datetime
    
    # Input state
    inputs: InputSnapshotResponse
    
    # Workout context
    context: WorkoutContextResponse
    
    # Trends
    efficiency_trend: TrendAnalysisResponse
    volume_trend: TrendAnalysisResponse
    
    # Flags
    is_outlier: bool = False
    outlier_reason: Optional[str] = None
    is_red_flag: bool = False
    red_flag_reason: Optional[str] = None
    
    # Root causes
    root_cause_hypotheses: List[RootCauseResponse] = []
    
    # Insights
    insights: List[str] = []


# ============ Endpoints ============
# NOTE: Specific routes MUST come before the catch-all /{activity_id}

@router.get("/trends/efficiency")
async def get_efficiency_trend(
    days: int = 30,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Get efficiency trend analysis over specified period.
    """
    engine = RunAnalysisEngine(db)
    trend = engine.detect_trend(athlete.id, "efficiency", days=days)
    
    return {
        "metric": trend.metric,
        "direction": trend.direction.value,
        "magnitude_percent": round(trend.magnitude, 2) if trend.magnitude else None,
        "confidence": round(trend.confidence, 2),
        "data_points": trend.data_points,
        "period_days": trend.period_days,
        "is_significant": trend.is_significant,
        "interpretation": _interpret_efficiency_trend(trend),
    }


@router.get("/trends/volume")
async def get_volume_trend(
    days: int = 30,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Get volume trend analysis over specified period.
    """
    engine = RunAnalysisEngine(db)
    trend = engine.detect_trend(athlete.id, "volume", days=days)
    
    return {
        "metric": trend.metric,
        "direction": trend.direction.value,
        "magnitude_percent": round(trend.magnitude, 2) if trend.magnitude else None,
        "confidence": round(trend.confidence, 2),
        "data_points": trend.data_points,
        "period_days": trend.period_days,
        "is_significant": trend.is_significant,
    }


@router.get("/root-causes")
async def analyze_root_causes(
    days: int = 30,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Analyze potential root causes for efficiency changes.
    Only meaningful if there's a trend (declining or improving).
    """
    engine = RunAnalysisEngine(db)
    
    # First check if there's a trend worth analyzing
    trend = engine.detect_trend(athlete.id, "efficiency", days=days)
    
    if not trend.is_significant:
        return {
            "status": "no_significant_trend",
            "message": "No significant efficiency trend detected. Root cause analysis not needed.",
            "trend": {
                "direction": trend.direction.value,
                "confidence": trend.confidence,
            },
            "hypotheses": [],
        }
    
    # Get root causes
    hypotheses = engine.analyze_root_causes(athlete.id, "efficiency", days=days)
    
    return {
        "status": "analysis_complete",
        "trend": {
            "direction": trend.direction.value,
            "magnitude_percent": round(trend.magnitude, 2) if trend.magnitude else None,
            "confidence": round(trend.confidence, 2),
        },
        "hypotheses": [
            {
                "factor": h.factor,
                "correlation": round(h.correlation_strength, 2),
                "direction": h.direction,
                "confidence": round(h.confidence, 2),
                "explanation": h.explanation,
            } for h in hypotheses
        ],
    }


def _interpret_efficiency_trend(trend: TrendAnalysis) -> str:
    """Generate human-readable interpretation of efficiency trend"""
    if trend.direction == TrendDirection.INSUFFICIENT_DATA:
        return "Not enough data to determine trend. Keep logging runs."
    
    if not trend.is_significant:
        return "Efficiency is stable. No significant changes detected."
    
    if trend.direction == TrendDirection.IMPROVING:
        magnitude = abs(trend.magnitude) if trend.magnitude else 0
        if magnitude > 10:
            return f"Strong improvement in efficiency ({magnitude:.1f}%). You're getting faster at the same effort."
        else:
            return f"Efficiency improving ({magnitude:.1f}%). Positive adaptation occurring."
    
    if trend.direction == TrendDirection.DECLINING:
        magnitude = abs(trend.magnitude) if trend.magnitude else 0
        if magnitude > 10:
            return f"Significant efficiency decline ({magnitude:.1f}%). Consider recovery or identifying root causes."
        else:
            return f"Slight efficiency decline ({magnitude:.1f}%). Worth monitoring but not alarming."
    
    return "Efficiency stable."


# Catch-all route MUST be last
@router.get("/{activity_id}", response_model=RunAnalysisResponse)
async def analyze_run(
    activity_id: UUID,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Get complete contextual analysis for a specific run.
    
    Analyzes:
    - All inputs leading up to the run (sleep, stress, load, etc.)
    - Historical context at multiple time scales
    - Comparison to similar workouts
    - Trend detection
    - Outlier and red flag detection
    - Root cause analysis if declining trends detected
    """
    # Verify activity belongs to athlete
    activity = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.athlete_id == athlete.id
    ).first()
    
    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found"
        )
    
    # Run analysis
    engine = RunAnalysisEngine(db)
    analysis = engine.analyze_run(activity_id)
    
    # Convert to response
    return RunAnalysisResponse(
        activity_id=str(analysis.activity_id),
        athlete_id=str(analysis.athlete_id),
        analysis_timestamp=analysis.analysis_timestamp,
        inputs=InputSnapshotResponse(
            sleep_last_night=analysis.inputs.sleep_last_night,
            sleep_3_day_avg=analysis.inputs.sleep_3_day_avg,
            sleep_7_day_avg=analysis.inputs.sleep_7_day_avg,
            stress_today=analysis.inputs.stress_today,
            stress_3_day_avg=analysis.inputs.stress_3_day_avg,
            soreness_today=analysis.inputs.soreness_today,
            soreness_3_day_avg=analysis.inputs.soreness_3_day_avg,
            hrv_today=analysis.inputs.hrv_today,
            hrv_7_day_avg=analysis.inputs.hrv_7_day_avg,
            resting_hr_today=analysis.inputs.resting_hr_today,
            resting_hr_7_day_avg=analysis.inputs.resting_hr_7_day_avg,
            days_since_last_run=analysis.inputs.days_since_last_run,
            runs_this_week=analysis.inputs.runs_this_week,
            volume_this_week_km=analysis.inputs.volume_this_week_km,
        ),
        context=WorkoutContextResponse(
            workout_type=analysis.context.workout_type.value,
            confidence=analysis.context.confidence,
            efficiency_score=analysis.context.efficiency_score,
            similar_workouts_count=analysis.context.similar_workouts_count,
            percentile_vs_similar=analysis.context.percentile_vs_similar,
            trend_vs_similar=analysis.context.trend_vs_similar.value if analysis.context.trend_vs_similar else None,
            context_this_week=analysis.context.context_this_week,
            context_this_month=analysis.context.context_this_month,
            context_this_year=analysis.context.context_this_year,
        ),
        efficiency_trend=TrendAnalysisResponse(
            metric=analysis.efficiency_trend.metric,
            direction=analysis.efficiency_trend.direction.value,
            magnitude=analysis.efficiency_trend.magnitude,
            confidence=analysis.efficiency_trend.confidence,
            data_points=analysis.efficiency_trend.data_points,
            period_days=analysis.efficiency_trend.period_days,
            is_significant=analysis.efficiency_trend.is_significant,
        ),
        volume_trend=TrendAnalysisResponse(
            metric=analysis.performance_trend.metric,
            direction=analysis.performance_trend.direction.value,
            magnitude=analysis.performance_trend.magnitude,
            confidence=analysis.performance_trend.confidence,
            data_points=analysis.performance_trend.data_points,
            period_days=analysis.performance_trend.period_days,
            is_significant=analysis.performance_trend.is_significant,
        ),
        is_outlier=analysis.is_outlier,
        outlier_reason=analysis.outlier_reason,
        is_red_flag=analysis.is_red_flag,
        red_flag_reason=analysis.red_flag_reason,
        root_cause_hypotheses=[
            RootCauseResponse(
                factor=h.factor,
                correlation_strength=h.correlation_strength,
                direction=h.direction,
                confidence=h.confidence,
                explanation=h.explanation,
            ) for h in (analysis.root_cause_hypotheses or [])
        ],
        insights=analysis.insights or [],
    )

