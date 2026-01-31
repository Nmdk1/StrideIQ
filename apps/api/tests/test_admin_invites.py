import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models import Athlete, InviteAllowlist


client = TestClient(app)


@pytest.fixture
def admin_user():
    db = SessionLocal()
    athlete = Athlete(
        email=f"admin_invites_{uuid4()}@example.com",
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
def admin_headers(admin_user):
    token = create_access_token({"sub": str(admin_user.id)})
    return {"Authorization": f"Bearer {token}"}


def test_admin_create_and_revoke_invite(admin_headers):
    email = f"invite_{uuid4()}@example.com"
    resp = client.post("/v1/admin/invites", json={"email": email, "note": "test"}, headers=admin_headers)
    assert resp.status_code == 200
    inv = resp.json()["invite"]
    assert inv["email"] == email.lower()
    assert inv["is_active"] is True

    resp2 = client.post("/v1/admin/invites/revoke", json={"email": email, "reason": "nope"}, headers=admin_headers)
    assert resp2.status_code == 200
    inv2 = resp2.json()["invite"]
    assert inv2["email"] == email.lower()
    assert inv2["is_active"] is False

    # DB sanity
    db = SessionLocal()
    try:
        row = db.query(InviteAllowlist).filter(InviteAllowlist.email == email.lower()).first()
        assert row is not None
        assert row.is_active is False
    finally:
        try:
            if row:
                db.delete(row)
            db.commit()
        except Exception:
            db.rollback()
        db.close()


def test_admin_create_invite_with_grant_tier(admin_headers):
    """Admin can create an invite with grant_tier='pro' for beta testers."""
    email = f"beta_invite_{uuid4()}@example.com"
    resp = client.post(
        "/v1/admin/invites", 
        json={"email": email, "note": "Beta tester - Brian", "grant_tier": "pro"}, 
        headers=admin_headers
    )
    assert resp.status_code == 200
    inv = resp.json()["invite"]
    assert inv["email"] == email.lower()
    assert inv["is_active"] is True
    assert inv["grant_tier"] == "pro"

    # DB sanity
    db = SessionLocal()
    try:
        row = db.query(InviteAllowlist).filter(InviteAllowlist.email == email.lower()).first()
        assert row is not None
        assert row.grant_tier == "pro"
    finally:
        try:
            if row:
                db.delete(row)
            db.commit()
        except Exception:
            db.rollback()
        db.close()


def test_admin_create_invite_without_grant_tier_defaults_null(admin_headers):
    """Invite without grant_tier should have grant_tier=null (user gets default 'free' tier)."""
    email = f"standard_invite_{uuid4()}@example.com"
    resp = client.post(
        "/v1/admin/invites", 
        json={"email": email, "note": "Standard invite"}, 
        headers=admin_headers
    )
    assert resp.status_code == 200
    inv = resp.json()["invite"]
    assert inv["email"] == email.lower()
    assert inv["grant_tier"] is None

    # DB sanity
    db = SessionLocal()
    try:
        row = db.query(InviteAllowlist).filter(InviteAllowlist.email == email.lower()).first()
        assert row is not None
        assert row.grant_tier is None
    finally:
        try:
            if row:
                db.delete(row)
            db.commit()
        except Exception:
            db.rollback()
        db.close()

