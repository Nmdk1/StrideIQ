"""
Regression tests for PersonalBest correctness.

These tests are intentionally "blast radius" tests:
- They touch the real DB schema (transactionally rolled back).
- They will fail if `best_effort` table is missing, preventing silent PB regressions.
"""

from datetime import datetime, timezone

from models import Activity, BestEffort, PersonalBest
from services.best_effort_service import regenerate_personal_bests


class TestPersonalBestFromBestEffort:
    def test_regenerate_uses_min_elapsed_time_per_category(self, db_session, test_athlete):
        # Create an activity (source for is_race flag)
        activity = Activity(
            athlete_id=test_athlete.id,
            start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
            provider="strava",
            external_activity_id="123",
            duration_s=3600,
            distance_m=10000,
            average_speed=4.0,
            is_race_candidate=True,
        )
        db_session.add(activity)
        db_session.commit()
        db_session.refresh(activity)

        # Two 5k efforts from the same activity; fastest should win.
        e1 = BestEffort(
            athlete_id=test_athlete.id,
            activity_id=activity.id,
            distance_category="5k",
            distance_meters=5000,
            elapsed_time=1200,
            achieved_at=activity.start_time,
            strava_effort_id=1,
        )
        e2 = BestEffort(
            athlete_id=test_athlete.id,
            activity_id=activity.id,
            distance_category="5k",
            distance_meters=5000,
            elapsed_time=1140,
            achieved_at=activity.start_time,
            strava_effort_id=2,
        )
        db_session.add_all([e1, e2])
        db_session.commit()

        res = regenerate_personal_bests(test_athlete, db_session)
        assert "5k" in res["categories"]

        pb = (
            db_session.query(PersonalBest)
            .filter(PersonalBest.athlete_id == test_athlete.id, PersonalBest.distance_category == "5k")
            .first()
        )
        assert pb is not None
        assert pb.time_seconds == 1140
        assert pb.is_race is True
        assert pb.activity_id == activity.id

    def test_marathon_category_is_supported(self, db_session, test_athlete):
        activity = Activity(
            athlete_id=test_athlete.id,
            start_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
            provider="strava",
            external_activity_id="456",
            duration_s=3 * 3600,
            distance_m=42195,
            average_speed=3.9,
            is_race_candidate=True,
        )
        db_session.add(activity)
        db_session.commit()
        db_session.refresh(activity)

        effort = BestEffort(
            athlete_id=test_athlete.id,
            activity_id=activity.id,
            distance_category="marathon",
            distance_meters=42195,
            elapsed_time=3 * 3600,
            achieved_at=activity.start_time,
            strava_effort_id=9999999999,
        )
        db_session.add(effort)
        db_session.commit()

        regenerate_personal_bests(test_athlete, db_session)
        pb = (
            db_session.query(PersonalBest)
            .filter(PersonalBest.athlete_id == test_athlete.id, PersonalBest.distance_category == "marathon")
            .first()
        )
        assert pb is not None
        assert pb.time_seconds == 3 * 3600
        assert pb.is_race is True

