"""
Insight Feedback API Router

Handles user feedback on insights to refine correlation engine thresholds.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from core.database import get_db
from core.auth import get_current_user
from models import Athlete, InsightFeedback
from schemas import InsightFeedbackCreate, InsightFeedbackResponse

router = APIRouter(prefix="/v1/insight-feedback", tags=["insight-feedback"])


@router.post("", response_model=InsightFeedbackResponse, status_code=201)
def create_insight_feedback(
    feedback: InsightFeedbackCreate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit feedback on an insight.
    
    Helps refine correlation engine thresholds by tracking which insights
    users find helpful vs not helpful.
    """
    db_feedback = InsightFeedback(
        athlete_id=current_user.id,
        insight_type=feedback.insight_type,
        insight_id=feedback.insight_id,
        insight_text=feedback.insight_text,
        helpful=feedback.helpful,
        feedback_text=feedback.feedback_text,
    )
    
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)
    
    return db_feedback


@router.get("", response_model=List[InsightFeedbackResponse])
def list_insight_feedback(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
    insight_type: Optional[str] = Query(None, description="Filter by insight type"),
    helpful: Optional[bool] = Query(None, description="Filter by helpful status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    List insight feedback for current user.
    """
    query = db.query(InsightFeedback).filter(
        InsightFeedback.athlete_id == current_user.id
    )
    
    if insight_type:
        query = query.filter(InsightFeedback.insight_type == insight_type)
    
    if helpful is not None:
        query = query.filter(InsightFeedback.helpful == helpful)
    
    query = query.order_by(InsightFeedback.created_at.desc())
    
    feedbacks = query.offset(offset).limit(limit).all()
    return feedbacks


@router.get("/stats")
def get_feedback_stats(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get aggregated feedback statistics for current user.
    """
    total = db.query(InsightFeedback).filter(
        InsightFeedback.athlete_id == current_user.id
    ).count()
    
    helpful_count = db.query(InsightFeedback).filter(
        InsightFeedback.athlete_id == current_user.id,
        InsightFeedback.helpful == True
    ).count()
    
    not_helpful_count = db.query(InsightFeedback).filter(
        InsightFeedback.athlete_id == current_user.id,
        InsightFeedback.helpful == False
    ).count()
    
    return {
        "total": total,
        "helpful": helpful_count,
        "not_helpful": not_helpful_count,
        "helpful_percentage": round((helpful_count / total * 100) if total > 0 else 0, 1),
    }


