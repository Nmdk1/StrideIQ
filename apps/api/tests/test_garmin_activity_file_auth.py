"""
Regression contract for Garmin activity-file FIT downloads.

Background: Garmin's activity-file callback URL must be requested with the
athlete's OAuth bearer token. Without it, Garmin returns HTTP 400 and we
silently drop every strength-workout FIT (no per-set data parsed, no
exercise_set rows written). This was the root cause of the Apr 20 2026
strength session showing "Detailed exercise data not available" on the
session detail page even though Garmin had captured all 8 sets.

These tests lock in:
  1. Authorization: Bearer <token> header is sent on every FIT GET
  2. Token is refreshed via ensure_fresh_garmin_token before the request
  3. Missing-token short-circuit returns a stable structured envelope
  4. Non-2xx responses surface Garmin's response body in the log payload
     so future debugging doesn't require log-spelunking

Future agents: do NOT remove these tests. The unauthenticated GET path
was production-broken for weeks before we found it; the cost was every
strength workout's per-set ingest.
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import requests as req_lib


def _mock_athlete():
    a = MagicMock()
    a.id = uuid.uuid4()
    a.garmin_connected = True
    return a


def _mock_response(status: int = 200, body: str = "", content: bytes = b""):
    r = MagicMock(spec=req_lib.Response)
    r.status_code = status
    r.text = body
    r.content = content
    return r


def _record(callback_url: str = "https://apis.garmin.com/wellness-api/cb/abc?token=xyz") -> dict:
    return {
        "userId": "garmin-user-id",
        "summaryId": "22596174467-file",
        "fileType": "FIT",
        "callbackURL": callback_url,
    }


def _run_task(
    *,
    record: dict | None = None,
    response: MagicMock | None = None,
    token: str | None = "valid-token",
    athlete: MagicMock | None = None,
):
    """
    Invoke the FIT download task with mocks for DB, OAuth, and HTTP.

    Stubs everything past the HTTP boundary (we don't exercise the parser
    or the activity matcher here — those have their own tests). The point
    of this suite is the auth contract.
    """
    from tasks.garmin_webhook_tasks import process_garmin_activity_file_task

    record = record if record is not None else _record()
    response = response if response is not None else _mock_response(status=200, content=b"\x00fit")
    athlete = athlete if athlete is not None else _mock_athlete()

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = athlete

    with patch(
        "tasks.garmin_webhook_tasks.get_db_sync", return_value=mock_db
    ), patch(
        "tasks.garmin_webhook_tasks.ensure_fresh_garmin_token", return_value=token
    ), patch(
        "tasks.garmin_webhook_tasks._find_activity_for_summary_id", return_value=None
    ) as mock_find, patch(
        "requests.get", return_value=response
    ) as mock_get:
        mock_find.return_value = None
        try:
            result = process_garmin_activity_file_task.run(
                str(athlete.id), record
            )
        except Exception as exc:
            result = {"_raised": exc}

    return result, mock_get


class TestActivityFileAuthContract:
    """The FIT download MUST send the athlete's OAuth bearer token."""

    def test_authorization_header_sent_on_callback_get(self):
        result, mock_get = _run_task(token="abc-123")
        assert mock_get.called, "FIT download was never attempted"
        call = mock_get.call_args
        headers = call.kwargs.get("headers") or {}
        assert headers.get("Authorization") == "Bearer abc-123", (
            f"Activity-file GET missing/wrong Authorization header: {headers!r}. "
            "Garmin returns HTTP 400 (not 401) on this endpoint when the "
            "bearer is absent — see test docstring."
        )

    def test_callback_url_is_passed_unmodified(self):
        url = "https://apis.garmin.com/wellness-api/cb/abc?token=xyz&t=1"
        result, mock_get = _run_task(record=_record(callback_url=url))
        assert mock_get.called
        called_url = mock_get.call_args.args[0]
        assert called_url == url, (
            f"Callback URL was modified before fetch: got {called_url!r} "
            f"expected {url!r}"
        )

    def test_missing_token_skips_without_fetch(self):
        """No token → don't issue an unauthenticated GET. Stable envelope."""
        result, mock_get = _run_task(token=None)
        assert not mock_get.called, (
            "Task issued a network request without a token — "
            "this is the bug we are guarding against."
        )
        assert result["status"] == "skipped"
        assert result["reason"] == "no_garmin_token"

    def test_missing_athlete_skips_without_fetch(self):
        """Athlete not found → don't fetch. Stable envelope."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        from tasks.garmin_webhook_tasks import process_garmin_activity_file_task

        with patch(
            "tasks.garmin_webhook_tasks.get_db_sync", return_value=mock_db
        ), patch(
            "tasks.garmin_webhook_tasks.ensure_fresh_garmin_token"
        ) as mock_token, patch(
            "requests.get"
        ) as mock_get:
            result = process_garmin_activity_file_task.run(
                str(uuid.uuid4()), _record()
            )

        assert not mock_get.called
        assert not mock_token.called
        assert result["status"] == "skipped"
        assert result["reason"] == "athlete_not_found"

    def test_no_callback_url_returns_skipped(self):
        record = _record()
        record.pop("callbackURL")
        result, mock_get = _run_task(record=record)
        assert not mock_get.called
        assert result["status"] == "skipped"
        assert result["reason"] == "no_callback_url"


class TestActivityFileErrorBodySurfaced:
    """Non-2xx responses must surface Garmin's body so root cause is visible."""

    def test_400_includes_body_preview_in_envelope(self):
        body = "invalid_token: signature verification failed"
        response = _mock_response(status=400, body=body)
        result, mock_get = _run_task(response=response)
        assert result["status"] == "error"
        assert result["http_code"] == 400
        assert body in result["body_preview"], (
            f"4xx error envelope must echo Garmin's response body for "
            f"debuggability. Got: {result!r}"
        )

    def test_403_does_not_retry(self):
        """4xx must not enter celery retry — they are permanent."""
        response = _mock_response(status=403, body="forbidden")
        result, _ = _run_task(response=response)
        # If the task had retried, .run() would have raised celery's Retry
        # exception, which our wrapper would have stored under _raised.
        assert "_raised" not in result
        assert result["status"] == "error"
        assert result["http_code"] == 403

    def test_long_body_truncated_in_envelope(self):
        big = "x" * 1000
        response = _mock_response(status=400, body=big)
        result, _ = _run_task(response=response)
        assert len(result["body_preview"]) <= 310  # 300 + ellipsis
        assert result["body_preview"].endswith("...")
