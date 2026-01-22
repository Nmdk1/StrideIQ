"""
Analytics API Router

Provides endpoints for efficiency trends, stability metrics, and load-response analysis.
This is the core product differentiator.
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date, timedelta
from core.database import get_db
from core.auth import get_current_user
from core.cache import cached, cache_key, get_cache, set_cache
from core.feature_flags import is_feature_enabled
from models import Athlete
from services.efficiency_analytics import get_efficiency_trends
from services.trend_attribution import get_trend_attribution, attribution_result_to_dict
from services.load_response_explain import explain_load_response_week

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
    days: int = Query(28, ge=7, le=365, description="Number of days to analyze"),
):
    """
    Get attribution analysis for a trend - "Why This Trend?"
    
    Aggregates signals from all analytics methods and correlates inputs
    (sleep, nutrition, training load, etc.) with the specified metric.
    
    Returns ranked attributions by contribution percentage with confidence badges.
    
    ADR-014: Why This Trend? Attribution Integration
    """
    # Elite-only (paid access); admins always allowed
    if current_user.role not in ("admin", "owner") and not getattr(current_user, "has_active_subscription", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Trend attribution requires Elite membership")
    
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


@router.get("/load-response-explain")
def get_load_response_explain_endpoint(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
    week_start: date = Query(..., description="Week start date (YYYY-MM-DD). Any date within the week is accepted; it will be normalized to Monday."),
):
    """
    Explain a specific load-response week.

    Returns:
    - The week’s load metrics + efficiency delta (vs prior week)
    - The exact rule used for load_type classification
    - A ranked set of “signals” (sleep/stress/soreness/HRV/resting HR, etc.) vs a recent baseline

    This is the “Harmful → Why?” drilldown for the Load → Response chart.
    """
    # Cache key per athlete per week
    cache_key_str = cache_key(
        "load_response_explain",
        str(current_user.id),
        week_start=week_start.isoformat(),
    )

    cached_result = get_cache(cache_key_str)
    if cached_result is not None:
        return cached_result

    try:
        payload = explain_load_response_week(
            athlete_id=str(current_user.id),
            week_start=week_start,
            db=db,
        )
        set_cache(cache_key_str, payload, ttl=1800)  # 30 minutes
        return payload
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error explaining load-response week: {str(e)}"
        )

# CS-prediction endpoint REMOVED
# Archived to branch: archive/cs-model-2026-01
# Reason: Redundant with Training Pace Calculator, low perceived value, user confusion
# See ADR-011 for details


@router.get("/diagnostic-report")
def get_diagnostic_report_endpoint(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate comprehensive diagnostic report for the authenticated athlete.
    
    Returns:
    - Executive summary with key findings
    - Personal best profile with pace analysis
    - Volume trajectory with phase detection
    - Efficiency trend analysis
    - Race history
    - Data quality assessment (what's missing)
    - Prioritized recommendations
    
    ADR-019: On-Demand Diagnostic Report
    
    Rate limited: 1 report per 15 minutes (cached for 1 hour)
    Elite-only (paid access); admins always allowed
    """
    from services.athlete_diagnostic import (
        generate_diagnostic_report,
        diagnostic_report_to_dict
    )
    
    if current_user.role not in ("admin", "owner") and not getattr(current_user, "has_active_subscription", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Diagnostic report requires Elite membership")
    
    # Generate cache key
    cache_key_str = cache_key(
        "diagnostic_report",
        str(current_user.id)
    )
    
    # Try cache first (reports are cached for 1 hour)
    cached_result = get_cache(cache_key_str)
    if cached_result is not None:
        return cached_result
    
    try:
        report = generate_diagnostic_report(
            athlete_id=str(current_user.id),
            db=db
        )
        
        response = diagnostic_report_to_dict(report)
        
        # Add personalized narratives (ADR-033)
        if is_feature_enabled("narrative.translation_enabled", str(current_user.id), db):
            try:
                from services.narrative_translator import NarrativeTranslator
                from services.narrative_memory import NarrativeMemory
                from services.fitness_bank import FitnessBankCalculator
                from services.training_load import TrainingLoadCalculator
                
                bank_calc = FitnessBankCalculator(db)
                bank = bank_calc.calculate(current_user.id)
                
                load_calc = TrainingLoadCalculator(db)
                load = load_calc.calculate_training_load(current_user.id)
                
                if bank and load:
                    translator = NarrativeTranslator(db, current_user.id)
                    memory = NarrativeMemory(db, current_user.id, use_redis=False)
                    
                    # Get all narratives for diagnostic summary
                    all_narratives = translator.get_all_narratives(
                        bank,
                        tsb=load.current_tsb,
                        ctl=load.current_ctl,
                        atl=load.current_atl,
                        max_count=5
                    )
                    
                    # Pick fresh ones
                    fresh = memory.pick_freshest(all_narratives, count=4)
                    
                    response["narratives"] = [
                        {"text": n.text, "type": n.signal_type, "priority": n.priority}
                        for n in fresh
                    ]
                    
                    # Record as shown
                    for n in fresh:
                        memory.record_shown(n.hash, n.signal_type, "diagnostic")
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Diagnostic narrative generation failed for {athlete.id}: {type(e).__name__}: {e}")
                try:
                    from services.audit_logger import log_narrative_error
                    log_narrative_error(athlete.id, "diagnostic", str(e))
                except Exception:
                    pass
                response["narratives"] = []
        else:
            response["narratives"] = []
        
        # Cache for 1 hour (3600 seconds)
        set_cache(cache_key_str, response, ttl=3600)
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating diagnostic report: {str(e)}"
        )

