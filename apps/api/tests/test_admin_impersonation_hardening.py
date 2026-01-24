import pytest
from fastapi.testclient import TestClient
from uuid import uuid4
from datetime import datetime, timezone

from main import app
from core.database import SessionLocal
from core.security import create_access_token, decode_access_token
from models import Athlete, AdminAuditEvent


client = TestClient(app)


@pytest.fixture
def owner_user():
    db = SessionLocal()
    athlete = Athlete(
        email=f"owner_{uuid4()}@example.com",
        display_name="Owner",
        subscription_tier="elite",
        role="owner",
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    db.close()
    return athlete


@pytest.fixture
def admin_user():
    db = SessionLocal()
    athlete = Athlete(
        email=f"admin_{uuid4()}@example.com",
        display_name="Admin",
        subscription_tier="elite",
        role="admin",
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    db.close()
    return athlete


@pytest.fixture
def target_user():
    db = SessionLocal()
    athlete = Athlete(
        email=f"target_{uuid4()}@example.com",
        display_name="Target",
        subscription_tier="free",
        role="athlete",
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    db.close()
    return athlete


def _headers(user: Athlete) -> dict:
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def test_impersonation_is_owner_only(admin_user, target_user):
    resp = client.post(f"/v1/admin/users/{target_user.id}/impersonate", headers=_headers(admin_user))
    assert resp.status_code == 403


def test_impersonation_is_timeboxed_and_audited(owner_user, target_user):
    resp = client.post(
        f"/v1/admin/users/{target_user.id}/impersonate",
        headers=_headers(owner_user),
        json={"reason": "support debug", "ttl_minutes": 15},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["id"] == str(target_user.id)
    assert data["ttl_minutes"] == 15
    assert data["expires_at"] is not None

    payload = decode_access_token(data["token"])
    assert payload is not None
    assert payload.get("is_impersonation") is True
    assert payload.get("impersonated_by") == str(owner_user.id)
    assert payload.get("sub") == str(target_user.id)
    assert payload.get("exp") is not None

    # Ensure audit event recorded
    db = SessionLocal()
    try:
        ev = (
            db.query(AdminAuditEvent)
            .filter(
                AdminAuditEvent.actor_athlete_id == owner_user.id,
                AdminAuditEvent.action == "auth.impersonate.start",
                AdminAuditEvent.target_athlete_id == target_user.id,
            )
            .order_by(AdminAuditEvent.created_at.desc())
            .first()
        )
        assert ev is not None
        assert ev.reason == "support debug"
        assert isinstance(ev.payload, dict)
        assert ev.payload.get("ttl_minutes") == 15
    finally:
        # Cleanup
        db.query(AdminAuditEvent).filter(
            AdminAuditEvent.actor_athlete_id == owner_user.id,
            AdminAuditEvent.target_athlete_id == target_user.id,
            AdminAuditEvent.action == "auth.impersonate.start",
        ).delete(synchronize_session=False)
        db.query(Athlete).filter(Athlete.id.in_([owner_user.id, target_user.id])).delete(synchronize_session=False)
        db.commit()
        db.close()

