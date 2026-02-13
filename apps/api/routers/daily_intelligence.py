"""
Daily Intelligence API (Phase 2D + 3A + 3B)

Endpoints for the frontend to retrieve intelligence insights and narrations.
These power the calendar card's daily intelligence display.

Design:
    - GET /today returns pre-computed insights + narrations (from the morning task)
    - GET /{date} returns insights for a specific date
    - POST /compute triggers on-demand computation (for pull-to-refresh)
    - GET /narration/quality returns narration quality metrics (for admin/gating)
    - GET /workout-narrative/{target_date} returns Phase 3B contextual workout note
    - No mutation of the training plan — read-only intelligence surface

Sources:
    docs/TRAINING_PLAN_REBUILD_PLAN.md (Phase 2D, 3A, 3B)
"""

from datetime import date, datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from core.database import get_db
from core.auth import get_current_user
from models import Athlete, InsightLog, DailyReadiness, NarrationLog

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
    narrative: Optional[str] = None       # Phase 3A: coach narration (None if suppressed)
    data_cited: Optional[dict] = None
    confidence: Optional[float] = None
    trigger_date: date
    readiness_score: Optional[float] = None


class NarrationQualityResponse(BaseModel):
    """Narration quality metrics for admin monitoring and Phase 3B gating."""
    window_start: date
    window_end: date
    total_narrations: int = 0
    total_criteria_checks: int = 0
    total_criteria_passed: int = 0
    score: float = 0.0
    factual_pass_rate: float = 0.0
    no_metrics_pass_rate: float = 0.0
    actionable_pass_rate: float = 0.0
    passes_90_threshold: bool = False
    suppression_rate: float = 0.0
    contradiction_rate: float = 0.0


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


@router.get("/narration/quality", response_model=NarrationQualityResponse)
def get_narration_quality(
    days: int = Query(default=7, ge=1, le=28),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get narration quality metrics for the last N days.

    Used for:
    - Admin monitoring of narration quality
    - Phase 3B gate check (90% for 4 weeks)
    - Identifying which criterion is weakest
    """
    today = date.today()
    window_start = today - timedelta(days=days)

    narrations = (
        db.query(NarrationLog)
        .filter(
            NarrationLog.athlete_id == current_user.id,
            NarrationLog.trigger_date >= window_start,
            NarrationLog.trigger_date <= today,
            NarrationLog.score.isnot(None),
        )
        .all()
    )

    total = len(narrations)
    if total == 0:
        return NarrationQualityResponse(
            window_start=window_start,
            window_end=today,
        )

    factual_pass = sum(1 for n in narrations if n.factually_correct)
    metrics_pass = sum(1 for n in narrations if n.no_raw_metrics)
    action_pass = sum(1 for n in narrations if n.actionable_language)
    suppressed = sum(1 for n in narrations if n.suppressed)
    contradictions = sum(1 for n in narrations if n.contradicts_engine)

    total_checks = total * 3
    total_passed = factual_pass + metrics_pass + action_pass
    score = total_passed / total_checks if total_checks > 0 else 0.0

    return NarrationQualityResponse(
        window_start=window_start,
        window_end=today,
        total_narrations=total,
        total_criteria_checks=total_checks,
        total_criteria_passed=total_passed,
        score=round(score, 4),
        factual_pass_rate=round(factual_pass / total, 4),
        no_metrics_pass_rate=round(metrics_pass / total, 4),
        actionable_pass_rate=round(action_pass / total, 4),
        passes_90_threshold=score >= 0.90,
        suppression_rate=round(suppressed / total, 4),
        contradiction_rate=round(contradictions / total, 4),
    )


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
            narrative=i.narrative if hasattr(i, "narrative") else None,  # Phase 3A
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


# =============================================================================
# Phase 3B: Contextual Workout Narrative
# =============================================================================

class WorkoutNarrativeResponse(BaseModel):
    """Response for Phase 3B contextual workout narrative."""
    narrative: Optional[str] = None
    suppressed: bool = False
    reason: Optional[str] = None
    eligibility: Optional[dict] = None


@router.get(
    "/workout-narrative/{target_date}",
    response_model=WorkoutNarrativeResponse,
)
def get_workout_narrative(
    target_date: date,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate a contextual workout narrative for the target date (Phase 3B).

    Premium tier only.  Returns a fresh narrative on each request —
    never cached, never templated.  If the generator can't produce
    something genuinely contextual, returns null narrative with reason.
    """
    from services.phase3_eligibility import get_3b_eligibility

    elig = get_3b_eligibility(current_user.id, db, as_of=target_date)
    eligibility_dict = {
        "eligible": elig.eligible,
        "reason": elig.reason,
        "confidence": elig.confidence,
        "provisional": elig.provisional,
    }

    if not elig.eligible:
        return WorkoutNarrativeResponse(
            suppressed=True,
            reason=elig.reason,
            eligibility=eligibility_dict,
        )

    # Generate narrative
    from services.workout_narrative_generator import generate_workout_narrative

    # Get Gemini client (best-effort; None = suppressed with reason)
    gemini_client = None
    try:
        from tasks.intelligence_tasks import _get_gemini_client
        gemini_client = _get_gemini_client()
    except Exception:
        pass

    result = generate_workout_narrative(
        athlete_id=current_user.id,
        target_date=target_date,
        db=db,
        gemini_client=gemini_client,
    )

    # Persist audit record for founder QA review (first 50 narratives).
    # Uses the existing NarrationLog table with rule_id="WORKOUT_NARRATIVE".
    try:
        log = NarrationLog(
            athlete_id=current_user.id,
            trigger_date=target_date,
            rule_id="WORKOUT_NARRATIVE",
            narration_text=result.narrative,
            prompt_used=result.prompt_used,
            suppressed=result.suppressed,
            suppression_reason=result.suppression_reason,
            model_used=result.model_used,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
            # Store eligibility evidence as ground_truth for review
            ground_truth={
                "eligibility": eligibility_dict,
                "suppression_reason": result.suppression_reason,
            },
        )
        db.add(log)
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Failed to persist workout narrative audit log", exc_info=True)

    return WorkoutNarrativeResponse(
        narrative=result.narrative,
        suppressed=result.suppressed,
        reason=result.suppression_reason,
        eligibility=eligibility_dict,
    )
