"""
HR backfill service: enrich Strava activities with HR data from matching Garmin activities.

When a Garmin activity is ingested and a Strava activity exists for the same
run without HR data, copy HR fields to the best-matching Strava activity.
"""
from datetime import timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from models import Activity


def backfill_hr_from_garmin(db: Session, athlete_id: UUID, garmin_activity: Activity):
    """
    If a Strava activity exists for the same run without HR,
    backfill HR from the matching Garmin activity.

    Match criteria: same athlete, start_time within 30 minutes,
    distance within 10%.
    If multiple candidates match, choose nearest start_time.

    Returns the enriched Strava activity ID, or None if no match found.
    """
    if garmin_activity.avg_hr is None:
        return None

    window = timedelta(minutes=30)
    start = garmin_activity.start_time - window
    end = garmin_activity.start_time + window

    strava_candidates = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.provider == "strava",
            Activity.avg_hr.is_(None),
            Activity.start_time >= start,
            Activity.start_time <= end,
        )
        .all()
    )

    if not strava_candidates:
        return None

    matched = []
    for c in strava_candidates:
        if c.distance_m and garmin_activity.distance_m:
            ratio = c.distance_m / garmin_activity.distance_m
            if ratio < 0.9 or ratio > 1.1:
                continue
        matched.append(c)

    if not matched:
        return None

    strava_match = min(
        matched,
        key=lambda c: abs((c.start_time - garmin_activity.start_time).total_seconds()),
    )

    strava_match.avg_hr = garmin_activity.avg_hr
    strava_match.max_hr = garmin_activity.max_hr
    db.flush()

    return strava_match.id
