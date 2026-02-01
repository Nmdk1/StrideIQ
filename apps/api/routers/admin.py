"""
Admin/Owners Dashboard API Router

Comprehensive command center for site management, monitoring, testing, and debugging.
Owner/admin role only.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Body, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_
from typing import List, Optional, Dict, Any, Literal
from uuid import UUID
from datetime import datetime, timedelta, date
from datetime import timezone

from core.database import get_db
from core.auth import require_admin, require_owner, require_permission, deny_impersonation_mutation
from models import (
    Athlete,
    Activity,
    ActivitySplit,
    NutritionEntry,
    WorkPattern,
    BodyComposition,
    ActivityFeedback,
    InsightFeedback,
    FeatureFlag,
    InviteAllowlist,
    InviteAuditEvent,
    IntakeQuestionnaire,
    AthleteIngestionState,
    AthleteDataImportJob,
    AthleteRaceResultAnchor,
    AthleteTrainingPaceProfile,
    TrainingPlan,
    PlannedWorkout,
    PlanModificationLog,
    CoachActionProposal,
    CoachChat,
    CoachIntentSnapshot,
    CoachUsage,
    CoachingRecommendation,
    Subscription,
    RacePromoCode,
    BestEffort,
    PersonalBest,
    CalendarInsight,
    CalendarNote,
    DailyCheckin,
    TrainingAvailability,
    AdminAuditEvent,
    WorkoutSelectionAuditEvent,
)
from schemas import AthleteResponse
from pydantic import BaseModel, Field
from services.plan_framework.feature_flags import FeatureFlagService
import logging
import io
import os

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin", tags=["admin"])

class FeatureFlagResponse(BaseModel):
    key: str
    name: str
    description: Optional[str] = None
    enabled: bool
    requires_subscription: bool
    requires_tier: Optional[str] = None
    requires_payment: Optional[float] = None
    rollout_percentage: int
    allowed_athlete_ids: List[str] = Field(default_factory=list)


class FeatureFlagUpdateRequest(BaseModel):
    enabled: Optional[bool] = None
    rollout_percentage: Optional[int] = Field(default=None, ge=0, le=100)
    allowed_athlete_ids: Optional[List[str]] = None


class ThreeDSelectionModeRequest(BaseModel):
    mode: Literal["off", "shadow", "on"]
    rollout_percentage: Optional[int] = Field(default=None, ge=0, le=100)
    # Admin-friendly: allow specifying emails rather than UUIDs.
    allowlist_emails: Optional[List[str]] = None
    allowlist_athlete_ids: Optional[List[str]] = None


class InviteCreateRequest(BaseModel):
    email: str
    note: Optional[str] = None
    grant_tier: Optional[Literal["free", "pro"]] = Field(
        default=None, 
        description="Subscription tier to grant on signup (e.g., 'pro' for beta testers)"
    )


class InviteRevokeRequest(BaseModel):
    email: str
    reason: Optional[str] = None


class CompAccessRequest(BaseModel):
    tier: Literal["free", "pro"] = Field(..., description="Subscription tier to set (free|pro)")
    reason: Optional[str] = Field(default=None, description="Why this comp was granted (audited)")


class TrialGrantRequest(BaseModel):
    days: int = Field(default=7, ge=1, le=30, description="Trial length in days (bounded)")
    reason: Optional[str] = Field(default=None, description="Why trial was granted (audited)")


class TrialRevokeRequest(BaseModel):
    reason: Optional[str] = Field(default=None, description="Why trial was revoked (audited)")


class ResetOnboardingRequest(BaseModel):
    reason: Optional[str] = Field(default=None, description="Why this reset was performed (audited)")
    stage: Optional[str] = Field(default="initial", description="Stage to reset to (default: initial)")


class ResetPasswordRequest(BaseModel):
    reason: Optional[str] = Field(default=None, description="Why password was reset (audited)")
    # Password is auto-generated and returned; admin shares with user


class RetryIngestionRequest(BaseModel):
    reason: Optional[str] = Field(default=None, description="Why this retry was performed (audited)")
    pages: int = Field(default=5, ge=1, le=50, description="Strava index backfill pages (bounded)")


class BlockUserRequest(BaseModel):
    blocked: bool = Field(..., description="Whether the user is blocked")
    reason: Optional[str] = Field(default=None, description="Why this block/unblock was performed (audited)")


class DeleteUserRequest(BaseModel):
    reason: Optional[str] = Field(default=None, description="Why this user is being deleted (audited)")
    confirm_email: str = Field(..., description="Must match the user's email to confirm deletion")


class ImpersonateUserRequest(BaseModel):
    reason: Optional[str] = Field(default=None, description="Why impersonation was started (audited)")
    ttl_minutes: Optional[int] = Field(default=None, ge=5, le=120, description="Override token TTL (bounded)")


class PauseIngestionRequest(BaseModel):
    paused: bool = Field(..., description="Whether global ingestion is paused")
    reason: Optional[str] = Field(default=None, description="Why ingestion was paused/unpaused (audited)")


class AdminPermissionsUpdateRequest(BaseModel):
    permissions: List[str] = Field(default_factory=list, description="Explicit admin permission keys")
    reason: Optional[str] = Field(default=None, description="Why permissions were changed (audited)")


class RegenerateStarterPlanRequest(BaseModel):
    reason: Optional[str] = Field(default=None, description="Why this plan regeneration was performed (audited)")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/ops/queue")
def get_ops_queue_snapshot(
    current_user: Athlete = Depends(require_admin),
):
    """
    Ops Visibility v0: best-effort queue snapshot.

    We intentionally avoid failing the admin page if Celery inspect is unavailable.
    """
    try:
        from tasks import celery_app

        insp = celery_app.control.inspect(timeout=1.0)
        active = insp.active() or {}
        reserved = insp.reserved() or {}
        scheduled = insp.scheduled() or {}

        def _count(d: dict) -> int:
            return sum(len(v or []) for v in (d or {}).values())

        return {
            "available": True,
            "active_count": _count(active),
            "reserved_count": _count(reserved),
            "scheduled_count": _count(scheduled),
            "workers_seen": sorted(list({*active.keys(), *reserved.keys(), *scheduled.keys()})),
        }
    except Exception as e:
        return {
            "available": False,
            "error": str(e),
            "active_count": 0,
            "reserved_count": 0,
            "scheduled_count": 0,
            "workers_seen": [],
        }


@router.get("/ops/coach-actions")
def get_ops_coach_actions_snapshot(
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
    hours: int = Query(24, ge=1, le=168, description="Lookback window (hours)"),
    top_errors: int = Query(5, ge=1, le=25, description="Top failed error reasons to return"),
):
    """
    Ops Pulse: Coach Action Automation lifecycle snapshot.

    Provides lightweight counts for propose/confirm/apply/failed states, and most common
    failure reasons in the lookback window.
    """
    since = _utcnow() - timedelta(hours=int(hours))

    total = db.query(func.count(CoachActionProposal.id)).scalar() or 0
    recent_total = (
        db.query(func.count(CoachActionProposal.id))
        .filter(CoachActionProposal.created_at >= since)
        .scalar()
        or 0
    )

    by_status_rows = (
        db.query(CoachActionProposal.status, func.count(CoachActionProposal.id))
        .filter(CoachActionProposal.created_at >= since)
        .group_by(CoachActionProposal.status)
        .all()
    )
    by_status = {str(s): int(c) for (s, c) in (by_status_rows or [])}

    failed_by_reason_rows = (
        db.query(CoachActionProposal.error, func.count(CoachActionProposal.id))
        .filter(
            CoachActionProposal.created_at >= since,
            CoachActionProposal.status == "failed",
            CoachActionProposal.error.isnot(None),
        )
        .group_by(CoachActionProposal.error)
        .order_by(desc(func.count(CoachActionProposal.id)))
        .limit(int(top_errors))
        .all()
    )
    failed_by_reason = [{"reason": str(r or ""), "count": int(c)} for (r, c) in (failed_by_reason_rows or [])]

    return {
        "window_hours": int(hours),
        "since": since.isoformat(),
        "total": int(total),
        "recent_total": int(recent_total),
        "recent_by_status": by_status,
        "recent_failed_top_reasons": failed_by_reason,
    }


@router.get("/ops/strava-capacity")
def get_ops_strava_capacity(
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Ops Pulse: Strava OAuth capacity visibility (best-effort).

    Strava enforces an "athlete capacity" per OAuth application (client_id).
    We cannot query Strava for the cap, but we can:
    - show how many athletes are currently linked in our DB
    - surface the configured safety threshold (STRAVA_MAX_CONNECTED_ATHLETES)
    """
    try:
        max_connected = int(getattr(settings, "STRAVA_MAX_CONNECTED_ATHLETES", None) or 0)
    except Exception:
        max_connected = 0

    connected_count = (
        db.query(func.count(Athlete.id))
        .filter(Athlete.strava_access_token.isnot(None))
        .scalar()
        or 0
    )

    return {
        "connected_athletes": int(connected_count),
        "max_connected_athletes_configured": int(max_connected) if max_connected > 0 else None,
        "capacity_guard_enabled": bool(max_connected > 0),
    }


