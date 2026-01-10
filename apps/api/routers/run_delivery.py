"""
Run Delivery API Router

Provides endpoint for complete run delivery experience.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Dict
from core.database import get_db
from core.auth import get_current_user
from models import Activity, Athlete
from services.run_delivery import get_run_delivery

router = APIRouter(prefix="/v1/activities", tags=["run-delivery"])


@router.get("/{activity_id}/delivery", response_model=Dict)
def get_activity_delivery(
    activity_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get complete run delivery for an activity.
    
    Returns:
        - Objective insights (only if meaningful - no noise)
        - Perception prompt (always shown if activity is recent)
        - Metrics summary
        - Delivery timestamp
    
    Tone:
        - Direct and sparse by default
        - Irreverent when warranted (meaningful improvements)
        - Supportive but no coddling - data speaks
    
    Key principle: Only show insights if they're meaningful.
    Always prompt for perception to build the correlation dataset.
    """
    # Get activity
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activity {activity_id} not found"
        )
    
    # Verify ownership
    if activity.athlete_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this activity"
        )
    
    # Get athlete
    athlete = db.query(Athlete).filter(Athlete.id == current_user.id).first()
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Athlete not found"
        )
    
    # Get run delivery
    try:
        delivery = get_run_delivery(str(activity_id), str(current_user.id), db)
        return delivery
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating run delivery: {str(e)}"
        )


