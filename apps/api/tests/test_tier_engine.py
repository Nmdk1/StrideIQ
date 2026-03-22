"""Unit tests for core/tier_utils.py — canonical tier engine.

These tests are pure logic: no database, no Stripe, no FastAPI.
They cover every path through normalize_tier, tier_level, and tier_satisfies
under the two-tier contract with backward-compatible normalization.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.tier_utils import normalize_tier, tier_level, tier_satisfies


# ===========================================================================
# normalize_tier
# ===========================================================================

class TestNormalizeTier:
    """normalize_tier maps any input to a canonical tier string."""

    # Canonical tiers pass through unchanged.
    def test_free_passthrough(self):
        assert normalize_tier("free") == "free"

    def test_subscriber_passthrough(self):
        assert normalize_tier("subscriber") == "subscriber"

    # Legacy paid labels all collapse to subscriber.
    def test_guided_maps_to_subscriber(self):
        assert normalize_tier("guided") == "subscriber"

    def test_premium_maps_to_subscriber(self):
        assert normalize_tier("premium") == "subscriber"

    def test_pro_maps_to_subscriber(self):
        assert normalize_tier("pro") == "subscriber"

    def test_elite_maps_to_subscriber(self):
        assert normalize_tier("elite") == "subscriber"

    def test_subscription_maps_to_subscriber(self):
        assert normalize_tier("subscription") == "subscriber"

    # Fail-closed: unknown strings → free.
    def test_unknown_string_maps_to_free(self):
        assert normalize_tier("gold") == "free"

    def test_empty_string_maps_to_free(self):
        assert normalize_tier("") == "free"

    def test_none_maps_to_free(self):
        assert normalize_tier(None) == "free"

    # Case insensitivity.
    def test_uppercase_pro_maps_to_subscriber(self):
        assert normalize_tier("PRO") == "subscriber"

    def test_mixed_case_guided(self):
        assert normalize_tier("Guided") == "subscriber"

    def test_whitespace_stripped(self):
        assert normalize_tier("  subscriber  ") == "subscriber"


# ===========================================================================
# tier_level
# ===========================================================================

class TestTierLevel:
    """tier_level returns the numeric level for a tier string."""

    def test_free_is_zero(self):
        assert tier_level("free") == 0

    def test_subscriber_is_one(self):
        assert tier_level("subscriber") == 1

    # Legacy paid labels map to subscriber level.
    def test_pro_level_equals_subscriber(self):
        assert tier_level("pro") == 1

    def test_elite_level_equals_subscriber(self):
        assert tier_level("elite") == 1

    def test_subscription_level_equals_subscriber(self):
        assert tier_level("subscription") == 1

    # Fail-closed: unknown → 0 (same as free).
    def test_unknown_level_is_zero(self):
        assert tier_level("platinum") == 0

    def test_none_level_is_zero(self):
        assert tier_level(None) == 0


# ===========================================================================
# tier_satisfies
# ===========================================================================

class TestTierSatisfies:
    """tier_satisfies checks actual >= required using canonical hierarchy."""

    # Same-level checks.
    def test_free_satisfies_free(self):
        assert tier_satisfies("free", "free") is True

    def test_subscriber_satisfies_subscriber(self):
        assert tier_satisfies("subscriber", "subscriber") is True

    def test_subscriber_satisfies_free(self):
        assert tier_satisfies("subscriber", "free") is True

    def test_free_does_not_satisfy_subscriber(self):
        assert tier_satisfies("free", "subscriber") is False

    # Legacy tier backward compat through normalization.
    def test_pro_satisfies_subscriber(self):
        assert tier_satisfies("pro", "subscriber") is True

    def test_premium_satisfies_subscriber(self):
        assert tier_satisfies("premium", "subscriber") is True

    def test_guided_satisfies_subscriber(self):
        assert tier_satisfies("guided", "subscriber") is True

    # Fail-closed: None / unknown does not satisfy paid tier.
    def test_none_does_not_satisfy_subscriber(self):
        assert tier_satisfies(None, "subscriber") is False

    def test_unknown_does_not_satisfy_subscriber(self):
        assert tier_satisfies("diamond", "subscriber") is False

    def test_none_satisfies_free(self):
        """None → free → satisfies free requirement."""
        assert tier_satisfies(None, "free") is True
