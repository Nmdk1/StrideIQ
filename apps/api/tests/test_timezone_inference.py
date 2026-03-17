"""
Tests for GPS-based timezone inference.
"""
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from services.timezone_utils import (
    infer_timezone_from_coordinates,
    infer_and_persist_athlete_timezone,
    is_valid_iana_timezone,
)


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
        # bellevignes: lat=30.47, lng=-90.33 — Louisiana/Mississippi area
        tz = infer_timezone_from_coordinates(lat=30.47, lng=-90.33)
        assert tz is not None
        assert str(tz) == "America/Chicago"

    def test_returns_zoninfo_type(self):
        tz = infer_timezone_from_coordinates(lat=37.77, lng=-122.42)
        assert isinstance(tz, ZoneInfo)

    def test_bad_coordinates_do_not_raise(self):
        # Open ocean — may return None
        result = infer_timezone_from_coordinates(lat=0.0, lng=0.0)
        # Should not raise; result may be None or Africa/Abidjan
        assert result is None or isinstance(result, ZoneInfo)

    def test_timezonefinder_unavailable_returns_none(self):
        with patch.dict("sys.modules", {"timezonefinder": None}):
            result = infer_timezone_from_coordinates(lat=41.85, lng=-87.65)
            assert result is None


class TestInferAndPersistAthleteTimezone:
    def _make_db(self, tz=None, lat=41.85, lng=-87.65):
        athlete = MagicMock()
        athlete.id = uuid4()
        athlete.email = "test@example.com"
        athlete.timezone = tz

        activity = MagicMock()
        activity.id = uuid4()
        activity.start_lat = lat
        activity.start_lng = lng
        activity.start_time = __import__("datetime").datetime(2026, 3, 1)

        db = MagicMock()

        def _query_side(model):
            from models import Athlete, Activity as ActivityModel
            q = MagicMock()
            if model is Athlete:
                q.filter.return_value.first.return_value = athlete
            elif model is ActivityModel:
                q.filter.return_value.order_by.return_value.first.return_value = activity
            return q

        db.query.side_effect = _query_side
        return db, athlete

    def test_infers_and_persists_chicago(self):
        db, athlete = self._make_db(tz=None, lat=41.85, lng=-87.65)
        result = infer_and_persist_athlete_timezone(db, athlete.id)
        assert result is not None
        assert str(result) == "America/Chicago"
        assert athlete.timezone == "America/Chicago"
        db.commit.assert_called()

    def test_skips_athlete_with_valid_timezone(self):
        db, athlete = self._make_db(tz="Europe/London")
        result = infer_and_persist_athlete_timezone(db, athlete.id)
        assert result == ZoneInfo("Europe/London")
        db.commit.assert_not_called()

    def test_returns_none_when_no_gps_activity(self):
        athlete = MagicMock()
        athlete.id = uuid4()
        athlete.timezone = None

        db = MagicMock()

        def _query_side(model):
            from models import Athlete, Activity as ActivityModel
            q = MagicMock()
            if model is Athlete:
                q.filter.return_value.first.return_value = athlete
            elif model is ActivityModel:
                q.filter.return_value.order_by.return_value.first.return_value = None
            return q

        db.query.side_effect = _query_side
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
