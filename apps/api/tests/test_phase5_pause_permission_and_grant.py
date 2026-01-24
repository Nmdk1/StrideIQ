import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models import Athlete, AdminAuditEvent


client = TestClient(app)


def _headers(user: Athlete) -> dict:
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def owner_user():
    db = SessionLocal()
    u = Athlete(email=f"owner_pause_{uuid4()}@example.com", display_name="Owner", role="owner", subscription_tier="elite")
    db.add(u)
    db.commit()
    db.refresh(u)
    db.close()
    return u


@pytest.fixture
def admin_user():
    db = SessionLocal()
    u = Athlete(
        email=f"admin_pause_{uuid4()}@example.com",
        display_name="Admin",
        role="admin",
        subscription_tier="elite",
        admin_permissions=[],  # explicit empty -> bootstrap mode
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    db.close()
    return u


def test_system_pause_requires_explicit_permission(owner_user, admin_user):
    # Admin with empty permissions should be denied (system.* not allowed in bootstrap mode)
    resp = client.post("/v1/admin/ops/ingestion/pause", json={"paused": True, "reason": "test"}, headers=_headers(admin_user))
    assert resp.status_code == 403

    # Owner grants system.ingestion.pause to admin
    resp = client.post(
        f"/v1/admin/users/{admin_user.id}/permissions",
        json={"permissions": ["system.ingestion.pause"], "reason": "grant pause"},
        headers=_headers(owner_user),
    )
    assert resp.status_code == 200
    assert resp.json()["admin_permissions"] == ["system.ingestion.pause"]

    # Admin can now pause
    resp = client.post("/v1/admin/ops/ingestion/pause", json={"paused": True, "reason": "test"}, headers=_headers(admin_user))
    assert resp.status_code == 200
    assert resp.json()["paused"] is True

    # Cleanup
    db = SessionLocal()
    try:
        db.query(AdminAuditEvent).filter(
            AdminAuditEvent.actor_athlete_id.in_([owner_user.id, admin_user.id])
        ).delete(synchronize_session=False)
        db.query(Athlete).filter(Athlete.id.in_([owner_user.id, admin_user.id])).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()

