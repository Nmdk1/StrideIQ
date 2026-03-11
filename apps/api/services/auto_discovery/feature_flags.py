"""
AutoDiscovery feature flag keys and gating helpers.

All controls are data-driven via the existing FeatureFlagService.
No athlete ID, email, or hardcoded founder logic lives here.

Flag keys
─────────
auto_discovery.enabled              — master kill-switch
auto_discovery.loop.rescan          — correlation multi-window rescan
auto_discovery.loop.interaction     — pairwise interaction scan (Phase 0B)
auto_discovery.loop.tuning          — registry tuning loop (Phase 0B)
auto_discovery.mutation.live        — allow live-config mutation (Phase 1+, default off)
auto_discovery.surfacing.athlete    — allow athlete-facing output (Phase 1+, default off)

Athlete allowlist
─────────────────
To restrict to a founder-only pilot, set `rollout_percentage: 0` on the
master flag and add the founder athlete UUID to `allowed_athlete_ids`.
This is the only mechanism; no hardcoded UUIDs belong in this file.
"""

from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Session

from core.feature_flags import is_feature_enabled

# ─── Public flag key constants ─────────────────────────────────────────────

FLAG_SYSTEM_ENABLED = "auto_discovery.enabled"
FLAG_LOOP_RESCAN = "auto_discovery.loop.rescan"
FLAG_LOOP_INTERACTION = "auto_discovery.loop.interaction"
FLAG_LOOP_TUNING = "auto_discovery.loop.tuning"
FLAG_LIVE_MUTATION = "auto_discovery.mutation.live"
FLAG_ATHLETE_SURFACING = "auto_discovery.surfacing.athlete"

# ─── Gating helpers ────────────────────────────────────────────────────────


def is_auto_discovery_enabled(athlete_id: Optional[str], db: Session) -> bool:
    """Return True iff the entire AutoDiscovery system is on for this athlete."""
    return is_feature_enabled(FLAG_SYSTEM_ENABLED, athlete_id, db)


def is_rescan_enabled(athlete_id: Optional[str], db: Session) -> bool:
    """Return True iff the correlation multi-window rescan loop is enabled."""
    return (
        is_auto_discovery_enabled(athlete_id, db)
        and is_feature_enabled(FLAG_LOOP_RESCAN, athlete_id, db)
    )


def is_interaction_enabled(athlete_id: Optional[str], db: Session) -> bool:
    """Return True iff the pairwise interaction loop is enabled (Phase 0B)."""
    return (
        is_auto_discovery_enabled(athlete_id, db)
        and is_feature_enabled(FLAG_LOOP_INTERACTION, athlete_id, db)
    )


def is_tuning_enabled(athlete_id: Optional[str], db: Session) -> bool:
    """Return True iff the registry tuning loop is enabled (Phase 0B)."""
    return (
        is_auto_discovery_enabled(athlete_id, db)
        and is_feature_enabled(FLAG_LOOP_TUNING, athlete_id, db)
    )


def is_live_mutation_enabled(athlete_id: Optional[str], db: Session) -> bool:
    """Return True iff live production config mutation is permitted.

    Phase 0: always returns False regardless of flag state — the flag
    provides the architecture for future phases but is hard-wired off here.
    """
    return False  # Phase 0 hard-guard; remove in Phase 1 after explicit approval


def is_athlete_surfacing_enabled(athlete_id: Optional[str], db: Session) -> bool:
    """Return True iff athlete-facing output surfacing is permitted.

    Phase 0: always returns False — shadow mode only.
    """
    return False  # Phase 0 hard-guard; remove after explicit approval


# ─── Seed helper (for migrations / management commands) ────────────────────

SEED_FLAGS: list[dict] = [
    {
        "key": FLAG_SYSTEM_ENABLED,
        "enabled": False,
        "rollout_percentage": 0,
        "description": "Master kill-switch for AutoDiscovery Phase 0",
    },
    {
        "key": FLAG_LOOP_RESCAN,
        "enabled": False,
        "rollout_percentage": 0,
        "description": "Correlation multi-window rescan loop",
    },
    {
        "key": FLAG_LOOP_INTERACTION,
        "enabled": False,
        "rollout_percentage": 0,
        "description": "Pairwise interaction scan loop (Phase 0B)",
    },
    {
        "key": FLAG_LOOP_TUNING,
        "enabled": False,
        "rollout_percentage": 0,
        "description": "Registry tuning loop (Phase 0B)",
    },
    {
        "key": FLAG_LIVE_MUTATION,
        "enabled": False,
        "rollout_percentage": 0,
        "description": "Live production config mutation (Phase 1+, never in Phase 0)",
    },
    {
        "key": FLAG_ATHLETE_SURFACING,
        "enabled": False,
        "rollout_percentage": 0,
        "description": "Athlete-facing output surfacing (Phase 1+, never in Phase 0)",
    },
]
