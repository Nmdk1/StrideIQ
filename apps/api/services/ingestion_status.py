"""
Ingestion Status Service

Purpose:
- Provide a cheap, deterministic view of ingestion completeness per athlete.
- Avoid "guessing" whether downstream metrics are wrong vs. ingestion incomplete.

This service intentionally does NOT call external providers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func

from models import Athlete, Activity, BestEffort


@dataclass
class BestEffortIngestionStatus:
    athlete_id: str
    provider: str
    total_activities: int
    # True processing coverage (details fetched + extraction attempted)
    activities_processed: int
    remaining_activities: int
    # How many activities actually produced BestEffort rows (PR-bearing activities)
    activities_with_efforts: int
    best_effort_rows: int
    last_provider_sync_at: Optional[str]

    @property
    def coverage_pct(self) -> float:
        if self.total_activities <= 0:
            return 0.0
        return round((self.activities_processed / self.total_activities) * 100.0, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "athlete_id": self.athlete_id,
            "provider": self.provider,
            "total_activities": self.total_activities,
            "activities_processed": self.activities_processed,
            "remaining_activities": self.remaining_activities,
            "coverage_pct": self.coverage_pct,
            "best_effort_rows": self.best_effort_rows,
            "activities_with_efforts": self.activities_with_efforts,
            "last_provider_sync_at": self.last_provider_sync_at,
        }


def get_best_effort_ingestion_status(athlete_id: UUID, db: Session, provider: str = "strava") -> BestEffortIngestionStatus:
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        raise ValueError("Athlete not found")

    total = (
        db.query(func.count(Activity.id))
        .filter(
            Activity.athlete_id == athlete.id,
            Activity.provider == provider,
            Activity.external_activity_id.isnot(None),
        )
        .scalar()
        or 0
    )

    activities_with_efforts = (
        db.query(func.count(func.distinct(BestEffort.activity_id)))
        .join(Activity, Activity.id == BestEffort.activity_id)
        .filter(
            BestEffort.athlete_id == athlete.id,
            Activity.provider == provider,
            Activity.external_activity_id.isnot(None),
        )
        .scalar()
        or 0
    )

    best_effort_rows = (
        db.query(func.count(BestEffort.id))
        .filter(BestEffort.athlete_id == athlete.id)
        .scalar()
        or 0
    )

    activities_processed = (
        db.query(func.count(Activity.id))
        .filter(
            Activity.athlete_id == athlete.id,
            Activity.provider == provider,
            Activity.external_activity_id.isnot(None),
            Activity.best_efforts_extracted_at.isnot(None),
        )
        .scalar()
        or 0
    )

    remaining = max(0, total - activities_processed)

    last_provider_sync_at = None
    if provider == "strava" and getattr(athlete, "last_strava_sync", None):
        last_provider_sync_at = athlete.last_strava_sync.isoformat()

    return BestEffortIngestionStatus(
        athlete_id=str(athlete.id),
        provider=provider,
        total_activities=int(total),
        activities_processed=int(activities_processed),
        activities_with_efforts=int(activities_with_efforts),
        remaining_activities=int(remaining),
        best_effort_rows=int(best_effort_rows),
        last_provider_sync_at=last_provider_sync_at,
    )

