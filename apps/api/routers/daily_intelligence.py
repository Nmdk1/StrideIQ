"""
Daily Intelligence API (Phase 2D)

Endpoints for the frontend to retrieve intelligence insights.
These power the calendar card's daily intelligence display.

Design:
    - GET /today returns pre-computed insights (from the morning task)
    - GET /{date} returns insights for a specific date
    - POST /compute triggers on-demand computation (for pull-to-refresh)
    - No mutation of the training plan — read-only intelligence surface

Sources:
    docs/TRAINING_PLAN_REBUILD_PLAN.md (Phase 2D)
"""

from datetime import date, datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from core.database import get_db
from core.auth import get_current_user
from models import Athlete, InsightLog, DailyReadiness

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/intelligence", tags=["Daily Intelligence"])


# =============================================================================
# SCHEMAS
# =============================================================================

class InsightResponse(BaseModel):
    """A single intelligence insight for display."""
    model_config = ConfigDict(from_attributes=True)

    rule_id: str
    mode: str                  # "inform", "suggest", "flag", "ask", "log"
    message: Optional[str] = None
    data_cited: Optional[dict] = None
    confidence: Optional[float] = None
    trigger_date: date
    readiness_score: Optional[float] = None


class ReadinessResponse(BaseModel):
    """Readiness score summary."""
    score: Optional[float] = None
    confidence: Optional[float] = None
    components: Optional[dict] = None
    computed_at: Optional[datetime] = None


class DailyIntelligenceResponse(BaseModel):
    """Complete intelligence response for a day."""
    date: date
    readiness: Optional[ReadinessResponse] = None
    insights: List[InsightResponse] = []
    highest_mode: Optional[str] = None
    insight_count: int = 0
    has_flag: bool = False


class ComputeResponse(BaseModel):
    """Response from on-demand computation."""
    status: str
    date: date
    readiness_score: Optional[float] = None
    insight_count: int = 0
    highest_mode: Optional[str] = None


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/today", response_model=DailyIntelligenceResponse)
def get_today_intelligence(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get today's intelligence insights for the authenticated athlete.

    Returns pre-computed insights from the morning intelligence task.
    If no insights exist yet (task hasn't run), returns empty.
    The calendar card uses this to display daily intelligence.
    """
    return _get_intelligence_for_date(current_user.id, date.today(), db)


@router.get("/{target_date}", response_model=DailyIntelligenceResponse)
def get_intelligence_for_date(
    target_date: date,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get intelligence insights for a specific date.

    Useful for reviewing past days' insights in the calendar view.
    """
    # Don't allow future dates
    if target_date > date.today():
        raise HTTPException(status_code=400, detail="Cannot get intelligence for future dates")

    return _get_intelligence_for_date(current_user.id, target_date, db)


@router.post("/compute", response_model=ComputeResponse)
def compute_intelligence_now(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Trigger on-demand intelligence computation for today.

    Used when:
    - Athlete pulls to refresh and the morning task hasn't run yet
    - After a Strava sync brings in new activity data
    - Athlete wants fresh readiness/intelligence after a check-in

    This runs synchronously (not via Celery) for immediate response.
    """
    from services.readiness_score import ReadinessScoreCalculator
    from services.daily_intelligence import DailyIntelligenceEngine

    today = date.today()

    try:
        # Compute readiness
        readiness_calc = ReadinessScoreCalculator()
        readiness_result = readiness_calc.compute(
            athlete_id=current_user.id,
            target_date=today,
            db=db,
        )

        # Run intelligence
        engine = DailyIntelligenceEngine()
        intel_result = engine.evaluate(
            athlete_id=current_user.id,
            target_date=today,
            db=db,
            readiness_score=readiness_result.score,
        )

        db.commit()

        highest = intel_result.highest_mode
        return ComputeResponse(
            status="ok",
            date=today,
            readiness_score=round(readiness_result.score, 1) if readiness_result.score else None,
            insight_count=len(intel_result.insights),
            highest_mode=highest.value if highest else None,
        )

    except Exception as e:
        db.rollback()
        logger.error(f"On-demand intelligence failed for {current_user.id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Intelligence computation failed")


@router.get("/history/recent", response_model=List[DailyIntelligenceResponse])
def get_recent_intelligence(
    days: int = Query(default=7, ge=1, le=30),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get intelligence insights for the last N days.

    Useful for the weekly view / trend analysis on the frontend.
    """
    results = []
    today = date.today()
    for i in range(days):
        d = today - timedelta(days=i)
        results.append(_get_intelligence_for_date(current_user.id, d, db))

    return results


# =============================================================================
# INTERNAL HELPERS
# =============================================================================

def _get_intelligence_for_date(
    athlete_id: UUID, target_date: date, db: Session,
) -> DailyIntelligenceResponse:
    """Build intelligence response from stored InsightLog + DailyReadiness."""

    # Get insights from InsightLog
    insights = (
        db.query(InsightLog)
        .filter(
            InsightLog.athlete_id == athlete_id,
            InsightLog.trigger_date == target_date,
        )
        .order_by(InsightLog.created_at.desc())
        .all()
    )

    # Get readiness from DailyReadiness
    readiness_row = (
        db.query(DailyReadiness)
        .filter(
            DailyReadiness.athlete_id == athlete_id,
            DailyReadiness.date == target_date,
        )
        .first()
    )

    readiness = None
    if readiness_row:
        readiness = ReadinessResponse(
            score=readiness_row.score,
            confidence=readiness_row.confidence,
            components=readiness_row.components,
            computed_at=readiness_row.created_at if hasattr(readiness_row, 'created_at') else None,
        )

    # Filter out LOG-mode insights for user-facing display
    # (LOG insights are internal tracking, not for the athlete)
    visible_insights = [
        InsightResponse(
            rule_id=i.rule_id,
            mode=i.mode,
            message=i.message,
            data_cited=i.data_cited,
            confidence=i.confidence,
            trigger_date=i.trigger_date,
            readiness_score=i.readiness_score,
        )
        for i in insights
        if i.mode != "log"
    ]

    # Determine highest mode
    mode_priority = {"inform": 1, "ask": 2, "suggest": 3, "flag": 4}
    highest_mode = None
    if visible_insights:
        highest_mode = max(
            visible_insights,
            key=lambda x: mode_priority.get(x.mode, 0),
        ).mode

    return DailyIntelligenceResponse(
        date=target_date,
        readiness=readiness,
        insights=visible_insights,
        highest_mode=highest_mode,
        insight_count=len(visible_insights),
        has_flag=any(i.mode == "flag" for i in visible_insights),
    )
