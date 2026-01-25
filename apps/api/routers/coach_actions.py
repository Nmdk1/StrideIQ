from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Annotated, Any, Literal
from uuid import UUID

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.orm import Session

from core.auth import get_current_athlete, security as bearer_security
from core.database import get_db
from core.security import decode_access_token
from models import CoachActionProposal, PlannedWorkout, TrainingPlan, WorkoutTemplate


router = APIRouter(prefix="/v2/coach/actions", tags=["Coach Actions"])
logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic models (request/response + strict action catalog validation)
# =============================================================================

ProposalStatus = Literal["proposed", "confirmed", "rejected", "applied", "failed"]


class SwapDaysPayload(BaseModel):
    plan_id: UUID
    workout_id_1: UUID
    workout_id_2: UUID
    reason: str | None = None


class AdjustLoadPayload(BaseModel):
    plan_id: UUID
    week_number: int = Field(..., ge=1)
    adjustment: Literal["reduce_light", "reduce_moderate", "increase_light"]
    reason: str | None = None


class ReplaceWithTemplatePayload(BaseModel):
    plan_id: UUID
    workout_id: UUID
    template_id: str
    variant: Literal["A", "B"] = "A"
    reason: str | None = None


class SkipOrRestorePayload(BaseModel):
    plan_id: UUID
    workout_id: UUID
    skipped: bool
    reason: str | None = None


class SwapDaysAction(BaseModel):
    type: Literal["swap_days"]
    payload: SwapDaysPayload


class AdjustLoadAction(BaseModel):
    type: Literal["adjust_load"]
    payload: AdjustLoadPayload


class ReplaceWithTemplateAction(BaseModel):
    type: Literal["replace_with_template"]
    payload: ReplaceWithTemplatePayload


class SkipOrRestoreAction(BaseModel):
    type: Literal["skip_or_restore"]
    payload: SkipOrRestorePayload


ActionUnion = Annotated[
    SwapDaysAction | AdjustLoadAction | ReplaceWithTemplateAction | SkipOrRestoreAction,
    Field(discriminator="type"),
]


class ActionsEnvelopeV1(BaseModel):
    version: Literal[1] = 1
    actions: list[ActionUnion] = Field(..., min_length=1, max_length=5)


IdempotencyKey = Annotated[str, StringConstraints(min_length=8, max_length=128)]


class ProposeRequest(BaseModel):
    athlete_id: UUID
    reason: str = Field(..., min_length=3, max_length=500)
    actions: ActionsEnvelopeV1
    idempotency_key: IdempotencyKey


class ConfirmRequest(BaseModel):
    idempotency_key: IdempotencyKey


class RejectRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class WorkoutSnapshot(BaseModel):
    id: UUID
    scheduled_date: date | None
    title: str | None
    workout_type: str | None
    target_distance_km: float | None = None
    target_duration_minutes: int | None = None
    skipped: bool | None = None


class DiffPreviewEntry(BaseModel):
    plan_id: UUID
    workout_id: UUID
    before: WorkoutSnapshot
    after: WorkoutSnapshot


class ProposeResponse(BaseModel):
    proposal_id: UUID
    status: ProposalStatus
    athlete_id: UUID
    target_plan_id: UUID | None
    diff_preview: list[DiffPreviewEntry]
    risk_notes: list[str]
    created_at: datetime


class ApplyReceipt(BaseModel):
    actions_applied: int
    changes: list[DiffPreviewEntry]


class ConfirmResponse(BaseModel):
    proposal_id: UUID
    status: ProposalStatus
    confirmed_at: datetime | None
    applied_at: datetime | None
    receipt: ApplyReceipt | None = None
    error: str | None = None


class RejectResponse(BaseModel):
    proposal_id: UUID
    status: ProposalStatus
    rejected_at: datetime


# =============================================================================
# Internal helpers
# =============================================================================


