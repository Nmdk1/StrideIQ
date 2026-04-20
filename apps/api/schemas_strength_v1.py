"""Pydantic schemas for the Strength v1 manual logging API.

Lives outside ``schemas.py`` so the entire surface can be deleted in one
file at rollback. Imported by ``routers/strength_v1.py``.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Enum literals — the canonical tuples are exported from
# services.strength_v1_enums for non-API code (taxonomy validators,
# Garmin reconcile job, narration suppression) to share.
ImplementType = Literal[
    "barbell",
    "dumbbell_each",
    "dumbbell_total",
    "kettlebell_each",
    "kettlebell_total",
    "plate_per_side",
    "machine",
    "cable",
    "bodyweight",
    "band",
    "other",
]

SetModifier = Literal[
    "straight",
    "warmup",
    "drop",
    "failure",
    "amrap",
    "pyramid_up",
    "pyramid_down",
    "tempo",
    "paused",
]

SetSource = Literal["garmin", "manual", "voice", "garmin_then_manual_edit"]


# ---------------------------------------------------------------------
# Set-level shapes
# ---------------------------------------------------------------------


class StrengthSetCreate(BaseModel):
    """One set as the athlete enters it.

    Only ``exercise_name`` is required. The 90-second logging contract
    in the scope (§6.1) depends on every other field being optional.
    """

    exercise_name: str = Field(..., min_length=1, max_length=120)
    reps: Optional[int] = Field(default=None, ge=0, le=500)
    weight_kg: Optional[float] = Field(default=None, ge=0, le=1000)
    duration_s: Optional[float] = Field(default=None, ge=0, le=7200)
    rpe: Optional[float] = Field(default=None, ge=1, le=10)
    implement_type: Optional[ImplementType] = None
    set_modifier: Optional[SetModifier] = None
    tempo: Optional[str] = Field(default=None, max_length=32)
    notes: Optional[str] = Field(default=None, max_length=1000)
    set_type: Literal["active", "rest"] = "active"

    @field_validator("exercise_name")
    @classmethod
    def _normalise_exercise_name(cls, v: str) -> str:
        # Taxonomy convention: UPPER_SNAKE_CASE.
        return v.strip().replace(" ", "_").upper()


class StrengthSetUpdate(BaseModel):
    """Fields editable on an existing set. Edits apply via supersede."""

    reps: Optional[int] = Field(default=None, ge=0, le=500)
    weight_kg: Optional[float] = Field(default=None, ge=0, le=1000)
    duration_s: Optional[float] = Field(default=None, ge=0, le=7200)
    rpe: Optional[float] = Field(default=None, ge=1, le=10)
    implement_type: Optional[ImplementType] = None
    set_modifier: Optional[SetModifier] = None
    tempo: Optional[str] = Field(default=None, max_length=32)
    notes: Optional[str] = Field(default=None, max_length=1000)


class StrengthSetResponse(BaseModel):
    """One set as it reads from the database (active row, not superseded)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    set_order: int
    exercise_name: str = Field(alias="exercise_name_raw")
    exercise_category: str
    movement_pattern: str
    muscle_group: Optional[str] = None
    is_unilateral: bool
    set_type: str
    reps: Optional[int] = None
    weight_kg: Optional[float] = None
    duration_s: Optional[float] = None
    estimated_1rm_kg: Optional[float] = None
    rpe: Optional[float] = None
    implement_type: Optional[str] = None
    set_modifier: Optional[str] = None
    tempo: Optional[str] = None
    notes: Optional[str] = None
    source: str
    manually_augmented: bool
    superseded_by_id: Optional[UUID] = None
    superseded_at: Optional[datetime] = None
    created_at: datetime


# ---------------------------------------------------------------------
# Session-level shapes
# ---------------------------------------------------------------------


class StrengthSessionCreate(BaseModel):
    """One full strength session being logged manually."""

    start_time: Optional[datetime] = Field(
        default=None,
        description="Session start. Defaults to server-side now() if omitted.",
    )
    duration_s: Optional[int] = Field(default=None, ge=0, le=24 * 3600)
    name: Optional[str] = Field(default=None, max_length=200)
    sets: List[StrengthSetCreate] = Field(..., min_length=1, max_length=400)
    routine_id: Optional[UUID] = Field(
        default=None,
        description="If started from a saved routine, that routine's id.",
    )


class StrengthSessionResponse(BaseModel):
    """A logged session as it reads back."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    athlete_id: UUID
    start_time: datetime
    duration_s: Optional[int] = None
    name: Optional[str] = None
    sport: str
    source: str
    sets: List[StrengthSetResponse]
    set_count: int
    total_volume_kg: Optional[float] = None
    movement_patterns: List[str]


class StrengthSessionListItem(BaseModel):
    """Compact list-row for the recent-sessions surface."""

    id: UUID
    start_time: datetime
    duration_s: Optional[int] = None
    name: Optional[str] = None
    set_count: int
    total_volume_kg: Optional[float] = None
    movement_patterns: List[str]


# ---------------------------------------------------------------------
# Exercise picker
# ---------------------------------------------------------------------


class ExercisePickerEntry(BaseModel):
    name: str
    movement_pattern: str
    muscle_group: Optional[str] = None
    is_unilateral: bool


class ExercisePickerResponse(BaseModel):
    query: Optional[str] = None
    results: List[ExercisePickerEntry]
    recent: List[ExercisePickerEntry]
