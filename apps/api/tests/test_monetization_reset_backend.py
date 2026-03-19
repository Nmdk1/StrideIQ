from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models import Athlete, RacePromoCode


client = TestClient(app)


def _headers(user: Athlete) -> dict:
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def _cleanup_athlete(email: str) -> None:
    db = SessionLocal()
    try:
        row = db.query(Athlete).filter(Athlete.email == email).first()
        if row is not None:
            db.delete(row)
            db.commit()
    finally:
        db.close()


def test_register_auto_starts_30_day_trial():
    email = f"auto_trial_{uuid4()}@example.com"
    try:
        resp = client.post(
            "/v1/auth/register",
            json={"email": email, "password": "TestPass123!@#"},
        )
        assert resp.status_code == 201, resp.text
        athlete = resp.json()["athlete"]
        assert athlete["trial_started_at"] is not None
        assert athlete["trial_ends_at"] is not None
        assert athlete["trial_source"] == "signup"

        started = datetime.fromisoformat(athlete["trial_started_at"].replace("Z", "+00:00"))
        ended = datetime.fromisoformat(athlete["trial_ends_at"].replace("Z", "+00:00"))
        assert 29 <= (ended - started).days <= 30
    finally:
        _cleanup_athlete(email)


def test_register_race_promo_extends_trial_beyond_30_days():
    db = SessionLocal()
    code = f"RACE{uuid4().hex[:8].upper()}"
    promo = RacePromoCode(
        code=code,
        race_name="Spec Marathon",
        trial_days=45,
        is_active=True,
        current_uses=0,
    )
    db.add(promo)
    db.commit()
    db.refresh(promo)
    db.close()

    email = f"race_trial_{uuid4()}@example.com"
    try:
        resp = client.post(
            "/v1/auth/register",
            json={"email": email, "password": "TestPass123!@#", "race_code": code},
        )
        assert resp.status_code == 201, resp.text
        athlete = resp.json()["athlete"]
        assert athlete["trial_source"] == f"race:{code}"
        started = datetime.fromisoformat(athlete["trial_started_at"].replace("Z", "+00:00"))
        ended = datetime.fromisoformat(athlete["trial_ends_at"].replace("Z", "+00:00"))
        assert (ended - started).days >= 44
    finally:
        db = SessionLocal()
        try:
            row = db.query(Athlete).filter(Athlete.email == email).first()
            if row is not None:
                db.delete(row)
            promo_row = db.query(RacePromoCode).filter(RacePromoCode.id == promo.id).first()
            if promo_row is not None:
                db.delete(promo_row)
            db.commit()
        finally:
            db.close()


def test_coach_endpoints_gated_for_free_and_open_for_active_trial():
    db = SessionLocal()
    free_user = Athlete(
        email=f"coach_free_{uuid4()}@example.com",
        display_name="CoachFree",
        role="athlete",
        subscription_tier="free",
    )
    trial_user = Athlete(
        email=f"coach_trial_{uuid4()}@example.com",
        display_name="CoachTrial",
        role="athlete",
        subscription_tier="free",
        trial_started_at=datetime.now(timezone.utc) - timedelta(days=1),
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=10),
        trial_source="signup",
    )
    db.add(free_user)
    db.add(trial_user)
    db.commit()
    db.refresh(free_user)
    db.refresh(trial_user)
    db.close()

    try:
        blocked = client.get("/v1/coach/history", headers=_headers(free_user))
        assert blocked.status_code == 403

        allowed = client.get("/v1/coach/history", headers=_headers(trial_user))
        assert allowed.status_code != 403
    finally:
        _cleanup_athlete(free_user.email)
        _cleanup_athlete(trial_user.email)


def test_checkout_ignores_tier_and_forces_single_paid_tier(monkeypatch):
    captured = {}

    def _fake_create_checkout_session(self, *, athlete, tier="premium", billing_period="annual"):
        captured["tier"] = tier
        captured["billing_period"] = billing_period
        return "https://stripe.test/checkout"

    from services import stripe_service as ss

    monkeypatch.setattr(ss.StripeService, "create_checkout_session", _fake_create_checkout_session)

    db = SessionLocal()
    athlete = Athlete(
        email=f"checkout_{uuid4()}@example.com",
        display_name="Checkout",
        role="athlete",
        subscription_tier="free",
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    db.close()

    try:
        resp = client.post(
            "/v1/billing/checkout",
            headers=_headers(athlete),
            json={"tier": "guided", "billing_period": "monthly"},
        )
        assert resp.status_code == 200, resp.text
        payload = resp.json()
        assert payload["tier"] == "premium"
        assert payload["billing_period"] == "monthly"
        assert captured["tier"] == "premium"
        assert captured["billing_period"] == "monthly"
    finally:
        _cleanup_athlete(athlete.email)


def test_trial_status_endpoint_returns_counts():
    db = SessionLocal()
    athlete = Athlete(
        email=f"trial_status_{uuid4()}@example.com",
        display_name="TrialStatus",
        role="athlete",
        subscription_tier="free",
        trial_started_at=datetime.now(timezone.utc) - timedelta(days=3),
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=5),
        trial_source="signup",
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    db.close()

    try:
        resp = client.get("/v1/billing/trial/status", headers=_headers(athlete))
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["has_trial"] is True
        assert data["trial_days_remaining"] >= 0
        assert data["facts_learned"] >= 0
        assert data["findings_discovered"] >= 0
        assert data["activities_analyzed"] >= 0
    finally:
        _cleanup_athlete(athlete.email)
