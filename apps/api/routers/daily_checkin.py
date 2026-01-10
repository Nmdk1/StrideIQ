"""
Daily Check-in API Router

Ultra-fast daily check-in endpoint.
Must be lightning fast - this is the data that feeds the correlation engine.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
from uuid import UUID

from core.database import get_db
from core.auth import get_current_user
from models import Athlete, DailyCheckin

router = APIRouter(prefix="/v1/daily-checkin", tags=["Daily Check-in"])


class DailyCheckinCreate(BaseModel):
    date: date
    sleep_h: Optional[float] = None
    stress_1_5: Optional[int] = None
    soreness_1_5: Optional[int] = None
    rpe_1_10: Optional[int] = None
    hrv_rmssd: Optional[float] = None
    hrv_sdnn: Optional[float] = None
    resting_hr: Optional[int] = None
    overnight_avg_hr: Optional[float] = None
    notes: Optional[str] = None
    # Coach-inspired additions
    enjoyment_1_5: Optional[int] = None  # Green: "if you don't enjoy it, you won't be consistent"
    confidence_1_5: Optional[int] = None  # Snow: mindset tracking
    motivation_1_5: Optional[int] = None  # Snow: mindset tracking


class DailyCheckinResponse(BaseModel):
    id: UUID
    athlete_id: UUID
    date: date
    sleep_h: Optional[float] = None
    stress_1_5: Optional[int] = None
    soreness_1_5: Optional[int] = None
    rpe_1_10: Optional[int] = None
    hrv_rmssd: Optional[float] = None
    hrv_sdnn: Optional[float] = None
    resting_hr: Optional[int] = None
    overnight_avg_hr: Optional[float] = None
    notes: Optional[str] = None
    # Coach-inspired additions
    enjoyment_1_5: Optional[int] = None
    confidence_1_5: Optional[int] = None
    motivation_1_5: Optional[int] = None

    class Config:
        from_attributes = True


@router.post("", response_model=DailyCheckinResponse, status_code=status.HTTP_201_CREATED)
async def create_or_update_checkin(
    checkin: DailyCheckinCreate,
    db: Session = Depends(get_db),
    current_user: Athlete = Depends(get_current_user)
):
    """
    Create or update daily check-in.
    
    If a check-in already exists for this date, it will be updated.
    This is the friction-free endpoint - one POST, done.
    """
    # Check if check-in already exists for this date
    existing = db.query(DailyCheckin).filter(
        DailyCheckin.athlete_id == current_user.id,
        DailyCheckin.date == checkin.date
    ).first()
    
    if existing:
        # Update existing
        for field, value in checkin.model_dump(exclude_unset=True).items():
            if field != 'date':
                setattr(existing, field, value)
        db.commit()
        db.refresh(existing)
        return existing
    else:
        # Create new
        db_checkin = DailyCheckin(
            athlete_id=current_user.id,
            **checkin.model_dump()
        )
        db.add(db_checkin)
        db.commit()
        db.refresh(db_checkin)
        return db_checkin


@router.get("/today", response_model=Optional[DailyCheckinResponse])
async def get_today_checkin(
    db: Session = Depends(get_db),
    current_user: Athlete = Depends(get_current_user)
):
    """
    Get today's check-in if it exists.
    """
    today = date.today()
    checkin = db.query(DailyCheckin).filter(
        DailyCheckin.athlete_id == current_user.id,
        DailyCheckin.date == today
    ).first()
    
    return checkin


@router.get("/{checkin_date}", response_model=Optional[DailyCheckinResponse])
async def get_checkin_by_date(
    checkin_date: date,
    db: Session = Depends(get_db),
    current_user: Athlete = Depends(get_current_user)
):
    """
    Get check-in for a specific date.
    """
    checkin = db.query(DailyCheckin).filter(
        DailyCheckin.athlete_id == current_user.id,
        DailyCheckin.date == checkin_date
    ).first()
    
    return checkin


@router.get("")
async def list_checkins(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = 30,
    db: Session = Depends(get_db),
    current_user: Athlete = Depends(get_current_user)
):
    """
    List recent check-ins.
    """
    query = db.query(DailyCheckin).filter(
        DailyCheckin.athlete_id == current_user.id
    )
    
    if start_date:
        query = query.filter(DailyCheckin.date >= start_date)
    if end_date:
        query = query.filter(DailyCheckin.date <= end_date)
    
    checkins = query.order_by(DailyCheckin.date.desc()).limit(limit).all()
    
    return {
        "checkins": [DailyCheckinResponse.model_validate(c) for c in checkins],
        "count": len(checkins)
    }

