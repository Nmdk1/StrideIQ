"""Body-area symptom log API (Strength v1, phase D).

Routes:

- ``GET    /v1/symptoms``           list active + recent history
- ``POST   /v1/symptoms``           log a new niggle/ache/pain/injury
- ``PATCH  /v1/symptoms/{id}``      update resolved_at, triggered_by, notes
- ``DELETE /v1/symptoms/{id}``      hard-delete an entry the athlete misfired

Every route is gated by the ``strength.v1`` feature flag (404 when off,
identical to ``routers/strength_v1.py`` so the surface is invisible to
athletes outside the rollout).

The system NEVER:
  - auto-classifies severity
  - infers a body area from sensor data
  - recommends a treatment, exercise, rest day, or referral
  - changes ``severity`` or ``body_area`` after the athlete enters it

If anyone adds an endpoint here that violates the contract above, the
narration purity test in ``test_strength_narration_purity.py`` (phase H)
will fail loudly. The endpoint vocabulary lives in
``schemas_symptom_v1`` so the purity test has a single source of truth.
"""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import List
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from core.feature_flags import is_feature_enabled
from models import Athlete, BodyAreaSymptomLog
from schemas_symptom_v1 import (
    SymptomLogCreate,
    SymptomLogListResponse,
    SymptomLogResponse,
    SymptomLogUpdate,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/symptoms", tags=["symptoms_v1"])

STRENGTH_V1_FLAG = "strength.v1"


def _require_strength_v1(athlete_id: UUID, db: Session) -> None:
    """Mirror the strength v1 router's gate.

    Symptom logging launches with strength v1 and shares its rollout —
    not a separate flag, by founder decision in
    ``docs/specs/STRENGTH_V1_SCOPE.md`` §6.5. 404 (not 403) keeps the
    surface invisible to athletes who aren't in the rollout.
    """
    if not is_feature_enabled(STRENGTH_V1_FLAG, str(athlete_id), db):
        raise HTTPException(status_code=404, detail="Not found")


@router.get("", response_model=SymptomLogListResponse)
def list_symptoms(
    history_limit: int = Query(50, ge=1, le=500),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SymptomLogListResponse:
    """Return active (resolved_at IS NULL) and recent history.

    Active rows come back ordered by ``started_at`` descending so the
    freshest niggle is at the top. History rows are also newest-first
    and capped by ``history_limit``.
    """
    _require_strength_v1(current_user.id, db)

    base = db.query(BodyAreaSymptomLog).filter(
        BodyAreaSymptomLog.athlete_id == current_user.id,
    )

    active = (
        base.filter(BodyAreaSymptomLog.resolved_at.is_(None))
        .order_by(BodyAreaSymptomLog.started_at.desc())
        .all()
    )
    history = (
        base.filter(BodyAreaSymptomLog.resolved_at.isnot(None))
        .order_by(BodyAreaSymptomLog.resolved_at.desc())
        .limit(history_limit)
        .all()
    )

    return SymptomLogListResponse(
        active=[SymptomLogResponse.model_validate(r) for r in active],
        history=[SymptomLogResponse.model_validate(r) for r in history],
    )


@router.post(
    "",
    response_model=SymptomLogResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_symptom(
    payload: SymptomLogCreate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SymptomLogResponse:
    """Log a new niggle / ache / pain / injury.

    The system stores exactly what the athlete entered; no
    auto-classification, no inferred severity, no clinical mapping.
    """
    _require_strength_v1(current_user.id, db)

    if payload.resolved_at and payload.resolved_at < payload.started_at:
        raise HTTPException(
            status_code=400,
            detail="resolved_at cannot be before started_at",
        )

    row = BodyAreaSymptomLog(
        id=uuid4(),
        athlete_id=current_user.id,
        body_area=payload.body_area,
        severity=payload.severity,
        started_at=payload.started_at,
        resolved_at=payload.resolved_at,
        triggered_by=payload.triggered_by,
        notes=payload.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return SymptomLogResponse.model_validate(row)


@router.patch("/{symptom_id}", response_model=SymptomLogResponse)
def update_symptom(
    symptom_id: UUID,
    payload: SymptomLogUpdate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SymptomLogResponse:
    """Update resolved_at / triggered_by / notes only.

    severity and body_area are intentionally immutable on this surface;
    if the athlete typed the wrong tier, the right move is "delete and
    re-log" so the timeline stays honest.
    """
    _require_strength_v1(current_user.id, db)

    row = (
        db.query(BodyAreaSymptomLog)
        .filter(
            BodyAreaSymptomLog.id == symptom_id,
            BodyAreaSymptomLog.athlete_id == current_user.id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Symptom not found")

    delta = payload.model_dump(exclude_unset=True)

    new_resolved = delta.get("resolved_at", row.resolved_at)
    if new_resolved is not None and new_resolved < row.started_at:
        raise HTTPException(
            status_code=400,
            detail="resolved_at cannot be before started_at",
        )

    for k, v in delta.items():
        setattr(row, k, v)

    db.commit()
    db.refresh(row)
    return SymptomLogResponse.model_validate(row)


@router.delete("/{symptom_id}", status_code=status.HTTP_200_OK)
def delete_symptom(
    symptom_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Hard-delete a symptom row.

    Symptom log entries are athlete-only writes; if they want one gone,
    we make it gone. Engine inputs (phase I) read from the live table,
    so a delete here also retroactively removes the symptom from any
    correlation that hasn't been computed yet.
    """
    _require_strength_v1(current_user.id, db)

    row = (
        db.query(BodyAreaSymptomLog)
        .filter(
            BodyAreaSymptomLog.id == symptom_id,
            BodyAreaSymptomLog.athlete_id == current_user.id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Symptom not found")

    db.delete(row)
    db.commit()
    return {"status": "deleted", "symptom_id": str(symptom_id)}
