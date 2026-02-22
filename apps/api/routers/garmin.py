"""
Garmin Connect Integration Router — OAuth 2.0 PKCE

Implements D2 of the Phase 2 Garmin integration spec.

Endpoints:
  GET  /v1/garmin/auth-url    — returns PKCE auth URL for athlete to visit
  GET  /v1/garmin/callback    — Garmin redirects here after athlete consent
  GET  /v1/garmin/status      — athlete's Garmin connection state
  POST /v1/garmin/disconnect  — explicit disconnect + data purge

OAuth version: 2.0 PKCE (S256). Verified in eval environment Feb 2026.
PKCE code_verifier is embedded in the signed state token (round-trip).
All Garmin API calls are server-side (Garmin does not support CORS).
Tokens stored encrypted at rest (Fernet, same as Strava pattern).

See docs/PHASE2_GARMIN_INTEGRATION_AC.md §D2
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.config import settings
from core.database import get_db
from core.feature_flags import is_feature_enabled
from models import Activity, ActivityStream, Athlete, ConsentAuditLog, GarminDay
from services.garmin_oauth import (
    build_auth_url,
    deregister_user,
    ensure_fresh_garmin_token,
    exchange_code_for_token,
    generate_pkce_pair,
    get_garmin_user_id,
    get_user_permissions,
    _store_token_data,
)
from services.oauth_state import create_oauth_state, verify_oauth_state
from services.token_encryption import decrypt_token
from tasks.garmin_webhook_tasks import request_garmin_backfill_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/garmin", tags=["garmin"])

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _client_ip(request: Request) -> Optional[str]:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else None


def _web_redirect(request: Request, path: str) -> str:
    """Build a frontend redirect URL, mirroring the Strava LAN-safe pattern."""
    web_base = settings.WEB_APP_BASE_URL
    try:
        host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
        proto = request.headers.get("x-forwarded-proto") or "http"
        env_is_local = "localhost" in web_base or "127.0.0.1" in web_base
        host_is_local = "localhost" in host or "127.0.0.1" in host
        if env_is_local and host and not host_is_local:
            host_only = host.rsplit(":", 1)[0] if ":" in host else host
            host = f"{host_only}:3000"
            web_base = f"{proto}://{host}"
    except Exception:
        pass
    return f"{web_base}{path}"


# ---------------------------------------------------------------------------
# D2.1: /auth-url — start OAuth PKCE flow
# ---------------------------------------------------------------------------

@router.get("/auth-url")
def get_auth_url(
    return_to: str = Query(default="/settings", description="Frontend path to redirect to after connect"),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return the Garmin OAuth 2.0 PKCE authorization URL.

    The frontend opens this URL. After athlete consent, Garmin redirects
    to GARMIN_REDIRECT_URI (/v1/garmin/callback) with ?code=X&state=Y.

    The code_verifier is embedded in the signed state token so it survives
    the browser round-trip without server-side session storage.

    Access is gated by the `garmin_connect_enabled` feature flag.
    """
    if not is_feature_enabled("garmin_connect_enabled", str(current_user.id), db):
        raise HTTPException(
            status_code=403,
            detail={"error": "garmin_not_available", "message": "Garmin Connect is not available for your account."},
        )

    if not settings.GARMIN_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Garmin integration not configured")

    if not return_to or not return_to.startswith("/") or return_to.startswith("//"):
        return_to = "/settings"

    code_verifier, code_challenge = generate_pkce_pair()

    state = create_oauth_state({
        "athlete_id": str(current_user.id),
        "code_verifier": code_verifier,
        "return_to": return_to,
    })

    auth_url = build_auth_url(code_challenge=code_challenge, state=state)

    return {"auth_url": auth_url}


# ---------------------------------------------------------------------------
# D2.1: /callback — Garmin redirects here after athlete consent
# ---------------------------------------------------------------------------

