"""
Audit Logger

Structured logging for user-impacting actions.
Used for debugging, compliance, and tracking changes.

Format: JSON structured logs with:
- timestamp
- athlete_id (anonymized hash)
- action_type
- before/after state (where applicable)
- metadata

ADR-033: Added for narrative translation layer audit trail.
"""

import logging
import json
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from uuid import UUID

# Configure structured logger
audit_logger = logging.getLogger("strideiq.audit")
audit_logger.setLevel(logging.INFO)

# Add handler if not already configured
if not audit_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    audit_logger.addHandler(handler)


def _anonymize_id(athlete_id: UUID) -> str:
    """Hash athlete ID for privacy in logs."""
    return hashlib.sha256(str(athlete_id).encode()).hexdigest()[:12]


def log_audit(
    action: str,
    athlete_id: UUID,
    success: bool = True,
    before_state: Optional[Dict[str, Any]] = None,
    after_state: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None
) -> None:
    """
    Log an audit event.
    
    Args:
        action: Action type (e.g., "narrative.hero_generated", "plan.created")
        athlete_id: Athlete UUID (will be anonymized)
        success: Whether the action succeeded
        before_state: State before action (optional)
        after_state: State after action (optional)
        metadata: Additional context
        error: Error message if failed
    """
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "athlete_hash": _anonymize_id(athlete_id),
        "success": success,
    }
    
    if before_state:
        event["before"] = before_state
    
    if after_state:
        event["after"] = after_state
    
    if metadata:
        event["metadata"] = metadata
    
    if error:
        event["error"] = error
    
    # Log as JSON for structured parsing
    audit_logger.info(json.dumps(event))


# =============================================================================
# NARRATIVE-SPECIFIC AUDIT FUNCTIONS
# =============================================================================

def log_narrative_generated(
    athlete_id: UUID,
    surface: str,
    signal_type: str,
    narrative_hash: str,
    anchors_used: int = 0,
    from_cache: bool = False
) -> None:
    """Log narrative generation event."""
    log_audit(
        action="narrative.generated",
        athlete_id=athlete_id,
        success=True,
        after_state={
            "surface": surface,  # home, activity, plan_preview, diagnostic
            "signal_type": signal_type,
            "hash": narrative_hash,
            "anchors_used": anchors_used,
            "from_cache": from_cache
        }
    )


def log_narrative_shown(
    athlete_id: UUID,
    surface: str,
    narrative_hash: str,
    was_fresh: bool
) -> None:
    """Log narrative display event."""
    log_audit(
        action="narrative.shown",
        athlete_id=athlete_id,
        success=True,
        metadata={
            "surface": surface,
            "hash": narrative_hash,
            "was_fresh": was_fresh
        }
    )


def log_narrative_skipped(
    athlete_id: UUID,
    surface: str,
    reason: str
) -> None:
    """Log when narrative was not shown."""
    log_audit(
        action="narrative.skipped",
        athlete_id=athlete_id,
        success=True,
        metadata={
            "surface": surface,
            "reason": reason
        }
    )


def log_narrative_error(
    athlete_id: UUID,
    surface: str,
    error: str
) -> None:
    """Log narrative generation failure."""
    log_audit(
        action="narrative.error",
        athlete_id=athlete_id,
        success=False,
        error=error,
        metadata={"surface": surface}
    )


# =============================================================================
# PLAN GENERATION AUDIT (for completeness)
# =============================================================================

def log_plan_generated(
    athlete_id: UUID,
    plan_type: str,
    race_distance: str,
    weeks: int,
    generation_method: str
) -> None:
    """Log plan generation event."""
    log_audit(
        action="plan.generated",
        athlete_id=athlete_id,
        success=True,
        after_state={
            "plan_type": plan_type,
            "race_distance": race_distance,
            "weeks": weeks,
            "generation_method": generation_method
        }
    )


def log_fitness_bank_calculated(
    athlete_id: UUID,
    constraint_type: str,
    experience_level: str,
    activities_analyzed: int
) -> None:
    """Log fitness bank calculation."""
    log_audit(
        action="fitness_bank.calculated",
        athlete_id=athlete_id,
        success=True,
        after_state={
            "constraint_type": constraint_type,
            "experience_level": experience_level,
            "activities_analyzed": activities_analyzed
        }
    )
