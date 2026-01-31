from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from typing import Any, Optional
from uuid import UUID

import stripe
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.config import settings
from models import Athlete, Subscription, StripeEvent


@dataclass(frozen=True)
class StripeConfig:
    secret_key: str
    webhook_secret: Optional[str]
    pro_monthly_price_id: str
    pro_annual_price_id: Optional[str]
    checkout_success_url: str
    checkout_cancel_url: str
    portal_return_url: str


def _get_stripe_config() -> StripeConfig:
    """
    Load Stripe config from environment via Settings.

    Fail closed: if configuration is missing, billing endpoints should not proceed.
    """
    # Support both "STRIPE_SECRET_KEY" and convenience local names (test/prod).
    secret_key = (
        getattr(settings, "STRIPE_SECRET_KEY", None)
        or os.getenv("STRIPE_SECRET_TEST_KEY")
        or os.getenv("STRIPE_SECRET_LIVE_KEY")
    )

    # Webhook secret is only required for the webhook endpoint; allow checkout/portal
    # to work without it for local development before Stripe CLI is configured.
    webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None) or os.getenv("STRIPE_WEBHOOK_TEST_SECRET") or os.getenv("STRIPE_WEBHOOK_LIVE_SECRET")

    price_id = getattr(settings, "STRIPE_PRICE_PRO_MONTHLY_ID", None)
    annual_price_id = getattr(settings, "STRIPE_PRICE_PRO_ANNUAL_ID", None)

    # Default redirect/return URLs to WEB_APP_BASE_URL so local dev can proceed
    # without forcing extra env config.
    base = getattr(settings, "WEB_APP_BASE_URL", "http://localhost:3000").rstrip("/")
    success_url = getattr(settings, "STRIPE_CHECKOUT_SUCCESS_URL", None) or f"{base}/settings?stripe=success"
    cancel_url = getattr(settings, "STRIPE_CHECKOUT_CANCEL_URL", None) or f"{base}/settings?stripe=cancel"
    portal_return_url = getattr(settings, "STRIPE_PORTAL_RETURN_URL", None) or f"{base}/settings"

    missing = [name for name, val in [("STRIPE_SECRET_KEY", secret_key), ("STRIPE_PRICE_PRO_MONTHLY_ID", price_id)] if not val]
    if missing:
        raise RuntimeError(f"Stripe not configured (missing: {', '.join(missing)})")

    return StripeConfig(
        secret_key=str(secret_key),
        webhook_secret=str(webhook_secret) if webhook_secret else None,
        pro_monthly_price_id=str(price_id),
        pro_annual_price_id=str(annual_price_id) if annual_price_id else None,
        checkout_success_url=str(success_url),
        checkout_cancel_url=str(cancel_url),
        portal_return_url=str(portal_return_url),
    )


def _entitlement_tier_for_subscription_status(status: Optional[str]) -> str:
    """
    Map Stripe subscription status -> StrideIQ paid tier.

    MVP policy: only active/trialing are paid.
    """
    s = (status or "").lower()
    if s in ("active", "trialing"):
        return "pro"
    return "free"


