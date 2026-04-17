"""Training block ORM model.

A training block is a multi-week period of consistent training, detected
from the activity stream by the block detection service. Blocks have a
phase label (base / build / peak / taper / race / recovery / off) and
weekly aggregate metrics — they are the primary unit for block-over-block
comparison and for surfacing periodization narratives.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class TrainingBlock(Base):
    """A detected training block — one row per (athlete, contiguous period)."""

    __tablename__ = "training_block"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(
        UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False
    )

    # ISO week of the first activity in the block (Monday of that week).
    start_date = Column(Date, nullable=False)
    # ISO week of the last activity in the block (Sunday of that week).
    end_date = Column(Date, nullable=False)
    weeks = Column(Integer, nullable=False)  # number of ISO weeks spanned

    # Detected phase. Free-form to allow downstream evolution; current
    # algorithm produces one of:
    #   'base' | 'build' | 'peak' | 'taper' | 'race' | 'recovery' | 'off'
    phase = Column(Text, nullable=False)

    # Aggregates — denormalized so the comparison endpoints don't need to
    # re-walk activities.
    total_distance_m = Column(Integer, nullable=False, default=0)
    total_duration_s = Column(Integer, nullable=False, default=0)
    run_count = Column(Integer, nullable=False, default=0)
    peak_week_distance_m = Column(Integer, nullable=False, default=0)
    longest_run_m = Column(Integer, nullable=True)

    # Composition: how many of each workout_type are in the block, plus
    # the top 3 by count for fast access. Quality metric is the % of runs
    # that were quality (interval/threshold/tempo/race-pace).
    workout_type_counts = Column(JSONB, nullable=False, default=dict)
    dominant_workout_types = Column(JSONB, nullable=False, default=list)
    quality_pct = Column(Integer, nullable=False, default=0)  # 0-100

    # If the block ended in or contained a race, store the activity name.
    goal_event_name = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    athlete = relationship("Athlete")

    __table_args__ = (
        Index("ix_training_block_athlete_start", "athlete_id", "start_date"),
        Index("ix_training_block_athlete_phase", "athlete_id", "phase"),
    )
