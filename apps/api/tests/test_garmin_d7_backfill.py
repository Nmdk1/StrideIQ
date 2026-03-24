"""
D7: Initial Backfill Tests

Tests for:
  - services/garmin_backfill.py :: request_garmin_backfill()
  - tasks/garmin_webhook_tasks.py :: request_garmin_backfill_task
  - routers/garmin.py :: backfill task triggered after successful OAuth callback

Coverage:
  - All 7 Tier 1 backfill endpoints called in sequence
  - Correct time range: now minus 90 days to now (as Unix timestamps)
  - Correct Authorization Bearer header included on each request
  - 202 Accepted counted as success (no body parsed)
  - Non-202 status counted as failure, logged, execution continues
  - 429 Too Many Requests counted as failure with extended back-off
  - No valid token → backfill aborted gracefully
  - time.sleep() called between requests (rate-limit courtesy)
  - Athlete not found → task returns skipped
  - Disconnected athlete (no token) → task returns aborted
  - Callback triggers backfill task after successful OAuth connect
  - Callback does NOT trigger backfill on error/redirect paths
"""

import time
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, call

import pytest
import requests as req_lib

ATHLETE_ID = str(uuid.uuid4())

# The 7 Tier 1 backfill endpoint paths (relative to wellness-api base)
EXPECTED_BACKFILL_PATHS = [
    "/rest/backfill/activities",
    "/rest/backfill/activityDetails",
    "/rest/backfill/sleeps",
    "/rest/backfill/hrv",
    "/rest/backfill/stressDetails",
    "/rest/backfill/dailies",
    "/rest/backfill/userMetrics",
]

GARMIN_WELLNESS_BASE = "https://apis.garmin.com/wellness-api"


def _make_mock_athlete(connected=True):
    a = MagicMock()
    a.id = uuid.UUID(ATHLETE_ID)
    a.garmin_connected = connected
    a.garmin_oauth_access_token = "enc-token" if connected else None
    return a


def _202_response():
    r = MagicMock(spec=req_lib.Response)
    r.status_code = 202
    return r


def _non_202_response(status=500):
    r = MagicMock(spec=req_lib.Response)
    r.status_code = status
    return r


# ---------------------------------------------------------------------------
# request_garmin_backfill service function
# ---------------------------------------------------------------------------

