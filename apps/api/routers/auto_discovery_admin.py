"""
AutoDiscovery Admin Router — Phase 1.

Provides founder-only visibility and control over AutoDiscovery live mutations.

Auth pattern (consistent with current hardening):
- Depends(get_current_user) + explicit _is_founder() check
- No subscription-tier middleware gate
- Malformed UUID params return 422 via FastAPI schema validation
"""

from __future__ import annotations

import os
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from models import Athlete
from services.auto_discovery.feature_flags import is_live_mutation_enabled

router = APIRouter(prefix="/v1/admin/auto-discovery", tags=["admin-auto-discovery"])


# ── Auth helper ─────────────────────────────────────────────────────────────

def _is_founder(current_user: Athlete) -> bool:
    owner_id = os.getenv("OWNER_ATHLETE_ID", "")
    return (
        str(current_user.id) == owner_id
        or getattr(current_user, "email", "") == "mbshaf@gmail.com"
    )


# ── Response models ─────────────────────────────────────────────────────────

class ChangeItem(BaseModel):
    change_id: str
    change_type: str
    change_key: str
    run_id: Optional[str]
    athlete_id: str
    created_at: str
    before_state: Optional[object]
    after_state: Optional[object]
    reverted: bool
    reverted_at: Optional[str]
    revert_reason: Optional[str]


class ChangesResponse(BaseModel):
    items: List[ChangeItem]
    total: int
    page: int
    page_size: int


class SummaryResponse(BaseModel):
    athlete_id: str
    last_run: Optional[object]
    changes_last_run: object
    pending_review: object
    coverage: object
    score_trends: object
    phase1_enabled: bool


class RevertResponse(BaseModel):
    change_id: str
    reverted: bool
    message: str


