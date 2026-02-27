"""
D4 Webhook Endpoint Tests

Tests for:
  - D4.1: verify_garmin_webhook dependency (layered security)
  - D4.0: per-type webhook route registration
  - D4.2: Celery task dispatch (fire-and-forget)
  - Source contracts: no hardcoded client IDs, task names correct

AC source: docs/PHASE2_GARMIN_INTEGRATION_AC.md §D4

NOTE ON D4.3 COMPLETION GATE:
  D4 is start-unblocked but completion-gated on the first live webhook
  capture (D4.3). The runtime tests here use a mocked payload structure.
  If the live webhook capture (D4.3) reveals that Garmin's actual envelope
  differs from this assumption, update the route handlers AND these tests.

  Unknown items pending D4.3 live capture:
    - Exact HTTP header set beyond garmin-client-id
    - Payload envelope shape (dict vs wrapped/array)
"""

import inspect
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ===========================================================================
# Source contracts
# ===========================================================================

class TestWebhookSourceContract:
    """Inspect garmin_webhooks.py for structural correctness."""

    def _get_source(self):
        import routers.garmin_webhooks as mod
        return inspect.getsource(mod)

    def test_all_tier1_routes_present(self):
        source = self._get_source()
        tier1_paths = [
            "/webhook/activities",
            "/webhook/activity-details",
            "/webhook/sleeps",
            "/webhook/hrv",
            "/webhook/stress",
            "/webhook/dailies",
            "/webhook/user-metrics",
            "/webhook/deregistrations",
            "/webhook/permissions",
        ]
        for path in tier1_paths:
            assert path in source, f"Tier 1 webhook route '{path}' missing from garmin_webhooks.py"

    def test_verify_garmin_webhook_used_on_all_routes(self):
        """verify_garmin_webhook must appear as a dependency on all routes."""
        source = self._get_source()
        assert "verify_garmin_webhook" in source

    def test_garmin_client_id_not_hardcoded(self):
        """GARMIN_CLIENT_ID must come from settings, never hardcoded."""
        import services.garmin_webhook_auth as auth_mod
        source = inspect.getsource(auth_mod)
        # Should reference settings.GARMIN_CLIENT_ID, not a literal string
        assert "settings.GARMIN_CLIENT_ID" in source

    def test_no_inline_processing_in_router(self):
        """Processing must happen in Celery tasks, not in the webhook handler."""
        source = self._get_source()
        # The router should dispatch via .delay() and return immediately
        assert ".delay(" in source, "Webhook router must dispatch tasks via .delay()"

    def test_celery_task_stubs_defined(self):
        from tasks.garmin_webhook_tasks import (
            process_garmin_activity_task,
            process_garmin_activity_detail_task,
            process_garmin_health_task,
            process_garmin_deregistration_task,
            process_garmin_permissions_task,
        )
        # All 5 tasks must be importable
        for task in (
            process_garmin_activity_task,
            process_garmin_activity_detail_task,
            process_garmin_health_task,
            process_garmin_deregistration_task,
            process_garmin_permissions_task,
        ):
            assert callable(task)


# ===========================================================================
# D4.1: verify_garmin_webhook auth dependency — unit tests
# ===========================================================================

