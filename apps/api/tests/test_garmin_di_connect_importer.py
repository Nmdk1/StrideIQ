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


def test_imports_run_like_activities_and_converts_units(db_session, test_athlete, tmp_path):
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
                "distance": 100000.0,
                "duration": 100000.0,
            },
        ],
    )

    stats = import_garmin_di_connect_summaries(db_session, athlete_id=test_athlete.id, extracted_root_dir=tmp_path)
    assert stats["created"] == 1
    assert stats["skipped_non_runs"] == 1

    act = (
        db_session.query(Activity)
        .filter(Activity.athlete_id == test_athlete.id, Activity.provider == "garmin", Activity.external_activity_id == "123")
        .first()
    )
    assert act is not None
    assert act.distance_m == 1609
    assert act.duration_s == 420
    assert act.avg_hr == 150
    assert act.max_hr == 175
    assert float(act.total_elevation_gain) == 50.0


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

