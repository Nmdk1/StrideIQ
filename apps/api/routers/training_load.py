"""
Training Load Router

Exposes training load metrics:
- Current ATL/CTL/TSB
- Load history for charting
- Training phase analysis
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import date
from pydantic import BaseModel

from core.database import get_db
from core.auth import get_current_athlete
from models import Athlete
from services.training_load import TrainingLoadCalculator, DailyLoad, LoadSummary

router = APIRouter(prefix="/v1/training-load", tags=["Training Load"])


# ============ Response Models ============

class LoadSummaryResponse(BaseModel):
    atl: float
    ctl: float
    tsb: float
    atl_trend: str
    ctl_trend: str
    tsb_trend: str
    training_phase: str
    recommendation: str


class DailyLoadResponse(BaseModel):
    date: str
    total_tss: float
    workout_count: int
    atl: float
    ctl: float
    tsb: float


class LoadHistoryResponse(BaseModel):
    history: List[DailyLoadResponse]
    summary: LoadSummaryResponse


# ============ Endpoints ============

@router.get("/current", response_model=LoadSummaryResponse)
async def get_current_load(
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Get current training load metrics.
    
    Returns:
    - ATL: Acute Training Load (fatigue, 7-day)
    - CTL: Chronic Training Load (fitness, 42-day)
    - TSB: Training Stress Balance (form = CTL - ATL)
    - Trends and training phase
    """
    calculator = TrainingLoadCalculator(db)
    summary = calculator.calculate_training_load(athlete.id)
    
    return LoadSummaryResponse(
        atl=summary.current_atl,
        ctl=summary.current_ctl,
        tsb=summary.current_tsb,
        atl_trend=summary.atl_trend,
        ctl_trend=summary.ctl_trend,
        tsb_trend=summary.tsb_trend,
        training_phase=summary.training_phase,
        recommendation=summary.recommendation
    )


@router.get("/history", response_model=LoadHistoryResponse)
async def get_load_history(
    days: int = 60,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Get daily training load history for charting.
    
    Useful for visualizing fitness/fatigue/form progression.
    """
    if days < 7:
        days = 7
    if days > 365:
        days = 365
    
    calculator = TrainingLoadCalculator(db)
    history = calculator.get_load_history(athlete.id, days=days)
    summary = calculator.calculate_training_load(athlete.id)
    
    return LoadHistoryResponse(
        history=[
            DailyLoadResponse(
                date=dl.date.isoformat(),
                total_tss=dl.total_tss,
                workout_count=dl.workout_count,
                atl=dl.atl,
                ctl=dl.ctl,
                tsb=dl.tsb
            ) for dl in history
        ],
        summary=LoadSummaryResponse(
            atl=summary.current_atl,
            ctl=summary.current_ctl,
            tsb=summary.current_tsb,
            atl_trend=summary.atl_trend,
            ctl_trend=summary.ctl_trend,
            tsb_trend=summary.tsb_trend,
            training_phase=summary.training_phase,
            recommendation=summary.recommendation
        )
    )


@router.get("/tss/{activity_id}")
async def get_workout_tss(
    activity_id: UUID,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Get TSS calculation details for a specific workout.
    """
    from models import Activity
    
    activity = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.athlete_id == athlete.id
    ).first()
    
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    calculator = TrainingLoadCalculator(db)
    stress = calculator.calculate_workout_tss(activity, athlete)
    
    return {
        "activity_id": str(stress.activity_id),
        "date": stress.date.isoformat(),
        "tss": stress.tss,
        "duration_minutes": round(stress.duration_minutes, 1),
        "intensity_factor": stress.intensity_factor,
        "calculation_method": stress.calculation_method
    }