class CandidatesResponse(BaseModel):
    items: List[object]
    total: int


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/summary", response_model=SummaryResponse)
def get_autodiscovery_summary(
    athlete_id: UUID = Query(..., description="Athlete UUID"),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Founder-only: Return AutoDiscovery summary for the specified athlete.

    Includes last run info, overnight changes, pending items,
    coverage %, and score trends.
    """
    if not _is_founder(current_user):
        raise HTTPException(status_code=403, detail="Founder-only endpoint.")

    from models import AutoDiscoveryRun, AutoDiscoveryChangeLog, AutoDiscoveryScanCoverage

    # Last run
    last_run_row = (
        db.query(AutoDiscoveryRun)
        .filter(AutoDiscoveryRun.athlete_id == athlete_id)
        .order_by(AutoDiscoveryRun.started_at.desc())
        .first()
    )
    last_run = None
    if last_run_row:
        last_run = {
            "run_id": str(last_run_row.id),
            "started_at": last_run_row.started_at.isoformat() if last_run_row.started_at else None,
            "status": last_run_row.status,
            "experiment_count": last_run_row.experiment_count,
            "kept_count": last_run_row.kept_count,
        }

    # Changes in last run
    changes_last_run_q = db.query(AutoDiscoveryChangeLog).filter(
        AutoDiscoveryChangeLog.athlete_id == athlete_id,
        AutoDiscoveryChangeLog.reverted == False,  # noqa: E712
    )
    if last_run_row:
        changes_last_run_q = changes_last_run_q.filter(
            AutoDiscoveryChangeLog.run_id == last_run_row.id
        )
    changes_last_run = {"count": changes_last_run_q.count()}

    # Pending review — degrading findings and candidates approaching threshold
    from models import CorrelationFinding, AutoDiscoveryCandidate
    degrading_count = (
        db.query(CorrelationFinding)
        .filter(
            CorrelationFinding.athlete_id == athlete_id,
            CorrelationFinding.stability_class == "degrading",
            CorrelationFinding.is_active == True,  # noqa: E712
        )
        .count()
    )
    near_threshold_count = (
        db.query(AutoDiscoveryCandidate)
        .filter(
            AutoDiscoveryCandidate.athlete_id == athlete_id,
            AutoDiscoveryCandidate.times_seen >= 2,
            AutoDiscoveryCandidate.current_status == "open",
        )
        .count()
    )
    pending_review = {
        "degrading_findings": degrading_count,
        "candidates_near_promotion_threshold": near_threshold_count,
    }

    # Coverage
    total_scanned = (
        db.query(AutoDiscoveryScanCoverage)
        .filter(AutoDiscoveryScanCoverage.athlete_id == athlete_id)
        .count()
    )
    coverage = {
        "tests_scanned": total_scanned,
        "tests_with_signal": (
            db.query(AutoDiscoveryScanCoverage)
            .filter(
                AutoDiscoveryScanCoverage.athlete_id == athlete_id,
                AutoDiscoveryScanCoverage.result == "signal",
            )
            .count()
        ),
    }

    # Score trends (last 7 runs)
    recent_runs = (
        db.query(AutoDiscoveryRun)
        .filter(
            AutoDiscoveryRun.athlete_id == athlete_id,
            AutoDiscoveryRun.status.in_(["completed", "partial"]),
        )
        .order_by(AutoDiscoveryRun.started_at.desc())
        .limit(7)
        .all()
    )
    score_trends = {
        "runs": [
            {
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "kept_count": r.kept_count,
                "experiment_count": r.experiment_count,
            }
            for r in reversed(recent_runs)
        ]
    }

    return SummaryResponse(
        athlete_id=str(athlete_id),
        last_run=last_run,
        changes_last_run=changes_last_run,
        pending_review=pending_review,
        coverage=coverage,
        score_trends=score_trends,
        phase1_enabled=is_live_mutation_enabled(str(athlete_id), db),
    )


@router.get("/changes", response_model=ChangesResponse)
def get_autodiscovery_changes(
    athlete_id: UUID = Query(..., description="Athlete UUID"),
    change_type: Optional[str] = Query(None),
    reverted: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Founder-only: Paginated list of all changes AutoDiscovery has applied.

    Each item includes change_id for use with the revert endpoint.
    """
    if not _is_founder(current_user):
        raise HTTPException(status_code=403, detail="Founder-only endpoint.")

    from models import AutoDiscoveryChangeLog

    q = db.query(AutoDiscoveryChangeLog).filter(
        AutoDiscoveryChangeLog.athlete_id == athlete_id
    )
    if change_type:
        q = q.filter(AutoDiscoveryChangeLog.change_type == change_type)
    if reverted is not None:
        q = q.filter(AutoDiscoveryChangeLog.reverted == reverted)

    total = q.count()
    rows = q.order_by(AutoDiscoveryChangeLog.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    items = [
        ChangeItem(
            change_id=str(row.id),
            change_type=row.change_type,
            change_key=row.change_key,
            run_id=str(row.run_id) if row.run_id else None,
            athlete_id=str(row.athlete_id),
            created_at=row.created_at.isoformat() if row.created_at else "",
            before_state=row.before_state,
            after_state=row.after_state,
            reverted=row.reverted,
            reverted_at=row.reverted_at.isoformat() if row.reverted_at else None,
            revert_reason=row.revert_reason,
        )
        for row in rows
    ]

    return ChangesResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/revert/{change_id}", response_model=RevertResponse)
def revert_autodiscovery_change(
    change_id: UUID,
    reason: Optional[str] = Query(None, description="Optional revert reason"),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Founder-only: Revert a specific change made by AutoDiscovery.

    Supported change types:
    - new_correlation_finding → deactivates the finding
    - stability_annotation → clears stability fields
    - new_interaction_finding → deactivates the AthleteFinding
    - tuning_override_applied → reverts the AthleteInvestigationConfig

    Revert operations are auditable and never hard-delete evidence rows.
    """
    if not _is_founder(current_user):
        raise HTTPException(status_code=403, detail="Founder-only endpoint.")

    from models import (
        AutoDiscoveryChangeLog, CorrelationFinding, AthleteFinding,
        AthleteInvestigationConfig,
    )
    from datetime import datetime, timezone

    change = db.query(AutoDiscoveryChangeLog).filter(
        AutoDiscoveryChangeLog.id == change_id
    ).first()
    if not change:
        raise HTTPException(status_code=404, detail=f"Change {change_id} not found.")
    if change.reverted:
        raise HTTPException(
            status_code=409, detail=f"Change {change_id} is already reverted."
        )

    now = datetime.now(timezone.utc)
    revert_message = f"Reverted change type={change.change_type}"

    try:
        if change.change_type == "new_correlation_finding":
            after = change.after_state or {}
            finding = (
                db.query(CorrelationFinding)
                .filter(
                    CorrelationFinding.athlete_id == change.athlete_id,
                    CorrelationFinding.input_name == after.get("input_name"),
                    CorrelationFinding.output_metric == after.get("output_metric"),
                )
                .first()
            )
            if finding and finding.discovery_source == "auto_discovery":
                finding.is_active = False
                revert_message = f"Deactivated CorrelationFinding {finding.id}"

        elif change.change_type == "stability_annotation":
            # Clear stability fields for the athlete (batch — no single finding targeted)
            db.query(CorrelationFinding).filter(
                CorrelationFinding.athlete_id == change.athlete_id,
                CorrelationFinding.stability_checked_at != None,  # noqa: E711
            ).update({
                "stability_class": None,
                "windows_confirmed": None,
                "stability_checked_at": None,
            })
            revert_message = "Cleared stability annotations"

        elif change.change_type == "new_interaction_finding":
            after = change.after_state or {}
            finding = (
                db.query(AthleteFinding)
                .filter(
                    AthleteFinding.athlete_id == change.athlete_id,
                    AthleteFinding.investigation_name == after.get("finding_key"),
                    AthleteFinding.finding_type == "pairwise_interaction",
                )
                .first()
            )
            if finding:
                finding.is_active = False
                finding.superseded_at = now
                revert_message = f"Deactivated AthleteFinding {finding.id}"

        elif change.change_type == "tuning_override_applied":
            after = change.after_state or {}
            inv_name = after.get("investigation_name")
            config = (
                db.query(AthleteInvestigationConfig)
                .filter(
                    AthleteInvestigationConfig.athlete_id == change.athlete_id,
                    AthleteInvestigationConfig.investigation_name == inv_name,
                    AthleteInvestigationConfig.applied_change_log_id == change.id,
                    AthleteInvestigationConfig.reverted == False,  # noqa: E712
                )
                .first()
            )
            if config:
                config.reverted = True
                config.reverted_at = now
                config.reverted_by = str(current_user.id)
                config.revert_reason = reason or "founder_revert"
                revert_message = f"Reverted AthleteInvestigationConfig {config.id}"

        change.reverted = True
        change.reverted_at = now
        change.reverted_by = str(current_user.id)
        change.revert_reason = reason or "founder_revert"
        db.commit()

    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Revert failed: {exc}")

    return RevertResponse(
        change_id=str(change_id),
        reverted=True,
        message=revert_message,
    )


@router.get("/candidates", response_model=CandidatesResponse)
def get_autodiscovery_candidates(
    athlete_id: UUID = Query(..., description="Athlete UUID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Founder-only: Return AutoDiscovery candidates not yet auto-promoted.

    Wraps the existing get_founder_review_summary() plus DB pagination.
    """
    if not _is_founder(current_user):
        raise HTTPException(status_code=403, detail="Founder-only endpoint.")

    from models import AutoDiscoveryCandidate

    q = db.query(AutoDiscoveryCandidate).filter(
        AutoDiscoveryCandidate.athlete_id == athlete_id
    )
    if status:
        q = q.filter(AutoDiscoveryCandidate.current_status == status)

    total = q.count()
    rows = q.order_by(AutoDiscoveryCandidate.times_seen.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    items = [
        {
            "candidate_id": str(row.id),
            "candidate_type": row.candidate_type,
            "candidate_key": row.candidate_key,
            "times_seen": row.times_seen,
            "current_status": row.current_status,
            "latest_score": row.latest_score,
            "latest_score_delta": row.latest_score_delta,
            "latest_summary": row.latest_summary,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        }
        for row in rows
    ]

    return CandidatesResponse(items=items, total=total)
