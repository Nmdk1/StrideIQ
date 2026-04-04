"""
Stamp pre-activity wellness data onto Activity records.

Looks up the matching GarminDay row for the activity's date and copies
sleep, resting HR, and both HRV values onto the Activity.  Called at
ingestion time (Strava, Garmin, manual) and during historical backfill.

Date resolution: uses the calendar_date of the activity's start_time
in the athlete's local timezone.  Falls back to UTC date if no timezone.
"""
import logging
from datetime import datetime, timezone as _tz
from typing import Optional

logger = logging.getLogger(__name__)


def stamp_wellness(activity, db, *, athlete_timezone: Optional[str] = None) -> bool:
    """
    Populate pre_sleep_h, pre_sleep_score, pre_resting_hr,
    pre_recovery_hrv, pre_overnight_hrv on an Activity from GarminDay.

    Returns True if at least one field was stamped.
    """
    from models import GarminDay

    start_time = activity.start_time
    if start_time is None:
        return False

    activity_date = _resolve_date(start_time, athlete_timezone)

    row = (
        db.query(GarminDay)
        .filter(
            GarminDay.athlete_id == activity.athlete_id,
            GarminDay.calendar_date == activity_date,
        )
        .first()
    )
    if row is None:
        return False

    stamped = False

    if row.sleep_total_s and activity.pre_sleep_h is None:
        activity.pre_sleep_h = round(row.sleep_total_s / 3600, 2)
        stamped = True
    if row.sleep_score and activity.pre_sleep_score is None:
        activity.pre_sleep_score = row.sleep_score
        stamped = True
    if row.resting_hr and activity.pre_resting_hr is None:
        activity.pre_resting_hr = row.resting_hr
        stamped = True
    if row.hrv_5min_high and activity.pre_recovery_hrv is None:
        activity.pre_recovery_hrv = row.hrv_5min_high
        stamped = True
    if row.hrv_overnight_avg and activity.pre_overnight_hrv is None:
        activity.pre_overnight_hrv = row.hrv_overnight_avg
        stamped = True

    return stamped


def backfill_wellness_for_athlete(athlete_id: str, db) -> dict:
    """
    Backfill wellness stamps on all existing activities for one athlete.
    Returns {"stamped": N, "skipped": N, "total": N}.
    """
    from models import Activity, Athlete

    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    tz_name = getattr(athlete, "timezone", None) if athlete else None

    activities = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.start_time.isnot(None),
            Activity.pre_recovery_hrv.is_(None),
        )
        .all()
    )

    stamped = 0
    skipped = 0
    for act in activities:
        if stamp_wellness(act, db, athlete_timezone=tz_name):
            stamped += 1
        else:
            skipped += 1

    if stamped > 0:
        db.commit()

    return {"stamped": stamped, "skipped": skipped, "total": len(activities)}


def _resolve_date(start_time: datetime, tz_name: Optional[str]):
    """Convert start_time to a calendar date in the athlete's timezone."""
    if tz_name:
        try:
            try:
                import zoneinfo
            except ImportError:
                import backports.zoneinfo as zoneinfo  # type: ignore
            tz = zoneinfo.ZoneInfo(tz_name)
            return start_time.astimezone(tz).date()
        except Exception:
            pass
    if start_time.tzinfo:
        return start_time.astimezone(_tz.utc).date()
    return start_time.date()
