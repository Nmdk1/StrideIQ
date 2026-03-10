"""
P0-1 Security: v1 endpoint lockdown tests.

Verifies that previously unauthenticated v1 endpoints now require auth
and enforce ownership. Run with: pytest tests/test_p0_1_v1_endpoint_lockdown.py -v
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import date, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-at-least-32-chars")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "test-encryption-key-32-chars-ok")

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models import Athlete, Activity, DailyCheckin

client = TestClient(app)


def _headers(athlete: Athlete) -> dict:
    token = create_access_token({"sub": str(athlete.id)})
    return {"Authorization": f"Bearer {token}"}


@contextmanager
def _two_users():
    """Create athletes A and B; yield (a, b); cleanup on exit."""
    db = SessionLocal()
    a = b = None
    try:
        a = Athlete(
            email=f"a_{uuid4()}@example.com",
            display_name="A",
            subscription_tier="free",
            role="athlete",
        )
        b = Athlete(
            email=f"b_{uuid4()}@example.com",
            display_name="B",
            subscription_tier="free",
            role="athlete",
        )
        db.add(a)
        db.add(b)
        db.commit()
        db.refresh(a)
        db.refresh(b)
        yield a, b
    finally:
        if a:
            db.query(Activity).filter(Activity.athlete_id == a.id).delete(synchronize_session=False)
            db.query(DailyCheckin).filter(DailyCheckin.athlete_id == a.id).delete(synchronize_session=False)
            db.query(Athlete).filter(Athlete.id == a.id).delete(synchronize_session=False)
        if b:
            db.query(Athlete).filter(Athlete.id == b.id).delete(synchronize_session=False)
        db.commit()
        db.close()


@contextmanager
def _one_user(role: str = "athlete"):
    """Create one athlete; yield user; cleanup on exit."""
    db = SessionLocal()
    user = None
    try:
        user = Athlete(
            email=f"user_{uuid4()}@example.com",
            display_name="User",
            subscription_tier="free",
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        yield user
    finally:
        if user:
            db.query(Activity).filter(Activity.athlete_id == user.id).delete(synchronize_session=False)
            db.query(DailyCheckin).filter(DailyCheckin.athlete_id == user.id).delete(synchronize_session=False)
            db.query(Athlete).filter(Athlete.id == user.id).delete(synchronize_session=False)
        db.commit()
        db.close()


class TestV1UnauthenticatedBlocked:
    """Unauthenticated requests must return 401."""

    def test_get_athletes_requires_auth(self):
        resp = client.get("/v1/athletes")
        assert resp.status_code == 401

    def test_get_athlete_by_id_requires_auth(self):
        resp = client.get(f"/v1/athletes/{uuid4()}")
        assert resp.status_code == 401

    def test_post_activities_requires_auth(self):
        resp = client.post(
            "/v1/activities",
            json={
                "athlete_id": str(uuid4()),
                "start_time": "2026-01-01T00:00:00Z",
                "sport": "run",
                "duration_s": 3600,
                "distance_m": 5000,
            },
        )
        assert resp.status_code == 401

    def test_post_checkins_requires_auth(self):
        resp = client.post(
            "/v1/checkins",
            json={
                "athlete_id": str(uuid4()),
                "date": "2026-01-15",
                "sleep_h": 7.0,
            },
        )
        assert resp.status_code == 401

    def test_post_calculate_metrics_requires_auth(self):
        resp = client.post(f"/v1/athletes/{uuid4()}/calculate-metrics")
        assert resp.status_code == 401

    def test_get_personal_bests_requires_auth(self):
        resp = client.get(f"/v1/athletes/{uuid4()}/personal-bests")
        assert resp.status_code == 401

    def test_post_recalculate_pbs_requires_auth(self):
        resp = client.post(f"/v1/athletes/{uuid4()}/recalculate-pbs")
        assert resp.status_code == 401

    def test_post_sync_best_efforts_requires_auth(self):
        resp = client.post(f"/v1/athletes/{uuid4()}/sync-best-efforts")
        assert resp.status_code == 401


class TestV1CrossUserAccessBlocked:
    """Authenticated user A cannot access user B's data. All 8 endpoints covered."""

    def test_get_athletes_non_admin_returns_403(self):
        """GET /v1/athletes requires admin; athlete gets 403."""
        with _one_user(role="athlete") as a:
            resp = client.get("/v1/athletes", headers=_headers(a))
            assert resp.status_code == 403

    def test_get_athlete_other_user_returns_403(self):
        with _two_users() as (a, b):
            resp = client.get(f"/v1/athletes/{b.id}", headers=_headers(a))
            assert resp.status_code == 403

    def test_post_activities_body_athlete_id_ignored_creates_for_self(self):
        """POST /v1/activities: body athlete_id=B still creates for A."""
        with _two_users() as (a, b):
            resp = client.post(
                "/v1/activities",
                headers=_headers(a),
                json={
                    "athlete_id": str(b.id),
                    "start_time": "2026-01-01T12:00:00Z",
                    "sport": "run",
                    "duration_s": 1800,
                    "distance_m": 4000,
                },
            )
            assert resp.status_code == 201
            data = resp.json()
            activity_id = data["id"]
            db = SessionLocal()
            try:
                created = db.query(Activity).filter(Activity.id == UUID(activity_id)).first()
                assert created is not None
                assert created.athlete_id == a.id
                assert created.athlete_id != b.id
            finally:
                db.close()

    def test_post_checkins_body_athlete_id_ignored_creates_for_self(self):
        """POST /v1/checkins: body athlete_id=B still creates for A."""
        with _two_users() as (a, b):
            resp = client.post(
                "/v1/checkins",
                headers=_headers(a),
                json={
                    "athlete_id": str(b.id),
                    "date": "2026-01-15",
                    "sleep_h": 7.0,
                },
            )
            assert resp.status_code == 201
            data = resp.json()
            checkin_id = data["id"]
            db = SessionLocal()
            try:
                created = db.query(DailyCheckin).filter(DailyCheckin.id == UUID(checkin_id)).first()
                assert created is not None
                assert created.athlete_id == a.id
                assert created.athlete_id != b.id
            finally:
                db.close()

    def test_post_calculate_metrics_other_user_returns_403(self):
        with _two_users() as (a, b):
            resp = client.post(
                f"/v1/athletes/{b.id}/calculate-metrics",
                headers=_headers(a),
            )
            assert resp.status_code == 403

    def test_get_personal_bests_other_user_returns_403(self):
        with _two_users() as (a, b):
            resp = client.get(
                f"/v1/athletes/{b.id}/personal-bests",
                headers=_headers(a),
            )
            assert resp.status_code == 403

    def test_post_recalculate_pbs_other_user_returns_403(self):
        with _two_users() as (a, b):
            resp = client.post(
                f"/v1/athletes/{b.id}/recalculate-pbs",
                headers=_headers(a),
            )
            assert resp.status_code == 403

    def test_post_sync_best_efforts_other_user_returns_403(self):
        with _two_users() as (a, b):
            resp = client.post(
                f"/v1/athletes/{b.id}/sync-best-efforts",
                headers=_headers(a),
            )
            assert resp.status_code == 403


