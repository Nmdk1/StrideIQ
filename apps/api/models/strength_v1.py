"""Strength v1 ORM models (Phase A).

New tables introduced by ``strength_v1_002``:

- :class:`StrengthRoutine`     — athlete-saved patterns. Not system-curated.
- :class:`StrengthGoal`        — athlete-set goals. Not system-suggested.
- :class:`BodyAreaSymptomLog`  — niggles / aches / pains / injury, runner
                                  language, athlete-entered only.

See ``docs/specs/STRENGTH_V1_SCOPE.md`` §5.2-§5.4.

Design contract: nothing in this module ever writes content the athlete
did not enter. The system observes; it does not prescribe. There is no
``recommended_routines`` table, no system-seeded goal, no auto-classified
symptom severity. If a future migration adds one, the strength v1
narration purity test (see ``test_strength_narration_purity.py``,
shipped in phase H) will still hold these surfaces silent.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class StrengthRoutine(Base):
    """Athlete-saved exercise pattern for two-tap session repeats.

    ``items`` is a JSONB list of dicts shaped like::

        {
            "exercise_name": "BARBELL_DEADLIFT",
            "default_sets": 3,
            "default_reps": 5,
            "default_weight_kg": 102.0,
            "default_implement_type": "barbell",
        }

    Edits overwrite (no version table in v1; if we need an audit trail for
    routine edits later, add it as a sibling table). Soft-delete via
    ``is_archived = true``; rows are never physically deleted.
    """

    __tablename__ = "strength_routine"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(
        UUID(as_uuid=True),
        ForeignKey("athlete.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(Text, nullable=False)
    items = Column(JSONB, nullable=False, default=list)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    times_used = Column(Integer, nullable=False, default=0)
    is_archived = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    athlete = relationship("Athlete")


class StrengthGoal(Base):
    """Athlete-set strength or body-composition goal.

    ``goal_type`` enum (validated at the API layer, not the DB):

    - ``e1rm_target``                 — target estimated 1RM for an exercise
    - ``e1rm_maintain``               — keep e1RM at or above current
    - ``bodyweight_target``           — target bodyweight in kg or lbs
    - ``volume_target``               — weekly volume in kg-reps
    - ``strength_to_bodyweight_ratio``— e.g. deadlift = 2x bodyweight
    - ``freeform``                    — unstructured text goal

    ``coupled_running_metric`` is an optional human-readable note that pairs
    a strength goal with a running condition the athlete is tracking it
    against ("while bodyweight drops 30 lb"). It is a string, not a typed
    join; the engine does not consume it.
    """

    __tablename__ = "strength_goal"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(
        UUID(as_uuid=True),
        ForeignKey("athlete.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    goal_type = Column(Text, nullable=False)
    exercise_name = Column(Text, nullable=True)
    target_value = Column(Float, nullable=True)
    target_unit = Column(Text, nullable=True)
    target_date = Column(Date, nullable=True)
    coupled_running_metric = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    athlete = relationship("Athlete")


class BodyAreaSymptomLog(Base):
    """Niggle / ache / pain / injury entry, athlete-entered only.

    Severity tier is the runner-language ladder, not a clinical scale:

    - ``niggle``  — "I notice it"
    - ``ache``    — "it bothers me but I run through it"
    - ``pain``    — "it changes how I run"
    - ``injury``  — "I can't train through it"

    The system never auto-classifies severity, never diagnoses, and never
    recommends treatment. It only stores what the athlete reports and
    feeds counts into the correlation engine (see phase I).

    ``body_area`` is a coarse text enum (~25 values mirroring a PT body
    chart). Validated at the API layer.
    """

    __tablename__ = "body_area_symptom_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(
        UUID(as_uuid=True),
        ForeignKey("athlete.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    body_area = Column(Text, nullable=False)
    severity = Column(Text, nullable=False)
    started_at = Column(Date, nullable=False)
    resolved_at = Column(Date, nullable=True)
    triggered_by = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    athlete = relationship("Athlete")
