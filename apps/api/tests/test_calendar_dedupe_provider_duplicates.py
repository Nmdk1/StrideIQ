from datetime import datetime, timezone

from models import Activity
from routers.calendar import dedupe_activities_for_calendar_display


def test_calendar_dedupe_prefers_strava_over_garmin(db_session, test_athlete):
    start = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    garmin = Activity(
        athlete_id=test_athlete.id,
        name="Garmin Run",
        start_time=start,
        sport="run",
        source="garmin_import",
        duration_s=3600,
        distance_m=16093,
        provider="garmin",
        external_activity_id="g1",
    )
    strava = Activity(
        athlete_id=test_athlete.id,
        name="Strava Run",
        start_time=start,
        sport="run",
        source="strava",
        duration_s=3605,
        distance_m=16080,  # within tolerance
        provider="strava",
        external_activity_id="s1",
    )
    db_session.add_all([garmin, strava])
    db_session.commit()

    out = dedupe_activities_for_calendar_display([garmin, strava])
    assert len(out) == 1
    assert out[0].provider == "strava"


def test_calendar_dedupe_does_not_collapse_distinct_doubles(db_session, test_athlete):
    # Two separate runs on same day, 4 hours apart: should remain distinct.
    a1 = Activity(
        athlete_id=test_athlete.id,
        name="AM Run",
        start_time=datetime(2026, 1, 1, 7, 0, 0, tzinfo=timezone.utc),
        sport="run",
        source="manual",
        duration_s=1800,
        distance_m=5000,
        provider="garmin",
        external_activity_id="g_am",
    )
    a2 = Activity(
        athlete_id=test_athlete.id,
        name="PM Run",
        start_time=datetime(2026, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
        sport="run",
        source="manual",
        duration_s=2400,
        distance_m=6000,
        provider="strava",
        external_activity_id="s_pm",
    )
    out = dedupe_activities_for_calendar_display([a1, a2])
    assert len(out) == 2

