"""
Regression tests for ingestion status calculations (no external calls).
"""

from datetime import datetime, timezone

from models import Activity, BestEffort
from services.ingestion_status import get_best_effort_ingestion_status


def test_best_effort_ingestion_status_counts(db_session, test_athlete):
    # Two Strava activities, only one has best efforts.
    a1 = Activity(
        athlete_id=test_athlete.id,
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        provider="strava",
        external_activity_id="111",
        sport="run",
        source="strava",
    )
    a2 = Activity(
        athlete_id=test_athlete.id,
        start_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
        provider="strava",
        external_activity_id="222",
        sport="run",
        source="strava",
    )
    db_session.add_all([a1, a2])
    db_session.commit()
    db_session.refresh(a1)

    be = BestEffort(
        athlete_id=test_athlete.id,
        activity_id=a1.id,
        distance_category="mile",
        distance_meters=1609,
        elapsed_time=360,
        achieved_at=a1.start_time,
        strava_effort_id=1,
    )
    db_session.add(be)
    db_session.commit()

    # Mark one activity as processed (details fetched + extraction attempted)
    a1.best_efforts_extracted_at = datetime.now(timezone.utc)
    db_session.commit()

    s = get_best_effort_ingestion_status(test_athlete.id, db_session, provider="strava")
    assert s.total_activities == 2
    assert s.activities_with_efforts == 1
    assert s.activities_processed == 1
    assert s.remaining_activities == 1
    assert s.best_effort_rows == 1
    assert s.coverage_pct == 50.0

