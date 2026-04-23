"""
Canonical timezone utilities for athlete-local date calculations.

**Storage vs calendar**
- Activity `start_time` and DB timestamps are **UTC instants** (timestamptz).
- **Calendar-day semantics** (today, L30 windows, “runs this week”) MUST use the
  athlete’s **IANA timezone**, not the server clock and not “helpful” UTC midnight.

**Source of truth for `Athlete.timezone`**
- Prefer provider IANA strings (e.g. Strava) when valid.
- Otherwise infer from **GPS** (`infer_timezone_from_coordinates` /
  `infer_and_persist_athlete_timezone` from recent `start_lat`/`start_lng`).
- **UTC (`ZoneInfo("UTC")`) is only a last-resort fallback** when no zone can be
  resolved — never substitute server `date.today()` or UTC calendar boundaries
  for athlete-relative windows; that causes system-wide trust bugs (see Adam
  relative-date incident: `docs/BUILDER_INSTRUCTIONS_2026-03-17_ADAM_TIMEZONE_RELATIVE_DATE_FIX.md`).

All athlete-facing date logic MUST use these helpers — never bare `date.today()`
on the server for athlete-local context.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone, timedelta
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_UTC = timezone.utc

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # Python 3.9+
except ImportError:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # type: ignore

_FALLBACK_TZ = ZoneInfo("UTC")


def get_athlete_timezone(athlete_or_tz_str) -> ZoneInfo:
    """
    Resolve the ZoneInfo for an athlete or a raw timezone string.

    Accepts:
      - an Athlete ORM object (reads .timezone)
      - a plain string (IANA timezone name, e.g. "America/Chicago")
      - None / empty string → falls back to UTC (unknown zone only; callers should
        run `infer_and_persist_athlete_timezone` when GPS exists so athletes are
        not permanently pinned to UTC calendar).

    Never raises; returns UTC on any invalid/missing value.
    """
    if athlete_or_tz_str is None:
        return _FALLBACK_TZ

    # Accept raw string or ORM object with .timezone attribute
    if isinstance(athlete_or_tz_str, str):
        tz_str = athlete_or_tz_str.strip()
    else:
        tz_str = (getattr(athlete_or_tz_str, "timezone", None) or "").strip()

    if not tz_str:
        return _FALLBACK_TZ

    try:
        return ZoneInfo(tz_str)
    except (ZoneInfoNotFoundError, KeyError, Exception):
        logger.debug("Invalid IANA timezone %r — falling back to UTC", tz_str)
        return _FALLBACK_TZ


def get_athlete_timezone_from_db(db: Session, athlete_id: UUID) -> ZoneInfo:
    """
    Look up athlete timezone from DB.

    Prefer passing the already-loaded Athlete object to avoid an extra
    query; use this only when you have an athlete_id but not the object.
    """
    from models import Athlete  # local import to avoid circular deps
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    return get_athlete_timezone(athlete)


def to_athlete_local_date(dt_utc: datetime, tz: ZoneInfo) -> date:
    """
    Convert a UTC datetime to the athlete's local calendar date.

    dt_utc may be naive (assumed UTC) or tz-aware.
    """
    if dt_utc is None:
        return datetime.now(_UTC).astimezone(tz).date()
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=_UTC)
    return dt_utc.astimezone(tz).date()


def athlete_local_today(
    athlete_or_tz,
    now_utc: Optional[datetime] = None,
) -> date:
    """
    Return the athlete's local calendar date for 'now'.

    athlete_or_tz: Athlete ORM object, ZoneInfo, or IANA string.
    now_utc: override the current UTC time (useful for testing).
    """
    if isinstance(athlete_or_tz, ZoneInfo):
        tz = athlete_or_tz
    else:
        tz = get_athlete_timezone(athlete_or_tz)

    utc_now = now_utc if now_utc is not None else datetime.now(_UTC)
    if utc_now.tzinfo is None:
        utc_now = utc_now.replace(tzinfo=_UTC)

    return utc_now.astimezone(tz).date()


def local_day_bounds_utc(local_day: date, tz: ZoneInfo) -> Tuple[datetime, datetime]:
    """
    Return (start_utc, end_utc) for the given local calendar day.

    start_utc is inclusive (midnight local), end_utc is exclusive (next midnight local).
    Both returned as tz-aware UTC datetimes.

    Example:
        For America/Chicago on 2026-03-16:
        start_utc = 2026-03-16 06:00:00+00:00
        end_utc   = 2026-03-17 06:00:00+00:00  (or 05:00 if DST applies)
    """
    # Construct naive midnight in the local timezone, then localise
    local_midnight = datetime(local_day.year, local_day.month, local_day.day, 0, 0, 0)
    start_local = local_midnight.replace(tzinfo=tz)
    end_local = (local_midnight + timedelta(days=1)).replace(tzinfo=tz)

    start_utc = start_local.astimezone(_UTC)
    end_utc = end_local.astimezone(_UTC)

    return start_utc, end_utc


def is_valid_iana_timezone(tz_str: str) -> bool:
    """Return True iff tz_str is a valid IANA timezone name."""
    if not tz_str or not tz_str.strip():
        return False
    try:
        ZoneInfo(tz_str.strip())
        return True
    except (ZoneInfoNotFoundError, KeyError, Exception):
        return False


_tf_instance = None


def _get_timezone_finder():
    """Lazy singleton for TimezoneFinder (disk-load is expensive, lookup is fast)."""
    global _tf_instance
    if _tf_instance is None:
        try:
            from timezonefinder import TimezoneFinder
            _tf_instance = TimezoneFinder()
        except ImportError:
            return None
    return _tf_instance


def infer_timezone_from_coordinates(lat: float, lng: float) -> Optional[ZoneInfo]:
    """
    Reverse-geocode a lat/lng to an IANA timezone using timezonefinder.

    Returns ZoneInfo on success, None if no timezone found (e.g. open ocean).
    Never raises.
    """
    try:
        tf = _get_timezone_finder()
        if tf is None:
            return None
        tz_str = tf.timezone_at(lat=lat, lng=lng)
        if tz_str:
            return ZoneInfo(tz_str)
    except Exception:
        logger.debug("timezonefinder lookup failed for lat=%s lng=%s", lat, lng, exc_info=True)
    return None


def to_activity_local_date(activity, athlete_tz: ZoneInfo) -> date:
    """
    Convert an activity's UTC start_time to the local date where the run happened.

    Handles travel: if the activity has GPS coordinates, uses the timezone at
    those coordinates instead of the athlete's home timezone. Falls back to
    athlete_tz if GPS is absent or timezone lookup fails.
    """
    tz = athlete_tz
    lat = getattr(activity, "start_lat", None)
    lng = getattr(activity, "start_lng", None)
    if lat is not None and lng is not None:
        try:
            gps_tz = infer_timezone_from_coordinates(float(lat), float(lng))
            if gps_tz is not None:
                tz = gps_tz
        except (ValueError, TypeError):
            pass
    return to_athlete_local_date(activity.start_time, tz)


def infer_and_persist_athlete_timezone(db: Session, athlete_id: UUID) -> Optional[ZoneInfo]:
    """
    Infer an athlete's timezone from their most recent GPS activity and persist it.

    - Only writes if current athlete.timezone is NULL/empty or invalid.
    - Picks the most recent activity with valid start_lat/start_lng.
    - Returns the resolved ZoneInfo, or None if inference failed.

    Safe to call repeatedly — idempotent if timezone already valid.
    """
    from models import Athlete, Activity  # local import to avoid circular deps

    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        return None

    # Skip if already have a valid timezone
    if athlete.timezone and is_valid_iana_timezone(athlete.timezone):
        return ZoneInfo(athlete.timezone)

    # Find most recent activity with GPS coordinates
    activity = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.start_lat.isnot(None),
            Activity.start_lng.isnot(None),
        )
        .order_by(Activity.start_time.desc())
        .first()
    )

    if not activity or activity.start_lat is None or activity.start_lng is None:
        logger.debug("No GPS activity found for athlete %s — cannot infer timezone", athlete_id)
        return None

    tz = infer_timezone_from_coordinates(float(activity.start_lat), float(activity.start_lng))
    if tz is None:
        logger.debug(
            "Timezone inference returned no result for lat=%s lng=%s (athlete %s)",
            activity.start_lat, activity.start_lng, athlete_id,
        )
        return None

    athlete.timezone = str(tz)

    if not getattr(athlete, "preferred_units_set_explicitly", False):
        from services.units_default import derive_default_units
        derived = derive_default_units(str(tz))
        if derived != athlete.preferred_units:
            logger.info(
                "Timezone inference: deriving preferred_units=%s for athlete %s "
                "from timezone=%s (was %s)",
                derived, athlete.id, tz, athlete.preferred_units,
            )
            athlete.preferred_units = derived

    db.commit()
    logger.info(
        "Inferred and persisted timezone %s for athlete %s from activity %s",
        tz, athlete_id, activity.id,
    )
    return tz
