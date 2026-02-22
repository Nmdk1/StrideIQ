"""
Garmin Initial Backfill Service (D7)

Requests 90-day historical data from Garmin's backfill API endpoints.

HOW IT WORKS:
  Garmin backfill is asynchronous. Calling a backfill endpoint returns 202 Accepted
  immediately — no data is returned synchronously. Garmin queues the request and
  pushes the historical data to the registered webhook endpoints (D4) when ready.
  This means D4/D5/D6 webhook handlers process backfill data identically to live
  webhook pushes. No special handling is needed on our end.

BACKFILL SCOPE (Tier 1 — 90 days):
  - activities
  - activityDetails
  - sleeps
  - hrv
  - stressDetails
  - dailies
  - userMetrics

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
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import requests

from services.garmin_oauth import ensure_fresh_garmin_token

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GARMIN_WELLNESS_BASE = "https://apis.garmin.com/wellness-api"

# 90-day backfill window matches the correlation engine's analysis window [M4].
_BACKFILL_DEPTH_DAYS = 90

# Short courtesy delay between sequential backfill requests.
_INTER_REQUEST_DELAY_S = 1

# Extended back-off when Garmin returns 429 Too Many Requests.
_RATE_LIMIT_BACKOFF_S = 30

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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def request_garmin_backfill(athlete: Any, db: Any) -> Dict[str, Any]:
    """
    Request a 90-day backfill for all Tier 1 Garmin data types.

    Called once after a successful OAuth connect. Each endpoint call returns
    202 Accepted — Garmin pushes the historical data to the D4 webhook endpoints
    asynchronously (may take minutes to hours).

    Args:
        athlete: SQLAlchemy Athlete ORM instance.
        db: Active SQLAlchemy session (used by ensure_fresh_garmin_token).

    Returns:
        {
            "status": "ok" | "aborted",
            "reason": str (only when status="aborted"),
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
    start = now - timedelta(days=_BACKFILL_DEPTH_DAYS)
    params = {
        "summaryStartTimeInSeconds": int(start.timestamp()),
        "summaryEndTimeInSeconds": int(now.timestamp()),
    }
    headers = {"Authorization": f"Bearer {access_token}"}

    requested = 0
    failed = 0

    for idx, endpoint in enumerate(_BACKFILL_ENDPOINTS):
        url = f"{_GARMIN_WELLNESS_BASE}{endpoint}"
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=_TIMEOUT_S)
        except Exception as exc:
            logger.exception("Garmin backfill request failed for %s: %s", endpoint, exc)
            failed += 1
            if idx < len(_BACKFILL_ENDPOINTS) - 1:
                time.sleep(_INTER_REQUEST_DELAY_S)
            continue

        if resp.status_code == 202:
            logger.info("Garmin backfill requested: %s → 202 Accepted", endpoint)
            requested += 1
        elif resp.status_code == 429:
            logger.warning(
                "Garmin backfill rate limited: %s → 429 (backing off %ds)",
                endpoint,
                _RATE_LIMIT_BACKOFF_S,
            )
            failed += 1
            time.sleep(_RATE_LIMIT_BACKOFF_S)
            continue
        else:
            logger.warning(
                "Garmin backfill unexpected status: %s → %d", endpoint, resp.status_code
            )
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
