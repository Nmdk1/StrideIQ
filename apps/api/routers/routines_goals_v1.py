"""Strength routines + goals CRUD (Strength v1, phase E).

Routes (all gated behind ``strength.v1`` flag, 404 when off):

Routines:
  GET    /v1/strength/routines              list active routines
  POST   /v1/strength/routines              create
  PATCH  /v1/strength/routines/{id}         rename / update items
  DELETE /v1/strength/routines/{id}         soft archive (is_archived=true)

Goals:
  GET    /v1/strength/goals                  list active goals
  POST   /v1/strength/goals                  create
  PATCH  /v1/strength/goals/{id}             update fields or deactivate
  DELETE /v1/strength/goals/{id}             hard delete

Important contract (STRENGTH_V1_SCOPE.md §6.2 / §6.3):

  The system never seeds, suggests, or recommends a routine OR a goal.
  These tables only store what the athlete saved themselves. The
  routes here are pure CRUD; no auto-population, no "suggested
  routine" endpoint, no "smart goal" endpoint. If a future change
  adds one, the strength narration purity test will fail.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from core.feature_flags import is_feature_enabled
from models import Athlete, StrengthGoal, StrengthRoutine
from schemas_routine_goal_v1 import (
    StrengthGoalCreate,
    StrengthGoalResponse,
    StrengthGoalUpdate,
    StrengthRoutineCreate,
    StrengthRoutineResponse,
    StrengthRoutineUpdate,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/strength", tags=["strength_v1_routines_goals"])

STRENGTH_V1_FLAG = "strength.v1"


def _require_strength_v1(athlete_id: UUID, db: Session) -> None:
    if not is_feature_enabled(STRENGTH_V1_FLAG, str(athlete_id), db):
        raise HTTPException(status_code=404, detail="Not found")


# ---------------------------------------------------------------------
# Routines
# ---------------------------------------------------------------------


@router.get("/routines", response_model=List[StrengthRoutineResponse])
def list_routines(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[StrengthRoutineResponse]:
    _require_strength_v1(current_user.id, db)
    rows = (
        db.query(StrengthRoutine)
        .filter(
            StrengthRoutine.athlete_id == current_user.id,
            StrengthRoutine.is_archived.is_(False),
        )
        .order_by(StrengthRoutine.last_used_at.desc().nullslast())
        .all()
    )
    return [StrengthRoutineResponse.model_validate(r) for r in rows]


@router.post(
    "/routines",
    response_model=StrengthRoutineResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_routine(
    payload: StrengthRoutineCreate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StrengthRoutineResponse:
    _require_strength_v1(current_user.id, db)
    row = StrengthRoutine(
        id=uuid4(),
        athlete_id=current_user.id,
        name=payload.name,
        items=[item.model_dump(mode="json") for item in payload.items],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return StrengthRoutineResponse.model_validate(row)


@router.patch(
    "/routines/{routine_id}", response_model=StrengthRoutineResponse
)
def update_routine(
    routine_id: UUID,
    payload: StrengthRoutineUpdate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StrengthRoutineResponse:
    _require_strength_v1(current_user.id, db)
    row = (
        db.query(StrengthRoutine)
        .filter(
            StrengthRoutine.id == routine_id,
            StrengthRoutine.athlete_id == current_user.id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Routine not found")

    delta = payload.model_dump(exclude_unset=True)
    if "name" in delta:
        row.name = delta["name"]
    if "items" in delta and delta["items"] is not None:
        row.items = [item for item in delta["items"]]
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return StrengthRoutineResponse.model_validate(row)


@router.delete("/routines/{routine_id}", status_code=status.HTTP_200_OK)
def archive_routine(
    routine_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_strength_v1(current_user.id, db)
    row = (
        db.query(StrengthRoutine)
        .filter(
            StrengthRoutine.id == routine_id,
            StrengthRoutine.athlete_id == current_user.id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Routine not found")
    row.is_archived = True
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "archived", "routine_id": str(routine_id)}


# ---------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------


@router.get("/goals", response_model=List[StrengthGoalResponse])
def list_goals(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[StrengthGoalResponse]:
    _require_strength_v1(current_user.id, db)
    rows = (
        db.query(StrengthGoal)
        .filter(
            StrengthGoal.athlete_id == current_user.id,
            StrengthGoal.is_active.is_(True),
        )
        .order_by(StrengthGoal.created_at.desc())
        .all()
    )
    return [StrengthGoalResponse.model_validate(r) for r in rows]


@router.post(
    "/goals",
    response_model=StrengthGoalResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_goal(
    payload: StrengthGoalCreate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StrengthGoalResponse:
    _require_strength_v1(current_user.id, db)
    row = StrengthGoal(
        id=uuid4(),
        athlete_id=current_user.id,
        goal_type=payload.goal_type,
        exercise_name=payload.exercise_name,
        target_value=payload.target_value,
        target_unit=payload.target_unit,
        target_date=payload.target_date,
        coupled_running_metric=payload.coupled_running_metric,
        notes=payload.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return StrengthGoalResponse.model_validate(row)


@router.patch("/goals/{goal_id}", response_model=StrengthGoalResponse)
def update_goal(
    goal_id: UUID,
    payload: StrengthGoalUpdate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StrengthGoalResponse:
    _require_strength_v1(current_user.id, db)
    row = (
        db.query(StrengthGoal)
        .filter(
            StrengthGoal.id == goal_id,
            StrengthGoal.athlete_id == current_user.id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Goal not found")

    delta = payload.model_dump(exclude_unset=True)
    for k, v in delta.items():
        setattr(row, k, v)
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return StrengthGoalResponse.model_validate(row)


@router.delete("/goals/{goal_id}", status_code=status.HTTP_200_OK)
def delete_goal(
    goal_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_strength_v1(current_user.id, db)
    row = (
        db.query(StrengthGoal)
        .filter(
            StrengthGoal.id == goal_id,
            StrengthGoal.athlete_id == current_user.id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Goal not found")
    db.delete(row)
    db.commit()
    return {"status": "deleted", "goal_id": str(goal_id)}
