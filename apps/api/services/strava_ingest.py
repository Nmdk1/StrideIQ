"""
Strava Ingest Helpers

Goal:
- Deterministically ingest a specific Strava activity by ID (authoritative link).
- Store Activity row (upsert) and its best_efforts (BestEffort).
- Optionally mark as user-verified race (for PB labeling correctness).

This is used for "surgical fixes" and for production backstops when an activity is missing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from models import Athlete, Activity
from services.strava_service import get_activity_details
from services.best_effort_service import extract_best_efforts_from_activity, regenerate_personal_bests


@dataclass
class IngestResult:
    created_activity: bool
    activity_id: str
    stored_best_efforts: int
    pbs_created: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "created_activity": self.created_activity,
            "activity_id": self.activity_id,
            "stored_best_efforts": self.stored_best_efforts,
            "pbs_created": self.pbs_created,
        }


def ingest_strava_activity_by_id(
    athlete: Athlete,
    db: Session,
    strava_activity_id: int,
    mark_as_race: Optional[bool] = None,
) -> IngestResult:
    """
    Ingest a single Strava activity (by its Strava ID).

    This uses Strava's activity details response as the source of truth and ensures
    the activity is linked to best_efforts from that exact run.
    """
    details = get_activity_details(athlete, int(strava_activity_id))
    if not details:
        raise ValueError("Could not fetch Strava activity details")

    # Minimal fields needed for downstream linking + display
    start_time = datetime.fromisoformat(details["start_date"].replace("Z", "+00:00"))
    distance_m = details.get("distance")
    moving_time = details.get("moving_time")
    elapsed_time = details.get("elapsed_time")
    avg_speed = details.get("average_speed")
    name = details.get("name")

    act = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete.id,
            Activity.provider == "strava",
            Activity.external_activity_id == str(strava_activity_id),
        )
        .first()
    )

    created = False
    if not act:
        act = Activity(
            athlete_id=athlete.id,
            start_time=start_time,
            provider="strava",
            external_activity_id=str(strava_activity_id),
            sport="run",
            source="strava",
            name=name,
            distance_m=int(round(distance_m)) if distance_m else None,
            duration_s=int(moving_time or elapsed_time) if (moving_time or elapsed_time) else None,
            average_speed=avg_speed,
        )
        db.add(act)
        db.commit()
        db.refresh(act)
        created = True
    else:
        # Opportunistic field refresh for missing data (do not override user edits)
        if not act.name and name:
            act.name = name
        if not act.distance_m and distance_m:
            act.distance_m = int(round(distance_m))
        if not act.duration_s and (moving_time or elapsed_time):
            act.duration_s = int(moving_time or elapsed_time)
        if act.average_speed is None and avg_speed is not None:
            act.average_speed = avg_speed
        db.commit()

    if mark_as_race is True:
        act.user_verified_race = True
        act.is_race_candidate = True
        act.race_confidence = 1.0
        db.commit()
    elif mark_as_race is False:
        act.user_verified_race = False
        act.is_race_candidate = False
        db.commit()

    stored = extract_best_efforts_from_activity(details, act, athlete, db)
    db.commit()

    pb = regenerate_personal_bests(athlete, db)

    return IngestResult(
        created_activity=created,
        activity_id=str(act.id),
        stored_best_efforts=stored,
        pbs_created=int(pb.get("created", 0)),
    )

