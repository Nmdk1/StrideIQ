"""
Strava Activity Index Backfill Helpers

Purpose:
- Ensure we have Activity rows for Strava activities (by ID) so downstream systems
  (best-efforts extraction, splits, PBs, analytics) can link deterministically.

This uses Strava "activity summary" objects (from /athlete/activities) and does NOT
fetch per-activity details (cheap + rate-limit friendly).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List

from sqlalchemy.orm import Session

from models import Athlete, Activity
from services.activity_deduplication import match_activities

logger = logging.getLogger(__name__)


# --- Strava activity-type → canonical sport mapping ---
# Defined here (not in tasks/) so all Strava ingestion paths — the main sync task, the
# index-upsert helper, and any future ingest entrypoint — share one source of truth.
# Output sport codes mirror services/sync/garmin_adapter._ACCEPTED_SPORTS so cross-provider
# dedup and downstream analysis don't have to know which provider an activity came from.
#
# Strava is the BACKUP ingestion path: when Garmin is connected, dedup ensures Garmin wins
# on overlapping activities (see services.activity_deduplication). When Garmin isn't
# connected — or for activities predating the Garmin connection — Strava is the
# authoritative source, so it must capture the same breadth of sports Garmin does.
_STRAVA_SPORT_MAP: Dict[str, str] = {
    # Runs
    "run": "run",
    "trailrun": "run",
    "virtualrun": "run",
    # Cycling family
    "ride": "cycling",
    "virtualride": "cycling",
    "mountainbikeride": "cycling",
    "gravelride": "cycling",
    "ebikeride": "cycling",
    "emountainbikeride": "cycling",
    "velomobile": "cycling",
    "handcycle": "cycling",
    # Walking / hiking
    "walk": "walking",
    "hike": "hiking",
    # Strength / conditioning
    "weighttraining": "strength",
    "crossfit": "strength",
    # Mobility
    "yoga": "flexibility",
}


def strava_sport_from_type(activity_type: str | None) -> str | None:
    """
    Map a Strava `type` (or `sport_type`) string to our canonical sport code.

    Returns None for sports we do not currently ingest (swim, ski, kayak, etc.). Callers
    must skip those — keeping the schema honest about what we've actually wired up
    downstream analysis for. New sports get added here once their analysis paths exist.
    """
    if not activity_type:
        return None
    return _STRAVA_SPORT_MAP.get(str(activity_type).strip().lower())


@dataclass
class IndexUpsertResult:
    created: int
    already_present: int
    skipped_non_runs: int  # legacy field name; semantically counts unsupported sports

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
        # Accept the same breadth of sports as the main sync path. Strava `sport_type`
        # is more specific than `type` (introduced 2022), so prefer it when present.
        raw_type = a.get("sport_type") or a.get("type")
        mapped_sport = strava_sport_from_type(raw_type)
        if mapped_sport is None:
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

        cross_provider_match = _find_cross_provider_match(
            db, athlete.id, start_time, distance, a.get("average_heartrate"),
        )
        if cross_provider_match:
            logger.info(
                "Strava index dedup: skipping %s, matches existing %s",
                external_activity_id, cross_provider_match.id,
            )
            already += 1
            continue

        moving_time = a.get("moving_time")
        avg_speed = a.get("average_speed")
        name = a.get("name")
        elev = a.get("total_elevation_gain")

        latlng = a.get("start_latlng") or []
        act = Activity(
            athlete_id=athlete.id,
            start_time=start_time,
            provider="strava",
            external_activity_id=external_activity_id,
            sport=mapped_sport,
            source="strava",
            name=name,
            distance_m=int(round(distance)) if distance else None,
            duration_s=int(moving_time) if moving_time else None,
            average_speed=avg_speed,
            total_elevation_gain=elev,
            start_lat=latlng[0] if len(latlng) >= 2 else None,
            start_lng=latlng[1] if len(latlng) >= 2 else None,
        )
        db.add(act)
        try:
            from services.wellness_stamp import stamp_wellness
            tz_name = getattr(athlete, "timezone", None)
            stamp_wellness(act, db, athlete_timezone=tz_name)
        except Exception:
            pass
        created += 1

    return IndexUpsertResult(created=created, already_present=already, skipped_non_runs=skipped)


def _find_cross_provider_match(
    db: Session,
    athlete_id,
    start_time: datetime,
    distance_m,
    avg_hr,
):
    """
    Check if any existing activity from another provider matches this
    Strava activity by time/distance/HR.
    """
    from datetime import timedelta

    window = timedelta(hours=8)
    candidates = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.provider != "strava",
            Activity.start_time >= start_time - window,
            Activity.start_time <= start_time + window,
        )
        .all()
    )

    strava_dict = {
        "start_time": start_time,
        "distance_m": float(distance_m) if distance_m else None,
        "avg_hr": int(avg_hr) if avg_hr else None,
    }

    for candidate in candidates:
        candidate_dict = {
            "start_time": candidate.start_time,
            "distance_m": float(candidate.distance_m) if candidate.distance_m else None,
            "avg_hr": int(candidate.avg_hr) if candidate.avg_hr else None,
        }
        if match_activities(strava_dict, candidate_dict):
            return candidate

    return None

