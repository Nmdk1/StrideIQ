"""
Onboarding ("Latency Bridge") router (Phase 3).

Purpose:
- Provide deterministic progress + bootstrap ingestion without long-running requests.
- Keep external provider sync queued and observable.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from core.auth import get_current_user
from models import Athlete


router = APIRouter(prefix="/v1/onboarding", tags=["onboarding"])


@router.get("/status")
def get_onboarding_status(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return Strava connection + ingestion status snapshot for the current user.
    """
    from services.ingestion_state import get_ingestion_state_snapshot

    snapshot = get_ingestion_state_snapshot(db, current_user.id, provider="strava")
    return {
        "strava_connected": bool(current_user.strava_access_token),
        "last_sync": current_user.last_strava_sync.isoformat() if current_user.last_strava_sync else None,
        "ingestion_state": snapshot.to_dict() if snapshot else None,
    }


@router.post("/bootstrap")
def bootstrap_ingestion(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Queue the minimal ingestion tasks that make the dashboard populate deterministically.

    - Index backfill is queued immediately (cheap, creates Activity rows quickly).
    - Full sync is queued (heavier, details/splits/pbs).
    """
    if not current_user.strava_access_token:
        raise HTTPException(status_code=400, detail="Strava not connected")

    from tasks.strava_tasks import backfill_strava_activity_index_task, sync_strava_activities_task
    from services.ingestion_state import get_ingestion_state_snapshot
    from datetime import datetime, timezone, timedelta

    # Best-effort idempotency: if an index backfill started recently, don't spam queue.
    snapshot = get_ingestion_state_snapshot(db, current_user.id, provider="strava")
    if snapshot and snapshot.last_index_started_at:
        try:
            started = snapshot.last_index_started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - started < timedelta(minutes=5) and snapshot.last_index_task_id:
                return {
                    "queued": False,
                    "index_task_id": snapshot.last_index_task_id,
                    "sync_task_id": None,
                    "message": "Index backfill already started recently",
                }
        except Exception:
            pass

    index_task = backfill_strava_activity_index_task.delay(str(current_user.id), pages=5)
    sync_task = sync_strava_activities_task.delay(str(current_user.id))
    return {
        "queued": True,
        "index_task_id": index_task.id,
        "sync_task_id": sync_task.id,
        "message": "Bootstrap ingestion queued",
    }

