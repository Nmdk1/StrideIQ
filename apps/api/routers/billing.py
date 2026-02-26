from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from core.auth import get_current_active_user
from core.database import get_db
from core.tier_utils import normalize_tier
from models import Athlete, Subscription
from services.stripe_service import StripeService, process_stripe_event


router = APIRouter(prefix="/v1/billing", tags=["billing"])


class StartTrialRequest(BaseModel):
    days: int = Field(default=7, ge=1, le=30, description="Trial length in days (bounded)")


@router.post("/trial/start")
def start_trial(
    request: StartTrialRequest,
    current_user: Athlete = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Start a time-bound free trial (Phase 6).

    Policy:
    - One trial per athlete (trial_started_at is immutable once set).
    - Cannot start a trial if already paid via Stripe or already has paid tier.
    """
    if getattr(current_user, "trial_started_at", None) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Trial already used")

    if getattr(current_user, "subscription_tier", "free") in getattr(Athlete, "PAID_TIERS", set()):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already has paid access")

    existing_sub = db.query(Subscription).filter(Subscription.athlete_id == current_user.id).first()
    if existing_sub and (existing_sub.status or "").lower() in ("active", "trialing"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already has paid access")

    now = datetime.now(timezone.utc)
    current_user.trial_started_at = now
    current_user.trial_ends_at = now + timedelta(days=int(request.days))
    current_user.trial_source = "self_serve"
    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    return {
        "success": True,
        "trial_started_at": current_user.trial_started_at,
        "trial_ends_at": current_user.trial_ends_at,
        "trial_source": current_user.trial_source,
        "has_active_subscription": bool(getattr(current_user, "has_active_subscription", False)),
    }


class CheckoutRequest(BaseModel):
    """Checkout request — backward-compatible with old clients.

    Old shape (still accepted):
        {"billing_period": "annual"}

    New shape:
        {"tier": "guided", "billing_period": "monthly"}
        {"tier": "premium", "billing_period": "annual"}

    If ``tier`` is omitted, defaults to "premium" to preserve existing behavior.
    """
    billing_period: str = Field(
        default="annual",
        description="'annual' or 'monthly'",
    )
    tier: Optional[str] = Field(
        default=None,
        description="'guided' or 'premium'. Defaults to 'premium' if omitted.",
    )


@router.post("/checkout")
def create_checkout(
    request: CheckoutRequest = None,
    current_user: Athlete = Depends(get_current_active_user),
):
    """Create a Stripe Checkout Session for a subscription tier.

    Backward-compatible: old clients sending only ``billing_period`` receive
    a premium checkout session (unchanged behavior).
    """
    billing_period = (request.billing_period if request else "annual") or "annual"
    if billing_period not in ("annual", "monthly"):
        raise HTTPException(status_code=400, detail="billing_period must be 'annual' or 'monthly'")

    raw_tier = (request.tier if request else None) or "premium"
    canonical_tier = normalize_tier(raw_tier)
    if canonical_tier not in ("guided", "premium"):
        raise HTTPException(
            status_code=400,
            detail="tier must be 'guided' or 'premium'",
        )

    try:
        url = StripeService().create_checkout_session(
            athlete=current_user,
            tier=canonical_tier,
            billing_period=billing_period,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to create checkout session")

    return {"url": url, "tier": canonical_tier, "billing_period": billing_period}


class PlanCheckoutRequest(BaseModel):
    """Request body for a one-time race-plan unlock checkout."""
    plan_snapshot_id: str = Field(
        ...,
        description="Stable, immutable identifier for the plan artifact being unlocked.",
    )


@router.post("/checkout/plan")
def create_plan_checkout(
    request: PlanCheckoutRequest,
    current_user: Athlete = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Create a Stripe Checkout Session for a one-time race-plan unlock ($5).

    The athlete must own the target plan artifact (plan_snapshot_id bound to
    their account). Cross-athlete unlock attempts are rejected with 403.
    """
    plan_snapshot_id = (request.plan_snapshot_id or "").strip()
    if not plan_snapshot_id:
        raise HTTPException(status_code=400, detail="plan_snapshot_id is required")

    # Ownership validation: verify the plan artifact belongs to this athlete.
    _verify_plan_ownership(db, athlete_id=current_user.id, plan_snapshot_id=plan_snapshot_id)

    try:
        url = StripeService().create_one_time_checkout_session(
            athlete=current_user,
            plan_snapshot_id=plan_snapshot_id,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to create plan checkout session")

    return {"url": url, "plan_snapshot_id": plan_snapshot_id, "purchase_type": "plan_onetime"}


@router.post("/portal")
def create_portal(
    current_user: Athlete = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Create a Stripe Customer Portal Session. Returns a hosted URL."""
    try:
        svc = StripeService()
        svc.best_effort_sync_customer_subscription(db, athlete=current_user)
        url = svc.create_portal_session(athlete=current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to create portal session")
    return {"url": url}


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Stripe webhook endpoint.

    Verifies signature and processes events idempotently.
    """
    sig = request.headers.get("stripe-signature")
    if not sig:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    payload = await request.body()
    try:
        event = StripeService().construct_event(payload=payload, sig_header=sig)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    result = process_stripe_event(db, event=event)
    return {"ok": True, "result": result}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _verify_plan_ownership(db: Session, *, athlete_id, plan_snapshot_id: str) -> None:
    """Verify that plan_snapshot_id belongs to athlete_id.

    Raises HTTPException 403 if the plan does not belong to this athlete,
    or 404 if the plan does not exist at all.

    This is the cross-athlete unlock guard per the non-negotiable contract.
    """
    from models import TrainingPlan  # local import to avoid circular deps

    plan = db.query(TrainingPlan).filter(
        TrainingPlan.id == plan_snapshot_id
    ).first()

    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan_athlete_id = getattr(plan, "athlete_id", None)
    if str(plan_athlete_id) != str(athlete_id):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to purchase an unlock for this plan",
        )
