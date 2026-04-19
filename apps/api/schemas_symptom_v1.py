"""Pydantic schemas for the body-area symptom log (Strength v1, phase D).

Lives outside ``schemas.py`` so the surface can be removed in one file at
rollback. Imported by ``routers/symptoms_v1.py`` and shared with the
narration purity test (the canonical body-area + severity vocabularies
double as the "never invent a tissue diagnosis" gate).

The vocabularies are intentionally coarse:

- Body areas mirror a runner-friendly PT chart. We never go more
  granular than "left calf"; the system is not a diagnostic tool.
- Severity tiers are runner language, not a clinical scale (see
  STRENGTH_V1_SCOPE.md §6.5).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# Severity ladder. Ordered ascending. The order matters for the
# correlation engine inputs (phase I); do not reorder without bumping
# the input registry.
SymptomSeverity = Literal["niggle", "ache", "pain", "injury"]


# Body areas the athlete can choose from. ~25 entries, intentionally
# coarse. New entries land here, never silently in the database via
# free text. If an athlete needs a region we don't model, "other_*"
# entries exist as the escape valve.
BodyArea = Literal[
    "left_foot",
    "right_foot",
    "left_ankle",
    "right_ankle",
    "left_calf",
    "right_calf",
    "left_shin",
    "right_shin",
    "left_knee",
    "right_knee",
    "left_quad",
    "right_quad",
    "left_hamstring",
    "right_hamstring",
    "left_hip",
    "right_hip",
    "left_glute",
    "right_glute",
    "lower_back",
    "upper_back",
    "left_shoulder",
    "right_shoulder",
    "neck",
    "core_abdominals",
    "other",
]


class SymptomLogCreate(BaseModel):
    body_area: BodyArea
    severity: SymptomSeverity
    started_at: date
    resolved_at: Optional[date] = None
    triggered_by: Optional[str] = Field(
        default=None,
        max_length=200,
        description=(
            "Free-text athlete note: 'after long run', 'after deadlifts', "
            "'sleeping wrong'. Never auto-classified."
        ),
    )
    notes: Optional[str] = Field(default=None, max_length=2000)


class SymptomLogUpdate(BaseModel):
    """Partial update. ``severity`` and ``body_area`` are intentionally
    not editable here; if the athlete got it wrong, they archive +
    re-log so the audit trail stays clean."""

    resolved_at: Optional[date] = None
    triggered_by: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=2000)


class SymptomLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    body_area: str
    severity: str
    started_at: date
    resolved_at: Optional[date] = None
    triggered_by: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SymptomLogListResponse(BaseModel):
    """Two slices: anything still active (no resolved_at), and the
    most recent ``recent_limit`` historic entries. The frontend
    renders them in two stacked sections."""

    active: List[SymptomLogResponse]
    history: List[SymptomLogResponse]
