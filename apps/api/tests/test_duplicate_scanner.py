"""Tests for retroactive duplicate scanner (Racing Fingerprint Pre-Work P1)."""

import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from services.duplicate_scanner import (
    _choose_primary,
    _merge_fields,
    scan_and_mark_duplicates,
)


def _make_activity(**kwargs):
    """Build a mock Activity with defaults."""
    defaults = {
        "id": uuid.uuid4(),
        "athlete_id": uuid.uuid4(),
        "provider": "strava",
        "external_activity_id": str(uuid.uuid4()),
        "start_time": datetime(2025, 6, 15, 8, 0, 0),
        "distance_m": 10000,
        "duration_s": 3600,
        "avg_hr": 150,
        "max_hr": 175,
        "name": "Morning Run",
        "is_duplicate": False,
        "duplicate_of_id": None,
        "is_race_candidate": False,
        "workout_type": None,
        "race_confidence": None,
        "intensity_score": None,
        "performance_percentage": None,
        "moving_time_s": 3500,
        "total_elevation_gain": 100,
        "start_lat": None,
        "start_lng": None,
        "avg_cadence": None,
        "max_cadence": None,
        "avg_stride_length_m": None,
        "avg_ground_contact_ms": None,
        "avg_vertical_oscillation_cm": None,
        "avg_power_w": None,
        "garmin_aerobic_te": None,
        "garmin_perceived_effort": None,
    }
    defaults.update(kwargs)
    act = MagicMock()
    for k, v in defaults.items():
        setattr(act, k, v)
    return act


class TestChoosePrimary:
    def test_garmin_preferred_when_strava_counterpart(self):
        garmin = _make_activity(provider="garmin", avg_hr=150)
        strava = _make_activity(provider="strava", avg_hr=148)
        primary, secondary = _choose_primary(garmin, strava)
        assert primary.provider == "garmin"
        assert secondary.provider == "strava"

    def test_strava_secondary_when_garmin_primary(self):
        garmin = _make_activity(provider="garmin")
        strava = _make_activity(provider="strava")
        primary, secondary = _choose_primary(garmin, strava)
        assert primary.provider == "garmin"

    def test_same_provider_prefers_more_data(self):
        a = _make_activity(provider="strava", avg_hr=150, avg_cadence=180)
        b = _make_activity(provider="strava", avg_hr=None, avg_cadence=None)
        primary, _ = _choose_primary(a, b)
        assert primary.id == a.id


class TestMergeFields:
    def test_fills_null_garmin_fields_from_secondary(self):
        primary = _make_activity(provider="garmin", avg_cadence=None)
        secondary = _make_activity(provider="strava", avg_cadence=180)
        _merge_fields(primary, secondary)
        assert primary.avg_cadence == 180

    def test_strava_name_fills_null_primary(self):
        primary = _make_activity(provider="garmin", name=None)
        secondary = _make_activity(provider="strava", name="Sunday Long Run")
        _merge_fields(primary, secondary)
        assert primary.name == "Sunday Long Run"

    def test_prefers_longer_moving_time_gps(self):
        primary = _make_activity(moving_time_s=3000, distance_m=9800)
        secondary = _make_activity(moving_time_s=3500, distance_m=10100)
        _merge_fields(primary, secondary)
        assert primary.distance_m == 10100

    def test_prefers_higher_performance_score(self):
        primary = _make_activity(performance_percentage=65.0)
        secondary = _make_activity(performance_percentage=67.0)
        _merge_fields(primary, secondary)
        assert primary.performance_percentage == 67.0


