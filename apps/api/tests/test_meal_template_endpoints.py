"""
Phase 3 — meal template REST endpoints.

Verifies the round-trip:
  POST /v1/nutrition/meals  -> save
  GET  /v1/nutrition/meals  -> list
  POST /v1/nutrition/meals/{id}/log -> log into nutrition_entry
  PATCH/DELETE for rename + remove
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models import Athlete, MealTemplate, NutritionEntry

client = TestClient(app)


def _auth_headers(athlete: Athlete) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {create_access_token({'sub': str(athlete.id)})}"
    }


@pytest.fixture
def athlete():
    db = SessionLocal()
    try:
        a = Athlete(
            email=f"meal_ep_{uuid4().hex[:8]}@example.com",
            display_name="Meal Endpoint Tester",
            subscription_tier="free",
        )
        db.add(a)
        db.commit()
        db.refresh(a)
        yield a

        db.query(NutritionEntry).filter(
            NutritionEntry.athlete_id == a.id
        ).delete()
        db.query(MealTemplate).filter(
            MealTemplate.athlete_id == a.id
        ).delete()
        db.delete(a)
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Create + list
# ---------------------------------------------------------------------------


class TestCreateAndList:
    def test_create_and_appears_in_list(self, athlete):
        r = client.post(
            "/v1/nutrition/meals",
            json={
                "name": "Workday Breakfast",
                "items": [
                    {"food": "Eggs", "calories": 140, "protein_g": 12},
                    {"food": "Toast", "calories": 120, "carbs_g": 22},
                ],
            },
            headers=_auth_headers(athlete),
        )
        assert r.status_code == 201, r.text
        meal = r.json()
        assert meal["name"] == "Workday Breakfast"
        assert meal["is_user_named"] is True
        assert meal["total_calories"] == 260

        rl = client.get("/v1/nutrition/meals", headers=_auth_headers(athlete))
        assert rl.status_code == 200
        meals = rl.json()
        assert any(m["id"] == meal["id"] for m in meals)

    def test_blank_name_400(self, athlete):
        r = client.post(
            "/v1/nutrition/meals",
            json={"name": "  ", "items": [{"food": "x"}]},
            headers=_auth_headers(athlete),
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Log + edit
# ---------------------------------------------------------------------------


class TestLogAndEdit:
    def test_log_creates_nutrition_entry(self, athlete):
        r = client.post(
            "/v1/nutrition/meals",
            json={
                "name": "Lunch",
                "items": [
                    {"food": "rice", "calories": 200, "carbs_g": 44},
                    {"food": "chicken", "calories": 180, "protein_g": 33},
                ],
            },
            headers=_auth_headers(athlete),
        )
        meal_id = r.json()["id"]

        rl = client.post(
            f"/v1/nutrition/meals/{meal_id}/log",
            json={"date": date.today().isoformat(), "entry_type": "daily"},
            headers=_auth_headers(athlete),
        )
        assert rl.status_code == 201, rl.text
        entry = rl.json()
        assert entry["calories"] == 380
        assert entry["protein_g"] == 33
        assert entry["carbs_g"] == 44
        assert entry["macro_source"] == "meal_template"
        assert entry["notes"] == "Lunch"

    def test_log_respects_past_day_window(self, athlete):
        r = client.post(
            "/v1/nutrition/meals",
            json={
                "name": "X",
                "items": [{"food": "a", "calories": 100}, {"food": "b", "calories": 100}],
            },
            headers=_auth_headers(athlete),
        )
        meal_id = r.json()["id"]

        too_old = (date.today() - timedelta(days=400)).isoformat()
        r2 = client.post(
            f"/v1/nutrition/meals/{meal_id}/log",
            json={"date": too_old, "entry_type": "daily"},
            headers=_auth_headers(athlete),
        )
        assert r2.status_code == 400

        future = (date.today() + timedelta(days=1)).isoformat()
        r3 = client.post(
            f"/v1/nutrition/meals/{meal_id}/log",
            json={"date": future, "entry_type": "daily"},
            headers=_auth_headers(athlete),
        )
        assert r3.status_code == 400

    def test_rename(self, athlete):
        r = client.post(
            "/v1/nutrition/meals",
            json={
                "name": "Old Name",
                "items": [{"food": "a"}, {"food": "b"}],
            },
            headers=_auth_headers(athlete),
        )
        meal_id = r.json()["id"]

        rp = client.patch(
            f"/v1/nutrition/meals/{meal_id}",
            json={"name": "New Name"},
            headers=_auth_headers(athlete),
        )
        assert rp.status_code == 200
        assert rp.json()["name"] == "New Name"

    def test_delete(self, athlete):
        r = client.post(
            "/v1/nutrition/meals",
            json={"name": "Bye", "items": [{"food": "a"}, {"food": "b"}]},
            headers=_auth_headers(athlete),
        )
        meal_id = r.json()["id"]

        rd = client.delete(
            f"/v1/nutrition/meals/{meal_id}",
            headers=_auth_headers(athlete),
        )
        assert rd.status_code == 204

        rl = client.get("/v1/nutrition/meals", headers=_auth_headers(athlete))
        assert all(m["id"] != meal_id for m in rl.json())


# ---------------------------------------------------------------------------
# Cross-athlete isolation
# ---------------------------------------------------------------------------


class TestIsolation:
    def test_other_athlete_cannot_see_or_log(self, athlete):
        r = client.post(
            "/v1/nutrition/meals",
            json={"name": "Mine", "items": [{"food": "a"}, {"food": "b"}]},
            headers=_auth_headers(athlete),
        )
        meal_id = r.json()["id"]

        other = Athlete(
            email=f"meal_iso_{uuid4().hex[:8]}@example.com",
            display_name="Other",
            subscription_tier="free",
        )
        db = SessionLocal()
        try:
            db.add(other)
            db.commit()
            db.refresh(other)
        finally:
            db.close()

        try:
            rl = client.get("/v1/nutrition/meals", headers=_auth_headers(other))
            assert all(m["id"] != meal_id for m in rl.json())

            rlog = client.post(
                f"/v1/nutrition/meals/{meal_id}/log",
                json={"date": date.today().isoformat(), "entry_type": "daily"},
                headers=_auth_headers(other),
            )
            assert rlog.status_code == 404
        finally:
            db = SessionLocal()
            try:
                db.delete(db.query(Athlete).filter(Athlete.id == other.id).first())
                db.commit()
            finally:
                db.close()
