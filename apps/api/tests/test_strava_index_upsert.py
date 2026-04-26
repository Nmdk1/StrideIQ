"""
Unit tests for Strava activity index upsert (no external calls).
"""

import uuid
from datetime import datetime, timezone

from models import Activity
from services.strava_index import upsert_strava_activity_summaries


def test_upsert_strava_activity_summaries_creates_missing(db_session, test_athlete):
    """
    Both runs and rides should be created. Sports we don't analyze yet (Swim, here)
    should be skipped via the 'unsupported sport' counter.
    """
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
        {
            "type": "Ride",
            "id": 222,
            "start_date": "2025-01-01T13:00:00Z",
            "distance": 30000.0,
            "moving_time": 3600,
            "name": "Test Ride",
        },
        {
            "type": "Swim",
            "id": 333,
            "start_date": "2025-01-01T14:00:00Z",
        },
    ]

    res = upsert_strava_activity_summaries(test_athlete, db_session, summaries)
    db_session.commit()

    assert res.created == 2
    assert res.skipped_non_runs == 1, "Swim is unsupported and should be skipped"

    run = (
        db_session.query(Activity)
        .filter(Activity.provider == "strava", Activity.external_activity_id == "111")
        .first()
    )
    assert run is not None
    assert run.sport == "run"
    assert run.distance_m == 5000
    assert run.duration_s == 1200

    ride = (
        db_session.query(Activity)
        .filter(Activity.provider == "strava", Activity.external_activity_id == "222")
        .first()
    )
    assert ride is not None, "Cycling is now ingested via Strava (Garmin-primary, Strava-backup)"
    assert ride.sport == "cycling", "Sport must be the canonical 'cycling' code, not 'ride'"
    assert ride.distance_m == 30000


def test_upsert_strava_activity_summaries_maps_all_canonical_sports(db_session, test_athlete):
    """
    Regression for the multi-sport ingestion fix: every Strava type we map to a canonical
    sport must round-trip with the right sport code. This prevents regressing back to the
    runs-only behavior that silently dropped cycling/walking/hiking/strength data for
    athletes whose Strava history predates their Garmin connection.
    """
    summaries = [
        {"type": "Run", "id": 1001, "start_date": "2025-01-01T12:00:00Z", "distance": 5000.0, "moving_time": 1200},
        {"type": "TrailRun", "id": 1002, "start_date": "2025-01-02T12:00:00Z", "distance": 10000.0, "moving_time": 3600},
        {"type": "Ride", "id": 1003, "start_date": "2025-01-03T12:00:00Z", "distance": 40000.0, "moving_time": 5400},
        {"type": "VirtualRide", "id": 1004, "start_date": "2025-01-04T12:00:00Z", "distance": 30000.0, "moving_time": 4500},
        {"type": "MountainBikeRide", "id": 1005, "start_date": "2025-01-05T12:00:00Z", "distance": 25000.0, "moving_time": 5400},
        {"type": "Walk", "id": 1006, "start_date": "2025-01-06T12:00:00Z", "distance": 3000.0, "moving_time": 1800},
        {"type": "Hike", "id": 1007, "start_date": "2025-01-07T12:00:00Z", "distance": 12000.0, "moving_time": 7200},
        {"type": "WeightTraining", "id": 1008, "start_date": "2025-01-08T12:00:00Z", "moving_time": 2700},
        {"type": "Yoga", "id": 1009, "start_date": "2025-01-09T12:00:00Z", "moving_time": 3600},
    ]

    res = upsert_strava_activity_summaries(test_athlete, db_session, summaries)
    db_session.commit()

    assert res.created == 9
    assert res.skipped_non_runs == 0

    expected = {
        "1001": "run",
        "1002": "run",
        "1003": "cycling",
        "1004": "cycling",
        "1005": "cycling",
        "1006": "walking",
        "1007": "hiking",
        "1008": "strength",
        "1009": "flexibility",
    }
    for ext_id, want_sport in expected.items():
        row = (
            db_session.query(Activity)
            .filter(Activity.provider == "strava", Activity.external_activity_id == ext_id)
            .first()
        )
        assert row is not None, f"Activity {ext_id} ({want_sport}) was not ingested"
        assert row.sport == want_sport, (
            f"Activity {ext_id}: expected sport={want_sport!r}, got {row.sport!r}"
        )


def test_upsert_strava_activity_summaries_prefers_sport_type_over_legacy_type(db_session, test_athlete):
    """
    Strava's `sport_type` (introduced 2022) is more specific than the legacy `type`. When
    both are present we should trust `sport_type` — e.g. an EBikeRide reported with
    `type='Ride'` and `sport_type='EBikeRide'` should still map to 'cycling'.
    """
    summaries = [
        {
            "type": "Ride",
            "sport_type": "EBikeRide",
            "id": 2001,
            "start_date": "2025-02-01T12:00:00Z",
            "distance": 50000.0,
            "moving_time": 5400,
        },
    ]

    res = upsert_strava_activity_summaries(test_athlete, db_session, summaries)
    db_session.commit()

    assert res.created == 1
    row = (
        db_session.query(Activity)
        .filter(Activity.provider == "strava", Activity.external_activity_id == "2001")
        .first()
    )
    assert row is not None
    assert row.sport == "cycling"


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