QUALITY_TYPES = {
    "threshold",
    "tempo",
    "intervals",
    "vo2max",
    "speed",
    "long_mp",
    "progression",
    "race_pace",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _snapshot(w: PlannedWorkout) -> WorkoutSnapshot:
    return WorkoutSnapshot(
        id=w.id,
        scheduled_date=w.scheduled_date,
        title=getattr(w, "title", None),
        workout_type=getattr(w, "workout_type", None),
        target_distance_km=getattr(w, "target_distance_km", None),
        target_duration_minutes=getattr(w, "target_duration_minutes", None),
        skipped=bool(getattr(w, "skipped", False)),
    )


def _client_ip(request: Request | None) -> str | None:
    if not request:
        return None
    # Common reverse proxy headers (best-effort).
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip() or None
    return getattr(request.client, "host", None)


def _user_agent(request: Request | None) -> str | None:
    if not request:
        return None
    ua = request.headers.get("user-agent")
    return ua if ua else None


def _emit_coach_action_event(
    *,
    event: str,
    athlete_id: UUID,
    proposal_id: UUID | None = None,
    status: str | None = None,
    reason: str | None = None,
    extra: dict | None = None,
) -> None:
    """
    Beta monitoring hook:
    - logs a structured event (parsable by log aggregation)
    - best-effort sends a Sentry breadcrumb/message if configured
    """
    payload = {
        "event": event,
        "athlete_id": str(athlete_id),
        "proposal_id": str(proposal_id) if proposal_id else None,
        "status": status,
        "reason": reason,
    }
    if extra:
        payload.update(extra)
    try:
        logger.info("coach_action_event", extra=payload)
    except Exception:
        # Never fail requests due to telemetry.
        pass

    try:
        import sentry_sdk  # type: ignore

        sentry_sdk.add_breadcrumb(category="coach_action", message=event, level="info", data=payload)
    except Exception:
        pass


_PERM_IMPERSONATION_COACH_APPLY = "coach.actions.apply_impersonation"


def _get_impersonation_actor(
    db: Session, *, credentials: HTTPAuthorizationCredentials | None
) -> tuple[bool, UUID | None, Any]:
    """
    Returns: (is_impersonation, impersonated_by_athlete_id, raw_payload)
    """
    if not credentials:
        return False, None, {}
    payload = decode_access_token(credentials.credentials) or {}
    if payload.get("is_impersonation") is True:
        try:
            return True, UUID(str(payload.get("impersonated_by"))), payload
        except Exception:
            return True, None, payload
    return False, None, payload


def _require_impersonation_apply_permission(
    db: Session,
    *,
    request: Request,
    impersonated_by_athlete_id: UUID | None,
    target_athlete_id: UUID,
    action: str,
) -> Any:
    """
    Phase 10 production-beta safety:
    - Confirm/apply/reject MUST NOT be executed under impersonation by default.
    - Only allow when the *impersonator* has an explicit permission flag.
    - Always emit a high-signal audit event.
    """
    from services.admin_audit import record_admin_audit_event
    from models import Athlete

    if impersonated_by_athlete_id is None:
        # High-signal audit: malformed impersonation token attempting mutation.
        try:
            record_admin_audit_event(
                db,
                request=request,
                actor=Athlete(id=target_athlete_id),  # type: ignore[arg-type]
                action=f"{action}.blocked_impersonation",
                target_athlete_id=str(target_athlete_id),
                reason="missing_impersonated_by",
                payload={"permission_required": _PERM_IMPERSONATION_COACH_APPLY},
            )
        except Exception:
            pass
        raise HTTPException(status_code=403, detail=f"impersonation_not_allowed:{action}")

    actor = db.query(Athlete).filter(Athlete.id == impersonated_by_athlete_id).first()
    if not actor:
        raise HTTPException(status_code=403, detail=f"impersonation_not_allowed:{action}")

    perms = getattr(actor, "admin_permissions", None) or []
    allowed = _PERM_IMPERSONATION_COACH_APPLY in perms

    # High-signal audit event, regardless of allow/deny.
    try:
        record_admin_audit_event(
            db,
            request=request,
            actor=actor,
            action=f"{action}.impersonation_allowed" if allowed else f"{action}.blocked_impersonation",
            target_athlete_id=str(target_athlete_id),
            reason="impersonation_apply_guard",
            payload={"permission_required": _PERM_IMPERSONATION_COACH_APPLY},
        )
    except Exception:
        pass

    if not allowed:
        raise HTTPException(status_code=403, detail=f"impersonation_not_allowed:{action}")

    return actor


def _require_plan_owner(db: Session, *, athlete_id: UUID, plan_id: UUID) -> TrainingPlan:
    plan = (
        db.query(TrainingPlan)
        .filter(TrainingPlan.id == plan_id, TrainingPlan.athlete_id == athlete_id)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


def _require_workout_owner(db: Session, *, athlete_id: UUID, plan_id: UUID, workout_id: UUID) -> PlannedWorkout:
    w = (
        db.query(PlannedWorkout)
        .filter(
            PlannedWorkout.id == workout_id,
            PlannedWorkout.plan_id == plan_id,
            PlannedWorkout.athlete_id == athlete_id,
        )
        .first()
    )
    if not w:
        raise HTTPException(status_code=404, detail="Workout not found")
    return w


def _resolve_single_plan_id(actions: list[ActionUnion]) -> UUID | None:
    plan_ids: set[UUID] = set()
    for a in actions:
        plan_ids.add(a.payload.plan_id)  # type: ignore[attr-defined]
    if len(plan_ids) == 1:
        return next(iter(plan_ids))
    return None


def _render_template_description(tpl: WorkoutTemplate) -> tuple[str, str]:
    """
    Render a safe, deterministic description from a WorkoutTemplate.
    We intentionally avoid athlete-specific substitution here (no paces).
    """
    prog = tpl.progression_logic or {}
    steps = []
    try:
        steps = (prog.get("steps") or []) if isinstance(prog, dict) else []
    except Exception:
        steps = []
    step0 = steps[0] if steps else {}
    raw = (step0.get("description_template") or step0.get("structure") or "").strip()
    if not raw:
        raw = f"{tpl.name}"
    # Replace placeholders with neutral text (no claims).
    for ph in ("{e_pace}", "{m_pace}", "{t_pace}", "{i_pace}", "{r_pace}"):
        raw = raw.replace(ph, "target pace")
    return (tpl.name, raw)


def _map_intensity_to_workout_type(intensity_tier: str | None) -> str:
    t = (intensity_tier or "").upper()
    return {
        "RECOVERY": "easy",
        "AEROBIC": "easy",
        "THRESHOLD": "threshold",
        "VO2MAX": "intervals",
        "ANAEROBIC": "sharpening",
    }.get(t, "threshold")


def _simulate_diff_swap(plan_id: UUID, w1: PlannedWorkout, w2: PlannedWorkout) -> list[DiffPreviewEntry]:
    b1 = _snapshot(w1)
    b2 = _snapshot(w2)
    a1 = b1.model_copy(update={"scheduled_date": b2.scheduled_date})
    a2 = b2.model_copy(update={"scheduled_date": b1.scheduled_date})
    return [
        DiffPreviewEntry(plan_id=plan_id, workout_id=w1.id, before=b1, after=a1),
        DiffPreviewEntry(plan_id=plan_id, workout_id=w2.id, before=b2, after=a2),
    ]


def _simulate_diff_skip(plan_id: UUID, w: PlannedWorkout, *, skipped: bool) -> list[DiffPreviewEntry]:
    b = _snapshot(w)
    a = b.model_copy(update={"skipped": skipped})
    return [DiffPreviewEntry(plan_id=plan_id, workout_id=w.id, before=b, after=a)]


def _simulate_diff_replace(plan_id: UUID, w: PlannedWorkout, tpl: WorkoutTemplate, variant: str) -> list[DiffPreviewEntry]:
    b = _snapshot(w)
    name, desc = _render_template_description(tpl)
    a = b.model_copy(
        update={
            "title": f"{name} ({variant})",
            "workout_type": _map_intensity_to_workout_type(getattr(tpl, "intensity_tier", None)),
        }
    )
    # Description is not part of snapshot to keep it bounded; title/type captures user-visible change.
    return [DiffPreviewEntry(plan_id=plan_id, workout_id=w.id, before=b, after=a)]


def _simulate_diff_adjust(
    plan_id: UUID,
    workouts: list[PlannedWorkout],
    adjustment: str,
) -> list[DiffPreviewEntry]:
    out: list[DiffPreviewEntry] = []
    for w in workouts:
        b = _snapshot(w)
        a = b
        if adjustment == "reduce_light":
            if b.target_distance_km is not None:
                a = a.model_copy(update={"target_distance_km": round(float(b.target_distance_km) * 0.9, 1)})
        elif adjustment == "reduce_moderate":
            if b.target_distance_km is not None:
                a = a.model_copy(update={"target_distance_km": round(float(b.target_distance_km) * 0.7, 1)})
            if (b.workout_type or "") not in ("easy", "recovery", "rest"):
                a = a.model_copy(update={"workout_type": "easy", "title": "Easy Recovery Run"})
        elif adjustment == "increase_light":
            if (b.workout_type or "") in ("easy", "easy_strides", "easy_hills") and b.target_distance_km is not None:
                a = a.model_copy(update={"target_distance_km": round(float(b.target_distance_km) + 1.6, 1)})
        if a != b:
            out.append(DiffPreviewEntry(plan_id=plan_id, workout_id=w.id, before=b, after=a))
    return out


def _risk_notes_for(actions: list[ActionUnion]) -> list[str]:
    notes: list[str] = []
    for a in actions:
        if a.type == "swap_days":
            notes.append("Swapping days can change recovery spacing between key sessions.")
        elif a.type == "adjust_load":
            notes.append("Adjusting load changes weekly volume; keep easy days easy.")
        elif a.type == "replace_with_template":
            notes.append("Replacing a workout changes session structure; verify it matches your intent and constraints.")
        elif a.type == "skip_or_restore":
            notes.append("Skipping reduces load; restoring reintroduces scheduled stress.")
    # De-dupe while preserving order
    seen: set[str] = set()
    out = []
    for n in notes:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


@dataclass
class _ApplyChange:
    plan_id: UUID
    workout: PlannedWorkout
    before: WorkoutSnapshot
    after: WorkoutSnapshot


def _apply_swap_days(db: Session, *, athlete_id: UUID, plan_id: UUID, payload: SwapDaysPayload) -> list[_ApplyChange]:
    _require_plan_owner(db, athlete_id=athlete_id, plan_id=plan_id)
    w1 = _require_workout_owner(db, athlete_id=athlete_id, plan_id=plan_id, workout_id=payload.workout_id_1)
    w2 = _require_workout_owner(db, athlete_id=athlete_id, plan_id=plan_id, workout_id=payload.workout_id_2)
    if not w1.scheduled_date or not w2.scheduled_date:
        raise HTTPException(status_code=400, detail="Cannot swap workouts without scheduled dates")
    if getattr(w1, "completed", False) or getattr(w2, "completed", False):
        raise HTTPException(status_code=400, detail="Cannot swap completed workouts")

    b1 = _snapshot(w1)
    b2 = _snapshot(w2)

    original_date_1 = w1.scheduled_date
    original_date_2 = w2.scheduled_date
    original_dow_1 = w1.day_of_week
    original_dow_2 = w2.day_of_week

    temp_date = date(1900, 1, 1)
    w1.scheduled_date = temp_date
    w1.day_of_week = 0
    db.flush()

    w2.scheduled_date = original_date_1
    w2.day_of_week = original_dow_1
    db.flush()

    w1.scheduled_date = original_date_2
    w1.day_of_week = original_dow_2
    db.flush()

    a1 = _snapshot(w1)
    a2 = _snapshot(w2)

    # Audit (plan_modification_log) — append-only.
    try:
        from services.plan_audit import log_modification

        log_modification(
            db=db,
            athlete_id=athlete_id,
            plan_id=plan_id,
            action="swap_workouts",
            workout_id=w1.id,
            before_state=b1.model_dump(mode="json"),
            after_state=a1.model_dump(mode="json"),
            reason=payload.reason,
            source="coach",
        )
        log_modification(
            db=db,
            athlete_id=athlete_id,
            plan_id=plan_id,
            action="swap_workouts",
            workout_id=w2.id,
            before_state=b2.model_dump(mode="json"),
            after_state=a2.model_dump(mode="json"),
            reason=payload.reason,
            source="coach",
        )
    except Exception:
        pass

    return [
        _ApplyChange(plan_id=plan_id, workout=w1, before=b1, after=a1),
        _ApplyChange(plan_id=plan_id, workout=w2, before=b2, after=a2),
    ]


def _apply_skip_restore(db: Session, *, athlete_id: UUID, plan_id: UUID, payload: SkipOrRestorePayload) -> list[_ApplyChange]:
    _require_plan_owner(db, athlete_id=athlete_id, plan_id=plan_id)
    w = _require_workout_owner(db, athlete_id=athlete_id, plan_id=plan_id, workout_id=payload.workout_id)
    b = _snapshot(w)
    w.skipped = bool(payload.skipped)
    if payload.skipped:
        w.completed = False
    db.flush()
    a = _snapshot(w)

    try:
        from services.plan_audit import log_modification

        log_modification(
            db=db,
            athlete_id=athlete_id,
            plan_id=plan_id,
            action="delete_workout" if payload.skipped else "edit_workout",
            workout_id=w.id,
            before_state=b.model_dump(mode="json"),
            after_state=a.model_dump(mode="json"),
            reason=payload.reason,
            source="coach",
        )
    except Exception:
        pass

    return [_ApplyChange(plan_id=plan_id, workout=w, before=b, after=a)]


def _apply_replace_with_template(
    db: Session,
    *,
    athlete_id: UUID,
    plan_id: UUID,
    payload: ReplaceWithTemplatePayload,
) -> list[_ApplyChange]:
    _require_plan_owner(db, athlete_id=athlete_id, plan_id=plan_id)
    w = _require_workout_owner(db, athlete_id=athlete_id, plan_id=plan_id, workout_id=payload.workout_id)
    tpl = db.query(WorkoutTemplate).filter(WorkoutTemplate.id == payload.template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="Workout template not found")

    b = _snapshot(w)
    name, desc = _render_template_description(tpl)

    w.workout_type = _map_intensity_to_workout_type(getattr(tpl, "intensity_tier", None))
    w.title = f"{name} ({payload.variant})"
    w.description = desc
    db.flush()
    a = _snapshot(w)

    try:
        from services.plan_audit import log_modification

        log_modification(
            db=db,
            athlete_id=athlete_id,
            plan_id=plan_id,
            action="edit_workout",
            workout_id=w.id,
            before_state=b.model_dump(mode="json"),
            after_state=a.model_dump(mode="json"),
            reason=payload.reason,
            source="coach",
        )
    except Exception:
        pass

    return [_ApplyChange(plan_id=plan_id, workout=w, before=b, after=a)]


def _apply_adjust_load(
    db: Session,
    *,
    athlete_id: UUID,
    plan_id: UUID,
    payload: AdjustLoadPayload,
) -> list[_ApplyChange]:
    _require_plan_owner(db, athlete_id=athlete_id, plan_id=plan_id)
    workouts = (
        db.query(PlannedWorkout)
        .filter(
            PlannedWorkout.plan_id == plan_id,
            PlannedWorkout.athlete_id == athlete_id,
            PlannedWorkout.week_number == payload.week_number,
        )
        .all()
    )
    if not workouts:
        raise HTTPException(status_code=404, detail=f"Week {payload.week_number} not found")

    # Only modify workouts that are not completed or skipped.
    modifiable = [w for w in workouts if (not getattr(w, "completed", False)) and (not getattr(w, "skipped", False))]
    if not modifiable:
        raise HTTPException(status_code=404, detail=f"No modifiable workouts found in week {payload.week_number}")

    from services.planned_workout_text import normalize_workout_text_fields

    changes: list[_ApplyChange] = []

    if payload.adjustment == "reduce_light":
        converted = False
        for w in modifiable:
            b = _snapshot(w)
            if (w.workout_type in QUALITY_TYPES) and (not converted):
                w.workout_type = "easy"
                w.title = "Easy Run (adjusted)"
                w.coach_notes = "Adjusted to easy for recovery."
                w.description = None
                converted = True
            if w.target_distance_km:
                w.target_distance_km = round(float(w.target_distance_km) * 0.9, 1)
                w.description = None
            normalize_workout_text_fields(w)
            db.flush()
            a = _snapshot(w)
            if a != b:
                changes.append(_ApplyChange(plan_id=plan_id, workout=w, before=b, after=a))

    elif payload.adjustment == "reduce_moderate":
        for w in modifiable:
            b = _snapshot(w)
            if w.workout_type not in ("easy", "recovery", "rest"):
                w.workout_type = "easy"
                w.title = "Easy Recovery Run"
                w.coach_notes = "Recovery week adjustment. Keep it easy and relaxed."
                w.description = None
            if w.target_distance_km:
                w.target_distance_km = round(float(w.target_distance_km) * 0.7, 1)
                w.description = None
            normalize_workout_text_fields(w)
            db.flush()
            a = _snapshot(w)
            if a != b:
                changes.append(_ApplyChange(plan_id=plan_id, workout=w, before=b, after=a))

    elif payload.adjustment == "increase_light":
        for w in modifiable:
            b = _snapshot(w)
            if w.workout_type in ("easy", "easy_strides", "easy_hills") and w.target_distance_km:
                w.target_distance_km = round(float(w.target_distance_km) + 1.6, 1)
                w.description = None
                normalize_workout_text_fields(w)
            db.flush()
            a = _snapshot(w)
            if a != b:
                changes.append(_ApplyChange(plan_id=plan_id, workout=w, before=b, after=a))
    else:
        raise HTTPException(status_code=400, detail="Invalid adjustment")

    # Audit changes (best-effort)
    try:
        from services.plan_audit import log_modification

        for c in changes:
            log_modification(
                db=db,
                athlete_id=athlete_id,
                plan_id=plan_id,
                action="adjust_load",
                workout_id=c.workout.id,
                before_state=c.before.model_dump(mode="json"),
                after_state=c.after.model_dump(mode="json"),
                reason=payload.reason,
                source="coach",
            )
    except Exception:
        pass

    return changes


def _apply_actions(db: Session, *, athlete_id: UUID, actions: list[ActionUnion]) -> list[DiffPreviewEntry]:
    all_changes: list[DiffPreviewEntry] = []
    for action in actions:
        plan_id = action.payload.plan_id  # type: ignore[attr-defined]

        if action.type == "swap_days":
            changes = _apply_swap_days(db, athlete_id=athlete_id, plan_id=plan_id, payload=action.payload)
        elif action.type == "skip_or_restore":
            changes = _apply_skip_restore(db, athlete_id=athlete_id, plan_id=plan_id, payload=action.payload)
        elif action.type == "replace_with_template":
            changes = _apply_replace_with_template(db, athlete_id=athlete_id, plan_id=plan_id, payload=action.payload)
        elif action.type == "adjust_load":
            changes = _apply_adjust_load(db, athlete_id=athlete_id, plan_id=plan_id, payload=action.payload)
        else:
            raise HTTPException(status_code=400, detail="Unsupported action type")

        for c in changes:
            all_changes.append(
                DiffPreviewEntry(plan_id=c.plan_id, workout_id=c.workout.id, before=c.before, after=c.after)
            )
    return all_changes


def _diff_preview(db: Session, *, athlete_id: UUID, actions: list[ActionUnion]) -> list[DiffPreviewEntry]:
    out: list[DiffPreviewEntry] = []
    for a in actions:
        plan_id = a.payload.plan_id  # type: ignore[attr-defined]
        _require_plan_owner(db, athlete_id=athlete_id, plan_id=plan_id)

        if a.type == "swap_days":
            w1 = _require_workout_owner(db, athlete_id=athlete_id, plan_id=plan_id, workout_id=a.payload.workout_id_1)
            w2 = _require_workout_owner(db, athlete_id=athlete_id, plan_id=plan_id, workout_id=a.payload.workout_id_2)
            out.extend(_simulate_diff_swap(plan_id, w1, w2))

        elif a.type == "skip_or_restore":
            w = _require_workout_owner(db, athlete_id=athlete_id, plan_id=plan_id, workout_id=a.payload.workout_id)
            out.extend(_simulate_diff_skip(plan_id, w, skipped=a.payload.skipped))

        elif a.type == "replace_with_template":
            w = _require_workout_owner(db, athlete_id=athlete_id, plan_id=plan_id, workout_id=a.payload.workout_id)
            tpl = db.query(WorkoutTemplate).filter(WorkoutTemplate.id == a.payload.template_id).first()
            if not tpl:
                raise HTTPException(status_code=404, detail="Workout template not found")
            out.extend(_simulate_diff_replace(plan_id, w, tpl, a.payload.variant))

        elif a.type == "adjust_load":
            workouts = (
                db.query(PlannedWorkout)
                .filter(
                    PlannedWorkout.plan_id == plan_id,
                    PlannedWorkout.athlete_id == athlete_id,
                    PlannedWorkout.week_number == a.payload.week_number,
                )
                .all()
            )
            if not workouts:
                raise HTTPException(status_code=404, detail=f"Week {a.payload.week_number} not found")
            out.extend(_simulate_diff_adjust(plan_id, workouts, a.payload.adjustment))
        else:
            raise HTTPException(status_code=400, detail="Unsupported action type")
    return out


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/propose", response_model=ProposeResponse)
async def propose_action(
    req: ProposeRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_security),
    athlete=Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    # MVP safety: self-only proposals.
    if req.athlete_id != athlete.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Safety: proposals may be viewed under impersonation, but proposing is a mutation.
    # Block unless explicit permission is present on the impersonator.
    is_imp, imp_by, _ = _get_impersonation_actor(db, credentials=credentials)
    if is_imp:
        _require_impersonation_apply_permission(
            db,
            request=request,
            impersonated_by_athlete_id=imp_by,
            target_athlete_id=athlete.id,
            action="coach.action.propose",
        )

    existing = (
        db.query(CoachActionProposal)
        .filter(CoachActionProposal.athlete_id == athlete.id, CoachActionProposal.idempotency_key == req.idempotency_key)
        .first()
    )
    actions = req.actions.actions
    target_plan_id = _resolve_single_plan_id(actions)
    if target_plan_id is None:
        raise HTTPException(status_code=400, detail="All actions in a proposal must target the same plan (MVP)")

    # Validate ownership and compute preview.
    preview = _diff_preview(db, athlete_id=athlete.id, actions=actions)
    risk_notes = _risk_notes_for(actions)

    if existing:
        _emit_coach_action_event(
            event="coach.action.proposed.idempotent_hit",
            athlete_id=athlete.id,
            proposal_id=existing.id,
            status=existing.status,
        )
        try:
            from services.admin_audit import record_admin_audit_event

            record_admin_audit_event(
                db,
                request=request,
                actor=athlete,
                action="coach.action.propose.idempotent_hit",
                target_athlete_id=str(athlete.id),
                payload={"proposal_id": str(existing.id), "actions_count": len(actions), "target_plan_id": str(target_plan_id)},
            )
        except Exception:
            pass
        return ProposeResponse(
            proposal_id=existing.id,
            status=existing.status,  # type: ignore[arg-type]
            athlete_id=existing.athlete_id,
            target_plan_id=existing.target_plan_id,
            diff_preview=preview,
            risk_notes=risk_notes,
            created_at=existing.created_at,
        )

    proposal = CoachActionProposal(
        athlete_id=athlete.id,
        created_by={"actor_type": "athlete", "actor_athlete_id": str(athlete.id), "source": "coach_chat"},
        status="proposed",
        actions_json=req.actions.model_dump(mode="json"),
        reason=req.reason,
        idempotency_key=req.idempotency_key,
        target_plan_id=target_plan_id,
    )
    db.add(proposal)
    db.flush()

    _emit_coach_action_event(
        event="coach.action.proposed",
        athlete_id=athlete.id,
        proposal_id=proposal.id,
        status=proposal.status,
        extra={"actions_count": len(actions), "target_plan_id": str(target_plan_id)},
    )
    try:
        from services.admin_audit import record_admin_audit_event

        record_admin_audit_event(
            db,
            request=request,
            actor=athlete,
            action="coach.action.proposed",
            target_athlete_id=str(athlete.id),
            payload={
                "proposal_id": str(proposal.id),
                "actions_count": len(actions),
                "action_types": [a.type for a in actions],
                "target_plan_id": str(target_plan_id),
            },
        )
    except Exception:
        pass

    return ProposeResponse(
        proposal_id=proposal.id,
        status="proposed",
        athlete_id=proposal.athlete_id,
        target_plan_id=proposal.target_plan_id,
        diff_preview=preview,
        risk_notes=risk_notes,
        created_at=proposal.created_at or _now(),
    )


@router.post("/{proposal_id}/confirm", response_model=ConfirmResponse)
async def confirm_action(
    proposal_id: UUID,
    req: ConfirmRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_security),
    athlete=Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    # Lock proposal row to prevent double-apply under concurrent confirms.
    proposal = (
        db.query(CoachActionProposal)
        .filter(CoachActionProposal.id == proposal_id)
        .with_for_update()
        .first()
    )
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if proposal.athlete_id != athlete.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Impersonation: confirm/apply is a high-risk mutation. Block unless explicitly permitted.
    is_imp, imp_by, _ = _get_impersonation_actor(db, credentials=credentials)
    impersonator = None
    if is_imp:
        impersonator = _require_impersonation_apply_permission(
            db,
            request=request,
            impersonated_by_athlete_id=imp_by,
            target_athlete_id=athlete.id,
            action="coach.action.confirm",
        )

    if proposal.status == "applied":
        receipt = proposal.apply_receipt_json or {}
        _emit_coach_action_event(
            event="coach.action.confirm.idempotent_hit",
            athlete_id=athlete.id,
            proposal_id=proposal.id,
            status=proposal.status,
        )
        return ConfirmResponse(
            proposal_id=proposal.id,
            status="applied",
            confirmed_at=proposal.confirmed_at,
            applied_at=proposal.applied_at,
            receipt=ApplyReceipt(**receipt) if receipt else None,
            error=None,
        )
    if proposal.status == "rejected":
        raise HTTPException(status_code=409, detail=f"Cannot confirm proposal in status: {proposal.status}")
    # Production-beta: allow retrying a failed apply (rollback-safe via savepoint).
    if proposal.status == "failed":
        proposal.error = None
    if proposal.status not in ("proposed", "failed"):
        raise HTTPException(status_code=409, detail=f"Cannot confirm proposal in status: {proposal.status}")

    # Optional TOCTOU guard: require plan still belongs to athlete.
    if proposal.target_plan_id is not None:
        _require_plan_owner(db, athlete_id=athlete.id, plan_id=proposal.target_plan_id)

    # Apply transactionally (DB transaction handled by get_db dependency).
    proposal.status = "confirmed"
    if proposal.confirmed_at is None:
        proposal.confirmed_at = _now()
    db.flush()

    try:
        env = ActionsEnvelopeV1.model_validate(proposal.actions_json or {})

        # Savepoint: if apply fails, roll back plan/workout mutations while still persisting
        # proposal.status=failed and error for operator visibility / retry.
        with db.begin_nested():
            changes = _apply_actions(db, athlete_id=athlete.id, actions=env.actions)
            proposal.status = "applied"
            proposal.applied_at = _now()
            receipt = ApplyReceipt(actions_applied=len(env.actions), changes=changes)
            proposal.apply_receipt_json = receipt.model_dump(mode="json")

        # Persist audit metadata onto each plan_modification_log entry best-effort (request context)
        try:
            from sqlalchemy import text

            # Backfill ip/user_agent onto rows created in this transaction (source='coach', created very recently).
            # Note: we do not depend on this for correctness; it's purely for operator visibility.
            ip = _client_ip(request)
            ua = _user_agent(request)
            if (ip or ua) and proposal.target_plan_id is not None:
                db.execute(
                    text(
                        """
                        UPDATE plan_modification_log
                        SET ip_address = COALESCE(ip_address, :ip),
                            user_agent = COALESCE(user_agent, :ua)
                        WHERE athlete_id = :athlete_id
                          AND plan_id = :plan_id
                          AND source = 'coach'
                          AND created_at > (now() - interval '5 minutes')
                        """
                    ),
                    {"ip": ip, "ua": ua, "athlete_id": str(athlete.id), "plan_id": str(proposal.target_plan_id)},
                )
        except Exception:
            pass

        db.flush()

        _emit_coach_action_event(
            event="coach.action.applied",
            athlete_id=athlete.id,
            proposal_id=proposal.id,
            status=proposal.status,
            extra={"actions_count": len(env.actions), "changes_count": len(changes)},
        )
        try:
            from services.admin_audit import record_admin_audit_event

            actor = impersonator or athlete
            record_admin_audit_event(
                db,
                request=request,
                actor=actor,
                action="coach.action.applied",
                target_athlete_id=str(athlete.id),
                payload={
                    "proposal_id": str(proposal.id),
                    "actions_count": len(env.actions),
                    "action_types": [a.type for a in env.actions],
                    "changes_count": len(changes),
                    "target_plan_id": str(proposal.target_plan_id) if proposal.target_plan_id else None,
                    "is_impersonation": bool(is_imp),
                    "impersonated_by": str(imp_by) if imp_by else None,
                },
            )
        except Exception:
            pass
        return ConfirmResponse(
            proposal_id=proposal.id,
            status="applied",
            confirmed_at=proposal.confirmed_at,
            applied_at=proposal.applied_at,
            receipt=receipt,
            error=None,
        )
    except HTTPException as e:
        # Persist failure state (apply changes were rolled back via savepoint).
        proposal.status = "failed"
        proposal.error = str(e.detail)
        try:
            db.flush()
            db.commit()
        except Exception:
            db.rollback()
        _emit_coach_action_event(
            event="coach.action.apply_failed",
            athlete_id=athlete.id,
            proposal_id=proposal.id,
            status="failed",
            reason=str(e.detail),
        )
        try:
            from services.admin_audit import record_admin_audit_event

            actor = impersonator or athlete
            record_admin_audit_event(
                db,
                request=request,
                actor=actor,
                action="coach.action.apply_failed",
                target_athlete_id=str(athlete.id),
                reason=str(e.detail),
                payload={
                    "proposal_id": str(proposal.id),
                    "actions_count": len((proposal.actions_json or {}).get("actions") or []),
                    "target_plan_id": str(proposal.target_plan_id) if proposal.target_plan_id else None,
                    "is_impersonation": bool(is_imp),
                    "impersonated_by": str(imp_by) if imp_by else None,
                },
            )
        except Exception:
            pass
        raise
    except Exception as e:
        proposal.status = "failed"
        proposal.error = f"{type(e).__name__}: {e}"
        try:
            db.flush()
            db.commit()
        except Exception:
            db.rollback()
        _emit_coach_action_event(
            event="coach.action.apply_failed",
            athlete_id=athlete.id,
            proposal_id=proposal.id,
            status="failed",
            reason=f"{type(e).__name__}",
        )
        try:
            from services.admin_audit import record_admin_audit_event

            actor = impersonator or athlete
            record_admin_audit_event(
                db,
                request=request,
                actor=actor,
                action="coach.action.apply_failed",
                target_athlete_id=str(athlete.id),
                reason=f"{type(e).__name__}",
                payload={
                    "proposal_id": str(proposal.id),
                    "target_plan_id": str(proposal.target_plan_id) if proposal.target_plan_id else None,
                    "is_impersonation": bool(is_imp),
                    "impersonated_by": str(imp_by) if imp_by else None,
                },
            )
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Apply failed")


@router.post("/{proposal_id}/reject", response_model=RejectResponse)
async def reject_action(
    proposal_id: UUID,
    req: RejectRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_security),
    athlete=Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    proposal = db.query(CoachActionProposal).filter(CoachActionProposal.id == proposal_id).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if proposal.athlete_id != athlete.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if proposal.status != "proposed":
        raise HTTPException(status_code=409, detail=f"Cannot reject proposal in status: {proposal.status}")

    is_imp, imp_by, _ = _get_impersonation_actor(db, credentials=credentials)
    impersonator = None
    if is_imp:
        impersonator = _require_impersonation_apply_permission(
            db,
            request=request,
            impersonated_by_athlete_id=imp_by,
            target_athlete_id=athlete.id,
            action="coach.action.reject",
        )

    proposal.status = "rejected"
    # We re-use confirmed_at as the decision timestamp (minimal schema).
    proposal.confirmed_at = _now()
    proposal.error = req.reason
    db.flush()

    _emit_coach_action_event(
        event="coach.action.rejected",
        athlete_id=athlete.id,
        proposal_id=proposal.id,
        status=proposal.status,
        reason=req.reason,
    )
    try:
        from services.admin_audit import record_admin_audit_event

        actor = impersonator or athlete
        record_admin_audit_event(
            db,
            request=request,
            actor=actor,
            action="coach.action.rejected",
            target_athlete_id=str(athlete.id),
            reason=req.reason,
            payload={
                "proposal_id": str(proposal.id),
                "is_impersonation": bool(is_imp),
                "impersonated_by": str(imp_by) if imp_by else None,
            },
        )
    except Exception:
        pass

    return RejectResponse(proposal_id=proposal.id, status="rejected", rejected_at=proposal.confirmed_at)

