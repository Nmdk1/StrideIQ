"""
Tests for timezone_utils.py canonical helpers.

Covers:
- get_athlete_timezone: valid IANA, invalid string, None, empty, ORM object
- to_athlete_local_date: UTC rollover boundary
- athlete_local_today: with injected now_utc
- local_day_bounds_utc: correct UTC boundaries
- is_valid_iana_timezone
"""
import pytest
from datetime import datetime, timezone, date
from unittest.mock import MagicMock

from services.timezone_utils import (
    get_athlete_timezone,
    get_athlete_timezone_from_db,
    to_athlete_local_date,
    athlete_local_today,
    local_day_bounds_utc,
    is_valid_iana_timezone,
)

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

_UTC = timezone.utc


# ---------------------------------------------------------------------------
# get_athlete_timezone
# ---------------------------------------------------------------------------

class TestGetAthleteTimezone:
    def test_valid_iana_string(self):
        tz = get_athlete_timezone("America/Chicago")
        assert tz == ZoneInfo("America/Chicago")

    def test_valid_iana_from_orm_object(self):
        athlete = MagicMock()
        athlete.timezone = "Europe/London"
        tz = get_athlete_timezone(athlete)
        assert tz == ZoneInfo("Europe/London")

    def test_none_falls_back_to_utc(self):
        tz = get_athlete_timezone(None)
        assert tz == ZoneInfo("UTC")

    def test_empty_string_falls_back_to_utc(self):
        tz = get_athlete_timezone("")
        assert tz == ZoneInfo("UTC")

    def test_orm_with_none_timezone_falls_back_to_utc(self):
        athlete = MagicMock()
        athlete.timezone = None
        tz = get_athlete_timezone(athlete)
        assert tz == ZoneInfo("UTC")

    def test_orm_with_empty_timezone_falls_back_to_utc(self):
        athlete = MagicMock()
        athlete.timezone = ""
        tz = get_athlete_timezone(athlete)
        assert tz == ZoneInfo("UTC")

    def test_invalid_iana_string_falls_back_to_utc(self):
        tz = get_athlete_timezone("Not/ATimezone")
        assert tz == ZoneInfo("UTC")

    def test_garbage_string_falls_back_to_utc(self):
        tz = get_athlete_timezone("(GMT-05:00)")
        assert tz == ZoneInfo("UTC")

    def test_no_exception_on_invalid(self):
        # Must never raise
        result = get_athlete_timezone("Complete garbage 🗑️")
        assert result == ZoneInfo("UTC")


# ---------------------------------------------------------------------------
# to_athlete_local_date — the core UTC-rollover fix
# ---------------------------------------------------------------------------

class TestToAthleteLocalDate:
    """
    Root cause scenario: UTC is 2026-03-17 00:30 (past midnight).
    Athlete in America/Chicago is still on 2026-03-16 (18:30 local).
    Using date.today() on server would return 2026-03-17 (wrong).
    """

    def test_chicago_utc_rollover_returns_previous_local_date(self):
        # UTC 00:30 on 2026-03-17 = 2026-03-16 18:30 Chicago (UTC-6 in March = CST)
        dt_utc = datetime(2026, 3, 17, 0, 30, 0, tzinfo=_UTC)
        tz = ZoneInfo("America/Chicago")
        local = to_athlete_local_date(dt_utc, tz)
        assert local == date(2026, 3, 16), (
            f"Expected 2026-03-16 (Chicago local), got {local}. "
            "UTC rollover must not affect athlete-local date."
        )

    def test_utc_midnight_still_returns_utc_date(self):
        dt_utc = datetime(2026, 3, 17, 0, 0, 0, tzinfo=_UTC)
        local = to_athlete_local_date(dt_utc, ZoneInfo("UTC"))
        assert local == date(2026, 3, 17)

    def test_naive_datetime_treated_as_utc(self):
        dt_naive = datetime(2026, 3, 17, 0, 30, 0)  # no tzinfo
        tz = ZoneInfo("America/Chicago")
        local = to_athlete_local_date(dt_naive, tz)
        assert local == date(2026, 3, 16)

    def test_new_york_utc_rollover(self):
        # UTC 01:00 = previous day in Eastern (UTC-5 in March = EST)
        dt_utc = datetime(2026, 3, 17, 1, 0, 0, tzinfo=_UTC)
        tz = ZoneInfo("America/New_York")
        local = to_athlete_local_date(dt_utc, tz)
        assert local == date(2026, 3, 16)

    def test_utc_plus_timezone_advances_date(self):
        # UTC 23:00 on 2026-03-16 = 2026-03-17 in Tokyo (UTC+9)
        dt_utc = datetime(2026, 3, 16, 23, 0, 0, tzinfo=_UTC)
        tz = ZoneInfo("Asia/Tokyo")
        local = to_athlete_local_date(dt_utc, tz)
        assert local == date(2026, 3, 17)


