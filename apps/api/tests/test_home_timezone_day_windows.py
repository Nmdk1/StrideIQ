"""
Regression tests for athlete-local day windowing in the home endpoint.

Root cause: home.py used date.today() (server UTC) for yesterday/today
windows. At UTC rollover, same-local-day activities fell outside the
"yesterday" window or into "today" when they shouldn't.

Tests verify:
1. yesterday window aligns to athlete-local yesterday (UTC boundary correct).
2. today window aligns to athlete-local today.
3. A run at 22:00 UTC (= 16:00 Chicago, same local day) does NOT appear
   in the "yesterday" insight window when athlete local day = 2026-03-16.
"""
import pytest
from datetime import datetime, timezone, date, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from services.timezone_utils import local_day_bounds_utc, athlete_local_today

_UTC = timezone.utc


class TestHomeTodayYesterdayWindows:
    """
    Scenario:
      now_utc = 2026-03-17 00:30 UTC
      athlete tz = America/Chicago (CST = UTC-6)
      athlete local today = 2026-03-16
      athlete local yesterday = 2026-03-15
    """
    NOW_UTC = datetime(2026, 3, 17, 0, 30, 0, tzinfo=_UTC)
    TZ = ZoneInfo("America/Chicago")

    def test_athlete_local_today_is_march_16(self):
        today = athlete_local_today(self.TZ, now_utc=self.NOW_UTC)
        assert today == date(2026, 3, 16)

    def test_athlete_local_yesterday_is_march_15(self):
        today = athlete_local_today(self.TZ, now_utc=self.NOW_UTC)
        yesterday = today - timedelta(days=1)
        assert yesterday == date(2026, 3, 15)

    def test_yesterday_utc_window_is_correct(self):
        today = athlete_local_today(self.TZ, now_utc=self.NOW_UTC)
        yesterday = today - timedelta(days=1)
        start_utc, end_utc = local_day_bounds_utc(yesterday, self.TZ)
        # March 2026: DST active (CDT = UTC-5)
        # Chicago 2026-03-15 starts at 05:00 UTC
        assert start_utc == datetime(2026, 3, 15, 5, 0, 0, tzinfo=_UTC)
        assert end_utc == datetime(2026, 3, 16, 5, 0, 0, tzinfo=_UTC)

    def test_today_utc_window_is_correct(self):
        today = athlete_local_today(self.TZ, now_utc=self.NOW_UTC)
        start_utc, end_utc = local_day_bounds_utc(today, self.TZ)
        # March 2026: DST active (CDT = UTC-5)
        # Chicago 2026-03-16 starts at 05:00 UTC
        assert start_utc == datetime(2026, 3, 16, 5, 0, 0, tzinfo=_UTC)
        assert end_utc == datetime(2026, 3, 17, 5, 0, 0, tzinfo=_UTC)

    def test_same_local_day_run_is_NOT_in_yesterday_window(self):
        """
        A run at 22:00 UTC on 2026-03-16 = 16:00 Chicago on 2026-03-16.
        It must NOT fall in the yesterday window (2026-03-15).
        """
        run_utc = datetime(2026, 3, 16, 22, 0, 0, tzinfo=_UTC)
        today = athlete_local_today(self.TZ, now_utc=self.NOW_UTC)
        yesterday = today - timedelta(days=1)
        yest_start, yest_end = local_day_bounds_utc(yesterday, self.TZ)

        in_yesterday_window = yest_start <= run_utc < yest_end
        assert not in_yesterday_window, (
            f"Run at {run_utc} UTC (= 2026-03-16 16:00 Chicago) must NOT be "
            f"in yesterday window [{yest_start}, {yest_end}). "
            "This would trigger the 'yesterday' label bug."
        )

    def test_same_local_day_run_IS_in_today_window(self):
        """
        Same run (22:00 UTC = 16:00 Chicago, 2026-03-16) must be in the
        today window.
        """
        run_utc = datetime(2026, 3, 16, 22, 0, 0, tzinfo=_UTC)
        today = athlete_local_today(self.TZ, now_utc=self.NOW_UTC)
        today_start, today_end = local_day_bounds_utc(today, self.TZ)

        in_today_window = today_start <= run_utc < today_end
        assert in_today_window, (
            f"Run at {run_utc} UTC (= 2026-03-16 16:00 Chicago) must be "
            f"in today window [{today_start}, {today_end})."
        )

    def test_actual_yesterday_run_IS_in_yesterday_window(self):
        """
        A run actually on 2026-03-15 (local) must be in yesterday window.
        """
        # 2026-03-15 20:00 UTC = 2026-03-15 14:00 Chicago
        run_utc = datetime(2026, 3, 15, 20, 0, 0, tzinfo=_UTC)
        today = athlete_local_today(self.TZ, now_utc=self.NOW_UTC)
        yesterday = today - timedelta(days=1)
        yest_start, yest_end = local_day_bounds_utc(yesterday, self.TZ)

        in_yesterday_window = yest_start <= run_utc < yest_end
        assert in_yesterday_window, (
            f"Run at {run_utc} UTC (= 2026-03-15 14:00 Chicago) must be "
            f"in yesterday window [{yest_start}, {yest_end})."
        )

    def test_utc_bias_would_have_been_wrong(self):
        """
        Document the old bug: the server UTC yesterday window (2026-03-16 00:00–2026-03-17 00:00)
        would have caught the same-local-day run at 22:00 UTC.
        The new athlete-local yesterday window does not.
        """
        run_utc = datetime(2026, 3, 16, 22, 0, 0, tzinfo=_UTC)

        # Old broken window (UTC-biased)
        utc_today = self.NOW_UTC.date()          # 2026-03-17
        utc_yesterday = utc_today - timedelta(days=1)  # 2026-03-16
        old_yest_start = datetime(utc_yesterday.year, utc_yesterday.month, utc_yesterday.day, tzinfo=_UTC)
        old_yest_end = datetime(utc_today.year, utc_today.month, utc_today.day, tzinfo=_UTC)
        in_old_window = old_yest_start <= run_utc < old_yest_end

        # New correct window (athlete-local)
        today = athlete_local_today(self.TZ, now_utc=self.NOW_UTC)
        yesterday = today - timedelta(days=1)
        new_yest_start, new_yest_end = local_day_bounds_utc(yesterday, self.TZ)
        in_new_window = new_yest_start <= run_utc < new_yest_end

        assert in_old_window, "Old UTC-biased window incorrectly captures same-local-day run"
        assert not in_new_window, "New athlete-local window correctly excludes same-local-day run"


