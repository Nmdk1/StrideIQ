"""
Contextual Comparison API

The differentiator: "Context vs Context" comparison.

Endpoints:
- GET /v1/compare/similar/{activity_id} - Find similar runs and compare
- POST /v1/compare/selected - Compare user-selected runs
- GET /v1/compare/auto-similar/{activity_id} - Auto-find most similar runs (no selection)
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.auth import get_current_user
from models import Athlete
from services.contextual_comparison import ContextualComparisonService

router = APIRouter(prefix="/v1/compare", tags=["compare"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class SelectedCompareRequest(BaseModel):
    """Request to compare user-selected activities"""
    activity_ids: List[str]  # UUIDs as strings
    baseline_id: Optional[str] = None  # Which activity to use as the baseline


class SimilarityConfig(BaseModel):
    """Configuration for similarity matching"""
    max_results: int = 10
    min_similarity: float = 0.3
    days_back: int = 365


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/similar/{activity_id}")
def find_similar_runs(
    activity_id: UUID,
    max_results: int = Query(10, ge=1, le=20),
    min_similarity: float = Query(0.3, ge=0.0, le=1.0),
    days_back: int = Query(365, ge=30, le=730),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Find runs similar to the target activity and build a contextual comparison.
    
    This is the core "Context vs Context" feature.
    
    Returns:
    - target_run: The activity being analyzed
    - similar_runs: List of similar runs with similarity scores
    - ghost_average: The baseline "ghost" averaged from similar runs
    - performance_score: How the target compares to the ghost
    - context_factors: Explanations for performance differences
    - headline: Plain-language performance summary
    - key_insight: The "BUT" explanation
    """
    service = ContextualComparisonService(db)
    
    try:
        result = service.find_similar_runs(
            activity_id=activity_id,
            athlete_id=current_user.id,
            max_results=max_results,
            min_similarity=min_similarity,
            days_back=days_back,
        )
        return result.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/selected")
