"""
Admin/Owners Dashboard API Router

Comprehensive command center for site management, monitoring, testing, and debugging.
Owner/admin role only.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_
from typing import List, Optional, Dict, Any, Literal
from uuid import UUID
from datetime import datetime, timedelta

from core.database import get_db
from core.auth import require_admin, require_permission
from models import (
    Athlete,
    Activity,
    NutritionEntry,
    WorkPattern,
    BodyComposition,
    ActivityFeedback,
    InsightFeedback,
    FeatureFlag,
    InviteAllowlist,
    IntakeQuestionnaire,
    AthleteIngestionState,
    TrainingPlan,
)
from schemas import AthleteResponse
from pydantic import BaseModel, Field
from services.plan_framework.feature_flags import FeatureFlagService
import logging

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


class InviteRevokeRequest(BaseModel):
    email: str
    reason: Optional[str] = None


class CompAccessRequest(BaseModel):
    tier: str = Field(..., description="Subscription tier to set (e.g., 'elite')")
    reason: Optional[str] = Field(default=None, description="Why this comp was granted (audited)")


class ResetOnboardingRequest(BaseModel):
    reason: Optional[str] = Field(default=None, description="Why this reset was performed (audited)")
    stage: Optional[str] = Field(default="initial", description="Stage to reset to (default: initial)")


class RetryIngestionRequest(BaseModel):
    reason: Optional[str] = Field(default=None, description="Why this retry was performed (audited)")
    pages: int = Field(default=5, ge=1, le=50, description="Strava index backfill pages (bounded)")


class BlockUserRequest(BaseModel):
    blocked: bool = Field(..., description="Whether the user is blocked")
    reason: Optional[str] = Field(default=None, description="Why this block/unblock was performed (audited)")


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
    """
    from services.invite_service import create_invite

    inv = create_invite(db, email=request.email, invited_by_athlete_id=current_user.id, note=request.note)
    db.commit()
    db.refresh(inv)
    return {"success": True, "invite": {"id": str(inv.id), "email": inv.email, "is_active": inv.is_active, "used_at": inv.used_at}}


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
    return {"success": True, "invite": {"id": str(inv.id), "email": inv.email, "is_active": inv.is_active}}


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

    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "subscription_tier": user.subscription_tier,
        "stripe_customer_id": getattr(user, "stripe_customer_id", None),
        "is_blocked": bool(getattr(user, "is_blocked", False)),
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


@router.post("/users/{user_id}/comp")
def comp_access(
    user_id: UUID,
    request: CompAccessRequest,
    http_request: Request,
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


@router.post("/users/{user_id}/onboarding/reset")
def reset_onboarding(
    user_id: UUID,
    request: ResetOnboardingRequest,
    http_request: Request,
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


@router.post("/users/{user_id}/ingestion/retry")
def retry_ingestion(
    user_id: UUID,
    request: RetryIngestionRequest,
    http_request: Request,
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


@router.post("/users/{user_id}/block")
def set_blocked(
    user_id: UUID,
    request: BlockUserRequest,
    http_request: Request,
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


@router.post("/users/{user_id}/impersonate")
def start_impersonation(
    user_id: UUID,
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Start impersonation session for a user.
    Returns a temporary token that can be used to act as that user.
    Admin/owner only.
    """
    target_user = db.query(Athlete).filter(Athlete.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Generate impersonation token (simplified - in production, use proper JWT with impersonation claim)
    from core.security import create_access_token
    impersonation_token = create_access_token(
        data={
            "sub": str(target_user.id),
            "email": target_user.email,
            "role": target_user.role,
            "impersonated_by": str(current_user.id),
            "is_impersonation": True,
        }
    )
    
    logger.warning(f"Admin {current_user.email} started impersonation of {target_user.email}")
    
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

