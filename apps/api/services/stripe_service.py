from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import stripe
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.config import settings
from core.tier_utils import normalize_tier
from models import Athlete, Subscription, StripeEvent

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class StripeConfig:
    secret_key: str
    webhook_secret: Optional[str]
    checkout_success_url: str
    checkout_cancel_url: str
    portal_return_url: str
    # 4-tier price IDs (all Optional; flows fail closed if required ID is absent)
    price_plan_onetime_id: Optional[str] = None
    price_guided_monthly_id: Optional[str] = None
    price_guided_annual_id: Optional[str] = None
    price_premium_monthly_id: Optional[str] = None
    price_premium_annual_id: Optional[str] = None
    # Monetization reset single paid tier.
    price_strideiq_monthly_id: Optional[str] = None
    price_strideiq_annual_id: Optional[str] = None
    # Legacy price IDs — existing subscribers only; new checkouts do not use these
    price_legacy_pro_monthly_id: Optional[str] = None


def _get_stripe_config() -> StripeConfig:
    """Load Stripe config from environment via Settings.

    Only STRIPE_SECRET_KEY is required for initialization. Individual price IDs
    are validated at checkout time so the service can initialize without all IDs
    (e.g., before new Stripe products are created in a fresh environment).
    """
    secret_key = (
        getattr(settings, "STRIPE_SECRET_KEY", None)
        or __import__("os").getenv("STRIPE_SECRET_TEST_KEY")
        or __import__("os").getenv("STRIPE_SECRET_LIVE_KEY")
    )
    if not secret_key:
        raise RuntimeError("Stripe not configured (missing: STRIPE_SECRET_KEY)")

    webhook_secret = (
        getattr(settings, "STRIPE_WEBHOOK_SECRET", None)
        or __import__("os").getenv("STRIPE_WEBHOOK_TEST_SECRET")
        or __import__("os").getenv("STRIPE_WEBHOOK_LIVE_SECRET")
    )

    base = getattr(settings, "WEB_APP_BASE_URL", "http://localhost:3000").rstrip("/")
    success_url = getattr(settings, "STRIPE_CHECKOUT_SUCCESS_URL", None) or f"{base}/settings?stripe=success"
    cancel_url = getattr(settings, "STRIPE_CHECKOUT_CANCEL_URL", None) or f"{base}/settings?stripe=cancel"
    portal_return_url = getattr(settings, "STRIPE_PORTAL_RETURN_URL", None) or f"{base}/settings"

    return StripeConfig(
        secret_key=str(secret_key),
        webhook_secret=str(webhook_secret) if webhook_secret else None,
        checkout_success_url=str(success_url),
        checkout_cancel_url=str(cancel_url),
        portal_return_url=str(portal_return_url),
        price_plan_onetime_id=getattr(settings, "STRIPE_PRICE_PLAN_ONETIME_ID", None) or None,
        price_guided_monthly_id=getattr(settings, "STRIPE_PRICE_GUIDED_MONTHLY_ID", None) or None,
        price_guided_annual_id=getattr(settings, "STRIPE_PRICE_GUIDED_ANNUAL_ID", None) or None,
        price_premium_monthly_id=getattr(settings, "STRIPE_PRICE_PREMIUM_MONTHLY_ID", None) or None,
        price_premium_annual_id=getattr(settings, "STRIPE_PRICE_PREMIUM_ANNUAL_ID", None) or None,
        price_strideiq_monthly_id=getattr(settings, "STRIPE_PRICE_STRIDEIQ_MONTHLY_ID", None) or None,
        price_strideiq_annual_id=getattr(settings, "STRIPE_PRICE_STRIDEIQ_ANNUAL_ID", None) or None,
        price_legacy_pro_monthly_id=getattr(settings, "STRIPE_PRICE_PRO_MONTHLY_ID", None) or None,
    )


