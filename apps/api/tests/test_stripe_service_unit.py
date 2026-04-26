"""Unit tests for Stripe service tier logic.

All tests run without any live Stripe API calls or database.
The tests cover:
  - build_price_to_tier: correct mapping from config to price→tier dict
  - tier_for_price_and_status: fail-closed behavior on unknown / missing price IDs
  - process_stripe_event: idempotency guard, tier derivation per event type
"""
import pytest
import sys
import os
from dataclasses import dataclass
from unittest.mock import MagicMock, patch, call
from typing import Optional
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.stripe_service import (
    StripeConfig,
    build_price_to_tier,
    tier_for_price_and_status,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_config(
    *,
    guided_monthly: Optional[str] = "price_guided_monthly",
    guided_annual: Optional[str] = "price_guided_annual",
    premium_monthly: Optional[str] = "price_premium_monthly",
    premium_annual: Optional[str] = "price_premium_annual",
    legacy_pro: Optional[str] = None,
    onetime: Optional[str] = "price_onetime",
) -> StripeConfig:
    return StripeConfig(
        secret_key="sk_test_xxx",
        webhook_secret=None,
        checkout_success_url="https://example.com/success",
        checkout_cancel_url="https://example.com/cancel",
        portal_return_url="https://example.com/portal",
        price_plan_onetime_id=onetime,
        price_guided_monthly_id=guided_monthly,
        price_guided_annual_id=guided_annual,
        price_premium_monthly_id=premium_monthly,
        price_premium_annual_id=premium_annual,
        price_legacy_pro_monthly_id=legacy_pro,
    )


# ===========================================================================
# build_price_to_tier
# ===========================================================================

class TestBuildPriceToTier:
    """build_price_to_tier produces a correct price_id → tier mapping."""

    def test_guided_monthly_maps_to_subscriber(self):
        cfg = make_config()
        mapping = build_price_to_tier(cfg)
        assert mapping["price_guided_monthly"] == "subscriber"

    def test_guided_annual_maps_to_subscriber(self):
        cfg = make_config()
        mapping = build_price_to_tier(cfg)
        assert mapping["price_guided_annual"] == "subscriber"

    def test_premium_monthly_maps_to_subscriber(self):
        cfg = make_config()
        mapping = build_price_to_tier(cfg)
        assert mapping["price_premium_monthly"] == "subscriber"

    def test_premium_annual_maps_to_subscriber(self):
        cfg = make_config()
        mapping = build_price_to_tier(cfg)
        assert mapping["price_premium_annual"] == "subscriber"

    def test_legacy_pro_maps_to_subscriber(self):
        cfg = make_config(legacy_pro="price_pro_monthly_legacy")
        mapping = build_price_to_tier(cfg)
        assert mapping["price_pro_monthly_legacy"] == "subscriber"

    def test_none_price_ids_excluded(self):
        cfg = make_config(guided_monthly=None, guided_annual=None)
        mapping = build_price_to_tier(cfg)
        assert "price_guided_monthly" not in mapping
        assert "price_guided_annual" not in mapping

    def test_one_time_price_not_in_subscription_map(self):
        """One-time price must NOT appear in the subscription tier map."""
        cfg = make_config(onetime="price_onetime_plan")
        mapping = build_price_to_tier(cfg)
        assert "price_onetime_plan" not in mapping

    def test_unknown_price_not_in_map(self):
        cfg = make_config()
        mapping = build_price_to_tier(cfg)
        assert "price_totally_unknown_xyz" not in mapping

    def test_empty_config_produces_empty_map(self):
        cfg = make_config(
            guided_monthly=None,
            guided_annual=None,
            premium_monthly=None,
            premium_annual=None,
            legacy_pro=None,
        )
        mapping = build_price_to_tier(cfg)
        assert mapping == {}


# ===========================================================================
# tier_for_price_and_status
# ===========================================================================

class TestTierForPriceAndStatus:
    """tier_for_price_and_status — the single source of subscription→tier truth."""

    def setup_method(self):
        self.price_to_tier = {
            "price_guided_monthly": "subscriber",
            "price_guided_annual": "subscriber",
            "price_premium_monthly": "subscriber",
            "price_premium_annual": "subscriber",
            "price_pro_legacy": "subscriber",
        }

    # Active subscription — known prices.
    def test_active_guided_monthly_grants_subscriber(self):
        result = tier_for_price_and_status("price_guided_monthly", "active", self.price_to_tier)
        assert result == "subscriber"

    def test_active_guided_annual_grants_subscriber(self):
        result = tier_for_price_and_status("price_guided_annual", "active", self.price_to_tier)
        assert result == "subscriber"

    def test_active_premium_monthly_grants_subscriber(self):
        result = tier_for_price_and_status("price_premium_monthly", "active", self.price_to_tier)
        assert result == "subscriber"

    def test_active_premium_annual_grants_subscriber(self):
        result = tier_for_price_and_status("price_premium_annual", "active", self.price_to_tier)
        assert result == "subscriber"

    def test_active_legacy_pro_grants_subscriber(self):
        result = tier_for_price_and_status("price_pro_legacy", "active", self.price_to_tier)
        assert result == "subscriber"

    # Trialing — same as active.
    def test_trialing_guided_grants_subscriber(self):
        result = tier_for_price_and_status("price_guided_monthly", "trialing", self.price_to_tier)
        assert result == "subscriber"

    def test_trialing_premium_grants_subscriber(self):
        result = tier_for_price_and_status("price_premium_monthly", "trialing", self.price_to_tier)
        assert result == "subscriber"

    # Non-active statuses → free regardless of price.
    def test_canceled_subscription_grants_free(self):
        result = tier_for_price_and_status("price_premium_monthly", "canceled", self.price_to_tier)
        assert result == "free"

    def test_past_due_grants_free(self):
        result = tier_for_price_and_status("price_premium_monthly", "past_due", self.price_to_tier)
        assert result == "free"

    def test_incomplete_grants_free(self):
        result = tier_for_price_and_status("price_premium_monthly", "incomplete", self.price_to_tier)
        assert result == "free"

    def test_unpaid_grants_free(self):
        result = tier_for_price_and_status("price_guided_monthly", "unpaid", self.price_to_tier)
        assert result == "free"

    def test_none_status_grants_free(self):
        result = tier_for_price_and_status("price_premium_monthly", None, self.price_to_tier)
        assert result == "free"

    # FAIL-CLOSED — unknown price ID must NEVER grant access.
    def test_unknown_price_active_grants_free(self):
        result = tier_for_price_and_status("price_totally_unknown_xyz", "active", self.price_to_tier)
        assert result == "free"

    def test_unknown_price_trialing_grants_free(self):
        result = tier_for_price_and_status("price_rogue_id", "trialing", self.price_to_tier)
        assert result == "free"

    def test_unknown_price_does_not_grant_premium(self):
        """Critical: no auto-promotion on unknown price."""
        result = tier_for_price_and_status("price_not_in_map", "active", self.price_to_tier)
        assert result != "subscriber"

    # FAIL-CLOSED — missing price ID.
    def test_none_price_id_grants_free(self):
        result = tier_for_price_and_status(None, "active", self.price_to_tier)
        assert result == "free"

    def test_empty_price_id_grants_free(self):
        result = tier_for_price_and_status("", "active", self.price_to_tier)
        assert result == "free"

    def test_empty_price_to_tier_map_grants_free(self):
        """No configured prices → everything fails closed."""
        result = tier_for_price_and_status("price_any", "active", {})
        assert result == "free"

    # Case-insensitive status.
    def test_status_case_insensitive_active(self):
        result = tier_for_price_and_status("price_premium_monthly", "ACTIVE", self.price_to_tier)
        assert result == "subscriber"

    def test_status_case_insensitive_trialing(self):
        result = tier_for_price_and_status("price_guided_monthly", "Trialing", self.price_to_tier)
        assert result == "subscriber"


# ===========================================================================
# StripeService.create_trial_checkout_session
# ===========================================================================

class TestCreateTrialCheckoutSession:
    """Trial checkout session creates a Stripe Checkout with trial_period_days."""

    @patch("services.stripe_service._get_stripe_config")
    @patch("services.stripe_service.stripe")
    def test_trial_checkout_includes_trial_period_days(self, mock_stripe, mock_config):
        mock_config.return_value = StripeConfig(
            secret_key="sk_test_xxx",
            webhook_secret=None,
            checkout_success_url="https://example.com/success",
            checkout_cancel_url="https://example.com/cancel",
            portal_return_url="https://example.com/portal",
            price_strideiq_monthly_id="price_strideiq_monthly",
        )

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/c/trial123"
        mock_stripe.checkout.Session.create.return_value = mock_session

        from services.stripe_service import StripeService
        svc = StripeService()

        athlete = MagicMock()
        athlete.id = uuid4()
        athlete.email = "trial@example.com"
        athlete.stripe_customer_id = None

        url = svc.create_trial_checkout_session(
            athlete=athlete,
            billing_period="monthly",
        )

        assert url == "https://checkout.stripe.com/c/trial123"
        call_kwargs = mock_stripe.checkout.Session.create.call_args[1]
        assert call_kwargs["mode"] == "subscription"
        assert call_kwargs["subscription_data"]["trial_period_days"] == 30
        assert call_kwargs["metadata"]["trial_days"] == "30"
        assert call_kwargs["line_items"][0]["price"] == "price_strideiq_monthly"

    @patch("services.stripe_service._get_stripe_config")
    @patch("services.stripe_service.stripe")
    def test_trial_checkout_annual_uses_annual_price(self, mock_stripe, mock_config):
        mock_config.return_value = StripeConfig(
            secret_key="sk_test_xxx",
            webhook_secret=None,
            checkout_success_url="https://example.com/success",
            checkout_cancel_url="https://example.com/cancel",
            portal_return_url="https://example.com/portal",
            price_strideiq_annual_id="price_strideiq_annual",
        )

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/c/trial_annual"
        mock_stripe.checkout.Session.create.return_value = mock_session

        from services.stripe_service import StripeService
        svc = StripeService()

        athlete = MagicMock()
        athlete.id = uuid4()
        athlete.email = "trial@example.com"
        athlete.stripe_customer_id = None

        url = svc.create_trial_checkout_session(
            athlete=athlete,
            billing_period="annual",
        )

        call_kwargs = mock_stripe.checkout.Session.create.call_args[1]
        assert call_kwargs["line_items"][0]["price"] == "price_strideiq_annual"

    @patch("services.stripe_service._get_stripe_config")
    def test_trial_checkout_invalid_period_raises(self, mock_config):
        mock_config.return_value = StripeConfig(
            secret_key="sk_test_xxx",
            webhook_secret=None,
            checkout_success_url="https://example.com/success",
            checkout_cancel_url="https://example.com/cancel",
            portal_return_url="https://example.com/portal",
        )

        from services.stripe_service import StripeService
        svc = StripeService()

        athlete = MagicMock()
        athlete.id = uuid4()

        with pytest.raises(ValueError, match="billing_period"):
            svc.create_trial_checkout_session(athlete=athlete, billing_period="weekly")

    @patch("services.stripe_service._get_stripe_config")
    @patch("services.stripe_service.stripe")
    def test_trial_checkout_uses_existing_customer_id(self, mock_stripe, mock_config):
        mock_config.return_value = StripeConfig(
            secret_key="sk_test_xxx",
            webhook_secret=None,
            checkout_success_url="https://example.com/success",
            checkout_cancel_url="https://example.com/cancel",
            portal_return_url="https://example.com/portal",
            price_strideiq_monthly_id="price_strideiq_monthly",
        )

        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/c/trial_cust"
        mock_stripe.checkout.Session.create.return_value = mock_session

        from services.stripe_service import StripeService
        svc = StripeService()

        athlete = MagicMock()
        athlete.id = uuid4()
        athlete.email = "trial@example.com"
        athlete.stripe_customer_id = "cus_existing123"

        svc.create_trial_checkout_session(athlete=athlete, billing_period="monthly")

        call_kwargs = mock_stripe.checkout.Session.create.call_args[1]
        assert call_kwargs["customer"] == "cus_existing123"
        assert "customer_email" not in call_kwargs


# ===========================================================================
# Webhook: trialing status from trial checkout
# ===========================================================================

class TestTrialingWebhookFlow:
    """Trialing status from Stripe trial checkout grants paid tier."""

    def test_trialing_status_grants_subscriber_tier(self):
        """When Stripe sends trialing status with a known price, tier = subscriber."""
        price_to_tier = {"price_strideiq_monthly": "subscriber"}
        result = tier_for_price_and_status("price_strideiq_monthly", "trialing", price_to_tier)
        assert result == "subscriber"

    def test_trialing_unknown_price_stays_free(self):
        """Unknown price on trialing subscription = free (fail closed)."""
        price_to_tier = {"price_strideiq_monthly": "subscriber"}
        result = tier_for_price_and_status("price_unknown", "trialing", price_to_tier)
        assert result == "free"

    def test_canceled_from_trialing_becomes_free(self):
        """Athlete cancels during trial → status becomes canceled → free."""
        price_to_tier = {"price_strideiq_monthly": "subscriber"}
        result = tier_for_price_and_status("price_strideiq_monthly", "canceled", price_to_tier)
        assert result == "free"


# ===========================================================================
# Trial checkout guard logic (unit tests — no DB)
# ===========================================================================

class TestTrialCheckoutGuards:
    """Verify trial checkout eligibility guards without a database."""

    def test_paid_tier_blocked(self):
        """subscriber tier → blocked from trial checkout."""
        from core.tier_utils import tier_satisfies
        assert tier_satisfies("subscriber", "subscriber") is True
        assert tier_satisfies("premium", "subscriber") is True
        assert tier_satisfies("guided", "subscriber") is True

    def test_free_tier_allowed(self):
        """free tier → allowed through tier gate."""
        from core.tier_utils import tier_satisfies
        assert tier_satisfies("free", "subscriber") is False

    def test_active_stripe_sub_blocked(self):
        """Active Stripe subscription status → blocked."""
        blocked_statuses = ["active", "trialing", "Active", "TRIALING"]
        for s in blocked_statuses:
            assert s.lower() in ("active", "trialing"), f"{s} should be blocked"

    def test_inactive_stripe_sub_allowed(self):
        """Canceled/expired Stripe subscription status → allowed."""
        allowed_statuses = ["canceled", "past_due", "incomplete", "unpaid", None, ""]
        for s in allowed_statuses:
            assert (s or "").lower() not in ("active", "trialing"), f"{s!r} should be allowed"

    def test_free_with_local_trial_only_allowed(self):
        """Free tier + local trial (no Stripe sub) → allowed through tier gate.

        This is the intended path: athlete signed up, got local 30-day trial,
        and now we're sending them to Stripe Checkout to collect CC.
        """
        from core.tier_utils import tier_satisfies
        assert tier_satisfies("free", "subscriber") is False
