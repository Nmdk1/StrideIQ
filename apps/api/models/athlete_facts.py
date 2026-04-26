from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class AthleteFacts(Base):
    """Artifact 9 athlete truth ledger: one structured JSONB row per athlete."""

    __tablename__ = "athlete_facts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(
        UUID(as_uuid=True),
        ForeignKey("athlete.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    payload = Column(JSONB, nullable=False, default=dict)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    athlete = relationship("Athlete")

    __table_args__ = (
        UniqueConstraint("athlete_id", name="uq_athlete_facts_athlete_id"),
    )


class AthleteFactsAudit(Base):
    """Append-only audit trail for all ledger writes."""

    __tablename__ = "athlete_facts_audit"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(
        UUID(as_uuid=True),
        ForeignKey("athlete.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field = Column(Text, nullable=False)
    action = Column(Text, nullable=False)
    previous_value = Column(JSONB, nullable=True)
    new_value = Column(JSONB, nullable=True)
    confidence = Column(Text, nullable=True)
    source = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    asserted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    athlete = relationship("Athlete")

    __table_args__ = (
        Index("ix_athlete_facts_audit_athlete_field", "athlete_id", "field"),
        Index("ix_athlete_facts_audit_created_at", "created_at"),
    )
