"""
Activity Analysis API Router

Provides endpoints for analyzing activities and getting efficiency insights.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Dict
from core.database import get_db
from core.auth import get_current_user
from models import Activity, Athlete, ActivityFeedback
from services.activity_analysis import analyze_activity, ActivityAnalysis
from services.perception_prompts import get_perception_prompts

router = APIRouter(prefix="/v1/activities", tags=["activity-analysis"])


@router.get("/{activity_id}/analysis", response_model=Dict)
def get_activity_analysis(
    activity_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analyze an activity and return efficiency insights.
    
    Returns:
        - Efficiency metrics (pace, HR, efficiency score)
        - Comparisons against multiple baselines (PR, last race, training block, run type average)
        - Meaningful insights (only if 2-3% improvement confirmed over multiple runs)
        - Trend confirmation status
    
    Key principles:
        - Only flags improvements that are confirmed over multiple runs (not single-run noise)
        - Uses research-backed 2-3% threshold for meaningful improvements
        - Multiple baseline types for comprehensive comparison
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
    
    # Perform analysis
    try:
        analysis = ActivityAnalysis(activity, athlete, db)
        result = analysis.analyze()
        
        # Check if we should prompt for perception feedback
        perception_prompt = get_perception_prompts(activity, db)
        
        # Check if feedback already exists
        existing_feedback = db.query(ActivityFeedback).filter(
            ActivityFeedback.activity_id == activity.id
        ).first()
        
        # Add perception prompt info to response
        result["perception_prompt"] = {
            "should_prompt": perception_prompt["should_prompt"],
            "prompt_text": perception_prompt["prompt_text"],
            "required_fields": perception_prompt["required_fields"],
            "optional_fields": perception_prompt["optional_fields"],
            "has_feedback": existing_feedback is not None,
            "run_type": perception_prompt["run_type"]
        }
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing activity: {str(e)}"
        )

