from __future__ import annotations

from datetime import date as _date
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models import WorkoutSelectionAuditEvent


def record_workout_selection_event(
    *,
    db: Session,
    athlete_id: UUID,
    trigger: str,
    payload: Dict[str, Any],
    plan_generation_id: Optional[str] = None,
    plan_id: Optional[UUID] = None,
    target_date: Optional[str] = None,
    phase: Optional[str] = None,
    phase_week: Optional[int] = None,
    selected_template_id: Optional[str] = None,
    selection_mode: Optional[str] = None,
) -> None:
    """
    Persist a bounded audit event for workout selection.

    This is intentionally write-only / append-only. No secrets, no raw tokens, no giant blobs.
    """
    try:
        td: Optional[_date] = None
        if target_date:
            try:
                td = _date.fromisoformat(str(target_date)[:10])
            except Exception:
                td = None

        ev = WorkoutSelectionAuditEvent(
            athlete_id=athlete_id,
            trigger=str(trigger or "unknown"),
            plan_generation_id=plan_generation_id,
            plan_id=plan_id,
            target_date=td,
            phase=(str(phase).lower() if phase else None),
            phase_week=int(phase_week) if phase_week is not None else None,
            selected_template_id=selected_template_id,
            selection_mode=selection_mode,
            payload=payload or {},
        )
        db.add(ev)
        # Flush so failures surface during request/test; commit remains caller-owned.
        db.flush()
    except Exception:
        # Never block plan generation on audit logging.
        try:
            db.rollback()
        except Exception:
            pass

