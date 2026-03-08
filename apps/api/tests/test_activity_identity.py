"""Tests for Activity Identity: resolve_activity_title, PUT title endpoint,
and resolved_title presence in list/detail/home/calendar responses."""
import pytest
from unittest.mock import MagicMock
from routers.activities import (
    resolve_activity_title, ActivityTitleUpdate, _is_auto_generated_name,
)


def _make_activity(**kwargs):
    a = MagicMock()
    a.athlete_title = kwargs.get('athlete_title', None)
    a.shape_sentence = kwargs.get('shape_sentence', None)
    a.name = kwargs.get('name', None)
    a.provider = kwargs.get('provider', 'garmin')
    a.user_verified_race = kwargs.get('user_verified_race', False)
    a.is_race_candidate = kwargs.get('is_race_candidate', False)
    return a


class TestAutoNameDetection:
    """Verifies platform auto-name detection for Strava and Garmin."""

    def test_strava_morning_run(self):
        assert _is_auto_generated_name("Morning Run", "strava") is True

    def test_strava_afternoon_run(self):
        assert _is_auto_generated_name("Afternoon Run", "strava") is True

    def test_strava_long_run(self):
        assert _is_auto_generated_name("Long Run", "strava") is True

    def test_strava_authored_title(self):
        assert _is_auto_generated_name("Father son, state age records 10 mile!", "strava") is False

    def test_strava_workout_description(self):
        assert _is_auto_generated_name("1 mile warmup, 2@8:00, 1@7:30", "strava") is False

    def test_garmin_location_running(self):
        assert _is_auto_generated_name("Lauderdale County Running", "garmin") is True

    def test_garmin_different_location(self):
        assert _is_auto_generated_name("Bay St Louis Running", "garmin") is True

    def test_garmin_authored_title(self):
        assert _is_auto_generated_name("forgot to start watch - one mile", "garmin") is False

    def test_garmin_workout_description(self):
        assert _is_auto_generated_name("Lauderdale County - 6 x 5 minutes", "garmin") is False

    def test_demo_always_auto(self):
        assert _is_auto_generated_name("Easy Run", "demo") is True

    def test_none_is_auto(self):
        assert _is_auto_generated_name(None, "strava") is True

    def test_empty_is_auto(self):
        assert _is_auto_generated_name("", "garmin") is True


class TestResolveActivityTitle:
    """Full priority chain with race and authorship guards."""

    def test_athlete_title_always_wins(self):
        a = _make_activity(
            athlete_title="My custom title",
            shape_sentence="5 miles easy",
            name="Morning Run",
        )
        assert resolve_activity_title(a) == "My custom title"

    def test_race_name_beats_shape_sentence(self):
        a = _make_activity(
            name="Father son, state age records 10 mile!",
            shape_sentence="10 miles tempo",
            provider="strava",
            user_verified_race=True,
        )
        assert resolve_activity_title(a) == "Father son, state age records 10 mile!"

    def test_race_candidate_name_beats_shape_sentence(self):
        a = _make_activity(
            name="Turkey Trot 5K",
            shape_sentence="3 miles at 6:20",
            provider="strava",
            is_race_candidate=True,
        )
        assert resolve_activity_title(a) == "Turkey Trot 5K"

    def test_authored_strava_beats_shape_sentence(self):
        a = _make_activity(
            name="Longest run before 3 week taper. Stunning weather.",
            shape_sentence="18.5 miles long run at 8:52",
            provider="strava",
        )
        assert resolve_activity_title(a) == "Longest run before 3 week taper. Stunning weather."

    def test_authored_garmin_beats_shape_sentence(self):
        a = _make_activity(
            name="forgot to start watch - one mile",
            shape_sentence="1 mile easy at 8:00",
            provider="garmin",
        )
        assert resolve_activity_title(a) == "forgot to start watch - one mile"

    def test_auto_strava_loses_to_shape_sentence(self):
        a = _make_activity(
            name="Morning Run",
            shape_sentence="5 miles easy at 8:30",
            provider="strava",
        )
        assert resolve_activity_title(a) == "5 miles easy at 8:30"

    def test_auto_garmin_loses_to_shape_sentence(self):
        a = _make_activity(
            name="Lauderdale County Running",
            shape_sentence="7 miles easy at 8:54",
            provider="garmin",
        )
        assert resolve_activity_title(a) == "7 miles easy at 8:54"

    def test_no_sentence_falls_to_name(self):
        a = _make_activity(name="Morning Run", provider="strava")
        assert resolve_activity_title(a) == "Morning Run"

    def test_all_none(self):
        a = _make_activity()
        assert resolve_activity_title(a) is None

    def test_empty_athlete_title_falls_through(self):
        a = _make_activity(
            athlete_title="",
            shape_sentence="5 miles easy",
            name="Morning Run",
            provider="strava",
        )
        assert resolve_activity_title(a) == "5 miles easy"

    def test_strava_workout_description_beats_sentence(self):
        a = _make_activity(
            name="1 mile warmup, 2@8:00, 1@7:30, 1 mile cool down",
            shape_sentence="5.5 miles building from 9:29 to 8:01",
            provider="strava",
        )
        assert resolve_activity_title(a) == "1 mile warmup, 2@8:00, 1@7:30, 1 mile cool down"

    def test_demo_auto_loses_to_shape_sentence(self):
        a = _make_activity(
            name="Easy Run",
            shape_sentence="5 miles building from 9:30 to 7:56",
            provider="demo",
        )
        assert resolve_activity_title(a) == "5 miles building from 9:30 to 7:56"


