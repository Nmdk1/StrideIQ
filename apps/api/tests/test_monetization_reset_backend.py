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

    from services import stripe_service as ss

    mock_cfg = ss.StripeConfig(
        secret_key="sk_test_dummy",
        webhook_secret=None,
        checkout_success_url="https://example.com/success",
        checkout_cancel_url="https://example.com/cancel",
        portal_return_url="https://example.com/portal",
        price_plan_onetime_id=None,
        price_guided_monthly_id=None,
        price_guided_annual_id=None,
        price_premium_monthly_id=None,
        price_premium_annual_id=None,
        price_legacy_pro_monthly_id=None,
        price_strideiq_monthly_id="price_strideiq_m",
        price_strideiq_annual_id="price_strideiq_a",
    )

    def _fake_create_checkout_session(self, *, athlete, tier="subscriber", billing_period="annual"):
        captured["tier"] = tier
        captured["billing_period"] = billing_period
        return "https://stripe.test/checkout"

    monkeypatch.setattr(ss, "_get_stripe_config", lambda: mock_cfg)
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
        assert payload["tier"] == "subscriber"
        assert payload["billing_period"] == "monthly"
        assert captured["tier"] == "subscriber"
        assert captured["billing_period"] == "monthly"
    finally:
        _cleanup_athlete(athlete.email)


def test_trial_checkout_returns_url_for_free_user(monkeypatch):
    """Free user with no active subscription gets a trial checkout URL."""
    from services import stripe_service as ss

    mock_cfg = ss.StripeConfig(
        secret_key="sk_test_dummy",
        webhook_secret=None,
        checkout_success_url="https://example.com/success",
        checkout_cancel_url="https://example.com/cancel",
        portal_return_url="https://example.com/portal",
        price_strideiq_monthly_id="price_strideiq_m",
        price_strideiq_annual_id="price_strideiq_a",
    )

    def _fake_trial_checkout(self, *, athlete, billing_period="monthly",
                             trial_days=30, success_url=None, cancel_url=None):
        return "https://stripe.test/trial-checkout"

    monkeypatch.setattr(ss, "_get_stripe_config", lambda: mock_cfg)
    monkeypatch.setattr(ss.StripeService, "create_trial_checkout_session", _fake_trial_checkout)

    db = SessionLocal()
    athlete = Athlete(
        email=f"trial_ck_{uuid4()}@example.com",
        display_name="TrialCheckout",
        role="athlete",
        subscription_tier="free",
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    db.close()

    try:
        resp = client.post(
            "/v1/billing/checkout/trial",
            headers=_headers(athlete),
            json={"billing_period": "monthly"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["url"] == "https://stripe.test/trial-checkout"
        assert data["trial_days"] == 30
        assert data["amount_due_today"] == "$0.00"
    finally:
        _cleanup_athlete(athlete.email)


def test_trial_checkout_blocked_for_paid_tier(monkeypatch):
    """Subscriber-tier athlete is blocked from trial checkout (409)."""
    from services import stripe_service as ss
    monkeypatch.setattr(ss, "_get_stripe_config", lambda: ss.StripeConfig(
        secret_key="sk_test_dummy", webhook_secret=None,
        checkout_success_url="x", checkout_cancel_url="x", portal_return_url="x",
    ))

    db = SessionLocal()
    athlete = Athlete(
        email=f"trial_paid_{uuid4()}@example.com",
        display_name="PaidTrialBlock",
        role="athlete",
        subscription_tier="subscriber",
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    db.close()

    try:
        resp = client.post(
            "/v1/billing/checkout/trial",
            headers=_headers(athlete),
            json={"billing_period": "monthly"},
        )
        assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"
    finally:
        _cleanup_athlete(athlete.email)


def test_trial_checkout_blocked_for_active_stripe_subscription(monkeypatch):
    """Free-tier athlete with active Stripe subscription is blocked (409)."""
    from services import stripe_service as ss
    monkeypatch.setattr(ss, "_get_stripe_config", lambda: ss.StripeConfig(
        secret_key="sk_test_dummy", webhook_secret=None,
        checkout_success_url="x", checkout_cancel_url="x", portal_return_url="x",
    ))

    db = SessionLocal()
    athlete = Athlete(
        email=f"trial_stripe_{uuid4()}@example.com",
        display_name="StripeTrialBlock",
        role="athlete",
        subscription_tier="free",
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)

    from models import Subscription
    sub = Subscription(
        athlete_id=athlete.id,
        stripe_customer_id="cus_test123",
        stripe_subscription_id="sub_test123",
        status="trialing",
    )
    db.add(sub)
    db.commit()
    db.close()

    try:
        resp = client.post(
            "/v1/billing/checkout/trial",
            headers=_headers(athlete),
            json={"billing_period": "monthly"},
        )
        assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"
    finally:
        db2 = SessionLocal()
        try:
            s = db2.query(Subscription).filter(Subscription.athlete_id == athlete.id).first()
            if s:
                db2.delete(s)
                db2.commit()
        finally:
            db2.close()
        _cleanup_athlete(athlete.email)


def test_trial_checkout_invalid_billing_period():
    """Invalid billing_period returns 400."""
    db = SessionLocal()
    athlete = Athlete(
        email=f"trial_bad_{uuid4()}@example.com",
        display_name="BadPeriod",
        role="athlete",
        subscription_tier="free",
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    db.close()

    try:
        resp = client.post(
            "/v1/billing/checkout/trial",
            headers=_headers(athlete),
            json={"billing_period": "weekly"},
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
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
