"""Canonical tier utilities — single source of truth for tier normalization.

All tier comparisons in auth, feature flags, entitlements, and routers
MUST route through here. Do not perform raw string equality checks against
tier values anywhere else in the codebase.

Canonical tiers (lowest → highest):
    free       = 0
    subscriber = 1

Legacy tier mapping (all historical paid labels collapse to subscriber):
    guided | premium | pro | elite | subscription → subscriber

Fail-closed policy: unknown or None tier values always resolve to "free".
"""
from typing import Literal

CanonicalTier = Literal["free", "subscriber"]

# All historical tier names that map to the canonical paid tier.
_LEGACY_TO_CANONICAL: dict[str, CanonicalTier] = {
    "guided": "subscriber",
    "premium": "subscriber",
    "pro": "subscriber",
    "elite": "subscriber",
    "subscription": "subscriber",
}

_CANONICAL_LEVELS: dict[str, int] = {
    "free": 0,
    "subscriber": 1,
}


def normalize_tier(tier: str | None) -> CanonicalTier:
    """Map any tier string (including legacy) to a canonical tier.

    Fail-closed: unknown / None → "free".
    """
    if not tier:
        return "free"
    t = tier.strip().lower()
    if t in _CANONICAL_LEVELS:
        return t  # type: ignore[return-value]
    return _LEGACY_TO_CANONICAL.get(t, "free")


def tier_level(tier: str | None) -> int:
    """Return numeric level for tier.

    free=0, subscriber=1. Unknown / None → 0.
    """
    return _CANONICAL_LEVELS.get(normalize_tier(tier), 0)


def tier_satisfies(actual: str | None, required: str) -> bool:
    """Return True if ``actual`` tier meets or exceeds ``required``.

    Examples::

        tier_satisfies("subscriber", "subscriber") → True   (1 >= 1)
        tier_satisfies("free",       "subscriber") → False  (0 < 1)
        tier_satisfies("premium",    "subscriber") → True   (premium→subscriber)
        tier_satisfies(None,         "subscriber") → False  (0 < 1)
        tier_satisfies("unknown", "free")    → True   (unknown→free=0 >= 0)
    """
    return tier_level(actual) >= tier_level(required)
