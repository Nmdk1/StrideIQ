"""
Tests for Strava token refresh logic (ADR-17, Phase 0).

Covers:
- /verify endpoint: refresh on 401 before wiping tokens (P0-1)
- /verify endpoint: wipe tokens when refresh fails (P0-2)
- /verify endpoint: returns valid after refresh without second call (P0-3)
- /verify endpoint: stores expires_at after refresh (P0-7)
- ensure_fresh_token pre-flight helper (P0-9)
- get_activity_laps refresh token persistence (P0-10)
"""
import os
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from cryptography.fernet import Fernet

from fastapi.testclient import TestClient
from main import app
from core.database import SessionLocal
from core.security import create_access_token
from models import Athlete

client = TestClient(app)


@pytest.fixture(autouse=True)
def _ensure_encryption_key():
    """Ensure a valid Fernet key is available for token encryption tests."""
    import services.token_encryption as te_mod
    key = Fernet.generate_key().decode()
    old_val = os.environ.get("TOKEN_ENCRYPTION_KEY")
    os.environ["TOKEN_ENCRYPTION_KEY"] = key
    te_mod._token_encryption = None  # Reset singleton to pick up new key
    yield
    # Restore
    te_mod._token_encryption = None
    if old_val is not None:
        os.environ["TOKEN_ENCRYPTION_KEY"] = old_val
    elif "TOKEN_ENCRYPTION_KEY" in os.environ:
        del os.environ["TOKEN_ENCRYPTION_KEY"]


