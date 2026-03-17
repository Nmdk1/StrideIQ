"""
Canonical timezone utilities for athlete-local date calculations.

All athlete-facing date logic MUST use these helpers — never date.today()
or datetime.utcnow().date() for athlete-local context.

Root cause of the "yesterday" label bug:
  UTC rolls to next day (e.g. 00:30 UTC) while athlete is still on the
  previous calendar day (e.g. 18:30 Chicago). Using date.today() on the
  server returns the UTC date, labeling same-local-day runs as "yesterday".
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
      - None / empty string → falls back to UTC

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
