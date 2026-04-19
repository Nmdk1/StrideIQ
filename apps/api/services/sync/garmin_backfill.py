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

import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

from core.cache import get_redis_client
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

# Redis checkpoint for deep backfill (per athlete, endpoint, target_start anchor).
_DEEP_BACKFILL_CK_PREFIX = "garmin:deep_backfill:cursor"
_DEEP_BACKFILL_CK_TTL_S = 60 * 60 * 24 * 120  # 120 days


def _deep_backfill_cursor_key(
    athlete_id: str, endpoint: str, target_start: datetime
) -> str:
    ts = int(target_start.timestamp())
    ep = endpoint.replace("/", "_").strip("_")
    return f"{_DEEP_BACKFILL_CK_PREFIX}:{athlete_id}:{ep}:t{ts}"


def _load_deep_backfill_cursor(
    redis_client: Any,
    athlete_id: str,
    endpoint: str,
    target_start: datetime,
    now: datetime,
) -> Optional[datetime]:
    if not redis_client:
        return None
    raw = redis_client.get(
        _deep_backfill_cursor_key(athlete_id, endpoint, target_start)
    )
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if int(data["target_start_ts"]) != int(target_start.timestamp()):
            return None
        cur = datetime.fromisoformat(data["cursor_iso"])
        if cur.tzinfo is None:
            cur = cur.replace(tzinfo=timezone.utc)
        if cur <= target_start or cur > now + timedelta(minutes=1):
            return None
        return cur
    except Exception:
        return None


def _save_deep_backfill_cursor(
    redis_client: Any,
    athlete_id: str,
    endpoint: str,
    target_start: datetime,
    cursor: datetime,
) -> None:
    if not redis_client:
        return
    payload = json.dumps(
        {
            "cursor_iso": cursor.isoformat(),
            "target_start_ts": int(target_start.timestamp()),
        }
    )
    redis_client.set(
        _deep_backfill_cursor_key(athlete_id, endpoint, target_start),
        payload,
        ex=_DEEP_BACKFILL_CK_TTL_S,
    )


def _clear_deep_backfill_cursor(
    redis_client: Any,
    athlete_id: str,
    endpoint: str,
    target_start: datetime,
) -> None:
    if not redis_client:
        return
    redis_client.delete(_deep_backfill_cursor_key(athlete_id, endpoint, target_start))


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

# Activity-files backfill is intentionally NOT in the auto-triggered list.
# It is requested explicitly by request_garmin_activity_files_backfill_task
# so that we can re-pull FIT files for the historical corpus without
# auto-firing on every new connect. Garmin pushes back to the existing
# webhook handler — no new code path on the receive side.
_ACTIVITY_FILES_ENDPOINT = "/rest/backfill/activityFiles"


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
                endpoint,
                attempt,
                max_attempts,
                exc,
            )
            return {"status": "failed", "code": 0, "error": str(exc)}

        body_preview = (resp.text or "").strip()
        if len(body_preview) > 300:
            body_preview = f"{body_preview[:300]}..."

        if resp.status_code == 202:
            logger.info("Backfill accepted: %s → 202", endpoint)
            return {"status": "ok", "code": 202}

        if resp.status_code == 409:
            logger.info(
                "Backfill duplicate (already processed): %s → 409 body=%r",
                endpoint,
                body_preview,
            )
            return {"status": "duplicate", "code": 409}

        if resp.status_code == 429 and attempt < max_attempts:
            logger.warning(
                "Backfill rate limited: %s → 429 (attempt %d/%d, backing off %ds, body=%r)",
                endpoint,
                attempt,
                max_attempts,
                _RATE_LIMIT_BACKOFF_S,
                body_preview,
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
                match = re.search(
                    r"required\s+([A-Z_]+)", body_preview, flags=re.IGNORECASE
                )
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
            endpoint,
            resp.status_code,
            attempt,
            max_attempts,
            body_preview,
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
        athlete.id,
        requested,
        failed,
    )
    return {"status": "ok", "requested": requested, "failed": failed}


# ---------------------------------------------------------------------------
# Activity-files backfill (FIT-derived metrics for historical runs)
# ---------------------------------------------------------------------------


def request_activity_files_backfill(
    athlete: Any,
    db: Any,
    days: int = 30,
) -> Dict[str, Any]:
    """
    Request a Garmin backfill for `activityFiles` only.

    Garmin replies 202 and asynchronously pushes the FIT files for the
    historical window to our existing activity-files webhook handler
    (process_garmin_activity_file_task), which then calls the FIT run parser.

    Use cases:
      - Bring FIT-derived metrics (power, running dynamics, total ascent/
        descent, intensity minutes) into existing activities that were
        ingested before the FIT pipeline existed.
      - Re-pull a single athlete's history after a FIT-parser bug fix.

    Garmin range limit for activityFiles: 30 days per request. Caller may
    invoke multiple times with non-overlapping windows for deeper backfill;
    duplicate (409) windows are silently skipped.

    Args:
        athlete: SQLAlchemy Athlete ORM instance.
        db:      Active session for token refresh.
        days:    Backfill depth in days (clamped to 1..30).

    Returns:
        {"status": "ok" | "aborted" | "deferred",
         "code": int, "reason": str | None}
    """
    access_token = ensure_fresh_garmin_token(athlete, db)
    if not access_token:
        return {"status": "aborted", "reason": "no_token", "code": 0}

    days = max(1, min(int(days), _BACKFILL_DEPTH_DAYS_ACTIVITY))
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "summaryStartTimeInSeconds": int(start.timestamp()),
        "summaryEndTimeInSeconds": int(now.timestamp()),
    }

    result = _request_single_backfill(_ACTIVITY_FILES_ENDPOINT, headers, params)
    logger.info(
        "activityFiles backfill for athlete %s days=%d → %s",
        athlete.id, days, result,
    )
    return result


