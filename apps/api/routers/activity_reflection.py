"""
RSI Layer 2 — Activity Reflection Router

POST /v1/activities/{activity_id}/reflection
GET  /v1/activities/{activity_id}/reflection

Simple 3-option post-run reflection: harder | expected | easier.
No free text in v1. One reflection per activity.

Status codes:
    POST: 201 Created (new) / 200 OK (update existing)
    GET:  200 OK / 404 if activity not found
"""
from enum import Enum
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from uuid import UUID

from core.database import get_db
from core.auth import get_current_user
from models import Activity, ActivityReflection, Athlete

router = APIRouter(prefix="/v1/activities", tags=["reflection"])


class ReflectionResponse(str, Enum):
    harder = "harder"
    expected = "expected"
    easier = "easier"


class ReflectionCreate(BaseModel):
    response: ReflectionResponse


class ReflectionOut(BaseModel):
    id: str
    activity_id: str
    response: str
    created_at: datetime

    class Config:
        from_attributes = True


def _to_out(reflection: ActivityReflection) -> dict:
    """Convert model to response dict."""
    return {
        "id": str(reflection.id),
        "activity_id": str(reflection.activity_id),
        "response": reflection.response,
        "created_at": reflection.created_at.isoformat(),
    }


@router.post("/{activity_id}/reflection", response_model=ReflectionOut)
def create_or_update_reflection(
    activity_id: UUID,
    payload: ReflectionCreate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit a post-run reflection for an activity.

    Stores: activity_id + athlete_id + response enum + timestamp.
    One reflection per activity — subsequent calls update the existing one.
    Returns 201 for new, 200 for update.
    """
    # Verify activity exists and belongs to user
    activity = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.athlete_id == current_user.id,
    ).first()
    if activity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found",
        )

    # Check for existing reflection (upsert behavior)
    existing = db.query(ActivityReflection).filter(
        ActivityReflection.activity_id == activity_id,
    ).first()

    if existing:
        existing.response = payload.response.value
        existing.created_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return JSONResponse(
            content=_to_out(existing),
            status_code=status.HTTP_200_OK,
        )

    # Create new reflection
    reflection = ActivityReflection(
        activity_id=activity_id,
        athlete_id=current_user.id,
        response=payload.response.value,
    )
    db.add(reflection)
    db.commit()
    db.refresh(reflection)

    return JSONResponse(
        content=_to_out(reflection),
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/{activity_id}/reflection", response_model=ReflectionOut | None)
def get_reflection(
    activity_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the existing reflection for an activity, or null if none exists."""
    # Verify activity exists and belongs to user
    activity = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.athlete_id == current_user.id,
    ).first()
    if activity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found",
        )

    reflection = db.query(ActivityReflection).filter(
        ActivityReflection.activity_id == activity_id,
    ).first()

    if reflection is None:
        return None

    return ReflectionOut(
        id=str(reflection.id),
        activity_id=str(reflection.activity_id),
        response=reflection.response,
        created_at=reflection.created_at,
    )
