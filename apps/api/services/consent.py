"""
AI Processing Consent Service

Provides the core consent operations:
- has_ai_consent(athlete_id, db) -> bool  [checked at every LLM call site]
- grant_consent(db, athlete_id, ...)
- revoke_consent(db, athlete_id, ...)

has_ai_consent checks BOTH the per-athlete flag AND the global kill switch
(ai_inference_enabled FeatureFlag). Either one being False blocks all AI.

Kill switch behavior: fail-open by design.
If the flag row does not exist, AI is enabled (default-on for consented users).
If the flag exists and enabled=False, AI is blocked for everyone.

Every grant/revoke writes to consent_audit_log, even if the action is
idempotent (already granted / already revoked). This ensures a complete
audit trail for compliance.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from models import Athlete, ConsentAuditLog, FeatureFlag

logger = logging.getLogger(__name__)

AI_INFERENCE_FLAG_KEY = "ai_inference_enabled"
CONSENT_TYPE_AI = "ai_processing"


def has_ai_consent(athlete_id: UUID, db: Session) -> bool:
    """
    Return True only when BOTH conditions hold:
      1. The athlete has explicitly granted AI processing consent.
      2. The global ai_inference_enabled kill switch is not disabled.

    Called at every LLM dispatch point. Must be fast — single-row queries only.
    Fail-open for missing kill switch (flag absent → AI is on).
    """
    # Check global kill switch first (cheap, shared across all athletes)
    try:
        flag = db.query(FeatureFlag).filter(FeatureFlag.key == AI_INFERENCE_FLAG_KEY).first()
        if flag is not None and not flag.enabled:
            logger.info("AI inference blocked: kill switch ai_inference_enabled=False")
            return False
    except Exception as e:
        logger.warning(f"Could not read ai_inference_enabled flag: {e} — allowing through")
        # Fail-open: if we can't read the flag, don't block the user

    # Check per-athlete consent
    try:
        athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if athlete is None:
            logger.warning(f"has_ai_consent: athlete {athlete_id} not found — returning False")
            return False
        return bool(athlete.ai_consent)
    except Exception as e:
        logger.warning(f"Could not read ai_consent for athlete {athlete_id}: {e} — returning False")
        return False


def grant_consent(
    db: Session,
    athlete_id: UUID,
    ip_address: str,
    user_agent: str,
    source: str,
) -> None:
    """
    Grant AI processing consent for an athlete.

    Sets ai_consent=True, ai_consent_granted_at=now(), clears ai_consent_revoked_at.
    Always writes an audit log row (even if already granted — idempotent field, logged action).
    """
    now = datetime.now(timezone.utc)

    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if athlete is None:
        raise ValueError(f"Athlete {athlete_id} not found")

    athlete.ai_consent = True
    athlete.ai_consent_granted_at = now
    athlete.ai_consent_revoked_at = None

    _write_audit_log(
        db=db,
        athlete_id=athlete_id,
        action="granted",
        ip_address=ip_address,
        user_agent=user_agent,
        source=source,
    )
    db.commit()
    logger.info(f"AI consent granted: athlete={athlete_id} source={source}")


def revoke_consent(
    db: Session,
    athlete_id: UUID,
    ip_address: str,
    user_agent: str,
    source: str,
) -> None:
    """
    Revoke AI processing consent for an athlete.

    Sets ai_consent=False, ai_consent_revoked_at=now(), preserves ai_consent_granted_at.
    Always writes an audit log row (even if already revoked — idempotent field, logged action).
    Revocation takes effect immediately — no new AI requests will be made for this athlete.
    """
    now = datetime.now(timezone.utc)

    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if athlete is None:
        raise ValueError(f"Athlete {athlete_id} not found")

    athlete.ai_consent = False
    athlete.ai_consent_revoked_at = now
    # Preserve granted_at — useful for audit / re-consent UX

    _write_audit_log(
        db=db,
        athlete_id=athlete_id,
        action="revoked",
        ip_address=ip_address,
        user_agent=user_agent,
        source=source,
    )
    db.commit()
    logger.info(f"AI consent revoked: athlete={athlete_id} source={source}")


def _write_audit_log(
    db: Session,
    athlete_id: UUID,
    action: str,
    ip_address: str,
    user_agent: str,
    source: str,
) -> None:
    """Write one row to consent_audit_log. Called by grant_consent and revoke_consent."""
    log = ConsentAuditLog(
        athlete_id=athlete_id,
        consent_type=CONSENT_TYPE_AI,
        action=action,
        ip_address=ip_address,
        user_agent=user_agent,
        source=source,
    )
    db.add(log)
