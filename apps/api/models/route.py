"""Athlete route ORM model.

A `route` is a canonical group of activities the athlete has run on the
same physical course. It is constructed by the route fingerprinting
service from geohash@7 cells of the GPS track, joined by Jaccard
similarity. The athlete may optionally name a route (Phase 3 UX).

Each `Activity` carries `route_id` (nullable) when matched.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from core.database import Base


class AthleteRoute(Base):
    """Canonical route — group of activities on the same course."""

    __tablename__ = "athlete_route"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False)
    name = Column(Text, nullable=True)

    centroid_lat = Column(Float, nullable=True)
    centroid_lng = Column(Float, nullable=True)

    distance_p50_m = Column(Integer, nullable=True)
    distance_min_m = Column(Integer, nullable=True)
    distance_max_m = Column(Integer, nullable=True)

    geohash_set = Column(JSONB, nullable=False, default=list)

    run_count = Column(Integer, nullable=False, default=0)
    first_seen_at = Column(DateTime(timezone=True), nullable=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    athlete = relationship("Athlete")

    __table_args__ = (
        Index("ix_athlete_route_athlete_id", "athlete_id"),
        Index("ix_athlete_route_athlete_distance", "athlete_id", "distance_p50_m"),
    )