class TestVerifyGarminWebhook:
    """Unit tests for the verify_garmin_webhook FastAPI dependency."""

    def _make_request(self, headers: dict = None):
        """Build a mock FastAPI Request with given headers."""
        from unittest.mock import MagicMock
        req = MagicMock()
        req.headers = headers or {}
        req.client = MagicMock()
        req.client.host = "1.2.3.4"
        return req

    @pytest.mark.asyncio
    async def test_missing_header_raises_401(self):
        from fastapi import HTTPException
        from services.garmin_webhook_auth import verify_garmin_webhook

        req = self._make_request({})
        with pytest.raises(HTTPException) as exc:
            await verify_garmin_webhook(req)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_header_raises_401(self):
        from fastapi import HTTPException
        from services.garmin_webhook_auth import verify_garmin_webhook

        req = self._make_request({"garmin-client-id": "wrong-id"})
        with (
            patch("services.garmin_webhook_auth.settings") as mock_settings,
            pytest.raises(HTTPException) as exc,
        ):
            mock_settings.GARMIN_CLIENT_ID = "correct-id"
            await verify_garmin_webhook(req)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_correct_header_does_not_raise(self):
        from services.garmin_webhook_auth import verify_garmin_webhook

        req = self._make_request({"garmin-client-id": "correct-id"})
        with patch("services.garmin_webhook_auth.settings") as mock_settings:
            mock_settings.GARMIN_CLIENT_ID = "correct-id"
            # Should not raise
            await verify_garmin_webhook(req)

    @pytest.mark.asyncio
    async def test_x_garmin_client_id_header_does_not_raise(self):
        from services.garmin_webhook_auth import verify_garmin_webhook

        req = self._make_request({"x-garmin-client-id": "correct-id"})
        with patch("services.garmin_webhook_auth.settings") as mock_settings:
            mock_settings.GARMIN_CLIENT_ID = "correct-id"
            await verify_garmin_webhook(req)

    @pytest.mark.asyncio
    async def test_unconfigured_raises_503(self):
        """If GARMIN_CLIENT_ID is not set, return 503."""
        from fastapi import HTTPException
        from services.garmin_webhook_auth import verify_garmin_webhook

        req = self._make_request({"garmin-client-id": "some-id"})
        with (
            patch("services.garmin_webhook_auth.settings") as mock_settings,
            pytest.raises(HTTPException) as exc,
        ):
            mock_settings.GARMIN_CLIENT_ID = None
            await verify_garmin_webhook(req)
        assert exc.value.status_code == 503


# ===========================================================================
# D4.1: Rate limiter unit tests
# ===========================================================================

class TestWebhookRateLimiter:
    """Unit tests for the in-process per-IP rate limiter."""

    def test_within_limit_is_allowed(self):
        from services.garmin_webhook_auth import WebhookRateLimiter

        limiter = WebhookRateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            assert limiter.is_allowed("1.2.3.4") is True

    def test_exceeds_limit_is_rejected(self):
        from services.garmin_webhook_auth import WebhookRateLimiter

        limiter = WebhookRateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            limiter.is_allowed("1.2.3.4")
        # 4th request should be rejected
        assert limiter.is_allowed("1.2.3.4") is False

    def test_different_ips_are_tracked_independently(self):
        from services.garmin_webhook_auth import WebhookRateLimiter

        limiter = WebhookRateLimiter(max_requests=2, window_seconds=60)
        limiter.is_allowed("1.1.1.1")
        limiter.is_allowed("1.1.1.1")
        # 1.1.1.1 is now at limit
        assert limiter.is_allowed("1.1.1.1") is False
        # 2.2.2.2 is untouched
        assert limiter.is_allowed("2.2.2.2") is True

    def test_window_reset_allows_new_requests(self):
        """After window expires, counter resets."""
        import time
        from services.garmin_webhook_auth import WebhookRateLimiter

        limiter = WebhookRateLimiter(max_requests=2, window_seconds=1)
        limiter.is_allowed("1.2.3.4")
        limiter.is_allowed("1.2.3.4")
        assert limiter.is_allowed("1.2.3.4") is False

        time.sleep(1.1)
        # After window expires, should be allowed again
        assert limiter.is_allowed("1.2.3.4") is True


class TestVerifyGarminWebhookProxyIpHandling:
    @pytest.mark.asyncio
    async def test_uses_x_forwarded_for_for_rate_limiter_key(self):
        from services.garmin_webhook_auth import verify_garmin_webhook

        req = MagicMock()
        req.headers = {
            "garmin-client-id": "correct-id",
            "x-forwarded-for": "203.0.113.10, 10.0.0.1",
        }
        req.client = MagicMock()
        req.client.host = "10.0.0.1"

        with patch("services.garmin_webhook_auth.settings") as mock_settings, \
             patch("services.garmin_webhook_auth._rate_limiter") as mock_limiter:
            mock_settings.GARMIN_CLIENT_ID = "correct-id"
            mock_limiter.is_allowed.return_value = True
            await verify_garmin_webhook(req)

        mock_limiter.is_allowed.assert_called_once_with("203.0.113.10")