class StripeService:
    def __init__(self) -> None:
        cfg = _get_stripe_config()
        stripe.api_key = cfg.secret_key
        self.cfg = cfg

    def create_checkout_session(self, *, athlete: Athlete, billing_period: str = "annual") -> str:
        """
        Create a Stripe Checkout session.
        
        Args:
            athlete: The athlete to create checkout for
            billing_period: "annual" ($149/yr) or "monthly" ($14.99/mo). Default is annual.
        """
        # Select price based on billing period (annual is primary offer)
        if billing_period == "annual" and self.cfg.pro_annual_price_id:
            price_id = self.cfg.pro_annual_price_id
        else:
            price_id = self.cfg.pro_monthly_price_id
        
        # Prefer explicit customer if we already have it.
        customer_id = getattr(athlete, "stripe_customer_id", None)
        params: dict[str, Any] = {
            "mode": "subscription",
            "success_url": self.cfg.checkout_success_url,
            "cancel_url": self.cfg.checkout_cancel_url,
            "line_items": [{"price": price_id, "quantity": 1}],
            "client_reference_id": str(athlete.id),
            "metadata": {"athlete_id": str(athlete.id), "billing_period": billing_period},
        }
        if customer_id:
            params["customer"] = customer_id
        elif athlete.email:
            params["customer_email"] = athlete.email

        session = stripe.checkout.Session.create(**params)
        return str(session.url)

    def create_portal_session(self, *, athlete: Athlete) -> str:
        customer_id = getattr(athlete, "stripe_customer_id", None)
        if not customer_id:
            raise ValueError("No stripe_customer_id for athlete")
        sess = stripe.billing_portal.Session.create(
            customer=str(customer_id),
            return_url=self.cfg.portal_return_url,
        )
        return str(sess.url)

    def construct_event(self, *, payload: bytes, sig_header: str):
        if not self.cfg.webhook_secret:
            raise RuntimeError("Stripe webhook secret not configured")
        return stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=self.cfg.webhook_secret,
        )

    def best_effort_sync_customer_subscription(self, db: Session, *, athlete: Athlete) -> None:
        """
        Failsafe reconciliation:
        Webhooks are the primary integration path, but in practice deliveries can be
        delayed/missed in local dev or during outages. This performs a best-effort
        pull of the customer's current subscription and mirrors it to our DB.

        This MUST NOT block portal access; failures are swallowed.
        """
        try:
            customer_id = getattr(athlete, "stripe_customer_id", None)
            if not customer_id:
                return

            # Stripe returns the newest subscription first by default.
            resp = stripe.Subscription.list(customer=str(customer_id), status="all", limit=10)
            subs = list(getattr(resp, "data", None) or [])
            if not subs:
                return

            # Prefer active/trialing if present; otherwise fall back to newest.
            def _rank(s: Any) -> int:
                st = str(getattr(s, "status", "") or "").lower()
                if st == "active":
                    return 0
                if st == "trialing":
                    return 1
                return 2

            subs_sorted = sorted(subs, key=_rank)
            s = subs_sorted[0]

            sub_row = _ensure_subscription_row(db, athlete_id=athlete.id)
            sub_row.stripe_customer_id = str(customer_id)
            sub_row.stripe_subscription_id = str(getattr(s, "id", None) or "") or None
            sub_row.status = str(getattr(s, "status", None) or "") or None

            current_period_end_ts = _extract_current_period_end_ts(s)
            cancel_at_ts = _extract_cancel_at_ts(s)
            if current_period_end_ts is None and cancel_at_ts is not None:
                current_period_end_ts = cancel_at_ts
            sub_row.current_period_end = _maybe_parse_period_end(current_period_end_ts)
            sub_row.cancel_at_period_end = _derive_cancel_at_period_end(s, current_period_end_ts=current_period_end_ts)

            # Best-effort price id from first subscription item.
            try:
                items = getattr(s, "items", None)
                data = getattr(items, "data", None) if items else None
                first = data[0] if data else None
                price = getattr(first, "price", None) if first else None
                price_id = getattr(price, "id", None) if price else None
                if price_id:
                    sub_row.stripe_price_id = str(price_id)
            except Exception:
                pass

            # Mirror entitlement on athlete (keep "pro" through end-of-period).
            athlete.subscription_tier = _entitlement_tier_for_subscription_status(sub_row.status)
            db.add(athlete)
            db.add(sub_row)
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            return


def _ensure_subscription_row(db: Session, *, athlete_id: UUID) -> Subscription:
    sub = db.query(Subscription).filter(Subscription.athlete_id == athlete_id).first()
    if sub:
        return sub
    sub = Subscription(athlete_id=athlete_id)
    db.add(sub)
    db.flush()
    return sub


def _maybe_parse_period_end(ts: Any) -> Optional[datetime]:
    try:
        if ts is None:
            return None
        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except Exception:
        return None


def _extract_current_period_end_ts(obj: Any) -> Optional[int]:
    """
    Stripe API compatibility:
    - Older API versions: `subscription.current_period_end` (top-level)
    - Newer API versions: billing period fields live on `subscription.items.data[*].current_period_end`
    """
    try:
        ts = getattr(obj, "current_period_end", None)
        if ts is not None:
            return int(ts)
    except Exception:
        pass

    try:
        items = getattr(obj, "items", None)
        data = getattr(items, "data", None) if items else None
        if data is None and isinstance(items, dict):
            data = items.get("data")

        ends: list[int] = []
        for it in (data or []):
            if isinstance(it, dict):
                it_end = it.get("current_period_end")
            else:
                it_end = getattr(it, "current_period_end", None)
            if it_end is not None:
                ends.append(int(it_end))
        if ends:
            return max(ends)
    except Exception:
        pass

    return None


def _extract_cancel_at_ts(obj: Any) -> Optional[int]:
    try:
        v = getattr(obj, "cancel_at", None)
        if v is None and isinstance(obj, dict):
            v = obj.get("cancel_at")
        return int(v) if v is not None else None
    except Exception:
        return None


def _derive_cancel_at_period_end(obj: Any, *, current_period_end_ts: Optional[int]) -> bool:
    # Legacy behavior (still present in some versions/paths)
    try:
        if bool(getattr(obj, "cancel_at_period_end", False)):
            return True
    except Exception:
        pass
    if isinstance(obj, dict) and bool(obj.get("cancel_at_period_end", False)):
        return True

    # Newer Stripe API uses `cancel_at` timestamps for scheduled cancellation.
    cancel_at = _extract_cancel_at_ts(obj)
    if cancel_at is None:
        return False
    if current_period_end_ts is None:
        return True
    return int(cancel_at) == int(current_period_end_ts)


