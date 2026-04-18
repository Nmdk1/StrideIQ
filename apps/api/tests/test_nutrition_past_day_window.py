"""
Phase 1 — Past-day add/edit window guard.

Athletes need to log meals they forgot, and edit past entries they got wrong,
without being able to invent fictional history or pre-log future days that
would corrupt correlation analytics.

Backend rule (single source of truth, see routers/nutrition._validate_entry_date):
  - dates strictly in the future → 400
  - dates older than MAX_BACKLOG_DAYS (60) → 400
  - dates in [today - 60d, today]                 → allowed
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models import Activity, Athlete, NutritionEntry
from routers.nutrition import MAX_BACKLOG_DAYS, _validate_entry_date

client = TestClient(app)


def _auth_headers(athlete: Athlete) -> dict[str, str]:
    token = create_access_token({"sub": str(athlete.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def athlete():
    db = SessionLocal()
    try:
        existing = (
            db.query(Athlete)
            .filter(Athlete.email == "test_pastday@example.com")
            .first()
        )
        if existing:
            db.query(NutritionEntry).filter(
                NutritionEntry.athlete_id == existing.id
            ).delete()
            for a in db.query(Activity).filter(Activity.athlete_id == existing.id).all():
                db.query(NutritionEntry).filter(
                    NutritionEntry.activity_id == a.id
                ).delete()
            db.query(Activity).filter(Activity.athlete_id == existing.id).delete()
            db.delete(existing)
            db.commit()

        a = Athlete(
            email="test_pastday@example.com",
            display_name="Past Day Tester",
            subscription_tier="free",
        )
        db.add(a)
        db.commit()
        db.refresh(a)
        yield a

        db.query(NutritionEntry).filter(
            NutritionEntry.athlete_id == a.id
        ).delete()
        db.delete(a)
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Pure validator (lives in routers.nutrition; pure-function tests run fast)
# ---------------------------------------------------------------------------


class TestValidateEntryDate:
    def test_today_is_allowed(self):
        _validate_entry_date(date.today())

    def test_yesterday_is_allowed(self):
        _validate_entry_date(date.today() - timedelta(days=1))

    def test_exactly_max_backlog_days_old_is_allowed(self):
        _validate_entry_date(date.today() - timedelta(days=MAX_BACKLOG_DAYS))

    def test_one_day_past_max_backlog_is_rejected(self):
        with pytest.raises(Exception) as exc:
            _validate_entry_date(date.today() - timedelta(days=MAX_BACKLOG_DAYS + 1))
        # FastAPI HTTPException stringifies to '' but the detail carries the message.
        msg = str(getattr(exc.value, "detail", exc.value)).lower()
        assert "60" in msg or "older" in msg

    def test_tomorrow_is_rejected(self):
        with pytest.raises(Exception) as exc:
            _validate_entry_date(date.today() + timedelta(days=1))
        msg = str(getattr(exc.value, "detail", exc.value)).lower()
        assert "future" in msg

    def test_far_future_is_rejected(self):
        with pytest.raises(Exception):
            _validate_entry_date(date.today() + timedelta(days=365))


# ---------------------------------------------------------------------------
# POST /v1/nutrition — create on past days
# ---------------------------------------------------------------------------


class TestPostNutritionAcceptsPastDates:
    def _payload(self, d: date) -> dict:
        return {
            "athlete_id": str(uuid4()),  # ignored, server uses current_user
            "date": d.isoformat(),
            "entry_type": "daily",
            "calories": 320,
            "protein_g": 22,
            "carbs_g": 40,
            "fat_g": 8,
            "notes": "test late log",
        }

    def test_create_for_today(self, athlete):
        r = client.post(
            "/v1/nutrition",
            json=self._payload(date.today()),
            headers=_auth_headers(athlete),
        )
        assert r.status_code == 201, r.text
        assert r.json()["date"] == date.today().isoformat()

    def test_create_for_yesterday(self, athlete):
        d = date.today() - timedelta(days=1)
        r = client.post(
            "/v1/nutrition",
            json=self._payload(d),
            headers=_auth_headers(athlete),
        )
        assert r.status_code == 201, r.text
        assert r.json()["date"] == d.isoformat()

    def test_create_for_thirty_days_ago(self, athlete):
        d = date.today() - timedelta(days=30)
        r = client.post(
            "/v1/nutrition",
            json=self._payload(d),
            headers=_auth_headers(athlete),
        )
        assert r.status_code == 201, r.text
        assert r.json()["date"] == d.isoformat()

    def test_reject_create_for_tomorrow(self, athlete):
        d = date.today() + timedelta(days=1)
        r = client.post(
            "/v1/nutrition",
            json=self._payload(d),
            headers=_auth_headers(athlete),
        )
        assert r.status_code == 400
        assert "future" in r.json().get("detail", "").lower()

    def test_reject_create_older_than_window(self, athlete):
        d = date.today() - timedelta(days=MAX_BACKLOG_DAYS + 5)
        r = client.post(
            "/v1/nutrition",
            json=self._payload(d),
            headers=_auth_headers(athlete),
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# PUT /v1/nutrition/{id} — edit existing entry, including moving to past day
# ---------------------------------------------------------------------------


class TestPutNutritionAcceptsPastDates:
    def _create_entry(self, athlete) -> dict:
        r = client.post(
            "/v1/nutrition",
            json={
                "athlete_id": str(uuid4()),
                "date": date.today().isoformat(),
                "entry_type": "daily",
                "calories": 300,
                "protein_g": 20,
                "carbs_g": 30,
                "fat_g": 10,
                "notes": "original",
            },
            headers=_auth_headers(athlete),
        )
        assert r.status_code == 201, r.text
        return r.json()

    def test_edit_moves_entry_to_yesterday(self, athlete):
        entry = self._create_entry(athlete)
        d = date.today() - timedelta(days=1)
        r = client.put(
            f"/v1/nutrition/{entry['id']}",
            json={
                "athlete_id": str(uuid4()),
                "date": d.isoformat(),
                "entry_type": "daily",
                "calories": 350,
                "protein_g": 25,
                "carbs_g": 35,
                "fat_g": 12,
                "notes": "edited and moved",
            },
            headers=_auth_headers(athlete),
        )
        assert r.status_code == 200, r.text
        assert r.json()["date"] == d.isoformat()
        assert r.json()["calories"] == "350.00" or float(r.json()["calories"]) == 350

    def test_reject_edit_to_future_date(self, athlete):
        entry = self._create_entry(athlete)
        d = date.today() + timedelta(days=2)
        r = client.put(
            f"/v1/nutrition/{entry['id']}",
            json={
                "athlete_id": str(uuid4()),
                "date": d.isoformat(),
                "entry_type": "daily",
                "calories": 400,
                "protein_g": 25,
                "carbs_g": 35,
                "fat_g": 12,
                "notes": "future",
            },
            headers=_auth_headers(athlete),
        )
        assert r.status_code == 400

    def test_reject_edit_older_than_window(self, athlete):
        entry = self._create_entry(athlete)
        d = date.today() - timedelta(days=MAX_BACKLOG_DAYS + 10)
        r = client.put(
            f"/v1/nutrition/{entry['id']}",
            json={
                "athlete_id": str(uuid4()),
                "date": d.isoformat(),
                "entry_type": "daily",
                "calories": 400,
                "protein_g": 25,
                "carbs_g": 35,
                "fat_g": 12,
                "notes": "ancient",
            },
            headers=_auth_headers(athlete),
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# GET /v1/nutrition?start_date=&end_date= still works for the new dates
# ---------------------------------------------------------------------------


class TestGetReadsPastDates:
    def test_get_returns_entry_logged_to_yesterday(self, athlete):
        d = date.today() - timedelta(days=1)
        client.post(
            "/v1/nutrition",
            json={
                "athlete_id": str(uuid4()),
                "date": d.isoformat(),
                "entry_type": "daily",
                "calories": 555,
                "protein_g": 33,
                "carbs_g": 60,
                "fat_g": 15,
                "notes": "yesterday meal",
            },
            headers=_auth_headers(athlete),
        )
        r = client.get(
            f"/v1/nutrition?start_date={d.isoformat()}&end_date={d.isoformat()}",
            headers=_auth_headers(athlete),
        )
        assert r.status_code == 200, r.text
        rows = r.json()
        assert any(row.get("notes") == "yesterday meal" for row in rows)
