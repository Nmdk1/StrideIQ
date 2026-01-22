"""
Unit tests for Strava activity index upsert (no external calls).
"""

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

