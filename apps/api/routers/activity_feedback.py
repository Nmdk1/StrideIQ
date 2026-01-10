"""
Activity Feedback API Router

Provides endpoints for collecting and managing perceptual feedback for activities.
This builds the perception ↔ performance correlation dataset.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
from core.database import get_db
from core.auth import get_current_user
from models import Activity, ActivityFeedback, Athlete
from schemas import ActivityFeedbackCreate, ActivityFeedbackResponse, ActivityFeedbackUpdate
from services.perception_prompts import get_pending_feedback_prompts

router = APIRouter(prefix="/v1/activity-feedback", tags=["activity-feedback"])


@router.post("", response_model=ActivityFeedbackResponse, status_code=201)
def create_activity_feedback(
    feedback: ActivityFeedbackCreate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create feedback for an activity.
    
    Collects perceptual data (RPE, leg feel, mood, energy) to correlate
    with objective performance metrics.
    
    Validations:
    - Activity must exist and belong to current user
    - Only one feedback per activity (unique constraint)
    - RPE and energy scales: 1-10
    - Leg feel: predefined categories
    """
    # Verify activity exists and belongs to user
    activity = db.query(Activity).filter(Activity.id == feedback.activity_id).first()
    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activity {feedback.activity_id} not found"
        )
    
    if activity.athlete_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this activity"
        )
    
    # Check if feedback already exists
    existing = db.query(ActivityFeedback).filter(
        ActivityFeedback.activity_id == feedback.activity_id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Feedback already exists for this activity. Use PUT to update."
        )
    
    # Validate scales
    if feedback.perceived_effort is not None and not (1 <= feedback.perceived_effort <= 10):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="perceived_effort must be between 1 and 10"
        )
    
    if feedback.energy_pre is not None and not (1 <= feedback.energy_pre <= 10):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="energy_pre must be between 1 and 10"
        )
    
    if feedback.energy_post is not None and not (1 <= feedback.energy_post <= 10):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="energy_post must be between 1 and 10"
        )
    
    # Validate leg_feel categories
    valid_leg_feel = ['fresh', 'normal', 'tired', 'heavy', 'sore', 'injured']
    if feedback.leg_feel is not None and feedback.leg_feel not in valid_leg_feel:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"leg_feel must be one of: {', '.join(valid_leg_feel)}"
        )
    
    # Create feedback
    db_feedback = ActivityFeedback(
        activity_id=feedback.activity_id,
        athlete_id=current_user.id,
        perceived_effort=feedback.perceived_effort,
        leg_feel=feedback.leg_feel,
        mood_pre=feedback.mood_pre,
        mood_post=feedback.mood_post,
        energy_pre=feedback.energy_pre,
        energy_post=feedback.energy_post,
        notes=feedback.notes,
        submitted_at=datetime.utcnow()
    )
    
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)
    
    return db_feedback


@router.get("/activity/{activity_id}", response_model=ActivityFeedbackResponse)
def get_activity_feedback(
    activity_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get feedback for a specific activity.
    
    Returns feedback if it exists and belongs to current user.
    """
    # Verify activity belongs to user
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activity {activity_id} not found"
        )
    
    if activity.athlete_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this activity"
        )
    
    feedback = db.query(ActivityFeedback).filter(
        ActivityFeedback.activity_id == activity_id
    ).first()
    
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No feedback found for this activity"
        )
    
    return feedback


@router.get("/pending", response_model=list)
def get_pending_prompts(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 10
):
    """
    Get list of activities that need feedback prompts.
    
    Returns activities from last 24 hours that don't have feedback yet.
    Useful for showing "pending feedback" list in UI.
    """
    prompts = get_pending_feedback_prompts(current_user.id, db, limit=limit)
    return prompts


@router.put("/{feedback_id}", response_model=ActivityFeedbackResponse)
def update_activity_feedback(
    feedback_id: UUID,
    feedback_update: ActivityFeedbackUpdate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update existing activity feedback.
    
    Only updates provided fields. Validates scales and categories.
    """
    feedback = db.query(ActivityFeedback).filter(ActivityFeedback.id == feedback_id).first()
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feedback {feedback_id} not found"
        )
    
    if feedback.athlete_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this feedback"
        )
    
    # Validate scales
    if feedback_update.perceived_effort is not None:
        if not (1 <= feedback_update.perceived_effort <= 10):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="perceived_effort must be between 1 and 10"
            )
        feedback.perceived_effort = feedback_update.perceived_effort
    
    if feedback_update.energy_pre is not None:
        if not (1 <= feedback_update.energy_pre <= 10):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="energy_pre must be between 1 and 10"
            )
        feedback.energy_pre = feedback_update.energy_pre
    
    if feedback_update.energy_post is not None:
        if not (1 <= feedback_update.energy_post <= 10):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="energy_post must be between 1 and 10"
            )
        feedback.energy_post = feedback_update.energy_post
    
    # Validate leg_feel
    valid_leg_feel = ['fresh', 'normal', 'tired', 'heavy', 'sore', 'injured']
    if feedback_update.leg_feel is not None:
        if feedback_update.leg_feel not in valid_leg_feel:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"leg_feel must be one of: {', '.join(valid_leg_feel)}"
            )
        feedback.leg_feel = feedback_update.leg_feel
    
    # Update other fields
    if feedback_update.mood_pre is not None:
        feedback.mood_pre = feedback_update.mood_pre
    if feedback_update.mood_post is not None:
        feedback.mood_post = feedback_update.mood_post
    if feedback_update.notes is not None:
        feedback.notes = feedback_update.notes
    
    feedback.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(feedback)
    
    return feedback


@router.delete("/{feedback_id}", status_code=204)
def delete_activity_feedback(
    feedback_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete activity feedback.
    
    Only the owner can delete their feedback.
    """
    feedback = db.query(ActivityFeedback).filter(ActivityFeedback.id == feedback_id).first()
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feedback {feedback_id} not found"
        )
    
    if feedback.athlete_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this feedback"
        )
    
    db.delete(feedback)
    db.commit()
    
    return None
