"""
Tests for the admin comp override precedence contract.

Four required tests from BUILDER_INSTRUCTIONS_2026-03-16:
1. test_admin_comp_sets_override_fields
2. test_stripe_sync_does_not_override_manual_comp
3. test_clear_override_reenables_stripe_authority
4. test_vip_toggle_does_not_mutate_subscription_tier
"""
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models import Athlete, AdminAuditEvent

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def admin_user():
    db = SessionLocal()
    athlete = Athlete(
        email=f"admin_override_{uuid4()}@example.com",
        display_name="Admin",
        subscription_tier="subscriber",
        role="admin",
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    db.close()
    return athlete


@pytest.fixture
def admin_headers(admin_user):
    token = create_access_token({"sub": str(admin_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def target_user():
    db = SessionLocal()
    athlete = Athlete(
        email=f"target_override_{uuid4()}@example.com",
        display_name="Target",
        subscription_tier="free",
        role="athlete",
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    db.close()
    return athlete


def _cleanup(*athletes):
    db = SessionLocal()
    try:
        for a in athletes:
            if a is None:
                continue
            row = db.query(Athlete).filter(Athlete.id == a.id).first()
            if row:
                # remove audit events too
                db.query(AdminAuditEvent).filter(
                    AdminAuditEvent.target_athlete_id == a.id
                ).delete(synchronize_session=False)
                db.delete(row)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 1: comp sets override fields + audit event
# ---------------------------------------------------------------------------

def test_admin_comp_sets_override_fields(admin_headers, admin_user, target_user):
    resp = client.post(
        f"/v1/admin/users/{target_user.id}/comp",
        json={"tier": "subscriber", "reason": "sponsor deal"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["success"] is True
    assert payload["user"]["subscription_tier"] == "subscriber"
    assert payload["user"]["admin_tier_override"] == "subscriber"
    assert payload["user"]["admin_tier_override_set_at"] is not None

    db = SessionLocal()
    try:
        row = db.query(Athlete).filter(Athlete.id == target_user.id).first()
        assert row is not None
        assert row.subscription_tier == "subscriber"
        assert row.admin_tier_override == "subscriber"
        assert row.admin_tier_override_set_by == admin_user.id
        assert row.admin_tier_override_set_at is not None
        assert row.admin_tier_override_reason == "sponsor deal"

        ev = (
            db.query(AdminAuditEvent)
            .filter(
                AdminAuditEvent.actor_athlete_id == admin_user.id,
                AdminAuditEvent.target_athlete_id == target_user.id,
                AdminAuditEvent.action == "billing.comp",
            )
            .order_by(AdminAuditEvent.created_at.desc())
            .first()
        )
        assert ev is not None
    finally:
        db.close()
        _cleanup(target_user, admin_user)


# ---------------------------------------------------------------------------
# Test 2: Stripe sync MUST NOT revert a manual comp override
# ---------------------------------------------------------------------------

def test_stripe_sync_does_not_override_manual_comp(target_user):
    """
    Athlete has admin_tier_override='premium'.
    Stripe best_effort_sync would derive 'free' (canceled sub).
    Effective subscription_tier must remain 'subscriber'.
    """
    # Set up override directly in DB.
    db = SessionLocal()
    try:
        row = db.query(Athlete).filter(Athlete.id == target_user.id).first()
        row.subscription_tier = "subscriber"
        row.admin_tier_override = "subscriber"
        db.commit()
        db.refresh(row)
    finally:
        db.close()

    from services.stripe_service import StripeService, StripeConfig

    mock_cfg = StripeConfig(
        secret_key="sk_test_x",
        webhook_secret=None,
        checkout_success_url="https://x.com",
        checkout_cancel_url="https://x.com",
        portal_return_url="https://x.com",
        price_plan_onetime_id=None,
        price_guided_monthly_id=None,
        price_guided_annual_id=None,
        price_premium_monthly_id=None,
        price_premium_annual_id=None,
        price_legacy_pro_monthly_id=None,
    )

    # Mock stripe.Subscription.list to return a canceled subscription at 'free' price.
    mock_sub = MagicMock()
    mock_sub.status = "canceled"
    mock_sub.id = "sub_fake"
    mock_price = MagicMock()
    mock_price.id = "price_free"
    mock_item = MagicMock()
    mock_item.price = mock_price
    mock_items = MagicMock()
    mock_items.data = [mock_item]
    mock_sub.items = mock_items

    mock_resp = MagicMock()
    mock_resp.data = [mock_sub]

    db2 = SessionLocal()
    try:
        row2 = db2.query(Athlete).filter(Athlete.id == target_user.id).first()
        row2.stripe_customer_id = "cus_fake"
        db2.commit()
        db2.refresh(row2)

        with patch("services.stripe_service._get_stripe_config", return_value=mock_cfg), \
             patch("stripe.Subscription.list", return_value=mock_resp):
            svc = StripeService()
            svc.best_effort_sync_customer_subscription(db2, athlete=row2)

        db2.refresh(row2)
        # Must remain subscriber — override locks the tier.
        assert row2.subscription_tier == "subscriber", (
            f"Stripe sync reverted comp override: tier is {row2.subscription_tier!r}"
        )
    finally:
        db2.close()
        _cleanup(target_user)


# ---------------------------------------------------------------------------
# Test 3: clear-override reenables Stripe authority
# ---------------------------------------------------------------------------

def test_clear_override_reenables_stripe_authority(admin_headers, admin_user, target_user):
    # Set override.
    db = SessionLocal()
    try:
        row = db.query(Athlete).filter(Athlete.id == target_user.id).first()
        row.subscription_tier = "subscriber"
        row.admin_tier_override = "subscriber"
        db.commit()
    finally:
        db.close()

    # Clear it via admin endpoint.
    resp = client.post(
        f"/v1/admin/users/{target_user.id}/comp/clear-override",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["success"] is True
    assert payload["user"]["admin_tier_override"] is None

    db2 = SessionLocal()
    try:
        row2 = db2.query(Athlete).filter(Athlete.id == target_user.id).first()
        assert row2.admin_tier_override is None
    finally:
        db2.close()

    # Now Stripe sync should be able to change the tier.
    from services.stripe_service import StripeService, StripeConfig

    mock_cfg2 = StripeConfig(
        secret_key="sk_test_x",
        webhook_secret=None,
        checkout_success_url="https://x.com",
        checkout_cancel_url="https://x.com",
        portal_return_url="https://x.com",
        price_plan_onetime_id=None,
        price_guided_monthly_id=None,
        price_guided_annual_id=None,
        price_premium_monthly_id=None,
        price_premium_annual_id=None,
        price_legacy_pro_monthly_id=None,
    )

    mock_sub = MagicMock()
    mock_sub.status = "canceled"
    mock_sub.id = "sub_fake2"
    mock_price = MagicMock()
    mock_price.id = "price_free"
    mock_item = MagicMock()
    mock_item.price = mock_price
    mock_items = MagicMock()
    mock_items.data = [mock_item]
    mock_sub.items = mock_items
    mock_resp = MagicMock()
    mock_resp.data = [mock_sub]

    db3 = SessionLocal()
    try:
        row3 = db3.query(Athlete).filter(Athlete.id == target_user.id).first()
        row3.stripe_customer_id = "cus_fake2"
        db3.commit()
        db3.refresh(row3)

        with patch("services.stripe_service._get_stripe_config", return_value=mock_cfg2), \
             patch("stripe.Subscription.list", return_value=mock_resp):
            svc2 = StripeService()
            svc2.best_effort_sync_customer_subscription(db3, athlete=row3)

        db3.refresh(row3)
        # With no override, Stripe authority is restored: tier changes to free.
        assert row3.subscription_tier == "free", (
            f"Stripe sync did not resume authority after clear: tier is {row3.subscription_tier!r}"
        )
    finally:
        db3.close()
        _cleanup(target_user, admin_user)


# ---------------------------------------------------------------------------
# Test 4: VIP toggle does not mutate subscription_tier
# ---------------------------------------------------------------------------

def test_vip_toggle_does_not_mutate_subscription_tier(admin_headers, admin_user, target_user):
    # Start with a specific tier.
    db = SessionLocal()
    try:
        row = db.query(Athlete).filter(Athlete.id == target_user.id).first()
        row.subscription_tier = "subscriber"
        row.is_coach_vip = False
        db.commit()
    finally:
        db.close()

    # Toggle VIP on.
    resp = client.post(
        f"/v1/admin/users/{target_user.id}/coach-vip",
        json={"is_vip": True, "reason": "test"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["user"]["is_coach_vip"] is True

    db2 = SessionLocal()
    try:
        row2 = db2.query(Athlete).filter(Athlete.id == target_user.id).first()
        assert row2.is_coach_vip is True
        assert row2.subscription_tier == "subscriber", (
            f"VIP toggle mutated subscription_tier: {row2.subscription_tier!r}"
        )
    finally:
        db2.close()

    # Toggle VIP off.
    resp2 = client.post(
        f"/v1/admin/users/{target_user.id}/coach-vip",
        json={"is_vip": False, "reason": "test"},
        headers=admin_headers,
    )
    assert resp2.status_code == 200

    db3 = SessionLocal()
    try:
        row3 = db3.query(Athlete).filter(Athlete.id == target_user.id).first()
        assert row3.is_coach_vip is False
        assert row3.subscription_tier == "subscriber", (
            f"VIP unset mutated subscription_tier: {row3.subscription_tier!r}"
        )
    finally:
        db3.close()
        _cleanup(target_user, admin_user)
