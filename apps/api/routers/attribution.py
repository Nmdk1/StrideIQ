"""
Attribution Engine API

The "WHY" behind performance changes.

Endpoints:
- POST /v1/attribution/analyze - Analyze drivers for a comparison
- GET /v1/attribution/activity/{id} - Quick attribution for single activity vs history
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.auth import get_current_user
from models import Athlete
from services.attribution_engine import AttributionEngineService

router = APIRouter(prefix="/v1/attribution", tags=["attribution"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class AttributionRequest(BaseModel):
    """Request for attribution analysis"""
    current_activity_id: str  # UUID as string
    baseline_activity_ids: List[str]  # UUIDs as strings
    performance_delta: Optional[float] = None  # Pre-calculated if available


class AttributionResponse(BaseModel):
    """Wrapper for attribution result"""
    success: bool
    data: dict
    message: Optional[str] = None


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/analyze")
def analyze_attribution(
    request: AttributionRequest,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Analyze what drove the performance difference between current and baseline runs.
    
    This is the core "WHY" feature.
    
    Request:
    - current_activity_id: The run we're analyzing
    - baseline_activity_ids: The comparison set (2-10 runs)
    - performance_delta: Optional pre-calculated % change
    
    Returns:
    - input_deltas: What changed in each input category
    - key_drivers: Top factors that likely contributed
    - summaries: Plain-language explanations
    - confidence levels
    """
    try:
        current_id = UUID(request.current_activity_id)
        baseline_ids = [UUID(id_str) for id_str in request.baseline_activity_ids]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid activity ID format")
    
    if len(baseline_ids) < 1:
        raise HTTPException(status_code=400, detail="Need at least 1 baseline activity")
    if len(baseline_ids) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 baseline activities")
    
    service = AttributionEngineService(db)
    
    try:
        result = service.analyze_performance_drivers(
            current_activity_id=current_id,
            baseline_activity_ids=baseline_ids,
            athlete_id=current_user.id,
            performance_delta=request.performance_delta,
        )
        
        return {
            "success": True,
            "data": result.to_dict(),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/activity/{activity_id}")
def get_activity_attribution(
    activity_id: UUID,
    days_back: int = Query(90, ge=30, le=365, description="How far back to look for baseline"),
    max_comparisons: int = Query(10, ge=3, le=20, description="Max baseline runs to include"),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Quick attribution for a single activity against recent history.
    
    Automatically finds similar runs from the past and analyzes drivers.
    Use this when you want a quick "why was this run good/bad?" answer.
    """
    from services.contextual_comparison import ContextualComparisonService
    from datetime import datetime, timedelta
    from models import Activity
    
    # Get the target activity
    activity = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.athlete_id == current_user.id,
    ).first()
    
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    # Find similar activities for comparison
    comparison_service = ContextualComparisonService(db)
    
    try:
        # Use the contextual comparison to find similar runs
        comparison = comparison_service.find_similar_runs(
            activity_id=activity_id,
            athlete_id=current_user.id,
            max_results=max_comparisons,
            min_similarity=0.25,
            days_back=days_back,
        )
        
        # Get the similar run IDs
        baseline_ids = [UUID(run.id) for run in comparison.similar_runs]
        
        if len(baseline_ids) < 2:
            return {
                "success": False,
                "data": None,
                "message": "Not enough similar runs for attribution analysis. Keep training!",
            }
        
        # Now run attribution
        attribution_service = AttributionEngineService(db)
        result = attribution_service.analyze_performance_drivers(
            current_activity_id=activity_id,
            baseline_activity_ids=baseline_ids,
            athlete_id=current_user.id,
            performance_delta=comparison.performance_score.pace_vs_baseline,
        )
        
        return {
            "success": True,
            "data": result.to_dict(),
            "comparison_context": {
                "similar_runs_count": len(baseline_ids),
                "performance_score": comparison.performance_score.score,
                "headline": comparison.headline,
            },
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/summary/{activity_id}")
def get_attribution_summary(
    activity_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lightweight endpoint for activity cards/lists.
    
    Returns just the top 2 drivers and summaries, not full analysis.
    Good for showing on activity list without full page load.
    """
    from services.contextual_comparison import ContextualComparisonService
    from models import Activity
    
    # Get the target activity
    activity = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.athlete_id == current_user.id,
    ).first()
    
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    # Quick comparison
    comparison_service = ContextualComparisonService(db)
    
    try:
        comparison = comparison_service.find_similar_runs(
            activity_id=activity_id,
            athlete_id=current_user.id,
            max_results=5,
            min_similarity=0.3,
            days_back=180,
        )
        
        baseline_ids = [UUID(run.id) for run in comparison.similar_runs]
        
        if len(baseline_ids) < 2:
            return {
                "activity_id": str(activity_id),
                "has_attribution": False,
                "top_drivers": [],
                "summary": None,
            }
        
        # Run attribution
        attribution_service = AttributionEngineService(db)
        result = attribution_service.analyze_performance_drivers(
            current_activity_id=activity_id,
            baseline_activity_ids=baseline_ids,
            athlete_id=current_user.id,
        )
        
        # Return summary only
        top_drivers = []
        for driver in result.key_drivers[:2]:
            top_drivers.append({
                "name": driver.name,
                "icon": driver.icon,
                "direction": driver.direction.value,
                "magnitude": driver.magnitude,
            })
        
        return {
            "activity_id": str(activity_id),
            "has_attribution": True,
            "top_drivers": top_drivers,
            "summary": result.summary_positive or result.summary_negative,
            "data_quality": result.data_quality_score,
        }
        
    except Exception:
        return {
            "activity_id": str(activity_id),
            "has_attribution": False,
            "top_drivers": [],
            "summary": None,
        }
