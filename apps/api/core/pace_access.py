"""
Pace Access — canonical gate for plan pace field visibility.

Pace visibility is controlled by role + subscription state.
Free plans return full plan structure with pace target fields set to null.

Usage::

    from core.pace_access import can_access_plan_paces

    show_paces = can_access_plan_paces(athlete, plan.id, db)
    if not show_paces:
        workout["coach_notes"] = None
"""

from uuid import UUID

from core.tier_utils import tier_satisfies


def can_access_plan_paces(athlete, plan_id: UUID, db) -> bool:
    """Return True if the athlete may see pace target fields for this plan.

    Access is granted when ANY of the following conditions hold:
    1. Role is admin or owner.
    2. Athlete has an active trial or subscription (has_active_subscription=True).
    3. Athlete subscription tier is paid (subscriber or legacy paid aliases).

    The check is fail-closed: any unexpected state (None tier, missing model)
    resolves to False.
    """
    # Admin / owner always see everything
    if getattr(athlete, "role", None) in ("admin", "owner"):
        return True

    # Active trial or subscription grants full access
    if getattr(athlete, "has_active_subscription", False):
        return True

    tier = str(getattr(athlete, "subscription_tier", "") or "").strip().lower()
    if tier == "subscriber":
        return True

    # Backward-compatibility during tier vocabulary migration.
    if tier_satisfies(getattr(athlete, "subscription_tier", None), "guided"):
        return True

    return False
