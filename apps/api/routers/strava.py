"""
Strava Integration Router

Handles OAuth flow and activity syncing.
Updated to work with authenticated users.
"""
import traceback
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, text
import requests

from core.database import get_db
from core.auth import get_current_user
from core.config import settings
from models import Athlete, Activity, ActivitySplit
from services.strava_service import (
    get_auth_url,
    exchange_code_for_token,
    poll_activities,
    get_activity_laps,
    get_activity_details,
    StravaOAuthCapacityError,
)
from services.performance_engine import (
    calculate_age_at_date,
    calculate_age_graded_performance,
    detect_race_candidate,
)
from services.oauth_state import create_oauth_state, verify_oauth_state

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
    return_to: str = Query("/onboarding", description="UI path to return to after OAuth (must start with /)"),
    db: Session = Depends(get_db),
):
    """
    Get Strava OAuth authorization URL for current user.
    Returns URL that user should be redirected to.
    """
    try:
        # Prevent open redirect.
        if not return_to.startswith("/") or return_to.startswith("//"):
            raise HTTPException(status_code=400, detail="Invalid return_to")

        # Production-beta safety: if Strava app athlete capacity is reached, fail fast before redirect.
        # This is configurable so ops can set a conservative threshold.
        try:
            max_connected = int(getattr(settings, "STRAVA_MAX_CONNECTED_ATHLETES", None) or 0)
        except Exception:
            max_connected = 0
        if max_connected > 0:
            connected_count = (
                db.query(func.count(Athlete.id))
                .filter(Athlete.strava_access_token.isnot(None))
                .scalar()
                or 0
            )
            if int(connected_count) >= int(max_connected):
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Strava connect is temporarily unavailable (app capacity reached). "
                        "Use Garmin upload for now, or try again later."
                    ),
                )

        state = create_oauth_state(
            {
                "athlete_id": str(current_user.id),
                "return_to": return_to,
            }
        )
        auth_url = get_auth_url(state=state)
        return {"auth_url": auth_url}
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/callback")
def strava_callback(
    http_request: Request,  # FastAPI injects; keep name distinct from request payloads
    code: str = Query(..., description="Authorization code from Strava"),
    state: str = Query(None, description="Signed state token"),
    db: Session = Depends(get_db),
):
    """
    Handle Strava OAuth callback.

    Phase 3: MUST NOT create new athletes here.
    Callback only links Strava to an existing athlete identified by signed `state`.
    """
    try:
        from services.token_encryption import encrypt_token
        from tasks.strava_tasks import backfill_strava_activity_index_task
        
        payload = verify_oauth_state(state or "")
        if not payload or not payload.get("athlete_id"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid OAuth state")

        athlete = db.query(Athlete).filter(Athlete.id == payload["athlete_id"]).first()
        if not athlete:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid OAuth state")

        try:
            token_data = exchange_code_for_token(code)
        except StravaOAuthCapacityError:
            # Redirect back to UI with a user-safe error. Do not leak provider payloads.
            return_to = payload.get("return_to") or "/onboarding"
            if not isinstance(return_to, str) or not return_to.startswith("/") or return_to.startswith("//"):
                return_to = "/onboarding"
            sep = "&" if "?" in return_to else "?"
            # Mirror the LAN-safe redirect logic used by the success path.
            web_base = settings.WEB_APP_BASE_URL
            try:
                host = http_request.headers.get("x-forwarded-host") or http_request.headers.get("host") or ""
                proto = http_request.headers.get("x-forwarded-proto") or "http"
                env_is_local = ("localhost" in web_base) or ("127.0.0.1" in web_base)
                host_is_local = ("localhost" in host) or ("127.0.0.1" in host)
                if env_is_local and host and (not host_is_local):
                    if ":" in host:
                        host_only, port = host.rsplit(":", 1)
                        if port.isdigit() and int(port) == 8000:
                            host = f"{host_only}:3000"
                        else:
                            host = f"{host_only}:3000"
                    else:
                        host = f"{host}:3000"
                    web_base = f"{proto}://{host}"
            except Exception:
                web_base = settings.WEB_APP_BASE_URL
            redirect_url = f"{web_base}{return_to}{sep}strava=error&reason=capacity"
            return RedirectResponse(url=redirect_url, status_code=302)
        except requests.HTTPError:
            # Strava can return 403 for multiple OAuth-related reasons. Never 500 the user.
            return_to = payload.get("return_to") or "/onboarding"
            if not isinstance(return_to, str) or not return_to.startswith("/") or return_to.startswith("//"):
                return_to = "/onboarding"
            sep = "&" if "?" in return_to else "?"
            web_base = settings.WEB_APP_BASE_URL
            redirect_url = f"{web_base}{return_to}{sep}strava=error&reason=oauth"
            return RedirectResponse(url=redirect_url, status_code=302)
        
        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")
        athlete_info = token_data.get("athlete", {})
        strava_athlete_id = athlete_info.get("id")
        
        if not strava_athlete_id:
            raise HTTPException(status_code=400, detail="No athlete ID in Strava response")
        
        encrypted_access_token = encrypt_token(access_token)
        encrypted_refresh_token = encrypt_token(refresh_token) if refresh_token else None
        
        display_name = (athlete_info.get("firstname", "") + " " + athlete_info.get("lastname", "")).strip()
        
        athlete.strava_access_token = encrypted_access_token
        if encrypted_refresh_token:
            athlete.strava_refresh_token = encrypted_refresh_token
        if display_name and not athlete.display_name:
            athlete.display_name = display_name
        athlete.strava_athlete_id = strava_athlete_id
        
        db.commit()
        db.refresh(athlete)

        # Latency bridge: enqueue cheap index backfill immediately (background).
        try:
            from services.system_flags import is_ingestion_paused

            if not is_ingestion_paused(db):
                backfill_strava_activity_index_task.delay(str(athlete.id), pages=5)
        except Exception:
            # Best-effort enqueue; UI will still show "connected" and user can retry.
            pass

        return_to = payload.get("return_to") or "/onboarding"
        # Avoid open redirect (defense-in-depth).
        if not isinstance(return_to, str) or not return_to.startswith("/") or return_to.startswith("//"):
            return_to = "/onboarding"
        sep = "&" if "?" in return_to else "?"

        # Dev/LAN safety: if WEB_APP_BASE_URL is localhost but the request is coming
        # from a LAN host (e.g. phone hitting http://192.168.x.x:8000), redirecting
        # to localhost:3000 will break on the device and look like "connection failed".
        web_base = settings.WEB_APP_BASE_URL
        try:
            if http_request is not None:
                host = http_request.headers.get("x-forwarded-host") or http_request.headers.get("host") or ""
                proto = http_request.headers.get("x-forwarded-proto") or "http"
                env_is_local = ("localhost" in web_base) or ("127.0.0.1" in web_base)
                host_is_local = ("localhost" in host) or ("127.0.0.1" in host)
                if env_is_local and host and (not host_is_local):
                    # Map API host -> web host by forcing port 3000.
                    if ":" in host:
                        host_only, port = host.rsplit(":", 1)
                        if port.isdigit() and int(port) == 8000:
                            host = f"{host_only}:3000"
                        else:
                            host = f"{host_only}:3000"
                    else:
                        host = f"{host}:3000"
                    web_base = f"{proto}://{host}"
        except Exception:
            web_base = settings.WEB_APP_BASE_URL

        redirect_url = f"{web_base}{return_to}{sep}strava=connected"
        return RedirectResponse(url=redirect_url, status_code=302)
        
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
        from core.cache import get_redis_client
        import json
        
        task = sync_strava_activities_task.delay(str(current_user.id))
        
        # Track task in Redis so we can distinguish "unknown" from "pending"
        # TTL of 5 minutes - tasks should complete well before this
        redis = get_redis_client()
        if redis:
            task_meta = json.dumps({
                "athlete_id": str(current_user.id),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            redis.setex(f"strava_sync_task:{task.id}", 300, task_meta)
        
        return {
            "status": "queued",
            "message": "Strava sync task queued",
            "task_id": task.id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error queuing sync: {str(e)}")


@router.get("/sync/status/{task_id}")
def get_sync_status(task_id: str):
    """
    Check the status of a Strava sync task.
    
    Uses Redis to track known tasks. This solves the Celery quirk where
    AsyncResult returns PENDING for unknown task IDs (indistinguishable
    from genuinely queued tasks).
    """
    from tasks import celery_app
    from core.cache import get_redis_client
    
    task = celery_app.AsyncResult(task_id)
    redis = get_redis_client()
    
    # Check if we know about this task
    task_known = False
    if redis:
        task_meta = redis.get(f"strava_sync_task:{task_id}")
        task_known = task_meta is not None
    
    if task.state == "PENDING":
        # Celery returns PENDING for unknown tasks too
        # Only return "pending" if we actually know about this task
        if task_known:
            return {
                "task_id": task_id,
                "status": "pending",
                "message": "Task is waiting to be processed"
            }
        else:
            # Unknown task - tell frontend to stop polling
            return {
                "task_id": task_id,
                "status": "unknown",
                "message": "Task not found or expired"
            }
    elif task.state == "STARTED":
        return {
            "task_id": task_id,
            "status": "started",
            "message": "Task is currently being processed"
        }
    elif task.state == "SUCCESS":
        # Clean up Redis tracking (task completed)
        if redis:
            redis.delete(f"strava_sync_task:{task_id}")
        return {
            "task_id": task_id,
            "status": "success",
            "result": task.result
        }
    else:
        # Error or other state - clean up Redis
        if redis:
            redis.delete(f"strava_sync_task:{task_id}")
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
