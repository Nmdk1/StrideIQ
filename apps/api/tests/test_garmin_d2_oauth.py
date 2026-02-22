"""
D2: OAuth 2.0 PKCE Flow — Tests

Covers:
  D2.1 — /auth-url, /callback, /status
  D2.2 — ensure_fresh_garmin_token (refresh logic)
  D2.3 — /disconnect (data purge)
  GDPR — /delete-account includes GarminDay + ActivityStream

AC reference: PHASE2_GARMIN_INTEGRATION_AC.md §D2
"""

import hashlib
import base64
import inspect
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# PKCE helpers — unit tests (no DB, no network)
# ---------------------------------------------------------------------------

class TestPKCEHelpers:
    def test_generate_pkce_pair_returns_tuple(self):
        from services.garmin_oauth import generate_pkce_pair
        verifier, challenge = generate_pkce_pair()
        assert isinstance(verifier, str)
        assert isinstance(challenge, str)

    def test_code_verifier_length_in_range(self):
        from services.garmin_oauth import generate_pkce_pair
        verifier, _ = generate_pkce_pair()
        assert 43 <= len(verifier) <= 128

    def test_code_verifier_uses_safe_alphabet(self):
        import re
        from services.garmin_oauth import generate_pkce_pair
        verifier, _ = generate_pkce_pair()
        # RFC 7636 §4.1: unreserved chars [A-Z a-z 0-9 - . _ ~]
        assert re.match(r'^[A-Za-z0-9\-._~]+$', verifier), (
            f"code_verifier contains invalid characters: {verifier}"
        )

    def test_code_challenge_is_sha256_of_verifier(self):
        from services.garmin_oauth import generate_pkce_pair
        verifier, challenge = generate_pkce_pair()
        expected_digest = hashlib.sha256(verifier.encode("ascii")).digest()
        expected_challenge = base64.urlsafe_b64encode(expected_digest).rstrip(b"=").decode("ascii")
        assert challenge == expected_challenge

    def test_pkce_pairs_are_unique(self):
        from services.garmin_oauth import generate_pkce_pair
        pairs = {generate_pkce_pair()[0] for _ in range(5)}
        assert len(pairs) == 5, "code_verifier must be unique each call"


class TestBuildAuthUrl:
    def _mock_settings(self, **kwargs):
        mock = MagicMock()
        mock.GARMIN_CLIENT_ID = kwargs.get("client_id", "test_client_id")
        mock.GARMIN_CLIENT_SECRET = kwargs.get("client_secret", "test_secret")
        mock.GARMIN_REDIRECT_URI = kwargs.get("redirect_uri", "https://api.strideiq.run/v1/garmin/callback")
        return mock

    def test_auth_url_contains_auth_endpoint(self):
        from services.garmin_oauth import build_auth_url
        with patch("services.garmin_oauth.settings", self._mock_settings()):
            url = build_auth_url("challenge_abc", "state_xyz")
        assert "connect.garmin.com/oauth2Confirm" in url

    def test_auth_url_contains_pkce_params(self):
        from services.garmin_oauth import build_auth_url
        with patch("services.garmin_oauth.settings", self._mock_settings()):
            url = build_auth_url("my_challenge", "my_state")
        assert "code_challenge=my_challenge" in url
        assert "code_challenge_method=S256" in url
        assert "response_type=code" in url
        assert "state=my_state" in url

    def test_auth_url_contains_client_id(self):
        from services.garmin_oauth import build_auth_url
        with patch("services.garmin_oauth.settings", self._mock_settings(client_id="garmin_app_123")):
            url = build_auth_url("challenge", "state")
        assert "client_id=garmin_app_123" in url

    def test_auth_url_contains_redirect_uri(self):
        from services.garmin_oauth import build_auth_url
        redirect = "https://api.strideiq.run/v1/garmin/callback"
        with patch("services.garmin_oauth.settings", self._mock_settings(redirect_uri=redirect)):
            url = build_auth_url("challenge", "state")
        assert redirect in url

    def test_raises_if_client_id_not_configured(self):
        from services.garmin_oauth import build_auth_url
        with patch("services.garmin_oauth.settings", self._mock_settings(client_id=None)):
            with pytest.raises(ValueError, match="GARMIN_CLIENT_ID"):
                build_auth_url("challenge", "state")


