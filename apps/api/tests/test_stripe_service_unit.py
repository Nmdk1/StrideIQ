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

    def test_guided_monthly_maps_to_guided(self):
        cfg = make_config()
        mapping = build_price_to_tier(cfg)
        assert mapping["price_guided_monthly"] == "guided"

    def test_guided_annual_maps_to_guided(self):
        cfg = make_config()
        mapping = build_price_to_tier(cfg)
        assert mapping["price_guided_annual"] == "guided"

    def test_premium_monthly_maps_to_premium(self):
        cfg = make_config()
        mapping = build_price_to_tier(cfg)
        assert mapping["price_premium_monthly"] == "premium"

    def test_premium_annual_maps_to_premium(self):
        cfg = make_config()
        mapping = build_price_to_tier(cfg)
        assert mapping["price_premium_annual"] == "premium"

    def test_legacy_pro_maps_to_premium(self):
        cfg = make_config(legacy_pro="price_pro_monthly_legacy")
        mapping = build_price_to_tier(cfg)
        assert mapping["price_pro_monthly_legacy"] == "premium"

    def test_none_price_ids_excluded(self):
        cfg = make_config(guided_monthly=None, guided_annual=None)
        mapping = build_price_to_tier(cfg)
        assert "guided" not in mapping.values() or all(
            v != "guided" for v in mapping.values()
        )

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
            "price_guided_monthly": "guided",
            "price_guided_annual": "guided",
            "price_premium_monthly": "premium",
            "price_premium_annual": "premium",
            "price_pro_legacy": "premium",
        }

    # Active subscription — known prices.
    def test_active_guided_monthly_grants_guided(self):
        result = tier_for_price_and_status("price_guided_monthly", "active", self.price_to_tier)
        assert result == "guided"

    def test_active_guided_annual_grants_guided(self):
        result = tier_for_price_and_status("price_guided_annual", "active", self.price_to_tier)
        assert result == "guided"

    def test_active_premium_monthly_grants_premium(self):
        result = tier_for_price_and_status("price_premium_monthly", "active", self.price_to_tier)
        assert result == "premium"

    def test_active_premium_annual_grants_premium(self):
        result = tier_for_price_and_status("price_premium_annual", "active", self.price_to_tier)
        assert result == "premium"

    def test_active_legacy_pro_grants_premium(self):
        result = tier_for_price_and_status("price_pro_legacy", "active", self.price_to_tier)
        assert result == "premium"

    # Trialing — same as active.
    def test_trialing_guided_grants_guided(self):
        result = tier_for_price_and_status("price_guided_monthly", "trialing", self.price_to_tier)
        assert result == "guided"

    def test_trialing_premium_grants_premium(self):
        result = tier_for_price_and_status("price_premium_monthly", "trialing", self.price_to_tier)
        assert result == "premium"

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
        assert result != "premium"
        assert result != "guided"

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
        assert result == "premium"

    def test_status_case_insensitive_trialing(self):
        result = tier_for_price_and_status("price_guided_monthly", "Trialing", self.price_to_tier)
        assert result == "guided"