# ---------------------------------------------------------------------------
# Deep backfill (multi-window, goes back months/years)
# ---------------------------------------------------------------------------


def request_deep_garmin_backfill(
    athlete: Any,
    db: Any,
    target_start: datetime,
    inter_window_delay_s: float = 3.0,
    run_health_phase: bool = True,
) -> Dict[str, Any]:
    """
    Request a deep Garmin backfill spanning multiple 30/90-day windows.

    Walks backward from now to target_start, issuing one backfill request
    per window per endpoint. **All activity stream windows complete before any
    health windows** — activity data and health backfill no longer interleave,
    reducing contention on Garmin rate limits.

    Progress is checkpointed in Redis per endpoint so a new run resumes from the
    last completed window instead of restarting the full walk from ``now``.

    409 (duplicate) responses are skipped gracefully — they mean Garmin
    already processed that window.

    Args:
        athlete: SQLAlchemy Athlete ORM instance.
        db: Active SQLAlchemy session.
        target_start: How far back to backfill (UTC datetime).
        inter_window_delay_s: Delay between window requests (default 3s).
        run_health_phase: When False, only activity + activityDetails windows are
            requested (health can be scheduled separately if needed).

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
        logger.warning(
            "Deep backfill aborted: no valid token for athlete %s", athlete.id
        )
        return {
            "status": "aborted",
            "reason": "no_token",
            "accepted": 0,
            "duplicates": 0,
            "failed": 0,
            "details": [],
        }

    headers = {"Authorization": f"Bearer {access_token}"}
    now = datetime.now(timezone.utc)
    redis_client = get_redis_client()
    athlete_id_str = str(athlete.id)

    # Phase 1: Activity endpoints (30-day windows) — activities first, then details
    activity_endpoints = ["/rest/backfill/activities", "/rest/backfill/activityDetails"]
    # Phase 2: Health endpoints (90-day windows) — runs only after all activity windows
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

    def _backfill_endpoint_windows(endpoint: str, window_days: int) -> None:
        nonlocal accepted, duplicates, failed, access_token

        resume = _load_deep_backfill_cursor(
            redis_client, athlete_id_str, endpoint, target_start, now
        )
        cursor = resume if resume is not None else now
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
                endpoint,
                window_num,
                window_start.strftime("%Y-%m-%d"),
                window_end.strftime("%Y-%m-%d"),
            )

            result = _request_single_backfill(endpoint, headers, params)
            result["endpoint"] = endpoint
            result["window"] = (
                f"{window_start.strftime('%Y-%m-%d')} → {window_end.strftime('%Y-%m-%d')}"
            )
            details.append(result)

            if result["status"] == "ok":
                accepted += 1
            elif result["status"] == "duplicate":
                duplicates += 1
            else:
                failed += 1
                if result.get("code") == 429:
                    logger.warning("Rate limited after retries — stopping %s", endpoint)
                    # Retry this window on the next run (same as original: no cursor advance).
                    _save_deep_backfill_cursor(
                        redis_client, athlete_id_str, endpoint, target_start, window_end
                    )
                    break

            if result.get("code") != 429:
                _save_deep_backfill_cursor(
                    redis_client, athlete_id_str, endpoint, target_start, window_start
                )

            cursor = window_start
            if cursor > target_start:
                time.sleep(inter_window_delay_s)

        if cursor <= target_start:
            _clear_deep_backfill_cursor(
                redis_client, athlete_id_str, endpoint, target_start
            )

    # Phase 1: Activities (30-day windows) — complete before health
    for ep in activity_endpoints:
        _backfill_endpoint_windows(ep, _BACKFILL_DEPTH_DAYS_ACTIVITY)
        time.sleep(inter_window_delay_s)

    # Refresh token if needed (deep backfill can take minutes)
    access_token = ensure_fresh_garmin_token(athlete, db)
    if access_token:
        headers = {"Authorization": f"Bearer {access_token}"}

    # Phase 2: Health (90-day windows) — same ordering; optional for split scheduling
    if run_health_phase:
        for ep in health_endpoints:
            _backfill_endpoint_windows(ep, _BACKFILL_DEPTH_DAYS_HEALTH)
            time.sleep(inter_window_delay_s)

    logger.info(
        "Deep backfill complete for athlete %s: accepted=%d duplicates=%d failed=%d",
        athlete.id,
        accepted,
        duplicates,
        failed,
    )
    return {
        "status": "ok",
        "accepted": accepted,
        "duplicates": duplicates,
        "failed": failed,
        "details": details,
    }
