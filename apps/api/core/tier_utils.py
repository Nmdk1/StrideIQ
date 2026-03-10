"""Canonical tier utilities — single source of truth for tier normalization.

All tier comparisons in auth, feature flags, entitlements, and routers
MUST route through here. Do not perform raw string equality checks against
tier values anywhere else in the codebase.

Canonical tiers (lowest → highest):
    free     = 0
    guided   = 1
    premium  = 2

Legacy tier mapping (all legacy paid tiers collapse to premium):
    pro | elite | subscription → premium

Fail-closed policy: unknown or None tier values always resolve to "free".
"""
from typing import Literal

CanonicalTier = Literal["free", "guided", "premium"]

# All tier names that map to the canonical "premium" level.
# These predate the 4-tier model and are preserved here for the migration window.
_LEGACY_TO_CANONICAL: dict[str, CanonicalTier] = {
    "pro": "premium",
    "elite": "premium",
    "subscription": "premium",
}

_CANONICAL_LEVELS: dict[str, int] = {
    "free": 0,
    "guided": 1,
    "premium": 2,
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

    free=0, guided=1, premium=2. Unknown / None → 0.
    """
    return _CANONICAL_LEVELS.get(normalize_tier(tier), 0)


def tier_satisfies(actual: str | None, required: str) -> bool:
    """Return True if ``actual`` tier meets or exceeds ``required``.

    Examples::

        tier_satisfies("premium", "guided")  → True   (2 >= 1)
        tier_satisfies("guided",  "premium") → False  (1 < 2)
        tier_satisfies("pro",     "guided")  → True   (pro→premium=2 >= 1)
        tier_satisfies(None,      "guided")  → False  (0 < 1)
        tier_satisfies("unknown", "free")    → True   (unknown→free=0 >= 0)
    """
    return tier_level(actual) >= tier_level(required)