class TestScanAndMarkDuplicates:
    def test_identifies_cross_provider_duplicate_with_five_hour_sync_delay(self):
        """Garmin records at run time; Strava arrives 5h later — must still dedup."""
        athlete_id = uuid.uuid4()
        t = datetime(2025, 6, 15, 8, 0, 0)

        garmin = _make_activity(
            athlete_id=athlete_id, provider="garmin",
            start_time=t, distance_m=16093, avg_hr=148,
        )
        strava = _make_activity(
            athlete_id=athlete_id, provider="strava",
            start_time=t + timedelta(hours=5), distance_m=16093 * 1.01, avg_hr=150,
        )

        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            garmin, strava,
        ]

        result = scan_and_mark_duplicates(athlete_id, db)
        assert result["pairs_found"] == 1
        assert strava.is_duplicate is True

    def test_doubles_same_distance_not_cross_paired(self):
        """
        AM and PM runs of the same distance must each match only their own
        cross-provider counterpart, not the other session's record.
        """
        athlete_id = uuid.uuid4()
        garmin_am = _make_activity(
            athlete_id=athlete_id, provider="garmin",
            start_time=datetime(2025, 6, 15, 6, 0, 0), distance_m=9656,
        )
        strava_am = _make_activity(
            athlete_id=athlete_id, provider="strava",
            start_time=datetime(2025, 6, 15, 11, 0, 0), distance_m=9656,
        )
        garmin_pm = _make_activity(
            athlete_id=athlete_id, provider="garmin",
            start_time=datetime(2025, 6, 15, 18, 0, 0), distance_m=9656,
        )
        strava_pm = _make_activity(
            athlete_id=athlete_id, provider="strava",
            start_time=datetime(2025, 6, 15, 23, 0, 0), distance_m=9656,
        )

        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            garmin_am, strava_am, garmin_pm, strava_pm,
        ]

        result = scan_and_mark_duplicates(athlete_id, db)
        assert result["pairs_found"] == 2
        assert strava_am.is_duplicate is True
        assert strava_pm.is_duplicate is True
        assert garmin_am.is_duplicate is False
        assert garmin_pm.is_duplicate is False

    def test_identifies_cross_provider_duplicate(self):
        athlete_id = uuid.uuid4()
        t = datetime(2025, 6, 15, 8, 0, 0)

        strava = _make_activity(
            athlete_id=athlete_id, provider="strava",
            start_time=t, distance_m=10000, avg_hr=150,
        )
        garmin = _make_activity(
            athlete_id=athlete_id, provider="garmin",
            start_time=t + timedelta(minutes=5), distance_m=10050, avg_hr=152,
        )

        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            strava, garmin,
        ]

        result = scan_and_mark_duplicates(athlete_id, db)
        assert result["pairs_found"] == 1
        assert result["marked_duplicate"] == 1

        # One of them should be marked duplicate
        marked = [a for a in [strava, garmin] if a.is_duplicate]
        assert len(marked) == 1

    def test_does_not_flag_different_activities(self):
        athlete_id = uuid.uuid4()

        a = _make_activity(
            athlete_id=athlete_id, provider="strava",
            start_time=datetime(2025, 6, 15, 8, 0, 0), distance_m=10000,
        )
        b = _make_activity(
            athlete_id=athlete_id, provider="garmin",
            start_time=datetime(2025, 6, 15, 14, 0, 0), distance_m=5000,
        )

        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [a, b]

        result = scan_and_mark_duplicates(athlete_id, db)
        assert result["pairs_found"] == 0
        assert result["marked_duplicate"] == 0

    def test_does_not_flag_same_provider(self):
        athlete_id = uuid.uuid4()
        t = datetime(2025, 6, 15, 8, 0, 0)

        a = _make_activity(
            athlete_id=athlete_id, provider="strava",
            start_time=t, distance_m=10000,
        )
        b = _make_activity(
            athlete_id=athlete_id, provider="strava",
            start_time=t + timedelta(minutes=2), distance_m=10020,
        )

        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [a, b]

        result = scan_and_mark_duplicates(athlete_id, db)
        assert result["pairs_found"] == 0

    def test_keeps_richer_record_as_primary(self):
        athlete_id = uuid.uuid4()
        t = datetime(2025, 6, 15, 8, 0, 0)

        strava = _make_activity(
            athlete_id=athlete_id, provider="strava",
            start_time=t, distance_m=10000, avg_hr=None, name="Race Day 10K",
        )
        garmin = _make_activity(
            athlete_id=athlete_id, provider="garmin",
            start_time=t + timedelta(minutes=3), distance_m=10020, avg_hr=155,
            name=None,
        )

        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            strava, garmin,
        ]

        scan_and_mark_duplicates(athlete_id, db)

        # Garmin is primary (has HR), Strava is duplicate
        assert strava.is_duplicate is True
        assert strava.duplicate_of_id == garmin.id
        # Garmin got the name from Strava
        assert garmin.name == "Race Day 10K"

    def test_multiple_duplicate_pairs(self):
        athlete_id = uuid.uuid4()

        activities = []
        for i in range(3):
            t = datetime(2025, 6, 15 + i, 8, 0, 0)
            activities.append(_make_activity(
                athlete_id=athlete_id, provider="strava",
                start_time=t, distance_m=10000 + i * 10,
            ))
            activities.append(_make_activity(
                athlete_id=athlete_id, provider="garmin",
                start_time=t + timedelta(minutes=2), distance_m=10000 + i * 10 + 5,
            ))

        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = activities

        result = scan_and_mark_duplicates(athlete_id, db)
        assert result["pairs_found"] == 3
        assert result["marked_duplicate"] == 3
