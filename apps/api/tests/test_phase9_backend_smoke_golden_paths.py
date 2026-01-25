from __future__ import annotations

import hmac
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import or_

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models import AdminAuditEvent, Athlete, PlannedWorkout, StripeEvent, TrainingPlan


client = TestClient(app)


def _headers(user: Athlete) -> dict:
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}", "User-Agent": "pytest"}


def _create_user(db, *, role: str, **kwargs) -> Athlete:
    subscription_tier = kwargs.pop("subscription_tier", None)
    athlete = Athlete(
        email=f"phase9_{role}_{uuid4()}@example.com",
        display_name=f"Phase9 {role}",
        subscription_tier=subscription_tier or ("elite" if role in ("admin", "owner") else "free"),
        role=role,
        **kwargs,
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    return athlete


def _cleanup(db, athlete_ids: list) -> None:
    try:
        if athlete_ids:
            # Delete plan rows first to avoid FK violations when removing athletes.
            db.query(PlannedWorkout).filter(PlannedWorkout.athlete_id.in_(athlete_ids)).delete(synchronize_session=False)
            db.query(TrainingPlan).filter(TrainingPlan.athlete_id.in_(athlete_ids)).delete(synchronize_session=False)
            db.query(AdminAuditEvent).filter(
                or_(
                    AdminAuditEvent.actor_athlete_id.in_(athlete_ids),
                    AdminAuditEvent.target_athlete_id.in_(athlete_ids),
                )
            ).delete(synchronize_session=False)
            db.query(StripeEvent).delete(synchronize_session=False)
            db.query(Athlete).filter(Athlete.id.in_(athlete_ids)).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()


class _DummyStripeConfig:
    def __init__(self, *, webhook_secret: str):
        self.secret_key = "sk_test_dummy"
        self.webhook_secret = webhook_secret
        self.pro_monthly_price_id = "price_dummy"
        self.checkout_success_url = "http://localhost:3000/settings?stripe=success"
        self.checkout_cancel_url = "http://localhost:3000/settings?stripe=cancel"
        self.portal_return_url = "http://localhost:3000/settings"


def _stripe_sig_header(*, secret: str, payload: bytes, timestamp: int) -> str:
    """
    Generate a Stripe-compatible signature header for a given webhook payload.
    Stripe signs: "{timestamp}.{payload}" with HMAC-SHA256 using the webhook secret.
    """
    signed_payload = f"{timestamp}.".encode("utf-8") + payload
    digest = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def test_stripe_webhook_rejects_invalid_signature(monkeypatch):
    """
    Phase 9 backend smoke: Stripe webhook signature validation (negative control).
    Invalid signature must return 400 and must not record a StripeEvent.
    """
    from services import stripe_service as ss

    webhook_secret = "whsec_test_" + ("x" * 24)
    monkeypatch.setattr(ss, "_get_stripe_config", lambda: _DummyStripeConfig(webhook_secret=webhook_secret))

    event_id = f"evt_{uuid4().hex}"
    payload = json.dumps(
        {
            "id": event_id,
            "type": "charge.succeeded",
            "created": int(datetime.now(timezone.utc).timestamp()),
            "data": {"object": {"id": "ch_test"}},
        }
    ).encode("utf-8")

    ts = int(datetime.now(timezone.utc).timestamp())
    bad_sig = _stripe_sig_header(secret="whsec_wrong_" + ("y" * 24), payload=payload, timestamp=ts)

    resp = client.post("/v1/billing/webhooks/stripe", data=payload, headers={"Stripe-Signature": bad_sig})
    assert resp.status_code == 400, resp.text

    db = SessionLocal()
    try:
        assert db.query(StripeEvent).filter(StripeEvent.event_id == event_id).count() == 0
    finally:
        db.close()


def test_stripe_webhook_accepts_valid_signature_and_records_event(monkeypatch):
    """
    Phase 9 backend smoke: Stripe webhook signature validation (positive control).
    Valid signature should return 200 and record an idempotency StripeEvent row.
    """
    from services import stripe_service as ss

    webhook_secret = "whsec_test_" + ("x" * 24)
    monkeypatch.setattr(ss, "_get_stripe_config", lambda: _DummyStripeConfig(webhook_secret=webhook_secret))

    event_id = f"evt_{uuid4().hex}"
    payload = json.dumps(
        {
            "id": event_id,
            "type": "charge.succeeded",  # unhandled type → accepted but no-op
            "created": int(datetime.now(timezone.utc).timestamp()),
            "data": {"object": {"id": "ch_test"}},
        }
    ).encode("utf-8")

    ts = int(datetime.now(timezone.utc).timestamp())
    sig = _stripe_sig_header(secret=webhook_secret, payload=payload, timestamp=ts)

    resp = client.post("/v1/billing/webhooks/stripe", data=payload, headers={"Stripe-Signature": sig})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("ok") is True

    db = SessionLocal()
    try:
        assert db.query(StripeEvent).filter(StripeEvent.event_id == event_id).count() == 1
    finally:
        db.close()


def test_admin_comp_transitions_paid_to_free():
    """
    Phase 9 backend smoke: entitlement transitions remain deterministic.
    Owner can comp a user to pro and back to free.
    """
    db = SessionLocal()
    owner = None
    target = None
    try:
        owner = _create_user(db, role="owner")
        target = _create_user(db, role="athlete")

        r1 = client.post(
            f"/v1/admin/users/{target.id}/comp",
            headers=_headers(owner),
            json={"tier": "pro", "reason": "phase9 entitlement pro"},
        )
        assert r1.status_code == 200, r1.text

        db.refresh(target)
        assert target.subscription_tier == "pro"
        assert bool(getattr(target, "has_active_subscription", False)) is True

        r2 = client.post(
            f"/v1/admin/users/{target.id}/comp",
            headers=_headers(owner),
            json={"tier": "free", "reason": "phase9 entitlement free"},
        )
        assert r2.status_code == 200, r2.text

        db.refresh(target)
        assert target.subscription_tier == "free"
        assert bool(getattr(target, "has_active_subscription", False)) is False
    finally:
        try:
            ids = [x.id for x in (owner, target) if x is not None]
            _cleanup(db, ids)
        finally:
            db.close()


def test_ingestion_pause_blocks_admin_retry():
    """
    Phase 9 backend smoke: ingestion safety seam.
    When global ingestion is paused, admin retry must be blocked (409).
    """
    db = SessionLocal()
    owner = None
    target = None
    try:
        owner = _create_user(db, role="owner")
        target = _create_user(
            db,
            role="athlete",
            strava_access_token="encrypted_token_placeholder",
            strava_refresh_token="encrypted_refresh_placeholder",
        )

        pause = client.post(
            "/v1/admin/ops/ingestion/pause",
            headers=_headers(owner),
            json={"paused": True, "reason": "phase9 pause"},
        )
        assert pause.status_code == 200, pause.text

        blocked = client.post(
            f"/v1/admin/users/{target.id}/ingestion/retry",
            headers=_headers(owner),
            json={"pages": 5, "reason": "phase9 retry while paused"},
        )
        assert blocked.status_code == 409, blocked.text
    finally:
        try:
            # Best-effort unpause (don’t block cleanup if it fails).
            if owner is not None:
                client.post(
                    "/v1/admin/ops/ingestion/pause",
                    headers=_headers(owner),
                    json={"paused": False, "reason": "phase9 cleanup"},
                )
        except Exception:
            pass
        try:
            ids = [x.id for x in (owner, target) if x is not None]
            _cleanup(db, ids)
        finally:
            db.close()


def test_v2_standard_plan_preview_shape_is_stable():
    """
    Phase 9 backend smoke: plan generation preview returns a stable, bounded shape.
    Public endpoint (no auth): POST /v2/plans/standard/preview
    """
    resp = client.post(
        "/v2/plans/standard/preview",
        json={
            "distance": "10k",
            "duration_weeks": 8,
            "days_per_week": 5,
            "volume_tier": "mid",
            "start_date": None,
            "race_name": None,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Top-level contract
    for key in (
        "plan_tier",
        "distance",
        "duration_weeks",
        "volume_tier",
        "days_per_week",
        "workouts",
        "weekly_volumes",
        "peak_volume",
        "total_miles",
        "total_quality_sessions",
    ):
        assert key in data, f"missing key: {key}"

    assert data["distance"] == "10k"
    assert int(data["duration_weeks"]) == 8
    assert isinstance(data["workouts"], list) and len(data["workouts"]) > 0
    assert isinstance(data["weekly_volumes"], list) and len(data["weekly_volumes"]) == 8

    # Spot-check one workout record has stable fields.
    w0 = data["workouts"][0]
    for key in ("week", "day", "workout_type", "title", "description"):
        assert key in w0


def test_v2_standard_plan_create_requires_auth():
    """
    Negative control: authenticated athlete is required to create/save a plan.
    """
    resp = client.post(
        "/v2/plans/standard",
        json={
            "distance": "10k",
            "duration_weeks": 8,
            "days_per_week": 5,
            "volume_tier": "mid",
            "start_date": None,
            "race_name": "Phase 9 Standard Plan",
        },
    )
    assert resp.status_code == 401, resp.text


def test_v2_standard_plan_create_succeeds_for_authenticated_athlete():
    """
    Positive control: authenticated athlete can create/save a standard plan.
    """
    db = SessionLocal()
    athlete = None
    try:
        athlete = _create_user(db, role="athlete")
        resp = client.post(
            "/v2/plans/standard",
            headers=_headers(athlete),
            json={
                "distance": "10k",
                "duration_weeks": 8,
                "days_per_week": 5,
                "volume_tier": "mid",
                "start_date": None,
                "race_name": "Phase 9 Standard Plan",
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("success") is True
        assert "plan_id" in body and body["plan_id"]
    finally:
        try:
            if athlete is not None:
                _cleanup(db, [athlete.id])
        finally:
            db.close()


def test_v2_model_driven_plan_requires_elite_tier(monkeypatch):
    """
    Phase 9 backend smoke: tier gating for model-driven plan generation.

    We force the feature flag ON to ensure we’re testing the *tier gate* (not flag gate),
    and then assert non-elite athletes are denied with stable 403 semantics.
    """
    import routers.plan_generation as pg

    # Force feature flag enabled so we hit the tier check.
    monkeypatch.setattr(pg.FeatureFlagService, "is_enabled", lambda self, key, athlete: True)

    db = SessionLocal()
    athlete = None
    try:
        athlete = _create_user(db, role="athlete", subscription_tier="free")

        race_date = (date.today() + timedelta(days=70)).isoformat()
        resp = client.post(
            "/v2/plans/model-driven",
            headers=_headers(athlete),
            json={"race_date": race_date, "race_distance": "marathon", "goal_time_seconds": None, "force_recalibrate": False},
        )
        assert resp.status_code == 403, resp.text
        detail = resp.json().get("detail")
        assert isinstance(detail, dict)
        assert "Elite" in (detail.get("reason") or "")
        assert detail.get("upgrade_path")
    finally:
        try:
            if athlete is not None:
                _cleanup(db, [athlete.id])
        finally:
            db.close()


def test_v2_model_driven_plan_requires_auth(monkeypatch):
    """
    Negative control: model-driven generation requires authentication (401).
    """
    # Use an always-valid request body; we should fail before validation matters.
    race_date = (date.today() + timedelta(days=70)).isoformat()
    resp = client.post("/v2/plans/model-driven", json={"race_date": race_date, "race_distance": "marathon"})
    assert resp.status_code == 401, resp.text

