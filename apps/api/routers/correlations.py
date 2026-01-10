"""
Correlation Analysis API Router

Provides endpoints for discovering which inputs lead to efficiency improvements.
This is the core discovery engine - identifying statistically significant correlations
between inputs (nutrition, sleep, work patterns, body composition) and outputs
(efficiency factor, decoupling, performance).
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from core.database import get_db
from core.auth import get_current_user
from core.cache import cache_key, get_cache, set_cache
from models import Athlete
from services.correlation_engine import analyze_correlations, discover_combination_correlations, get_combination_insights

router = APIRouter(prefix="/v1/correlations", tags=["correlations"])


@router.get("/discover")
def discover_correlations(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
    days: int = Query(90, ge=30, le=365, description="Analysis period in days")
):
    """
    Discover correlations between inputs and efficiency outputs.
    
    Analyzes:
    - Sleep (hours, HRV, resting HR) vs efficiency
    - Nutrition (daily protein, carbs) vs efficiency
    - Work patterns (stress, hours) vs efficiency
    - Body composition (weight, BMI) vs efficiency
    
    Returns statistically significant correlations with time-shifted effects.
    This is the core discovery engine - identifying what actually works for THIS athlete.
    
    Key features:
    - Personal curves only (no global averages)
    - Time-shifted correlations (delayed effects discovered from data)
    - Statistical significance testing (p < 0.05)
    - Minimum correlation strength (|r| >= 0.3)
    
    Cached for 24 hours (invalidated on new data).
    """
    # Generate cache key
    cache_key_str = cache_key("correlations", str(current_user.id), days=days)
    
    # Try cache first
    cached_result = get_cache(cache_key_str)
    if cached_result is not None:
        return cached_result
    
    try:
        result = analyze_correlations(
            athlete_id=str(current_user.id),
            days=days,
            db=db
        )
        
        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
        # Cache for 24 hours (86400 seconds)
        set_cache(cache_key_str, result, ttl=86400)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing correlations: {str(e)}"
        )


@router.get("/what-works")
def what_works(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
    days: int = Query(90, ge=30, le=365, description="Analysis period in days")
):
    """
    Get "What's Working" insights - positive correlations that improve efficiency.
    
    Returns only positive correlations (inputs that increase efficiency).
    Formatted for easy consumption in UI.
    
    Cached for 24 hours (invalidated on new data).
    """
    # Generate cache key
    cache_key_str = cache_key("correlations:what_works", str(current_user.id), days=days)
    
    # Try cache first
    cached_result = get_cache(cache_key_str)
    if cached_result is not None:
        return cached_result
    
    try:
        result = analyze_correlations(
            athlete_id=str(current_user.id),
            days=days,
            db=db
        )
        
        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
        # Filter for positive correlations only
        positive_correlations = [
            c for c in result["correlations"]
            if c["direction"] == "negative"  # Negative correlation = lower EF = better efficiency
        ]
        
        response = {
            "athlete_id": result["athlete_id"],
            "analysis_period": result["analysis_period"],
            "what_works": positive_correlations,
            "count": len(positive_correlations)
        }
        
        # Cache for 24 hours
        set_cache(cache_key_str, response, ttl=86400)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing what works: {str(e)}"
        )


@router.get("/what-doesnt-work")
def what_doesnt_work(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
    days: int = Query(90, ge=30, le=365, description="Analysis period in days")
):
    """
    Get "What Doesn't Work" insights - negative correlations that reduce efficiency.
    
    Returns only negative correlations (inputs that decrease efficiency).
    Formatted for easy consumption in UI.
    
    Cached for 24 hours (invalidated on new data).
    """
    # Generate cache key
    cache_key_str = cache_key("correlations:what_doesnt_work", str(current_user.id), days=days)
    
    # Try cache first
    cached_result = get_cache(cache_key_str)
    if cached_result is not None:
        return cached_result
    
    try:
        result = analyze_correlations(
            athlete_id=str(current_user.id),
            days=days,
            db=db
        )
        
        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
        # Filter for negative correlations only (positive correlation = higher EF = worse efficiency)
        negative_correlations = [
            c for c in result["correlations"]
            if c["direction"] == "positive"
        ]
        
        response = {
            "athlete_id": result["athlete_id"],
            "analysis_period": result["analysis_period"],
            "what_doesnt_work": negative_correlations,
            "count": len(negative_correlations)
        }
        
        # Cache for 24 hours
        set_cache(cache_key_str, response, ttl=86400)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing what doesn't work: {str(e)}"
        )


@router.get("/combinations")
def discover_combinations(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
    days: int = Query(90, ge=30, le=365, description="Analysis period in days")
):
    """
    Discover multi-factor combination correlations.
    
    Tests combinations of inputs to find patterns like:
    - "High sleep + Low work stress = Better efficiency"
    - "High protein + Good HRV = Better decoupling"
    
    This is the next level of the correlation engine - finding what combinations
    of factors lead to improvement. Single-variable correlations are useful but
    often the real gains come from optimizing multiple factors together.
    
    Based on manifesto: "We build personal response curves"
    
    Cached for 24 hours (invalidated on new data).
    """
    # Generate cache key
    cache_key_str = cache_key("correlations:combinations", str(current_user.id), days=days)
    
    # Try cache first
    cached_result = get_cache(cache_key_str)
    if cached_result is not None:
        return cached_result
    
    try:
        result = discover_combination_correlations(
            athlete_id=str(current_user.id),
            days=days,
            db=db
        )
        
        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
        # Cache for 24 hours
        set_cache(cache_key_str, result, ttl=86400)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing combinations: {str(e)}"
        )


@router.get("/insights")
def get_insights(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
    days: int = Query(90, ge=30, le=365, description="Analysis period in days")
):
    """
    Get actionable insights combining single and multi-factor correlations.
    
    Returns a unified view of:
    - What single factors work/don't work
    - What combinations work best
    - Formatted for display on discovery dashboard
    
    Tone-aligned: sparse, irreverent when earned, data-driven.
    """
    # Generate cache key
    cache_key_str = cache_key("correlations:insights", str(current_user.id), days=days)
    
    # Try cache first
    cached_result = get_cache(cache_key_str)
    if cached_result is not None:
        return cached_result
    
    try:
        # Get single-factor correlations
        single_result = analyze_correlations(
            athlete_id=str(current_user.id),
            days=days,
            db=db
        )
        
        # Get combination insights
        combo_insights = get_combination_insights(
            athlete_id=str(current_user.id),
            days=days,
            db=db
        )
        
        # Format single-factor insights
        single_insights = []
        if "correlations" in single_result:
            for c in single_result["correlations"]:
                # Lower EF = better, so negative correlation = good
                is_good = c["direction"] == "negative"
                single_insights.append({
                    'type': 'single_factor',
                    'factor': c["input_name"],
                    'direction': 'positive' if is_good else 'negative',
                    'strength': c["strength"],
                    'correlation': c["correlation_coefficient"],
                    'lag_days': c.get("time_lag_days", 0),
                    'insight': _format_single_insight(c, is_good)
                })
        
        response = {
            "athlete_id": str(current_user.id),
            "analysis_period": single_result.get("analysis_period", {}),
            "single_factor_insights": single_insights,
            "combination_insights": combo_insights,
            "total_insights": len(single_insights) + len(combo_insights)
        }
        
        # Cache for 24 hours
        set_cache(cache_key_str, response, ttl=86400)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting insights: {str(e)}"
        )


def _format_single_insight(correlation: dict, is_good: bool) -> str:
    """Format a single correlation into an insight string."""
    factor = correlation["input_name"].replace("_", " ")
    strength = correlation["strength"]
    lag = correlation.get("time_lag_days", 0)
    
    lag_text = f" (effect shows after {lag} days)" if lag > 0 else ""
    
    if is_good:
        return f"Higher {factor} correlates with better efficiency{lag_text}. Pattern is {strength}."
    else:
        return f"Higher {factor} correlates with worse efficiency{lag_text}. Pattern is {strength}."

