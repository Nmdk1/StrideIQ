"""
Causal Attribution API Endpoints

Exposes the Causal Attribution Engine for:
1. Full causal analysis (discover leading indicators)
2. "Why This Trend?" explanations
3. Context block generation for AI Coach

Tone: Sparse, forensic, non-prescriptive.
"Data hints X preceded Y. Test it."
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from core.database import get_db
from core.auth import get_current_user
from models import Athlete
from services.causal_attribution import (
    CausalAttributionEngine,
    CausalAnalysisResult,
    LeadingIndicator,
    CausalConfidence,
    ImpactDirection,
    FrequencyLoop,
)


router = APIRouter(prefix="/v1/causal", tags=["Causal Attribution"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class LeadingIndicatorResponse(BaseModel):
    """A discovered leading indicator."""
    input_key: str
    input_name: str
    icon: str
    loop: str
    lag_days: int
    effect_direction: str
    granger_p: float
    correlation_r: float
    sample_size: int
    confidence: str
    insight: str
    
    model_config = ConfigDict(from_attributes=True)


class CausalAnalysisResponse(BaseModel):
    """Complete causal analysis result."""
    athlete_id: str
    analysis_date: str
    analysis_period_days: int
    readiness_indicators: List[LeadingIndicatorResponse]
    fitness_indicators: List[LeadingIndicatorResponse]
    top_indicators: List[LeadingIndicatorResponse]
    data_quality_score: float
    data_quality_notes: List[str]
    context_block: str


class TrendExplainRequest(BaseModel):
    """Request to explain a specific trend."""
    trend_name: str = Field(..., description="Name of the trend (e.g., 'Efficiency')")
    trend_direction: str = Field(..., description="'up' or 'down'")
    trend_magnitude_pct: float = Field(..., description="Magnitude of change in %")
    recent_days: int = Field(28, ge=7, le=90, description="Days to analyze")


class TrendExplainResponse(BaseModel):
    """Explanation for a specific trend."""
    trend_name: str
    trend_direction: str
    trend_magnitude_pct: float
    leading_indicators: List[LeadingIndicatorResponse]
    summary: str
    

# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/analyze", response_model=CausalAnalysisResponse)
async def analyze_causal_relationships(
    days: int = Query(90, ge=30, le=365, description="Days of history to analyze"),
    output_metric: str = Query("efficiency", description="'efficiency' or 'pace'"),
    db: Session = Depends(get_db),
    current_user: Athlete = Depends(get_current_user),
):
    """
    Discover leading indicators for this athlete.
    
    Performs dual-frequency causal analysis:
    - Readiness Loop (0-7 days): Sleep, HRV, Stress, Soreness, Resting HR
    - Fitness Loop (14-42 days): Volume, Threshold Work, Long Runs, Consistency, ACWR
    
    Returns statistically significant leading indicators with Granger causality p-values.
    
    **Interpretation:**
    - Lower p-value = stronger evidence that input PRECEDES performance change
    - Lag = how many days before the effect appeared in your data
    - This is YOUR data, not population averages
    """
    engine = CausalAttributionEngine(db)
    
    result = engine.analyze(
        athlete_id=current_user.id,
        analysis_days=days,
        output_metric=output_metric,
    )
    
    return CausalAnalysisResponse(
        athlete_id=result.athlete_id,
        analysis_date=result.analysis_date.isoformat(),
        analysis_period_days=result.analysis_period_days,
        readiness_indicators=[
            LeadingIndicatorResponse(**i.to_dict()) for i in result.readiness_indicators
        ],
        fitness_indicators=[
            LeadingIndicatorResponse(**i.to_dict()) for i in result.fitness_indicators
        ],
        top_indicators=[
            LeadingIndicatorResponse(**i.to_dict()) for i in result.top_indicators
        ],
        data_quality_score=result.data_quality_score,
        data_quality_notes=result.data_quality_notes,
        context_block=result.context_block,
    )


@router.post("/explain-trend", response_model=TrendExplainResponse)
async def explain_trend(
    request: TrendExplainRequest,
    db: Session = Depends(get_db),
    current_user: Athlete = Depends(get_current_user),
):
    """
    "Why This Trend?" - Explain a specific performance trend.
    
    Given a trend (e.g., "Efficiency up 12% over 28 days"), this endpoint
    discovers what input changes PRECEDED the trend.
    
    **Example use case:**
    - Dashboard shows: "Efficiency +12% (last 28 days)"
    - User clicks "Why?"
    - Response: "Sleep increased 45min/night starting 3 weeks ago (Granger p=0.02)"
    
    **Philosophy:**
    - We report what preceded the change
    - We don't claim causation, but statistical precedence
    - The athlete decides what to test
    """
    engine = CausalAttributionEngine(db)
    
    indicators = engine.analyze_trend(
        athlete_id=current_user.id,
        trend_name=request.trend_name,
        trend_direction=request.trend_direction,
        trend_magnitude_pct=request.trend_magnitude_pct,
        recent_days=request.recent_days,
    )
    
    # Generate summary
    if indicators:
        top = indicators[0]
        summary = f"Data suggests: {top.input_name} changes {top.lag_days} days prior may have contributed."
        if top.confidence in [CausalConfidence.HIGH, CausalConfidence.MODERATE]:
            summary += f" (Granger p={top.granger_p:.3f})"
    else:
        summary = "No clear leading indicators found. Consider logging more data."
    
    return TrendExplainResponse(
        trend_name=request.trend_name,
        trend_direction=request.trend_direction,
        trend_magnitude_pct=request.trend_magnitude_pct,
        leading_indicators=[
            LeadingIndicatorResponse(**i.to_dict()) for i in indicators
        ],
        summary=summary,
    )


@router.get("/context-block", response_model=str)
async def get_causal_context_block(
    days: int = Query(90, ge=30, le=180, description="Days of history to analyze"),
    db: Session = Depends(get_db),
    current_user: Athlete = Depends(get_current_user),
):
    """
    Get the causal context block for AI Coach injection.
    
    This returns a plain text block summarizing discovered leading indicators,
    formatted for injection into GPT/Claude prompts for smarter coaching.
    
    **Usage:**
    Inject into AI Coach system prompt to make recommendations aware of
    what inputs historically PRECEDED performance changes for this athlete.
    """
    engine = CausalAttributionEngine(db)
    
    result = engine.analyze(
        athlete_id=current_user.id,
        analysis_days=days,
    )
    
    return result.context_block


@router.get("/readiness", response_model=List[LeadingIndicatorResponse])
async def get_readiness_indicators(
    days: int = Query(90, ge=30, le=365),
    db: Session = Depends(get_db),
    current_user: Athlete = Depends(get_current_user),
):
    """
    Get only Readiness Loop indicators (0-7 day lag).
    
    These are acute readiness factors:
    - Sleep duration
    - HRV
    - Stress level
    - Muscle soreness
    - Resting heart rate
    """
    engine = CausalAttributionEngine(db)
    
    result = engine.analyze(
        athlete_id=current_user.id,
        analysis_days=days,
    )
    
    return [
        LeadingIndicatorResponse(**i.to_dict()) 
        for i in result.readiness_indicators
        if i.confidence != CausalConfidence.INSUFFICIENT
    ]


@router.get("/fitness", response_model=List[LeadingIndicatorResponse])
async def get_fitness_indicators(
    days: int = Query(90, ge=30, le=365),
    db: Session = Depends(get_db),
    current_user: Athlete = Depends(get_current_user),
):
    """
    Get only Fitness Loop indicators (14-42 day lag).
    
    These are chronic adaptation factors:
    - Weekly volume
    - Threshold work percentage
    - Long run percentage
    - Training consistency
    - ACWR (Acute:Chronic Workload Ratio)
    """
    engine = CausalAttributionEngine(db)
    
    result = engine.analyze(
        athlete_id=current_user.id,
        analysis_days=days,
    )
    
    return [
        LeadingIndicatorResponse(**i.to_dict()) 
        for i in result.fitness_indicators
        if i.confidence != CausalConfidence.INSUFFICIENT
    ]


@router.get("/simple-patterns")
async def get_simple_patterns(
    min_runs: int = Query(10, ge=5, le=50, description="Minimum runs required"),
    db: Session = Depends(get_db),
    current_user: Athlete = Depends(get_current_user),
):
    """
    SIMPLE PATTERN MATCHING (No statistics required!)
    
    Compares your BEST runs to your WORST runs and finds differences.
    Only needs 10+ activities - no daily check-ins required.
    
    **How it works:**
    1. Takes your top 20% runs (by efficiency) as "best"
    2. Takes your bottom 20% as "worst"
    3. Compares training patterns leading up to each group
    4. Reports what was different
    
    **Example output:**
    "Your top 5 runs had ~45km in trailing 3 weeks vs ~28km before your worst runs."
    
    **Perfect for:**
    - Athletes who don't log daily check-ins
    - Quick insights from activity data alone
    - Understanding YOUR personal patterns
    """
    engine = CausalAttributionEngine(db)
    
    patterns = engine.get_simple_patterns(
        athlete_id=current_user.id,
        min_runs=min_runs,
    )
    
    if not patterns:
        return {
            "message": "Need more runs to detect patterns.",
            "min_runs_required": min_runs,
            "suggestion": "Keep training! Patterns emerge after 10+ runs.",
            "patterns": [],
        }
    
    return {
        "message": "Patterns discovered from your best vs worst runs:",
        "patterns": patterns,
        "methodology": "Compared top 20% runs (by efficiency) to bottom 20%",
        "note": "These are YOUR patterns - not population averages.",
    }
