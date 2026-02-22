"""
Garmin Connect Webhook Routes (D4)

Per-type webhook endpoints matching the Garmin developer portal's Endpoint
Configuration page. Each data type has its own URL. All routes share the
`verify_garmin_webhook` dependency (Layer 1 auth + rate limiting).

Topology [PV-2]:
  Per-type routes — one endpoint per Garmin data type. The portal configures
  each URL independently. Matching this structure eliminates a dispatch layer.

Security [PV-3]:
  Layer 1 — garmin-client-id header (verify_garmin_webhook dependency)
  Layer 2 — per-route schema validation (userId required)
  Layer 3 — unknown userId → 200 + log + skip (no retry storm)
  Layer 4 — per-IP rate limiting (WebhookRateLimiter in garmin_webhook_auth)
  Layer 5 — IP allowlisting: DEFERRED — Garmin does not publish source IP
             ranges. Documented gap. Layers 1-4 are the primary defence.

Dispatch model [D4.2]:
  Each route returns 200 immediately. Processing happens in Celery workers.
  Enqueue via .delay() — fire-and-forget. No inline data processing.

D4.3 Completion gate:
  D4 cannot be marked DONE until:
    1. Endpoints are deployed to eval/staging
    2. Founder registers URLs in portal Endpoint Configuration
    3. Live webhook is captured — actual headers and payload envelope confirmed
    4. If live payload contradicts assumptions here → update before marking DONE
  See docs/PHASE2_GARMIN_INTEGRATION_AC.md §D4.3

Tier 1 routes (9):
  POST /v1/garmin/webhook/activities
  POST /v1/garmin/webhook/activity-details
  POST /v1/garmin/webhook/sleeps
  POST /v1/garmin/webhook/hrv
  POST /v1/garmin/webhook/stress
  POST /v1/garmin/webhook/dailies
  POST /v1/garmin/webhook/user-metrics
  POST /v1/garmin/webhook/deregistrations
  POST /v1/garmin/webhook/permissions

Tier 2 routes (defined but returning 501 until enabled):
  POST /v1/garmin/webhook/respiration
  POST /v1/garmin/webhook/body-comps
  POST /v1/garmin/webhook/pulse-ox
  POST /v1/garmin/webhook/mct
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from core.database import get_db
from models import Athlete
from services.garmin_webhook_auth import verify_garmin_webhook
from tasks.garmin_webhook_tasks import (
    process_garmin_activity_detail_task,
    process_garmin_activity_task,
    process_garmin_deregistration_task,
    process_garmin_health_task,
    process_garmin_permissions_task,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/garmin", tags=["garmin-webhooks"])

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _find_athlete_by_garmin_user_id(
    garmin_user_id: str,
    db: Session,
) -> Optional[Athlete]:
    """Return the connected Athlete with this garmin_user_id, or None."""
    if not garmin_user_id:
        return None
    return (
        db.query(Athlete)
        .filter(
            Athlete.garmin_user_id == garmin_user_id,
            Athlete.garmin_connected.is_(True),
        )
        .first()
    )


async def _parse_and_validate_push_payload(
    request: Request,
    route: str,
) -> Dict[str, Any]:
    """
    Layer 2: Parse JSON body and validate it is a dict with a userId field.

    Combines JSON parse (returns 400 on invalid JSON) and schema validation.

    NOTE (D4.3): The actual Garmin envelope shape is unconfirmed until the
    first live webhook capture. This validation assumes a flat dict with
    `userId` at the top level, matching the REST API schemas in
    docs/garmin-portal/HEALTH_API.md. If the live payload uses an array or
    nested envelope, update this function and tests before marking D4 DONE.

    Raises:
        HTTPException(400): Body is not valid JSON, not a dict, or missing userId.
    """
    try:
        payload = await request.json()
    except Exception:
        logger.warning(
            "Garmin webhook: invalid JSON body",
            extra={"route": route},
        )
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    if not isinstance(payload, dict):
        logger.warning(
            "Garmin webhook: non-dict payload",
            extra={"route": route, "payload_type": type(payload).__name__},
        )
        raise HTTPException(
            status_code=400,
            detail="Invalid payload: expected JSON object",
        )
    if "userId" not in payload:
        logger.warning(
            "Garmin webhook: missing userId in payload",
            extra={"route": route},
        )
        raise HTTPException(
            status_code=400,
            detail="Invalid payload: missing required field 'userId'",
        )
    return payload


def _resolve_athlete(
    payload: Dict[str, Any],
    db: Session,
    route: str,
) -> Optional[Athlete]:
    """
    Layer 3: Resolve athlete from payload userId.

    Unknown userId → log + return None (caller returns 200, no processing).
    This prevents Garmin retry storms for users who haven't connected yet
    or have since disconnected.
    """
    garmin_user_id = payload.get("userId")
    athlete = _find_athlete_by_garmin_user_id(garmin_user_id, db)
    if not athlete:
        logger.warning(
            "Garmin webhook: unknown or disconnected userId — skipping",
            extra={"route": route, "garmin_user_id": garmin_user_id},
        )
    return athlete


# ---------------------------------------------------------------------------
# Tier 1: Activity endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/webhook/activities",
    status_code=200,
    summary="Garmin activity push webhook",
)
async def webhook_activities(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(verify_garmin_webhook),
) -> Dict[str, str]:
    """
    Receives Garmin activity summary push payloads.

    Dispatch: process_garmin_activity_task (D5)
    Delivery mode: push
    """
    payload = await _parse_and_validate_push_payload(request, route="/webhook/activities")

    athlete = _resolve_athlete(payload, db, route="/webhook/activities")
    if not athlete:
        return {"status": "ok"}

    process_garmin_activity_task.delay(str(athlete.id), payload)
    logger.info(
        "Garmin webhook: activity queued",
        extra={
            "athlete_id": str(athlete.id),
            "summary_id": payload.get("summaryId"),
        },
    )
    return {"status": "ok"}


@router.post(
    "/webhook/activity-details",
    status_code=200,
    summary="Garmin activity details push webhook",
)
async def webhook_activity_details(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(verify_garmin_webhook),
) -> Dict[str, str]:
    """
    Receives Garmin activity detail push payloads (GPS, samples, laps).

    Dispatch: process_garmin_activity_detail_task (D5)
    Delivery mode: push
    """
    payload = await _parse_and_validate_push_payload(request, route="/webhook/activity-details")

    athlete = _resolve_athlete(payload, db, route="/webhook/activity-details")
    if not athlete:
        return {"status": "ok"}

    process_garmin_activity_detail_task.delay(str(athlete.id), payload)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Tier 1: Health/wellness endpoints (all dispatch to process_garmin_health_task)
# ---------------------------------------------------------------------------

@router.post(
    "/webhook/sleeps",
    status_code=200,
    summary="Garmin sleep summary push webhook",
)
async def webhook_sleeps(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(verify_garmin_webhook),
) -> Dict[str, str]:
    """
    Receives Garmin sleep summary push payloads.

    Dispatch: process_garmin_health_task (D6) with data_type="sleeps"
    Delivery mode: push
    CalendarDate rule: calendarDate is the wakeup morning, not prior night (L1).
    """
    payload = await _parse_and_validate_push_payload(request, route="/webhook/sleeps")

    athlete = _resolve_athlete(payload, db, route="/webhook/sleeps")
    if not athlete:
        return {"status": "ok"}

    process_garmin_health_task.delay(str(athlete.id), "sleeps", payload)
    return {"status": "ok"}


@router.post(
    "/webhook/hrv",
    status_code=200,
    summary="Garmin HRV summary push webhook",
)
async def webhook_hrv(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(verify_garmin_webhook),
) -> Dict[str, str]:
    """
    Receives Garmin HRV summary push payloads.

    Dispatch: process_garmin_health_task (D6) with data_type="hrv"
    Delivery mode: push
    """
    payload = await _parse_and_validate_push_payload(request, route="/webhook/hrv")

    athlete = _resolve_athlete(payload, db, route="/webhook/hrv")
    if not athlete:
        return {"status": "ok"}

    process_garmin_health_task.delay(str(athlete.id), "hrv", payload)
    return {"status": "ok"}


@router.post(
    "/webhook/stress",
    status_code=200,
    summary="Garmin stress detail push webhook",
)
async def webhook_stress(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(verify_garmin_webhook),
) -> Dict[str, str]:
    """
    Receives Garmin stress + Body Battery push payloads.

    Dispatch: process_garmin_health_task (D6) with data_type="stress"
    Delivery mode: push
    Note: negative stress values (-1 to -5) indicate data quality issues.
    Store as-is; filter at query time (WHERE avg_stress > 0).
    """
    payload = await _parse_and_validate_push_payload(request, route="/webhook/stress")

    athlete = _resolve_athlete(payload, db, route="/webhook/stress")
    if not athlete:
        return {"status": "ok"}

    process_garmin_health_task.delay(str(athlete.id), "stress", payload)
    return {"status": "ok"}


@router.post(
    "/webhook/dailies",
    status_code=200,
    summary="Garmin daily summary push webhook",
)
async def webhook_dailies(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(verify_garmin_webhook),
) -> Dict[str, str]:
    """
    Receives Garmin daily summary (midnight-to-midnight) push payloads.

    Dispatch: process_garmin_health_task (D6) with data_type="dailies"
    Delivery mode: push
    """
    payload = await _parse_and_validate_push_payload(request, route="/webhook/dailies")

    athlete = _resolve_athlete(payload, db, route="/webhook/dailies")
    if not athlete:
        return {"status": "ok"}

    process_garmin_health_task.delay(str(athlete.id), "dailies", payload)
    return {"status": "ok"}


@router.post(
    "/webhook/user-metrics",
    status_code=200,
    summary="Garmin user metrics push webhook",
)
async def webhook_user_metrics(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(verify_garmin_webhook),
) -> Dict[str, str]:
    """
    Receives Garmin user metrics push payloads (VO2 max, fitness age).

    Dispatch: process_garmin_health_task (D6) with data_type="user-metrics"
    Delivery mode: push
    Note: only vo2Max is captured in Tier 1. vo2MaxCycling and fitnessAge
    are deferred per [PV-6].
    """
    payload = await _parse_and_validate_push_payload(request, route="/webhook/user-metrics")

    athlete = _resolve_athlete(payload, db, route="/webhook/user-metrics")
    if not athlete:
        return {"status": "ok"}

    process_garmin_health_task.delay(str(athlete.id), "user-metrics", payload)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Tier 1: Common endpoints (ping mode — no push payload, just notification)
# ---------------------------------------------------------------------------

@router.post(
    "/webhook/deregistrations",
    status_code=200,
    summary="Garmin deregistration ping webhook",
)
async def webhook_deregistrations(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(verify_garmin_webhook),
) -> Dict[str, str]:
    """
    Receives Garmin deregistration pings.

    Delivery mode: enabled (ping only — no push payload).
    Triggered when a user disconnects StrideIQ from the Garmin Connect app.

    NOTE (D4.3): Ping payloads may not contain a full data object. The userId
    may be at the top level or in a nested structure. Update after live capture.

    Dispatch: process_garmin_deregistration_task
    """
    try:
        raw = await request.json()
    except Exception:
        raw = {}

    user_id = raw.get("userId") if isinstance(raw, dict) else None
    if not user_id:
        # Ping with no userId — log and acknowledge
        logger.info("Garmin deregistration ping received (no userId)")
        return {"status": "ok"}

    athlete = _find_athlete_by_garmin_user_id(user_id, db)
    if not athlete:
        logger.info(
            "Garmin deregistration ping: unknown userId",
            extra={"garmin_user_id": user_id},
        )
        return {"status": "ok"}

    process_garmin_deregistration_task.delay(str(athlete.id), raw)
    return {"status": "ok"}


@router.post(
    "/webhook/permissions",
    status_code=200,
    summary="Garmin user permissions change ping webhook",
)
async def webhook_permissions(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(verify_garmin_webhook),
) -> Dict[str, str]:
    """
    Receives Garmin user permissions change pings.

    Delivery mode: enabled (ping only — no push payload).
    Triggered when a user changes their data sharing permissions in Garmin Connect.

    NOTE (D4.3): Confirm ping payload shape after live capture.

    Dispatch: process_garmin_permissions_task
    """
    try:
        raw = await request.json()
    except Exception:
        raw = {}

    user_id = raw.get("userId") if isinstance(raw, dict) else None
    if not user_id:
        logger.info("Garmin permissions ping received (no userId)")
        return {"status": "ok"}

    athlete = _find_athlete_by_garmin_user_id(user_id, db)
    if not athlete:
        return {"status": "ok"}

    process_garmin_permissions_task.delay(str(athlete.id), raw)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Tier 2: Defined but not yet enabled (return 501 until registered in portal)
# ---------------------------------------------------------------------------

def _tier2_not_enabled() -> HTTPException:
    return HTTPException(
        status_code=501,
        detail="Tier 2 Garmin webhook not yet enabled",
    )


@router.post("/webhook/respiration", status_code=200, include_in_schema=False)
async def webhook_respiration(_: None = Depends(verify_garmin_webhook)):
    raise _tier2_not_enabled()


@router.post("/webhook/body-comps", status_code=200, include_in_schema=False)
async def webhook_body_comps(_: None = Depends(verify_garmin_webhook)):
    raise _tier2_not_enabled()


@router.post("/webhook/pulse-ox", status_code=200, include_in_schema=False)
async def webhook_pulse_ox(_: None = Depends(verify_garmin_webhook)):
    raise _tier2_not_enabled()


@router.post("/webhook/mct", status_code=200, include_in_schema=False)
async def webhook_mct(_: None = Depends(verify_garmin_webhook)):
    """MCT = Menstrual Cycle Tracking. Tier 2: separate GarminCycle model."""
    raise _tier2_not_enabled()
