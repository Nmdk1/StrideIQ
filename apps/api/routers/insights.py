"""
Insights API Router

Proactive, personalized insights for athletes.
This is the "brain view" of training - answering WHY, not just WHAT.

Endpoints:
- GET /insights/active - Get active insights (ranked, personalized)
- GET /insights/build-status - Get current build KPIs and trajectory
- GET /insights/intelligence - Get athlete intelligence bank
- POST /insights/{id}/dismiss - Dismiss an insight
- POST /insights/{id}/save - Save insight to profile
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional, List, Literal
from uuid import UUID
from datetime import date, timedelta
from pydantic import BaseModel, ConfigDict

from core.database import get_db
from core.auth import get_current_user
from models import Athlete, CalendarInsight
from services.insight_aggregator import (
    InsightAggregator,
    get_active_insights,
    InsightType,
)

router = APIRouter(prefix="/v1/insights", tags=["Insights"])


# =============================================================================
# SCHEMAS
# =============================================================================

class InsightResponse(BaseModel):
    """Single insight for display"""
    id: UUID
    insight_type: str
    priority: int
    title: str
    content: str
    insight_date: date
    activity_id: Optional[UUID] = None
    data: Optional[dict] = None
    is_dismissed: bool = False
    
    model_config = ConfigDict(from_attributes=True)


class ActiveInsightsResponse(BaseModel):
    """Response with active insights"""
    insights: List[InsightResponse]
    is_elite: bool
    total_available: int


class FeedEvidenceItem(BaseModel):
    label: str
    value: str


class FeedActionItem(BaseModel):
    label: str
    href: str


class FeedConfidence(BaseModel):
    label: str
    score: float
    details: Optional[str] = None


class InsightFeedCard(BaseModel):
    key: str
    type: Literal["trend", "load_response", "plan", "readiness", "personal_bests"]
    priority: int
    title: str
    summary: str
    confidence: FeedConfidence
    evidence: List[FeedEvidenceItem] = []
    actions: List[FeedActionItem] = []


class InsightFeedResponse(BaseModel):
    generated_at: str
    cards: List[InsightFeedCard]


class KPIResponse(BaseModel):
    """Key Performance Indicator"""
    name: str
    current_value: Optional[str] = None
    start_value: Optional[str] = None
    change: Optional[str] = None
    trend: Optional[str] = None  # "up", "down", "stable"


class BuildStatusResponse(BaseModel):
    """Current build/training plan status"""
    has_active_plan: bool
    plan_name: Optional[str] = None
    current_week: Optional[int] = None
    total_weeks: Optional[int] = None
    current_phase: Optional[str] = None
    phase_focus: Optional[str] = None
    goal_race_name: Optional[str] = None
    goal_race_date: Optional[date] = None
    days_to_race: Optional[int] = None
    progress_percent: Optional[float] = None
    
    # KPIs
    kpis: List[KPIResponse] = []
    
    # Trajectory
    projected_time: Optional[str] = None
    confidence: Optional[str] = None
    
    # This week
    week_focus: Optional[str] = None
    key_session: Optional[str] = None


class IntelligenceItemResponse(BaseModel):
    """Single learning item"""
    text: str
    source: str = "n1"  # "n1" or "population"
    confidence: Optional[float] = None


class PatternResponse(BaseModel):
    """Detected pattern"""
    name: str
    description: str
    data: Optional[dict] = None


class AthleteIntelligenceResponse(BaseModel):
    """Athlete intelligence bank"""
    what_works: List[IntelligenceItemResponse]
    what_doesnt: List[IntelligenceItemResponse]
    patterns: List[PatternResponse]
    injury_patterns: List[IntelligenceItemResponse]
    career_prs: dict


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/active", response_model=ActiveInsightsResponse)
def get_insights(
    limit: int = Query(10, ge=1, le=50),
    include_dismissed: bool = Query(False),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get active insights for the current athlete.
    
    Returns personalized, ranked insights generated from recent activity.
    Elite members see the full product. (We intentionally avoid "premium" tier fragmentation.)
    """
    # Treat all paid tiers as "elite access" (until we migrate old tier labels).
    is_elite = getattr(current_user, "has_active_subscription", False) or current_user.subscription_tier == "elite"
    
    # Get persisted insights
    insights = get_active_insights(
        db=db,
        athlete_id=current_user.id,
        limit=limit,
        include_dismissed=include_dismissed,
    )

    # Build response
    response_insights = []
    for i in insights[:limit]:
        response_insights.append(InsightResponse(
            id=i.id,
            insight_type=i.insight_type,
            priority=i.priority,
            title=i.title,
            content=i.content,
            insight_date=i.insight_date,
            activity_id=i.activity_id,
            data=i.generation_data,
            is_dismissed=i.is_dismissed,
        ))
    
    return ActiveInsightsResponse(
        insights=response_insights,
        is_elite=is_elite,
        total_available=len(insights),
    )


@router.get("/feed", response_model=InsightFeedResponse)
def get_insight_feed(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
    max_cards: int = Query(5, ge=3, le=10),
):
    """
    Ranked insight feed with evidence + actions.
    Deterministic (no LLM calls); built from existing engines.
    """
    from services.insight_feed import build_insight_feed_cards

    payload = build_insight_feed_cards(db=db, athlete=current_user, max_cards=max_cards)
    return payload