class TestBackfillService:
    """Unit tests for services.garmin_backfill.request_garmin_backfill."""

    def _run(self, mock_responses=None, token="valid-token", sleep_scale=0):
        """
        Run request_garmin_backfill with a mocked requests.get and token.

        mock_responses: list of responses in call order (default: all 202).
        """
        from services.garmin_backfill import request_garmin_backfill

        mock_athlete = _make_mock_athlete()
        mock_db = MagicMock()

        if mock_responses is None:
            mock_responses = [_202_response() for _ in EXPECTED_BACKFILL_PATHS]

        with patch("services.garmin_backfill.ensure_fresh_garmin_token", return_value=token), \
             patch("services.garmin_backfill.requests.get", side_effect=mock_responses) as mock_get, \
             patch("services.garmin_backfill.time.sleep") as mock_sleep:
            result = request_garmin_backfill(mock_athlete, mock_db)

        return result, mock_get, mock_sleep

    def test_all_tier1_endpoints_requested(self):
        result, mock_get, _ = self._run()
        called_urls = [c.args[0] for c in mock_get.call_args_list]
        for path in EXPECTED_BACKFILL_PATHS:
            expected_url = f"{GARMIN_WELLNESS_BASE}{path}"
            assert expected_url in called_urls, (
                f"Expected backfill endpoint {path} was not called. Called: {called_urls}"
            )

    def test_exactly_seven_endpoints_called(self):
        result, mock_get, _ = self._run()
        assert mock_get.call_count == len(EXPECTED_BACKFILL_PATHS)

    def test_authorization_header_sent(self):
        result, mock_get, _ = self._run(token="my-access-token")
        for c in mock_get.call_args_list:
            headers = c.kwargs.get("headers") or (c.args[1] if len(c.args) > 1 else {})
            assert headers.get("Authorization") == "Bearer my-access-token", (
                f"Authorization header missing or wrong: {headers}"
            )

    def test_time_range_is_endpoint_specific(self):
        """Activities/details use 30d, health endpoints use 90d."""
        result, mock_get, _ = self._run()
        now = datetime.now(timezone.utc)
        for c in mock_get.call_args_list:
            url = c.args[0]
            params = c.kwargs.get("params") or {}
            start_ts = params.get("summaryStartTimeInSeconds")
            end_ts = params.get("summaryEndTimeInSeconds")
            assert start_ts is not None, "summaryStartTimeInSeconds missing from params"
            assert end_ts is not None, "summaryEndTimeInSeconds missing from params"

            # End should be roughly now (within 60s tolerance for test execution time)
            assert abs(end_ts - int(now.timestamp())) < 60, (
                f"summaryEndTimeInSeconds {end_ts} is not approximately now {int(now.timestamp())}"
            )
            # Duration should match endpoint limit
            duration_days = (end_ts - start_ts) / 86400
            expected_days = 30 if (
                "backfill/activities" in url and "activityDetails" not in url
            ) or ("backfill/activityDetails" in url) else 90
            assert abs(duration_days - expected_days) < 1, (
                f"Backfill range for {url} is {duration_days:.1f} days, expected ~{expected_days}"
            )

    def test_202_counted_as_requested(self):
        result, _, _ = self._run()
        assert result["requested"] == len(EXPECTED_BACKFILL_PATHS)
        assert result["failed"] == 0

    def test_non_202_counted_as_failed(self):
        """One 500 response means 1 failure, rest succeed."""
        responses = [_202_response()] * 6 + [_non_202_response(500)]
        result, _, _ = self._run(mock_responses=responses)
        assert result["requested"] == 6
        assert result["failed"] == 1

    def test_no_body_parsed_on_202(self):
        """202 has no meaningful body — must not call .json() on response."""
        resp = _202_response()
        self._run(mock_responses=[resp] * len(EXPECTED_BACKFILL_PATHS))
        resp.json.assert_not_called()

    def test_network_error_counted_as_failed(self):
        """Requests exception on one endpoint is caught, counted as failure, continues."""
        responses = (
            [_202_response()] * 3
            + [req_lib.ConnectionError("timeout")]
            + [_202_response()] * 3
        )
        result, mock_get, _ = self._run(mock_responses=responses)
        assert result["failed"] == 1
        assert result["requested"] == 6
        # All 7 endpoints were still attempted
        assert mock_get.call_count == 7

    def test_sleep_called_between_requests(self):
        """A short sleep must occur between each request (rate-limit courtesy)."""
        result, _, mock_sleep = self._run()
        # Should be called between requests (N-1 times for N endpoints)
        assert mock_sleep.call_count >= len(EXPECTED_BACKFILL_PATHS) - 1

    def test_no_token_returns_aborted(self):
        """If ensure_fresh_garmin_token returns None, backfill is aborted."""
        from services.garmin_backfill import request_garmin_backfill
        mock_athlete = _make_mock_athlete(connected=False)
        mock_db = MagicMock()

        with patch("services.garmin_backfill.ensure_fresh_garmin_token", return_value=None), \
             patch("services.garmin_backfill.requests.get") as mock_get:
            result = request_garmin_backfill(mock_athlete, mock_db)

        assert result["status"] == "aborted"
        assert result["reason"] == "no_token"
        mock_get.assert_not_called()

    def test_429_retries_same_endpoint_with_extended_sleep(self):
        """A 429 should back off and retry same endpoint (up to max retries)."""
        responses = [_non_202_response(429)] + [_202_response()] * 7
        result, _, mock_sleep = self._run(mock_responses=responses)
        assert result["failed"] == 0
        assert result["requested"] == 7
        # There must be at least one sleep call longer than the normal inter-request delay
        sleep_args = [c.args[0] for c in mock_sleep.call_args_list]
        max_sleep = max(sleep_args) if sleep_args else 0
        assert max_sleep > 1, f"Expected an extended sleep on 429 (got max={max_sleep}s)"

    def test_429_after_max_retries_counts_as_failed(self):
        """If endpoint keeps returning 429, backfill is deferred early."""
        responses = (
            [_non_202_response(429), _non_202_response(429), _non_202_response(429)]
        )
        result, mock_get, _ = self._run(mock_responses=responses)
        assert result["status"] == "deferred"
        assert result["reason"] == "rate_limited"
        assert result["failed"] == 1
        assert result["requested"] == 0
        # 3 attempts for first endpoint, then stop.
        assert mock_get.call_count == 3

    def test_412_historical_permission_denied_aborts_without_spam(self):
        """Missing HISTORICAL_DATA_EXPORT should abort immediately after first endpoint."""
        denied = _non_202_response(412)
        denied.text = (
            '{"errorMessage":"Access denied for abc required HISTORICAL_DATA_EXPORT"}'
        )
        result, mock_get, _ = self._run(mock_responses=[denied])
        assert result["status"] == "aborted"
        assert result["reason"] == "permission_denied"
        assert result["required_permission"] == "HISTORICAL_DATA_EXPORT"
        assert result["failed"] == 1
        assert result["requested"] == 0
        assert mock_get.call_count == 1

    def test_status_ok_on_all_success(self):
        result, _, _ = self._run()
        assert result["status"] == "ok"

    def test_endpoints_called_in_correct_order(self):
        """Activities and activityDetails must be requested before wellness data."""
        result, mock_get, _ = self._run()
        called_urls = [c.args[0] for c in mock_get.call_args_list]
        activities_idx = next(i for i, u in enumerate(called_urls) if "backfill/activities" in u and "Details" not in u)
        details_idx = next(i for i, u in enumerate(called_urls) if "activityDetails" in u)
        # activities before activityDetails (both before wellness)
        assert activities_idx < details_idx


