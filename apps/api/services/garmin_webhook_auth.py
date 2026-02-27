"""
Garmin Webhook Authentication Service (D4.1)

Provides the `verify_garmin_webhook` FastAPI dependency and a per-IP
rate limiter for all Garmin webhook endpoints.

Security model (mandatory layered compensating controls — no HMAC exists):
  Layer 1 — garmin-client-id header check (primary gate, fail-closed)
  Layer 2 — strict schema validation (handled in each route handler)
  Layer 3 — unknown userId skip-and-log (handled in each route handler)
  Layer 4 — per-IP rate limiting (WebhookRateLimiter below)
  Layer 5 — IP allowlisting (deferred: Garmin does not publish source IP ranges;
             documented gap, rely on layers 1-4)

VERIFIED: No HMAC/signing secret configuration exists in the Garmin developer
portal (docs/garmin-portal/ENDPOINT_CONFIGURATION.md). Auth must use
compensating controls.

See docs/PHASE2_GARMIN_INTEGRATION_AC.md §D4.1
"""

from __future__ import annotations

import hmac
import logging
import time
from collections import defaultdict
from typing import Dict, List

from fastapi import HTTPException, Request

from core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Layer 4: Per-IP rate limiter (sliding window, in-process)
# ---------------------------------------------------------------------------
# Garmin push webhooks arrive at predictable, bounded rates (one push per
# athlete per sync event). 120 requests per minute per IP is generous enough
# to handle a batch push burst without false positives.
#
# Limitation: in-process storage is not shared across multiple workers.
# For multi-worker deployments, Redis-backed rate limiting (via the global
# RateLimitMiddleware) is the primary defence. This limiter provides an
# additional in-process check specifically for webhook endpoints.

_WEBHOOK_RATE_LIMIT = 600   # max requests per window per IP
_WEBHOOK_RATE_WINDOW = 60   # sliding window in seconds


class WebhookRateLimiter:
    """
    Sliding window per-IP rate limiter.

    Thread safety: designed for single-threaded async FastAPI workers.
    For multi-process deployments, Redis-backed middleware in
    core/rate_limit.py provides the shared rate limiting layer.
    """

    def __init__(
        self,
        max_requests: int = _WEBHOOK_RATE_LIMIT,
        window_seconds: int = _WEBHOOK_RATE_WINDOW,
    ) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._log: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, ip: str) -> bool:
        """Return True if request is within limit, False if rate exceeded."""
        now = time.monotonic()
        cutoff = now - self._window
        # Prune expired timestamps
        self._log[ip] = [t for t in self._log[ip] if t > cutoff]
        if len(self._log[ip]) >= self._max:
            return False
        self._log[ip].append(now)
        return True


# Module-level rate limiter instance (shared across requests in one worker)
_rate_limiter = WebhookRateLimiter()


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

async def verify_garmin_webhook(request: Request) -> None:
    """
    FastAPI dependency — shared by all Garmin webhook routes.

    Implements Layer 1 (client ID header check) and Layer 4 (rate limiting).
    Layer 2 (schema validation) and Layer 3 (unknown userId) are handled
    per-route since they depend on the data type.

    Args:
        request: Incoming FastAPI request.

    Raises:
        HTTPException(401): Missing or incorrect `garmin-client-id` header.
        HTTPException(503): GARMIN_CLIENT_ID not configured in environment.
        HTTPException(429): Per-IP rate limit exceeded.
    """
    # Layer 4: rate limiting (before any other processing)
    # Prefer the true client IP when behind a reverse proxy.
    forwarded_for = request.headers.get("x-forwarded-for", "")
    client_ip = (
        forwarded_for.split(",")[0].strip()
        if forwarded_for
        else (request.client.host if request.client else "unknown")
    )
    if not _rate_limiter.is_allowed(client_ip):
        logger.warning(
            "Garmin webhook rate limit exceeded",
            extra={"client_ip": client_ip, "path": str(request.url.path)},
        )
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
        )

    # Layer 1: Garmin client ID header check (primary gate).
    # Accept both documented and observed variants.
    received_id = (
        request.headers.get("garmin-client-id")
        or request.headers.get("x-garmin-client-id")
    )

    if not received_id:
        logger.warning(
            "Garmin webhook: missing garmin-client-id header",
            extra={"client_ip": client_ip},
        )
        raise HTTPException(
            status_code=401,
            detail="Missing garmin-client-id header",
        )

    expected_id = settings.GARMIN_CLIENT_ID
    if not expected_id:
        logger.error("Garmin webhook: GARMIN_CLIENT_ID not configured")
        raise HTTPException(
            status_code=503,
            detail="Garmin integration not configured",
        )

    # Timing-safe comparison — prevents timing attacks on the client ID
    if not hmac.compare_digest(received_id, expected_id):
        logger.warning(
            "Garmin webhook: invalid garmin-client-id header",
            extra={"client_ip": client_ip},
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid garmin-client-id header",
        )