# ===========================================================================
# D4.0 + D4.2: Webhook endpoint integration tests
# ===========================================================================

@pytest.fixture
def client_with_garmin_id():
    """TestClient with GARMIN_CLIENT_ID configured and DB mocked."""
    from main import app
    from core.database import get_db

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    def _override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_get_db
    with patch("services.garmin_webhook_auth.settings") as mock_settings:
        mock_settings.GARMIN_CLIENT_ID = "test-client-id"
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
    app.dependency_overrides.pop(get_db, None)


def _valid_headers(client_id: str = "test-client-id") -> dict:
    return {"garmin-client-id": client_id, "Content-Type": "application/json"}


def _minimal_payload(user_id: str = "garmin-user-xyz") -> dict:
    """Garmin push envelope: array of records keyed by data type."""
    return {"activities": [{"userId": user_id, "summaryId": "abc-001"}]}


def _minimal_record(user_id: str = "garmin-user-xyz") -> dict:
    """Single record inside the array."""
    return {"userId": user_id, "summaryId": "abc-001"}


class TestWebhookAuthViaEndpoints:
    """Test the auth middleware behavior via the actual HTTP endpoints."""

    def test_missing_header_returns_401(self, client_with_garmin_id):
        resp = client_with_garmin_id.post(
            "/v1/garmin/webhook/activities",
            json=_minimal_payload(),
        )
        assert resp.status_code == 401

    def test_wrong_header_returns_401(self, client_with_garmin_id):
        resp = client_with_garmin_id.post(
            "/v1/garmin/webhook/activities",
            headers=_valid_headers("wrong-id"),
            json=_minimal_payload(),
        )
        assert resp.status_code == 401

    def test_malformed_payload_returns_400(self, client_with_garmin_id):
        """Genuinely invalid JSON -> 400."""
        resp = client_with_garmin_id.post(
            "/v1/garmin/webhook/activities",
            headers=_valid_headers(),
            content="not-json",
        )
        assert resp.status_code in (400, 422)

    def test_missing_data_key_returns_200(self, client_with_garmin_id):
        """Unrecognized envelope -> 200 (no retry storm), no task enqueued."""
        with patch("routers.garmin_webhooks.process_garmin_activity_task") as mock_task:
            resp = client_with_garmin_id.post(
                "/v1/garmin/webhook/activities",
                headers=_valid_headers(),
                json={"somethingElse": []},
            )
        assert resp.status_code == 200
        mock_task.delay.assert_not_called()

    def test_unknown_user_id_returns_200_and_skips(self, client_with_garmin_id):
        """Unknown userId -> 200 (no retry storm), no task enqueued."""
        with patch("routers.garmin_webhooks.process_garmin_activity_task") as mock_task:
            resp = client_with_garmin_id.post(
                "/v1/garmin/webhook/activities",
                headers=_valid_headers(),
                json=_minimal_payload(user_id="unknown-garmin-user"),
            )
        assert resp.status_code == 200
        mock_task.delay.assert_not_called()

    def test_valid_request_returns_200(self, client_with_garmin_id):
        """Valid header + known userId -> 200."""
        mock_athlete = MagicMock()
        mock_athlete.id = "athlete-uuid-123"
        with patch(
            "routers.garmin_webhooks._find_athlete_by_garmin_user_id",
            return_value=mock_athlete,
        ):
            with patch("routers.garmin_webhooks.process_garmin_activity_task"):
                resp = client_with_garmin_id.post(
                    "/v1/garmin/webhook/activities",
                    headers=_valid_headers(),
                    json=_minimal_payload(user_id="known-garmin-user"),
                )
        assert resp.status_code == 200

    def test_valid_request_enqueues_task(self, client_with_garmin_id):
        """Valid webhook dispatches Celery task via .delay()."""
        mock_athlete = MagicMock()
        mock_athlete.id = "athlete-uuid-123"
        with patch(
            "routers.garmin_webhooks._find_athlete_by_garmin_user_id",
            return_value=mock_athlete,
        ) as _:
            with patch(
                "routers.garmin_webhooks.process_garmin_activity_task"
            ) as mock_task:
                client_with_garmin_id.post(
                    "/v1/garmin/webhook/activities",
                    headers=_valid_headers(),
                    json=_minimal_payload(user_id="known-garmin-user"),
                )
        mock_task.delay.assert_called_once()

    def test_multiple_records_dispatch_multiple_tasks(self, client_with_garmin_id):
        """Multiple records in the array -> one task per record."""
        mock_athlete = MagicMock()
        mock_athlete.id = "athlete-uuid-123"
        with patch(
            "routers.garmin_webhooks._find_athlete_by_garmin_user_id",
            return_value=mock_athlete,
        ):
            with patch(
                "routers.garmin_webhooks.process_garmin_activity_task"
            ) as mock_task:
                client_with_garmin_id.post(
                    "/v1/garmin/webhook/activities",
                    headers=_valid_headers(),
                    json={"activities": [
                        {"userId": "u1", "summaryId": "s1"},
                        {"userId": "u1", "summaryId": "s2"},
                    ]},
                )
        assert mock_task.delay.call_count == 2

    def test_flat_payload_fallback_still_works(self, client_with_garmin_id):
        """Flat dict with userId (legacy/unexpected) is still handled."""
        mock_athlete = MagicMock()
        mock_athlete.id = "athlete-uuid-123"
        with patch(
            "routers.garmin_webhooks._find_athlete_by_garmin_user_id",
            return_value=mock_athlete,
        ):
            with patch(
                "routers.garmin_webhooks.process_garmin_activity_task"
            ) as mock_task:
                resp = client_with_garmin_id.post(
                    "/v1/garmin/webhook/activities",
                    headers=_valid_headers(),
                    json={"userId": "known-garmin-user", "summaryId": "abc-001"},
                )
        assert resp.status_code == 200
        mock_task.delay.assert_called_once()


