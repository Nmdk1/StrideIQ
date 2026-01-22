"""
Strava Activity Index Backfill Helpers

Purpose:
- Ensure we have Activity rows for Strava activities (by ID) so downstream systems
  (best-efforts extraction, splits, PBs, analytics) can link deterministically.

This uses Strava "activity summary" objects (from /athlete/activities) and does NOT
fetch per-activity details (cheap + rate-limit friendly).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List

from sqlalchemy.orm import Session

from models import Athlete, Activity


@dataclass
class IndexUpsertResult:
    created: int
    already_present: int
    skipped_non_runs: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "created": self.created,
            "already_present": self.already_present,
            "skipped_non_runs": self.skipped_non_runs,
        }


def upsert_strava_activity_summaries(athlete: Athlete, db: Session, summaries: List[Dict[str, Any]]) -> IndexUpsertResult:
    created = 0
    already = 0
    skipped = 0

    for a in summaries or []:
        activity_type = (a.get("type") or "").lower()
        if activity_type != "run":
            skipped += 1
            continue

        strava_activity_id = a.get("id")
        if not strava_activity_id:
            continue

        external_activity_id = str(strava_activity_id)

        existing = (
            db.query(Activity)
            .filter(Activity.provider == "strava", Activity.external_activity_id == external_activity_id)
            .first()
        )
        if existing:
            already += 1
            continue

        start_time_str = a.get("start_date")
        if not start_time_str:
            continue
        start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))

        distance = a.get("distance")
        moving_time = a.get("moving_time")
        avg_speed = a.get("average_speed")
        name = a.get("name")
        elev = a.get("total_elevation_gain")

        act = Activity(
            athlete_id=athlete.id,
            start_time=start_time,
            provider="strava",
            external_activity_id=external_activity_id,
            sport="run",
            source="strava",
            name=name,
            distance_m=int(round(distance)) if distance else None,
            duration_s=int(moving_time) if moving_time else None,
            average_speed=avg_speed,
            total_elevation_gain=elev,
        )
        db.add(act)
        created += 1

    return IndexUpsertResult(created=created, already_present=already, skipped_non_runs=skipped)

