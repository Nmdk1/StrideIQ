"""
Strava Integration Router

Handles OAuth flow and activity syncing.
Updated to work with authenticated users.
"""
import traceback
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from core.database import get_db
from core.auth import get_current_user
from models import Athlete, Activity, ActivitySplit
from services.strava_service import (
    get_auth_url,
    exchange_code_for_token,
    poll_activities,
    get_activity_laps,
    get_activity_details,
)
from services.performance_engine import (
    calculate_age_at_date,
    calculate_age_graded_performance,
    detect_race_candidate,
)

router = APIRouter(prefix="/v1/strava", tags=["strava"])


def _coerce_int(x):
    try:
        if x is None:
            return None
        return int(round(float(x)))
    except Exception:
        return None


def _calculate_performance_metrics(
    activity: Activity,
    athlete: Athlete,
    db: Session
) -> None:
    """Calculate age-graded performance percentage and race detection for an activity."""
    if activity.pace_per_mile and activity.distance_m:
        age = calculate_age_at_date(athlete.birthdate, activity.start_time)
        
        performance_pct_intl = calculate_age_graded_performance(
            actual_pace_per_mile=activity.pace_per_mile,
            age=age,
            sex=athlete.sex,
            distance_meters=float(activity.distance_m),
            use_national=False
        )
        if performance_pct_intl:
            activity.performance_percentage = performance_pct_intl
        
        performance_pct_nat = calculate_age_graded_performance(
            actual_pace_per_mile=activity.pace_per_mile,
            age=age,
            sex=athlete.sex,
            distance_meters=float(activity.distance_m),
            use_national=True
        )
        if performance_pct_nat:
            activity.performance_percentage_national = performance_pct_nat
    
    if activity.user_verified_race is not True:
        splits = db.query(ActivitySplit).filter(
            ActivitySplit.activity_id == activity.id
        ).order_by(ActivitySplit.split_number).all()
        
        splits_data = []
        for split in splits:
            splits_data.append({
                'distance': float(split.distance) if split.distance else None,
                'moving_time': split.moving_time,
                'elapsed_time': split.elapsed_time,
                'average_heartrate': split.average_heartrate,
                'max_heartrate': split.max_heartrate,
                'avg_hr': split.average_heartrate,
            })
        
        is_race, confidence = detect_race_candidate(
            activity_pace=activity.pace_per_mile,
            max_hr=activity.max_hr,
            avg_hr=activity.avg_hr,
            splits=splits_data,
            distance_meters=float(activity.distance_m) if activity.distance_m else 0,
            duration_seconds=activity.duration_s
        )
        
        if confidence > 0:
            activity.is_race_candidate = is_race
            activity.race_confidence = confidence