# ---------------------------------------------------------------------------
# athlete_local_today
# ---------------------------------------------------------------------------

class TestAthleteLocalToday:
    """
    Freeze 'now' via now_utc param to ensure deterministic tests.
    """

    def test_chicago_today_before_midnight_utc(self):
        # UTC 2026-03-17 00:30 — Chicago is still on 2026-03-16
        now_utc = datetime(2026, 3, 17, 0, 30, 0, tzinfo=_UTC)
        tz = ZoneInfo("America/Chicago")
        today = athlete_local_today(tz, now_utc=now_utc)
        assert today == date(2026, 3, 16)

    def test_utc_athlete_midnight(self):
        now_utc = datetime(2026, 3, 17, 0, 0, 0, tzinfo=_UTC)
        today = athlete_local_today(ZoneInfo("UTC"), now_utc=now_utc)
        assert today == date(2026, 3, 17)

    def test_accepts_iana_string(self):
        now_utc = datetime(2026, 3, 17, 0, 30, 0, tzinfo=_UTC)
        today = athlete_local_today("America/Chicago", now_utc=now_utc)
        assert today == date(2026, 3, 16)

    def test_accepts_athlete_orm_object(self):
        now_utc = datetime(2026, 3, 17, 0, 30, 0, tzinfo=_UTC)
        athlete = MagicMock()
        athlete.timezone = "America/Chicago"
        today = athlete_local_today(athlete, now_utc=now_utc)
        assert today == date(2026, 3, 16)

    def test_none_timezone_falls_back_to_utc(self):
        now_utc = datetime(2026, 3, 17, 0, 30, 0, tzinfo=_UTC)
        athlete = MagicMock()
        athlete.timezone = None
        today = athlete_local_today(athlete, now_utc=now_utc)
        assert today == date(2026, 3, 17)


# ---------------------------------------------------------------------------
# local_day_bounds_utc
# ---------------------------------------------------------------------------

class TestLocalDayBoundsUtc:
    def test_chicago_cst_day_bounds(self):
        # March 2026: DST is active (CDT = UTC-5), so Chicago 2026-03-16 starts at 05:00 UTC
        tz = ZoneInfo("America/Chicago")
        start, end = local_day_bounds_utc(date(2026, 3, 16), tz)
        assert start == datetime(2026, 3, 16, 5, 0, 0, tzinfo=_UTC)
        assert end == datetime(2026, 3, 17, 5, 0, 0, tzinfo=_UTC)

    def test_utc_day_bounds(self):
        tz = ZoneInfo("UTC")
        start, end = local_day_bounds_utc(date(2026, 3, 16), tz)
        assert start == datetime(2026, 3, 16, 0, 0, 0, tzinfo=_UTC)
        assert end == datetime(2026, 3, 17, 0, 0, 0, tzinfo=_UTC)

    def test_bounds_are_tz_aware(self):
        tz = ZoneInfo("America/Los_Angeles")
        start, end = local_day_bounds_utc(date(2026, 3, 16), tz)
        assert start.tzinfo is not None
        assert end.tzinfo is not None

    def test_day_length_is_always_at_least_23_hours(self):
        # Handles DST transitions: day may be 23 or 25 hours
        tz = ZoneInfo("America/New_York")
        start, end = local_day_bounds_utc(date(2026, 3, 8), tz)  # DST spring-forward
        diff = (end - start).total_seconds() / 3600
        assert 22 <= diff <= 26, f"Unexpected day length {diff}h on DST day"


# ---------------------------------------------------------------------------
# is_valid_iana_timezone
# ---------------------------------------------------------------------------

class TestIsValidIanaTimezone:
    def test_valid_timezones(self):
        for tz in ["America/Chicago", "Europe/London", "Asia/Tokyo", "UTC"]:
            assert is_valid_iana_timezone(tz), f"{tz} should be valid"

    def test_invalid_timezones(self):
        for tz in ["(GMT-05:00)", "US/Eastern_Invalid", "", "   ", None]:
            assert not is_valid_iana_timezone(tz), f"{tz!r} should be invalid"  # type: ignore