def _create_test_athlete(db):
    """Create a test athlete with Strava tokens."""
    athlete = Athlete(
        email=f"strava_test_{uuid4()}@example.com",
        display_name="Strava Test",
        role="athlete",
        subscription_tier="free",
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    return athlete


def _auth_headers(athlete):
    token = create_access_token({"sub": str(athlete.id)})
    return {"Authorization": f"Bearer {token}"}


def _cleanup(db, athlete):
    try:
        db.delete(athlete)
        db.commit()
    except Exception:
        db.rollback()


class TestVerifyRefreshBeforeWipe:
    """P0-1, P0-2, P0-3: /verify attempts refresh on 401 before wiping."""

    def test_verify_refreshes_on_401(self):
        """P0-1: When Strava returns 401, /verify attempts refresh and succeeds."""
        from services.token_encryption import encrypt_token

        db = SessionLocal()
        athlete = _create_test_athlete(db)
        try:
            athlete.strava_access_token = encrypt_token("expired_access_token")
            athlete.strava_refresh_token = encrypt_token("valid_refresh_token")
            athlete.strava_athlete_id = 12345
            db.commit()

            mock_verify_response = MagicMock()
            mock_verify_response.status_code = 401

            future_ts = int((datetime.now(timezone.utc) + timedelta(hours=6)).timestamp())
            mock_refresh_response = MagicMock()
            mock_refresh_response.status_code = 200
            mock_refresh_response.json.return_value = {
                "access_token": "new_access_token",
                "refresh_token": "new_refresh_token",
                "expires_at": future_ts,
                "token_type": "Bearer",
            }
            mock_refresh_response.raise_for_status = MagicMock()

            with patch("routers.strava.requests.get", return_value=mock_verify_response):
                with patch("services.strava_service.requests.post", return_value=mock_refresh_response):
                    resp = client.get("/v1/strava/verify", headers=_auth_headers(athlete))

            assert resp.status_code == 200
            data = resp.json()
            assert data["valid"] is True
            assert data["connected"] is True

            # Tokens should NOT be wiped
            db.refresh(athlete)
            assert athlete.strava_access_token is not None
            assert athlete.strava_refresh_token is not None
            assert athlete.strava_athlete_id is not None
        finally:
            _cleanup(db, athlete)
            db.close()

    def test_verify_wipes_when_refresh_fails(self):
        """P0-2: When Strava returns 401 AND refresh fails, tokens are wiped."""
        from services.token_encryption import encrypt_token
        import requests as req_lib

        db = SessionLocal()
        athlete = _create_test_athlete(db)
        try:
            athlete.strava_access_token = encrypt_token("expired_access_token")
            athlete.strava_refresh_token = encrypt_token("revoked_refresh_token")
            athlete.strava_athlete_id = 12345
            db.commit()

            mock_verify_response = MagicMock()
            mock_verify_response.status_code = 401

            # Refresh fails with 400 (truly revoked)
            mock_refresh_response = MagicMock()
            mock_refresh_response.status_code = 400
            mock_refresh_response.raise_for_status.side_effect = req_lib.HTTPError(
                response=mock_refresh_response
            )

            with patch("routers.strava.requests.get", return_value=mock_verify_response):
                with patch("services.strava_service.requests.post", return_value=mock_refresh_response):
                    resp = client.get("/v1/strava/verify", headers=_auth_headers(athlete))

            assert resp.status_code == 200
            data = resp.json()
            assert data["valid"] is False
            assert data["connected"] is False
            assert data["reason"] == "revoked"

            # Tokens SHOULD be wiped
            db.refresh(athlete)
            assert athlete.strava_access_token is None
            assert athlete.strava_refresh_token is None
            assert athlete.strava_athlete_id is None
        finally:
            _cleanup(db, athlete)
            db.close()

    def test_verify_returns_valid_after_refresh_no_second_call(self):
        """P0-3: After successful refresh, returns valid:True with only ONE Strava API call."""
        from services.token_encryption import encrypt_token

        db = SessionLocal()
        athlete = _create_test_athlete(db)
        try:
            athlete.strava_access_token = encrypt_token("expired_token")
            athlete.strava_refresh_token = encrypt_token("good_refresh")
            athlete.strava_athlete_id = 99999
            db.commit()

            mock_verify_response = MagicMock()
            mock_verify_response.status_code = 401

            future_ts = int((datetime.now(timezone.utc) + timedelta(hours=6)).timestamp())
            mock_refresh_response = MagicMock()
            mock_refresh_response.status_code = 200
            mock_refresh_response.json.return_value = {
                "access_token": "fresh_token",
                "refresh_token": "fresh_refresh",
                "expires_at": future_ts,
            }
            mock_refresh_response.raise_for_status = MagicMock()

            with patch("routers.strava.requests.get", return_value=mock_verify_response) as mock_get:
                with patch("services.strava_service.requests.post", return_value=mock_refresh_response):
                    resp = client.get("/v1/strava/verify", headers=_auth_headers(athlete))

            data = resp.json()
            assert data["valid"] is True
            # Only ONE call to Strava API (the initial verify), not a second one after refresh
            assert mock_get.call_count == 1
        finally:
            _cleanup(db, athlete)
            db.close()


class TestVerifyStoresExpiresAt:
    """P0-7: After refresh in /verify, expires_at is stored on athlete."""

    def test_verify_refresh_stores_expires_at(self):
        from services.token_encryption import encrypt_token

        db = SessionLocal()
        athlete = _create_test_athlete(db)
        try:
            athlete.strava_access_token = encrypt_token("expired")
            athlete.strava_refresh_token = encrypt_token("valid")
            athlete.strava_athlete_id = 11111
            athlete.strava_token_expires_at = None
            db.commit()

            future_ts = int((datetime.now(timezone.utc) + timedelta(hours=6)).timestamp())

            mock_verify_response = MagicMock()
            mock_verify_response.status_code = 401

            mock_refresh_response = MagicMock()
            mock_refresh_response.status_code = 200
            mock_refresh_response.json.return_value = {
                "access_token": "new",
                "refresh_token": "new_refresh",
                "expires_at": future_ts,
            }
            mock_refresh_response.raise_for_status = MagicMock()

            with patch("routers.strava.requests.get", return_value=mock_verify_response):
                with patch("services.strava_service.requests.post", return_value=mock_refresh_response):
                    resp = client.get("/v1/strava/verify", headers=_auth_headers(athlete))

            assert resp.json()["valid"] is True
            db.refresh(athlete)
            assert athlete.strava_token_expires_at is not None
            expected = datetime.fromtimestamp(future_ts, tz=timezone.utc)
            # Ensure both sides are tz-aware for comparison (some DBs strip tz)
            actual = athlete.strava_token_expires_at
            if actual.tzinfo is None:
                actual = actual.replace(tzinfo=timezone.utc)
            diff = abs((actual - expected).total_seconds())
            assert diff < 2
        finally:
            _cleanup(db, athlete)
            db.close()


class TestEnsureFreshToken:
    """P0-9: Pre-flight token refresh helper."""

    def test_skips_when_token_still_fresh(self):
        """Token not expiring soon — no refresh needed."""
        from services.token_encryption import encrypt_token
        from services.strava_service import ensure_fresh_token

        db = SessionLocal()
        athlete = _create_test_athlete(db)
        try:
            athlete.strava_access_token = encrypt_token("good_token")
            athlete.strava_refresh_token = encrypt_token("refresh")
            athlete.strava_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=5)
            db.commit()

            with patch("services.strava_service.refresh_access_token") as mock_refresh:
                result = ensure_fresh_token(athlete, db)

            assert result is True
            mock_refresh.assert_not_called()
        finally:
            _cleanup(db, athlete)
            db.close()

    def test_refreshes_when_token_expiring_soon(self):
        """Token expires in 2 minutes — should refresh."""
        from services.token_encryption import encrypt_token
        from services.strava_service import ensure_fresh_token

        db = SessionLocal()
        athlete = _create_test_athlete(db)
        try:
            athlete.strava_access_token = encrypt_token("expiring_token")
            athlete.strava_refresh_token = encrypt_token("valid_refresh")
            athlete.strava_token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=2)
            db.commit()

            future_ts = int((datetime.now(timezone.utc) + timedelta(hours=6)).timestamp())

            with patch("services.strava_service.refresh_access_token") as mock_refresh:
                mock_refresh.return_value = {
                    "access_token": "new_access",
                    "refresh_token": "new_refresh",
                    "expires_at": future_ts,
                }
                result = ensure_fresh_token(athlete, db)

            assert result is True
            mock_refresh.assert_called_once()
            db.refresh(athlete)
            assert athlete.strava_token_expires_at is not None
        finally:
            _cleanup(db, athlete)
            db.close()

    def test_returns_true_when_no_expires_at(self):
        """No expires_at stored — can't check, assume OK."""
        from services.token_encryption import encrypt_token
        from services.strava_service import ensure_fresh_token

        db = SessionLocal()
        athlete = _create_test_athlete(db)
        try:
            athlete.strava_access_token = encrypt_token("token")
            athlete.strava_refresh_token = encrypt_token("refresh")
            athlete.strava_token_expires_at = None
            db.commit()

            result = ensure_fresh_token(athlete, db)
            assert result is True
        finally:
            _cleanup(db, athlete)
            db.close()

    def test_returns_false_when_refresh_fails(self):
        """Refresh fails — return False."""
        from services.token_encryption import encrypt_token
        from services.strava_service import ensure_fresh_token
        import requests as req_lib

        db = SessionLocal()
        athlete = _create_test_athlete(db)
        try:
            athlete.strava_access_token = encrypt_token("expiring")
            athlete.strava_refresh_token = encrypt_token("bad_refresh")
            athlete.strava_token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=1)
            db.commit()

            with patch("services.strava_service.refresh_access_token") as mock_refresh:
                mock_refresh.side_effect = req_lib.HTTPError("Refresh failed")
                result = ensure_fresh_token(athlete, db)

            assert result is False
        finally:
            _cleanup(db, athlete)
            db.close()


