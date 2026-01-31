import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models import Athlete, InviteAllowlist, FeatureFlag


client = TestClient(app)


def test_register_allows_without_invite_when_flag_disabled():
    email = f"no_invite_{uuid4()}@example.com"
    resp = client.post(
        "/v1/auth/register",
        json={"email": email, "password": "password123", "display_name": "Test"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body.get("access_token")
    assert body.get("athlete", {}).get("email") == email.lower()


def test_register_requires_invite_when_flag_enabled():
    db = SessionLocal()
    email = f"no_invite_required_{uuid4()}@example.com".lower()
    try:
        # Enable invite requirement via system flag.
        ff = db.query(FeatureFlag).filter(FeatureFlag.key == "system.invites_required").first()
        if not ff:
            ff = FeatureFlag(
                key="system.invites_required",
                name="Require invites for signup",
                description="Test flag: require invite allowlist for registration",
                enabled=True,
                requires_subscription=False,
                requires_tier=None,
                requires_payment=None,
                rollout_percentage=100,
            )
            db.add(ff)
        else:
            ff.enabled = True
        db.commit()

        resp = client.post(
            "/v1/auth/register",
            json={"email": email, "password": "password123", "display_name": "Test"},
        )
        assert resp.status_code == 403
        assert resp.json().get("detail") == "Invite required"
    finally:
        # Disable flag after test (avoid cross-test coupling).
        try:
            ff = db.query(FeatureFlag).filter(FeatureFlag.key == "system.invites_required").first()
            if ff:
                ff.enabled = False
            athlete = db.query(Athlete).filter(Athlete.email == email).first()
            if athlete:
                db.delete(athlete)
            db.commit()
        except Exception:
            db.rollback()
        db.close()


def test_register_with_invite_marks_used():
    db = SessionLocal()
    email = f"invited_{uuid4()}@example.com".lower()
    try:
        inv = InviteAllowlist(email=email, is_active=True)
        db.add(inv)
        db.commit()

        resp = client.post(
            "/v1/auth/register",
            json={"email": email, "password": "password123", "display_name": "Invited"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body.get("access_token")

        db.refresh(inv)
        assert inv.used_at is not None
        assert inv.used_by_athlete_id is not None
        assert inv.is_active is False
    finally:
        # Best-effort cleanup
        try:
            athlete = db.query(Athlete).filter(Athlete.email == email).first()
            if athlete:
                db.delete(athlete)
            inv = db.query(InviteAllowlist).filter(InviteAllowlist.email == email).first()
            if inv:
                db.delete(inv)
            db.commit()
        except Exception:
            db.rollback()
        db.close()


def test_register_with_grant_tier_applies_pro():
    """
    When an invite has grant_tier='pro', the registered user should
    automatically get subscription_tier='pro' instead of 'free'.
    """
    db = SessionLocal()
    email = f"beta_tester_{uuid4()}@example.com".lower()
    try:
        # Create invite with grant_tier='pro' (beta tester)
        inv = InviteAllowlist(email=email, is_active=True, grant_tier="pro", note="Beta tester")
        db.add(inv)
        db.commit()

        resp = client.post(
            "/v1/auth/register",
            json={"email": email, "password": "password123", "display_name": "Beta Tester"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body.get("access_token")
        
        # Verify the athlete was created with pro tier
        athlete = db.query(Athlete).filter(Athlete.email == email).first()
        assert athlete is not None
        assert athlete.subscription_tier == "pro", f"Expected 'pro', got '{athlete.subscription_tier}'"
        
        # Verify invite was marked as used
        db.refresh(inv)
        assert inv.used_at is not None
        assert inv.is_active is False
    finally:
        # Cleanup
        try:
            athlete = db.query(Athlete).filter(Athlete.email == email).first()
            if athlete:
                db.delete(athlete)
            inv = db.query(InviteAllowlist).filter(InviteAllowlist.email == email).first()
            if inv:
                db.delete(inv)
            db.commit()
        except Exception:
            db.rollback()
        db.close()


def test_register_without_grant_tier_defaults_to_free():
    """
    When an invite has no grant_tier (null), the registered user should
    get the default subscription_tier='free'.
    """
    db = SessionLocal()
    email = f"regular_invite_{uuid4()}@example.com".lower()
    try:
        # Create invite without grant_tier
        inv = InviteAllowlist(email=email, is_active=True, grant_tier=None)
        db.add(inv)
        db.commit()

        resp = client.post(
            "/v1/auth/register",
            json={"email": email, "password": "password123", "display_name": "Regular User"},
        )
        assert resp.status_code == 201
        
        # Verify the athlete was created with free tier
        athlete = db.query(Athlete).filter(Athlete.email == email).first()
        assert athlete is not None
        assert athlete.subscription_tier == "free", f"Expected 'free', got '{athlete.subscription_tier}'"
    finally:
        # Cleanup
        try:
            athlete = db.query(Athlete).filter(Athlete.email == email).first()
            if athlete:
                db.delete(athlete)
            inv = db.query(InviteAllowlist).filter(InviteAllowlist.email == email).first()
            if inv:
                db.delete(inv)
            db.commit()
        except Exception:
            db.rollback()
        db.close()


def test_register_with_revoked_invite_blocked_when_required():
    """
    If invites are required and the invite was revoked, registration should fail.
    """
    db = SessionLocal()
    email = f"revoked_invite_{uuid4()}@example.com".lower()
    try:
        # Enable invite requirement
        ff = db.query(FeatureFlag).filter(FeatureFlag.key == "system.invites_required").first()
        if not ff:
            ff = FeatureFlag(
                key="system.invites_required",
                name="Require invites for signup",
                description="Test flag",
                enabled=True,
                requires_subscription=False,
            )
            db.add(ff)
        else:
            ff.enabled = True
        
        # Create and revoke invite
        inv = InviteAllowlist(email=email, is_active=False, grant_tier="pro")  # revoked
        db.add(inv)
        db.commit()

        resp = client.post(
            "/v1/auth/register",
            json={"email": email, "password": "password123", "display_name": "Revoked User"},
        )
        # Should be blocked because invite is not active
        assert resp.status_code == 403
        assert resp.json().get("detail") == "Invite required"
    finally:
        try:
            ff = db.query(FeatureFlag).filter(FeatureFlag.key == "system.invites_required").first()
            if ff:
                ff.enabled = False
            athlete = db.query(Athlete).filter(Athlete.email == email).first()
            if athlete:
                db.delete(athlete)
            inv = db.query(InviteAllowlist).filter(InviteAllowlist.email == email).first()
            if inv:
                db.delete(inv)
            db.commit()
        except Exception:
            db.rollback()
        db.close()


def test_register_with_already_used_invite_blocked_when_required():
    """
    If invites are required and the invite was already used, registration should fail.
    """
    from datetime import datetime, timezone
    db = SessionLocal()
    email = f"used_invite_{uuid4()}@example.com".lower()
    try:
        # Enable invite requirement
        ff = db.query(FeatureFlag).filter(FeatureFlag.key == "system.invites_required").first()
        if not ff:
            ff = FeatureFlag(
                key="system.invites_required",
                name="Require invites for signup",
                description="Test flag",
                enabled=True,
                requires_subscription=False,
            )
            db.add(ff)
        else:
            ff.enabled = True
        
        # Create already-used invite
        inv = InviteAllowlist(
            email=email, 
            is_active=False, 
            grant_tier="pro",
            used_at=datetime.now(timezone.utc),
        )
        db.add(inv)
        db.commit()

        resp = client.post(
            "/v1/auth/register",
            json={"email": email, "password": "password123", "display_name": "Used Invite User"},
        )
        # Should be blocked because invite is already used
        assert resp.status_code == 403
        assert resp.json().get("detail") == "Invite required"
    finally:
        try:
            ff = db.query(FeatureFlag).filter(FeatureFlag.key == "system.invites_required").first()
            if ff:
                ff.enabled = False
            athlete = db.query(Athlete).filter(Athlete.email == email).first()
            if athlete:
                db.delete(athlete)
            inv = db.query(InviteAllowlist).filter(InviteAllowlist.email == email).first()
            if inv:
                db.delete(inv)
            db.commit()
        except Exception:
            db.rollback()
        db.close()

