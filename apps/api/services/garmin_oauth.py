"""
Garmin Connect OAuth 2.0 PKCE Service

Verified in the eval environment (February 2026):
  - OAuth 2.0 authorization code grant with PKCE (code_challenge_method=S256)
  - Auth URL:       https://connect.garmin.com/oauth2Confirm
  - Token endpoint: https://diauth.garmin.com/di-oauth2-service/oauth/token
  - Access token TTL:  86,400 seconds (24 hours)
  - Refresh token TTL: ~7,775,998 seconds (~90 days); rotates on each refresh
  - User ID endpoint:  GET  https://apis.garmin.com/wellness-api/rest/user/id
  - Deregistration:    DELETE https://apis.garmin.com/wellness-api/rest/user/registration
  - CORS: Garmin does not support CORS pre-flight — all calls are server-side.

All tokens are encrypted at rest using Fernet (token_encryption.py).
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import requests
from sqlalchemy.orm import Session

from core.config import settings
from services.token_encryption import decrypt_token, encrypt_token

logger = logging.getLogger(__name__)

# --- Garmin OAuth 2.0 PKCE endpoints (verified in eval environment) ---
_AUTH_URL = "https://connect.garmin.com/oauth2Confirm"
_TOKEN_URL = "https://diauth.garmin.com/di-oauth2-service/oauth/token"
_USER_ID_URL = "https://apis.garmin.com/wellness-api/rest/user/id"
_DEREGISTER_URL = "https://apis.garmin.com/wellness-api/rest/user/registration"

# Garmin's recommended buffer before proactive refresh (their docs say subtract 600s).
# We use 600s (10 minutes) as a conservative buffer, matching Garmin's own guidance.
_TOKEN_REFRESH_BUFFER_S = 600

# Request timeout for all Garmin API calls.
_TIMEOUT_S = 15


# ---------------------------------------------------------------------------
# PKCE helpers
# ---------------------------------------------------------------------------

def generate_pkce_pair() -> Tuple[str, str]:
    """
    Generate a PKCE code_verifier and code_challenge pair.

    Returns:
        (code_verifier, code_challenge)

    code_verifier: 86-char cryptographically random string from the
        base64url alphabet (a valid PKCE verifier per RFC 7636 §4.1).
    code_challenge: BASE64URL(SHA256(ASCII(code_verifier))), no padding.
    """
    # 64 random bytes → 86 chars when base64url-encoded (no padding).
    # All characters are from [A-Z a-z 0-9 - _], which is a subset of
    # the RFC 7636 unreserved characters [A-Z a-z 0-9 - . _ ~].
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode("ascii")

    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    return code_verifier, code_challenge


# ---------------------------------------------------------------------------
# Auth URL
# ---------------------------------------------------------------------------

def build_auth_url(
    code_challenge: str,
    state: str,
) -> str:
    """
    Build the Garmin OAuth 2.0 PKCE authorization URL.

    The caller is responsible for generating the code_verifier/code_challenge
    pair and embedding the code_verifier in the signed `state` token so it
    survives the round-trip to the callback.

    Returns the full URL to redirect the athlete's browser to.
    """
    if not settings.GARMIN_CLIENT_ID:
        raise ValueError("GARMIN_CLIENT_ID is not configured")
    if not settings.GARMIN_REDIRECT_URI:
        raise ValueError("GARMIN_REDIRECT_URI is not configured")

    params = {
        "response_type": "code",
        "client_id": settings.GARMIN_CLIENT_ID,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "redirect_uri": settings.GARMIN_REDIRECT_URI,
        "state": state,
    }
    # Build query string manually to control encoding precisely.
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{_AUTH_URL}?{qs}"


# ---------------------------------------------------------------------------
# Token exchange
# ---------------------------------------------------------------------------

def exchange_code_for_token(code: str, code_verifier: str) -> Dict[str, Any]:
    """
    Exchange an authorization code for access + refresh tokens.

    Args:
        code: The `code` query parameter from the Garmin callback.
        code_verifier: The PKCE code_verifier generated before the auth redirect.

    Returns:
        Garmin token response dict containing at least:
            access_token, refresh_token, expires_in
    Raises:
        requests.HTTPError: If Garmin returns a non-2xx response.
    """
    if not settings.GARMIN_CLIENT_ID or not settings.GARMIN_CLIENT_SECRET:
        raise ValueError("GARMIN_CLIENT_ID / GARMIN_CLIENT_SECRET are not configured")
    if not settings.GARMIN_REDIRECT_URI:
        raise ValueError("GARMIN_REDIRECT_URI is not configured")

    payload = {
        "grant_type": "authorization_code",
        "client_id": settings.GARMIN_CLIENT_ID,
        "client_secret": settings.GARMIN_CLIENT_SECRET,
        "code": code,
        "code_verifier": code_verifier,
        "redirect_uri": settings.GARMIN_REDIRECT_URI,
    }
    resp = requests.post(_TOKEN_URL, data=payload, timeout=_TIMEOUT_S)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------

def refresh_token(refresh_token_plaintext: str) -> Dict[str, Any]:
    """
    Refresh an expired Garmin access token.

    Garmin rotates refresh tokens — the response contains a new refresh_token.
    Both the new access_token and the new refresh_token must be stored.

    Returns:
        Garmin token response dict.
    Raises:
        requests.HTTPError: If Garmin returns a non-2xx response.
    """
    if not settings.GARMIN_CLIENT_ID or not settings.GARMIN_CLIENT_SECRET:
        raise ValueError("GARMIN_CLIENT_ID / GARMIN_CLIENT_SECRET are not configured")

    payload = {
        "grant_type": "refresh_token",
        "client_id": settings.GARMIN_CLIENT_ID,
        "client_secret": settings.GARMIN_CLIENT_SECRET,
        "refresh_token": refresh_token_plaintext,
    }
    resp = requests.post(_TOKEN_URL, data=payload, timeout=_TIMEOUT_S)
    resp.raise_for_status()
    return resp.json()


def ensure_fresh_garmin_token(athlete: Any, db: Session) -> Optional[str]:
    """
    Return a valid plaintext Garmin access token for the athlete.

    Before any Garmin API call:
      1. Decrypt stored access token.
      2. If token expires within _TOKEN_REFRESH_BUFFER_S (600 s), attempt refresh.
      3. On refresh success: store new encrypted access + refresh tokens and new expiry.
      4. On refresh failure: set garmin_connected=False and return None.
         Callers must treat None as "skip this Garmin operation gracefully."

    Args:
        athlete: SQLAlchemy Athlete instance (must have garmin_oauth_* fields).
        db: Active SQLAlchemy session.

    Returns:
        Plaintext access token, or None if unavailable/expired and unrefreshable.
    """
    from models import Athlete  # local import to avoid circulars

    if not athlete.garmin_connected or not athlete.garmin_oauth_access_token:
        return None

    # Check expiry with buffer.
    if athlete.garmin_oauth_token_expires_at:
        now = datetime.now(timezone.utc)
        buffer = timedelta(seconds=_TOKEN_REFRESH_BUFFER_S)
        if now >= (athlete.garmin_oauth_token_expires_at - buffer):
            # Token is near expiry — attempt refresh.
            logger.info(f"Garmin token near expiry for athlete {athlete.id} — refreshing")
            raw_refresh = decrypt_token(athlete.garmin_oauth_refresh_token)
            if not raw_refresh:
                logger.warning(f"No Garmin refresh token for athlete {athlete.id} — marking disconnected")
                _mark_disconnected(athlete, db)
                return None
            try:
                token_data = refresh_token(raw_refresh)
            except Exception as exc:
                logger.warning(f"Garmin token refresh failed for athlete {athlete.id}: {exc}")
                _mark_disconnected(athlete, db)
                return None

            _store_token_data(athlete, token_data, db)
            return token_data["access_token"]

    # Token is still valid — decrypt and return.
    return decrypt_token(athlete.garmin_oauth_access_token)


# ---------------------------------------------------------------------------
# Garmin API helpers
# ---------------------------------------------------------------------------

def get_garmin_user_id(access_token_plaintext: str) -> str:
    """
    Fetch the stable Garmin user ID from the Wellness API.

    This ID persists across reconnections — the same Garmin account always
    returns the same API User ID. Store as athlete.garmin_user_id.

    Returns:
        The Garmin user ID string.
    Raises:
        requests.HTTPError: On API error.
    """
    resp = requests.get(
        _USER_ID_URL,
        headers={"Authorization": f"Bearer {access_token_plaintext}"},
        timeout=_TIMEOUT_S,
    )
    resp.raise_for_status()
    data = resp.json()
    return str(data.get("userId") or data.get("user_id") or "")


def deregister_user(access_token_plaintext: str) -> None:
    """
    Call the Garmin deregistration endpoint.

    Tells Garmin to stop sending webhook data for this user. Must be called
    on explicit disconnect before clearing tokens. Safe to skip if the token
    is already invalid (caller should catch HTTPError and continue).

    Args:
        access_token_plaintext: Decrypted Garmin access token.
    Raises:
        requests.HTTPError: On non-2xx response (caller handles gracefully).
    """
    resp = requests.delete(
        _DEREGISTER_URL,
        headers={"Authorization": f"Bearer {access_token_plaintext}"},
        timeout=_TIMEOUT_S,
    )
    resp.raise_for_status()


def get_user_permissions(access_token_plaintext: str) -> list:
    """
    Check which permissions the athlete granted during OAuth consent.

    Returns a list of permission strings, e.g.:
        ["ACTIVITY_EXPORT", "HEALTH_EXPORT", "WORKOUT_IMPORT"]

    Caller should verify ACTIVITY_EXPORT and HEALTH_EXPORT are present.
    Missing permissions are non-fatal on connect — the athlete can re-auth
    to grant more.
    """
    try:
        resp = requests.get(
            "https://apis.garmin.com/wellness-api/rest/user/permissions",
            headers={"Authorization": f"Bearer {access_token_plaintext}"},
            timeout=_TIMEOUT_S,
        )
        resp.raise_for_status()
        return resp.json() or []
    except Exception as exc:
        logger.warning(f"Could not fetch Garmin user permissions: {exc}")
        return []


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _store_token_data(athlete: Any, token_data: Dict[str, Any], db: Session) -> None:
    """
    Persist encrypted token data from a Garmin OAuth response.
    Commits the session.
    """
    athlete.garmin_oauth_access_token = encrypt_token(token_data["access_token"])

    new_refresh = token_data.get("refresh_token")
    if new_refresh:
        # Refresh tokens rotate — always store the latest one.
        athlete.garmin_oauth_refresh_token = encrypt_token(new_refresh)

    expires_in = token_data.get("expires_in")
    if expires_in is not None:
        athlete.garmin_oauth_token_expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        )

    athlete.garmin_connected = True
    db.commit()


def _mark_disconnected(athlete: Any, db: Session) -> None:
    """
    Mark athlete as Garmin-disconnected without deleting data.
    Used by token refresh failures (soft disconnect).
    """
    athlete.garmin_connected = False
    db.commit()
    logger.info(f"Athlete {athlete.id} marked garmin_connected=False (token failure)")
