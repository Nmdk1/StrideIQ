from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from core.auth import get_current_active_user
from core.database import get_db
from models import Athlete
from services.stripe_service import StripeService, process_stripe_event


router = APIRouter(prefix="/v1/billing", tags=["billing"])


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
def create_portal(current_user: Athlete = Depends(get_current_active_user)):
    """
    Create a Stripe Customer Portal Session.
    Returns a hosted URL.
    """
    try:
        url = StripeService().create_portal_session(athlete=current_user)
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