# ---------------------------------------------------------------------------
# Token exchange / refresh — unit tests (mocked HTTP)
# ---------------------------------------------------------------------------

class TestTokenExchange:
    def _mock_settings(self):
        s = MagicMock()
        s.GARMIN_CLIENT_ID = "cid"
        s.GARMIN_CLIENT_SECRET = "csecret"
        s.GARMIN_REDIRECT_URI = "https://api.strideiq.run/v1/garmin/callback"
        return s

    def _fake_token_response(self):
        return {
            "access_token": "garmin_at_abc",
            "refresh_token": "garmin_rt_xyz",
            "expires_in": 86400,
        }

    def test_exchange_code_posts_correct_payload(self):
        from services.garmin_oauth import exchange_code_for_token
        mock_resp = MagicMock()
        mock_resp.json.return_value = self._fake_token_response()
        mock_resp.raise_for_status = MagicMock()

        with patch("services.garmin_oauth.settings", self._mock_settings()), \
             patch("services.garmin_oauth.requests.post", return_value=mock_resp) as mock_post:
            result = exchange_code_for_token("auth_code_123", "verifier_456")

        call_kwargs = mock_post.call_args
        payload = call_kwargs[1]["data"]
        assert payload["grant_type"] == "authorization_code"
        assert payload["code"] == "auth_code_123"
        assert payload["code_verifier"] == "verifier_456"
        assert result["access_token"] == "garmin_at_abc"

    def test_refresh_token_sends_grant_type_refresh_token(self):
        from services.garmin_oauth import refresh_token
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "access_token": "new_at",
            "refresh_token": "new_rt",
            "expires_in": 86400,
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("services.garmin_oauth.settings", self._mock_settings()), \
             patch("services.garmin_oauth.requests.post", return_value=mock_resp) as mock_post:
            result = refresh_token("old_refresh_token")

        payload = mock_post.call_args[1]["data"]
        assert payload["grant_type"] == "refresh_token"
        assert payload["refresh_token"] == "old_refresh_token"
        assert result["access_token"] == "new_at"
        assert result["refresh_token"] == "new_rt"


# ---------------------------------------------------------------------------
# D2.2: ensure_fresh_garmin_token — unit tests
# ---------------------------------------------------------------------------

