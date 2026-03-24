"""
Garmin Initial Backfill Service (D7)

Requests historical data from Garmin's backfill API endpoints.

HOW IT WORKS:
  Garmin backfill is asynchronous. Calling a backfill endpoint returns 202 Accepted
  immediately — no data is returned synchronously. Garmin queues the request and
  pushes the historical data to the registered webhook endpoints (D4) when ready.
  This means D4/D5/D6 webhook handlers process backfill data identically to live
  webhook pushes. No special handling is needed on our end.

BACKFILL SCOPE (Tier 1):
  - activities
  - activityDetails
  - sleeps
  - hrv
  - stressDetails
  - dailies
  - userMetrics

Garmin range limits:
  - activities/activityDetails: max 30 days
  - health endpoints: max 90 days

RATE LIMITING:
  A 1-second delay is observed between requests as a courtesy to Garmin's API.
  A 30-second delay is used after a 429 Too Many Requests response.

AUTH:
  All requests require a valid Bearer token from ensure_fresh_garmin_token().
  If no valid token is available, backfill is aborted (returns status="aborted").

SOURCE CONTRACT NOTE:
  This file makes direct Garmin API calls (not field translation). The
  adapter-to-model source contract (Garmin field names only in garmin_adapter.py)
  applies to the webhook ingestion path, not to this outbound HTTP call layer.
  API query parameter names (summaryStartTimeInSeconds, summaryEndTimeInSeconds)
  are documented here as they are part of the outbound request, not the adapter path.

See docs/PHASE2_GARMIN_INTEGRATION_AC.md §D7
See docs/garmin-portal/HEALTH_API.md §Backfill Endpoints
"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import requests

from services.garmin_oauth import ensure_fresh_garmin_token

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GARMIN_WELLNESS_BASE = "https://apis.garmin.com/wellness-api"

# Garmin backfill limits by endpoint type.
_BACKFILL_DEPTH_DAYS_ACTIVITY = 30
_BACKFILL_DEPTH_DAYS_HEALTH = 90

# Short courtesy delay between sequential backfill requests.
_INTER_REQUEST_DELAY_S = 1

# Extended back-off when Garmin returns 429 Too Many Requests.
_RATE_LIMIT_BACKOFF_S = 30
_MAX_429_RETRIES = 2

# Request timeout for each backfill call.
_TIMEOUT_S = 15

# Tier 1 backfill endpoints — ordered activities-first so webhook ingestion
# can link detail payloads to already-created activity rows.
_BACKFILL_ENDPOINTS = [
    "/rest/backfill/activities",
    "/rest/backfill/activityDetails",
    "/rest/backfill/sleeps",
    "/rest/backfill/hrv",
    "/rest/backfill/stressDetails",
    "/rest/backfill/dailies",
    "/rest/backfill/userMetrics",
]

_ACTIVITY_BACKFILL_ENDPOINTS = {
    "/rest/backfill/activities",
    "/rest/backfill/activityDetails",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _params_for_endpoint(endpoint: str, now: datetime) -> Dict[str, int]:
    """Build endpoint-specific backfill time range params."""
    depth_days = (
        _BACKFILL_DEPTH_DAYS_ACTIVITY
        if endpoint in _ACTIVITY_BACKFILL_ENDPOINTS
        else _BACKFILL_DEPTH_DAYS_HEALTH
    )
    start = now - timedelta(days=depth_days)
    return {
        "summaryStartTimeInSeconds": int(start.timestamp()),
        "summaryEndTimeInSeconds": int(now.timestamp()),
    }


def _request_single_backfill(
    endpoint: str,
    headers: Dict[str, str],
    params: Dict[str, int],
) -> Dict[str, Any]:
    """
    Make a single backfill request with 429 retry logic.

    Returns {"status": "ok"|"failed"|"duplicate"|"rate_limited"|"permission_denied", "code": int}
    """
    url = f"{_GARMIN_WELLNESS_BASE}{endpoint}"
    attempt = 0
    max_attempts = 1 + _MAX_429_RETRIES

    while attempt < max_attempts:
        attempt += 1
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=_TIMEOUT_S)
        except Exception as exc:
            logger.exception(
                "Backfill request failed for %s (attempt %d/%d): %s",
                endpoint, attempt, max_attempts, exc,
            )
            return {"status": "failed", "code": 0, "error": str(exc)}

        body_preview = (resp.text or "").strip()
        if len(body_preview) > 300:
            body_preview = f"{body_preview[:300]}..."

        if resp.status_code == 202:
            logger.info("Backfill accepted: %s → 202", endpoint)
            return {"status": "ok", "code": 202}

        if resp.status_code == 409:
            logger.info("Backfill duplicate (already processed): %s → 409 body=%r", endpoint, body_preview)
            return {"status": "duplicate", "code": 409}

        if resp.status_code == 429 and attempt < max_attempts:
            logger.warning(
                "Backfill rate limited: %s → 429 (attempt %d/%d, backing off %ds, body=%r)",
                endpoint, attempt, max_attempts, _RATE_LIMIT_BACKOFF_S, body_preview,
            )
            time.sleep(_RATE_LIMIT_BACKOFF_S)
            continue
        if resp.status_code == 429:
            logger.warning(
                "Backfill persistent rate limit: %s → 429 (attempt %d/%d, body=%r)",
                endpoint,
                attempt,
                max_attempts,
                body_preview,
            )
            return {"status": "rate_limited", "code": 429, "body": body_preview}

        if resp.status_code == 412:
            required_permission = None
            try:
                match = re.search(r"required\s+([A-Z_]+)", body_preview, flags=re.IGNORECASE)
                if match:
                    required_permission = str(match.group(1)).upper()
            except Exception:
                required_permission = None
            logger.warning(
                "Backfill permission denied: %s → 412 required_permission=%s body=%r",
                endpoint,
                required_permission,
                body_preview,
            )
            return {
                "status": "permission_denied",
                "code": 412,
                "required_permission": required_permission,
                "body": body_preview,
            }

        logger.warning(
            "Backfill unexpected: %s → %d (attempt %d/%d, body=%r)",
            endpoint, resp.status_code, attempt, max_attempts, body_preview,
        )
        return {"status": "failed", "code": resp.status_code, "body": body_preview}

    return {"status": "rate_limited", "code": 429}


# ---------------------------------------------------------------------------
# Standard backfill (30-day / 90-day)
# ---------------------------------------------------------------------------

def request_garmin_backfill(athlete: Any, db: Any) -> Dict[str, Any]:
    """
    Request a Garmin backfill for all Tier 1 data types.

    Called once after a successful OAuth connect. Each endpoint call returns
    202 Accepted — Garmin pushes the historical data to the D4 webhook endpoints
    asynchronously (may take minutes to hours).

    Args:
        athlete: SQLAlchemy Athlete ORM instance.
        db: Active SQLAlchemy session (used by ensure_fresh_garmin_token).

    Returns:
        {
            "status": "ok" | "aborted" | "deferred",
            "reason": str (when status!="ok"),
            "requested": int,   # number of 202 responses
            "failed": int,      # number of non-202 or exception responses
        }
    """
    access_token = ensure_fresh_garmin_token(athlete, db)
    if not access_token:
        logger.warning(
            "Garmin backfill aborted: no valid token for athlete %s", athlete.id
        )
        return {"status": "aborted", "reason": "no_token", "requested": 0, "failed": 0}

    now = datetime.now(timezone.utc)
    headers = {"Authorization": f"Bearer {access_token}"}

    requested = 0
    failed = 0

    for idx, endpoint in enumerate(_BACKFILL_ENDPOINTS):
        params = _params_for_endpoint(endpoint, now)
        result = _request_single_backfill(endpoint, headers, params)

        if result["status"] == "ok":
            requested += 1
        elif result["status"] == "duplicate":
            pass  # already processed, not a failure
        elif result["status"] == "rate_limited":
            failed += 1
            logger.warning(
                "Garmin backfill deferred for athlete %s due to persistent rate limit",
                athlete.id,
            )
            return {
                "status": "deferred",
                "reason": "rate_limited",
                "retry_after_s": _RATE_LIMIT_BACKOFF_S,
                "requested": requested,
                "failed": failed,
            }
        elif result["status"] == "permission_denied":
            failed += 1
            required_permission = result.get("required_permission")
            logger.warning(
                "Garmin backfill aborted for athlete %s due to missing permission: %s",
                athlete.id,
                required_permission,
            )
            return {
                "status": "aborted",
                "reason": "permission_denied",
                "required_permission": required_permission,
                "requested": requested,
                "failed": failed,
            }
        else:
            failed += 1

        if idx < len(_BACKFILL_ENDPOINTS) - 1:
            time.sleep(_INTER_REQUEST_DELAY_S)

    logger.info(
        "Garmin backfill complete for athlete %s: requested=%d failed=%d",
        athlete.id, requested, failed,
    )
    return {"status": "ok", "requested": requested, "failed": failed}


# ---------------------------------------------------------------------------
# Deep backfill (multi-window, goes back months/years)
# ---------------------------------------------------------------------------

def request_deep_garmin_backfill(
    athlete: Any,
    db: Any,
    target_start: datetime,
    inter_window_delay_s: float = 3.0,
) -> Dict[str, Any]:
    """
    Request a deep Garmin backfill spanning multiple 30/90-day windows.

    Walks backward from now to target_start, issuing one backfill request
    per window per endpoint. Activities are requested first (30-day windows),
    then activityDetails, then health endpoints (90-day windows).

    409 (duplicate) responses are skipped gracefully — they mean Garmin
    already processed that window.

    Args:
        athlete: SQLAlchemy Athlete ORM instance.
        db: Active SQLAlchemy session.
        target_start: How far back to backfill (UTC datetime).
        inter_window_delay_s: Delay between window requests (default 3s).

    Returns:
        {
            "status": "ok" | "aborted",
            "accepted": int,
            "duplicates": int,
            "failed": int,
            "details": list of per-request results,
        }
    """
    access_token = ensure_fresh_garmin_token(athlete, db)
    if not access_token:
        logger.warning("Deep backfill aborted: no valid token for athlete %s", athlete.id)
        return {"status": "aborted", "reason": "no_token",
                "accepted": 0, "duplicates": 0, "failed": 0, "details": []}

    headers = {"Authorization": f"Bearer {access_token}"}
    now = datetime.now(timezone.utc)

    # Phase 1: Activity endpoints (30-day windows) — activities first, then details
    activity_endpoints = ["/rest/backfill/activities", "/rest/backfill/activityDetails"]
    # Phase 2: Health endpoints (90-day windows)
    health_endpoints = [
        "/rest/backfill/sleeps",
        "/rest/backfill/hrv",
        "/rest/backfill/stressDetails",
        "/rest/backfill/dailies",
        "/rest/backfill/userMetrics",
    ]

    accepted = 0
    duplicates = 0
    failed = 0
    details: List[Dict[str, Any]] = []

    def _backfill_endpoint_windows(endpoint: str, window_days: int):
        nonlocal accepted, duplicates, failed, access_token

        cursor = now
        window_num = 0
        while cursor > target_start:
            window_num += 1
            window_end = cursor
            window_start = max(cursor - timedelta(days=window_days), target_start)

            params = {
                "summaryStartTimeInSeconds": int(window_start.timestamp()),
                "summaryEndTimeInSeconds": int(window_end.timestamp()),
            }

            logger.info(
                "Deep backfill: %s window %d [%s → %s]",
                endpoint, window_num,
                window_start.strftime("%Y-%m-%d"),
                window_end.strftime("%Y-%m-%d"),
            )

            result = _request_single_backfill(endpoint, headers, params)
            result["endpoint"] = endpoint
            result["window"] = f"{window_start.strftime('%Y-%m-%d')} → {window_end.strftime('%Y-%m-%d')}"
            details.append(result)

            if result["status"] == "ok":
                accepted += 1
            elif result["status"] == "duplicate":
                duplicates += 1
            else:
                failed += 1
                if result.get("code") == 429:
                    logger.warning("Rate limited after retries — stopping %s", endpoint)
                    break

            cursor = window_start
            if cursor > target_start:
                time.sleep(inter_window_delay_s)

    # Phase 1: Activities (30-day windows)
    for ep in activity_endpoints:
        _backfill_endpoint_windows(ep, _BACKFILL_DEPTH_DAYS_ACTIVITY)
        time.sleep(inter_window_delay_s)

    # Refresh token if needed (deep backfill can take minutes)
    access_token = ensure_fresh_garmin_token(athlete, db)
    if access_token:
        headers = {"Authorization": f"Bearer {access_token}"}

    # Phase 2: Health (90-day windows)
    for ep in health_endpoints:
        _backfill_endpoint_windows(ep, _BACKFILL_DEPTH_DAYS_HEALTH)
        time.sleep(inter_window_delay_s)

    logger.info(
        "Deep backfill complete for athlete %s: accepted=%d duplicates=%d failed=%d",
        athlete.id, accepted, duplicates, failed,
    )
    return {
        "status": "ok",
        "accepted": accepted,
        "duplicates": duplicates,
        "failed": failed,
        "details": details,
    }