def build_price_to_tier(cfg: StripeConfig) -> dict[str, str]:
    """Build price_id → canonical tier mapping from config.

    Only subscription prices are mapped here (guided / premium).
    One-time prices are NOT in this map — they follow a separate entitlement path.
    Unknown price IDs will never appear in this dict, enforcing fail-closed behavior:
    any price_id not present here grants no entitlement.
    """
    mapping: dict[str, str] = {}
    pairs: list[tuple[Optional[str], str]] = [
        (getattr(cfg, "price_strideiq_monthly_id", None), "premium"),
        (getattr(cfg, "price_strideiq_annual_id", None), "premium"),
        (getattr(cfg, "price_guided_monthly_id", None), "guided"),
        (getattr(cfg, "price_guided_annual_id", None), "guided"),
        (getattr(cfg, "price_premium_monthly_id", None), "premium"),
        (getattr(cfg, "price_premium_annual_id", None), "premium"),
        # Legacy pro price maps to premium (existing subscribers retain access)
        (getattr(cfg, "price_legacy_pro_monthly_id", None), "premium"),
    ]
    for price_id, tier in pairs:
        if price_id:
            mapping[price_id] = tier
    return mapping


def tier_for_price_and_status(
    price_id: Optional[str],
    status: Optional[str],
    price_to_tier: dict[str, str],
) -> str:
    """Derive canonical entitlement tier from a subscription's price ID and status.

    Fail-closed contract:
    - Non active/trialing status → "free"
    - Missing price_id → "free" (logged as warning)
    - Unknown price_id → "free" (logged as warning — flag for ops follow-up)

    This function is the ONLY place where Stripe subscription state translates
    to a StrideIQ tier. It must never auto-promote.
    """
    s = (status or "").lower()
    if s not in ("active", "trialing"):
        return "free"

    if not price_id:
        log.warning(
            "stripe: active/trialing subscription has no price_id — granting free (fail closed)"
        )
        return "free"

    tier = price_to_tier.get(price_id)
    if tier is None:
        log.warning(
            "stripe: unknown price_id=%s on %s subscription — granting free (fail closed); "
            "add to PRICE_TO_TIER or investigate",
            price_id,
            s,
        )
        return "free"

    return tier