# ---------------------------------------------------------------------------
# request_garmin_backfill_task Celery task
# ---------------------------------------------------------------------------

class TestBackfillTask:
    """Unit tests for request_garmin_backfill_task in garmin_webhook_tasks.py."""

    def test_task_exists_in_module(self):
        from tasks.garmin_webhook_tasks import (
            request_deep_garmin_backfill_task,
            request_garmin_backfill_task,
        )
        assert request_garmin_backfill_task is not None
        assert request_deep_garmin_backfill_task is not None

    def test_task_name_is_correct(self):
        from tasks.garmin_webhook_tasks import (
            request_deep_garmin_backfill_task,
            request_garmin_backfill_task,
        )
        assert request_garmin_backfill_task.name == "request_garmin_backfill_task"
        assert request_deep_garmin_backfill_task.name == "request_deep_garmin_backfill_task"

    def test_athlete_not_found_returns_skipped(self):
        from tasks.garmin_webhook_tasks import request_garmin_backfill_task
        mock_db = MagicMock()

        with patch("tasks.garmin_webhook_tasks.get_db_sync", return_value=mock_db), \
             patch("tasks.garmin_webhook_tasks._find_athlete_in_db", return_value=None):
            result = request_garmin_backfill_task.run(ATHLETE_ID)

        assert result["status"] == "skipped"
        assert result["reason"] == "athlete_not_found"

    def test_no_token_returns_aborted(self):
        """Disconnected athlete (no valid token) → task returns aborted result."""
        from tasks.garmin_webhook_tasks import request_garmin_backfill_task
        mock_db = MagicMock()
        mock_athlete = _make_mock_athlete(connected=False)

        with patch("tasks.garmin_webhook_tasks.get_db_sync", return_value=mock_db), \
             patch("tasks.garmin_webhook_tasks._find_athlete_in_db", return_value=mock_athlete), \
             patch("tasks.garmin_webhook_tasks.request_garmin_backfill") as mock_backfill:
            mock_backfill.return_value = {
                "status": "aborted", "reason": "no_token", "requested": 0, "failed": 0
            }
            result = request_garmin_backfill_task.run(ATHLETE_ID)

        mock_backfill.assert_called_once_with(mock_athlete, mock_db)
        assert result["status"] == "aborted"

    def test_successful_backfill_returns_result(self):
        from tasks.garmin_webhook_tasks import request_garmin_backfill_task
        mock_db = MagicMock()
        mock_athlete = _make_mock_athlete()

        with patch("tasks.garmin_webhook_tasks.get_db_sync", return_value=mock_db), \
             patch("tasks.garmin_webhook_tasks._find_athlete_in_db", return_value=mock_athlete), \
             patch("tasks.garmin_webhook_tasks.request_garmin_backfill") as mock_backfill:
            mock_backfill.return_value = {
                "status": "ok", "requested": 7, "failed": 0
            }
            result = request_garmin_backfill_task.run(ATHLETE_ID)

        assert result["status"] == "ok"
        assert result["requested"] == 7

    def test_task_calls_backfill_with_athlete_and_db(self):
        """Task must pass the ORM athlete object and DB session to backfill."""
        from tasks.garmin_webhook_tasks import request_garmin_backfill_task
        mock_db = MagicMock()
        mock_athlete = _make_mock_athlete()

        with patch("tasks.garmin_webhook_tasks.get_db_sync", return_value=mock_db), \
             patch("tasks.garmin_webhook_tasks._find_athlete_in_db", return_value=mock_athlete), \
             patch("tasks.garmin_webhook_tasks.request_garmin_backfill") as mock_backfill:
            mock_backfill.return_value = {"status": "ok", "requested": 7, "failed": 0}
            request_garmin_backfill_task.run(ATHLETE_ID)

        mock_backfill.assert_called_once_with(mock_athlete, mock_db)

    def test_db_closed_on_exception(self):
        """DB session must be closed even when backfill raises an exception."""
        from tasks.garmin_webhook_tasks import request_garmin_backfill_task
        mock_db = MagicMock()
        mock_athlete = _make_mock_athlete()

        with patch("tasks.garmin_webhook_tasks.get_db_sync", return_value=mock_db), \
             patch("tasks.garmin_webhook_tasks._find_athlete_in_db", return_value=mock_athlete), \
             patch("tasks.garmin_webhook_tasks.request_garmin_backfill", side_effect=RuntimeError("boom")):
            with pytest.raises(Exception):
                # .run() calls the underlying function directly with the real task self.
                # self.retry() raises celery.exceptions.Retry; finally block still executes.
                request_garmin_backfill_task.run(ATHLETE_ID)

        mock_db.close.assert_called()

    def test_deep_backfill_task_calls_service(self):
        from tasks.garmin_webhook_tasks import request_deep_garmin_backfill_task

        mock_db = MagicMock()
        mock_athlete = _make_mock_athlete()
        with patch("tasks.garmin_webhook_tasks.get_db_sync", return_value=mock_db), \
             patch("tasks.garmin_webhook_tasks._find_athlete_in_db", return_value=mock_athlete), \
             patch("tasks.garmin_webhook_tasks.request_deep_garmin_backfill") as mock_service:
            mock_service.return_value = {"status": "ok", "accepted": 3, "failed": 0}
            result = request_deep_garmin_backfill_task.run(ATHLETE_ID, target_days_back=730)

        assert result["status"] == "ok"
        mock_service.assert_called_once()


