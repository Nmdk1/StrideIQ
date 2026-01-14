"""
Analytics API Router

Provides endpoints for efficiency trends, stability metrics, and load-response analysis.
This is the core product differentiator.
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from core.database import get_db
from core.auth import get_current_user
from core.cache import cached, cache_key, get_cache, set_cache
from core.feature_flags import is_feature_enabled
from models import Athlete
from services.efficiency_analytics import get_efficiency_trends
from services.trend_attribution import get_trend_attribution, attribution_result_to_dict

router = APIRouter(prefix="/v1/analytics", tags=["analytics"])


@router.get("/efficiency-trends")
def get_efficiency_trends_endpoint(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
    days: int = Query(90, ge=7, le=365, description="Number of days to analyze"),
    include_stability: bool = Query(True, description="Include stability metrics"),
    include_load_response: bool = Query(True, description="Include load-response analysis"),
    include_annotations: bool = Query(True, description="Include annotations (best-effort windows, regressions, plateaus)"),
):
    """
    Get efficiency trends over time.
    
    Returns:
    - Time series of efficiency factors (pace @ HR)
    - Rolling averages (7-day, 14-day)
    - Stability metrics (consistency score, variance)
    - Load-response relationships (productive vs wasted vs harmful load)
    - Trend direction and magnitude
    
    This is the core product differentiator - showing if athletes are getting fitter
    or just accumulating work.
    
    Cached for 1 hour (invalidated on new activity data).
    """
    # Generate cache key
    cache_key_str = cache_key(
        "efficiency_trends",
        str(current_user.id),
        days=days,
        include_stability=include_stability,
        include_load_response=include_load_response,
        include_annotations=include_annotations
    )
    
    # Try cache first
    cached_result = get_cache(cache_key_str)
    if cached_result is not None:
        return cached_result
    
    try:
        result = get_efficiency_trends(
            athlete_id=str(current_user.id),
            db=db,
            days=days,
            include_stability=include_stability,
            include_load_response=include_load_response,
            include_annotations=include_annotations
        )
        
        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
        # Cache for 1 hour (3600 seconds)
        set_cache(cache_key_str, result, ttl=3600)
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating efficiency trends: {str(e)}"
        )


@router.get("/trend-attribution")
def get_trend_attribution_endpoint(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
    metric: str = Query("efficiency", description="Metric to explain: efficiency, load, speed, pacing"),
    days: int = Query(28, ge=7, le=90, description="Number of days to analyze"),
):
    """
    Get attribution analysis for a trend - "Why This Trend?"
    
    Aggregates signals from all analytics methods and correlates inputs
    (sleep, nutrition, training load, etc.) with the specified metric.
    
    Returns ranked attributions by contribution percentage with confidence badges.
    
    ADR-014: Why This Trend? Attribution Integration
    
    Requires feature flag: analytics.trend_attribution
    """
    # Check feature flag
    flag_enabled = is_feature_enabled("analytics.trend_attribution", str(current_user.id), db)
    
    if not flag_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Trend attribution feature is not enabled"
        )
    
    # Generate cache key
    cache_key_str = cache_key(
        "trend_attribution",
        str(current_user.id),
        metric=metric,
        days=days
    )
    
    # Try cache first
    cached_result = get_cache(cache_key_str)
    if cached_result is not None:
        return cached_result
    
    try:
        result = get_trend_attribution(
            athlete_id=str(current_user.id),
            metric=metric,
            days=days,
            db=db
        )
        
        if not result:
            return {
                "trend_summary": None,
                "attributions": [],
                "method_contributions": {},
                "message": "Insufficient data for attribution analysis"
            }
        
        response = attribution_result_to_dict(result)
        
        # Cache for 30 minutes (1800 seconds)
        set_cache(cache_key_str, response, ttl=1800)
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating trend attribution: {str(e)}"
        )


# CS-prediction endpoint REMOVED
# Archived to branch: archive/cs-model-2026-01
# Reason: Redundant with Training Pace Calculator, low perceived value, user confusion
# See ADR-011 for details

