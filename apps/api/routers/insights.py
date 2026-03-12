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
from core.auth import get_current_user, require_tier
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
    evidence: Optional[dict] = None
    fingerprint: Optional[str] = None  # suppression key for 3C N=1 items


class PatternResponse(BaseModel):
    """Detected pattern"""
    name: str
    description: str
    data: Optional[dict] = None


class N1EligibilityMeta(BaseModel):
    """Phase 3C eligibility metadata returned alongside intelligence."""
    eligible: bool
    reason: str
    confidence: float = 0.0
    provisional: bool = False


class AthleteIntelligenceResponse(BaseModel):
    """Athlete intelligence bank"""
    what_works: List[IntelligenceItemResponse]
    what_doesnt: List[IntelligenceItemResponse]
    patterns: List[PatternResponse]
    injury_patterns: List[IntelligenceItemResponse]
    career_prs: dict
    n1_eligibility: Optional[N1EligibilityMeta] = None


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
    current_user: Athlete = Depends(require_tier(["guided"])),
    db: Session = Depends(get_db),
):
    """
    Get athlete intelligence bank.

    Requires Guided or above tier.  Returns banked learnings: what works,
    what doesn't, patterns, injury history.  Guided + Premium tiers get N=1
    personalized insights (Phase 3C) when eligibility gates are met.
    """

    aggregator = InsightAggregator(db, current_user)
    intelligence = aggregator.get_athlete_intelligence()

    def _to_item(x) -> IntelligenceItemResponse:
        # Backward/forward compatible: handle both strings and dicts from the service layer.
        if isinstance(x, dict):
            return IntelligenceItemResponse(
                text=str(x.get("text") or ""),
                source=str(x.get("source") or "n1"),
                confidence=x.get("confidence"),
                evidence=x.get("evidence"),
            )
        return IntelligenceItemResponse(text=str(x), source="n1")

    what_works = [_to_item(item) for item in (intelligence.what_works or [])]
    what_doesnt = [_to_item(item) for item in (intelligence.what_doesnt or [])]
    patterns_list = [
        PatternResponse(
            name=str(k),
            description=str(v),
            data=v if isinstance(v, dict) else None,
        )
        for k, v in (intelligence.patterns or {}).items()
    ]

    # --- Phase 3C: N=1 personalized insights ---
    n1_meta = None
    try:
        from services.phase3_eligibility import get_3c_eligibility
        from services.n1_insight_generator import generate_n1_insights

        elig = get_3c_eligibility(current_user.id, db)
        n1_meta = N1EligibilityMeta(
            eligible=elig.eligible,
            reason=elig.reason,
            confidence=elig.confidence,
            provisional=elig.provisional,
        )
        if elig.eligible:
            n1_insights = generate_n1_insights(current_user.id, db)
            for ins in n1_insights:
                item = IntelligenceItemResponse(
                    text=ins.text,
                    source=ins.source,
                    confidence=ins.confidence,
                    evidence=ins.evidence,
                    fingerprint=ins.fingerprint,
                )
                if ins.category == "what_works":
                    what_works.append(item)
                elif ins.category == "what_doesnt":
                    what_doesnt.append(item)
                else:
                    patterns_list.append(PatternResponse(
                        name="N=1 Pattern",
                        description=ins.text,
                        data=ins.evidence,
                    ))
    except Exception:
        # N=1 is additive — never break the base endpoint.
        pass

    return AthleteIntelligenceResponse(
        what_works=what_works,
        what_doesnt=what_doesnt,
        patterns=patterns_list,
        injury_patterns=[
            _to_item(item) for item in (intelligence.injury_patterns or [])
        ],
        career_prs=intelligence.career_prs,
        n1_eligibility=n1_meta,
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


# =============================================================================
# FOUNDER / ADMIN ENDPOINTS — Phase 3C Graduation Controls
# =============================================================================

class N1ReviewItem(BaseModel):
    """A single 3C insight surfaced for founder review."""
    athlete_id: str
    text: str
    fingerprint: str
    confidence: float
    category: str
    evidence: Optional[dict] = None
    eligibility_reason: str
    correlations_tested: int = 0
    significant_after_correction: int = 0


class N1ReviewResponse(BaseModel):
    """Batch of 3C insights ready for founder review."""
    generated_at: str
    kill_switch_active: bool
    items: List[N1ReviewItem]
    total: int


class N1SuppressRequest(BaseModel):
    """Request to suppress a single N=1 insight pattern for an athlete."""
    athlete_id: str
    fingerprint: str
    reason: Optional[str] = None


def _is_founder(current_user: Athlete) -> bool:
    """Check if current user is the founder (mbshaf@gmail.com)."""
    import os
    owner_id = os.getenv("OWNER_ATHLETE_ID", "")
    return str(current_user.id) == owner_id or getattr(current_user, "email", "") == "mbshaf@gmail.com"


@router.get("/admin/n1-review", response_model=N1ReviewResponse)
def founder_review_n1_insights(
    athlete_id: Optional[str] = Query(None, description="Filter to specific athlete"),
    current_user: Athlete = Depends(require_tier(["guided"])),
    db: Session = Depends(get_db),
):
    """
    Founder-only: Review generated 3C N=1 insights before broader rollout.

    Lists insights that would surface for eligible athletes, along with
    eligibility context and evidence payload for quality judgment.
    Suppressed insights are excluded (already filtered in generator).
    """
    if not _is_founder(current_user):
        raise HTTPException(status_code=403, detail="Founder-only endpoint.")

    import os
    from datetime import datetime as _dt
    from services.phase3_eligibility import get_3c_eligibility, KILL_SWITCH_3C_ENV
    from services.n1_insight_generator import generate_n1_insights

    kill_switch_active = os.getenv(KILL_SWITCH_3C_ENV, "").lower() in ("1", "true", "yes")

    # Determine which athletes to review
    target_ids: list
    if athlete_id:
        from models import Athlete as AthleteModel
        a = db.query(AthleteModel).filter(
            AthleteModel.id == athlete_id
        ).first()
        target_ids = [a.id] if a else []
    else:
        from models import Athlete as AthleteModel
        from services.phase3_eligibility import TIERS_3C
        athletes = db.query(AthleteModel).filter(
            AthleteModel.subscription_tier.in_(TIERS_3C)
        ).limit(50).all()
        target_ids = [a.id for a in athletes]

    items: List[N1ReviewItem] = []
    for aid in target_ids:
        try:
            elig = get_3c_eligibility(aid, db)
            if not elig.eligible:
                continue
            n1_insights = generate_n1_insights(aid, db)
            for ins in n1_insights:
                items.append(N1ReviewItem(
                    athlete_id=str(aid),
                    text=ins.text,
                    fingerprint=ins.fingerprint,
                    confidence=ins.confidence,
                    category=ins.category,
                    evidence=ins.evidence,
                    eligibility_reason=elig.reason,
                    correlations_tested=elig.evidence.get("correlations_tested", 0),
                    significant_after_correction=elig.evidence.get("significant_after_correction", 0),
                ))
        except Exception:
            continue

    return N1ReviewResponse(
        generated_at=_dt.utcnow().isoformat() + "Z",
        kill_switch_active=kill_switch_active,
        items=items,
        total=len(items),
    )


@router.post("/admin/n1-suppress")
def founder_suppress_n1_insight(
    body: N1SuppressRequest,
    current_user: Athlete = Depends(require_tier(["guided"])),
    db: Session = Depends(get_db),
):
    """
    Founder-only: Suppress a specific 3C N=1 insight pattern for an athlete.

    Suppression is keyed by insight fingerprint (input_name:direction:output_metric).
    Once suppressed, the pattern will not surface for that athlete even if
    the correlation remains significant.  Other athletes and other patterns
    are unaffected.  3C remains globally active.
    """
    if not _is_founder(current_user):
        raise HTTPException(status_code=403, detail="Founder-only endpoint.")

    from models import N1InsightSuppression
    from sqlalchemy.exc import IntegrityError

    existing = db.query(N1InsightSuppression).filter(
        N1InsightSuppression.athlete_id == body.athlete_id,
        N1InsightSuppression.insight_fingerprint == body.fingerprint,
    ).first()

    if existing:
        return {
            "status": "already_suppressed",
            "athlete_id": body.athlete_id,
            "fingerprint": body.fingerprint,
        }

    record = N1InsightSuppression(
        athlete_id=body.athlete_id,
        insight_fingerprint=body.fingerprint,
        suppressed_by=getattr(current_user, "email", str(current_user.id)),
        reason=body.reason,
    )
    try:
        db.add(record)
        db.commit()
    except IntegrityError:
        db.rollback()
        return {
            "status": "already_suppressed",
            "athlete_id": body.athlete_id,
            "fingerprint": body.fingerprint,
        }

    return {
        "status": "suppressed",
        "athlete_id": body.athlete_id,
        "fingerprint": body.fingerprint,
        "reason": body.reason,
    }