@router.get("/status")
def get_strava_status(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get Strava connection status for current user.
    """
    is_connected = bool(current_user.strava_access_token)
    last_sync = current_user.last_strava_sync.isoformat() if current_user.last_strava_sync else None
    
    return {
        "connected": is_connected,
        "strava_athlete_id": current_user.strava_athlete_id,
        "last_sync": last_sync,
    }


@router.get("/auth-url")
def get_strava_auth_url(
    current_user: Athlete = Depends(get_current_user),
):
    """
    Get Strava OAuth authorization URL for current user.
    Returns URL that user should be redirected to.
    """
    try:
        auth_url = get_auth_url()
        return {"auth_url": auth_url}
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/callback")
def strava_callback(
    code: str = Query(..., description="Authorization code from Strava"),
    state: str = Query(None, description="Optional state parameter (athlete_id)"),
    db: Session = Depends(get_db),
):
    """
    Handle Strava OAuth callback.
    If state contains athlete_id, associate with that athlete.
    Otherwise, creates/finds by strava_athlete_id.
    """
    try:
        from services.token_encryption import encrypt_token
        
        token_data = exchange_code_for_token(code)
        
        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")
        athlete_info = token_data.get("athlete", {})
        strava_athlete_id = athlete_info.get("id")
        
        if not strava_athlete_id:
            raise HTTPException(status_code=400, detail="No athlete ID in Strava response")
        
        encrypted_access_token = encrypt_token(access_token)
        encrypted_refresh_token = encrypt_token(refresh_token) if refresh_token else None
        
        display_name = (athlete_info.get("firstname", "") + " " + athlete_info.get("lastname", "")).strip()
        
        # If state contains athlete_id, use that
        athlete = None
        if state:
            try:
                from uuid import UUID
                athlete_id = UUID(state)
                athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
            except:
                pass
        
        # Otherwise, find by strava_athlete_id
        if not athlete:
            athlete = (
                db.query(Athlete)
                .filter(Athlete.strava_athlete_id == strava_athlete_id)
                .first()
            )
        
        if not athlete:
            athlete = Athlete(
                strava_athlete_id=strava_athlete_id,
                display_name=display_name or None,
                strava_access_token=encrypted_access_token,
                strava_refresh_token=encrypted_refresh_token,
            )
            db.add(athlete)
        else:
            athlete.strava_access_token = encrypted_access_token
            if encrypted_refresh_token:
                athlete.strava_refresh_token = encrypted_refresh_token
            if display_name and not athlete.display_name:
                athlete.display_name = display_name
            athlete.strava_athlete_id = strava_athlete_id
        
        db.commit()
        db.refresh(athlete)
        
        return {
            "status": "success",
            "message": "Strava account connected successfully",
            "athlete_id": str(athlete.id),
            "strava_athlete_id": strava_athlete_id,
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error connecting Strava: {str(e)}")


@router.post("/sync")
def trigger_strava_sync(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Trigger a sync of activities from Strava for current user.
    Returns task ID for checking status.
    """
    if not current_user.strava_access_token:
        raise HTTPException(status_code=400, detail="Strava not connected")
    
    try:
        from tasks.strava_tasks import sync_strava_activities_task
        task = sync_strava_activities_task.delay(str(current_user.id))
        
        return {
            "status": "queued",
            "message": "Strava sync task queued",
            "task_id": task.id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error queuing sync: {str(e)}")


@router.get("/sync/status/{task_id}")
def get_sync_status(task_id: str):
    """Check the status of a Strava sync task."""
    from tasks import celery_app
    
    task = celery_app.AsyncResult(task_id)
    
    if task.state == "PENDING":
        return {
            "task_id": task_id,
            "status": "pending",
            "message": "Task is waiting to be processed"
        }
    elif task.state == "STARTED":
        return {
            "task_id": task_id,
            "status": "started",
            "message": "Task is currently being processed"
        }
    elif task.state == "SUCCESS":
        return {
            "task_id": task_id,
            "status": "success",
            "result": task.result
        }
    else:
        return {
            "task_id": task_id,
            "status": "error",
            "error": str(task.info) if task.info else "Unknown error"
        }


@router.post("/backfill-names")
def backfill_activity_names(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Backfill activity names from Strava for activities missing names.
    
    This fetches activity details from Strava API and updates the name field.
    Rate-limited to respect Strava's API limits.
    """
    import time
    
    if not current_user.strava_access_token:
        raise HTTPException(status_code=400, detail="Strava not connected")
    
    # Find activities missing names
    activities_missing_names = db.query(Activity).filter(
        Activity.athlete_id == current_user.id,
        Activity.provider == "strava",
        Activity.external_activity_id.isnot(None),
        Activity.name.is_(None)
    ).limit(100).all()  # Limit to 100 per call to avoid timeouts
    
    if not activities_missing_names:
        return {
            "status": "success",
            "message": "All activities already have names",
            "updated": 0,
            "remaining": 0
        }
    
    # Count total remaining
    total_remaining = db.query(func.count(Activity.id)).filter(
        Activity.athlete_id == current_user.id,
        Activity.provider == "strava",
        Activity.external_activity_id.isnot(None),
        Activity.name.is_(None)
    ).scalar()
    
    updated = 0
    errors = []
    
    for idx, activity in enumerate(activities_missing_names):
        try:
            # Rate limit: 1.5 second delay between requests
            if idx > 0:
                time.sleep(1.5)
            
            # Fetch activity details from Strava
            details = get_activity_details(current_user, int(activity.external_activity_id))
            
            if details and details.get("name"):
                activity.name = details.get("name")
                updated += 1
        except Exception as e:
            errors.append({
                "activity_id": str(activity.id),
                "error": str(e)
            })
    
    db.commit()
    
    return {
        "status": "success",
        "message": f"Updated {updated} activity names",
        "updated": updated,
        "remaining": total_remaining - updated,
        "errors": errors[:5] if errors else []  # Only return first 5 errors
    }
