"""
Regression test for the "yesterday" labeling bug in get_recent_runs.

Root cause: coach_tools.py used a.start_time.date() (UTC date) and
_relative_date(...) with reference=date.today() (server UTC date).
At UTC rollover (e.g. 00:30 UTC), a run completed earlier that evening
(same local day) was labeled "(yesterday)" instead of "(today)".

Repro:
  - now_utc = 2026-03-17 00:30 UTC
  - athlete timezone = America/Chicago (CST = UTC-6)
  - run start_time = 2026-03-16 22:00 UTC = 2026-03-16 16:00 Chicago
  - athlete local "today" = 2026-03-16
  - run local date = 2026-03-16
  - Expected label: (today)
  - Bug label: (yesterday) — because date.today() returned 2026-03-17 UTC
"""
import pytest
from datetime import datetime, timezone, date, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from services.timezone_utils import athlete_local_today, to_athlete_local_date
from services.coach_tools import _relative_date

_UTC = timezone.utc


def _make_run(start_utc: datetime, athlete_id=None):
    """Build a minimal Activity mock."""
    a = MagicMock()
    a.id = uuid4()
    a.start_time = start_utc
    a.athlete_id = athlete_id or uuid4()
    a.sport = "run"
    a.distance_m = 8000.0
    a.duration_s = 2400
    a.avg_hr = 145
    a.max_hr = 165
    a.workout_type = "easy"
    a.intensity_score = 55.0
    a.total_elevation_gain = 50.0
    a.temperature_f = 65.0
    a.humidity_pct = 60.0
    a.weather_condition = "clear"
    a.shape_sentence = None
    a.name = "Evening Run"
    a.user_verified_race = False
    a.is_race_candidate = False
    return a


class TestCoachToolsTimezoneRelativeLabels:
    """
    Test that get_recent_runs uses athlete-local dates for relative labels.
    """

    # Freeze: UTC is 2026-03-17 00:30 (past midnight)
    # Chicago athlete is still on 2026-03-16 (18:30 local)
    NOW_UTC = datetime(2026, 3, 17, 0, 30, 0, tzinfo=_UTC)
    CHICAGO_TZ = ZoneInfo("America/Chicago")

    def test_same_local_day_run_labeled_today_not_yesterday(self):
        """
        Evening run (2026-03-16 22:00 UTC = 16:00 Chicago) must be labeled
        '(today)' when now_utc = 2026-03-17 00:30.
        """
        run_start_utc = datetime(2026, 3, 16, 22, 0, 0, tzinfo=_UTC)
        ath_tz = self.CHICAGO_TZ
        now_utc = self.NOW_UTC

        local_run_date = to_athlete_local_date(run_start_utc, ath_tz)
        local_today = athlete_local_today(ath_tz, now_utc=now_utc)

        label = _relative_date(local_run_date, local_today)

        assert local_run_date == date(2026, 3, 16), "Run local date should be 2026-03-16"
        assert local_today == date(2026, 3, 16), "Athlete local today should be 2026-03-16"
        assert label == "(today)", (
            f"Same-local-day run must be labeled '(today)', got '{label}'. "
            "This is the exact regression Adam hit."
        )

    def test_previous_local_day_run_labeled_yesterday(self):
        """
        A run from the previous local day must still be labeled '(yesterday)'.
        """
        run_start_utc = datetime(2026, 3, 15, 22, 0, 0, tzinfo=_UTC)  # 2026-03-15 16:00 Chicago
        ath_tz = self.CHICAGO_TZ
        now_utc = self.NOW_UTC

        local_run_date = to_athlete_local_date(run_start_utc, ath_tz)
        local_today = athlete_local_today(ath_tz, now_utc=now_utc)

        label = _relative_date(local_run_date, local_today)

        assert local_run_date == date(2026, 3, 15)
        assert label == "(yesterday)"

    def test_utc_date_biased_label_would_have_been_wrong(self):
        """
        Demonstrate the old bug: using UTC date would have returned 'yesterday'
        for a same-local-day run. This test documents the regression
        and confirms the fix produces a different (correct) result.
        """
        run_start_utc = datetime(2026, 3, 16, 22, 0, 0, tzinfo=_UTC)
        now_utc = self.NOW_UTC

        # Old (broken) behavior: use UTC dates
        utc_run_date = run_start_utc.date()  # 2026-03-16
        utc_today = now_utc.date()           # 2026-03-17
        old_label = _relative_date(utc_run_date, utc_today)

        # New (correct) behavior: use athlete-local dates
        ath_tz = self.CHICAGO_TZ
        local_run_date = to_athlete_local_date(run_start_utc, ath_tz)
        local_today = athlete_local_today(ath_tz, now_utc=now_utc)
        new_label = _relative_date(local_run_date, local_today)

        assert old_label == "(yesterday)", "Old approach would label it '(yesterday)'"
        assert new_label == "(today)", "New approach correctly labels it '(today)'"

    def test_get_recent_runs_uses_athlete_local_dates(self):
        """
        Integration: verify athlete-local timezone is used for date_str and
        _run_rel in the evidence list by injecting now via timezone_utils.
        """
        from services import coach_tools

        athlete_id = uuid4()
        run_start_utc = datetime(2026, 3, 16, 22, 0, 0, tzinfo=_UTC)
        now_utc = self.NOW_UTC  # 2026-03-17 00:30 UTC

        run = _make_run(run_start_utc, athlete_id)

        mock_db = MagicMock()
        mock_athlete = MagicMock()
        mock_athlete.preferred_units = "imperial"
        mock_athlete.timezone = "America/Chicago"

        def _side_effect(model):
            q = MagicMock()
            q.filter.return_value.first.return_value = mock_athlete
            q.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [run]
            q.filter.return_value.all.return_value = []
            return q

        mock_db.query.side_effect = _side_effect

        tz = ZoneInfo("America/Chicago")

        # Patch athlete_local_today in timezone_utils to inject now_utc
        with patch("services.timezone_utils.athlete_local_today",
                   return_value=athlete_local_today(tz, now_utc=now_utc)):
            result = coach_tools.get_recent_runs(mock_db, athlete_id, days=7)

        evidence = result.get("evidence", [])
        assert evidence, "Should have evidence for the run"
        run_ev = evidence[0]
        # date_str should be athlete-local date, not UTC date
        assert "2026-03-16" in run_ev["date"], (
            f"date should be athlete-local 2026-03-16, got: {run_ev['date']}"
        )
        assert "(today)" in run_ev["date"], (
            f"Label should be '(today)' for same-local-day run, got: {run_ev['date']}"
        )

    def test_no_exception_with_missing_timezone(self):
        """Athlete with no timezone must not raise — falls back to UTC."""
        from services import coach_tools

        athlete_id = uuid4()
        run_start_utc = datetime(2026, 3, 16, 22, 0, 0, tzinfo=_UTC)

        run = _make_run(run_start_utc, athlete_id)
        mock_db = MagicMock()
        mock_athlete = MagicMock()
        mock_athlete.preferred_units = "metric"
        mock_athlete.timezone = None

        def _side_effect(model):
            q = MagicMock()
            q.filter.return_value.first.return_value = mock_athlete
            q.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [run]
            q.filter.return_value.all.return_value = []
            return q

        mock_db.query.side_effect = _side_effect

        # Should not raise
        result = coach_tools.get_recent_runs(mock_db, athlete_id, days=7)
        assert "evidence" in result
