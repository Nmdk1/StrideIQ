"""Unit tests for core/tier_utils.py — canonical tier engine.

These tests are pure logic: no database, no Stripe, no FastAPI.
They cover every path through normalize_tier, tier_level, and tier_satisfies
including all legacy tier strings and the fail-closed unknown-tier behavior.
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

    def test_guided_passthrough(self):
        assert normalize_tier("guided") == "guided"

    def test_premium_passthrough(self):
        assert normalize_tier("premium") == "premium"

    # Legacy tiers all collapse to premium.
    def test_pro_maps_to_premium(self):
        assert normalize_tier("pro") == "premium"

    def test_elite_maps_to_premium(self):
        assert normalize_tier("elite") == "premium"

    def test_subscription_maps_to_premium(self):
        assert normalize_tier("subscription") == "premium"

    # Fail-closed: unknown strings → free.
    def test_unknown_string_maps_to_free(self):
        assert normalize_tier("gold") == "free"

    def test_empty_string_maps_to_free(self):
        assert normalize_tier("") == "free"

    def test_none_maps_to_free(self):
        assert normalize_tier(None) == "free"

    # Case insensitivity.
    def test_uppercase_pro_maps_to_premium(self):
        assert normalize_tier("PRO") == "premium"

    def test_mixed_case_guided(self):
        assert normalize_tier("Guided") == "guided"

    def test_whitespace_stripped(self):
        assert normalize_tier("  premium  ") == "premium"


# ===========================================================================
# tier_level
# ===========================================================================

class TestTierLevel:
    """tier_level returns the numeric level for a tier string."""

    def test_free_is_zero(self):
        assert tier_level("free") == 0

    def test_guided_is_one(self):
        assert tier_level("guided") == 1

    def test_premium_is_two(self):
        assert tier_level("premium") == 2

    # Legacy tiers map to premium level.
    def test_pro_level_equals_premium(self):
        assert tier_level("pro") == 2

    def test_elite_level_equals_premium(self):
        assert tier_level("elite") == 2

    def test_subscription_level_equals_premium(self):
        assert tier_level("subscription") == 2

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

    def test_guided_satisfies_guided(self):
        assert tier_satisfies("guided", "guided") is True

    def test_premium_satisfies_premium(self):
        assert tier_satisfies("premium", "premium") is True

    # Higher tier satisfies lower requirement.
    def test_premium_satisfies_guided(self):
        assert tier_satisfies("premium", "guided") is True

    def test_premium_satisfies_free(self):
        assert tier_satisfies("premium", "free") is True

    def test_guided_satisfies_free(self):
        assert tier_satisfies("guided", "free") is True

    # Lower tier does NOT satisfy higher requirement.
    def test_guided_does_not_satisfy_premium(self):
        assert tier_satisfies("guided", "premium") is False

    def test_free_does_not_satisfy_guided(self):
        assert tier_satisfies("free", "guided") is False

    def test_free_does_not_satisfy_premium(self):
        assert tier_satisfies("free", "premium") is False

    # Legacy tier backward compat.
    def test_pro_satisfies_guided(self):
        """Legacy 'pro' maps to premium (level 2) which satisfies guided (level 1)."""
        assert tier_satisfies("pro", "guided") is True

    def test_pro_satisfies_premium(self):
        """Legacy 'pro' maps to premium — satisfies premium check."""
        assert tier_satisfies("pro", "premium") is True

    def test_elite_satisfies_premium(self):
        assert tier_satisfies("elite", "premium") is True

    def test_subscription_satisfies_guided(self):
        assert tier_satisfies("subscription", "guided") is True

    # Fail-closed: None / unknown does not satisfy paid tiers.
    def test_none_does_not_satisfy_guided(self):
        assert tier_satisfies(None, "guided") is False

    def test_unknown_does_not_satisfy_guided(self):
        assert tier_satisfies("diamond", "guided") is False

    def test_none_satisfies_free(self):
        """None → free → satisfies free requirement."""
        assert tier_satisfies(None, "free") is True
