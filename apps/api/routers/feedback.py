"""
Feedback Loop API Endpoints

Provides endpoints for the Continuous Feedback Loop system:
- Observe: Collect athlete data
- Hypothesize: Analyze limiting factors
- Intervene: Generate recommendations
- Validate: Check intervention effectiveness
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime

from core.database import get_db
from core.auth import get_current_user
from models import Athlete
from services.feedback_loop import (
    observe_athlete_data,
    hypothesize_limiting_factors,
    intervene_recommendations,
    validate_intervention,
    run_complete_feedback_loop,
)

router = APIRouter(prefix="/v1/feedback", tags=["feedback"])


@router.get("/athletes/{athlete_id}/observe")
def observe_endpoint(
    athlete_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    lookback_days: int = 30,
    db: Session = Depends(get_db)
):
    """
    Observe: Collect and aggregate all available data for an athlete.
    
    This is the first step in the feedback loop.
    """
    # Verify user is accessing their own data
    if athlete_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    observation = observe_athlete_data(current_user, db, lookback_days)
    return observation


@router.get("/athletes/{athlete_id}/hypothesize")
def hypothesize_endpoint(
    athlete_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    lookback_days: int = 30,
    db: Session = Depends(get_db)
):
    """
    Hypothesize: Analyze observed data to identify limiting factors.
    
    This step takes observed data and creates hypotheses about what might be
    limiting the athlete's performance.
    """
    # Verify user is accessing their own data
    if athlete_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    observation = observe_athlete_data(current_user, db, lookback_days)
    hypothesis = hypothesize_limiting_factors(observation)
    return hypothesis


@router.get("/athletes/{athlete_id}/intervene")
def intervene_endpoint(
    athlete_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    lookback_days: int = 30,
    db: Session = Depends(get_db)
):
    """
    Intervene: Generate recommendations based on hypotheses.
    
    This step creates actionable recommendations to address identified
    limiting factors.
    """
    # Verify user is accessing their own data
    if athlete_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    observation = observe_athlete_data(current_user, db, lookback_days)
    hypothesis = hypothesize_limiting_factors(observation)
    intervention = intervene_recommendations(hypothesis, observation)
    return intervention


@router.get("/athletes/{athlete_id}/loop")
def complete_loop_endpoint(
    athlete_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    lookback_days: int = 30,
    db: Session = Depends(get_db)
):
    """
    Run the complete feedback loop: Observe -> Hypothesize -> Intervene -> Validate.
    
    This is the main entry point for the feedback loop system.
    """
    # Verify user is accessing their own data
    if athlete_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    result = run_complete_feedback_loop(current_user, db, lookback_days)
    return result


@router.post("/athletes/{athlete_id}/validate")
def validate_endpoint(
    athlete_id: UUID,
    intervention_date: datetime,
    metric_to_track: str,
    expected_improvement: str,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Validate: Check if interventions are having the desired effect.
    
    This step compares current metrics to pre-intervention baseline.
    """
    # Verify user is accessing their own data
    if athlete_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    validation = validate_intervention(
        current_user, db, intervention_date, metric_to_track, expected_improvement
    )
    return validation
