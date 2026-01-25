from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import or_

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models import AdminAuditEvent, Athlete


client = TestClient(app)


def _headers(user: Athlete) -> dict:
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}", "User-Agent": "pytest"}


def _create_user(db, *, role: str) -> Athlete:
    athlete = Athlete(
        email=f"phase8_audit_{role}_{uuid4()}@example.com",
        display_name=f"Phase8 Audit {role}",
        subscription_tier="elite" if role in ("admin", "owner") else "free",
        role=role,
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    return athlete


def _latest_event(db, *, actor_id, action: str, reason: str) -> AdminAuditEvent | None:
    return (
        db.query(AdminAuditEvent)
        .filter(
            AdminAuditEvent.actor_athlete_id == actor_id,
            AdminAuditEvent.action == action,
            AdminAuditEvent.reason == reason,
        )
        .order_by(AdminAuditEvent.created_at.desc())
        .first()
    )


def _cleanup(db, athlete_ids: list) -> None:
    try:
        if athlete_ids:
            db.query(AdminAuditEvent).filter(
                or_(
                    AdminAuditEvent.actor_athlete_id.in_(athlete_ids),
                    AdminAuditEvent.target_athlete_id.in_(athlete_ids),
                )
            ).delete(synchronize_session=False)
            db.query(Athlete).filter(Athlete.id.in_(athlete_ids)).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()


def test_audit_event_emitted_for_system_ingestion_pause():
    """
    High-risk mutation: global ingestion pause/resume must emit an AdminAuditEvent
    with action + reason + bounded payload.
    """
    db = SessionLocal()
    owner = None
    try:
        owner = _create_user(db, role="owner")
        reason = f"phase8_audit_pause_{uuid4()}"

        resp = client.post(
            "/v1/admin/ops/ingestion/pause",
            headers=_headers(owner),
            json={"paused": True, "reason": reason},
        )
        assert resp.status_code == 200, resp.text

        ev = _latest_event(db, actor_id=owner.id, action="system.ingestion.pause", reason=reason)
        assert ev is not None
        assert ev.created_at is not None
        assert ev.target_athlete_id is None
        assert ev.ip_address is not None  # best-effort from TestClient
        assert isinstance(ev.payload, dict)
        assert "before" in ev.payload and "after" in ev.payload
        assert ev.payload["after"].get("paused") is True
    finally:
        try:
            if owner is not None:
                _cleanup(db, [owner.id])
        finally:
            db.close()


def test_audit_event_emitted_for_billing_comp():
    """
    High-risk mutation: billing comp must emit an AdminAuditEvent with before/after.
    """
    db = SessionLocal()
    owner = None
    target = None
    try:
        owner = _create_user(db, role="owner")
        target = _create_user(db, role="athlete")
        reason = f"phase8_audit_comp_{uuid4()}"

        resp = client.post(
            f"/v1/admin/users/{target.id}/comp",
            headers=_headers(owner),
            json={"tier": "pro", "reason": reason},
        )
        assert resp.status_code == 200, resp.text

        ev = _latest_event(db, actor_id=owner.id, action="billing.comp", reason=reason)
        assert ev is not None
        assert str(ev.target_athlete_id) == str(target.id)
        assert isinstance(ev.payload, dict)
        assert ev.payload.get("before", {}).get("subscription_tier") in ("free", "pro", "elite", "premium", "guided", "subscription", None)
        assert ev.payload.get("after", {}).get("subscription_tier") == "pro"
    finally:
        try:
            ids = [x.id for x in (owner, target) if x is not None]
            _cleanup(db, ids)
        finally:
            db.close()


def test_audit_event_emitted_for_athlete_block():
    """
    High-risk mutation: block/unblock must emit an AdminAuditEvent with before/after.
    """
    db = SessionLocal()
    owner = None
    target = None
    try:
        owner = _create_user(db, role="owner")
        target = _create_user(db, role="athlete")
        reason = f"phase8_audit_block_{uuid4()}"

        resp = client.post(
            f"/v1/admin/users/{target.id}/block",
            headers=_headers(owner),
            json={"blocked": True, "reason": reason},
        )
        assert resp.status_code == 200, resp.text

        ev = _latest_event(db, actor_id=owner.id, action="athlete.block", reason=reason)
        assert ev is not None
        assert str(ev.target_athlete_id) == str(target.id)
        assert isinstance(ev.payload, dict)
        assert "before" in ev.payload and "after" in ev.payload
        assert ev.payload["after"].get("is_blocked") is True
    finally:
        try:
            ids = [x.id for x in (owner, target) if x is not None]
            _cleanup(db, ids)
        finally:
            db.close()


def test_audit_event_emitted_for_admin_permissions_set():
    """
    High-risk mutation: owner-only permissions set must emit an AdminAuditEvent with before/after.
    """
    db = SessionLocal()
    owner = None
    target_admin = None
    try:
        owner = _create_user(db, role="owner")
        target_admin = _create_user(db, role="admin")
        reason = f"phase8_audit_perms_{uuid4()}"

        resp = client.post(
            f"/v1/admin/users/{target_admin.id}/permissions",
            headers=_headers(owner),
            json={"permissions": ["billing.comp", "athlete.block"], "reason": reason},
        )
        assert resp.status_code == 200, resp.text

        ev = _latest_event(db, actor_id=owner.id, action="admin.permissions.set", reason=reason)
        assert ev is not None
        assert str(ev.target_athlete_id) == str(target_admin.id)
        assert isinstance(ev.payload, dict)
        assert "before" in ev.payload and "after" in ev.payload
        after = ev.payload.get("after") or {}
        assert after.get("admin_permissions") == ["billing.comp", "athlete.block"]
    finally:
        try:
            ids = [x.id for x in (owner, target_admin) if x is not None]
            _cleanup(db, ids)
        finally:
            db.close()

