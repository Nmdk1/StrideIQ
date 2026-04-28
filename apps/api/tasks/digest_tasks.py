"""
Scheduled Digest Tasks

Weekly email digests with coached interpretation of correlation findings.
Runs via Celery Beat scheduler.

Architecture: eligible persisted findings are passed through an LLM coaching
prompt that translates to athlete language. If there are too few eligible
findings, or if generation fails validation, the digest is suppressed or falls
back to safe deterministic bullets. Raw correlation scans never go straight to
email.
"""

from typing import Dict, List
from celery import Task
from sqlalchemy.orm import Session
from core.database import get_db_sync
from tasks import celery_app
from models import Athlete
from services.correlation_persistence import get_surfaceable_findings, mark_surfaced
from services.email_service import email_service
from services.n1_insight_generator import friendly_signal_name
import logging

logger = logging.getLogger(__name__)

MIN_DIGEST_FINDINGS = 2
MAX_DIGEST_FINDINGS = 5


def _build_findings_context(correlations: List[dict]) -> str:
    """Render correlation findings as structured text for the LLM prompt."""
    lines: List[str] = []
    for c in correlations:
        raw = c.get("input_name", "unknown")
        friendly = friendly_signal_name(raw)
        coeff = c.get("correlation_coefficient", 0)
        direction = "positive" if coeff > 0 else "negative"
        strength = abs(coeff)
        sample = c.get("sample_size", 0)
        lines.append(
            f"- {friendly} (internal: {raw}): r={coeff:+.2f}, "
            f"direction={direction}, strength={strength:.0%}, "
            f"sample={sample} runs"
        )
    return "\n".join(lines) if lines else "(no significant correlations found)"


def _finding_to_digest_dict(finding) -> dict:
    """Convert a persisted eligible CorrelationFinding into digest input."""
    return {
        "id": str(finding.id),
        "input_name": finding.input_name,
        "output_metric": finding.output_metric,
        "direction": finding.direction,
        "correlation_coefficient": float(finding.correlation_coefficient or 0),
        "sample_size": int(finding.sample_size or 0),
        "times_confirmed": int(finding.times_confirmed or 0),
        "confidence": float(finding.confidence or 0),
        "category": finding.category,
    }


@celery_app.task(name="tasks.send_weekly_digest", bind=True)
def send_weekly_digest_task(self: Task, athlete_id: str) -> Dict:
    """
    Send weekly digest email to a single athlete.

    Fetches their top correlations, passes them through an LLM coaching
    filter, and sends the result as an email.
    """
    db: Session = get_db_sync()

    try:
        athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            return {"status": "error", "message": "Athlete not found"}

        if not athlete.email:
            return {"status": "skipped", "message": "No email address"}

        try:
            findings = get_surfaceable_findings(
                athlete_id=athlete.id,
                db=db,
                min_confirmations=3,
                limit=MAX_DIGEST_FINDINGS,
            )

            if len(findings) < MIN_DIGEST_FINDINGS:
                logger.info(
                    "Skipping weekly digest for %s: only %d eligible findings",
                    athlete.email,
                    len(findings),
                )
                return {"status": "skipped", "message": "Not enough eligible findings"}

            all_correlations = [_finding_to_digest_dict(f) for f in findings]
            findings_context = _build_findings_context(all_correlations)

            success = email_service.send_coached_digest(
                to_email=athlete.email,
                athlete_name=athlete.display_name,
                findings_context=findings_context,
                analysis_period_days=90,
                total_correlations=len(all_correlations),
                all_correlations=all_correlations,
            )

            if success:
                mark_surfaced([f.id for f in findings], db)
                db.commit()
                return {
                    "status": "success",
                    "athlete_id": str(athlete.id),
                    "email": athlete.email,
                    "correlations_analyzed": len(all_correlations),
                }
            else:
                return {"status": "error", "message": "Failed to send email"}

        except Exception as e:
            logger.error("Error generating digest for %s: %s", athlete.email, e)
            return {"status": "error", "message": str(e)}

    except Exception as e:
        logger.error("Error in send_weekly_digest_task: %s", e)
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="tasks.send_all_weekly_digests")
def send_all_weekly_digests_task() -> Dict:
    """
    Send weekly digests to all athletes who have email addresses.
    
    This task is called by Celery Beat on a schedule (e.g., every Monday).
    It enqueues individual digest tasks for each athlete.
    """
    db: Session = get_db_sync()
    
    try:
        # Get all athletes with email addresses
        athletes = db.query(Athlete).filter(
            Athlete.email.isnot(None),
            Athlete.email != ""
        ).all()
        
        logger.info(f"Sending weekly digests to {len(athletes)} athletes")
        
        results = []
        for athlete in athletes:
            # Enqueue individual digest task
            task_result = send_weekly_digest_task.delay(str(athlete.id))
            results.append({
                "athlete_id": str(athlete.id),
                "email": athlete.email,
                "task_id": task_result.id
            })
        
        return {
            "status": "success",
            "total_athletes": len(athletes),
            "tasks_enqueued": len(results),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error in send_all_weekly_digests_task: {str(e)}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


