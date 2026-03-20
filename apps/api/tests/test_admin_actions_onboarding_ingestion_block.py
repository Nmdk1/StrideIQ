import pytest
from fastapi.testclient import TestClient
from uuid import uuid4
from unittest.mock import Mock

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models import Athlete, AdminAuditEvent


client = TestClient(app)


@pytest.fixture
def admin_user():
    db = SessionLocal()
    athlete = Athlete(
        email=f"admin_actions_{uuid4()}@example.com",
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


@pytest.fixture
def normal_user():
    db = SessionLocal()
    athlete = Athlete(
        email=f"user_actions_{uuid4()}@example.com",
        display_name="User",
        subscription_tier="free",
        role="athlete",
        # Simulate connected Strava so ingestion retry can queue.
        strava_access_token="encrypted_token_blob",
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    db.close()
    return athlete


@pytest.fixture
def garmin_user():
    db = SessionLocal()
    athlete = Athlete(
        email=f"garmin_actions_{uuid4()}@example.com",
        display_name="Garmin User",
        subscription_tier="free",
        role="athlete",
        garmin_connected=True,
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    db.close()
    return athlete


def _latest_audit(db, *, actor_id, target_id, action: str):
    return (
        db.query(AdminAuditEvent)
        .filter(AdminAuditEvent.actor_athlete_id == actor_id, AdminAuditEvent.target_athlete_id == target_id, AdminAuditEvent.action == action)
        .order_by(AdminAuditEvent.created_at.desc())
        .first()
    )


def test_reset_onboarding_is_audited(admin_headers, admin_user, normal_user):
    resp = client.post(
        f"/v1/admin/users/{normal_user.id}/onboarding/reset",
        json={"reason": "support reset", "stage": "initial"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["onboarding_completed"] is False

    db = SessionLocal()
    try:
        ev = _latest_audit(db, actor_id=admin_user.id, target_id=normal_user.id, action="onboarding.reset")
        assert ev is not None
        assert ev.reason == "support reset"
        assert ev.payload["after"]["onboarding_completed"] is False
    finally:
        db.close()


def test_retry_ingestion_queues_tasks_and_is_audited(admin_headers, admin_user, normal_user, monkeypatch):
    # Ensure the Phase 5 emergency brake does not interfere with this test.
    from services.plan_framework.feature_flags import FeatureFlagService

    db = SessionLocal()
    try:
        svc = FeatureFlagService(db)
        if svc.get_flag("system.ingestion_paused"):
            svc.set_flag("system.ingestion_paused", {"enabled": False})
    finally:
        db.close()

    index_mock = Mock()
    index_mock.id = "task_index_123"
    sync_mock = Mock()
    sync_mock.id = "task_sync_456"

    delay_calls = {"index": None, "sync": None}

    def _index_delay(*args, **kwargs):
        delay_calls["index"] = {"args": args, "kwargs": kwargs}
        return index_mock

    def _sync_delay(*args, **kwargs):
        delay_calls["sync"] = {"args": args, "kwargs": kwargs}
        return sync_mock

    from tasks import strava_tasks

    monkeypatch.setattr(strava_tasks.backfill_strava_activity_index_task, "delay", _index_delay)
    monkeypatch.setattr(strava_tasks.sync_strava_activities_task, "delay", _sync_delay)

    resp = client.post(
        f"/v1/admin/users/{normal_user.id}/ingestion/retry",
        json={"reason": "stuck", "pages": 7},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["queued"] is True
    assert body["index_task_id"] == "task_index_123"
    assert body["sync_task_id"] == "task_sync_456"

    assert delay_calls["index"]["args"][0] == str(normal_user.id)
    assert delay_calls["index"]["kwargs"]["pages"] == 7
    assert delay_calls["sync"]["args"][0] == str(normal_user.id)

    db = SessionLocal()
    try:
        ev = _latest_audit(db, actor_id=admin_user.id, target_id=normal_user.id, action="ingestion.retry")
        assert ev is not None
        assert ev.reason == "stuck"
        assert ev.payload["provider"] == "strava"
        assert ev.payload["pages"] == 7
        assert ev.payload["index_task_id"] == "task_index_123"
        assert ev.payload["sync_task_id"] == "task_sync_456"
    finally:
        db.close()


def test_retry_ingestion_returns_409_when_system_paused(admin_headers, admin_user, normal_user, monkeypatch):
    # Enable system.ingestion_paused
    from services.plan_framework.feature_flags import FeatureFlagService

    db = SessionLocal()
    try:
        svc = FeatureFlagService(db)
        if not svc.get_flag("system.ingestion_paused"):
            svc.create_flag(
                key="system.ingestion_paused",
                name="Pause global ingestion",
                description="test",
                enabled=True,
                requires_subscription=False,
                requires_tier=None,
                requires_payment=None,
                rollout_percentage=100,
            )
        else:
            svc.set_flag("system.ingestion_paused", {"enabled": True})
    finally:
        db.close()

    resp = client.post(
        f"/v1/admin/users/{normal_user.id}/ingestion/retry",
        json={"reason": "paused test", "pages": 5},
        headers=admin_headers,
    )
    assert resp.status_code == 409
    assert "paused" in resp.text.lower()

    # Reset the brake so other tests aren't affected.
    db = SessionLocal()
    try:
        svc = FeatureFlagService(db)
        if svc.get_flag("system.ingestion_paused"):
            svc.set_flag("system.ingestion_paused", {"enabled": False})
    finally:
        db.close()


def test_block_prevents_auth_and_is_audited(admin_headers, admin_user, normal_user):
    # Block
    resp = client.post(
        f"/v1/admin/users/{normal_user.id}/block",
        json={"blocked": True, "reason": "abuse"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["is_blocked"] is True

    db = SessionLocal()
    try:
        ev = _latest_audit(db, actor_id=admin_user.id, target_id=normal_user.id, action="athlete.block")
        assert ev is not None
        assert ev.reason == "abuse"
    finally:
        db.close()

    # Blocked user cannot access authenticated endpoints
    token = create_access_token({"sub": str(normal_user.id)})
    me = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 403

    # Unblock
    resp2 = client.post(
        f"/v1/admin/users/{normal_user.id}/block",
        json={"blocked": False, "reason": "resolved"},
        headers=admin_headers,
    )
    assert resp2.status_code == 200
    assert resp2.json()["is_blocked"] is False


def test_admin_garmin_deep_backfill_success_and_audited(admin_headers, admin_user, garmin_user, monkeypatch):
    from tasks import garmin_webhook_tasks

    task_mock = Mock()
    task_mock.id = "task_deep_123"
    monkeypatch.setattr(garmin_webhook_tasks.request_deep_garmin_backfill_task, "apply_async", lambda *a, **k: task_mock)

    resp = client.post(
        f"/v1/admin/users/{garmin_user.id}/garmin/deep-backfill",
        json={"reason": "support backfill"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["queued"] is True
    assert body["task_id"] == "task_deep_123"

    db = SessionLocal()
    try:
        ev = _latest_audit(db, actor_id=admin_user.id, target_id=garmin_user.id, action="garmin.deep_backfill")
        assert ev is not None
        assert ev.reason == "support backfill"
        assert ev.payload["task_id"] == "task_deep_123"
    finally:
        db.close()


def test_admin_garmin_deep_backfill_user_not_found(admin_headers):
    resp = client.post(
        f"/v1/admin/users/{uuid4()}/garmin/deep-backfill",
        json={"reason": "missing user"},
        headers=admin_headers,
    )
    assert resp.status_code == 404


def test_admin_garmin_deep_backfill_requires_connected(admin_headers, normal_user):
    resp = client.post(
        f"/v1/admin/users/{normal_user.id}/garmin/deep-backfill",
        json={"reason": "not connected"},
        headers=admin_headers,
    )
    assert resp.status_code == 400
    assert "Garmin not connected" in resp.text


def test_admin_garmin_deep_backfill_impersonation_blocked(admin_user, garmin_user):
    impersonation_token = create_access_token(
        {
            "sub": str(admin_user.id),
            "is_impersonation": True,
            "impersonated_by": str(uuid4()),
        }
    )
    resp = client.post(
        f"/v1/admin/users/{garmin_user.id}/garmin/deep-backfill",
        json={"reason": "impersonation should fail"},
        headers={"Authorization": f"Bearer {impersonation_token}"},
    )
    assert resp.status_code == 403

