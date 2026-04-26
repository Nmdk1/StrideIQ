"""
Tests for GPS-based timezone inference and the two-timezone model.

Two-timezone model:
- Athlete.timezone           = HOME timezone (stable, mode-based GPS inference)
- get_athlete_effective_timezone = CURRENT timezone (volatile, 72h travel window)

Key regression guarded here: the "NC trip" bug where a single run in an Eastern-
timezone city set home = America/New_York for a Mississippi athlete permanently
because the backfill ran the day after their return and grabbed the latest GPS.
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from services.timezone_utils import (
    infer_timezone_from_coordinates,
    infer_and_persist_athlete_timezone,
    get_athlete_effective_timezone,
    is_valid_iana_timezone,
)

_UTC = timezone.utc

# Real GPS coordinates used in tests
_MERIDIAN_MS = (32.36, -88.66)    # America/Chicago
_CHICAGO_IL  = (41.85, -87.65)    # America/Chicago
_CARY_NC     = (35.79, -78.89)    # America/New_York (the NC trip)
_LONDON_UK   = (51.51, -0.13)     # Europe/London


class TestInferTimezoneFromCoordinates:
    def test_chicago_coordinates(self):
        tz = infer_timezone_from_coordinates(lat=41.85, lng=-87.65)
        assert tz is not None
        assert str(tz) == "America/Chicago"

    def test_new_york_coordinates(self):
        tz = infer_timezone_from_coordinates(lat=40.71, lng=-74.01)
        assert tz is not None
        assert str(tz) == "America/New_York"

    def test_london_coordinates(self):
        tz = infer_timezone_from_coordinates(lat=51.51, lng=-0.13)
        assert tz is not None
        assert str(tz) in ("Europe/London",)

    def test_mississippi_coordinates(self):
        tz = infer_timezone_from_coordinates(lat=32.36, lng=-88.66)
        assert tz is not None
        assert str(tz) == "America/Chicago"

    def test_returns_zoninfo_type(self):
        tz = infer_timezone_from_coordinates(lat=37.77, lng=-122.42)
        assert isinstance(tz, ZoneInfo)

    def test_bad_coordinates_do_not_raise(self):
        result = infer_timezone_from_coordinates(lat=0.0, lng=0.0)
        assert result is None or isinstance(result, ZoneInfo)

    def test_timezonefinder_unavailable_returns_none(self):
        import services.timezone_utils as _tzu
        original = _tzu._tf_instance
        _tzu._tf_instance = None
        try:
            with patch.dict("sys.modules", {"timezonefinder": None}):
                result = infer_timezone_from_coordinates(lat=41.85, lng=-87.65)
                assert result is None
        finally:
            _tzu._tf_instance = original


def _make_activity(lat, lng, days_ago=1):
    act = MagicMock()
    act.id = uuid4()
    act.start_lat = lat
    act.start_lng = lng
    act.start_time = datetime.now(_UTC) - timedelta(days=days_ago)
    return act


def _make_db_for_inference(tz=None, activities=None):
    """Build a mock DB for infer_and_persist_athlete_timezone (uses .limit().all())."""
    athlete = MagicMock()
    athlete.id = uuid4()
    athlete.timezone = tz
    athlete.preferred_units = "imperial"
    athlete.preferred_units_set_explicitly = False

    acts = activities or []

    db = MagicMock()

    def _query_side(model):
        from models import Athlete, Activity as ActivityModel
        q = MagicMock()
        if model is Athlete:
            q.filter.return_value.first.return_value = athlete
        elif model is ActivityModel:
            # Mode-based: filter → order_by → limit → all
            q.filter.return_value.order_by.return_value.limit.return_value.all.return_value = acts
        return q

    db.query.side_effect = _query_side
    return db, athlete


class TestInferAndPersistAthleteTimezone:
    """Tests for mode-based home timezone inference."""

    def test_infers_chicago_from_all_home_activities(self):
        """20 runs in Mississippi/Illinois → America/Chicago."""
        acts = [_make_activity(*_MERIDIAN_MS, days_ago=i) for i in range(1, 21)]
        db, athlete = _make_db_for_inference(tz=None, activities=acts)
        result = infer_and_persist_athlete_timezone(db, athlete.id)
        assert result is not None
        assert str(result) == "America/Chicago"
        assert athlete.timezone == "America/Chicago"
        db.commit.assert_called()

    def test_one_nc_trip_does_not_poison_home_timezone(self):
        """
        NC trip regression: 18 Central + 2 Eastern runs.
        Before this fix: the most-recent-activity approach set home = Eastern.
        After: mode = Central (18/20 majority) → home stays Central.
        """
        home_acts = [_make_activity(*_MERIDIAN_MS, days_ago=i) for i in range(3, 21)]
        trip_acts = [_make_activity(*_CARY_NC, days_ago=1), _make_activity(*_CARY_NC, days_ago=2)]
        # Most recent first — NC trip is at the top
        acts = trip_acts + home_acts
        db, athlete = _make_db_for_inference(tz=None, activities=acts)

        result = infer_and_persist_athlete_timezone(db, athlete.id)

        assert result is not None
        assert str(result) == "America/Chicago", (
            "One NC trip (2/20 activities) must not override 18 Mississippi runs"
        )
        assert athlete.timezone == "America/Chicago"

    def test_majority_eastern_correctly_sets_eastern(self):
        """If the athlete genuinely runs mostly in the Eastern zone, set Eastern."""
        eastern_acts = [_make_activity(*_CARY_NC, days_ago=i) for i in range(1, 16)]
        central_acts = [_make_activity(*_MERIDIAN_MS, days_ago=i) for i in range(16, 21)]
        acts = eastern_acts + central_acts
        db, athlete = _make_db_for_inference(tz=None, activities=acts)

        result = infer_and_persist_athlete_timezone(db, athlete.id)

        assert result is not None
        assert str(result) == "America/New_York"

    def test_skips_athlete_with_valid_timezone(self):
        db, athlete = _make_db_for_inference(tz="Europe/London")
        result = infer_and_persist_athlete_timezone(db, athlete.id)
        assert result == ZoneInfo("Europe/London")
        db.commit.assert_not_called()

    def test_returns_none_when_no_gps_activities(self):
        db, athlete = _make_db_for_inference(tz=None, activities=[])
        result = infer_and_persist_athlete_timezone(db, athlete.id)
        assert result is None
        db.commit.assert_not_called()

    def test_returns_none_for_missing_athlete(self):
        db = MagicMock()
        q = MagicMock()
        q.filter.return_value.first.return_value = None
        db.query.return_value = q
        result = infer_and_persist_athlete_timezone(db, uuid4())
        assert result is None


def _make_db_for_effective(home_tz, recent_activity=None):
    """Build a mock DB for get_athlete_effective_timezone."""
    athlete = MagicMock()
    athlete.id = uuid4()
    athlete.timezone = home_tz

    db = MagicMock()

    def _query_side(model):
        from models import Athlete, Activity as ActivityModel
        q = MagicMock()
        if model is Athlete:
            q.filter.return_value.first.return_value = athlete
        elif model is ActivityModel:
            # Effective TZ: filter → order_by → first
            q.filter.return_value.order_by.return_value.first.return_value = recent_activity
        return q

    db.query.side_effect = _query_side
    return db, athlete


class TestGetAthleteEffectiveTimezone:
    """Tests for the travel-aware current timezone."""

    def test_returns_home_when_no_recent_activity(self):
        """No GPS activity in 72h → home timezone."""
        db, athlete = _make_db_for_effective("America/Chicago", recent_activity=None)
        result = get_athlete_effective_timezone(athlete.id, db)
        assert str(result) == "America/Chicago"

    def test_returns_home_when_recent_activity_at_home(self):
        """Recent activity in same timezone as home → home timezone."""
        recent = _make_activity(*_MERIDIAN_MS, days_ago=0)
        db, athlete = _make_db_for_effective("America/Chicago", recent_activity=recent)
        result = get_athlete_effective_timezone(athlete.id, db)
        assert str(result) == "America/Chicago"

    def test_returns_travel_tz_when_recently_ran_in_eastern(self):
        """
        Travel scenario: athlete ran in Eastern time zone (NC race) 12 hours ago.
        Briefing should show Eastern time, not Central home time.
        """
        recent = _make_activity(*_CARY_NC, days_ago=0)
        db, athlete = _make_db_for_effective("America/Chicago", recent_activity=recent)
        result = get_athlete_effective_timezone(athlete.id, db)
        assert str(result) == "America/New_York", (
            "Athlete who ran in Eastern 12h ago should see Eastern time in briefing"
        )

    def test_returns_home_after_return_run(self):
        """
        Return home: most recent GPS activity is back in Central (home run).
        Even if they ran in Eastern 5 days ago, today's home run takes precedence.
        """
        home_run = _make_activity(*_MERIDIAN_MS, days_ago=0)
        db, athlete = _make_db_for_effective("America/Chicago", recent_activity=home_run)
        result = get_athlete_effective_timezone(athlete.id, db)
        assert str(result) == "America/Chicago", (
            "After returning home and running, effective timezone must be home"
        )

    def test_respects_72h_travel_window(self):
        """
        Activity older than 72h in Eastern zone → no longer considered traveling.
        Falls back to home timezone.
        """
        old_eastern = _make_activity(*_CARY_NC, days_ago=4)
        # The mock returns this activity, but the query filters by start_time >= window_start.
        # Simulate window miss by returning None (what the real query would return).
        db, athlete = _make_db_for_effective("America/Chicago", recent_activity=None)
        result = get_athlete_effective_timezone(athlete.id, db)
        assert str(result) == "America/Chicago"

    def test_european_travel_from_us_home(self):
        """US athlete running in London → briefing shows Europe/London."""
        recent = _make_activity(*_LONDON_UK, days_ago=1)
        db, athlete = _make_db_for_effective("America/Chicago", recent_activity=recent)
        result = get_athlete_effective_timezone(athlete.id, db)
        assert str(result) == "Europe/London"

    def test_home_tz_null_falls_back_gracefully(self):
        """Athlete with no home timezone set → effective tz is UTC (fallback)."""
        recent = _make_activity(*_MERIDIAN_MS, days_ago=0)
        db, athlete = _make_db_for_effective(None, recent_activity=recent)
        # home_tz resolves to UTC fallback; recent activity is also Central
        # but home_tz comparison won't match → returns inferred GPS tz
        result = get_athlete_effective_timezone(athlete.id, db)
        assert result is not None  # Must not raise

    def test_does_not_mutate_athlete_timezone(self):
        """Effective timezone is read-only — must never write to athlete.timezone."""
        recent = _make_activity(*_CARY_NC, days_ago=0)
        db, athlete = _make_db_for_effective("America/Chicago", recent_activity=recent)
        _ = get_athlete_effective_timezone(athlete.id, db)
        db.commit.assert_not_called()
        # athlete.timezone must be unchanged
        assert athlete.timezone == "America/Chicago"
