import json
from datetime import datetime, timezone
from pathlib import Path

from models import Activity
from services.provider_import.garmin_di_connect import import_garmin_di_connect_summaries


def _write_summarized_activities_file(root: Path, filename: str, activities: list[dict]) -> Path:
    p = root / "DI_CONNECT" / "DI-Connect-Fitness"
    p.mkdir(parents=True, exist_ok=True)
    f = p / filename
    f.write_text(json.dumps([{"summarizedActivitiesExport": activities}]), encoding="utf-8")
    return f


def test_imports_multi_sport_activities_and_converts_units(db_session, test_athlete, tmp_path):
    """
    Both runs and non-run activities (cycling, etc.) must be ingested. Sports we don't
    analyze yet (e.g. swimming) should be skipped via the unsupported-sport counter.
    Unit conversions are still verified on the run row.
    """
    # distance is centimeters, duration is milliseconds, startTimeLocal is epoch ms
    start_ms = 1700000000000.0  # ~2023-11-14 UTC

    _write_summarized_activities_file(
        tmp_path,
        "test_summarizedActivities.json",
        activities=[
            {
                "activityId": 123,
                "activityType": "running",
                "startTimeLocal": start_ms,
                "distance": 160934.4,  # 1609.344m (1 mile) in cm
                "duration": 420000.0,  # 420s in ms
                "averageHeartRate": 150,
                "maxHeartRate": 175,
                "elevationGain": 50.0,
            },
            {
                "activityId": 999,
                "activityType": "cycling",
                "startTimeLocal": start_ms + 86400000.0,
                "distance": 4000000.0,  # 40km in cm
                "duration": 5400000.0,  # 90 min in ms
            },
            {
                "activityId": 5555,
                "activityType": "lap_swimming",
                "startTimeLocal": start_ms + 2 * 86400000.0,
                "distance": 100000.0,
                "duration": 1500000.0,
            },
        ],
    )

    stats = import_garmin_di_connect_summaries(db_session, athlete_id=test_athlete.id, extracted_root_dir=tmp_path)
    assert stats["created"] == 2, "Run + cycling should both be created; swimming skipped"
    assert stats["skipped_non_runs"] == 1
    assert stats["skipped_unsupported_sport"] == 1

    run = (
        db_session.query(Activity)
        .filter(Activity.athlete_id == test_athlete.id, Activity.provider == "garmin", Activity.external_activity_id == "123")
        .first()
    )
    assert run is not None
    assert run.sport == "run"
    assert run.distance_m == 1609
    assert run.duration_s == 420
    assert run.avg_hr == 150
    assert run.max_hr == 175
    assert float(run.total_elevation_gain) == 50.0

    ride = (
        db_session.query(Activity)
        .filter(Activity.athlete_id == test_athlete.id, Activity.provider == "garmin", Activity.external_activity_id == "999")
        .first()
    )
    assert ride is not None, "Garmin DI-Connect must ingest cycling activities (Dejan-class regression)"
    assert ride.sport == "cycling", "Sport must be canonical 'cycling', not legacy 'ride'"


def test_imports_canonical_sport_codes_for_all_supported_types(db_session, test_athlete, tmp_path):
    """
    Regression for the multi-sport ingest fix: all supported Garmin DI-Connect activity
    types must round-trip with the right canonical sport code. This prevents future
    regressions to runs-only behavior that silently dropped athletes' historical
    cycling/walking/hiking/strength data.
    """
    start_ms = 1700000000000.0
    cases = [
        (3001, "running", "run"),
        (3002, "trail_running", "run"),
        (3003, "treadmill_running", "run"),
        (3004, "cycling", "cycling"),
        (3005, "mountain_biking", "cycling"),
        (3006, "indoor_cycling", "cycling"),
        (3007, "gravel_cycling", "cycling"),
        (3008, "walking", "walking"),
        (3009, "hiking", "hiking"),
        (3010, "strength_training", "strength"),
        (3011, "yoga", "flexibility"),
    ]

    activities = [
        {
            "activityId": cid,
            "activityType": at,
            "startTimeLocal": start_ms + (i * 86400000.0),
            "distance": 100000.0,
            "duration": 1800000.0,
        }
        for i, (cid, at, _) in enumerate(cases)
    ]

    _write_summarized_activities_file(
        tmp_path,
        "test_summarizedActivities.json",
        activities=activities,
    )

    stats = import_garmin_di_connect_summaries(db_session, athlete_id=test_athlete.id, extracted_root_dir=tmp_path)
    assert stats["created"] == len(cases)
    assert stats["skipped_non_runs"] == 0

    for cid, at, want_sport in cases:
        row = (
            db_session.query(Activity)
            .filter(
                Activity.athlete_id == test_athlete.id,
                Activity.provider == "garmin",
                Activity.external_activity_id == str(cid),
            )
            .first()
        )
        assert row is not None, f"DI-Connect dropped activityType={at!r} (id={cid})"
        assert row.sport == want_sport, (
            f"activityType={at!r}: expected sport={want_sport!r}, got {row.sport!r}"
        )