class TestV1PostActivitiesResponseShape:
    """Regression: POST /v1/activities response has required ActivityResponse fields."""

    def test_post_activities_response_has_required_fields(self):
        with _one_user() as user:
            resp = client.post(
                "/v1/activities",
                headers=_headers(user),
                json={
                    "athlete_id": str(user.id),
                    "start_time": "2026-01-01T12:00:00Z",
                    "sport": "run",
                    "duration_s": 3600,
                    "distance_m": 5000,
                },
            )
            assert resp.status_code == 201
            data = resp.json()
            # ActivityResponse required fields
            assert "id" in data
            assert isinstance(data["name"], str)
            assert isinstance(data["distance"], (int, float))
            assert isinstance(data["moving_time"], int)
            assert "start_date" in data
            assert isinstance(data["average_speed"], (int, float))
            # Optional but commonly present
            assert "strava_id" in data
            assert "pace_per_mile" in data
            assert "duration_formatted" in data


class TestV1AdminOwnerBypass:
    """Admin/owner can access where intended; athlete cannot."""

    def test_admin_can_get_athletes_list(self):
        with _one_user(role="admin") as admin:
            resp = client.get("/v1/athletes", headers=_headers(admin))
            assert resp.status_code == 200
            assert isinstance(resp.json(), list)

    def test_admin_can_get_other_athlete(self):
        with _two_users() as (a, b):
            with _one_user(role="admin") as admin:
                resp = client.get(f"/v1/athletes/{b.id}", headers=_headers(admin))
                assert resp.status_code == 200
                assert resp.json()["id"] == str(b.id)

    def test_athlete_cannot_get_athletes_list(self):
        with _one_user(role="athlete") as athlete:
            resp = client.get("/v1/athletes", headers=_headers(athlete))
            assert resp.status_code == 403


class TestV1LegitClientBehavior:
    """Legit clients can still access their own data."""

    def test_get_athlete_own_id_returns_200(self):
        with _one_user() as user:
            resp = client.get(f"/v1/athletes/{user.id}", headers=_headers(user))
            assert resp.status_code == 200
            assert resp.json()["id"] == str(user.id)

    def test_get_athletes_me_returns_200(self):
        with _one_user() as user:
            resp = client.get("/v1/athletes/me", headers=_headers(user))
            assert resp.status_code == 200
            assert resp.json()["id"] == str(user.id)