class TestActivityTitleUpdateSchema:
    """Validator: normalize empty → None, enforce 200-char max."""

    def test_normal_title(self):
        update = ActivityTitleUpdate(title="My race day!")
        assert update.title == "My race day!"

    def test_none_passes(self):
        update = ActivityTitleUpdate(title=None)
        assert update.title is None

    def test_empty_string_normalized_to_none(self):
        update = ActivityTitleUpdate(title="")
        assert update.title is None

    def test_whitespace_only_normalized_to_none(self):
        update = ActivityTitleUpdate(title="   ")
        assert update.title is None

    def test_strips_whitespace(self):
        update = ActivityTitleUpdate(title="  My run  ")
        assert update.title == "My run"

    def test_200_chars_accepted(self):
        title = "A" * 200
        update = ActivityTitleUpdate(title=title)
        assert len(update.title) == 200

    def test_201_chars_rejected(self):
        with pytest.raises(Exception):
            ActivityTitleUpdate(title="A" * 201)


class TestPutTitleEndpoint:
    """Integration tests for PUT /v1/activities/{id}/title."""

    @pytest.fixture
    def setup(self):
        from fastapi.testclient import TestClient
        from main import app
        from core.database import SessionLocal
        from models import Athlete, Activity
        from core.security import create_access_token
        from uuid import uuid4
        from datetime import datetime
        from decimal import Decimal

        db = SessionLocal()
        athlete = Athlete(
            email=f"test_identity_{uuid4()}@example.com",
            display_name="Identity Test",
            subscription_tier="free",
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)

        activity = Activity(
            athlete_id=athlete.id,
            start_time=datetime.now(),
            sport="run",
            source="manual",
            duration_s=1800,
            distance_m=5000,
            avg_hr=150,
            average_speed=Decimal("2.78"),
            name="Morning Run",
            shape_sentence="3 miles easy at 8:30",
        )
        db.add(activity)
        db.commit()
        db.refresh(activity)

        token = create_access_token(
            data={"sub": str(athlete.id), "email": athlete.email, "role": "athlete"}
        )
        client = TestClient(app)
        headers = {"Authorization": f"Bearer {token}"}

        yield {
            "db": db,
            "athlete": athlete,
            "activity": activity,
            "client": client,
            "headers": headers,
        }

        db.query(Activity).filter(Activity.athlete_id == athlete.id).delete()
        db.delete(athlete)
        db.commit()
        db.close()

    def test_set_title(self, setup):
        resp = setup["client"].put(
            f"/v1/activities/{setup['activity'].id}/title",
            json={"title": "My epic run"},
            headers=setup["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["athlete_title"] == "My epic run"
        assert data["resolved_title"] == "My epic run"

    def test_clear_title_with_null(self, setup):
        c = setup["client"]
        h = setup["headers"]
        aid = setup["activity"].id
        c.put(f"/v1/activities/{aid}/title", json={"title": "Custom"}, headers=h)
        resp = c.put(f"/v1/activities/{aid}/title", json={"title": None}, headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["athlete_title"] is None
        assert data["resolved_title"] == "3 miles easy at 8:30"

    def test_clear_title_with_empty_string(self, setup):
        c = setup["client"]
        h = setup["headers"]
        aid = setup["activity"].id
        c.put(f"/v1/activities/{aid}/title", json={"title": "Custom"}, headers=h)
        resp = c.put(f"/v1/activities/{aid}/title", json={"title": ""}, headers=h)
        assert resp.status_code == 200
        assert resp.json()["athlete_title"] is None

    def test_wrong_athlete_403(self, setup):
        from core.security import create_access_token
        from uuid import uuid4

        other_token = create_access_token(
            data={"sub": str(uuid4()), "email": "other@example.com", "role": "athlete"}
        )
        resp = setup["client"].put(
            f"/v1/activities/{setup['activity'].id}/title",
            json={"title": "Hacked"},
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert resp.status_code == 403

    def test_not_found_404(self, setup):
        from uuid import uuid4

        resp = setup["client"].put(
            f"/v1/activities/{uuid4()}/title",
            json={"title": "Ghost"},
            headers=setup["headers"],
        )
        assert resp.status_code == 404

    def test_too_long_422(self, setup):
        resp = setup["client"].put(
            f"/v1/activities/{setup['activity'].id}/title",
            json={"title": "A" * 201},
            headers=setup["headers"],
        )
        assert resp.status_code == 422

    def test_list_includes_resolved_title(self, setup):
        resp = setup["client"].get("/v1/activities", headers=setup["headers"])
        assert resp.status_code == 200
        activities = resp.json()
        assert len(activities) >= 1
        first = activities[0]
        assert "resolved_title" in first
        assert first["resolved_title"] == "3 miles easy at 8:30"
        assert first["shape_sentence"] == "3 miles easy at 8:30"

    def test_detail_includes_resolved_title(self, setup):
        resp = setup["client"].get(
            f"/v1/activities/{setup['activity'].id}",
            headers=setup["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["resolved_title"] == "3 miles easy at 8:30"
        assert data["shape_sentence"] == "3 miles easy at 8:30"
        assert data["athlete_title"] is None


class TestRuntoonResolvedTitle:
    """Unit test for _format_activity_context using resolved title."""

    def test_uses_athlete_title(self):
        from services.runtoon_service import _format_activity_context

        activity = MagicMock()
        activity.start_time = None
        activity.distance_meters = None
        activity.moving_time_s = None
        activity.workout_type = None
        activity.athlete_title = "My race day"
        activity.shape_sentence = "5 miles easy"
        activity.name = "Morning Run"
        activity.provider = "strava"
        activity.is_race_candidate = False
        activity.user_verified_race = False
        activity.average_hr = None

        result = _format_activity_context(activity)
        assert "My race day" in result
        assert "Morning Run" not in result

    def test_auto_name_falls_to_shape_sentence(self):
        from services.runtoon_service import _format_activity_context

        activity = MagicMock()
        activity.start_time = None
        activity.distance_meters = None
        activity.moving_time_s = None
        activity.workout_type = None
        activity.athlete_title = None
        activity.shape_sentence = "5 miles easy"
        activity.name = "Morning Run"
        activity.provider = "strava"
        activity.is_race_candidate = False
        activity.user_verified_race = False
        activity.average_hr = None

        result = _format_activity_context(activity)
        assert "5 miles easy" in result
        assert "Morning Run" not in result

    def test_authored_strava_name_wins(self):
        from services.runtoon_service import _format_activity_context

        activity = MagicMock()
        activity.start_time = None
        activity.distance_meters = None
        activity.moving_time_s = None
        activity.workout_type = None
        activity.athlete_title = None
        activity.shape_sentence = "10 miles tempo"
        activity.name = "Father son, state age records 10 mile!"
        activity.provider = "strava"
        activity.is_race_candidate = False
        activity.user_verified_race = True
        activity.average_hr = None

        result = _format_activity_context(activity)
        assert "Father son, state age records" in result
        assert "10 miles tempo" not in result