def test_imports_unknown_sport_variants_via_substring_fallback(db_session, test_athlete, tmp_path):
    """
    Garmin occasionally introduces new device/activity-type strings. The substring
    fallback in `_sport_from_activity_type` keeps these from being silently dropped:
    a hypothetical 'gravel_e_bike' should still map into the cycling family rather
    than disappearing into skipped_non_runs.
    """
    start_ms = 1700000000000.0
    _write_summarized_activities_file(
        tmp_path,
        "test_summarizedActivities.json",
        activities=[
            {
                "activityId": 4001,
                "activityType": "gravel_e_bike",  # not in explicit map
                "startTimeLocal": start_ms,
                "distance": 5000000.0,
                "duration": 5400000.0,
            },
        ],
    )

    stats = import_garmin_di_connect_summaries(db_session, athlete_id=test_athlete.id, extracted_root_dir=tmp_path)
    assert stats["created"] == 1
    row = (
        db_session.query(Activity)
        .filter(Activity.athlete_id == test_athlete.id, Activity.external_activity_id == "4001")
        .first()
    )
    assert row is not None
    assert row.sport == "cycling"


def test_import_normalizes_garmin_elevation_gain_centimeters_to_meters(db_session, test_athlete, tmp_path):
    """
    Regression: some Garmin exports report elevationGain in centimeters.
    Example: 26200 => 262m (not 26,200m).
    """
    start_ms = 1700000000000.0
    _write_summarized_activities_file(
        tmp_path,
        "test_summarizedActivities.json",
        activities=[
            {
                "activityId": 124,
                "activityType": "running",
                "startTimeLocal": start_ms,
                "distance": 5000 * 100.0,  # cm
                "duration": 1800 * 1000.0,  # ms
                "elevationGain": 26200.0,  # cm
            },
        ],
    )

    stats = import_garmin_di_connect_summaries(db_session, athlete_id=test_athlete.id, extracted_root_dir=tmp_path)
    assert stats["created"] == 1

    act = (
        db_session.query(Activity)
        .filter(Activity.athlete_id == test_athlete.id, Activity.provider == "garmin", Activity.external_activity_id == "124")
        .first()
    )
    assert act is not None
    assert float(act.total_elevation_gain) == 262.0


def test_import_is_idempotent_by_provider_external_id(db_session, test_athlete, tmp_path):
    start_ms = 1700000000000.0
    _write_summarized_activities_file(
        tmp_path,
        "test_summarizedActivities.json",
        activities=[
            {"activityId": 123, "activityType": "running", "startTimeLocal": start_ms, "distance": 100000.0, "duration": 600000.0},
        ],
    )

    stats1 = import_garmin_di_connect_summaries(db_session, athlete_id=test_athlete.id, extracted_root_dir=tmp_path)
    stats2 = import_garmin_di_connect_summaries(db_session, athlete_id=test_athlete.id, extracted_root_dir=tmp_path)

    assert stats1["created"] == 1
    assert stats2["created"] == 0
    assert stats2["already_present"] == 1


def test_import_does_not_error_if_external_id_exists_for_other_athlete(db_session, test_athlete, tmp_path):
    """
    The Activity table has a global unique constraint on (provider, external_activity_id).
    Re-imports must never crash even if another athlete already has an activity with the same external id.
    """
    from uuid import uuid4
    from models import Athlete

    other = Athlete(email=f"other_{uuid4()}@example.com", display_name="Other Athlete")
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)

    start_dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    db_session.add(
        Activity(
            athlete_id=other.id,
            name="Other Garmin Run",
            start_time=start_dt,
            sport="run",
            source="garmin_import",
            duration_s=1800,
            distance_m=5000,
            provider="garmin",
            external_activity_id="999999",
        )
    )
    db_session.commit()

    start_ms = float(int(start_dt.timestamp() * 1000))
    _write_summarized_activities_file(
        tmp_path,
        "test_summarizedActivities.json",
        activities=[
            {"activityId": 999999, "activityType": "running", "startTimeLocal": start_ms, "distance": 5000 * 100.0, "duration": 1800 * 1000.0},
        ],
    )

    stats = import_garmin_di_connect_summaries(db_session, athlete_id=test_athlete.id, extracted_root_dir=tmp_path)
    assert stats["created"] == 0
    assert stats["already_present"] == 1


def test_import_skips_possible_duplicates_by_time_and_distance(db_session, test_athlete, tmp_path):
    # Existing Strava activity at a given time/distance
    start_dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    db_session.add(
        Activity(
            athlete_id=test_athlete.id,
            name="Existing Strava Run",
            start_time=start_dt,
            sport="run",
            source="strava",
            duration_s=1800,
            distance_m=5000,
            provider="strava",
            external_activity_id="strava_1",
        )
    )
    db_session.commit()

    # Garmin activity within 2 minutes and within 1.5% distance tolerance
    start_ms = int(start_dt.timestamp() * 1000) + 60_000  # +60s
    _write_summarized_activities_file(
        tmp_path,
        "test_summarizedActivities.json",
        activities=[
            {
                "activityId": 456,
                "activityType": "running",
                "startTimeLocal": float(start_ms),
                "distance": 5000 * 100.0,  # cm
                "duration": 1800 * 1000.0,  # ms
            }
        ],
    )

    stats = import_garmin_di_connect_summaries(db_session, athlete_id=test_athlete.id, extracted_root_dir=tmp_path)
    assert stats["created"] == 0
    assert stats["skipped_possible_duplicate"] == 1

