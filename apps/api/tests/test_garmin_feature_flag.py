"""
Garmin Connect — Feature Flag Gate Tests

Covers:
  - GET /v1/garmin/auth-url: allowlisted athlete → 200, non-allowlisted → 403
  - GET /v1/garmin/callback: blocked athlete does not store tokens / enqueue backfill
  - GET /v1/garmin/callback: allowlisted athlete proceeds normally
  - GET /v1/garmin/status: garmin_connect_available reflects flag state

Flag semantics (non-negotiable per handoff):
  enabled=True, rollout_percentage=0, allowed_athlete_ids=[founder, father]
  → only athletes on the allowlist pass is_feature_enabled()

AC reference: docs/SESSION_HANDOFF_2026-02-22_GARMIN_FEATURE_FLAG_BUILDER_NOTE.md
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from main import app

FOUNDER_ID = str(uuid4())
FATHER_ID = str(uuid4())
STRANGER_ID = str(uuid4())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_athlete(athlete_id: str, **kwargs) -> MagicMock:
    """Return a minimal Athlete mock."""
    a = MagicMock()
    a.id = athlete_id
    a.garmin_connected = kwargs.get("garmin_connected", False)
    a.garmin_oauth_access_token = kwargs.get("garmin_oauth_access_token", None)
    a.garmin_user_id = kwargs.get("garmin_user_id", None)
    a.last_garmin_sync = None
    return a


def _client_with_athlete(athlete: MagicMock) -> TestClient:
    """Return a TestClient where get_current_user returns the given athlete."""
    from core.auth import get_current_user
    from core.database import get_db

    mock_db = MagicMock()

    def override_user():
        return athlete

    def override_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app, raise_server_exceptions=False)
    return client, mock_db


# ---------------------------------------------------------------------------
# Source contract
# ---------------------------------------------------------------------------

class TestSourceContract:
    def test_feature_flag_import_exists(self):
        import routers.garmin as mod
        assert hasattr(mod, "is_feature_enabled"), (
            "routers.garmin must import is_feature_enabled"
        )


# ---------------------------------------------------------------------------
# GET /v1/garmin/auth-url — feature flag gate
# ---------------------------------------------------------------------------

class TestAuthUrlFeatureFlag:
    """Allowlisted → 200 (or 503 if GARMIN_CLIENT_ID missing); blocked → 403."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_allowlisted_athlete_passes_flag(self):
        """Founder-class athlete gets past the flag gate."""
        founder = _make_athlete(FOUNDER_ID)
        client, _ = _client_with_athlete(founder)

        with patch("routers.garmin.is_feature_enabled", return_value=True), \
             patch("routers.garmin.settings") as mock_settings, \
             patch("routers.garmin.generate_pkce_pair", return_value=("verifier", "challenge")), \
             patch("routers.garmin.create_oauth_state", return_value="state_token"), \
             patch("routers.garmin.build_auth_url", return_value="https://connect.garmin.com/auth"):
            mock_settings.GARMIN_CLIENT_ID = "test_client"
            resp = client.get("/v1/garmin/auth-url")

        assert resp.status_code == 200
        assert "auth_url" in resp.json()

    def test_non_allowlisted_athlete_gets_403(self):
        """Stranger who is not on the allowlist gets 403."""
        stranger = _make_athlete(STRANGER_ID)
        client, _ = _client_with_athlete(stranger)

        with patch("routers.garmin.is_feature_enabled", return_value=False):
            resp = client.get("/v1/garmin/auth-url")

        assert resp.status_code == 403
        body = resp.json()
        assert body["detail"]["error"] == "garmin_not_available"

    def test_403_payload_is_stable(self):
        """403 body must be stable — client code parses this."""
        stranger = _make_athlete(STRANGER_ID)
        client, _ = _client_with_athlete(stranger)

        with patch("routers.garmin.is_feature_enabled", return_value=False):
            resp = client.get("/v1/garmin/auth-url")

        detail = resp.json()["detail"]
        assert "error" in detail
        assert "message" in detail

    def test_father_athlete_passes_flag(self):
        """Second allowlisted athlete (father) also passes."""
        father = _make_athlete(FATHER_ID)
        client, _ = _client_with_athlete(father)

        with patch("routers.garmin.is_feature_enabled", return_value=True), \
             patch("routers.garmin.settings") as mock_settings, \
             patch("routers.garmin.generate_pkce_pair", return_value=("v2", "c2")), \
             patch("routers.garmin.create_oauth_state", return_value="state2"), \
             patch("routers.garmin.build_auth_url", return_value="https://connect.garmin.com/auth2"):
            mock_settings.GARMIN_CLIENT_ID = "test_client"
            resp = client.get("/v1/garmin/auth-url")

        assert resp.status_code == 200

    def test_flag_check_uses_caller_athlete_id(self):
        """is_feature_enabled must be called with the authenticated athlete's ID."""
        founder = _make_athlete(FOUNDER_ID)
        client, mock_db = _client_with_athlete(founder)

        captured_calls = []

        def fake_flag(flag_key, athlete_id, db):
            captured_calls.append((flag_key, athlete_id))
            return True

        with patch("routers.garmin.is_feature_enabled", side_effect=fake_flag), \
             patch("routers.garmin.settings") as mock_settings, \
             patch("routers.garmin.generate_pkce_pair", return_value=("v", "c")), \
             patch("routers.garmin.create_oauth_state", return_value="s"), \
             patch("routers.garmin.build_auth_url", return_value="https://x"):
            mock_settings.GARMIN_CLIENT_ID = "cid"
            client.get("/v1/garmin/auth-url")

        assert len(captured_calls) == 1
        assert captured_calls[0][0] == "garmin_connect_enabled"
        assert captured_calls[0][1] == FOUNDER_ID


