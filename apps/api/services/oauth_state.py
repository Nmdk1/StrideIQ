"""
Signed OAuth state helper (Phase 3).

We need a tamper-proof `state` round-trip to bind provider callbacks to the
already-authenticated athlete without creating new accounts.
"""

from __future__ import annotations

import base64
import hmac
import json
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.config import settings


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("utf-8"))


def _sign(payload_b64: str) -> str:
    key = settings.SECRET_KEY.encode("utf-8")
    mac = hmac.new(key, payload_b64.encode("utf-8"), hashlib.sha256).digest()
    return _b64url_encode(mac)


def create_oauth_state(data: Dict[str, Any]) -> str:
    """
    Create a signed state token with an issued-at timestamp.
    """
    payload = dict(data)
    payload["iat"] = int(datetime.now(timezone.utc).timestamp())
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = _b64url_encode(raw)
    sig = _sign(payload_b64)
    return f"{payload_b64}.{sig}"


def verify_oauth_state(token: str, *, ttl_s: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Verify signature and TTL. Returns payload dict if valid, else None.
    """
    if not token or "." not in token:
        return None
    payload_b64, sig = token.split(".", 1)
    if not payload_b64 or not sig:
        return None
    expected = _sign(payload_b64)
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        payload = json.loads(_b64url_decode(payload_b64))
    except Exception:
        return None

    try:
        iat = int(payload.get("iat"))
    except Exception:
        return None

    now = int(datetime.now(timezone.utc).timestamp())
    ttl = int(ttl_s if ttl_s is not None else settings.OAUTH_STATE_TTL_S)
    if ttl > 0 and (now - iat) > ttl:
        return None
    return payload

