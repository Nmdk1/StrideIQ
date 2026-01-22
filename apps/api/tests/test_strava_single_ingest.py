"""
Unit tests for single-activity Strava ingest (mocked; no external calls).
"""

from datetime import datetime, timezone
from unittest.mock import patch

from models import Activity, BestEffort, PersonalBest
from services.strava_ingest import ingest_strava_activity_by_id


def test_ingest_single_activity_creates_activity_and_efforts(db_session, test_athlete):
    # Use an ID that won't collide with real DB data (provider+external_activity_id is globally unique).
    sid = 99999123456
    fake_details = {
        "id": sid,
        "start_date": "2025-04-18T23:00:09Z",
        "distance": 1641.0,
        "moving_time": 344,
        "elapsed_time": 344,
        "average_speed": 4.8,
        "name": "1st place in the Threefoot mile!",
        "best_efforts": [
            {"name": "1 mile", "distance": 1609.34, "elapsed_time": 334, "start_date": "2025-04-18T23:00:09Z", "id": 999},
            {"name": "400m", "distance": 400.0, "elapsed_time": 75, "start_date": "2025-04-18T23:00:09Z", "id": 998},
        ],
    }

    with patch("services.strava_ingest.get_activity_details", return_value=fake_details):
        res = ingest_strava_activity_by_id(test_athlete, db_session, sid, mark_as_race=True)

    assert res.created_activity is True
    assert res.stored_best_efforts >= 1

    act = (
        db_session.query(Activity)
        .filter(Activity.athlete_id == test_athlete.id, Activity.provider == "strava", Activity.external_activity_id == "14217725443")
        .first()
    )
    # Query must match the synthetic Strava ID used above.
    if act is None:
        act = (
            db_session.query(Activity)
            .filter(
                Activity.athlete_id == test_athlete.id,
                Activity.provider == "strava",
                Activity.external_activity_id == str(sid),
            )
            .first()
        )
    assert act is not None
    assert act.user_verified_race is True
    assert act.is_race_candidate is True

    # Ensure BestEffort rows exist for this activity
    be_count = db_session.query(BestEffort).filter(BestEffort.activity_id == act.id).count()
    assert be_count == 2

    # Ensure PBs were regenerated and mile exists
    mile_pb = (
        db_session.query(PersonalBest)
        .filter(PersonalBest.athlete_id == test_athlete.id, PersonalBest.distance_category == "mile")
        .first()
    )
    assert mile_pb is not None
    assert mile_pb.time_seconds == 334
    assert mile_pb.is_race is True