class StripeService:
    def __init__(self) -> None:
        cfg = _get_stripe_config()
        stripe.api_key = cfg.secret_key
        self.cfg = cfg
        self._price_to_tier = build_price_to_tier(cfg)

    def create_checkout_session(
        self,
        *,
        athlete: Athlete,
        tier: str = "premium",
        billing_period: str = "annual",
    ) -> str:
        """Create a Stripe Checkout session for a subscription tier.

        Args:
            athlete: The athlete subscribing.
            tier: "guided" or "premium". Defaults to "premium" for backward compat.
            billing_period: "monthly" or "annual". Defaults to "annual".

        Raises:
            RuntimeError: If the required price ID is not configured.
            ValueError: If tier or billing_period is invalid.
        """
        canonical = normalize_tier(tier)
        if canonical not in ("guided", "premium"):
            raise ValueError(f"Subscription tier must be 'guided' or 'premium', got: {tier!r}")
        if billing_period not in ("monthly", "annual"):
            raise ValueError(f"billing_period must be 'monthly' or 'annual', got: {billing_period!r}")

        price_id = self._resolve_subscription_price(canonical, billing_period)

        customer_id = getattr(athlete, "stripe_customer_id", None)
        params: dict[str, Any] = {
            "mode": "subscription",
            "success_url": self.cfg.checkout_success_url,
            "cancel_url": self.cfg.checkout_cancel_url,
            "line_items": [{"price": price_id, "quantity": 1}],
            "client_reference_id": str(athlete.id),
            "metadata": {
                "athlete_id": str(athlete.id),
                "tier": canonical,
                "billing_period": billing_period,
            },
        }
        if customer_id:
            params["customer"] = customer_id
        elif athlete.email:
            params["customer_email"] = athlete.email

        session = stripe.checkout.Session.create(**params)
        return str(session.url)

    def create_one_time_checkout_session(
        self,
        *,
        athlete: Athlete,
        plan_snapshot_id: str,
        success_url: Optional[str] = None,
    ) -> str:
        """Create a Stripe Checkout session for a one-time race-plan unlock ($5).

        Args:
            athlete: The athlete purchasing the unlock.
            plan_snapshot_id: Stable, immutable identifier for the plan artifact.
                Must be bound to this athlete; verified by the caller before invocation.
            success_url: Override the default success redirect URL.  When supplied,
                the athlete is sent here after a successful payment instead of the
                global STRIPE_CHECKOUT_SUCCESS_URL.  Callers should pass a plan-
                specific URL (e.g. /plans/{id}?unlocked=1) so the athlete lands
                back on their plan page.

        Raises:
            RuntimeError: If STRIPE_PRICE_PLAN_ONETIME_ID is not configured.
        """
        if not self.cfg.price_plan_onetime_id:
            raise RuntimeError(
                "One-time plan checkout not configured (missing: STRIPE_PRICE_PLAN_ONETIME_ID)"
            )

        customer_id = getattr(athlete, "stripe_customer_id", None)
        params: dict[str, Any] = {
            "mode": "payment",
            "success_url": success_url or self.cfg.checkout_success_url,
            "cancel_url": self.cfg.checkout_cancel_url,
            "line_items": [{"price": self.cfg.price_plan_onetime_id, "quantity": 1}],
            "client_reference_id": str(athlete.id),
            "metadata": {
                "athlete_id": str(athlete.id),
                "plan_snapshot_id": plan_snapshot_id,
                "purchase_type": "plan_onetime",
            },
        }
        if customer_id:
            params["customer"] = customer_id
        elif athlete.email:
            params["customer_email"] = athlete.email

        session = stripe.checkout.Session.create(**params)
        return str(session.url)

    def _resolve_subscription_price(self, canonical_tier: str, billing_period: str) -> str:
        """Look up the configured price ID for a subscription tier + period.

        Fails closed: raises RuntimeError if the required price is not configured.
        This ensures the service never silently falls back to an unrelated price.
        """
        lookup: dict[tuple[str, str], Optional[str]] = {
            ("guided", "monthly"): self.cfg.price_guided_monthly_id,
            ("guided", "annual"): self.cfg.price_guided_annual_id,
            ("premium", "monthly"): self.cfg.price_strideiq_monthly_id or self.cfg.price_premium_monthly_id,
            ("premium", "annual"): self.cfg.price_strideiq_annual_id or self.cfg.price_premium_annual_id,
        }
        price_id = lookup.get((canonical_tier, billing_period))
        if not price_id:
            env_name = (
                f"STRIPE_PRICE_{canonical_tier.upper()}_{billing_period.upper()}_ID"
            )
            raise RuntimeError(
                f"Stripe price not configured for {canonical_tier}/{billing_period} "
                f"(missing: {env_name})"
            )
        return price_id

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
        """Failsafe reconciliation: mirror latest Stripe subscription state to DB.

        Webhooks are primary; this is a safety net for missed deliveries.
        Failures are swallowed — must NOT block portal access.
        """
        try:
            customer_id = getattr(athlete, "stripe_customer_id", None)
            if not customer_id:
                return

            resp = stripe.Subscription.list(customer=str(customer_id), status="all", limit=10)
            subs = list(getattr(resp, "data", None) or [])
            if not subs:
                return

            def _rank(s: Any) -> int:
                st = str(getattr(s, "status", "") or "").lower()
                if st == "active":
                    return 0
                if st == "trialing":
                    return 1
                return 2

            s = sorted(subs, key=_rank)[0]

            sub_row = _ensure_subscription_row(db, athlete_id=athlete.id)
            sub_row.stripe_customer_id = str(customer_id)
            sub_row.stripe_subscription_id = str(getattr(s, "id", None) or "") or None
            sub_row.status = str(getattr(s, "status", None) or "") or None

            current_period_end_ts = _extract_current_period_end_ts(s)
            cancel_at_ts = _extract_cancel_at_ts(s)
            if current_period_end_ts is None and cancel_at_ts is not None:
                current_period_end_ts = cancel_at_ts
            sub_row.current_period_end = _maybe_parse_period_end(current_period_end_ts)
            sub_row.cancel_at_period_end = _derive_cancel_at_period_end(
                s, current_period_end_ts=current_period_end_ts
            )

            try:
                items = getattr(s, "items", None)
                data = getattr(items, "data", None) if items else None
                first = data[0] if data else None
                price = getattr(first, "price", None) if first else None
                price_id = getattr(price, "id", None) if price else None
                if price_id:
                    sub_row.stripe_price_id = str(price_id)
            except Exception:
                price_id = None

            _apply_stripe_tier(
                athlete,
                tier_for_price_and_status(price_id, sub_row.status, self._price_to_tier),
            )
            db.add(athlete)
            db.add(sub_row)
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Module-level helpers (also used by process_stripe_event)
# ---------------------------------------------------------------------------

