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


def test_admin_create_duplicate_invite_is_idempotent(admin_headers):
    """Creating an invite for an email that already exists should reactivate it, not fail."""
    email = f"duplicate_invite_{uuid4()}@example.com"
    
    # Create first invite
    resp1 = client.post(
        "/v1/admin/invites", 
        json={"email": email, "note": "First invite"}, 
        headers=admin_headers
    )
    assert resp1.status_code == 200
    inv1 = resp1.json()["invite"]
    
    # Create duplicate invite with different note
    resp2 = client.post(
        "/v1/admin/invites", 
        json={"email": email, "note": "Updated note", "grant_tier": "pro"}, 
        headers=admin_headers
    )
    assert resp2.status_code == 200
    inv2 = resp2.json()["invite"]
    
    # Should be same invite ID, updated grant_tier
    assert inv2["id"] == inv1["id"]
    assert inv2["grant_tier"] == "pro"

    # Cleanup
    db = SessionLocal()
    try:
        row = db.query(InviteAllowlist).filter(InviteAllowlist.email == email.lower()).first()
        if row:
            db.delete(row)
        db.commit()
    except Exception:
        db.rollback()
    db.close()


def test_admin_revoke_nonexistent_invite_returns_404(admin_headers):
    """Revoking an invite that doesn't exist should return 404."""
    email = f"nonexistent_{uuid4()}@example.com"
    resp = client.post(
        "/v1/admin/invites/revoke", 
        json={"email": email, "reason": "Testing"}, 
        headers=admin_headers
    )
    assert resp.status_code == 404


def test_admin_email_case_insensitive(admin_headers):
    """Email should be case-insensitive (stored lowercase)."""
    email_upper = f"UPPERCASE_{uuid4()}@EXAMPLE.COM"
    email_lower = email_upper.lower()
    
    resp = client.post(
        "/v1/admin/invites", 
        json={"email": email_upper, "note": "Case test"}, 
        headers=admin_headers
    )
    assert resp.status_code == 200
    inv = resp.json()["invite"]
    assert inv["email"] == email_lower

    # Cleanup
    db = SessionLocal()
    try:
        row = db.query(InviteAllowlist).filter(InviteAllowlist.email == email_lower).first()
        if row:
            db.delete(row)
        db.commit()
    except Exception:
        db.rollback()
    db.close()


def test_admin_email_whitespace_trimmed(admin_headers):
    """Email with leading/trailing whitespace should be trimmed."""
    base_email = f"whitespace_{uuid4()}@example.com"
    email_with_spaces = f"  {base_email}  "
    
    resp = client.post(
        "/v1/admin/invites", 
        json={"email": email_with_spaces, "note": "Whitespace test"}, 
        headers=admin_headers
    )
    assert resp.status_code == 200
    inv = resp.json()["invite"]
    assert inv["email"] == base_email.lower()

    # Cleanup
    db = SessionLocal()
    try:
        row = db.query(InviteAllowlist).filter(InviteAllowlist.email == base_email.lower()).first()
        if row:
            db.delete(row)
        db.commit()
    except Exception:
        db.rollback()
    db.close()

