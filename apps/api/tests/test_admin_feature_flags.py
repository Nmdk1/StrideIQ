"""
Integration tests for admin feature flag management endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models import Athlete, FeatureFlag


client = TestClient(app)


@pytest.fixture
def admin_user():
    db = SessionLocal()
    try:
        athlete = Athlete(
            email=f"admin_{uuid4()}@example.com",
            display_name="Admin User",
            subscription_tier="elite",
            role="admin",
        )
        db.add(athlete)
        db.commit()
        db.refresh(athlete)
        yield athlete
    finally:
        # Cleanup best-effort
        try:
            db.delete(athlete)
            db.commit()
        except Exception:
            db.rollback()
        db.close()


@pytest.fixture
def admin_headers(admin_user):
    token = create_access_token({"sub": str(admin_user.id)})
    return {"Authorization": f"Bearer {token}"}


def test_admin_feature_flags_requires_auth():
    resp = client.get("/v1/admin/feature-flags")
    assert resp.status_code in (401, 403)


def test_admin_feature_flags_list_success(admin_headers):
    resp = client.get("/v1/admin/feature-flags?prefix=plan.", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "flags" in data
    assert isinstance(data["flags"], list)


def test_set_3d_quality_selection_mode_shadow(admin_headers):
    resp = client.post(
        "/v1/admin/features/3d-quality-selection",
        json={"mode": "shadow", "rollout_percentage": 0, "allowlist_emails": []},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["mode"] == "shadow"

    # Verify flags were set in DB
    db = SessionLocal()
    try:
        on_flag = db.query(FeatureFlag).filter(FeatureFlag.key == "plan.3d_workout_selection").first()
        shadow_flag = db.query(FeatureFlag).filter(FeatureFlag.key == "plan.3d_workout_selection_shadow").first()
        assert on_flag is not None
        assert shadow_flag is not None
        assert on_flag.enabled is False
        assert shadow_flag.enabled is True
    finally:
        db.close()

