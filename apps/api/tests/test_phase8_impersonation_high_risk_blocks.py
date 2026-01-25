import pytest
from fastapi.testclient import TestClient
from sqlalchemy import or_
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
def admin_user_with_perms():
    """
    Admin user with explicit permissions so the only blocker is impersonation guard.
    """
    db = SessionLocal()
    athlete = Athlete(
        email=f"admin_{uuid4()}@example.com",
        display_name="Admin",
        subscription_tier="elite",
        role="admin",
    )
    athlete.admin_permissions = [
        "system.ingestion.pause",
        "billing.comp",
        "billing.trial.grant",
        "billing.trial.revoke",
        "athlete.block",
        "onboarding.reset",
        "ingestion.retry",
        "plan.starter.regenerate",
    ]
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


def test_impersonation_token_cannot_call_high_risk_admin_mutations(owner_user, admin_user_with_perms, target_user):
    """
    Phase 8 Sprint 2 / Item #1:
    Impersonation tokens must not be usable for high-risk admin mutations.
    """
    # Owner impersonates an admin (this would otherwise allow admin mutations).
    resp = client.post(
        f"/v1/admin/users/{admin_user_with_perms.id}/impersonate",
        headers=_headers(owner_user),
        json={"reason": "support debug", "ttl_minutes": 15},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["token"]
    imp_headers = {"Authorization": f"Bearer {token}"}

    # Read-only admin endpoint should still work for triage.
    resp = client.get(f"/v1/admin/users/{target_user.id}", headers=imp_headers)
    assert resp.status_code == 200, resp.text

    # High-risk mutations must be blocked with a stable code prefix.
    cases = [
        (
            "POST",
            "/v1/admin/ops/ingestion/pause",
            {"paused": True, "reason": "test"},
        ),
        (
            "POST",
            f"/v1/admin/users/{target_user.id}/comp",
            {"tier": "pro", "reason": "test"},
        ),
        (
            "POST",
            f"/v1/admin/users/{target_user.id}/trial/grant",
            {"days": 7, "reason": "test"},
        ),
        (
            "POST",
            f"/v1/admin/users/{target_user.id}/trial/revoke",
            {"reason": "test"},
        ),
        (
            "POST",
            f"/v1/admin/users/{target_user.id}/block",
            {"blocked": True, "reason": "test"},
        ),
        (
            "POST",
            f"/v1/admin/users/{target_user.id}/onboarding/reset",
            {"stage": "initial", "reason": "test"},
        ),
        (
            "POST",
            f"/v1/admin/users/{target_user.id}/ingestion/retry",
            {"pages": 5, "reason": "test"},
        ),
    ]

    for method, url, body in cases:
        if method == "POST":
            r = client.post(url, headers=imp_headers, json=body)
        else:
            r = client.request(method, url, headers=imp_headers, json=body)

        assert r.status_code == 403, (url, r.status_code, r.text)
        detail = (r.json() or {}).get("detail")
        assert isinstance(detail, str)
        assert detail.startswith("impersonation_not_allowed:"), detail

    # Cleanup
    db = SessionLocal()
    try:
        db.query(AdminAuditEvent).filter(
            or_(
                AdminAuditEvent.actor_athlete_id.in_([owner_user.id, admin_user_with_perms.id, target_user.id]),
                AdminAuditEvent.target_athlete_id.in_([owner_user.id, admin_user_with_perms.id, target_user.id]),
            )
        ).delete(synchronize_session=False)
        db.query(Athlete).filter(Athlete.id.in_([owner_user.id, admin_user_with_perms.id, target_user.id])).delete(
            synchronize_session=False
        )
        db.commit()
    finally:
        db.close()