def compare_selected_runs(
    request: SelectedCompareRequest,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Compare user-selected runs with contextual analysis.
    
    Use this when the athlete manually selects 2-10 runs to compare.
    
    If baseline_id is provided, that run is treated as the "target" being analyzed.
    Otherwise, the most recent run is the target.
    """
    # Convert string IDs to UUIDs
    try:
        activity_ids = [UUID(id_str) for id_str in request.activity_ids]
        baseline_id = UUID(request.baseline_id) if request.baseline_id else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid activity ID format")
    
    service = ContextualComparisonService(db)
    
    try:
        result = service.compare_selected_runs(
            activity_ids=activity_ids,
            athlete_id=current_user.id,
            baseline_id=baseline_id,
        )
        return result.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/auto-similar/{activity_id}")
def auto_compare_similar(
    activity_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    One-click contextual comparison.
    
    Automatically finds the 10 most similar runs and builds a complete
    comparison with ghost average, performance score, and insights.
    
    This is the "magic" endpoint - minimal input, maximum insight.
    """
    service = ContextualComparisonService(db)
    
    try:
        result = service.find_similar_runs(
            activity_id=activity_id,
            athlete_id=current_user.id,
            max_results=10,
            min_similarity=0.25,  # Slightly lower threshold for auto
            days_back=365,
        )
        return result.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/quick-score/{activity_id}")
def get_quick_performance_score(
    activity_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get just the performance score for an activity.
    
    Lighter-weight endpoint for showing scores on activity lists.
    Returns: score, rating, headline
    """
    service = ContextualComparisonService(db)
    
    try:
        result = service.find_similar_runs(
            activity_id=activity_id,
            athlete_id=current_user.id,
            max_results=5,  # Fewer for speed
            min_similarity=0.3,
            days_back=180,  # Shorter window for speed
        )
        
        return {
            "activity_id": str(activity_id),
            "score": result.performance_score.score,
            "rating": result.performance_score.rating,
            "headline": result.headline,
            "similar_runs_count": len(result.similar_runs),
            "key_insight": result.key_insight,
        }
    except ValueError:
        return {
            "activity_id": str(activity_id),
            "score": None,
            "rating": None,
            "headline": "Not enough similar runs for comparison",
            "similar_runs_count": 0,
            "key_insight": None,
        }


# =============================================================================
# EXPLICIT HR SEARCH ENDPOINTS
# These allow athletes to explicitly search/filter by heart rate.
# Foundation for the upcoming query engine.
# =============================================================================

@router.get("/by-avg-hr/{activity_id}")
def find_by_avg_hr(
    activity_id: UUID,
    tolerance: int = Query(5, ge=1, le=20, description="HR tolerance in bpm (±)"),
    max_results: int = Query(20, ge=1, le=50),
    days_back: int = Query(365, ge=30, le=730),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Find runs with similar average heart rate.
    
    Physiologically, same avg HR = same relative effort level.
    Use this to find runs where you maintained similar effort regardless of pace.
    
    Example: "Show me all runs where I held ~145 bpm"
    """
    service = ContextualComparisonService(db)
    
    results = service.find_by_avg_hr(
        activity_id=activity_id,
        athlete_id=current_user.id,
        hr_tolerance=tolerance,
        max_results=max_results,
        days_back=days_back,
    )
    
    return {
        "target_activity_id": str(activity_id),
        "hr_tolerance": tolerance,
        "count": len(results),
        "activities": results,
    }


@router.get("/by-max-hr/{activity_id}")
def find_by_max_hr(
    activity_id: UUID,
    tolerance: int = Query(5, ge=1, le=20, description="HR tolerance in bpm (±)"),
    max_results: int = Query(20, ge=1, le=50),
    days_back: int = Query(365, ge=30, le=730),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Find runs with similar maximum heart rate.
    
    Same max HR indicates similar cardiovascular peak stress.
    Use this to find runs where you hit similar intensity peaks.
    
    Example: "Show me runs where I peaked at ~175 bpm"
    """
    service = ContextualComparisonService(db)
    
    results = service.find_by_max_hr(
        activity_id=activity_id,
        athlete_id=current_user.id,
        hr_tolerance=tolerance,
        max_results=max_results,
        days_back=days_back,
    )
    
    return {
        "target_activity_id": str(activity_id),
        "hr_tolerance": tolerance,
        "count": len(results),
        "activities": results,
    }


@router.get("/hr-range")
def find_by_hr_range(
    min_hr: int = Query(..., ge=60, le=220, description="Minimum average HR"),
    max_hr: int = Query(..., ge=60, le=220, description="Maximum average HR"),
    min_duration: Optional[int] = Query(None, ge=1, description="Minimum duration in minutes"),
    max_results: int = Query(50, ge=1, le=100),
    days_back: int = Query(365, ge=30, le=730),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Find all runs within an average HR range.
    
    Pure query endpoint - no reference activity needed.
    Foundation primitive for the query engine.
    
    Example: "Show me all runs where I maintained 145-155 bpm for 30+ minutes"
    """
    if min_hr > max_hr:
        raise HTTPException(status_code=400, detail="min_hr must be <= max_hr")
    
    service = ContextualComparisonService(db)
    
    results = service.find_by_hr_range(
        athlete_id=current_user.id,
        min_hr=min_hr,
        max_hr=max_hr,
        min_duration_minutes=min_duration,
        max_results=max_results,
        days_back=days_back,
    )
    
    return {
        "hr_range": {"min": min_hr, "max": max_hr},
        "min_duration_minutes": min_duration,
        "count": len(results),
        "activities": results,
    }


@router.get("/metric-history/{activity_id}")
def get_metric_history(
    activity_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get historical metric data for the interactive tile drill-down.
    
    Returns efficiency, cardiac drift, aerobic decoupling, and pace consistency
    trends from similar runs to provide context for the current run's metrics.
    """
    service = ContextualComparisonService(db)
    
    try:
        history = service.get_metric_history(
            activity_id=activity_id,
            athlete_id=current_user.id,
        )
        return history
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
