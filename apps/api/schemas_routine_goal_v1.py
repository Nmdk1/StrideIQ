"""Pydantic schemas for routines + goals (Strength v1, phase E).

Routines:
  Athlete-saved exercise patterns. Items list is opaque to the engine —
  it exists only to make repeating a session a two-tap operation.
  The system never seeds a routine; we only store what the athlete saves.

Goals:
  Athlete-set strength or body-composition goals. The system never
  suggests a target. ``coupled_running_metric`` is a free-text note
  the athlete uses to remember why this matters.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from schemas_strength_v1 import ImplementType


GoalType = Literal[
    "e1rm_target",
    "e1rm_maintain",
    "bodyweight_target",
    "volume_target",
    "strength_to_bodyweight_ratio",
    "freeform",
]


# ---------------------------------------------------------------------
# Routines
# ---------------------------------------------------------------------


class RoutineItem(BaseModel):
    """One exercise inside a routine. Defaults are athlete-typed and
    used to pre-fill the SessionLogger when the routine is started."""

    exercise_name: str = Field(..., min_length=1, max_length=120)
    default_sets: Optional[int] = Field(default=None, ge=1, le=20)
    default_reps: Optional[int] = Field(default=None, ge=1, le=500)
    default_weight_kg: Optional[float] = Field(default=None, ge=0, le=1000)
    default_implement_type: Optional[ImplementType] = None


class StrengthRoutineCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    items: List[RoutineItem] = Field(default_factory=list, max_length=80)


class StrengthRoutineUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    items: Optional[List[RoutineItem]] = Field(default=None, max_length=80)


class StrengthRoutineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    items: List[dict]
    last_used_at: Optional[datetime] = None
    times_used: int
    is_archived: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------


class StrengthGoalCreate(BaseModel):
    goal_type: GoalType
    exercise_name: Optional[str] = Field(default=None, max_length=120)
    target_value: Optional[float] = Field(default=None, ge=0, le=10000)
    target_unit: Optional[str] = Field(default=None, max_length=24)
    target_date: Optional[date] = None
    coupled_running_metric: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=2000)


class StrengthGoalUpdate(BaseModel):
    goal_type: Optional[GoalType] = None
    exercise_name: Optional[str] = Field(default=None, max_length=120)
    target_value: Optional[float] = Field(default=None, ge=0, le=10000)
    target_unit: Optional[str] = Field(default=None, max_length=24)
    target_date: Optional[date] = None
    coupled_running_metric: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=2000)
    is_active: Optional[bool] = None


class StrengthGoalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    goal_type: str
    exercise_name: Optional[str] = None
    target_value: Optional[float] = None
    target_unit: Optional[str] = None
    target_date: Optional[date] = None
    coupled_running_metric: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
