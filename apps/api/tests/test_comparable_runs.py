"""Phase 5 — comparable runs tier logic tests (pure-function, no DB).

The persistence + tier integration tests live in
``test_comparable_runs_persistence.py`` and skip when no Postgres
fixture is available.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from services.comparison.comparable_runs import (
    ANNIVERSARY_WINDOW_DAYS,
    DEFAULT_TRAILING_DAYS,
    DISTANCE_TOLERANCE,
    ELEVATION_TOLERANCE,
    HEAT_DEW_TOLERANCE_F,
    HEAT_TEMP_TOLERANCE_F,
    SAME_ROUTE_RECENT_LIMIT,
    SAME_TYPE_LIMIT,
    _avg_pace_s_per_km,
    _days_ago,
    _elevation_in_tolerance,
    _heat_in_tolerance,
)


@dataclass
class _A:
    """Lightweight stand-in for Activity for pure-function tests."""

    temperature_f: Optional[float] = None
    dew_point_f: Optional[float] = None
    total_elevation_gain: Optional[float] = None
    distance_m: Optional[int] = None
    duration_s: Optional[int] = None
    start_time: Optional[datetime] = None
    workout_type: Optional[str] = None
    avg_hr: Optional[int] = None
    name: Optional[str] = None
    route_id: Optional[uuid.UUID] = None
    id: uuid.UUID = uuid.uuid4()
    athlete_id: uuid.UUID = uuid.uuid4()
    sport: str = "run"


# ---------------------------------------------------------------------------
# Constants sanity (catch accidental edits)
# ---------------------------------------------------------------------------


def test_tolerances_are_sane():
    assert HEAT_TEMP_TOLERANCE_F == 5.0
    assert HEAT_DEW_TOLERANCE_F == 5.0
    assert ELEVATION_TOLERANCE == 0.20
    assert DISTANCE_TOLERANCE == 0.15
    assert DEFAULT_TRAILING_DAYS == 90
    assert ANNIVERSARY_WINDOW_DAYS == 30
    assert SAME_ROUTE_RECENT_LIMIT == 5
    assert SAME_TYPE_LIMIT == 5


# ---------------------------------------------------------------------------
# avg_pace
# ---------------------------------------------------------------------------


class TestAvgPace:
    def test_normal(self):
        # 10 km in 50 minutes → 5:00 / km = 300 s/km
        assert _avg_pace_s_per_km(10000, 3000) == 300.0

    def test_missing_returns_none(self):
        assert _avg_pace_s_per_km(None, 3000) is None
        assert _avg_pace_s_per_km(10000, None) is None
        assert _avg_pace_s_per_km(0, 3000) is None


# ---------------------------------------------------------------------------
# heat tolerance
# ---------------------------------------------------------------------------


class TestHeatTolerance:
    def test_both_missing_temp_returns_false(self):
        a = _A(temperature_f=None, dew_point_f=60)
        b = _A(temperature_f=None, dew_point_f=60)
        assert _heat_in_tolerance(a, b) is False

    def test_one_missing_dew_returns_false(self):
        a = _A(temperature_f=70, dew_point_f=None)
        b = _A(temperature_f=70, dew_point_f=60)
        assert _heat_in_tolerance(a, b) is False

    def test_within_tolerance(self):
        a = _A(temperature_f=72, dew_point_f=63)
        b = _A(temperature_f=70, dew_point_f=60)
        assert _heat_in_tolerance(a, b) is True

    def test_temp_outside_tolerance(self):
        a = _A(temperature_f=72, dew_point_f=63)
        b = _A(temperature_f=82, dew_point_f=63)
        assert _heat_in_tolerance(a, b) is False

    def test_dew_outside_tolerance(self):
        # Even matching temps, very different dew = different "feels like"
        a = _A(temperature_f=72, dew_point_f=50)
        b = _A(temperature_f=72, dew_point_f=70)
        assert _heat_in_tolerance(a, b) is False


# ---------------------------------------------------------------------------
# elevation tolerance
# ---------------------------------------------------------------------------


class TestElevationTolerance:
    def test_both_missing_returns_false(self):
        a = _A(total_elevation_gain=None)
        b = _A(total_elevation_gain=None)
        assert _elevation_in_tolerance(a, b) is False

    def test_one_missing_returns_false(self):
        a = _A(total_elevation_gain=200)
        b = _A(total_elevation_gain=None)
        assert _elevation_in_tolerance(a, b) is False

    def test_within_tolerance(self):
        a = _A(total_elevation_gain=200)
        b = _A(total_elevation_gain=220)
        assert _elevation_in_tolerance(a, b) is True

    def test_outside_tolerance(self):
        a = _A(total_elevation_gain=200)
        b = _A(total_elevation_gain=400)
        assert _elevation_in_tolerance(a, b) is False

    def test_both_zero_in_tolerance(self):
        a = _A(total_elevation_gain=0)
        b = _A(total_elevation_gain=0)
        assert _elevation_in_tolerance(a, b) is True


# ---------------------------------------------------------------------------
# days_ago
# ---------------------------------------------------------------------------


class TestDaysAgo:
    def test_simple(self):
        focus = datetime(2026, 4, 17, 8, 0, tzinfo=timezone.utc)
        prior = datetime(2026, 4, 10, 8, 0, tzinfo=timezone.utc)
        assert _days_ago(prior, focus) == 7

    def test_one_year(self):
        focus = datetime(2026, 4, 17, tzinfo=timezone.utc)
        prior = datetime(2025, 4, 17, tzinfo=timezone.utc)
        assert _days_ago(prior, focus) == 365

    def test_none_returns_none(self):
        assert _days_ago(None, datetime(2026, 4, 17, tzinfo=timezone.utc)) is None
        assert _days_ago(datetime(2026, 4, 17, tzinfo=timezone.utc), None) is None