@router.get("/ops/ingestion/pause")
def get_ingestion_pause_status(
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from services.system_flags import is_ingestion_paused

    return {"paused": bool(is_ingestion_paused(db))}


@router.post("/ops/ingestion/pause")
def set_ingestion_pause_status(
    request: PauseIngestionRequest,
    http_request: Request,
    _: None = Depends(deny_impersonation_mutation("system.ingestion.pause")),
    current_user: Athlete = Depends(require_permission("system.ingestion.pause")),
    db: Session = Depends(get_db),
):
    from services.system_flags import is_ingestion_paused, set_ingestion_paused
    from services.admin_audit import record_admin_audit_event

    before = {"paused": bool(is_ingestion_paused(db))}
    ok = set_ingestion_paused(db, paused=bool(request.paused))
    after = {"paused": bool(request.paused)}

    record_admin_audit_event(
        db,
        request=http_request,
        actor=current_user,
        action="system.ingestion.pause" if request.paused else "system.ingestion.resume",
        target_athlete_id=None,
        reason=request.reason,
        payload={"before": before, "after": after, "ok": bool(ok)},
    )
    db.commit()
    return {"success": True, "paused": bool(request.paused)}


@router.post("/users/{user_id}/permissions")
def set_admin_permissions(
    user_id: UUID,
    request: AdminPermissionsUpdateRequest,
    http_request: Request,
    _: None = Depends(deny_impersonation_mutation("admin.permissions.set")),
    current_user: Athlete = Depends(require_owner),
    db: Session = Depends(get_db),
):
    """
    Owner-only: set explicit admin permissions for a target user.

    This is the safety valve that makes the RBAC seam usable without DB access.
    """
    target = db.query(Athlete).filter(Athlete.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.role not in ("admin", "owner"):
        raise HTTPException(status_code=400, detail="Target user is not admin/owner")

    before = {"admin_permissions": list(getattr(target, "admin_permissions", []) or [])}
    # Normalize + de-dupe while preserving order.
    perms_in = [p.strip() for p in (request.permissions or []) if isinstance(p, str) and p.strip()]
    seen = set()
    perms = [p for p in perms_in if not (p in seen or seen.add(p))]
    target.admin_permissions = perms
    db.add(target)

    from services.admin_audit import record_admin_audit_event

    record_admin_audit_event(
        db,
        request=http_request,
        actor=current_user,
        action="admin.permissions.set",
        target_athlete_id=str(target.id),
        reason=request.reason,
        payload={"before": before, "after": {"admin_permissions": perms}},
    )
    db.commit()
    db.refresh(target)
    return {"success": True, "user_id": str(target.id), "admin_permissions": target.admin_permissions}


@router.get("/ops/ingestion/deferred")
def list_deferred_ingestion(
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
    limit: int = Query(200, ge=1, le=1000),
):
    """
    Ops Visibility v0+: list athletes with deferred ingestion (e.g. rate limit / paused).
    """
    now = _utcnow()
    rows = (
        db.query(AthleteIngestionState, Athlete)
        .join(Athlete, Athlete.id == AthleteIngestionState.athlete_id)
        .filter(
            AthleteIngestionState.provider == "strava",
            AthleteIngestionState.deferred_until.isnot(None),
            AthleteIngestionState.deferred_until > now,
        )
        .order_by(AthleteIngestionState.deferred_until.asc())
        .limit(limit)
        .all()
    )

    out: list[dict] = []
    for st, athlete in rows:
        out.append(
            {
                "athlete_id": str(athlete.id),
                "email": athlete.email,
                "display_name": athlete.display_name,
                "deferred_until": st.deferred_until.isoformat() if st.deferred_until else None,
                "deferred_reason": st.deferred_reason,
                "last_index_status": st.last_index_status,
                "last_best_efforts_status": st.last_best_efforts_status,
                "updated_at": st.updated_at.isoformat() if st.updated_at else None,
            }
        )

    return {"now": now.isoformat(), "count": len(out), "items": out}


@router.get("/ops/ingestion/stuck")
def list_stuck_ingestion(
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
    minutes: int = Query(30, ge=5, le=24 * 60, description="Consider a task stuck after this many minutes"),
    limit: int = Query(100, ge=1, le=500),
):
    """
    Ops Visibility v0: list athletes whose ingestion appears stuck.

    Heuristic:
    - last_index_status == 'running' and started_at older than threshold
    - last_best_efforts_status == 'running' and started_at older than threshold
    """
    cutoff = _utcnow() - timedelta(minutes=int(minutes))

    rows = (
        db.query(AthleteIngestionState, Athlete)
        .join(Athlete, Athlete.id == AthleteIngestionState.athlete_id)
        .filter(
            AthleteIngestionState.provider == "strava",
            or_(
                and_(AthleteIngestionState.last_index_status == "running", AthleteIngestionState.last_index_started_at.isnot(None), AthleteIngestionState.last_index_started_at < cutoff),
                and_(
                    AthleteIngestionState.last_best_efforts_status == "running",
                    AthleteIngestionState.last_best_efforts_started_at.isnot(None),
                    AthleteIngestionState.last_best_efforts_started_at < cutoff,
                ),
            ),
        )
        .order_by(AthleteIngestionState.updated_at.asc())
        .limit(limit)
        .all()
    )

    out: list[dict] = []
    for st, athlete in rows:
        # Prefer showing whichever process is the stuck one.
        kind = None
        started_at = None
        task_id = None
        if st.last_index_status == "running" and st.last_index_started_at and st.last_index_started_at < cutoff:
            kind = "index"
            started_at = st.last_index_started_at
            task_id = st.last_index_task_id
        elif st.last_best_efforts_status == "running" and st.last_best_efforts_started_at and st.last_best_efforts_started_at < cutoff:
            kind = "best_efforts"
            started_at = st.last_best_efforts_started_at
            task_id = st.last_best_efforts_task_id

        out.append(
            {
                "athlete_id": str(athlete.id),
                "email": athlete.email,
                "display_name": athlete.display_name,
                "kind": kind,
                "started_at": started_at.isoformat() if started_at else None,
                "task_id": task_id,
                "updated_at": st.updated_at.isoformat() if st.updated_at else None,
                "last_index_status": st.last_index_status,
                "last_index_error": st.last_index_error,
                "last_best_efforts_status": st.last_best_efforts_status,
                "last_best_efforts_error": st.last_best_efforts_error,
            }
        )

    return {"cutoff": cutoff.isoformat(), "count": len(out), "items": out}


@router.get("/ops/ingestion/errors")
def list_recent_ingestion_errors(
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(200, ge=1, le=1000),
):
    """
    Ops Visibility v0: recent ingestion errors (index or best-efforts).
    """
    cutoff = _utcnow() - timedelta(days=int(days))

    rows = (
        db.query(AthleteIngestionState, Athlete)
        .join(Athlete, Athlete.id == AthleteIngestionState.athlete_id)
        .filter(
            AthleteIngestionState.provider == "strava",
            AthleteIngestionState.updated_at.isnot(None),
            AthleteIngestionState.updated_at >= cutoff,
            or_(
                AthleteIngestionState.last_index_error.isnot(None),
                AthleteIngestionState.last_best_efforts_error.isnot(None),
            ),
        )
        .order_by(AthleteIngestionState.updated_at.desc())
        .limit(limit)
        .all()
    )

    out: list[dict] = []
    for st, athlete in rows:
        out.append(
            {
                "athlete_id": str(athlete.id),
                "email": athlete.email,
                "display_name": athlete.display_name,
                "updated_at": st.updated_at.isoformat() if st.updated_at else None,
                "last_index_status": st.last_index_status,
                "last_index_error": st.last_index_error,
                "last_best_efforts_status": st.last_best_efforts_status,
                "last_best_efforts_error": st.last_best_efforts_error,
            }
        )

    return {"cutoff": cutoff.isoformat(), "count": len(out), "items": out}


def _ensure_flag_exists(db: Session, key: str, name: str, description: str) -> None:
    existing = db.query(FeatureFlag).filter(FeatureFlag.key == key).first()
    if existing:
        return
    svc = FeatureFlagService(db)
    svc.create_flag(
        key=key,
        name=name,
        description=description,
        enabled=False,
        requires_subscription=False,
        requires_tier="elite",
        requires_payment=None,
        rollout_percentage=0,
    )


@router.get("/feature-flags")
def list_feature_flags(
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
    prefix: Optional[str] = Query(None, description="Optional key prefix filter (e.g., 'plan.')"),
):
    """
    List feature flags.
    Admin/owner only.
    """
    q = db.query(FeatureFlag)
    if prefix:
        q = q.filter(FeatureFlag.key.ilike(f"{prefix}%"))
    flags = q.order_by(FeatureFlag.key.asc()).all()

    return {
        "flags": [
            FeatureFlagResponse(
                key=f.key,
                name=f.name,
                description=f.description,
                enabled=bool(f.enabled),
                requires_subscription=bool(f.requires_subscription),
                requires_tier=f.requires_tier,
                requires_payment=float(f.requires_payment) if f.requires_payment is not None else None,
                rollout_percentage=int(f.rollout_percentage or 0),
                allowed_athlete_ids=[str(x) for x in (f.allowed_athlete_ids or [])],
            ).model_dump()
            for f in flags
        ]
    }


@router.get("/invites")
def list_invites(
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
    active_only: bool = Query(False),
    limit: int = Query(200, ge=1, le=1000),
):
    """
    List invite allowlist entries.
    Admin/owner only.
    """
    q = db.query(InviteAllowlist)
    if active_only:
        q = q.filter(InviteAllowlist.is_active.is_(True), InviteAllowlist.used_at.is_(None))
    rows = q.order_by(InviteAllowlist.created_at.desc()).limit(limit).all()
    return {
        "invites": [
            {
                "id": str(r.id),
                "email": r.email,
                "is_active": bool(r.is_active),
                "note": r.note,
                "grant_tier": r.grant_tier,
                "invited_at": r.invited_at.isoformat() if r.invited_at else None,
                "revoked_at": r.revoked_at.isoformat() if r.revoked_at else None,
                "used_at": r.used_at.isoformat() if r.used_at else None,
                "invited_by_athlete_id": str(r.invited_by_athlete_id) if r.invited_by_athlete_id else None,
                "revoked_by_athlete_id": str(r.revoked_by_athlete_id) if r.revoked_by_athlete_id else None,
                "used_by_athlete_id": str(r.used_by_athlete_id) if r.used_by_athlete_id else None,
            }
            for r in rows
        ]
    }


@router.post("/invites")
def create_invite_endpoint(
    request: InviteCreateRequest,
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Create or re-activate an invite allowlist entry.
    Admin/owner only.
    
    Use grant_tier="pro" to give beta testers automatic pro access on signup.
    """
    from services.invite_service import create_invite

    inv = create_invite(
        db, 
        email=request.email, 
        invited_by_athlete_id=current_user.id, 
        note=request.note,
        grant_tier=request.grant_tier,
    )
    db.commit()
    db.refresh(inv)
    return {
        "success": True, 
        "invite": {
            "id": str(inv.id), 
            "email": inv.email, 
            "is_active": inv.is_active, 
            "used_at": inv.used_at,
            "grant_tier": inv.grant_tier,
        }
    }


@router.post("/invites/revoke")
def revoke_invite_endpoint(
    request: InviteRevokeRequest,
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Revoke an invite allowlist entry.
    Admin/owner only.
    """
    from services.invite_service import revoke_invite

    inv = revoke_invite(db, email=request.email, revoked_by_athlete_id=current_user.id, reason=request.reason)
    if not inv:
        raise HTTPException(status_code=404, detail="Invite not found")
    db.commit()
    db.refresh(inv)
    return {
        "success": True, 
        "invite": {
            "id": str(inv.id), 
            "email": inv.email, 
            "is_active": inv.is_active,
            "revoked_at": inv.revoked_at.isoformat() if inv.revoked_at else None,
        }
    }


@router.patch("/feature-flags/{flag_key}")
def update_feature_flag(
    flag_key: str,
    request: FeatureFlagUpdateRequest,
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Update a feature flag.
    Admin/owner only.
    """
    flag = db.query(FeatureFlag).filter(FeatureFlag.key == flag_key).first()
    if not flag:
        raise HTTPException(status_code=404, detail="Feature flag not found")

    updates: Dict[str, Any] = {}
    if request.enabled is not None:
        updates["enabled"] = request.enabled
    if request.rollout_percentage is not None:
        updates["rollout_percentage"] = request.rollout_percentage
    if request.allowed_athlete_ids is not None:
        updates["allowed_athlete_ids"] = request.allowed_athlete_ids

    if not updates:
        return {"success": True, "message": "No updates", "flag_key": flag_key}

    svc = FeatureFlagService(db)
    ok = svc.set_flag(flag_key, updates)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update feature flag")

    updated = db.query(FeatureFlag).filter(FeatureFlag.key == flag_key).first()
    return {
        "success": True,
        "flag": FeatureFlagResponse(
            key=updated.key,
            name=updated.name,
            description=updated.description,
            enabled=bool(updated.enabled),
            requires_subscription=bool(updated.requires_subscription),
            requires_tier=updated.requires_tier,
            requires_payment=float(updated.requires_payment) if updated.requires_payment is not None else None,
            rollout_percentage=int(updated.rollout_percentage or 0),
            allowed_athlete_ids=[str(x) for x in (updated.allowed_athlete_ids or [])],
        ).model_dump(),
    }


@router.post("/features/3d-quality-selection")
def set_3d_quality_selection_mode(
    request: ThreeDSelectionModeRequest,
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Admin-friendly control for ADR-036 3D quality-session selection.

    This endpoint sets BOTH flags in a coherent way so admins don't have to
    think about the underlying implementation details.
    """
    # Ensure flags exist (idempotent safety for environments that didn't run all migrations).
    _ensure_flag_exists(
        db,
        key="plan.3d_workout_selection",
        name="3D Workout Selection (ON)",
        description="ADR-036: Serve 3D workout template selection for quality sessions (phase × progression × variance + N=1 weighting).",
    )
    _ensure_flag_exists(
        db,
        key="plan.3d_workout_selection_shadow",
        name="3D Workout Selection (SHADOW)",
        description="ADR-036: Compute 3D selection and log diffs, but continue serving legacy quality sessions.",
    )

    allowlist_ids: List[str] = []
    if request.allowlist_athlete_ids:
        allowlist_ids.extend([str(x) for x in request.allowlist_athlete_ids])

    if request.allowlist_emails:
        emails = [e.strip().lower() for e in request.allowlist_emails if e and e.strip()]
        if emails:
            athletes = db.query(Athlete).filter(func.lower(Athlete.email).in_(emails)).all()
            allowlist_ids.extend([str(a.id) for a in athletes])

    # De-dupe while preserving order.
    seen = set()
    allowlist_ids = [x for x in allowlist_ids if not (x in seen or seen.add(x))]

    rollout = request.rollout_percentage

    svc = FeatureFlagService(db)

    if request.mode == "off":
        svc.set_flag("plan.3d_workout_selection", {"enabled": False, "rollout_percentage": 0, "allowed_athlete_ids": []})
        svc.set_flag("plan.3d_workout_selection_shadow", {"enabled": False, "rollout_percentage": 0, "allowed_athlete_ids": []})
    elif request.mode == "shadow":
        svc.set_flag("plan.3d_workout_selection", {"enabled": False, "rollout_percentage": 0, "allowed_athlete_ids": []})
        payload: Dict[str, Any] = {"enabled": True}
        if rollout is not None:
            payload["rollout_percentage"] = rollout
        if allowlist_ids:
            payload["allowed_athlete_ids"] = allowlist_ids
        svc.set_flag("plan.3d_workout_selection_shadow", payload)
    else:  # "on"
        svc.set_flag("plan.3d_workout_selection_shadow", {"enabled": False, "rollout_percentage": 0, "allowed_athlete_ids": []})
        payload = {"enabled": True}
        if rollout is not None:
            payload["rollout_percentage"] = rollout
        if allowlist_ids:
            payload["allowed_athlete_ids"] = allowlist_ids
        svc.set_flag("plan.3d_workout_selection", payload)

    return {
        "success": True,
        "mode": request.mode,
        "rollout_percentage": rollout,
        "allowlist_athlete_ids": allowlist_ids,
    }


@router.get("/users")
def list_users(
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
    search: Optional[str] = Query(None, description="Search by email or display name"),
    role: Optional[str] = Query(None, description="Filter by role"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    List all users with filtering and pagination.
    Admin/owner only.
    """
    query = db.query(Athlete)
    
    if search:
        query = query.filter(
            or_(
                Athlete.email.ilike(f"%{search}%"),
                Athlete.display_name.ilike(f"%{search}%")
            )
        )
    
    if role:
        query = query.filter(Athlete.role == role)
    
    total = query.count()
    users = query.order_by(Athlete.created_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "total": total,
        "users": [
            {
                "id": str(user.id),
                "email": user.email,
                "display_name": user.display_name,
                "role": user.role,
                "subscription_tier": user.subscription_tier,
                "created_at": user.created_at.isoformat(),
                "onboarding_completed": user.onboarding_completed,
            }
            for user in users
        ],
        "offset": offset,
        "limit": limit,
    }


@router.get("/users/{user_id}")
def get_user(
    user_id: UUID,
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Get detailed user information.
    Admin/owner only.
    """
    user = db.query(Athlete).filter(Athlete.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get activity count
    activity_count = db.query(Activity).filter(Activity.athlete_id == user_id).count()
    
    # Get data collection stats
    nutrition_count = db.query(NutritionEntry).filter(NutritionEntry.athlete_id == user_id).count()
    work_pattern_count = db.query(WorkPattern).filter(WorkPattern.athlete_id == user_id).count()
    body_comp_count = db.query(BodyComposition).filter(BodyComposition.athlete_id == user_id).count()
    
    # Integration / ingestion state (best-effort; may be missing).
    ingestion = (
        db.query(AthleteIngestionState)
        .filter(AthleteIngestionState.athlete_id == user_id, AthleteIngestionState.provider == "strava")
        .first()
    )

    # Intake interview history (append-only-ish: one row per stage; we return latest first).
    intake_rows = (
        db.query(IntakeQuestionnaire)
        .filter(IntakeQuestionnaire.athlete_id == user_id)
        .order_by(IntakeQuestionnaire.created_at.desc())
        .all()
    )

    # Active plan (if any).
    active_plan = (
        db.query(TrainingPlan)
        .filter(TrainingPlan.athlete_id == user_id, TrainingPlan.status == "active")
        .order_by(TrainingPlan.created_at.desc())
        .first()
    )

    # Stripe subscription mirror (best-effort; may be missing).
    sub = db.query(Subscription).filter(Subscription.athlete_id == user_id).first()

    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "subscription_tier": user.subscription_tier,
        "stripe_customer_id": getattr(user, "stripe_customer_id", None),
        "trial_started_at": user.trial_started_at.isoformat() if getattr(user, "trial_started_at", None) else None,
        "trial_ends_at": user.trial_ends_at.isoformat() if getattr(user, "trial_ends_at", None) else None,
        "trial_source": getattr(user, "trial_source", None),
        "has_active_subscription": bool(getattr(user, "has_active_subscription", False)),
        "subscription": None
        if not sub
        else {
            "status": sub.status,
            "cancel_at_period_end": bool(sub.cancel_at_period_end),
            "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
            "stripe_subscription_id": sub.stripe_subscription_id,
            "stripe_price_id": sub.stripe_price_id,
        },
        "is_blocked": bool(getattr(user, "is_blocked", False)),
        "is_coach_vip": bool(getattr(user, "is_coach_vip", False)),
        "created_at": user.created_at.isoformat(),
        "onboarding_completed": user.onboarding_completed,
        "onboarding_stage": user.onboarding_stage,
        "integrations": {
            "preferred_units": getattr(user, "preferred_units", None),
            "strava_athlete_id": user.strava_athlete_id,
            "last_strava_sync": user.last_strava_sync.isoformat() if user.last_strava_sync else None,
            "garmin_connected": getattr(user, "garmin_connected", False),
            "last_garmin_sync": user.last_garmin_sync.isoformat() if getattr(user, "last_garmin_sync", None) else None,
        },
        "ingestion_state": None
        if not ingestion
        else {
            "provider": ingestion.provider,
            "updated_at": ingestion.updated_at.isoformat() if ingestion.updated_at else None,
            "last_index_status": ingestion.last_index_status,
            "last_index_error": ingestion.last_index_error,
            "last_index_started_at": ingestion.last_index_started_at.isoformat() if ingestion.last_index_started_at else None,
            "last_index_finished_at": ingestion.last_index_finished_at.isoformat() if ingestion.last_index_finished_at else None,
            "last_best_efforts_status": ingestion.last_best_efforts_status,
            "last_best_efforts_error": ingestion.last_best_efforts_error,
            "last_best_efforts_started_at": ingestion.last_best_efforts_started_at.isoformat()
            if ingestion.last_best_efforts_started_at
            else None,
            "last_best_efforts_finished_at": ingestion.last_best_efforts_finished_at.isoformat()
            if ingestion.last_best_efforts_finished_at
            else None,
        },
        "intake_history": [
            {
                "id": str(r.id),
                "stage": r.stage,
                "responses": r.responses,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in intake_rows
        ],
        "active_plan": None
        if not active_plan
        else {
            "id": str(active_plan.id),
            "name": active_plan.name,
            "status": active_plan.status,
            "plan_type": active_plan.plan_type,
            "plan_start_date": active_plan.plan_start_date.isoformat() if active_plan.plan_start_date else None,
            "plan_end_date": active_plan.plan_end_date.isoformat() if active_plan.plan_end_date else None,
            "goal_race_name": active_plan.goal_race_name,
            "goal_race_date": active_plan.goal_race_date.isoformat() if active_plan.goal_race_date else None,
        },
        "stats": {
            "activities": activity_count,
            "nutrition_entries": nutrition_count,
            "work_patterns": work_pattern_count,
            "body_composition_entries": body_comp_count,
        },
    }


@router.post("/users/{user_id}/trial/grant")
def grant_trial(
    user_id: UUID,
    request: TrialGrantRequest,
    http_request: Request,
    _: None = Depends(deny_impersonation_mutation("billing.trial.grant")),
    current_user: Athlete = Depends(require_permission("billing.trial.grant")),
    db: Session = Depends(get_db),
):
    """
    Admin action: grant/extend a user's trial (audited).
    """
    target = db.query(Athlete).filter(Athlete.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    from services.admin_audit import record_admin_audit_event

    before = {
        "trial_started_at": target.trial_started_at.isoformat() if getattr(target, "trial_started_at", None) else None,
        "trial_ends_at": target.trial_ends_at.isoformat() if getattr(target, "trial_ends_at", None) else None,
        "trial_source": getattr(target, "trial_source", None),
    }

    now = _utcnow()
    if getattr(target, "trial_started_at", None) is None:
        target.trial_started_at = now
    target.trial_ends_at = now + timedelta(days=int(request.days))
    target.trial_source = "admin_grant"
    db.add(target)

    record_admin_audit_event(
        db,
        request=http_request,
        actor=current_user,
        action="billing.trial.grant",
        target_athlete_id=str(target.id),
        reason=request.reason,
        payload={"before": before, "after": {"trial_started_at": target.trial_started_at.isoformat() if target.trial_started_at else None, "trial_ends_at": target.trial_ends_at.isoformat() if target.trial_ends_at else None, "trial_source": target.trial_source}, "days": int(request.days)},
    )

    db.commit()
    db.refresh(target)
    return {"success": True, "user_id": str(target.id), "trial_ends_at": target.trial_ends_at.isoformat() if target.trial_ends_at else None}


@router.post("/users/{user_id}/trial/revoke")
def revoke_trial(
    user_id: UUID,
    request: TrialRevokeRequest,
    http_request: Request,
    _: None = Depends(deny_impersonation_mutation("billing.trial.revoke")),
    current_user: Athlete = Depends(require_permission("billing.trial.revoke")),
    db: Session = Depends(get_db),
):
    """
    Admin action: revoke a user's trial immediately (audited).
    """
    target = db.query(Athlete).filter(Athlete.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    from services.admin_audit import record_admin_audit_event

    before = {
        "trial_started_at": target.trial_started_at.isoformat() if getattr(target, "trial_started_at", None) else None,
        "trial_ends_at": target.trial_ends_at.isoformat() if getattr(target, "trial_ends_at", None) else None,
        "trial_source": getattr(target, "trial_source", None),
    }

    now = _utcnow()
    target.trial_ends_at = now
    if not getattr(target, "trial_source", None):
        target.trial_source = "admin_grant"
    db.add(target)

    record_admin_audit_event(
        db,
        request=http_request,
        actor=current_user,
        action="billing.trial.revoke",
        target_athlete_id=str(target.id),
        reason=request.reason,
        payload={"before": before, "after": {"trial_ends_at": target.trial_ends_at.isoformat() if target.trial_ends_at else None}},
    )

    db.commit()
    db.refresh(target)
    return {"success": True, "user_id": str(target.id), "trial_ends_at": target.trial_ends_at.isoformat() if target.trial_ends_at else None}


@router.post("/users/{user_id}/comp")
def comp_access(
    user_id: UUID,
    request: CompAccessRequest,
    http_request: Request,
    _: None = Depends(deny_impersonation_mutation("billing.comp")),
    current_user: Athlete = Depends(require_permission("billing.comp")),
    db: Session = Depends(get_db),
):
    """
    Manually grant (or change) a user's subscription tier.

    Pre-Phase-6: DB is the source of truth for entitlements.
    This endpoint is the MVP of billing control and is fully auditable.
    """
    target = db.query(Athlete).filter(Athlete.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    old_tier = target.subscription_tier
    target.subscription_tier = request.tier
    db.add(target)

    from services.admin_audit import record_admin_audit_event

    record_admin_audit_event(
        db,
        request=http_request,
        actor=current_user,
        action="billing.comp",
        target_athlete_id=str(target.id),
        reason=request.reason,
        payload={"before": {"subscription_tier": old_tier}, "after": {"subscription_tier": target.subscription_tier}},
    )

    db.commit()
    db.refresh(target)

    return {
        "success": True,
        "user": {
            "id": str(target.id),
            "email": target.email,
            "subscription_tier": target.subscription_tier,
        },
    }


class SetCoachVIPRequest(BaseModel):
    """Request to set/unset Coach VIP status for an athlete."""
    is_vip: bool
    reason: Optional[str] = None


@router.post("/users/{user_id}/coach-vip")
def set_coach_vip(
    user_id: UUID,
    request: SetCoachVIPRequest,
    http_request: Request,
    _: None = Depends(deny_impersonation_mutation("coach_vip.set")),
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Set or unset Coach VIP status for an athlete.
    
    VIP athletes get the premium model (gpt-5.2) for high-complexity queries.
    See ADR-060 for tiering rationale.
    
    Admin/owner only.
    """
    target = db.query(Athlete).filter(Athlete.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    old_vip = bool(getattr(target, "is_coach_vip", False))
    target.is_coach_vip = request.is_vip
    db.add(target)

    from services.admin_audit import record_admin_audit_event

    record_admin_audit_event(
        db,
        request=http_request,
        actor=current_user,
        action="coach_vip.set",
        target_athlete_id=str(target.id),
        reason=request.reason,
        payload={"before": {"is_coach_vip": old_vip}, "after": {"is_coach_vip": request.is_vip}},
    )

    db.commit()
    db.refresh(target)

    return {
        "success": True,
        "user": {
            "id": str(target.id),
            "email": target.email,
            "is_coach_vip": target.is_coach_vip,
        },
    }


@router.post("/users/{user_id}/onboarding/reset")
def reset_onboarding(
    user_id: UUID,
    request: ResetOnboardingRequest,
    http_request: Request,
    _: None = Depends(deny_impersonation_mutation("onboarding.reset")),
    current_user: Athlete = Depends(require_permission("onboarding.reset")),
    db: Session = Depends(get_db),
):
    """
    Reset a user's onboarding state (soft reset).

    Policy:
    - Does not delete intake history by default (we want evidence + context).
    - Only resets the onboarding stage/completion flags.
    """
    target = db.query(Athlete).filter(Athlete.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    before = {"onboarding_stage": target.onboarding_stage, "onboarding_completed": bool(target.onboarding_completed)}
    target.onboarding_stage = request.stage or "initial"
    target.onboarding_completed = False
    db.add(target)

    from services.admin_audit import record_admin_audit_event

    record_admin_audit_event(
        db,
        request=http_request,
        actor=current_user,
        action="onboarding.reset",
        target_athlete_id=str(target.id),
        reason=request.reason,
        payload={"before": before, "after": {"onboarding_stage": target.onboarding_stage, "onboarding_completed": False}},
    )

    db.commit()
    db.refresh(target)
    return {"success": True, "user_id": str(target.id), "onboarding_stage": target.onboarding_stage, "onboarding_completed": target.onboarding_completed}


@router.post("/users/{user_id}/password/reset")
def reset_password(
    user_id: UUID,
    request: ResetPasswordRequest,
    http_request: Request,
    _: None = Depends(deny_impersonation_mutation("password.reset")),
    current_user: Athlete = Depends(require_permission("password.reset")),
    db: Session = Depends(get_db),
):
    """
    Reset a user's password (admin action).

    Generates a secure temporary password and returns it to the admin.
    The admin must communicate this password to the user out-of-band.
    User should change password after first login.

    Security:
    - Requires explicit permission
    - Blocked under impersonation
    - Fully audited (but password NOT logged)
    """
    import secrets

    target = db.query(Athlete).filter(Athlete.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Generate a secure temporary password (12 chars, URL-safe)
    temp_password = secrets.token_urlsafe(9)  # 12 base64 chars

    # Hash and store
    from core.security import get_password_hash

    target.password_hash = get_password_hash(temp_password)
    db.add(target)

    from services.admin_audit import record_admin_audit_event

    record_admin_audit_event(
        db,
        request=http_request,
        actor=current_user,
        action="password.reset",
        target_athlete_id=str(target.id),
        reason=request.reason,
        payload={"email": target.email},  # DO NOT log the password
    )

    db.commit()

    logger.info(f"Password reset for athlete {target.id} by admin {current_user.id}")

    return {
        "success": True,
        "user_id": str(target.id),
        "email": target.email,
        "temporary_password": temp_password,
        "message": "Share this password with the user. They should change it after first login.",
    }


@router.post("/users/{user_id}/ingestion/retry")
def retry_ingestion(
    user_id: UUID,
    request: RetryIngestionRequest,
    http_request: Request,
    _: None = Depends(deny_impersonation_mutation("ingestion.retry")),
    current_user: Athlete = Depends(require_permission("ingestion.retry")),
    db: Session = Depends(get_db),
):
    """
    Retry ingestion for a user (Phase 4 operator action).

    Mirrors Phase 3 bootstrap behavior (cheap index backfill + full sync),
    but targets an arbitrary athlete and is auditable.
    """
    target = db.query(Athlete).filter(Athlete.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if not target.strava_access_token:
        raise HTTPException(status_code=400, detail="Strava not connected")

    from services.system_flags import is_ingestion_paused

    if is_ingestion_paused(db):
        from services.admin_audit import record_admin_audit_event

        record_admin_audit_event(
            db,
            request=http_request,
            actor=current_user,
            action="ingestion.retry.blocked_by_pause",
            target_athlete_id=str(target.id),
            reason=request.reason,
            payload={"paused": True},
        )
        db.commit()
        raise HTTPException(status_code=409, detail="Ingestion paused by system")

    from tasks.strava_tasks import backfill_strava_activity_index_task, sync_strava_activities_task

    index_task = backfill_strava_activity_index_task.delay(str(target.id), pages=int(request.pages))
    sync_task = sync_strava_activities_task.delay(str(target.id))

    from services.admin_audit import record_admin_audit_event

    record_admin_audit_event(
        db,
        request=http_request,
        actor=current_user,
        action="ingestion.retry",
        target_athlete_id=str(target.id),
        reason=request.reason,
        payload={"provider": "strava", "pages": int(request.pages), "index_task_id": index_task.id, "sync_task_id": sync_task.id},
    )

    db.commit()
    return {"success": True, "queued": True, "index_task_id": index_task.id, "sync_task_id": sync_task.id}


@router.post("/users/{user_id}/plans/starter/regenerate")
def regenerate_starter_plan(
    user_id: UUID,
    request: RegenerateStarterPlanRequest,
    http_request: Request,
    _: None = Depends(deny_impersonation_mutation("plan.starter.regenerate")),
    current_user: Athlete = Depends(require_permission("plan.starter.regenerate")),
    db: Session = Depends(get_db),
):
    """
    Beta support action: archive the user's current active plan (if any) and regenerate a new
    starter plan from their saved intake (goals) + race anchor (if present).

    This is intentionally deterministic and fully auditable.
    """
    target = db.query(Athlete).filter(Athlete.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Ensure goals intake exists (otherwise regen would silently do nothing).
    has_goals = (
        db.query(IntakeQuestionnaire)
        .filter(IntakeQuestionnaire.athlete_id == target.id, IntakeQuestionnaire.stage == "goals")
        .count()
        > 0
    )
    if not has_goals:
        raise HTTPException(status_code=409, detail="Cannot regenerate starter plan: missing goals intake")

    existing = (
        db.query(TrainingPlan)
        .filter(TrainingPlan.athlete_id == target.id, TrainingPlan.status == "active")
        .all()
    )
    before = {"active_plan_ids": [str(p.id) for p in existing], "active_plan_generation_methods": [p.generation_method for p in existing]}

    today = date.today()
    archived_ids: List[str] = []
    for p in existing:
        p.status = "archived"
        archived_ids.append(str(p.id))

        # Mark future planned workouts as skipped so the calendar doesn't show two competing plans.
        db.query(PlannedWorkout).filter(
            PlannedWorkout.plan_id == p.id,
            PlannedWorkout.scheduled_date >= today,
            PlannedWorkout.completed == False,
        ).update({"skipped": True})

    db.commit()

    # Create new starter plan from intake (best-effort deterministic).
    from services.starter_plan import ensure_starter_plan
    from services.admin_audit import record_admin_audit_event

    created = ensure_starter_plan(db, athlete=target)
    if not created:
        record_admin_audit_event(
            db,
            request=http_request,
            actor=current_user,
            action="plan.starter.regenerate.failed",
            target_athlete_id=str(target.id),
            reason=request.reason,
            payload={"before": before, "after": {"archived_plan_ids": archived_ids}, "error": "ensure_starter_plan returned None"},
        )
        db.commit()
        raise HTTPException(status_code=500, detail="Failed to regenerate starter plan")

    after = {
        "archived_plan_ids": archived_ids,
        "new_plan_id": str(created.id),
        "new_generation_method": getattr(created, "generation_method", None),
    }

    record_admin_audit_event(
        db,
        request=http_request,
        actor=current_user,
        action="plan.starter.regenerate",
        target_athlete_id=str(target.id),
        reason=request.reason,
        payload={"before": before, "after": after},
    )
    db.commit()
    return {"success": True, **after}


@router.post("/users/{user_id}/block")
def set_blocked(
    user_id: UUID,
    request: BlockUserRequest,
    http_request: Request,
    _: None = Depends(deny_impersonation_mutation("athlete.block")),
    current_user: Athlete = Depends(require_permission("athlete.block")),
    db: Session = Depends(get_db),
):
    """
    Block/unblock a user from accessing authenticated endpoints.
    """
    target = db.query(Athlete).filter(Athlete.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    before = {"is_blocked": bool(getattr(target, "is_blocked", False))}
    target.is_blocked = bool(request.blocked)
    db.add(target)

    from services.admin_audit import record_admin_audit_event

    record_admin_audit_event(
        db,
        request=http_request,
        actor=current_user,
        action="athlete.block" if request.blocked else "athlete.unblock",
        target_athlete_id=str(target.id),
        reason=request.reason,
        payload={"before": before, "after": {"is_blocked": bool(target.is_blocked)}},
    )

    db.commit()
    db.refresh(target)
    return {"success": True, "user_id": str(target.id), "is_blocked": bool(target.is_blocked)}


@router.delete("/users/{user_id}")
def delete_user(
    user_id: UUID,
    request: DeleteUserRequest,
    http_request: Request,
    _: None = Depends(deny_impersonation_mutation("athlete.delete")),
    current_user: Athlete = Depends(require_owner),
    db: Session = Depends(get_db),
):
    """
    Permanently delete a user and all their data.
    
    Owner only. Requires email confirmation to prevent accidental deletion.
    This action is irreversible and fully audited.
    
    The deletion cascades through all FK relationships in the correct order.
    """
    target = db.query(Athlete).filter(Athlete.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Safety: require email confirmation
    if request.confirm_email.lower().strip() != target.email.lower().strip():
        raise HTTPException(
            status_code=400, 
            detail="Email confirmation does not match. Provide the user's email to confirm deletion."
        )
    
    # Cannot delete yourself
    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    # Cannot delete other owners
    if target.role == "owner":
        raise HTTPException(status_code=400, detail="Cannot delete owner accounts")
    
    # Capture info for audit before deletion
    deleted_user_info = {
        "id": str(target.id),
        "email": target.email,
        "display_name": target.display_name,
        "role": target.role,
        "created_at": target.created_at.isoformat() if target.created_at else None,
    }
    
    # Delete in FK-dependency order (deepest children first)
    # Level 1: Deepest children (FK to planned_workout and training_plan)
    db.query(PlanModificationLog).filter(
        PlanModificationLog.workout_id.in_(
            db.query(PlannedWorkout.id).filter(PlannedWorkout.athlete_id == user_id)
        )
    ).delete(synchronize_session=False)
    db.query(PlanModificationLog).filter(
        PlanModificationLog.plan_id.in_(
            db.query(TrainingPlan.id).filter(TrainingPlan.athlete_id == user_id)
        )
    ).delete(synchronize_session=False)
    db.query(CoachActionProposal).filter(
        CoachActionProposal.target_plan_id.in_(
            db.query(TrainingPlan.id).filter(TrainingPlan.athlete_id == user_id)
        )
    ).delete(synchronize_session=False)
    db.query(CoachChat).filter(
        CoachChat.context_plan_id.in_(
            db.query(TrainingPlan.id).filter(TrainingPlan.athlete_id == user_id)
        )
    ).delete(synchronize_session=False)
    db.query(WorkoutSelectionAuditEvent).filter(
        WorkoutSelectionAuditEvent.plan_id.in_(
            db.query(TrainingPlan.id).filter(TrainingPlan.athlete_id == user_id)
        )
    ).delete(synchronize_session=False)
    
    # Level 2: planned_workout
    db.query(PlannedWorkout).filter(PlannedWorkout.athlete_id == user_id).delete(synchronize_session=False)
    
    # Level 3: training_plan and activity children
    db.query(TrainingPlan).filter(TrainingPlan.athlete_id == user_id).delete(synchronize_session=False)
    
    # Activity children (before deleting activities)
    activity_ids = db.query(Activity.id).filter(Activity.athlete_id == user_id).subquery()
    db.query(ActivitySplit).filter(ActivitySplit.activity_id.in_(activity_ids)).delete(synchronize_session=False)
    db.query(ActivityFeedback).filter(ActivityFeedback.activity_id.in_(activity_ids)).delete(synchronize_session=False)
    db.query(BestEffort).filter(BestEffort.activity_id.in_(activity_ids)).delete(synchronize_session=False)
    db.query(CalendarInsight).filter(CalendarInsight.activity_id.in_(activity_ids)).delete(synchronize_session=False)
    db.query(CalendarNote).filter(CalendarNote.activity_id.in_(activity_ids)).delete(synchronize_session=False)
    db.query(NutritionEntry).filter(NutritionEntry.activity_id.in_(activity_ids)).delete(synchronize_session=False)
    db.query(PersonalBest).filter(PersonalBest.activity_id.in_(activity_ids)).delete(synchronize_session=False)
    db.query(Activity).filter(Activity.athlete_id == user_id).delete(synchronize_session=False)
    
    # Level 4: All other direct FK tables (order matters for nested FKs)
    db.query(ActivityFeedback).filter(ActivityFeedback.athlete_id == user_id).delete(synchronize_session=False)
    db.query(AdminAuditEvent).filter(AdminAuditEvent.target_athlete_id == user_id).delete(synchronize_session=False)
    db.query(AdminAuditEvent).filter(AdminAuditEvent.actor_athlete_id == user_id).delete(synchronize_session=False)
    db.query(AthleteDataImportJob).filter(AthleteDataImportJob.athlete_id == user_id).delete(synchronize_session=False)
    db.query(AthleteIngestionState).filter(AthleteIngestionState.athlete_id == user_id).delete(synchronize_session=False)
    db.query(AthleteTrainingPaceProfile).filter(AthleteTrainingPaceProfile.athlete_id == user_id).delete(synchronize_session=False)
    db.query(AthleteRaceResultAnchor).filter(AthleteRaceResultAnchor.athlete_id == user_id).delete(synchronize_session=False)
    db.query(BestEffort).filter(BestEffort.athlete_id == user_id).delete(synchronize_session=False)
    db.query(BodyComposition).filter(BodyComposition.athlete_id == user_id).delete(synchronize_session=False)
    db.query(CalendarInsight).filter(CalendarInsight.athlete_id == user_id).delete(synchronize_session=False)
    db.query(CalendarNote).filter(CalendarNote.athlete_id == user_id).delete(synchronize_session=False)
    db.query(CoachActionProposal).filter(CoachActionProposal.athlete_id == user_id).delete(synchronize_session=False)
    db.query(CoachChat).filter(CoachChat.athlete_id == user_id).delete(synchronize_session=False)
    db.query(CoachIntentSnapshot).filter(CoachIntentSnapshot.athlete_id == user_id).delete(synchronize_session=False)
    db.query(CoachUsage).filter(CoachUsage.athlete_id == user_id).delete(synchronize_session=False)
    db.query(CoachingRecommendation).filter(CoachingRecommendation.athlete_id == user_id).delete(synchronize_session=False)
    db.query(DailyCheckin).filter(DailyCheckin.athlete_id == user_id).delete(synchronize_session=False)
    db.query(InsightFeedback).filter(InsightFeedback.athlete_id == user_id).delete(synchronize_session=False)
    db.query(IntakeQuestionnaire).filter(IntakeQuestionnaire.athlete_id == user_id).delete(synchronize_session=False)
    
    # Invite handling (invite_audit_event references invite_allowlist)
    invite_ids = db.query(InviteAllowlist.id).filter(InviteAllowlist.invited_by_athlete_id == user_id).subquery()
    db.query(InviteAuditEvent).filter(InviteAuditEvent.invite_id.in_(invite_ids)).delete(synchronize_session=False)
    db.query(InviteAuditEvent).filter(InviteAuditEvent.actor_athlete_id == user_id).delete(synchronize_session=False)
    db.query(InviteAllowlist).filter(InviteAllowlist.revoked_by_athlete_id == user_id).delete(synchronize_session=False)
    db.query(InviteAllowlist).filter(InviteAllowlist.used_by_athlete_id == user_id).delete(synchronize_session=False)
    db.query(InviteAllowlist).filter(InviteAllowlist.invited_by_athlete_id == user_id).delete(synchronize_session=False)
    
    db.query(NutritionEntry).filter(NutritionEntry.athlete_id == user_id).delete(synchronize_session=False)
    db.query(PersonalBest).filter(PersonalBest.athlete_id == user_id).delete(synchronize_session=False)
    db.query(PlanModificationLog).filter(PlanModificationLog.athlete_id == user_id).delete(synchronize_session=False)
    db.query(RacePromoCode).filter(RacePromoCode.created_by == user_id).delete(synchronize_session=False)
    db.query(Subscription).filter(Subscription.athlete_id == user_id).delete(synchronize_session=False)
    db.query(TrainingAvailability).filter(TrainingAvailability.athlete_id == user_id).delete(synchronize_session=False)
    db.query(WorkPattern).filter(WorkPattern.athlete_id == user_id).delete(synchronize_session=False)
    db.query(WorkoutSelectionAuditEvent).filter(WorkoutSelectionAuditEvent.athlete_id == user_id).delete(synchronize_session=False)
    
    # Level 5: Delete the athlete
    db.query(Athlete).filter(Athlete.id == user_id).delete(synchronize_session=False)
    
    # Audit the deletion (record under actor, not target since target is now deleted)
    from services.admin_audit import record_admin_audit_event
    
    record_admin_audit_event(
        db,
        request=http_request,
        actor=current_user,
        action="athlete.delete",
        target_athlete_id=None,  # User is deleted, can't reference
        reason=request.reason,
        payload={"deleted_user": deleted_user_info},
    )
    
    db.commit()
    
    logger.warning(f"User {deleted_user_info['email']} (id={deleted_user_info['id']}) permanently deleted by {current_user.email}")
    
    return {
        "success": True,
        "deleted_user": deleted_user_info,
        "message": "User and all associated data permanently deleted",
    }


@router.post("/users/{user_id}/impersonate")
def start_impersonation(
    user_id: UUID,
    http_request: Request,
    request: Optional[ImpersonateUserRequest] = Body(default=None),
    _: None = Depends(deny_impersonation_mutation("auth.impersonate.start")),
    current_user: Athlete = Depends(require_owner),
    db: Session = Depends(get_db),
):
    """
    Start impersonation session for a user.
    Returns a temporary token that can be used to act as that user.
    Owner only (time-boxed token + audited).
    """
    target_user = db.query(Athlete).filter(Athlete.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    from core.security import create_access_token, decode_access_token
    from core.config import settings
    from datetime import timedelta, datetime, timezone

    ttl_min = int(getattr(settings, "IMPERSONATION_TOKEN_TTL_MINUTES", 20))
    if request and request.ttl_minutes is not None:
        ttl_min = int(request.ttl_minutes)

    impersonation_token = create_access_token(
        data={
            "sub": str(target_user.id),
            "email": target_user.email,
            "role": target_user.role,
            "impersonated_by": str(current_user.id),
            "is_impersonation": True,
        },
        expires_delta=timedelta(minutes=ttl_min),
    )

    exp = None
    payload = decode_access_token(impersonation_token) or {}
    if payload.get("exp"):
        try:
            exp = datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc)
        except Exception:
            exp = None

    # Hard audit (best-effort: should not block primary path).
    try:
        from services.admin_audit import record_admin_audit_event

        record_admin_audit_event(
            db,
            request=http_request,
            actor=current_user,
            action="auth.impersonate.start",
            target_athlete_id=str(target_user.id),
            reason=(request.reason if request else None),
            payload={
                "ttl_minutes": ttl_min,
                "expires_at": exp.isoformat() if exp else None,
            },
        )
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    logger.warning(f"Owner {current_user.email} started impersonation of {target_user.email} (ttl={ttl_min}m)")

    return {
        "token": impersonation_token,
        "user": {
            "id": str(target_user.id),
            "email": target_user.email,
            "display_name": target_user.display_name,
        },
        "impersonated_by": {
            "id": str(current_user.id),
            "email": current_user.email,
        },
        "expires_at": exp.isoformat() if exp else None,
        "ttl_minutes": ttl_min,
    }


@router.get("/health")
def get_system_health(
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Get detailed system health metrics.
    Admin/owner only.
    """
    # Database health
    try:
        db.execute(func.now())
        db_healthy = True
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        db_healthy = False
    
    # User counts
    total_users = db.query(Athlete).count()
    active_users = db.query(Athlete).filter(
        Athlete.created_at >= datetime.now() - timedelta(days=30)
    ).count()
    
    # Activity counts
    total_activities = db.query(Activity).count()
    recent_activities = db.query(Activity).filter(
        Activity.start_time >= datetime.now() - timedelta(days=7)
    ).count()
    
    # Data collection stats
    nutrition_entries = db.query(NutritionEntry).count()
    work_patterns = db.query(WorkPattern).count()
    body_composition = db.query(BodyComposition).count()
    
    return {
        "database": "healthy" if db_healthy else "unhealthy",
        "users": {
            "total": total_users,
            "active_30d": active_users,
        },
        "activities": {
            "total": total_activities,
            "last_7d": recent_activities,
        },
        "data_collection": {
            "nutrition_entries": nutrition_entries,
            "work_patterns": work_patterns,
            "body_composition": body_composition,
        },
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/metrics")
def get_site_metrics(
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
):
    """
    Get site-wide metrics for growth and engagement.
    Admin/owner only.
    """
    cutoff_date = datetime.now() - timedelta(days=days)
    
    # User growth
    new_users = db.query(Athlete).filter(
        Athlete.created_at >= cutoff_date
    ).count()
    
    # Engagement metrics
    users_with_activities = db.query(func.count(func.distinct(Activity.athlete_id))).filter(
        Activity.start_time >= cutoff_date
    ).scalar()
    
    users_with_nutrition = db.query(func.count(func.distinct(NutritionEntry.athlete_id))).filter(
        NutritionEntry.date >= cutoff_date.date()
    ).scalar()
    
    # Average activities per user
    avg_activities = db.query(
        func.avg(func.count(Activity.id))
    ).filter(
        Activity.start_time >= cutoff_date
    ).group_by(Activity.athlete_id).scalar() or 0
    
    return {
        "period_days": days,
        "user_growth": {
            "new_users": new_users,
            "growth_rate": round((new_users / max(1, db.query(Athlete).filter(Athlete.created_at < cutoff_date).count())) * 100, 2),
        },
        "engagement": {
            "users_with_activities": users_with_activities,
            "users_with_nutrition": users_with_nutrition,
            "avg_activities_per_user": round(float(avg_activities), 2),
        },
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/correlations/test")
def test_correlation_calculation(
    athlete_id: UUID = Query(..., description="Athlete ID to test"),
    days: int = Query(90, ge=30, le=365),
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Trigger correlation calculation for a specific athlete and return raw output.
    Admin/owner only.
    """
    from services.correlation_engine import analyze_correlations
    
    try:
        result = analyze_correlations(
            athlete_id=str(athlete_id),
            days=days,
            db=db
        )
        
        return {
            "status": "success",
            "athlete_id": str(athlete_id),
            "days": days,
            "result": result,
        }
    except Exception as e:
        logger.error(f"Error testing correlations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )


@router.get("/query/templates")
def list_query_templates(
    current_user: Athlete = Depends(require_admin),
):
    """
    List available query templates.
    Admin/owner only.
    """
    return {
        "templates": [
            {
                "name": "efficiency_by_workout_type",
                "description": "Average efficiency by workout type",
                "scope": "admin",
                "params": ["athlete_id (optional)", "days"],
            },
            {
                "name": "workout_type_distribution", 
                "description": "Distribution of workout types across all athletes",
                "scope": "admin",
                "params": ["days"],
            },
            {
                "name": "correlation_patterns",
                "description": "Significant correlations found across athletes",
                "scope": "admin", 
                "params": ["min_strength"],
            },
            {
                "name": "cross_athlete_efficiency",
                "description": "Efficiency distribution across population",
                "scope": "admin",
                "params": ["days"],
            },
            {
                "name": "performance_over_time",
                "description": "Track an athlete's performance metrics over time",
                "scope": "admin",
                "params": ["athlete_id", "workout_type (optional)", "days"],
            },
        ]
    }


@router.post("/query/execute")
def execute_query_template(
    template: str = Query(..., description="Template name"),
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
    athlete_id: Optional[UUID] = Query(None, description="Athlete ID for single-athlete queries"),
    days: int = Query(180, ge=1, le=730),
    workout_type: Optional[str] = Query(None, description="Filter by workout type"),
    min_strength: float = Query(0.3, ge=0.0, le=1.0, description="Min correlation strength"),
):
    """
    Execute a pre-built query template.
    Admin/owner only.
    """
    from services.query_engine import QueryEngine, QueryTemplates, QueryScope
    
    engine = QueryEngine(db)
    
    # Get the appropriate template
    if template == "efficiency_by_workout_type":
        spec = QueryTemplates.efficiency_by_workout_type(athlete_id=athlete_id, days=days)
    elif template == "workout_type_distribution":
        spec = QueryTemplates.workout_type_distribution(days=days)
    elif template == "correlation_patterns":
        spec = QueryTemplates.correlation_patterns(min_strength=min_strength)
    elif template == "cross_athlete_efficiency":
        spec = QueryTemplates.cross_athlete_efficiency_distribution(days=days)
    elif template == "performance_over_time":
        if not athlete_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="athlete_id required for performance_over_time template"
            )
        spec = QueryTemplates.performance_over_time(
            athlete_id=athlete_id, 
            workout_type=workout_type,
            days=days
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown template: {template}"
        )
    
    # Execute with admin scope
    result = engine.execute(spec, current_user, scope=QueryScope.ADMIN_ONLY)
    
    return {
        "template": template,
        "success": result.success,
        "data": result.data,
        "total_count": result.total_count,
        "execution_time_ms": result.execution_time_ms,
        "metadata": result.metadata,
        "error": result.error,
    }


@router.post("/query/custom")
def execute_custom_query(
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
    entity: str = Query(..., description="Entity to query: activity, nutrition, body_composition, correlation"),
    days: int = Query(180, ge=1, le=730),
    athlete_id: Optional[UUID] = Query(None, description="Filter to specific athlete"),
    group_by: Optional[str] = Query(None, description="Comma-separated fields to group by"),
    aggregations: Optional[str] = Query(None, description="Comma-separated field:agg_type pairs (e.g., 'efficiency:avg,distance_m:sum')"),
    filters_json: Optional[str] = Query(None, description="JSON array of filter objects [{field, operator, value}]"),
    sort_by: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    Execute a custom query with full flexibility.
    Admin/owner only.
    
    This is the power user interface - allows arbitrary queries
    with proper access control.
    """
    from services.query_engine import (
        QueryEngine, QuerySpec, QueryFilter, QueryScope, AggregationType
    )
    import json
    
    engine = QueryEngine(db)
    
    # Parse filters
    query_filters = []
    if filters_json:
        try:
            filter_list = json.loads(filters_json)
            for f in filter_list:
                query_filters.append(QueryFilter(
                    field=f.get("field"),
                    operator=f.get("operator", "eq"),
                    value=f.get("value")
                ))
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid filters_json: {str(e)}"
            )
    
    # Parse group_by
    group_by_list = group_by.split(",") if group_by else None
    
    # Parse aggregations
    agg_dict = None
    if aggregations:
        agg_dict = {}
        for pair in aggregations.split(","):
            if ":" in pair:
                field, agg_type = pair.split(":", 1)
                try:
                    agg_dict[field.strip()] = AggregationType(agg_type.strip())
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid aggregation type: {agg_type}"
                    )
    
    # Build spec
    spec = QuerySpec(
        entity=entity,
        days=days,
        athlete_id=athlete_id,
        filters=query_filters,
        group_by=group_by_list,
        aggregations=agg_dict,
        sort_by=sort_by,
        limit=limit,
        anonymize=True,
    )
    
    # Execute
    result = engine.execute(spec, current_user, scope=QueryScope.ADMIN_ONLY)
    
    return {
        "entity": entity,
        "success": result.success,
        "data": result.data,
        "total_count": result.total_count,
        "execution_time_ms": result.execution_time_ms,
        "metadata": result.metadata,
        "error": result.error,
    }


@router.get("/query/entities")
def list_queryable_entities(
    current_user: Athlete = Depends(require_admin),
):
    """
    List all entities that can be queried with their available fields.
    Admin/owner only.
    """
    from services.query_engine import QueryEngine
    
    entities = {}
    for entity_name, model in QueryEngine.ENTITY_MODELS.items():
        entities[entity_name] = {
            "fields": [col.name for col in model.__table__.columns],
            "date_field": QueryEngine.DATE_FIELDS.get(entity_name),
        }
    
    return {"entities": entities}


@router.get("/query")
def cross_athlete_query(
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
    query_type: str = Query(..., description="Query type: 'avg_efficiency', 'correlation_patterns', 'workout_distribution'"),
    min_activities: int = Query(10, ge=1, description="Minimum activities per athlete"),
    days: int = Query(180, ge=1, le=730),
):
    """
    Cross-athlete anonymized aggregate queries (legacy endpoint).
    Use /query/execute or /query/custom for full functionality.
    Admin/owner only.
    """
    from services.query_engine import QueryEngine, QueryTemplates, QueryScope
    
    engine = QueryEngine(db)
    
    if query_type == "avg_efficiency":
        spec = QueryTemplates.efficiency_by_workout_type(days=days)
        result = engine.execute(spec, current_user, scope=QueryScope.ADMIN_ONLY)
        return {
            "query_type": query_type,
            "data": result.data,
            "execution_time_ms": result.execution_time_ms,
        }
    
    elif query_type == "correlation_patterns":
        spec = QueryTemplates.correlation_patterns()
        result = engine.execute(spec, current_user, scope=QueryScope.ADMIN_ONLY)
        return {
            "query_type": query_type,
            "data": result.data,
            "execution_time_ms": result.execution_time_ms,
        }
    
    elif query_type == "workout_distribution":
        spec = QueryTemplates.workout_type_distribution(days=days)
        result = engine.execute(spec, current_user, scope=QueryScope.ADMIN_ONLY)
        return {
            "query_type": query_type,
            "data": result.data,
            "execution_time_ms": result.execution_time_ms,
        }
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown query type: {query_type}. Use /query/templates to see available options."
        )


# ─────────────────────────────────────────────────────────────────────────────
# RACE PROMO CODE MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

class CreateRacePromoCodeRequest(BaseModel):
    """Request to create a race promo code."""
    code: str = Field(..., description="The promo code (e.g., MARATHON2026)")
    race_name: str = Field(..., description="Name of the race")
    race_date: Optional[date] = Field(None, description="Date of the race")
    trial_days: int = Field(30, ge=1, le=90, description="Trial length in days")
    valid_until: Optional[datetime] = Field(None, description="Expiration date (null = never)")
    max_uses: Optional[int] = Field(None, ge=1, description="Max uses (null = unlimited)")


@router.post("/race-codes")
def create_race_promo_code(
    request: CreateRacePromoCodeRequest,
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Create a new race promo code for QR activation at packet pickup.
    
    Athletes who register with this code get an extended trial (default 30 days).
    """
    code = request.code.strip().upper()
    
    # Check if code already exists
    existing = db.query(RacePromoCode).filter(RacePromoCode.code == code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Code '{code}' already exists")
    
    promo = RacePromoCode(
        code=code,
        race_name=request.race_name,
        race_date=request.race_date,
        trial_days=request.trial_days,
        valid_until=request.valid_until,
        max_uses=request.max_uses,
        is_active=True,
        created_by=current_user.id,
    )
    
    db.add(promo)
    db.commit()
    db.refresh(promo)
    
    return {
        "success": True,
        "code": promo.code,
        "race_name": promo.race_name,
        "trial_days": promo.trial_days,
        "valid_until": promo.valid_until.isoformat() if promo.valid_until else None,
        "max_uses": promo.max_uses,
    }


@router.get("/race-codes")
def list_race_promo_codes(
    include_inactive: bool = False,
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all race promo codes with usage stats."""
    query = db.query(RacePromoCode)
    if not include_inactive:
        query = query.filter(RacePromoCode.is_active == True)
    
    codes = query.order_by(RacePromoCode.created_at.desc()).all()
    
    return {
        "codes": [
            {
                "id": str(c.id),
                "code": c.code,
                "race_name": c.race_name,
                "race_date": c.race_date.isoformat() if c.race_date else None,
                "trial_days": c.trial_days,
                "valid_until": c.valid_until.isoformat() if c.valid_until else None,
                "max_uses": c.max_uses,
                "current_uses": c.current_uses,
                "is_active": c.is_active,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in codes
        ],
        "total": len(codes),
    }


@router.post("/race-codes/{code}/deactivate")
def deactivate_race_promo_code(
    code: str,
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Deactivate a race promo code."""
    promo = db.query(RacePromoCode).filter(RacePromoCode.code == code.upper()).first()
    if not promo:
        raise HTTPException(status_code=404, detail="Code not found")
    
    promo.is_active = False
    db.commit()
    
    return {"success": True, "code": promo.code, "is_active": False}


@router.get("/race-codes/{code}/qr")
def get_race_code_qr(
    code: str,
    size: int = Query(default=400, ge=100, le=1000, description="QR code size in pixels"),
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Generate a QR code PNG for a race promo code.
    
    The QR code links to the registration page with the code pre-filled.
    Returns a PNG image that can be printed on flyers or packet inserts.
    """
    if not HAS_QRCODE:
        raise HTTPException(status_code=500, detail="QR code library not installed")
    
    promo = db.query(RacePromoCode).filter(RacePromoCode.code == code.upper()).first()
    if not promo:
        raise HTTPException(status_code=404, detail="Code not found")
    
    # Build the registration URL with the code
    base_url = os.getenv("FRONTEND_URL", "https://strideiq.run")
    registration_url = f"{base_url}/register?code={promo.code}"
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction for print
        box_size=10,
        border=4,
    )
    qr.add_data(registration_url)
    qr.make(fit=True)
    
    # Create image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Resize to requested size
    img = img.resize((size, size))
    
    # Convert to bytes
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    
    return Response(
        content=buffer.getvalue(),
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="{promo.code}_qr.png"',
            "Cache-Control": "max-age=86400",  # Cache for 24 hours
        }
    )

