"""
User Preferences API Router

Manages athlete preferences like units (metric/imperial), timezone, etc.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from typing import Literal

from core.database import get_db
from core.auth import get_current_athlete
from models import Athlete

router = APIRouter(prefix="/v1/preferences", tags=["Preferences"])


class PreferencesResponse(BaseModel):
    """Current user preferences."""
    preferred_units: Literal["metric", "imperial"]
    
    model_config = ConfigDict(from_attributes=True)


class UpdatePreferencesRequest(BaseModel):
    """Request to update preferences."""
    preferred_units: Literal["metric", "imperial"] | None = None


@router.get("", response_model=PreferencesResponse)
async def get_preferences(
    athlete: Athlete = Depends(get_current_athlete),
):
    """Get current user preferences."""
    return PreferencesResponse(
        preferred_units=athlete.preferred_units or "metric"
    )


@router.patch("", response_model=PreferencesResponse)
async def update_preferences(
    request: UpdatePreferencesRequest,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """Update user preferences."""
    if request.preferred_units is not None:
        athlete.preferred_units = request.preferred_units
    
    db.commit()
    db.refresh(athlete)
    
    return PreferencesResponse(
        preferred_units=athlete.preferred_units or "metric"
    )
