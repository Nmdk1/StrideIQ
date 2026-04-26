from datetime import datetime, timedelta, timezone

from models import Activity


def _activity(test_athlete, *, name, start_time, distance_m=5000, duration_s=1500, is_race=False):
    return Activity(
        athlete_id=test_athlete.id,
        name=name,
        start_time=start_time,
        sport="run",
        source="test",
        duration_s=duration_s,
        distance_m=distance_m,
        user_verified_race=is_race,
        is_race_candidate=is_race,
        workout_type="race" if is_race else "easy_run",
    )


def test_search_activities_finds_old_race_beyond_recent_50(db_session, test_athlete):
    from services.coach_tools import search_activities

    target = _activity(
        test_athlete,
        name="Tuscaloosa Mayor's Cup 5K",
        start_time=datetime(2025, 4, 26, 8, 0, tzinfo=timezone.utc),
        distance_m=5000,
        duration_s=1170,
        is_race=True,
    )
    db_session.add(target)

    base = datetime(2026, 4, 24, 8, 0, tzinfo=timezone.utc)
    for i in range(60):
        db_session.add(
            _activity(
                test_athlete,
                name=f"Recent Training Run {i}",
                start_time=base - timedelta(days=i),
                distance_m=8000,
                duration_s=2400,
                is_race=False,
            )
        )
    db_session.commit()

    result = search_activities(
        db_session,
        test_athlete.id,
        start_date="2025-04-26",
        end_date="2025-04-26",
        name_contains="Tuscaloosa",
        race_only=True,
        distance_min_m=4800,
        distance_max_m=5200,
        limit=10,
    )

    assert result["ok"] is True
    assert result["data"]["match_count"] == 1
    match = result["data"]["activities"][0]
    assert match["activity_id"] == str(target.id)
    assert match["name"] == "Tuscaloosa Mayor's Cup 5K"
    assert match["is_race"] is True
    assert result["data"]["search_criteria"]["name_contains"] == "Tuscaloosa"
    assert result["evidence"][0]["activity_id"] == str(target.id)


def test_search_activities_reports_empty_search_criteria(db_session, test_athlete):
    from services.coach_tools import search_activities

    result = search_activities(
        db_session,
        test_athlete.id,
        start_date="2024-01-01",
        end_date="2024-01-02",
        name_contains="No Such Race",
        race_only=True,
    )

    assert result["ok"] is True
    assert result["data"]["match_count"] == 0
    assert "No activities matched" in result["narrative"]
    assert result["data"]["search_criteria"]["race_only"] is True