def process_stripe_event(db: Session, *, event: Any) -> dict[str, Any]:
    """
    Idempotently process Stripe webhook event and update the subscription mirror + athlete tier.
    """
    event_id = str(getattr(event, "id", "") or "")
    event_type = str(getattr(event, "type", "") or "")
    stripe_created = getattr(event, "created", None)

    if not event_id:
        return {"processed": False, "reason": "missing_event_id"}

    # Idempotency: if event already processed, do nothing.
    db.add(StripeEvent(event_id=event_id, event_type=event_type or "unknown", stripe_created=int(stripe_created) if stripe_created else None))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return {"processed": False, "idempotent": True, "event_id": event_id}

    obj = None
    try:
        obj = event.data.object  # stripe.Event supports attribute access
    except Exception:
        obj = (event.get("data") or {}).get("object") if isinstance(event, dict) else None

    # Helper to locate athlete by reference id or stripe customer id.
    athlete: Optional[Athlete] = None

    def _find_athlete_by_reference_id(ref: Optional[str]) -> Optional[Athlete]:
        if not ref:
            return None
        try:
            return db.query(Athlete).filter(Athlete.id == ref).first()
        except Exception:
            return None

    def _find_athlete_by_customer_id(cust_id: Optional[str]) -> Optional[Athlete]:
        if not cust_id:
            return None
        return db.query(Athlete).filter(Athlete.stripe_customer_id == cust_id).first()

    if event_type == "checkout.session.completed":
        customer_id = str(getattr(obj, "customer", None) or "")
        subscription_id = str(getattr(obj, "subscription", None) or "")
        ref_id = str(getattr(obj, "client_reference_id", None) or "") or str((getattr(obj, "metadata", {}) or {}).get("athlete_id") or "")

        athlete = _find_athlete_by_reference_id(ref_id) or _find_athlete_by_customer_id(customer_id)
        if not athlete:
            db.commit()
            return {"processed": True, "event_id": event_id, "event_type": event_type, "matched_athlete": False}

        if customer_id and not athlete.stripe_customer_id:
            athlete.stripe_customer_id = customer_id
        db.add(athlete)

        sub = _ensure_subscription_row(db, athlete_id=athlete.id)
        if customer_id:
            sub.stripe_customer_id = customer_id
        if subscription_id:
            sub.stripe_subscription_id = subscription_id
        sub.status = "active"
        sub.cancel_at_period_end = False
        db.add(sub)

        athlete.subscription_tier = "pro"
        db.add(athlete)

        db.commit()
        return {"processed": True, "event_id": event_id, "event_type": event_type, "athlete_id": str(athlete.id)}

    if event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
        customer_id = str(getattr(obj, "customer", None) or "")
        subscription_id = str(getattr(obj, "id", None) or "")
        status = str(getattr(obj, "status", None) or "") or None
        current_period_end_ts = _extract_current_period_end_ts(obj)
        cancel_at_ts = _extract_cancel_at_ts(obj)
        if current_period_end_ts is None and cancel_at_ts is not None:
            # Some objects may omit period fields but include cancellation timestamp.
            current_period_end_ts = cancel_at_ts
        current_period_end = _maybe_parse_period_end(current_period_end_ts)
        cancel_at_period_end = _derive_cancel_at_period_end(obj, current_period_end_ts=current_period_end_ts)

        athlete = _find_athlete_by_customer_id(customer_id)
        if not athlete and subscription_id:
            # Fallback match: find Subscription row by subscription id, then athlete.
            existing = db.query(Subscription).filter(Subscription.stripe_subscription_id == subscription_id).first()
            if existing:
                athlete = db.query(Athlete).filter(Athlete.id == existing.athlete_id).first()

        if not athlete:
            db.commit()
            return {"processed": True, "event_id": event_id, "event_type": event_type, "matched_athlete": False}

        if customer_id and not athlete.stripe_customer_id:
            athlete.stripe_customer_id = customer_id
        db.add(athlete)

        sub = _ensure_subscription_row(db, athlete_id=athlete.id)
        if customer_id:
            sub.stripe_customer_id = customer_id
        if subscription_id:
            sub.stripe_subscription_id = subscription_id
        sub.status = status
        sub.current_period_end = current_period_end
        sub.cancel_at_period_end = cancel_at_period_end

        # Try to capture the price id (best-effort).
        try:
            items = getattr(obj, "items", None)
            data = getattr(items, "data", None) if items else None
            first = data[0] if data else None
            price = getattr(first, "price", None) if first else None
            price_id = getattr(price, "id", None) if price else None
            if price_id:
                sub.stripe_price_id = str(price_id)
        except Exception:
            pass

        db.add(sub)

        # Entitlement mirror on athlete
        athlete.subscription_tier = _entitlement_tier_for_subscription_status(status)
        db.add(athlete)

        db.commit()
        return {"processed": True, "event_id": event_id, "event_type": event_type, "athlete_id": str(athlete.id), "status": status}

    # Unknown/unhandled event: accept but no-op (still idempotently recorded).
    db.commit()
    return {"processed": True, "event_id": event_id, "event_type": event_type, "handled": False}

