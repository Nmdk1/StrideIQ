import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

from main import app
from core.database import SessionLocal
from models import Athlete
from services.oauth_state import create_oauth_state


client = TestClient(app)


def test_strava_callback_requires_valid_state(monkeypatch):
    # Ensure we never call out to Strava when state is missing/invalid.
    called = {"exchange": False}

    def _fake_exchange(_code: str):
        called["exchange"] = True
        raise RuntimeError("should not be called")

    monkeypatch.setattr("routers.strava.exchange_code_for_token", _fake_exchange)

    resp = client.get("/v1/strava/callback?code=abc")
    assert resp.status_code == 403
    assert called["exchange"] is False


def test_strava_callback_links_existing_athlete_and_redirects(monkeypatch):
    db = SessionLocal()
    athlete = Athlete(email=f"oauth_{uuid4()}@example.com", display_name="OAuth User", role="athlete", subscription_tier="free")
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    db.close()

    def _fake_exchange(_code: str):
        return {
            "access_token": "access123",
            "refresh_token": "refresh123",
            "athlete": {"id": 12345, "firstname": "Test", "lastname": "User"},
        }

    # Token encryption is used; mock it to a deterministic pass-through.
    monkeypatch.setattr("routers.strava.exchange_code_for_token", _fake_exchange)
    monkeypatch.setattr("services.token_encryption.encrypt_token", lambda x: f"enc:{x}")

    state = create_oauth_state({"athlete_id": str(athlete.id), "return_to": "/onboarding"})
    resp = client.get(f"/v1/strava/callback?code=abc&state={state}", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers.get("location", "").endswith("/onboarding?strava=connected") or "strava=connected" in resp.headers.get("location", "")

    db = SessionLocal()
    try:
        updated = db.get(Athlete, athlete.id)
        assert updated is not None
        assert updated.strava_athlete_id == 12345
        assert updated.strava_access_token == "enc:access123"
        assert updated.strava_refresh_token == "enc:refresh123"
    finally:
        try:
            updated = db.get(Athlete, athlete.id)
            if updated:
                db.delete(updated)
            db.commit()
        except Exception:
            db.rollback()
        db.close()

