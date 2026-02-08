"""
Celery tasks for best effort backfilling.

These tasks run in the background to populate the BestEffort table
from existing Strava activities.
"""
from typing import Dict
from celery import Task
from sqlalchemy.orm import Session
from core.database import get_db_sync
from tasks import celery_app
from models import Athlete
import traceback


@celery_app.task(name="tasks.backfill_best_efforts", bind=True)
def backfill_best_efforts_task(self: Task, athlete_id: str, limit: int = 100) -> Dict:
    """
    Background task to backfill best efforts for existing activities.
    
    This fetches activity details from Strava for activities that don't
    have best efforts stored yet, and extracts their best_efforts.
    
    Args:
        athlete_id: UUID string of the athlete
        limit: Max activities to process per run
        
    Returns:
        Dictionary with backfill results
    """
    from services.strava_pbs import sync_strava_best_efforts
    from services.ingestion_state import (
        mark_best_efforts_started,
        mark_best_efforts_finished,
        mark_best_efforts_error,
    )
    
    db: Session = get_db_sync()
    
    try:
        athlete = db.get(Athlete, athlete_id)
        if not athlete:
            return {"status": "error", "error": f"Athlete {athlete_id} not found"}
        
        if not athlete.strava_access_token:
            return {"status": "error", "error": "No Strava connection"}

        # Durable ops marker: record task start
        mark_best_efforts_started(db, athlete.id, "strava", task_id=str(self.request.id))
        db.commit()
        
        # Production behavior: do NOT sleep for long periods inside a worker.
        # If Strava rate limits, stop early and let the caller re-queue later.
        result = sync_strava_best_efforts(athlete, db, limit=limit, allow_rate_limit_sleep=False)
        mark_best_efforts_finished(db, athlete.id, "strava", result)
        db.commit()
        
        return {
            "status": "success",
            "athlete_id": athlete_id,
            "activities_checked": result.get('activities_checked', 0),
            "efforts_stored": result.get('efforts_stored', 0),
            "pbs_created": result.get('pbs_created', 0),
            "rate_limited": result.get("rate_limited", False),
            "retry_after_s": result.get("retry_after_s"),
        }
        
    except Exception as e:
        db.rollback()
        try:
            # Best-efforts ops marker: record error (best-effort; never break the task return)
            athlete = db.get(Athlete, athlete_id)
            if athlete:
                mark_best_efforts_error(db, athlete.id, "strava", error=str(e), task_id=str(self.request.id))
                db.commit()
        except Exception:
            db.rollback()
        traceback.print_exc()
        return {"status": "error", "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="tasks.regenerate_personal_bests", bind=True)
def regenerate_personal_bests_task(self: Task, athlete_id: str) -> Dict:
    """
    Background task to regenerate PersonalBest from BestEffort table.
    
    This is a fast aggregation - no external API calls.
    
    Args:
        athlete_id: UUID string of the athlete
        
    Returns:
        Dictionary with regeneration results
    """
    from services.best_effort_service import regenerate_personal_bests
    
    db: Session = get_db_sync()
    
    try:
        athlete = db.get(Athlete, athlete_id)
        if not athlete:
            return {"status": "error", "error": f"Athlete {athlete_id} not found"}
        
        result = regenerate_personal_bests(athlete, db)
        
        return {
            "status": "success",
            "athlete_id": athlete_id,
            "updated": result.get('updated', 0),
            "created": result.get('created', 0),
            "kept": result.get('kept', 0),
            "categories": result.get('categories', []),
        }
        
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        return {"status": "error", "error": str(e)}
    finally:
        db.close()
