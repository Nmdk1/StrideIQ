from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from core.auth import get_current_active_user
from core.database import get_db
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
    """
    Start a time-bound free trial (Phase 6).

    Policy:
    - One trial per athlete (trial_started_at is immutable once set)
    - Cannot start a trial if already paid via Stripe or already has paid tier
    """
    # Already used a trial
    if getattr(current_user, "trial_started_at", None) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Trial already used")

    # Already paid (either via current tier or Stripe mirror)
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


@router.post("/checkout")
def create_checkout(current_user: Athlete = Depends(get_current_active_user)):
    """
    Create a Stripe Checkout Session (subscription, monthly Pro).
    Returns a hosted URL.
    """
    try:
        url = StripeService().create_checkout_session(athlete=current_user)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to create checkout session")
    return {"url": url}


@router.post("/portal")
def create_portal(current_user: Athlete = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """
    Create a Stripe Customer Portal Session.
    Returns a hosted URL.
    """
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
    """
    Stripe webhook endpoint.

    Verifies signature and processes events idempotently.
    """
    sig = request.headers.get("stripe-signature")
    if not sig:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    payload = await request.body()
    try:
        event = StripeService().construct_event(payload=payload, sig_header=sig)
    except Exception:
        # Signature verification errors should return 400 so Stripe can retry appropriately.
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    result = process_stripe_event(db, event=event)
    return {"ok": True, "result": result}