def _apply_stripe_tier(athlete: Athlete, tier: str) -> None:
    """
    Set athlete.subscription_tier from a Stripe-derived tier, respecting the
    admin comp override precedence contract.

    If admin_tier_override is set, the manual comp takes precedence and Stripe
    MUST NOT downgrade the tier.  The Subscription mirror (status, price_id,
    current_period_end) is still updated by callers — only the final tier
    assignment is guarded here.
    """
    if getattr(athlete, "admin_tier_override", None):
        # Keep the manually comped tier; do not revert.
        return
    athlete.subscription_tier = tier

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
    """Stripe API compatibility: period end may be top-level or nested in items."""
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
            it_end = it.get("current_period_end") if isinstance(it, dict) else getattr(it, "current_period_end", None)
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
    try:
        if bool(getattr(obj, "cancel_at_period_end", False)):
            return True
    except Exception:
        pass
    if isinstance(obj, dict) and bool(obj.get("cancel_at_period_end", False)):
        return True

    cancel_at = _extract_cancel_at_ts(obj)
    if cancel_at is None:
        return False
    if current_period_end_ts is None:
        return True
    return int(cancel_at) == int(current_period_end_ts)


def process_stripe_event(db: Session, *, event: Any) -> dict[str, Any]:
    """Idempotently process Stripe webhook event.

    Updates the subscription mirror and athlete tier. Signature verification
    must be performed by the caller before invoking this function.

    Replay safety: duplicate event_id → immediate no-op (idempotent insert guard).
    """
    event_id = str(getattr(event, "id", "") or "")
    event_type = str(getattr(event, "type", "") or "")
    stripe_created = getattr(event, "created", None)

    if not event_id:
        return {"processed": False, "reason": "missing_event_id"}

    # Idempotency guard: unique constraint on event_id; duplicate → no-op.
    db.add(StripeEvent(
        event_id=event_id,
        event_type=event_type or "unknown",
        stripe_created=int(stripe_created) if stripe_created else None,
    ))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return {"processed": False, "idempotent": True, "event_id": event_id}

    obj = None
    try:
        obj = event.data.object
    except Exception:
        obj = (event.get("data") or {}).get("object") if isinstance(event, dict) else None

    # Build price→tier map once per event using current config.
    # This keeps event processing decoupled from a StripeService instance.
    try:
        cfg = _get_stripe_config()
        price_to_tier = build_price_to_tier(cfg)
    except RuntimeError:
        price_to_tier = {}

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

    athlete: Optional[Athlete] = None

    # ------------------------------------------------------------------
    # checkout.session.completed
    # Handles both subscription (mode=subscription) and one-time (mode=payment).
    # ------------------------------------------------------------------
    if event_type == "checkout.session.completed":
        customer_id = str(getattr(obj, "customer", None) or "")
        subscription_id = str(getattr(obj, "subscription", None) or "")
        payment_intent_id = str(getattr(obj, "payment_intent", None) or "")
        mode = str(getattr(obj, "mode", None) or "")
        metadata = dict(getattr(obj, "metadata", None) or {})
        ref_id = str(getattr(obj, "client_reference_id", None) or "") or str(
            metadata.get("athlete_id") or ""
        )

        athlete = _find_athlete_by_reference_id(ref_id) or _find_athlete_by_customer_id(customer_id)
        if not athlete:
            db.commit()
            return {
                "processed": True,
                "event_id": event_id,
                "event_type": event_type,
                "matched_athlete": False,
            }

        if customer_id and not athlete.stripe_customer_id:
            athlete.stripe_customer_id = customer_id
        db.add(athlete)

        if mode == "payment":
            # One-time plan unlock: record purchase artifact, do NOT change subscription_tier.
            plan_snapshot_id = metadata.get("plan_snapshot_id") or ""
            if plan_snapshot_id and payment_intent_id:
                _record_plan_purchase(
                    db,
                    athlete_id=athlete.id,
                    plan_snapshot_id=plan_snapshot_id,
                    stripe_session_id=event_id,
                    stripe_payment_intent_id=payment_intent_id,
                )
            db.commit()
            return {
                "processed": True,
                "event_id": event_id,
                "event_type": event_type,
                "mode": "payment",
                "athlete_id": str(athlete.id),
                "plan_snapshot_id": plan_snapshot_id,
            }

        # Subscription checkout: mirror tier using price→tier map.
        sub = _ensure_subscription_row(db, athlete_id=athlete.id)
        if customer_id:
            sub.stripe_customer_id = customer_id
        if subscription_id:
            sub.stripe_subscription_id = subscription_id
        sub.status = "active"
        sub.cancel_at_period_end = False

        # Derive tier from the price on the session (prefer metadata tier if present).
        price_id = metadata.get("price_id") or _extract_price_id_from_session(obj)
        granted_tier = tier_for_price_and_status(price_id, "active", price_to_tier)
        # Fallback: if metadata explicitly carries canonical tier, use it.
        if granted_tier == "free" and metadata.get("tier") in ("guided", "premium"):
            granted_tier = metadata["tier"]

        _apply_stripe_tier(athlete, granted_tier)
        db.add(athlete)
        db.add(sub)
        db.commit()
        return {
            "processed": True,
            "event_id": event_id,
            "event_type": event_type,
            "mode": "subscription",
            "athlete_id": str(athlete.id),
            "granted_tier": athlete.subscription_tier,  # effective tier (may differ if override active)
        }

    # ------------------------------------------------------------------
    # customer.subscription.updated / customer.subscription.deleted
    # ------------------------------------------------------------------
    if event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
        customer_id = str(getattr(obj, "customer", None) or "")
        subscription_id = str(getattr(obj, "id", None) or "")
        status = str(getattr(obj, "status", None) or "") or None
        current_period_end_ts = _extract_current_period_end_ts(obj)
        cancel_at_ts = _extract_cancel_at_ts(obj)
        if current_period_end_ts is None and cancel_at_ts is not None:
            current_period_end_ts = cancel_at_ts
        current_period_end = _maybe_parse_period_end(current_period_end_ts)
        cancel_at_period_end = _derive_cancel_at_period_end(obj, current_period_end_ts=current_period_end_ts)

        athlete = _find_athlete_by_customer_id(customer_id)
        if not athlete and subscription_id:
            existing = db.query(Subscription).filter(
                Subscription.stripe_subscription_id == subscription_id
            ).first()
            if existing:
                athlete = db.query(Athlete).filter(Athlete.id == existing.athlete_id).first()

        if not athlete:
            db.commit()
            return {
                "processed": True,
                "event_id": event_id,
                "event_type": event_type,
                "matched_athlete": False,
            }

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

        price_id: Optional[str] = None
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

        # Derive tier via price→tier map (fail closed on unknown price).
        _apply_stripe_tier(athlete, tier_for_price_and_status(price_id, status, price_to_tier))
        db.add(athlete)
        db.commit()
        return {
            "processed": True,
            "event_id": event_id,
            "event_type": event_type,
            "athlete_id": str(athlete.id),
            "status": status,
            "granted_tier": athlete.subscription_tier,  # effective tier (may differ if override active)
        }

    # Unknown/unhandled event: accept and record, no state change.
    db.commit()
    return {"processed": True, "event_id": event_id, "event_type": event_type, "handled": False}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_price_id_from_session(obj: Any) -> Optional[str]:
    """Best-effort extraction of price_id from a checkout.session object."""
    try:
        line_items = getattr(obj, "line_items", None)
        if line_items:
            data = getattr(line_items, "data", None) or []
            first = data[0] if data else None
            price = getattr(first, "price", None) if first else None
            return getattr(price, "id", None) if price else None
    except Exception:
        pass
    return None


def _record_plan_purchase(
    db: Session,
    *,
    athlete_id: UUID,
    plan_snapshot_id: str,
    stripe_session_id: str,
    stripe_payment_intent_id: str,
) -> None:
    """Insert a PlanPurchase row for a completed one-time payment.

    Idempotent: if the payment_intent already exists, the unique constraint
    prevents a duplicate row and the exception is suppressed.
    """
    try:
        from models import PlanPurchase
        purchase = PlanPurchase(
            athlete_id=athlete_id,
            plan_snapshot_id=plan_snapshot_id,
            stripe_session_id=stripe_session_id,
            stripe_payment_intent_id=stripe_payment_intent_id,
            purchased_at=datetime.now(timezone.utc),
        )
        db.add(purchase)
        db.flush()
    except IntegrityError:
        db.rollback()
        log.info(
            "plan_purchase: duplicate payment_intent=%s — already recorded (idempotent)",
            stripe_payment_intent_id,
        )
    except Exception as exc:
        log.warning("plan_purchase: failed to record purchase: %s", exc)
        db.rollback()
