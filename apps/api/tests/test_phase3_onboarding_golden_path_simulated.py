from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple
from urllib.parse import urlparse, parse_qs
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models import Athlete, InviteAllowlist


client = TestClient(app)


@dataclass
class _DelayCall:
    args: Tuple[Any, ...]
    kwargs: Dict[str, Any]


@dataclass
class _DummyAsyncResult:
    id: str


def _extract_state_from_auth_url(auth_url: str) -> str:
    parsed = urlparse(auth_url)
    qs = parse_qs(parsed.query or "")
    state = (qs.get("state") or [None])[0]
    assert state, f"auth_url missing state param: {auth_url}"
    return state


def test_phase3_simulated_golden_path_invite_register_oauth_callback_and_bootstrap(monkeypatch):
    """
    Simulated Phase 3 Golden Path (no real Strava, no burner accounts).

    Requirements satisfied:
    1) Transaction isolation: Invite flips active -> used in the real DB.
    2) Cryptographic verification: State is extracted from auth_url and must round-trip.
       A random/forged state must be rejected.
    3) Task signature verification: Mock only Celery .delay and assert args match the new athlete_id.
    """

    db = SessionLocal()
    admin = None
    created_athlete = None
    invite_row = None
    try:
        # Ensure the Phase 5 emergency brake does not interfere with Phase 3 golden path.
        from services.plan_framework.feature_flags import FeatureFlagService

        svc = FeatureFlagService(db)
        if svc.get_flag("system.ingestion_paused"):
            svc.set_flag("system.ingestion_paused", {"enabled": False})

        # --- Admin setup: create admin + auth header ---
        admin = Athlete(
            email=f"admin_phase3_{uuid4()}@example.com",
            display_name="Admin",
            subscription_tier="elite",
            role="admin",
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

        admin_headers = {"Authorization": f"Bearer {create_access_token({'sub': str(admin.id)})}"}

        # --- Create invite via admin API ---
        invited_email = f"invited_{uuid4()}@example.com"
        resp = client.post("/v1/admin/invites", json={"email": invited_email, "note": "phase3 test"}, headers=admin_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json().get("success") is True

        # Invite should exist and be active before registration.
        invite_row = db.query(InviteAllowlist).filter(InviteAllowlist.email == invited_email.lower()).first()
        assert invite_row is not None
        assert invite_row.is_active is True
        assert invite_row.used_at is None

        # --- Registration: must succeed ONLY with invite ---
        password = "SecureP@ss123"
        resp = client.post(
            "/v1/auth/register",
            json={"email": invited_email, "password": password, "display_name": "Invited User"},
        )
        assert resp.status_code == 201, resp.text
        created_id = resp.json().get("athlete", {}).get("id")
        assert created_id

        created_athlete = db.query(Athlete).filter(Athlete.email == invited_email.lower()).first()
        assert created_athlete is not None

        # Transaction isolation: invite flips active -> used (real DB write).
        db.refresh(invite_row)
        assert invite_row.used_at is not None
        assert invite_row.used_by_athlete_id == created_athlete.id
        assert invite_row.is_active is False

        # --- Login to get auth token for /v1/strava/auth-url ---
        resp = client.post("/v1/auth/login", json={"email": invited_email, "password": password})
        assert resp.status_code == 200, resp.text
        user_token = resp.json()["access_token"]
        user_headers = {"Authorization": f"Bearer {user_token}"}

        # --- OAuth start: auth-url must contain signed state ---
        resp = client.get("/v1/strava/auth-url?return_to=/onboarding", headers=user_headers)
        assert resp.status_code == 200, resp.text
        auth_url = resp.json()["auth_url"]
        state = _extract_state_from_auth_url(auth_url)

        # --- OAuth callback must reject forged/random state (and must not call Strava exchange) ---
        called = {"exchange": False}

        def _exchange_should_not_run(_code: str):
            called["exchange"] = True
            raise RuntimeError("exchange_code_for_token should not run for invalid state")

        monkeypatch.setattr("routers.strava.exchange_code_for_token", _exchange_should_not_run)
        bad_state = f"bad.{uuid4()}"
        resp = client.get(f"/v1/strava/callback?code=fake&state={bad_state}", follow_redirects=False)
        assert resp.status_code == 403
        assert called["exchange"] is False

        # --- OAuth callback: mock Strava edge + token encryption + celery delay ---
        def _fake_exchange(_code: str):
            return {
                "access_token": "access123",
                "refresh_token": "refresh123",
                "athlete": {"id": 12345, "firstname": "Test", "lastname": "User"},
            }

        monkeypatch.setattr("routers.strava.exchange_code_for_token", _fake_exchange)
        monkeypatch.setattr("services.token_encryption.encrypt_token", lambda x: f"enc:{x}")

        delay_calls: list[_DelayCall] = []

        def _capture_delay(*args, **kwargs):
            delay_calls.append(_DelayCall(args=args, kwargs=kwargs))
            return _DummyAsyncResult(id=f"task_{uuid4()}")

        monkeypatch.setattr("tasks.strava_tasks.backfill_strava_activity_index_task.delay", _capture_delay)

        resp = client.get(f"/v1/strava/callback?code=fake&state={state}", follow_redirects=False)
        assert resp.status_code == 302
        loc = resp.headers.get("location", "")
        assert "strava=connected" in loc
        assert "/onboarding" in loc

        # DB: athlete linked to Strava + token stored
        db.refresh(created_athlete)
        assert created_athlete.strava_athlete_id == 12345
        assert created_athlete.strava_access_token == "enc:access123"
        assert created_athlete.strava_refresh_token == "enc:refresh123"

        # Task signature verification: correct athlete_id argument and pages=5
        assert len(delay_calls) >= 1
        last = delay_calls[-1]
        assert last.args and last.args[0] == str(created_athlete.id)
        assert last.kwargs.get("pages") == 5

        # --- Bootstrap endpoint: must queue index + sync for THIS user (mock only .delay) ---
        bootstrap_index_calls: list[_DelayCall] = []
        bootstrap_sync_calls: list[_DelayCall] = []

        def _capture_index(*args, **kwargs):
            bootstrap_index_calls.append(_DelayCall(args=args, kwargs=kwargs))
            return _DummyAsyncResult(id="index_task_1")

        def _capture_sync(*args, **kwargs):
            bootstrap_sync_calls.append(_DelayCall(args=args, kwargs=kwargs))
            return _DummyAsyncResult(id="sync_task_1")

        monkeypatch.setattr("tasks.strava_tasks.backfill_strava_activity_index_task.delay", _capture_index)
        monkeypatch.setattr("tasks.strava_tasks.sync_strava_activities_task.delay", _capture_sync)

        resp = client.post("/v1/onboarding/bootstrap", headers=user_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("queued") in (True, False)

        # Must call both tasks with correct athlete_id.
        assert bootstrap_index_calls, "expected index backfill task to be queued"
        assert bootstrap_sync_calls, "expected sync task to be queued"
        assert bootstrap_index_calls[0].args[0] == str(created_athlete.id)
        assert bootstrap_index_calls[0].kwargs.get("pages") == 5
        assert bootstrap_sync_calls[0].args[0] == str(created_athlete.id)

    finally:
        # Best-effort cleanup (test suite also uses transaction rollback in many places,
        # but we avoid leaving rows behind).
        try:
            if created_athlete is not None:
                created_athlete = db.query(Athlete).filter(Athlete.id == created_athlete.id).first()
                if created_athlete:
                    db.delete(created_athlete)
            if invite_row is not None:
                invite_row = db.query(InviteAllowlist).filter(InviteAllowlist.id == invite_row.id).first()
                if invite_row:
                    db.delete(invite_row)
            if admin is not None:
                admin = db.query(Athlete).filter(Athlete.id == admin.id).first()
                if admin:
                    db.delete(admin)
            db.commit()
        except Exception:
            db.rollback()
        db.close()


def test_strava_callback_skips_enqueue_when_ingestion_paused(monkeypatch):
    """
    Phase 5 brake: when system.ingestion_paused is enabled, the OAuth callback must
    still link tokens but must NOT enqueue ingestion.
    """
    from services.plan_framework.feature_flags import FeatureFlagService

    db = SessionLocal()
    admin = None
    created_athlete = None
    invite_row = None
    try:
        admin = Athlete(
            email=f"admin_pause_{uuid4()}@example.com",
            display_name="Admin",
            subscription_tier="elite",
            role="admin",
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

        admin_headers = {"Authorization": f"Bearer {create_access_token({'sub': str(admin.id)})}"}

        invited_email = f"paused_{uuid4()}@example.com"
        resp = client.post("/v1/admin/invites", json={"email": invited_email, "note": "pause test"}, headers=admin_headers)
        assert resp.status_code == 200, resp.text

        password = "SecureP@ss123"
        resp = client.post("/v1/auth/register", json={"email": invited_email, "password": password, "display_name": "User"})
        assert resp.status_code == 201, resp.text

        created_athlete = db.query(Athlete).filter(Athlete.email == invited_email.lower()).first()
        assert created_athlete is not None

        # Enable the pause flag
        svc = FeatureFlagService(db)
        if not svc.get_flag("system.ingestion_paused"):
            svc.create_flag(key="system.ingestion_paused", name="Pause global ingestion", enabled=True, description="test")
        else:
            svc.set_flag("system.ingestion_paused", {"enabled": True})
        db.commit()

        # Login to get state
        resp = client.post("/v1/auth/login", json={"email": invited_email, "password": password})
        user_headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
        resp = client.get("/v1/strava/auth-url?return_to=/onboarding", headers=user_headers)
        state = _extract_state_from_auth_url(resp.json()["auth_url"])

        # Mock Strava edge + token encryption
        monkeypatch.setattr(
            "routers.strava.exchange_code_for_token",
            lambda _code: {"access_token": "access123", "refresh_token": "refresh123", "athlete": {"id": 999, "firstname": "T", "lastname": "U"}},
        )
        monkeypatch.setattr("services.token_encryption.encrypt_token", lambda x: f"enc:{x}")

        # Capture delay calls; should stay empty.
        delay_calls: list[_DelayCall] = []
        monkeypatch.setattr("tasks.strava_tasks.backfill_strava_activity_index_task.delay", lambda *a, **k: delay_calls.append(_DelayCall(args=a, kwargs=k)))

        resp = client.get(f"/v1/strava/callback?code=fake&state={state}", follow_redirects=False)
        assert resp.status_code == 302
        db.refresh(created_athlete)
        assert created_athlete.strava_athlete_id == 999
        assert created_athlete.strava_access_token == "enc:access123"
        assert delay_calls == []
    finally:
        try:
            # Reset emergency brake so other tests aren't affected.
            from services.plan_framework.feature_flags import FeatureFlagService

            svc = FeatureFlagService(db)
            if svc.get_flag("system.ingestion_paused"):
                svc.set_flag("system.ingestion_paused", {"enabled": False})

            if created_athlete is not None:
                created_athlete = db.query(Athlete).filter(Athlete.id == created_athlete.id).first()
                if created_athlete:
                    db.delete(created_athlete)
            if invite_row is not None:
                invite_row = db.query(InviteAllowlist).filter(InviteAllowlist.id == invite_row.id).first()
                if invite_row:
                    db.delete(invite_row)
            if admin is not None:
                admin = db.query(Athlete).filter(Athlete.id == admin.id).first()
                if admin:
                    db.delete(admin)
            db.commit()
        except Exception:
            db.rollback()
        db.close()