# ---------------------------------------------------------------------------
# GET /v1/garmin/callback — feature flag defense in depth
# ---------------------------------------------------------------------------

class TestCallbackFeatureFlag:
    """Blocked callbacks must not persist tokens or enqueue backfill."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def _build_callback_url(self, code: str = "auth_code_abc", state: str = "state_xyz") -> str:
        return f"/v1/garmin/callback?code={code}&state={state}"

    def test_blocked_callback_does_not_store_tokens(self):
        """When flag is disabled, _store_token_data must NOT be called."""
        stranger = _make_athlete(STRANGER_ID)
        client, mock_db = _client_with_athlete(stranger)

        mock_db.query.return_value.filter.return_value.first.return_value = stranger

        with patch("routers.garmin.verify_oauth_state", return_value={
                "athlete_id": STRANGER_ID,
                "code_verifier": "cv",
                "return_to": "/settings",
             }), \
             patch("routers.garmin.is_feature_enabled", return_value=False), \
             patch("routers.garmin._store_token_data") as mock_store, \
             patch("routers.garmin.exchange_code_for_token") as mock_exchange:

            resp = client.get(self._build_callback_url(), follow_redirects=False)

        mock_store.assert_not_called()
        mock_exchange.assert_not_called()

    def test_blocked_callback_does_not_enqueue_backfill(self):
        """When flag is disabled, the backfill task must NOT be enqueued."""
        stranger = _make_athlete(STRANGER_ID)
        client, mock_db = _client_with_athlete(stranger)

        mock_db.query.return_value.filter.return_value.first.return_value = stranger

        with patch("routers.garmin.verify_oauth_state", return_value={
                "athlete_id": STRANGER_ID,
                "code_verifier": "cv",
                "return_to": "/settings",
             }), \
             patch("routers.garmin.is_feature_enabled", return_value=False), \
             patch("routers.garmin._store_token_data"), \
             patch("routers.garmin.exchange_code_for_token"), \
             patch("routers.garmin.request_garmin_backfill_task") as mock_task:

            client.get(self._build_callback_url(), follow_redirects=False)

        mock_task.delay.assert_not_called()

    def test_blocked_callback_redirects_with_error(self):
        """Blocked callback returns a redirect (not 500) with an error indicator."""
        stranger = _make_athlete(STRANGER_ID)
        client, mock_db = _client_with_athlete(stranger)

        mock_db.query.return_value.filter.return_value.first.return_value = stranger

        with patch("routers.garmin.verify_oauth_state", return_value={
                "athlete_id": STRANGER_ID,
                "code_verifier": "cv",
                "return_to": "/settings",
             }), \
             patch("routers.garmin.is_feature_enabled", return_value=False), \
             patch("routers.garmin._store_token_data"), \
             patch("routers.garmin.exchange_code_for_token"):

            resp = client.get(self._build_callback_url(), follow_redirects=False)

        assert resp.status_code == 302
        location = resp.headers.get("location", "")
        assert "garmin=error" in location or "not_available" in location

    def test_allowlisted_callback_proceeds_to_token_exchange(self):
        """When flag is enabled, token exchange IS called."""
        founder = _make_athlete(FOUNDER_ID)
        client, mock_db = _client_with_athlete(founder)

        mock_db.query.return_value.filter.return_value.first.return_value = founder

        mock_token_data = {"access_token": "at", "refresh_token": "rt", "expires_in": 86400}

        with patch("routers.garmin.verify_oauth_state", return_value={
                "athlete_id": FOUNDER_ID,
                "code_verifier": "cv",
                "return_to": "/settings",
             }), \
             patch("routers.garmin.is_feature_enabled", return_value=True), \
             patch("routers.garmin.exchange_code_for_token", return_value=mock_token_data) as mock_exchange, \
             patch("routers.garmin._store_token_data"), \
             patch("routers.garmin.get_garmin_user_id", return_value="garmin_uid_123"), \
             patch("routers.garmin.get_user_permissions", return_value=["ACTIVITY_EXPORT", "HEALTH_EXPORT"]), \
             patch("routers.garmin.request_garmin_backfill_task") as mock_task, \
             patch("routers.garmin.settings") as mock_settings:

            mock_settings.WEB_APP_BASE_URL = "http://localhost:3000"
            client.get(self._build_callback_url(), follow_redirects=False)

        mock_exchange.assert_called_once()

    def test_allowlisted_callback_enqueues_backfill(self):
        """When flag is enabled, backfill task IS enqueued."""
        founder = _make_athlete(FOUNDER_ID)
        client, mock_db = _client_with_athlete(founder)

        mock_db.query.return_value.filter.return_value.first.return_value = founder

        mock_token_data = {"access_token": "at", "refresh_token": "rt", "expires_in": 86400}

        with patch("routers.garmin.verify_oauth_state", return_value={
                "athlete_id": FOUNDER_ID,
                "code_verifier": "cv",
                "return_to": "/settings",
             }), \
             patch("routers.garmin.is_feature_enabled", return_value=True), \
             patch("routers.garmin.exchange_code_for_token", return_value=mock_token_data), \
             patch("routers.garmin._store_token_data"), \
             patch("routers.garmin.get_garmin_user_id", return_value="garmin_uid_123"), \
             patch("routers.garmin.get_user_permissions", return_value=["ACTIVITY_EXPORT", "HEALTH_EXPORT"]), \
             patch("routers.garmin.request_garmin_backfill_task") as mock_task, \
             patch("routers.garmin.settings") as mock_settings:

            mock_settings.WEB_APP_BASE_URL = "http://localhost:3000"
            client.get(self._build_callback_url(), follow_redirects=False)

        mock_task.delay.assert_called_once_with(FOUNDER_ID)


# ---------------------------------------------------------------------------
# GET /v1/garmin/status — garmin_connect_available field
# ---------------------------------------------------------------------------

class TestStatusFlagField:
    """Status response must include garmin_connect_available from the flag."""

    def teardown_method(self):
        app.dependency_overrides.clear()

    def test_status_includes_garmin_connect_available_true(self):
        founder = _make_athlete(FOUNDER_ID, garmin_connected=True)
        client, _ = _client_with_athlete(founder)

        with patch("routers.garmin.is_feature_enabled", return_value=True):
            resp = client.get("/v1/garmin/status")

        assert resp.status_code == 200
        assert resp.json()["garmin_connect_available"] is True

    def test_status_includes_garmin_connect_available_false(self):
        stranger = _make_athlete(STRANGER_ID)
        client, _ = _client_with_athlete(stranger)

        with patch("routers.garmin.is_feature_enabled", return_value=False):
            resp = client.get("/v1/garmin/status")

        assert resp.status_code == 200
        assert resp.json()["garmin_connect_available"] is False

    def test_status_returns_connected_true_for_connected_blocked_athlete(self):
        """Already-connected athlete shows connected=True even when flag is off."""
        athlete = _make_athlete(STRANGER_ID, garmin_connected=True)
        client, _ = _client_with_athlete(athlete)

        with patch("routers.garmin.is_feature_enabled", return_value=False):
            resp = client.get("/v1/garmin/status")

        body = resp.json()
        assert body["connected"] is True
        assert body["garmin_connect_available"] is False


# ---------------------------------------------------------------------------
# Flag semantics verification (unit, no HTTP)
# ---------------------------------------------------------------------------

class TestFlagSemantics:
    """
    Verify that enabled=True + rollout_percentage=0 + allowed_athlete_ids=[A, B]
    produces the correct outcome: A and B pass, everyone else is blocked.
    """

    def _make_flag_dict(self, allowed_ids: list) -> dict:
        return {
            "key": "garmin_connect_enabled",
            "name": "Garmin Connect",
            "description": None,
            "enabled": True,
            "requires_subscription": False,
            "requires_tier": None,
            "requires_payment": None,
            "rollout_percentage": 0,
            "allowed_athlete_ids": allowed_ids,
        }

    def test_allowlisted_id_returns_true(self):
        from services.plan_framework.feature_flags import FeatureFlagService
        svc = FeatureFlagService(db=MagicMock())
        flag = self._make_flag_dict([FOUNDER_ID, FATHER_ID])
        svc._local_cache["garmin_connect_enabled"] = flag
        assert svc.is_enabled("garmin_connect_enabled", FOUNDER_ID) is True
        assert svc.is_enabled("garmin_connect_enabled", FATHER_ID) is True

    def test_non_allowlisted_id_returns_false(self):
        from services.plan_framework.feature_flags import FeatureFlagService
        svc = FeatureFlagService(db=MagicMock())
        flag = self._make_flag_dict([FOUNDER_ID, FATHER_ID])
        svc._local_cache["garmin_connect_enabled"] = flag
        assert svc.is_enabled("garmin_connect_enabled", STRANGER_ID) is False

    def test_zero_rollout_alone_blocks_everyone(self):
        """With rollout=0 and no allowlist, no one passes."""
        from services.plan_framework.feature_flags import FeatureFlagService
        svc = FeatureFlagService(db=MagicMock())
        flag = self._make_flag_dict([])  # empty allowlist
        svc._local_cache["garmin_connect_enabled"] = flag
        assert svc.is_enabled("garmin_connect_enabled", FOUNDER_ID) is False

    def test_absent_flag_returns_false(self):
        """Flag not in DB → is_enabled returns False (not fail-open for missing flags)."""
        from services.plan_framework.feature_flags import FeatureFlagService
        svc = FeatureFlagService(db=MagicMock())
        # No flag in local cache, and db returns None
        svc.db.query.return_value.filter_by.return_value.first.return_value = None
        assert svc.is_enabled("garmin_connect_enabled", FOUNDER_ID) is False

    def test_allowlist_checked_before_rollout(self):
        """Beta list is checked FIRST — a zero-rollout flag still grants allowlisted athletes."""
        from services.plan_framework.feature_flags import FeatureFlagService
        svc = FeatureFlagService(db=MagicMock())
        flag = self._make_flag_dict([FOUNDER_ID])
        flag["rollout_percentage"] = 0
        svc._local_cache["garmin_connect_enabled"] = flag
        # Founder is on allowlist → passes despite 0% rollout
        assert svc.is_enabled("garmin_connect_enabled", FOUNDER_ID) is True
        # Stranger is not on allowlist → 0% rollout blocks them
        assert svc.is_enabled("garmin_connect_enabled", STRANGER_ID) is False
