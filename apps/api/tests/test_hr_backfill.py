"""
Tests for HR backfill service (Fix 3).

Covers: time-window matching, distance tolerance, skip-when-HR-exists,
best-match selection (nearest start_time), and no-garmin-HR guard.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest


def _make_activity(db_session, athlete, **overrides):
    """Create an Activity row with minimal required fields."""
    from models import Activity

    defaults = dict(
        athlete_id=athlete.id,
        provider="strava",
        external_activity_id=str(uuid.uuid4()),
        name="Test Run",
        start_time=datetime(2026, 3, 10, 8, 0, tzinfo=timezone.utc),
        distance_m=8000,
        duration_s=3600,
        avg_hr=None,
        max_hr=None,
    )
    defaults.update(overrides)
    activity = Activity(**defaults)
    db_session.add(activity)
    db_session.commit()
    db_session.refresh(activity)
    return activity


class TestHrBackfill:
    """Tests for services.hr_backfill.backfill_hr_from_garmin."""

    def test_hr_backfill_matches_by_time(self, db_session, test_athlete):
        """Garmin activity within 30min of Strava activity triggers HR fill."""
        from services.hr_backfill import backfill_hr_from_garmin

        base = datetime(2026, 3, 10, 8, 0, tzinfo=timezone.utc)
        strava = _make_activity(
            db_session, test_athlete,
            provider="strava",
            start_time=base,
            distance_m=8000,
            avg_hr=None,
        )
        garmin = _make_activity(
            db_session, test_athlete,
            provider="garmin",
            start_time=base + timedelta(minutes=5),
            distance_m=8050,
            avg_hr=145,
            max_hr=162,
        )

        result_id = backfill_hr_from_garmin(db_session, test_athlete.id, garmin)

        assert result_id == strava.id
        db_session.refresh(strava)
        assert strava.avg_hr == 145
        assert strava.max_hr == 162

    def test_hr_backfill_skips_distance_mismatch(self, db_session, test_athlete):
        """Activities with >10% distance difference are not matched."""
        from services.hr_backfill import backfill_hr_from_garmin

        base = datetime(2026, 3, 11, 8, 0, tzinfo=timezone.utc)
        strava = _make_activity(
            db_session, test_athlete,
            provider="strava",
            start_time=base,
            distance_m=5000,
            avg_hr=None,
        )
        garmin = _make_activity(
            db_session, test_athlete,
            provider="garmin",
            start_time=base + timedelta(minutes=2),
            distance_m=8000,   # >10% different from 5000
            avg_hr=145,
            max_hr=162,
        )

        result_id = backfill_hr_from_garmin(db_session, test_athlete.id, garmin)

        assert result_id is None
        db_session.refresh(strava)
        assert strava.avg_hr is None

    def test_hr_backfill_skips_when_strava_has_hr(self, db_session, test_athlete):
        """Strava activities that already have HR are not overwritten."""
        from services.hr_backfill import backfill_hr_from_garmin

        base = datetime(2026, 3, 12, 8, 0, tzinfo=timezone.utc)
        strava = _make_activity(
            db_session, test_athlete,
            provider="strava",
            start_time=base,
            distance_m=8000,
            avg_hr=140,  # already has HR
            max_hr=158,
        )
        garmin = _make_activity(
            db_session, test_athlete,
            provider="garmin",
            start_time=base + timedelta(minutes=3),
            distance_m=8050,
            avg_hr=145,
            max_hr=162,
        )

        result_id = backfill_hr_from_garmin(db_session, test_athlete.id, garmin)

        assert result_id is None
        db_session.refresh(strava)
        assert strava.avg_hr == 140  # unchanged

    def test_hr_backfill_skips_when_garmin_has_no_hr(self, db_session, test_athlete):
        """Garmin activity without HR returns None immediately."""
        from services.hr_backfill import backfill_hr_from_garmin

        base = datetime(2026, 3, 13, 8, 0, tzinfo=timezone.utc)
        _make_activity(
            db_session, test_athlete,
            provider="strava",
            start_time=base,
            distance_m=8000,
            avg_hr=None,
        )
        garmin = _make_activity(
            db_session, test_athlete,
            provider="garmin",
            start_time=base + timedelta(minutes=2),
            distance_m=8050,
            avg_hr=None,  # no HR on garmin side
        )

        result_id = backfill_hr_from_garmin(db_session, test_athlete.id, garmin)

        assert result_id is None

    def test_hr_backfill_outside_time_window_no_match(self, db_session, test_athlete):
        """Strava activity >30min away from Garmin is not matched."""
        from services.hr_backfill import backfill_hr_from_garmin

        base = datetime(2026, 3, 14, 8, 0, tzinfo=timezone.utc)
        strava = _make_activity(
            db_session, test_athlete,
            provider="strava",
            start_time=base,
            distance_m=8000,
            avg_hr=None,
        )
        garmin = _make_activity(
            db_session, test_athlete,
            provider="garmin",
            start_time=base + timedelta(minutes=45),  # outside 30min window
            distance_m=8050,
            avg_hr=145,
        )

        result_id = backfill_hr_from_garmin(db_session, test_athlete.id, garmin)

        assert result_id is None
        db_session.refresh(strava)
        assert strava.avg_hr is None

    def test_hr_backfill_picks_nearest_when_multiple_candidates(self, db_session, test_athlete):
        """When multiple Strava activities match, the nearest start_time wins."""
        from services.hr_backfill import backfill_hr_from_garmin

        base = datetime(2026, 3, 15, 8, 0, tzinfo=timezone.utc)
        # Two strava activities close to garmin time, same distance
        strava_near = _make_activity(
            db_session, test_athlete,
            provider="strava",
            start_time=base + timedelta(minutes=3),
            distance_m=8000,
            avg_hr=None,
        )
        strava_far = _make_activity(
            db_session, test_athlete,
            provider="strava",
            start_time=base + timedelta(minutes=20),
            distance_m=8000,
            avg_hr=None,
        )
        garmin = _make_activity(
            db_session, test_athlete,
            provider="garmin",
            start_time=base,
            distance_m=8000,
            avg_hr=150,
            max_hr=168,
        )

        result_id = backfill_hr_from_garmin(db_session, test_athlete.id, garmin)

        assert result_id == strava_near.id
        db_session.refresh(strava_near)
        db_session.refresh(strava_far)
        assert strava_near.avg_hr == 150
        assert strava_far.avg_hr is None  # not touched
