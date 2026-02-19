"""
AI Processing Consent Endpoints

GET  /v1/consent/ai  — Returns the current consent status for the authenticated athlete.
POST /v1/consent/ai  — Grants or revokes AI processing consent.

Both endpoints require authentication. The source is recorded as "consent_prompt"
for explicit API calls (frontend consent prompt), or overridable via request body.
IP address and user agent are captured from the request for the audit log.
"""
from __future__ import annotations

import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from models import Athlete
from services.consent import grant_consent, revoke_consent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/consent", tags=["consent"])


class ConsentStatusResponse(BaseModel):
    ai_consent: bool
    granted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


class ConsentUpdateRequest(BaseModel):
    granted: bool
    source: Optional[str] = "consent_prompt"


class ConsentUpdateResponse(BaseModel):
    ai_consent: bool
    granted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


@router.get("/ai", response_model=ConsentStatusResponse)
def get_ai_consent_status(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConsentStatusResponse:
    """
    Return the AI processing consent status for the authenticated athlete.

    Frontend uses this on app load to decide whether to show the consent prompt
    and whether to render AI surfaces.
    """
    # Re-query to get the latest state (current_user may be from token, not fresh)
    fresh = db.query(Athlete).filter(Athlete.id == current_user.id).first()
    return ConsentStatusResponse(
        ai_consent=bool(fresh.ai_consent),
        granted_at=fresh.ai_consent_granted_at,
        revoked_at=fresh.ai_consent_revoked_at,
    )


@router.post("/ai", response_model=ConsentUpdateResponse)
def update_ai_consent(
    body: ConsentUpdateRequest,
    request: Request,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConsentUpdateResponse:
    """
    Grant or revoke AI processing consent for the authenticated athlete.

    Accepts { "granted": true/false, "source": "..." }.
    Always writes an audit log row. Idempotent on the consent field.
    Revocation takes effect immediately — no new AI requests will be dispatched.
    """
    ip_address = _get_client_ip(request)
    user_agent = request.headers.get("user-agent", "unknown")
    source = body.source or "consent_prompt"

    if body.granted:
        grant_consent(
            db=db,
            athlete_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            source=source,
        )
    else:
        revoke_consent(
            db=db,
            athlete_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            source=source,
        )

    # Return fresh state
    fresh = db.query(Athlete).filter(Athlete.id == current_user.id).first()
    return ConsentUpdateResponse(
        ai_consent=bool(fresh.ai_consent),
        granted_at=fresh.ai_consent_granted_at,
        revoked_at=fresh.ai_consent_revoked_at,
    )


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request headers (handles proxies)."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    if request.client:
        return request.client.host
    return "unknown"
