"""
Pace Access — canonical gate for plan pace field visibility.

Decision (2026-02-26): Paces are gated behind $5 one-time purchase OR
Guided/Premium subscription.  Free plans return full plan structure with
pace target fields set to null.  The frontend shows blurred paces + "$5 to
unlock" CTA for unauthorized tiers.

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
    3. Athlete subscription tier is guided or above (tier_satisfies).
    4. Athlete has a completed PlanPurchase record for this specific plan.

    The check is fail-closed: any unexpected state (None tier, missing model)
    resolves to False.
    """
    # Admin / owner always see everything
    if getattr(athlete, "role", None) in ("admin", "owner"):
        return True

    # Active trial or subscription grants full access
    if getattr(athlete, "has_active_subscription", False):
        return True

    # Subscription tier — guided+ unlocks paces
    if tier_satisfies(getattr(athlete, "subscription_tier", None), "guided"):
        return True

    # One-time purchase: check PlanPurchase for this specific plan artifact
    from models import PlanPurchase

    purchase = (
        db.query(PlanPurchase)
        .filter(
            PlanPurchase.athlete_id == athlete.id,
            PlanPurchase.plan_snapshot_id == str(plan_id),
        )
        .first()
    )
    return purchase is not None