class TestEnsureFreshGarminToken:
    def _make_athlete(self, connected=True, access_token="encrypted_at",
                      refresh_token="encrypted_rt", expires_in_s=7200):
        """Build a mock Athlete with Garmin OAuth fields."""
        athlete = MagicMock()
        athlete.id = str(uuid4())
        athlete.garmin_connected = connected
        athlete.garmin_oauth_access_token = access_token if connected else None
        athlete.garmin_oauth_refresh_token = refresh_token if connected else None
        if expires_in_s is not None:
            athlete.garmin_oauth_token_expires_at = (
                datetime.now(timezone.utc) + timedelta(seconds=expires_in_s)
            )
        else:
            athlete.garmin_oauth_token_expires_at = None
        return athlete

    def test_returns_none_when_not_connected(self):
        from services.garmin_oauth import ensure_fresh_garmin_token
        athlete = self._make_athlete(connected=False)
        db = MagicMock()
        result = ensure_fresh_garmin_token(athlete, db)
        assert result is None

    def test_returns_decrypted_token_when_fresh(self):
        from services.garmin_oauth import ensure_fresh_garmin_token
        athlete = self._make_athlete(expires_in_s=3600)

        db = MagicMock()
        with patch("services.garmin_oauth.decrypt_token", return_value="plaintext_at"):
            result = ensure_fresh_garmin_token(athlete, db)

        assert result == "plaintext_at"

    def test_triggers_refresh_when_near_expiry(self):
        """Token expires in 300 seconds — within the 600-second buffer."""
        from services.garmin_oauth import ensure_fresh_garmin_token
        athlete = self._make_athlete(expires_in_s=300)

        fake_token_data = {
            "access_token": "new_at_plaintext",
            "refresh_token": "new_rt",
            "expires_in": 86400,
        }

        with patch("services.garmin_oauth.decrypt_token", return_value="plaintext_rt"), \
             patch("services.garmin_oauth.refresh_token", return_value=fake_token_data), \
             patch("services.garmin_oauth._store_token_data") as mock_store:
            db = MagicMock()
            result = ensure_fresh_garmin_token(athlete, db)

        mock_store.assert_called_once()
        assert result == "new_at_plaintext"

    def test_marks_disconnected_on_refresh_failure(self):
        from services.garmin_oauth import ensure_fresh_garmin_token
        athlete = self._make_athlete(expires_in_s=300)

        with patch("services.garmin_oauth.decrypt_token", return_value="plaintext_rt"), \
             patch("services.garmin_oauth.refresh_token", side_effect=Exception("401 Unauthorized")), \
             patch("services.garmin_oauth._mark_disconnected") as mock_mark:
            db = MagicMock()
            result = ensure_fresh_garmin_token(athlete, db)

        mock_mark.assert_called_once()
        assert result is None

    def test_no_api_call_made_with_expired_token(self):
        """
        Contract test: ensure_fresh_garmin_token must attempt refresh
        rather than return an expired token.
        """
        from services.garmin_oauth import ensure_fresh_garmin_token
        athlete = self._make_athlete(expires_in_s=-1)  # already expired

        with patch("services.garmin_oauth.decrypt_token", return_value="old_rt"), \
             patch("services.garmin_oauth.refresh_token", return_value={
                 "access_token": "fresh_at", "refresh_token": "new_rt", "expires_in": 86400
             }) as mock_refresh, \
             patch("services.garmin_oauth._store_token_data"):
            db = MagicMock()
            result = ensure_fresh_garmin_token(athlete, db)

        mock_refresh.assert_called_once()
        assert result == "fresh_at"


# ---------------------------------------------------------------------------
# D2: Router endpoint tests — /auth-url, /status, /disconnect
# (All external HTTP calls mocked; DB tests skip without Docker)
# ---------------------------------------------------------------------------

class TestGarminRouterSourceContract:
    """Router must use the PKCE service, not the retired garmin_service."""

    def _source(self):
        import routers.garmin as mod
        return inspect.getsource(mod)

    def test_no_garmin_service_import(self):
        src = self._source()
        assert "from services.garmin_service" not in src
        assert "import GarminService" not in src

    def test_no_garmin_username_or_password(self):
        src = self._source()
        assert "garmin_username" not in src
        assert "garmin_password" not in src

    def test_uses_pkce(self):
        src = self._source()
        assert "generate_pkce_pair" in src
        assert "code_verifier" in src
        assert "code_challenge" in src

    def test_state_is_verified_in_callback(self):
        src = self._source()
        assert "verify_oauth_state" in src

    def test_tokens_are_encrypted(self):
        src = self._source()
        # Router must call _store_token_data (which calls encrypt_token internally)
        assert "_store_token_data" in src or "encrypt_token" in src

    def test_consent_audit_log_written_on_connect(self):
        src = self._source()
        assert "garmin_connected" in src
        assert "ConsentAuditLog" in src

    def test_consent_audit_log_written_on_disconnect(self):
        src = self._source()
        assert "garmin_disconnected" in src

    def test_deregister_called_on_disconnect(self):
        src = self._source()
        assert "deregister_user" in src

    def test_garmin_day_deleted_on_disconnect(self):
        src = self._source()
        assert "GarminDay" in src

    def test_garmin_activities_deleted_on_disconnect(self):
        src = self._source()
        assert 'provider == "garmin"' in src or "provider='garmin'" in src


