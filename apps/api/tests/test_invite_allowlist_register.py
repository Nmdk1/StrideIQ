import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models import Athlete, InviteAllowlist


client = TestClient(app)


def test_register_requires_invite():
    email = f"no_invite_{uuid4()}@example.com"
    resp = client.post(
        "/v1/auth/register",
        json={"email": email, "password": "password123", "display_name": "Test"},
    )
    assert resp.status_code == 403
    assert resp.json().get("detail") == "Invite required"


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

