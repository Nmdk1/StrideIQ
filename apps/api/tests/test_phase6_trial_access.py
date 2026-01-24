from uuid import uuid4
from datetime import datetime, timezone, timedelta

import pytest
from fastapi.testclient import TestClient

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models import Athlete


client = TestClient(app)


def _headers(user: Athlete) -> dict:
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_free():
    db = SessionLocal()
    athlete = Athlete(
        email=f"trial_{uuid4()}@example.com",
        display_name="TrialUser",
        role="athlete",
        subscription_tier="free",
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    db.close()
    return athlete


def test_self_serve_trial_start_sets_fields_and_grants_access(user_free):
    resp = client.post("/v1/billing/trial/start", json={"days": 7}, headers=_headers(user_free))
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["trial_started_at"] is not None
    assert data["trial_ends_at"] is not None
    assert data["trial_source"] == "self_serve"
    assert data["has_active_subscription"] is True

    db = SessionLocal()
    try:
        row = db.query(Athlete).filter(Athlete.id == user_free.id).first()
        assert row is not None
        assert row.trial_started_at is not None
        assert row.trial_ends_at is not None
        assert row.trial_ends_at > datetime.now(timezone.utc)
        assert row.has_active_subscription is True
    finally:
        try:
            if row:
                db.delete(row)
            db.commit()
        finally:
            db.close()


def test_trial_cannot_be_started_twice(user_free):
    resp1 = client.post("/v1/billing/trial/start", json={"days": 7}, headers=_headers(user_free))
    assert resp1.status_code == 200

    resp2 = client.post("/v1/billing/trial/start", json={"days": 7}, headers=_headers(user_free))
    assert resp2.status_code == 409

    db = SessionLocal()
    try:
        row = db.query(Athlete).filter(Athlete.id == user_free.id).first()
        assert row is not None
    finally:
        try:
            if row:
                db.delete(row)
            db.commit()
        finally:
            db.close()


def test_trial_denied_if_already_paid_tier():
    db = SessionLocal()
    athlete = Athlete(
        email=f"trial_paid_{uuid4()}@example.com",
        display_name="PaidUser",
        role="athlete",
        subscription_tier="pro",
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    db.close()

    resp = client.post("/v1/billing/trial/start", json={"days": 7}, headers=_headers(athlete))
    assert resp.status_code == 409

    db = SessionLocal()
    try:
        row = db.query(Athlete).filter(Athlete.id == athlete.id).first()
        assert row is not None
    finally:
        try:
            if row:
                db.delete(row)
            db.commit()
        finally:
            db.close()


def test_trial_expiry_removes_active_subscription_signal():
    db = SessionLocal()
    athlete = Athlete(
        email=f"trial_exp_{uuid4()}@example.com",
        display_name="ExpiredTrialUser",
        role="athlete",
        subscription_tier="free",
        trial_started_at=datetime.now(timezone.utc) - timedelta(days=10),
        trial_ends_at=datetime.now(timezone.utc) - timedelta(days=3),
        trial_source="self_serve",
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    db.close()

    # /me should reflect trial fields and computed entitlement
    me = client.get("/v1/auth/me", headers=_headers(athlete))
    assert me.status_code == 200
    payload = me.json()
    assert payload["subscription_tier"] == "free"
    assert payload["trial_ends_at"] is not None
    assert payload["has_active_subscription"] is False

    db = SessionLocal()
    try:
        row = db.query(Athlete).filter(Athlete.id == athlete.id).first()
        assert row is not None
    finally:
        try:
            if row:
                db.delete(row)
            db.commit()
        finally:
            db.close()