class TestGarminStatusEndpoint:
    """GET /v1/garmin/status — no DB required."""

    def _call_status(self, garmin_connected: bool, last_sync=None):
        """Call the status handler directly with a mock athlete."""
        from routers.garmin import get_garmin_status
        athlete = MagicMock()
        athlete.garmin_connected = garmin_connected
        athlete.last_garmin_sync = last_sync
        return get_garmin_status(current_user=athlete)

    def test_unconnected_returns_false(self):
        result = self._call_status(garmin_connected=False)
        assert result["connected"] is False

    def test_connected_returns_true(self):
        result = self._call_status(garmin_connected=True)
        assert result["connected"] is True

    def test_last_sync_none_when_never_synced(self):
        result = self._call_status(garmin_connected=True, last_sync=None)
        assert result["last_sync"] is None

    def test_last_sync_is_iso_string_when_set(self):
        ts = datetime(2026, 2, 21, 8, 0, 0, tzinfo=timezone.utc)
        result = self._call_status(garmin_connected=True, last_sync=ts)
        assert isinstance(result["last_sync"], str)
        assert "2026-02-21" in result["last_sync"]


class TestGarminAuthUrlEndpoint:
    """GET /v1/garmin/auth-url — no DB required."""

    def test_returns_auth_url_key(self):
        from routers.garmin import get_auth_url
        athlete = MagicMock()
        athlete.id = str(uuid4())

        with patch("routers.garmin.settings") as mock_settings, \
             patch("routers.garmin.generate_pkce_pair", return_value=("verifier", "challenge")), \
             patch("routers.garmin.create_oauth_state", return_value="signed_state"), \
             patch("routers.garmin.build_auth_url", return_value="https://connect.garmin.com/oauth2Confirm?..."):
            mock_settings.GARMIN_CLIENT_ID = "cid"
            result = get_auth_url(return_to="/settings", current_user=athlete)

        assert "auth_url" in result
        assert result["auth_url"] == "https://connect.garmin.com/oauth2Confirm?..."

    def test_returns_503_when_not_configured(self):
        from fastapi import HTTPException
        from routers.garmin import get_auth_url
        athlete = MagicMock()
        with patch("routers.garmin.settings") as mock_settings:
            mock_settings.GARMIN_CLIENT_ID = None
            with pytest.raises(HTTPException) as exc_info:
                get_auth_url(return_to="/settings", current_user=athlete)
        assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# GDPR router — source contract test
# ---------------------------------------------------------------------------

class TestGDPRSourceContract:
    """GDPR delete-account must include GarminDay and ActivityStream deletions."""

    def _source(self):
        import routers.gdpr as mod
        return inspect.getsource(mod)

    def test_garmin_day_deleted_in_gdpr(self):
        assert "GarminDay" in self._source()

    def test_activity_stream_deleted_in_gdpr(self):
        assert "ActivityStream" in self._source()

    def test_garmin_day_deleted_before_activity(self):
        """GarminDay must be deleted before Activity (no FK, but ordering is auditable)."""
        src = self._source()
        garmin_day_pos = src.index("GarminDay")
        activity_pos = src.index("db.query(Activity).filter(Activity.athlete_id")
        assert garmin_day_pos < activity_pos, (
            "GarminDay deletion must appear before Activity deletion in gdpr.py"
        )

    def test_activity_stream_deleted_before_activity(self):
        """ActivityStream must be deleted before Activity rows (FK constraint)."""
        src = self._source()
        stream_pos = src.index("ActivityStream")
        activity_pos = src.index("db.query(Activity).filter(Activity.athlete_id")
        assert stream_pos < activity_pos, (
            "ActivityStream deletion must appear before Activity deletion in gdpr.py"
        )