@router.get("/callback")
def garmin_callback(
    request: Request,
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    Garmin OAuth callback. Exchanges authorization code for tokens.

    On success: stores encrypted tokens, fetches user ID, logs audit entry,
    redirects athlete to frontend /settings?garmin=connected.

    On failure: redirects to /settings?garmin=error.
    """
    # --- CSRF / state verification ---
    if error:
        logger.warning(f"Garmin OAuth error from provider: {error}")
        return RedirectResponse(url="/settings?garmin=error&reason=provider", status_code=302)

    if not state or not code:
        return RedirectResponse(url="/settings?garmin=error&reason=missing_params", status_code=302)

    payload = verify_oauth_state(state, ttl_s=600)
    if not payload:
        logger.warning("Garmin callback: invalid or expired state token")
        return RedirectResponse(url="/settings?garmin=error&reason=invalid_state", status_code=302)

    athlete_id_str = payload.get("athlete_id")
    code_verifier = payload.get("code_verifier")
    return_to = payload.get("return_to") or "/settings"

    if not isinstance(return_to, str) or not return_to.startswith("/") or return_to.startswith("//"):
        return_to = "/settings"

    if not athlete_id_str or not code_verifier:
        return RedirectResponse(url="/settings?garmin=error&reason=invalid_state", status_code=302)

    athlete = db.query(Athlete).filter(Athlete.id == athlete_id_str).first()
    if not athlete:
        return RedirectResponse(url="/settings?garmin=error&reason=athlete_not_found", status_code=302)

    # --- Feature flag gate (defense in depth) ---
    # Prevents token storage and backfill for non-allowlisted athletes even if
    # they somehow reach the callback (e.g., reused URL after flag change).
    if not is_feature_enabled("garmin_connect_enabled", str(athlete.id), db):
        logger.warning(
            "Garmin callback blocked by feature flag for athlete %s", athlete_id_str
        )
        redirect_url = _web_redirect(request, f"{return_to}?garmin=error&reason=not_available")
        return RedirectResponse(url=redirect_url, status_code=302)

    # --- Token exchange ---
    try:
        token_data = exchange_code_for_token(code=code, code_verifier=code_verifier)
    except requests.HTTPError as exc:
        logger.warning(f"Garmin token exchange failed for athlete {athlete_id_str}: {exc}")
        redirect_url = _web_redirect(request, f"{return_to}?garmin=error&reason=token_exchange")
        return RedirectResponse(url=redirect_url, status_code=302)
    except Exception as exc:
        logger.error(f"Unexpected error during Garmin token exchange: {exc}")
        redirect_url = _web_redirect(request, f"{return_to}?garmin=error&reason=internal")
        return RedirectResponse(url=redirect_url, status_code=302)

    # --- Store tokens encrypted ---
    _store_token_data(athlete, token_data, db)

    # --- Fetch stable Garmin User ID ---
    access_token_plaintext = token_data.get("access_token", "")
    try:
        garmin_uid = get_garmin_user_id(access_token_plaintext)
        if garmin_uid:
            athlete.garmin_user_id = garmin_uid
            db.commit()
    except Exception as exc:
        logger.warning(f"Could not fetch Garmin user ID for athlete {athlete_id_str}: {exc}")

    # --- Check granted permissions ---
    permissions = get_user_permissions(access_token_plaintext)
    if permissions:
        has_activity = "ACTIVITY_EXPORT" in permissions
        has_health = "HEALTH_EXPORT" in permissions
        if not has_activity or not has_health:
            logger.warning(
                f"Athlete {athlete_id_str} connected Garmin but missing permissions: "
                f"ACTIVITY_EXPORT={has_activity}, HEALTH_EXPORT={has_health}. "
                f"Granted: {permissions}"
            )

    # --- Audit log ---
    ip = _client_ip(request)
    try:
        db.add(ConsentAuditLog(
            athlete_id=athlete.id,
            consent_type="integration",
            action="garmin_connected",
            source="settings",
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
        ))
        db.commit()
    except Exception as exc:
        logger.error(f"Failed to write Garmin connect audit log for athlete {athlete_id_str}: {exc}")

    # --- Trigger 90-day initial backfill (D7) — fire-and-forget ---
    # Backfill is async: Garmin returns 202 per endpoint and pushes historical
    # data to the D4 webhook endpoints. The callback does not wait for backfill.
    try:
        request_garmin_backfill_task.delay(athlete_id_str)
        logger.info("Garmin backfill task enqueued for athlete %s", athlete_id_str)
    except Exception as exc:
        logger.warning(
            "Could not enqueue Garmin backfill task for athlete %s: %s",
            athlete_id_str,
            exc,
        )

    sep = "&" if "?" in return_to else "?"
    redirect_url = _web_redirect(request, f"{return_to}{sep}garmin=connected")
    return RedirectResponse(url=redirect_url, status_code=302)


# ---------------------------------------------------------------------------
# D2.1: /status — athlete-facing connection status
# ---------------------------------------------------------------------------

@router.get("/status")
def get_garmin_status(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return the athlete's Garmin connection status.

    Response:
        connected: bool
        garmin_user_id: str | null
        last_sync: ISO-8601 string | null
        garmin_connect_available: bool  — whether the athlete can initiate new connects
    """
    last_sync = None
    if current_user.last_garmin_sync:
        last_sync = current_user.last_garmin_sync.isoformat()

    return {
        "connected": bool(current_user.garmin_connected),
        "garmin_user_id": current_user.garmin_user_id,
        "last_sync": last_sync,
        "garmin_connect_available": is_feature_enabled(
            "garmin_connect_enabled", str(current_user.id), db
        ),
    }


# ---------------------------------------------------------------------------
# D2.3: /disconnect — explicit athlete-initiated disconnect
# ---------------------------------------------------------------------------

@router.post("/disconnect")
def disconnect_garmin(
    request: Request,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Disconnect athlete's Garmin account. Purges all Garmin data.

    Ordered steps (per AC §D2.3):
      1. Call Garmin deregistration endpoint (if token available).
      2. Clear OAuth tokens and mark garmin_connected=False.
      3. Reset AthleteIngestionState for Garmin (if present).
      4. Delete all GarminDay rows.
      5. Delete all Activity rows with provider="garmin".
      6. Write disconnect audit log entry.

    Idempotent — safe to call multiple times.
    """
    athlete = current_user
    ip = _client_ip(request)

    # --- Step 1: Deregister with Garmin (if we have a live token) ---
    if athlete.garmin_oauth_access_token:
        plaintext = decrypt_token(athlete.garmin_oauth_access_token)
        if plaintext:
            try:
                deregister_user(plaintext)
                logger.info(f"Garmin deregistration succeeded for athlete {athlete.id}")
            except Exception as exc:
                # Non-fatal — token may already be invalid. Proceed with local purge.
                logger.warning(
                    f"Garmin deregistration call failed for athlete {athlete.id} "
                    f"(continuing with local purge): {exc}"
                )

    # --- Step 2: Clear OAuth tokens ---
    athlete.garmin_oauth_access_token = None
    athlete.garmin_oauth_refresh_token = None
    athlete.garmin_oauth_token_expires_at = None
    athlete.garmin_user_id = None
    athlete.garmin_connected = False
    db.commit()

    # --- Step 3: Reset AthleteIngestionState for Garmin (if present) ---
    from models import AthleteIngestionState
    garmin_state = (
        db.query(AthleteIngestionState)
        .filter(
            AthleteIngestionState.athlete_id == athlete.id,
            AthleteIngestionState.provider == "garmin",
        )
        .first()
    )
    if garmin_state:
        db.delete(garmin_state)
        db.commit()

    # --- Step 4: Delete GarminDay rows ---
    garmin_day_count = (
        db.query(GarminDay)
        .filter(GarminDay.athlete_id == athlete.id)
        .delete(synchronize_session=False)
    )
    db.commit()
    logger.info(f"Deleted {garmin_day_count} GarminDay rows for athlete {athlete.id}")

    # --- Step 5: Delete ActivityStream rows and Garmin activities ---
    garmin_activity_ids = [
        row.id
        for row in db.query(Activity.id)
        .filter(Activity.athlete_id == athlete.id, Activity.provider == "garmin")
        .all()
    ]
    if garmin_activity_ids:
        db.query(ActivityStream).filter(
            ActivityStream.activity_id.in_(garmin_activity_ids)
        ).delete(synchronize_session=False)
        db.query(Activity).filter(
            Activity.id.in_(garmin_activity_ids)
        ).delete(synchronize_session=False)
        db.commit()
        logger.info(
            f"Deleted {len(garmin_activity_ids)} Garmin activities and their streams "
            f"for athlete {athlete.id}"
        )

    # --- Step 6: Audit log ---
    try:
        db.add(ConsentAuditLog(
            athlete_id=athlete.id,
            consent_type="integration",
            action="garmin_disconnected",
            source="settings",
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
        ))
        db.commit()
    except Exception as exc:
        logger.error(f"Failed to write Garmin disconnect audit log: {exc}")

    return {"status": "disconnected"}