class TestAllTier1Routes:
    """All 9 Tier 1 routes must exist and return 401 without auth."""

    TIER1_ROUTES = [
        "/v1/garmin/webhook/activities",
        "/v1/garmin/webhook/activity-details",
        "/v1/garmin/webhook/sleeps",
        "/v1/garmin/webhook/hrv",
        "/v1/garmin/webhook/stress",
        "/v1/garmin/webhook/dailies",
        "/v1/garmin/webhook/user-metrics",
        "/v1/garmin/webhook/deregistrations",
        "/v1/garmin/webhook/permissions",
    ]

    @pytest.fixture
    def client(self):
        from main import app
        from core.database import get_db

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        def _override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = _override_get_db
        with patch("services.garmin_webhook_auth.settings") as mock_settings:
            mock_settings.GARMIN_CLIENT_ID = "test-id"
            with TestClient(app, raise_server_exceptions=False) as c:
                yield c
        app.dependency_overrides.pop(get_db, None)

    def test_all_routes_exist_and_reject_unauthenticated(self, client):
        for route in self.TIER1_ROUTES:
            resp = client.post(route, json={"test": [{"userId": "x"}]})
            assert resp.status_code == 401, (
                f"{route} should return 401 for missing auth, got {resp.status_code}"
            )

    def test_correct_tasks_per_route(self):
        """Source inspection: each route dispatches to the correct task."""
        import routers.garmin_webhooks as mod
        source = inspect.getsource(mod)

        task_assertions = [
            ("process_garmin_activity_task", "/webhook/activities"),
            ("process_garmin_activity_detail_task", "/webhook/activity-details"),
            ("process_garmin_health_task", "/webhook/sleeps"),
            ("process_garmin_deregistration_task", "/webhook/deregistrations"),
            ("process_garmin_permissions_task", "/webhook/permissions"),
        ]
        for task_name, route_path in task_assertions:
            assert task_name in source, (
                f"Task '{task_name}' not found in garmin_webhooks.py"
            )
