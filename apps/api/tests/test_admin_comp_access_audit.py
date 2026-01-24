import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models import Athlete, AdminAuditEvent


client = TestClient(app)


@pytest.fixture
def admin_user():
    db = SessionLocal()
    athlete = Athlete(
        email=f"admin_comp_{uuid4()}@example.com",
        display_name="Admin",
        subscription_tier="elite",
        role="admin",
        # Leave admin_permissions empty to exercise "bootstrap mode" (full admin).
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


@pytest.fixture
def normal_user():
    db = SessionLocal()
    athlete = Athlete(
        email=f"user_comp_{uuid4()}@example.com",
        display_name="User",
        subscription_tier="free",
        role="athlete",
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    db.close()
    return athlete


def test_admin_can_comp_access_and_audits(admin_headers, admin_user, normal_user):
    reason = "VIP tester"
    resp = client.post(
        f"/v1/admin/users/{normal_user.id}/comp",
        json={"tier": "elite", "reason": reason},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["success"] is True
    assert payload["user"]["id"] == str(normal_user.id)
    assert payload["user"]["subscription_tier"] == "elite"

    db = SessionLocal()
    try:
        updated = db.query(Athlete).filter(Athlete.id == normal_user.id).first()
        assert updated is not None
        assert updated.subscription_tier == "elite"

        ev = (
            db.query(AdminAuditEvent)
            .filter(
                AdminAuditEvent.actor_athlete_id == admin_user.id,
                AdminAuditEvent.target_athlete_id == normal_user.id,
                AdminAuditEvent.action == "billing.comp",
            )
            .order_by(AdminAuditEvent.created_at.desc())
            .first()
        )
        assert ev is not None
        assert ev.reason == reason
        assert ev.payload.get("before", {}).get("subscription_tier") == "free"
        assert ev.payload.get("after", {}).get("subscription_tier") == "elite"
    finally:
        try:
            # Best-effort cleanup for non-transactional tests.
            if updated:
                db.delete(updated)
            if admin_user:
                admin_row = db.query(Athlete).filter(Athlete.id == admin_user.id).first()
                if admin_row:
                    db.delete(admin_row)
            if ev:
                db.delete(ev)
            db.commit()
        except Exception:
            db.rollback()
        db.close()


def test_non_admin_cannot_comp_access(normal_user):
    token = create_access_token({"sub": str(normal_user.id)})
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post(
        f"/v1/admin/users/{normal_user.id}/comp",
        json={"tier": "elite", "reason": "nope"},
        headers=headers,
    )
    assert resp.status_code == 403