class TestGetActivityLapsRefreshTokenPersistence:
    """P0-10: get_activity_laps stores refresh token after 401 refresh."""

    def test_laps_stores_refresh_token_on_401(self):
        """On 401, BOTH access and refresh tokens are persisted after refresh."""
        from services.token_encryption import encrypt_token, decrypt_token
        from services.strava_service import get_activity_laps

        db = SessionLocal()
        athlete = _create_test_athlete(db)
        try:
            athlete.strava_access_token = encrypt_token("expired_access")
            athlete.strava_refresh_token = encrypt_token("old_refresh")
            db.commit()

            old_refresh_encrypted = athlete.strava_refresh_token

            # First call returns 401, second call (after refresh) returns laps
            mock_401 = MagicMock()
            mock_401.status_code = 401

            mock_200 = MagicMock()
            mock_200.status_code = 200
            mock_200.json.return_value = [{"id": 1, "name": "Lap 1"}]
            mock_200.raise_for_status = MagicMock()

            future_ts = int((datetime.now(timezone.utc) + timedelta(hours=6)).timestamp())
            mock_refresh_response = MagicMock()
            mock_refresh_response.status_code = 200
            mock_refresh_response.json.return_value = {
                "access_token": "new_access_from_laps",
                "refresh_token": "new_refresh_from_laps",
                "expires_at": future_ts,
            }
            mock_refresh_response.raise_for_status = MagicMock()

            with patch("services.strava_service.requests.get", side_effect=[mock_401, mock_200]):
                with patch("services.strava_service.requests.post", return_value=mock_refresh_response):
                    laps = get_activity_laps(athlete, 123456)

            assert laps == [{"id": 1, "name": "Lap 1"}]
            # Refresh token should have been updated (not same as old)
            assert athlete.strava_refresh_token != old_refresh_encrypted
            # Decrypt and verify the new refresh token
            new_refresh = decrypt_token(athlete.strava_refresh_token)
            assert new_refresh == "new_refresh_from_laps"
            # expires_at should be stored
            assert athlete.strava_token_expires_at is not None
        finally:
            _cleanup(db, athlete)
            db.close()
