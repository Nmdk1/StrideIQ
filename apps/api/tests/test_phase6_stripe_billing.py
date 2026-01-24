from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models import Athlete, StripeEvent, Subscription


client = TestClient(app)


def _headers(user: Athlete) -> dict:
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


class _DummyStripeConfig:
    def __init__(self):
        self.secret_key = "sk_test_dummy"
        self.webhook_secret = "whsec_dummy"
        self.pro_monthly_price_id = "price_dummy"
        self.checkout_success_url = "http://localhost:3000/settings?success=1"
        self.checkout_cancel_url = "http://localhost:3000/settings?canceled=1"
        self.portal_return_url = "http://localhost:3000/settings"


class _DummyEvent:
    def __init__(self, event_id: str, event_type: str, obj):
        self.id = event_id
        self.type = event_type
        self.created = 123

        class _Data:
            def __init__(self, o):
                self.object = o

        self.data = _Data(obj)


class _DummySubObj:
    def __init__(self, *, customer: str, subscription_id: str, status: str):
        self.customer = customer
        self.id = subscription_id
        self.status = status
        # Newer Stripe API versions place billing period fields on subscription items.
        # Keep top-level period fields absent to ensure our compatibility parsing works.
        self.cancel_at_period_end = False
        self.cancel_at = None
        item = type("item", (), {"current_period_end": 1234567890, "price": type("price", (), {"id": "price_dummy"})()})()
        self.items = type("items", (), {"data": [item]})


def test_checkout_and_portal_endpoints(monkeypatch):
    from services import stripe_service as ss

    monkeypatch.setattr(ss, "_get_stripe_config", lambda: _DummyStripeConfig())
    monkeypatch.setattr(ss.StripeService, "create_checkout_session", lambda self, athlete: "https://stripe.test/checkout")
    monkeypatch.setattr(ss.StripeService, "create_portal_session", lambda self, athlete: "https://stripe.test/portal")
    monkeypatch.setattr(ss.StripeService, "best_effort_sync_customer_subscription", lambda self, db, athlete: None)

    db = SessionLocal()
    try:
        user = Athlete(email=f"stripe_{uuid4()}@example.com", display_name="Stripe", role="athlete", subscription_tier="free")
        user.stripe_customer_id = "cus_123"
        db.add(user)
        db.commit()
        db.refresh(user)

        resp = client.post("/v1/billing/checkout", headers=_headers(user))
        assert resp.status_code == 200
        assert resp.json()["url"].startswith("https://stripe.test/")

        resp = client.post("/v1/billing/portal", headers=_headers(user))
        assert resp.status_code == 200
        assert resp.json()["url"].startswith("https://stripe.test/")
    finally:
        # Cleanup
        try:
            db.query(StripeEvent).delete(synchronize_session=False)
            db.query(Subscription).delete(synchronize_session=False)
            db.query(Athlete).filter(Athlete.email.like("stripe_%@example.com")).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()


def test_stripe_webhook_requires_signature_header():
    resp = client.post("/v1/billing/webhooks/stripe", data=b"{}")
    assert resp.status_code == 400


def test_webhook_idempotency_and_entitlement_update(monkeypatch):
    from services import stripe_service as ss

    monkeypatch.setattr(ss, "_get_stripe_config", lambda: _DummyStripeConfig())

    db = SessionLocal()
    try:
        user = Athlete(
            email=f"stripe_evt_{uuid4()}@example.com",
            display_name="StripeEvt",
            role="athlete",
            subscription_tier="free",
            stripe_customer_id="cus_evt_1",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    finally:
        db.close()

    def _construct(self, payload: bytes, sig_header: str):
        obj = _DummySubObj(customer="cus_evt_1", subscription_id="sub_1", status="active")
        return _DummyEvent("evt_1", "customer.subscription.updated", obj)

    monkeypatch.setattr(ss.StripeService, "construct_event", _construct)

    # First delivery processes
    resp = client.post("/v1/billing/webhooks/stripe", data=b"{}", headers={"Stripe-Signature": "sig"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # Second delivery is idempotent
    resp2 = client.post("/v1/billing/webhooks/stripe", data=b"{}", headers={"Stripe-Signature": "sig"})
    assert resp2.status_code == 200

    db = SessionLocal()
    try:
        updated = db.query(Athlete).filter(Athlete.email.like("stripe_evt_%@example.com")).first()
        assert updated is not None
        assert updated.subscription_tier == "pro"

        ev_count = db.query(StripeEvent).filter(StripeEvent.event_id == "evt_1").count()
        assert ev_count == 1

        sub = db.query(Subscription).filter(Subscription.athlete_id == updated.id).first()
        assert sub is not None
        assert sub.status == "active"
        assert sub.stripe_customer_id == "cus_evt_1"
        assert sub.stripe_subscription_id == "sub_1"
    finally:
        try:
            db.query(StripeEvent).delete(synchronize_session=False)
            db.query(Subscription).delete(synchronize_session=False)
            db.query(Athlete).filter(Athlete.email.like("stripe_evt_%@example.com")).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