class TestHomeDayWindowsUTCPlus:
    """Verify windows also work correctly for UTC+ timezones."""

    def test_tokyo_run_at_utc_2300_is_next_local_day(self):
        """
        23:00 UTC on 2026-03-16 = 08:00 Tokyo on 2026-03-17.
        Tokyo today window for 2026-03-17 must include this run.
        """
        run_utc = datetime(2026, 3, 16, 23, 0, 0, tzinfo=_UTC)
        now_utc = datetime(2026, 3, 17, 1, 0, 0, tzinfo=_UTC)  # 10:00 Tokyo
        tz = ZoneInfo("Asia/Tokyo")

        today = athlete_local_today(tz, now_utc=now_utc)
        assert today == date(2026, 3, 17)

        today_start, today_end = local_day_bounds_utc(today, tz)
        in_window = today_start <= run_utc < today_end
        assert in_window, f"Tokyo 08:00 run should be in today window [{today_start}, {today_end})"

    def test_missing_timezone_falls_back_to_utc_windows(self):
        """No timezone = UTC windows, no exception."""
        from unittest.mock import MagicMock
        from services.timezone_utils import get_athlete_timezone

        athlete = MagicMock()
        athlete.timezone = None
        tz = get_athlete_timezone(athlete)

        today = athlete_local_today(tz, now_utc=datetime(2026, 3, 17, 0, 30, 0, tzinfo=_UTC))
        assert today == date(2026, 3, 17)  # UTC date, no crash

        start, end = local_day_bounds_utc(today, tz)
        assert start < end
