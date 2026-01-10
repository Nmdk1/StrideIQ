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
from models import Athlete
from services.efficiency_analytics import get_efficiency_trends

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

