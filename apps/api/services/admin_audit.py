from __future__ import annotations

from typing import Any, Dict, Optional

import logging
from fastapi import Request
from sqlalchemy.orm import Session

from models import AdminAuditEvent, Athlete

logger = logging.getLogger(__name__)


def record_admin_audit_event(
    db: Session,
    *,
    request: Optional[Request],
    actor: Athlete,
    action: str,
    target_athlete_id: Optional[str] = None,
    reason: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Best-effort append-only audit logging for admin actions.

    Safety:
    - Never throws (does not block primary operation).
    - Payload must be bounded and must not contain secrets.
    """
    try:
        ip_address = None
        user_agent = None
        if request is not None:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")

        ev = AdminAuditEvent(
            actor_athlete_id=actor.id,
            action=action,
            target_athlete_id=target_athlete_id,
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent,
            payload=payload or {},
        )
        db.add(ev)
        db.flush()
    except Exception as e:
        # Never block admin operations on audit logging, but do emit a server log.
        logger.exception("Admin audit logging failed: %s", str(e))

