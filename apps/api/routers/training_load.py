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

class PersonalZonesResponse(BaseModel):
    """N=1 personalized TSB zone thresholds based on athlete history."""
    mean_tsb: float
    std_tsb: float
    threshold_fresh: float      # TSB above this = Race Ready
    threshold_recovering: float # TSB above this = Recovering
    threshold_normal_low: float # TSB above this = Normal Training
    threshold_danger: float     # TSB above this = Overreaching, below = Danger
    sample_days: int
    is_personalized: bool       # True if enough data, False = population defaults
    current_zone: str           # Current zone based on personal thresholds
    zone_description: str       # Human-readable description


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
    personal_zones: Optional[PersonalZonesResponse] = None


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
    
    Includes N=1 personalized TSB zones based on athlete history.
    """
    if days < 7:
        days = 7
    if days > 365:
        days = 365
    
    calculator = TrainingLoadCalculator(db)
    history = calculator.get_load_history(athlete.id, days=days)
    summary = calculator.calculate_training_load(athlete.id)
    
    # Get personal TSB profile for N=1 zone display
    profile = calculator.get_personal_tsb_profile(athlete.id)
    zone_info = calculator.get_tsb_zone(summary.current_tsb, athlete_id=athlete.id)
    
    personal_zones = PersonalZonesResponse(
        mean_tsb=profile.mean_tsb,
        std_tsb=profile.std_tsb,
        threshold_fresh=profile.threshold_fresh,
        threshold_recovering=profile.threshold_recovering,
        threshold_normal_low=profile.threshold_normal_low,
        threshold_danger=profile.threshold_danger,
        sample_days=profile.sample_days,
        is_personalized=profile.is_sufficient_data,
        current_zone=zone_info.zone.value,
        zone_description=zone_info.description
    )
    
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
        ),
        personal_zones=personal_zones
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


