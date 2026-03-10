"""
Diagnostics API Router

Trust & readiness view:
- Provider health (connected? last sync? last ingestion errors?)
- Ingestion status (coverage/progress for best-efforts extraction)
- Data completeness (counts of key inputs)
- Model readiness (can we responsibly surface insights?)
- Recommended actions (what to do next)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.auth import require_admin
from core.database import get_db
from models import Athlete, Activity, ActivitySplit, DailyCheckin, PersonalBest


router = APIRouter(prefix="/v1/admin/diagnostics", tags=["Admin", "Diagnostics"])


class ProviderHealth(BaseModel):
    provider: Literal["strava", "garmin"]
    connected: bool
    last_sync_at: Optional[str] = None
    detail: Optional[str] = None


class IngestionStatus(BaseModel):
    provider: str
    coverage_pct: float
    total_activities: int
    activities_processed: int
    remaining_activities: int
    last_provider_sync_at: Optional[str] = None
    last_task_status: Optional[str] = None
    last_task_error: Optional[str] = None
    last_task_retry_after_s: Optional[int] = None


class CompletenessCounts(BaseModel):
    activities_total: int
    activities_with_hr: int
    activities_with_splits: int
    splits_total: int
    splits_with_gap: int
    checkins_total: int
    checkins_with_hrv: int
    personal_bests: int


class ModelReadiness(BaseModel):
    efficiency_trend_ready: bool
    load_response_ready: bool
    trend_attribution_ready: bool
    personal_bests_ready: bool
    notes: List[str] = []


class RecommendedAction(BaseModel):
    id: str
    severity: Literal["critical", "recommended", "optional"]
    title: str
    detail: str
    href: str


class DiagnosticsSummaryResponse(BaseModel):
    model_config = {"protected_namespaces": ()}
    
    generated_at: str
    overall_status: Literal["ready", "degraded", "blocked"]
    provider_health: List[ProviderHealth]
    ingestion: Optional[IngestionStatus] = None
    completeness: CompletenessCounts
    model_readiness: ModelReadiness
    actions: List[RecommendedAction]


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bool(v: Any) -> bool:
    return bool(v)


@router.get("/summary", response_model=DiagnosticsSummaryResponse)
def get_diagnostics_summary(
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Trust & readiness summary (operator view).
    Deterministic and cheap: no external provider calls.
    """
    athlete = current_user

    # ---------------------------------------------------------------------
    # Provider health
    # ---------------------------------------------------------------------
    strava_connected = _bool(getattr(athlete, "strava_access_token", None))
    garmin_connected = _bool(getattr(athlete, "garmin_connected", False))

    provider_health: List[ProviderHealth] = [
        ProviderHealth(
            provider="strava",
            connected=strava_connected,
            last_sync_at=getattr(athlete, "last_strava_sync", None).isoformat() if getattr(athlete, "last_strava_sync", None) else None,
            detail="Connected" if strava_connected else "Not connected",
        ),
        ProviderHealth(
            provider="garmin",
            connected=garmin_connected,
            last_sync_at=getattr(athlete, "last_garmin_sync", None).isoformat() if getattr(athlete, "last_garmin_sync", None) else None,
            detail="Connected" if garmin_connected else "Not connected",
        ),
    ]

    # ---------------------------------------------------------------------
    # Ingestion status (best efforts)
    # ---------------------------------------------------------------------
    ingestion: Optional[IngestionStatus] = None
    if strava_connected:
        from services.ingestion_status import get_best_effort_ingestion_status
        from services.ingestion_state import get_ingestion_state_snapshot

        status_obj = get_best_effort_ingestion_status(athlete.id, db, provider="strava")
        snap = get_ingestion_state_snapshot(db, athlete.id, provider="strava")

        ingestion = IngestionStatus(
            provider="strava",
            coverage_pct=status_obj.coverage_pct,
            total_activities=status_obj.total_activities,
            activities_processed=status_obj.activities_processed,
            remaining_activities=status_obj.remaining_activities,
            last_provider_sync_at=status_obj.last_provider_sync_at,
            last_task_status=snap.last_best_efforts_status if snap else None,
            last_task_error=snap.last_best_efforts_error if snap else None,
            last_task_retry_after_s=snap.last_best_efforts_retry_after_s if snap else None,
        )

    # ---------------------------------------------------------------------
    # Data completeness
    # ---------------------------------------------------------------------
    activities_total = (
        db.query(func.count(Activity.id))
        .filter(Activity.athlete_id == athlete.id)
        .scalar()
        or 0
    )

    activities_with_hr = (
        db.query(func.count(Activity.id))
        .filter(Activity.athlete_id == athlete.id, Activity.avg_hr.isnot(None), Activity.avg_hr > 0)
        .scalar()
        or 0
    )

    activities_with_splits = (
        db.query(func.count(func.distinct(ActivitySplit.activity_id)))
        .join(Activity, Activity.id == ActivitySplit.activity_id)
        .filter(Activity.athlete_id == athlete.id)
        .scalar()
        or 0
    )

    splits_total = (
        db.query(func.count(ActivitySplit.id))
        .join(Activity, Activity.id == ActivitySplit.activity_id)
        .filter(Activity.athlete_id == athlete.id)
        .scalar()
        or 0
    )

    splits_with_gap = (
        db.query(func.count(ActivitySplit.id))
        .join(Activity, Activity.id == ActivitySplit.activity_id)
        .filter(Activity.athlete_id == athlete.id, ActivitySplit.gap_seconds_per_mile.isnot(None))
        .scalar()
        or 0
    )

    checkins_total = (
        db.query(func.count(DailyCheckin.id))
        .filter(DailyCheckin.athlete_id == athlete.id)
        .scalar()
        or 0
    )

    checkins_with_hrv = (
        db.query(func.count(DailyCheckin.id))
        .filter(DailyCheckin.athlete_id == athlete.id, DailyCheckin.hrv_rmssd.isnot(None))
        .scalar()
        or 0
    )

    personal_bests = (
        db.query(func.count(PersonalBest.id))
        .filter(PersonalBest.athlete_id == athlete.id)
        .scalar()
        or 0
    )

    completeness = CompletenessCounts(
        activities_total=int(activities_total),
        activities_with_hr=int(activities_with_hr),
        activities_with_splits=int(activities_with_splits),
        splits_total=int(splits_total),
        splits_with_gap=int(splits_with_gap),
        checkins_total=int(checkins_total),
        checkins_with_hrv=int(checkins_with_hrv),
        personal_bests=int(personal_bests),
    )

    # ---------------------------------------------------------------------
    # Model readiness (conservative heuristics)
    # ---------------------------------------------------------------------
    notes: List[str] = []
    efficiency_trend_ready = completeness.activities_with_hr >= 10 and completeness.splits_with_gap > 0
    if not efficiency_trend_ready:
        notes.append("Efficiency trend needs more HR runs and GAP-enabled splits.")

    load_response_ready = completeness.activities_with_hr >= 7
    if not load_response_ready:
        notes.append("Load→Response needs at least ~7 HR runs in the recent window.")

    trend_attribution_ready = completeness.checkins_total >= 7
    if not trend_attribution_ready:
        notes.append("Trend attribution is stronger with at least ~7 check-ins.")

    personal_bests_ready = bool(personal_bests >= 3) or bool(ingestion and ingestion.coverage_pct >= 90.0)
    if not personal_bests_ready:
        notes.append("PB profile improves after best-effort ingestion reaches high coverage.")

    model_readiness = ModelReadiness(
        efficiency_trend_ready=efficiency_trend_ready,
        load_response_ready=load_response_ready,
        trend_attribution_ready=trend_attribution_ready,
        personal_bests_ready=personal_bests_ready,
        notes=notes,
    )

    # ---------------------------------------------------------------------
    # Actions
    # ---------------------------------------------------------------------
    actions: List[RecommendedAction] = []

    if not strava_connected:
        actions.append(
            RecommendedAction(
                id="connect_strava",
                severity="critical",
                title="Connect Strava",
                detail="Required for reliable ingestion and most analytics.",
                href="/settings",
            )
        )
    else:
        if ingestion and ingestion.remaining_activities > 0:
            actions.append(
                RecommendedAction(
                    id="finish_best_efforts",
                    severity="recommended",
                    title="Finish best-effort ingestion",
                    detail=f"{ingestion.remaining_activities} activities remaining ({ingestion.coverage_pct:.1f}% covered).",
                    href="/personal-bests",
                )
            )
        if ingestion and ingestion.last_task_status == "rate_limited":
            actions.append(
                RecommendedAction(
                    id="wait_rate_limit",
                    severity="optional",
                    title="Strava rate limit cooldown",
                    detail="Ingestion is throttled. Try again later; the system will self-recover.",
                    href="/personal-bests",
                )
            )

    if completeness.activities_with_hr < 10:
        actions.append(
            RecommendedAction(
                id="more_hr_runs",
                severity="recommended",
                title="Use heart rate for more runs",
                detail="Efficiency and load-response models need HR to be trustworthy.",
                href="/settings",
            )
        )

    if completeness.splits_with_gap == 0 and completeness.activities_total > 0:
        actions.append(
            RecommendedAction(
                id="backfill_splits",
                severity="recommended",
                title="Backfill splits (pace/GAP/cadence)",
                detail="Your splits are missing GAP, which weakens efficiency modeling.",
                href="/activities",
            )
        )

    if completeness.checkins_total < 7:
        actions.append(
            RecommendedAction(
                id="start_checkins",
                severity="optional",
                title="Start daily check-ins (10 seconds/day)",
                detail="Unlocks wellness → performance attribution (sleep/stress/soreness).",
                href="/checkin",
            )
        )

    actions.append(
        RecommendedAction(
            id="full_report",
            severity="optional",
            title="View full diagnostic report",
            detail="Deep narrative and detailed breakdown (long-form).",
            href="/diagnostic/report",
        )
    )

    # ---------------------------------------------------------------------
    # Overall status
    # ---------------------------------------------------------------------
    blocked = not strava_connected
    degraded = not (efficiency_trend_ready and personal_bests_ready)
    overall_status: Literal["ready", "degraded", "blocked"] = "blocked" if blocked else ("degraded" if degraded else "ready")

    return DiagnosticsSummaryResponse(
        generated_at=_utcnow_iso(),
        overall_status=overall_status,
        provider_health=provider_health,
        ingestion=ingestion,
        completeness=completeness,
        model_readiness=model_readiness,
        actions=actions,
    )