@router.get("/build-status", response_model=BuildStatusResponse)
def get_build_status(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get current build/training plan status.
    
    Returns KPIs, trajectory, and phase context for active training plan.
    """
    aggregator = InsightAggregator(db, current_user)
    build_status = aggregator.get_build_status()
    
    if not build_status:
        return BuildStatusResponse(has_active_plan=False)
    
    # Calculate progress
    progress = None
    if build_status.current_week and build_status.total_weeks:
        progress = (build_status.current_week / build_status.total_weeks) * 100
    
    # Build KPIs (would be more sophisticated in production)
    kpis = []
    
    if build_status.threshold_pace_current:
        kpis.append(KPIResponse(
            name="Threshold Pace",
            current_value=f"{build_status.threshold_pace_current:.2f}/mi",
            start_value=f"{build_status.threshold_pace_start:.2f}/mi" if build_status.threshold_pace_start else None,
            trend="up" if build_status.threshold_pace_start and build_status.threshold_pace_current < build_status.threshold_pace_start else "stable",
        ))
    
    if build_status.ef_current:
        kpis.append(KPIResponse(
            name="Efficiency Factor",
            current_value=f"{build_status.ef_current:.2f}",
            start_value=f"{build_status.ef_start:.2f}" if build_status.ef_start else None,
            trend="up" if build_status.ef_start and build_status.ef_current > build_status.ef_start else "stable",
        ))
    
    return BuildStatusResponse(
        has_active_plan=True,
        plan_name=build_status.plan_name,
        current_week=build_status.current_week,
        total_weeks=build_status.total_weeks,
        current_phase=build_status.current_phase,
        phase_focus=build_status.phase_focus,
        goal_race_name=build_status.goal_race_name,
        goal_race_date=build_status.goal_race_date,
        days_to_race=build_status.days_to_race,
        progress_percent=progress,
        kpis=kpis,
        projected_time=build_status.projected_time,
        confidence=build_status.confidence,
        week_focus=build_status.week_focus,
        key_session=build_status.key_session,
    )


@router.get("/intelligence", response_model=AthleteIntelligenceResponse)
def get_athlete_intelligence(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get athlete intelligence bank.
    
    Returns banked learnings: what works, what doesn't, patterns, injury history.
    This is part of Elite.
    """
    is_elite = getattr(current_user, "has_active_subscription", False) or current_user.subscription_tier == "elite"
    
    if not is_elite:
        raise HTTPException(
            status_code=403,
            detail="Athlete Intelligence requires Elite tier."
        )
    
    aggregator = InsightAggregator(db, current_user)
    intelligence = aggregator.get_athlete_intelligence()

    def _to_item(x) -> IntelligenceItemResponse:
        # Backward/forward compatible: handle both strings and dicts from the service layer.
        if isinstance(x, dict):
            return IntelligenceItemResponse(
                text=str(x.get("text") or ""),
                source=str(x.get("source") or "n1"),
                confidence=x.get("confidence"),
            )
        return IntelligenceItemResponse(text=str(x), source="n1")

    return AthleteIntelligenceResponse(
        what_works=[
            _to_item(item) for item in (intelligence.what_works or [])
        ],
        what_doesnt=[
            _to_item(item) for item in (intelligence.what_doesnt or [])
        ],
        patterns=[
            PatternResponse(
                name=str(k),
                description=str(v),
                data=v if isinstance(v, dict) else None,
            )
            for k, v in (intelligence.patterns or {}).items()
        ],
        injury_patterns=[
            _to_item(item) for item in (intelligence.injury_patterns or [])
        ],
        career_prs=intelligence.career_prs,
    )


@router.post("/{insight_id}/dismiss")
def dismiss_insight(
    insight_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Dismiss an insight (hide from active list).
    """
    insight = (
        db.query(CalendarInsight)
        .filter(
            CalendarInsight.id == insight_id,
            CalendarInsight.athlete_id == current_user.id,
        )
        .first()
    )
    
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")
    
    insight.is_dismissed = True
    db.commit()
    
    return {"status": "dismissed", "insight_id": str(insight_id)}


@router.post("/{insight_id}/save")
def save_insight(
    insight_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Save an insight to athlete profile (bank it for future reference).
    
    This would save to a separate athlete_intelligence table in production.
    """
    insight = (
        db.query(CalendarInsight)
        .filter(
            CalendarInsight.id == insight_id,
            CalendarInsight.athlete_id == current_user.id,
        )
        .first()
    )
    
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")
    
    # In production, this would copy to athlete_intelligence table
    # For now, we just acknowledge
    
    return {
        "status": "saved",
        "insight_id": str(insight_id),
        "message": "Insight saved to your profile"
    }


@router.post("/generate")
def generate_insights_now(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manually trigger insight generation.
    
    This is normally done automatically on activity sync.
    """
    aggregator = InsightAggregator(db, current_user)
    insights = aggregator.generate_insights()
    saved = aggregator.persist_insights(insights)
    
    return {
        "status": "generated",
        "insights_generated": len(insights),
        "insights_saved": saved,
    }
