"""
Scheduled Digest Tasks

Weekly email digests with top correlations and insights.
Runs via Celery Beat scheduler.
"""

from datetime import datetime, timedelta
from typing import Dict, List
from celery import Task
from sqlalchemy.orm import Session
from core.database import get_db_sync
from tasks import celery_app
from models import Athlete
from services.correlation_engine import analyze_correlations
from services.email_service import email_service
import logging

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.send_weekly_digest", bind=True)
def send_weekly_digest_task(self: Task, athlete_id: str) -> Dict:
    """
    Send weekly digest email to a single athlete.
    
    Fetches their top correlations and sends formatted email.
    """
    db: Session = next(get_db_sync())
    
    try:
        athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            return {"status": "error", "message": "Athlete not found"}
        
        if not athlete.email:
            return {"status": "skipped", "message": "No email address"}
        
        # Get correlations for last 90 days
        try:
            correlation_result = analyze_correlations(
                athlete_id=str(athlete.id),
                days=90,
                db=db
            )
            
            if "error" in correlation_result:
                logger.info(f"Skipping digest for {athlete.email}: {correlation_result['error']}")
                return {"status": "skipped", "message": correlation_result["error"]}
            
            # Filter correlations
            what_works = [
                c for c in correlation_result.get("correlations", [])
                if c.get("direction") == "negative"  # Negative correlation = better efficiency
            ]
            what_doesnt_work = [
                c for c in correlation_result.get("correlations", [])
                if c.get("direction") == "positive"  # Positive correlation = worse efficiency
            ]
            
            # Sort by correlation strength
            what_works.sort(key=lambda x: abs(x.get("correlation_coefficient", 0)), reverse=True)
            what_doesnt_work.sort(key=lambda x: abs(x.get("correlation_coefficient", 0)), reverse=True)
            
            # Send email
            success = email_service.send_digest(
                to_email=athlete.email,
                athlete_name=athlete.display_name,
                what_works=what_works,
                what_doesnt_work=what_doesnt_work,
                analysis_period_days=90
            )
            
            if success:
                return {
                    "status": "success",
                    "athlete_id": str(athlete.id),
                    "email": athlete.email,
                    "what_works_count": len(what_works),
                    "what_doesnt_work_count": len(what_doesnt_work)
                }
            else:
                return {"status": "error", "message": "Failed to send email"}
                
        except Exception as e:
            logger.error(f"Error generating correlations for {athlete.email}: {str(e)}")
            return {"status": "error", "message": str(e)}
            
    except Exception as e:
        logger.error(f"Error in send_weekly_digest_task: {str(e)}")
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
    db: Session = next(get_db_sync())
    
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


