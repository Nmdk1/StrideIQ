"""Tests for Activity Identity: resolve_activity_title, PUT title endpoint,
and resolved_title presence in list/detail/home/calendar responses."""
import pytest
from unittest.mock import MagicMock
from routers.activities import resolve_activity_title, ActivityTitleUpdate


class TestResolveActivityTitle:
    """Priority chain: athlete_title > shape_sentence > name."""

    def test_athlete_title_wins(self):
        a = MagicMock()
        a.athlete_title = "My custom title"
        a.shape_sentence = "5 miles easy"
        a.name = "Morning Run"
        assert resolve_activity_title(a) == "My custom title"

    def test_shape_sentence_wins_when_no_athlete_title(self):
        a = MagicMock()
        a.athlete_title = None
        a.shape_sentence = "5 miles easy"
        a.name = "Morning Run"
        assert resolve_activity_title(a) == "5 miles easy"

    def test_name_wins_when_nothing_else(self):
        a = MagicMock()
        a.athlete_title = None
        a.shape_sentence = None
        a.name = "Morning Run"
        assert resolve_activity_title(a) == "Morning Run"

    def test_all_none(self):
        a = MagicMock()
        a.athlete_title = None
        a.shape_sentence = None
        a.name = None
        assert resolve_activity_title(a) is None

    def test_empty_string_athlete_title_falls_through(self):
        a = MagicMock()
        a.athlete_title = ""
        a.shape_sentence = "5 miles easy"
        a.name = "Morning Run"
        assert resolve_activity_title(a) == "5 miles easy"


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

    def test_uses_resolved_title(self):
        from services.runtoon_service import _format_activity_context

        activity = MagicMock()
        activity.start_time = None
        activity.distance_meters = None
        activity.moving_time_s = None
        activity.workout_type = None
        activity.athlete_title = "My race day"
        activity.shape_sentence = "5 miles easy"
        activity.name = "Morning Run"
        activity.is_race_candidate = False
        activity.average_hr = None

        result = _format_activity_context(activity)
        assert "My race day" in result
        assert "Morning Run" not in result

    def test_falls_back_to_shape_sentence(self):
        from services.runtoon_service import _format_activity_context

        activity = MagicMock()
        activity.start_time = None
        activity.distance_meters = None
        activity.moving_time_s = None
        activity.workout_type = None
        activity.athlete_title = None
        activity.shape_sentence = "5 miles easy"
        activity.name = "Morning Run"
        activity.is_race_candidate = False
        activity.average_hr = None

        result = _format_activity_context(activity)
        assert "5 miles easy" in result
        assert "Morning Run" not in result
