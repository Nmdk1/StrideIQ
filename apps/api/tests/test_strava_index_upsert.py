"""
Unit tests for Strava activity index upsert (no external calls).
"""

import uuid
from datetime import datetime, timezone

from models import Activity
from services.strava_index import upsert_strava_activity_summaries


def test_upsert_strava_activity_summaries_creates_missing(db_session, test_athlete):
    summaries = [
        {
            "type": "Run",
            "id": 111,
            "start_date": "2025-01-01T12:00:00Z",
            "distance": 5000.0,
            "moving_time": 1200,
            "average_speed": 4.0,
            "name": "Test Run",
            "total_elevation_gain": 10.0,
        },
        {"type": "Ride", "id": 222, "start_date": "2025-01-01T12:00:00Z"},
    ]

    res = upsert_strava_activity_summaries(test_athlete, db_session, summaries)
    db_session.commit()

    assert res.created == 1
    assert res.skipped_non_runs == 1

    act = (
        db_session.query(Activity)
        .filter(Activity.provider == "strava", Activity.external_activity_id == "111")
        .first()
    )
    assert act is not None
    assert act.athlete_id == test_athlete.id
    assert act.distance_m == 5000
    assert act.duration_s == 1200


def test_cross_provider_dedup_skips_garmin_match(db_session, test_athlete):
    """If a Garmin activity exists at the same time/distance, Strava index should skip it."""
    garmin_act = Activity(
        id=uuid.uuid4(),
        athlete_id=test_athlete.id,
        start_time=datetime(2025, 3, 15, 8, 0, 0, tzinfo=timezone.utc),
        provider="garmin",
        external_activity_id="garmin_999",
        sport="run",
        source="garmin",
        name="Morning Run",
        distance_m=10000,
        duration_s=3000,
        avg_hr=145,
    )
    db_session.add(garmin_act)
    db_session.commit()

    strava_summaries = [
        {
            "type": "Run",
            "id": 555,
            "start_date": "2025-03-15T08:00:30Z",
            "distance": 10050.0,
            "moving_time": 3005,
            "average_speed": 3.3,
            "average_heartrate": 146,
            "name": "Morning Run",
        },
    ]

    res = upsert_strava_activity_summaries(test_athlete, db_session, strava_summaries)
    db_session.commit()

    assert res.created == 0
    assert res.already_present == 1

    strava_row = (
        db_session.query(Activity)
        .filter(Activity.provider == "strava", Activity.external_activity_id == "555")
        .first()
    )
    assert strava_row is None, "Strava duplicate should not have been created"

    total = db_session.query(Activity).filter(Activity.athlete_id == test_athlete.id).count()
    assert total == 1, "Should only have the original Garmin activity"


def test_cross_provider_dedup_allows_different_run(db_session, test_athlete):
    """If no Garmin match exists, Strava activity should be created normally."""
    garmin_act = Activity(
        id=uuid.uuid4(),
        athlete_id=test_athlete.id,
        start_time=datetime(2025, 3, 15, 8, 0, 0, tzinfo=timezone.utc),
        provider="garmin",
        external_activity_id="garmin_888",
        sport="run",
        source="garmin",
        name="Morning Run",
        distance_m=10000,
        duration_s=3000,
    )
    db_session.add(garmin_act)
    db_session.commit()

    strava_summaries = [
        {
            "type": "Run",
            "id": 666,
            "start_date": "2025-03-15T17:00:00Z",
            "distance": 5000.0,
            "moving_time": 1500,
            "average_speed": 3.3,
            "name": "Evening Run",
        },
    ]

    res = upsert_strava_activity_summaries(test_athlete, db_session, strava_summaries)
    db_session.commit()

    assert res.created == 1, "Different run should be created"
    total = db_session.query(Activity).filter(Activity.athlete_id == test_athlete.id).count()
    assert total == 2

