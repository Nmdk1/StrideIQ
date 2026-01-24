"""
System-level feature flags (operator controls).

These are DB-backed and intended for safety / resilience controls.
Unlike product flags, these should fail CLOSED where appropriate.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from services.plan_framework.feature_flags import FeatureFlagService


INGESTION_PAUSED_FLAG_KEY = "system.ingestion_paused"


def is_ingestion_paused(db: Session) -> bool:
    """
    Returns True if global ingestion is paused.

    Fail-closed: if anything goes wrong reading the flag, return False (do not pause).
    """
    try:
        svc = FeatureFlagService(db)
        flag = svc.get_flag(INGESTION_PAUSED_FLAG_KEY)
        if not flag:
            return False
        return bool(flag.get("enabled", False))
    except Exception:
        return False


def set_ingestion_paused(db: Session, *, paused: bool) -> bool:
    """
    Set global ingestion pause.

    Creates the flag if missing.
    """
    svc = FeatureFlagService(db)
    flag = svc.get_flag(INGESTION_PAUSED_FLAG_KEY)
    if not flag:
        svc.create_flag(
            key=INGESTION_PAUSED_FLAG_KEY,
            name="Pause global ingestion",
            description="Phase 5: Emergency brake to stop queue growth under load spikes. When enabled, ingestion tasks should not be enqueued from callbacks/admin.",
            enabled=bool(paused),
            requires_subscription=False,
            requires_tier=None,
            requires_payment=None,
            rollout_percentage=100,
        )
        return True
    return svc.set_flag(INGESTION_PAUSED_FLAG_KEY, {"enabled": bool(paused)})