# ---------------------------------------------------------------------------
# OAuth callback triggers backfill
# ---------------------------------------------------------------------------

class TestCallbackTriggersBackfill:
    """
    After a successful Garmin OAuth callback, request_garmin_backfill_task.delay()
    must be enqueued. On error paths it must NOT be enqueued.
    """

    def test_backfill_tasks_enqueued_on_successful_connect(self):
        """
        Successful callback must dispatch request_garmin_backfill_task.delay(athlete_id).
        """
        from routers.garmin import garmin_callback
        from fastapi import Request as FastAPIRequest

        mock_athlete = _make_mock_athlete()
        mock_athlete.id = uuid.UUID(ATHLETE_ID)

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_athlete

        token_data = {
            "access_token": "tok",
            "refresh_token": "ref",
            "expires_in": 86400,
        }

        mock_request = MagicMock(spec=FastAPIRequest)
        mock_request.headers = {}
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.base_url = MagicMock()
        mock_request.base_url.__str__ = lambda s: "http://localhost/"

        with patch("routers.garmin.verify_oauth_state", return_value={
                "athlete_id": ATHLETE_ID,
                "code_verifier": "verifier123",
                "return_to": "/settings",
            }), \
             patch("routers.garmin.exchange_code_for_token", return_value=token_data), \
             patch("routers.garmin.get_garmin_user_id", return_value="garmin-uid-1"), \
             patch("routers.garmin.get_user_permissions", return_value=["ACTIVITY_EXPORT", "HEALTH_EXPORT"]), \
             patch("routers.garmin._store_token_data"), \
             patch("routers.garmin.request_garmin_backfill_task") as mock_task, \
             patch("routers.garmin.request_deep_garmin_backfill_task") as mock_deep_task, \
             patch("routers.garmin.ConsentAuditLog"), \
             patch("routers.garmin.logger"):
            mock_task.delay = MagicMock()
            mock_deep_task.apply_async = MagicMock()
            response = garmin_callback(
                request=mock_request,
                code="auth-code",
                state="signed-state",
                error=None,
                db=mock_db,
            )

        mock_task.delay.assert_called_once_with(ATHLETE_ID)
        mock_deep_task.apply_async.assert_called_once()

    def test_backfill_not_enqueued_on_missing_code(self):
        """Error path (missing code) must not enqueue backfill."""
        from routers.garmin import garmin_callback
        from fastapi import Request as FastAPIRequest

        mock_request = MagicMock(spec=FastAPIRequest)
        mock_request.headers = {}
        mock_request.base_url = MagicMock()
        mock_request.base_url.__str__ = lambda s: "http://localhost/"
        mock_db = MagicMock()

        with patch("routers.garmin.request_garmin_backfill_task") as mock_task, \
             patch("routers.garmin.request_deep_garmin_backfill_task") as mock_deep_task:
            mock_task.delay = MagicMock()
            mock_deep_task.apply_async = MagicMock()
            response = garmin_callback(
                request=mock_request,
                code=None,    # missing code → early redirect
                state=None,
                error=None,
                db=mock_db,
            )

        mock_task.delay.assert_not_called()
        mock_deep_task.apply_async.assert_not_called()

    def test_backfill_not_enqueued_on_provider_error(self):
        """Provider error param must not enqueue backfill."""
        from routers.garmin import garmin_callback
        from fastapi import Request as FastAPIRequest

        mock_request = MagicMock(spec=FastAPIRequest)
        mock_request.headers = {}
        mock_request.base_url = MagicMock()
        mock_request.base_url.__str__ = lambda s: "http://localhost/"
        mock_db = MagicMock()

        with patch("routers.garmin.request_garmin_backfill_task") as mock_task, \
             patch("routers.garmin.request_deep_garmin_backfill_task") as mock_deep_task:
            mock_task.delay = MagicMock()
            mock_deep_task.apply_async = MagicMock()
            response = garmin_callback(
                request=mock_request,
                code=None,
                state=None,
                error="access_denied",
                db=mock_db,
            )

        mock_task.delay.assert_not_called()
        mock_deep_task.apply_async.assert_not_called()

    def test_backfill_task_import_in_callback_module(self):
        """
        Contract test: garmin.py must import or reference request_garmin_backfill_task.
        """
        import inspect
        import routers.garmin as garmin_mod
        source = inspect.getsource(garmin_mod)
        assert "request_garmin_backfill_task" in source
