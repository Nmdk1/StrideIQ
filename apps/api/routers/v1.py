from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel

from core.database import get_db
from core.auth import get_current_user, require_admin
from models import Athlete, Activity, DailyCheckin, ActivitySplit, AthleteTrainingPaceProfile, AthleteRaceResultAnchor
from schemas import (
    AthleteCreate,
    AthleteUpdate,
    AthleteResponse,
    ActivityCreate,
    ActivityResponse,
    DailyCheckinCreate,
    DailyCheckinResponse,
    ActivitySplitResponse,
    PersonalBestResponse,
)

router = APIRouter(prefix="/v1", tags=["v1"])


@router.get("/athletes", response_model=List[AthleteResponse])
def get_athletes(
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get all athletes (admin only)."""
    athletes = db.query(Athlete).all()
    result = []
    from services.performance_engine import calculate_age_at_date, get_age_category
    from datetime import datetime
    
    for athlete in athletes:
        age_category = None
        if athlete.birthdate:
            age = calculate_age_at_date(athlete.birthdate, datetime.now())
            if age:
                age_category = get_age_category(age)
        
        athlete_dict = {
            "id": athlete.id,
            "created_at": athlete.created_at,
            "email": athlete.email,
            "display_name": athlete.display_name,
            "birthdate": athlete.birthdate,
            "sex": athlete.sex,
            "subscription_tier": athlete.subscription_tier,
            "age_category": age_category,
            "durability_index": athlete.durability_index,
            "recovery_half_life_hours": athlete.recovery_half_life_hours,
            "consistency_index": athlete.consistency_index,
            "strava_athlete_id": athlete.strava_athlete_id,  # Add for frontend filtering
        }
        result.append(AthleteResponse(**athlete_dict))
    
    return result


@router.post("/athletes", response_model=AthleteResponse, status_code=201)
def create_athlete(
    athlete: AthleteCreate,
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new athlete (admin only)."""
    db_athlete = Athlete(**athlete.dict())
    db.add(db_athlete)
    db.commit()
    db.refresh(db_athlete)
    return db_athlete


@router.get("/athletes/me", response_model=AthleteResponse)
def get_current_athlete_profile(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the current authenticated athlete's profile.
    
    This is the primary way athletes access their own data.
    """
    from services.performance_engine import calculate_age_at_date, get_age_category
    from datetime import datetime
    
    age_category = None
    if current_user.birthdate:
        age = calculate_age_at_date(current_user.birthdate, datetime.now())
        if age:
            age_category = get_age_category(age)
    
    athlete_dict = {
        "id": current_user.id,
        "created_at": current_user.created_at,
        "email": current_user.email,
        "display_name": current_user.display_name,
        "birthdate": current_user.birthdate,
        "sex": current_user.sex,
        "subscription_tier": current_user.subscription_tier,
        "age_category": age_category,
        "durability_index": current_user.durability_index,
        "recovery_half_life_hours": current_user.recovery_half_life_hours,
        "consistency_index": current_user.consistency_index,
        "strava_athlete_id": current_user.strava_athlete_id,
    }
    
    return AthleteResponse(**athlete_dict)


@router.get("/athletes/{id}", response_model=AthleteResponse)
def get_athlete(
    id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get an athlete by ID with Performance Physics Engine metrics (auth + ownership or admin)."""
    if current_user.id != id and getattr(current_user, "role", "athlete") not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Forbidden")
    from services.performance_engine import calculate_age_at_date, get_age_category
    from datetime import datetime
    
    athlete = db.query(Athlete).filter(Athlete.id == id).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    
    # Calculate age category if birthdate is available
    age_category = None
    if athlete.birthdate:
        age = calculate_age_at_date(athlete.birthdate, datetime.now())
        if age:
            age_category = get_age_category(age)
    
    # Convert to response dict to include computed age_category
    athlete_dict = {
        "id": athlete.id,
        "created_at": athlete.created_at,
        "email": athlete.email,
        "display_name": athlete.display_name,
        "birthdate": athlete.birthdate,
        "sex": athlete.sex,
        "subscription_tier": athlete.subscription_tier,
        "age_category": age_category,
        "durability_index": athlete.durability_index,
        "recovery_half_life_hours": athlete.recovery_half_life_hours,
        "consistency_index": athlete.consistency_index,
    }
    
    return AthleteResponse(**athlete_dict)


@router.put("/athletes/me", response_model=AthleteResponse)
def update_current_athlete(
    athlete_update: AthleteUpdate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update current athlete's profile.
    
    Athletes can update their own profile information.
    """
    # Track onboarding completion transition for auto-provisioning.
    was_completed = bool(getattr(current_user, "onboarding_completed", False))

    # Update fields if provided
    if athlete_update.display_name is not None:
        current_user.display_name = athlete_update.display_name
    if athlete_update.birthdate is not None:
        current_user.birthdate = athlete_update.birthdate
    if athlete_update.sex is not None:
        current_user.sex = athlete_update.sex
    if athlete_update.height_cm is not None:
        current_user.height_cm = athlete_update.height_cm
    if athlete_update.email is not None:
        # Security: Email changes require verification (see H6 in Security Audit)
        # Don't change email directly - initiate verification flow instead
        new_email = athlete_update.email.lower().strip()
        
        # Skip if email is the same
        if new_email != current_user.email:
            # Check if email is already taken by another user
            existing = db.query(Athlete).filter(
                Athlete.email == new_email,
                Athlete.id != current_user.id
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already in use"
                )
            
            # Generate verification token and send email
            from services.email_verification import initiate_email_change
            verification_sent = initiate_email_change(
                db=db,
                athlete=current_user,
                new_email=new_email
            )
            
            if verification_sent:
                # Return a message that verification is required
                # The email will NOT be changed until verified
                raise HTTPException(
                    status_code=status.HTTP_202_ACCEPTED,
                    detail=f"Verification email sent to {new_email}. Please click the link to confirm your email change."
                )
    if athlete_update.onboarding_stage is not None:
        current_user.onboarding_stage = athlete_update.onboarding_stage
    if athlete_update.onboarding_completed is not None:
        current_user.onboarding_completed = athlete_update.onboarding_completed
    
    db.commit()
    db.refresh(current_user)

    # Trust fix: once onboarding is marked complete, ensure the athlete immediately has
    # a starter plan (so the calendar isn't empty even before visiting /calendar).
    try:
        now_completed = bool(getattr(current_user, "onboarding_completed", False))
        if (not was_completed) and now_completed:
            enabled = True
            try:
                from services.plan_framework.feature_flags import FeatureFlagService

                svc = FeatureFlagService(db)
                flag = svc.get_flag("onboarding.auto_starter_plan_v1")
                enabled = True if not flag else svc.is_enabled("onboarding.auto_starter_plan_v1", current_user.id)
            except Exception:
                enabled = True

            if enabled:
                from services.starter_plan import ensure_starter_plan

                ensure_starter_plan(db, athlete=current_user)
                # If plan creation succeeded, it will have committed. If not, it's best-effort.
    except Exception:
        # Do not block profile updates; calendar still has lazy provisioning as fallback.
        pass
    
    # Calculate age category if birthdate updated
    from services.performance_engine import calculate_age_at_date, get_age_category
    from datetime import datetime
    
    age_category = None
    if current_user.birthdate:
        age = calculate_age_at_date(current_user.birthdate, datetime.now())
        if age:
            age_category = get_age_category(age)
    
    # Convert to response dict
    athlete_dict = {
        "id": current_user.id,
        "created_at": current_user.created_at,
        "email": current_user.email,
        "display_name": current_user.display_name,
        "birthdate": current_user.birthdate,
        "sex": current_user.sex,
        "height_cm": float(current_user.height_cm) if current_user.height_cm else None,
        "subscription_tier": current_user.subscription_tier,
        "onboarding_stage": current_user.onboarding_stage,
        "onboarding_completed": current_user.onboarding_completed,
        "age_category": age_category,
        "durability_index": current_user.durability_index,
        "recovery_half_life_hours": current_user.recovery_half_life_hours,
        "consistency_index": current_user.consistency_index,
    }
    
    return AthleteResponse(**athlete_dict)


class TrainingPaceProfileResponse(BaseModel):
    status: str  # computed | missing
    pace_profile: Optional[dict] = None
    updated_at: Optional[datetime] = None


@router.get("/athletes/me/training-pace-profile", response_model=TrainingPaceProfileResponse)
def get_my_training_pace_profile(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return the athlete's current Training Pace Profile (if present).

    Trust contract:
    - This profile is computed from a race/time-trial anchor (not inferred from training).
    - Stored separately from Athlete.rpi/threshold fields to avoid unintended plan changes.
    """
    prof = db.query(AthleteTrainingPaceProfile).filter(AthleteTrainingPaceProfile.athlete_id == current_user.id).first()
    if not prof:
        return TrainingPaceProfileResponse(status="missing", pace_profile=None, updated_at=None)
    return TrainingPaceProfileResponse(
        status="computed",
        pace_profile=prof.paces,
        updated_at=prof.updated_at,
    )


def format_pace(pace_per_mile: Optional[float]) -> Optional[str]:
    """Format pace as MM:SS/mi"""
    if pace_per_mile is None:
        return None
    
    minutes = int(pace_per_mile)
    seconds = int(round((pace_per_mile - minutes) * 60))
    return f"{minutes}:{seconds:02d}/mi"


def format_duration(seconds: Optional[int]) -> Optional[str]:
    """Format duration as HH:MM:SS or MM:SS"""
    if seconds is None or seconds <= 0:
        return None
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


# NOTE: GET /activities endpoint moved to routers/activities.py
# That endpoint has proper authentication, filtering, and uses actual activity names
# This duplicate was removed to avoid route conflicts


@router.post("/activities", response_model=ActivityResponse, status_code=201)
def create_activity(
    activity: ActivityCreate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new activity (auth required; athlete_id from auth context only)."""
    data = activity.model_dump() if hasattr(activity, "model_dump") else activity.dict()
    data.pop("athlete_id", None)
    db_activity = Activity(athlete_id=current_user.id, **data)
    db.add(db_activity)
    db.commit()
    db.refresh(db_activity)
    activity_name = db_activity.name or f"{db_activity.sport.title()} Activity"
    activity_dict = {
        "id": str(db_activity.id),
        "strava_id": None,
        "name": activity_name,
        "distance": float(db_activity.distance_m) if db_activity.distance_m else 0.0,
        "moving_time": db_activity.duration_s or 0,
        "start_date": db_activity.start_time.isoformat(),
        "average_speed": float(db_activity.average_speed) if db_activity.average_speed else 0.0,
        "max_hr": db_activity.max_hr,
        "average_heartrate": db_activity.avg_hr,
        "average_cadence": None,
        "total_elevation_gain": float(db_activity.total_elevation_gain) if db_activity.total_elevation_gain else None,
        "pace_per_mile": None,
        "duration_formatted": None,
        "splits": None,
        "performance_percentage": db_activity.performance_percentage,
        "performance_percentage_national": db_activity.performance_percentage_national,
        "is_race_candidate": db_activity.is_race_candidate,
        "race_confidence": db_activity.race_confidence,
    }
    if db_activity.average_speed and float(db_activity.average_speed) > 0:
        pace_per_mile = 26.8224 / float(db_activity.average_speed)
        minutes = int(pace_per_mile)
        seconds = int(round((pace_per_mile - minutes) * 60))
        activity_dict["pace_per_mile"] = f"{minutes}:{seconds:02d}/mi"
    if db_activity.duration_s:
        h, m, s = db_activity.duration_s // 3600, (db_activity.duration_s % 3600) // 60, db_activity.duration_s % 60
        activity_dict["duration_formatted"] = f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m}:{s:02d}"
    return ActivityResponse(**activity_dict)


@router.get("/activities/{activity_id}/splits", response_model=List[ActivitySplitResponse])
def get_activity_splits(
    activity_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get splits for a specific activity (auth + ownership enforced)."""
    # Verify activity exists AND belongs to the authenticated user
    activity = (
        db.query(Activity)
        .filter(Activity.id == activity_id, Activity.athlete_id == current_user.id)
        .first()
    )
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    splits = db.query(ActivitySplit).filter(
        ActivitySplit.activity_id == activity_id
    ).order_by(ActivitySplit.split_number).all()
    
    return splits


@router.post("/athletes/{id}/calculate-metrics")
def calculate_athlete_metrics(
    id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Calculate Performance Physics Engine derived signals for an athlete.
    This implements Manifesto Section 4: Derived Signals.
    """
    if current_user.id != id and getattr(current_user, "role", "athlete") not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Forbidden")
    from services.athlete_metrics import calculate_athlete_derived_signals
    
    athlete = db.query(Athlete).filter(Athlete.id == id).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    
    metrics = calculate_athlete_derived_signals(athlete, db, force_recalculate=True)
    
    return {
        "status": "success",
        "athlete_id": str(athlete.id),
        "metrics": metrics,
        "calculated_at": athlete.last_metrics_calculation.isoformat() if athlete.last_metrics_calculation else None,
    }


@router.get("/athletes/{id}/personal-bests", response_model=List[PersonalBestResponse])
def get_personal_bests_endpoint(
    id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all personal bests for an athlete (auth + ownership or admin)."""
    if current_user.id != id and getattr(current_user, "role", "athlete") not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Forbidden")
    from services.personal_best import get_personal_bests as get_pbs_service
    
    athlete = db.query(Athlete).filter(Athlete.id == id).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    
    pbs = get_pbs_service(str(athlete.id), db)
    return pbs


@router.post("/athletes/{id}/recalculate-pbs")
def recalculate_pbs_endpoint(
    id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Recalculate personal bests from ALL sources (activities + BestEffort).
    
    Two-step process:
    1. Scan all activities for whole-distance PBs (covers Garmin, manual imports, etc.)
    2. Merge with Strava BestEffort data (sub-activity segments like fastest mile within a 10K)
    
    The fastest time per distance wins, regardless of source.
    """
    if current_user.id != id and getattr(current_user, "role", "athlete") not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Forbidden")
    from services.personal_best import recalculate_all_pbs
    from services.best_effort_service import regenerate_personal_bests
    from models import BestEffort

    athlete = db.query(Athlete).filter(Athlete.id == id).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")

    # Step 1: Rebuild PBs from ALL activities (Garmin, Strava, manual, etc.)
    activity_result = recalculate_all_pbs(athlete, db, preserve_strava_pbs=False)

    # Step 2: Merge in Strava BestEffort data (keeps whichever is faster)
    effort_count = db.query(BestEffort).filter(BestEffort.athlete_id == athlete.id).count()
    merge_result = regenerate_personal_bests(athlete, db)

    return {
        "status": "success",
        "athlete_id": str(athlete.id),
        "activity_pbs": activity_result.get('created', 0) + activity_result.get('updated', 0),
        "efforts_in_db": effort_count,
        "merged_from_efforts": merge_result.get('created', 0) + merge_result.get('updated', 0),
        "kept_existing": merge_result.get('kept', 0),
        "categories": merge_result.get('categories', []),
        "message": (
            f"Rebuilt {activity_result.get('total', 0)} PBs from activities, "
            f"merged {merge_result.get('created', 0) + merge_result.get('updated', 0)} from {effort_count} Strava efforts, "
            f"kept {merge_result.get('kept', 0)} existing (faster)"
        ),
    }


@router.post("/athletes/{id}/sync-best-efforts")
def sync_best_efforts_endpoint(
    id: UUID,
    limit: int = 50,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Sync best efforts from Strava API into the BestEffort table.
    
    This fetches activity details from Strava - can take 30-60 seconds.
    After syncing, PersonalBest is regenerated from the stored efforts.
    
    Best efforts are also synced automatically during regular Strava sync.
    """
    if current_user.id != id and getattr(current_user, "role", "athlete") not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Forbidden")
    from services.strava_pbs import sync_strava_best_efforts

    athlete = db.query(Athlete).filter(Athlete.id == id).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")

    if not athlete.strava_access_token:
        raise HTTPException(status_code=400, detail="No Strava connection")

    # NOTE: This endpoint is retained for backwards compatibility, but should not
    # sleep for long periods inside an HTTP request. If Strava rate limits, it will
    # return partial progress and the caller should retry or use the queued endpoint.
    try:
        result = sync_strava_best_efforts(athlete, db, limit=limit, allow_rate_limit_sleep=False)
        db.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")

    return {
        "status": "success",
        "athlete_id": str(athlete.id),
        "activities_checked": result.get('activities_checked', 0),
        "efforts_stored": result.get('efforts_stored', 0),
        "pbs_created": result.get('pbs_created', 0),
        "message": f"Checked {result.get('activities_checked', 0)} activities, stored {result.get('efforts_stored', 0)} efforts"
    }


@router.post("/athletes/{id}/sync-best-efforts/queue")
def queue_best_efforts_backfill(
    id: UUID,
    limit: int = 200,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Queue best-effort backfill in the background (recommended).

    This avoids long-running HTTP requests and respects Strava rate limits naturally
    via the worker process.
    """
    if current_user.id != id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    athlete = db.query(Athlete).filter(Athlete.id == id).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    if not athlete.strava_access_token:
        raise HTTPException(status_code=400, detail="No Strava connection")

    from tasks.best_effort_tasks import backfill_best_efforts_task

    task = backfill_best_efforts_task.delay(str(athlete.id), limit=limit)
    return {
        "status": "queued",
        "athlete_id": str(athlete.id),
        "task_id": task.id,
        "message": "Best-effort backfill queued",
    }


@router.get("/athletes/{id}/best-efforts/status")
def get_best_efforts_status(
    id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get ingestion completeness for best-efforts (no external calls).
    """
    if current_user.id != id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    from services.ingestion_status import get_best_effort_ingestion_status
    from services.ingestion_state import get_ingestion_state_snapshot

    try:
        status_obj = get_best_effort_ingestion_status(id, db, provider="strava")
    except ValueError:
        raise HTTPException(status_code=404, detail="Athlete not found")
    snapshot = get_ingestion_state_snapshot(db, id, provider="strava")
    return {
        "status": "success",
        "best_efforts": status_obj.to_dict(),
        "ingestion_state": snapshot.to_dict() if snapshot else None,
    }


@router.get("/tasks/{task_id}")
def get_task_status(task_id: str, current_user: Athlete = Depends(get_current_user)):
    """
    Generic Celery task status endpoint (used by web polling).

    Security: result payload is redacted to prevent cross-user data leakage.
    The frontend only needs status; detailed results are fetched via
    athlete-scoped endpoints after task completion.
    """
    from tasks import celery_app

    task = celery_app.AsyncResult(task_id)
    if task.state == "PENDING":
        return {"task_id": task_id, "status": "pending"}
    if task.state == "STARTED":
        return {"task_id": task_id, "status": "started"}
    if task.state == "SUCCESS":
        return {"task_id": task_id, "status": "success"}
    return {"task_id": task_id, "status": "error"}


@router.post("/athletes/{id}/strava/ingest-activity/{strava_activity_id}")
def ingest_single_strava_activity(
    id: UUID,
    strava_activity_id: int,
    mark_as_race: Optional[bool] = None,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Ingest a single Strava activity by Strava ID (authoritative link).

    Use this when an activity is missing locally but Strava shows best-efforts for it.
    """
    if current_user.id != id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    athlete = db.query(Athlete).filter(Athlete.id == id).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    if not athlete.strava_access_token:
        raise HTTPException(status_code=400, detail="No Strava connection")

    from services.strava_ingest import ingest_strava_activity_by_id

    try:
        res = ingest_strava_activity_by_id(athlete, db, int(strava_activity_id), mark_as_race=mark_as_race)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "success", "athlete_id": str(athlete.id), "result": res.to_dict()}


@router.post("/athletes/{id}/strava/backfill-index/queue")
def queue_strava_activity_index_backfill(
    id: UUID,
    pages: int = 5,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Queue a Strava activity index backfill (paged /athlete/activities).

    This creates missing Activity rows without per-activity detail calls.
    """
    if current_user.id != id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    athlete = db.query(Athlete).filter(Athlete.id == id).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    if not athlete.strava_access_token:
        raise HTTPException(status_code=400, detail="No Strava connection")

    from tasks.strava_tasks import backfill_strava_activity_index_task

    task = backfill_strava_activity_index_task.delay(str(athlete.id), pages=int(pages))
    return {"status": "queued", "athlete_id": str(athlete.id), "task_id": task.id}


@router.post("/activities/{activity_id}/mark-race")
def mark_activity_as_race(
    activity_id: UUID,
    is_race: bool = True,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually mark/unmark an activity as a race.
    This allows users to override the automatic race detection.
    """
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    # SECURITY: Only allow users to modify their own activities
    if activity.athlete_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot modify another user's activity")
    
    activity.user_verified_race = is_race
    activity.is_race_candidate = is_race  # Also update the candidate flag
    
    # If marking as race, set confidence to 1.0 (user verified)
    if is_race:
        activity.race_confidence = 1.0
    
    db.commit()
    
    return {
        "status": "success",
        "activity_id": str(activity_id),
        "is_race": is_race,
        "message": f"Activity marked as {'race' if is_race else 'not a race'}"
    }


@router.post("/activities/{activity_id}/backfill-splits")
def backfill_activity_splits(
    activity_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Backfill splits for an activity that is missing them.
    Fetches lap data from Strava API and creates split records.
    """
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    # SECURITY: Only allow users to backfill their own activities
    if activity.athlete_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot modify another user's activity")
    
    if not activity.provider == "strava" or not activity.external_activity_id:
        raise HTTPException(status_code=400, detail="Activity is not from Strava or missing external ID")
    
    # Use the authenticated user's Strava token
    if not current_user.strava_access_token:
        raise HTTPException(status_code=400, detail="Missing Strava token")
    
    from services.strava_service import get_activity_laps, get_activity_details
    from routers.strava import _coerce_int
    from services.pace_normalization import calculate_ngp_from_split
    
    try:
        def _gap_seconds_per_mile_from_lap(lap: dict) -> tuple[Optional[float], bool]:
            """
            Prefer Strava's grade-adjusted speed if available; otherwise fallback
            to our NGP approximation using elevation gain.
            """
            try:
                ga_speed = (
                    lap.get("average_grade_adjusted_speed")
                    or lap.get("avg_grade_adjusted_speed")
                    or lap.get("grade_adjusted_speed")
                )
                if ga_speed is not None:
                    ga = float(ga_speed)
                    if ga > 0:
                        return (1609.34 / ga, True)
            except Exception:
                pass

            try:
                distance_m = lap.get("distance")
                moving_time_s = lap.get("moving_time")
                elevation_gain_m = lap.get("total_elevation_gain")
                if distance_m and moving_time_s:
                    return (
                        calculate_ngp_from_split(
                        distance_m=float(distance_m),
                        moving_time_s=int(moving_time_s),
                        elevation_gain_m=elevation_gain_m,
                    )
                        , False
                    )
            except Exception:
                return (None, False)
            return (None, False)

        def _extract_strava_mile_splits_from_details(details: dict) -> list[dict]:
            splits = details.get("splits_standard") or []
            if not isinstance(splits, list):
                return []
            out: list[dict] = []
            for i, s in enumerate(splits, start=1):
                if not isinstance(s, dict):
                    continue
                # Guard against pathological tiny splits (seen rarely in Strava payloads)
                try:
                    if s.get("distance") is not None and float(s.get("distance")) < 50:
                        continue
                    if s.get("moving_time") is not None and int(s.get("moving_time")) < 10:
                        continue
                except Exception:
                    pass
                out.append(
                    {
                        "split_number": int(s.get("split") or s.get("split_number") or i),
                        "distance": s.get("distance"),
                        "elapsed_time": s.get("elapsed_time"),
                        "moving_time": s.get("moving_time"),
                        "average_heartrate": s.get("average_heartrate"),
                        "max_heartrate": s.get("max_heartrate"),
                        "average_cadence": s.get("average_cadence"),
                        "average_grade_adjusted_speed": s.get("average_grade_adjusted_speed"),
                    }
                )
            return out
        
        strava_activity_id = int(activity.external_activity_id)
        details = get_activity_details(current_user, int(strava_activity_id), allow_rate_limit_sleep=True) or {}
        mile_splits = _extract_strava_mile_splits_from_details(details)

        # Prefer laps as the segmentation source if present (matches Strava "Laps" tab / user-defined laps).
        laps = get_activity_laps(current_user, strava_activity_id) or []
        mile_map = {}
        for ms in mile_splits:
            try:
                mile_map[int(ms["split_number"])] = ms
            except Exception:
                continue

        source_splits = []
        if laps:
            for lap in laps:
                idx = lap.get("lap_index") or lap.get("split")
                if not idx:
                    continue
                split_num = int(idx)
                # Enrich lap with Strava's canonical GA speed when the numbering aligns.
                ms = mile_map.get(split_num) or {}
                source_splits.append(
                    {
                        "split_number": split_num,
                        "distance": lap.get("distance"),
                        "elapsed_time": lap.get("elapsed_time"),
                        "moving_time": lap.get("moving_time"),
                        "average_heartrate": lap.get("average_heartrate"),
                        "max_heartrate": lap.get("max_heartrate"),
                        "average_cadence": lap.get("average_cadence"),
                        "average_grade_adjusted_speed": ms.get("average_grade_adjusted_speed")
                        or lap.get("average_grade_adjusted_speed"),
                        "total_elevation_gain": lap.get("total_elevation_gain"),
                    }
                )
        else:
            source_splits = mile_splits
        
        if not source_splits:
            return {
                "status": "warning",
                "message": "No split/lap data available from Strava for this activity",
                "splits_count": 0
            }
        
        # Upsert split records (create missing + fill missing fields)
        created = 0
        updated = 0

        existing = {
            int(s.split_number): s
            for s in db.query(ActivitySplit).filter(ActivitySplit.activity_id == activity.id).all()
        }

        for src in source_splits:
            idx = src.get("split_number")
            if not idx:
                continue
            split_num = int(idx)

            # Guard against pathological tiny splits
            try:
                if src.get("distance") is not None and float(src.get("distance")) < 50:
                    continue
                if src.get("moving_time") is not None and int(src.get("moving_time")) < 10:
                    continue
            except Exception:
                pass

            gap_seconds_per_mile = None
            is_auth = False
            try:
                ga = src.get("average_grade_adjusted_speed")
                if ga is not None:
                    ga = float(ga)
                    if ga > 0:
                        gap_seconds_per_mile = 1609.34 / ga
                        is_auth = True
            except Exception:
                pass
            if gap_seconds_per_mile is None:
                gap_seconds_per_mile, is_auth = _gap_seconds_per_mile_from_lap(src)

            if split_num in existing:
                s = existing[split_num]
                before = (s.average_cadence, s.gap_seconds_per_mile, s.max_heartrate, s.average_heartrate)
                if s.max_heartrate is None:
                    s.max_heartrate = _coerce_int(src.get("max_heartrate"))
                if s.average_heartrate is None:
                    s.average_heartrate = _coerce_int(src.get("average_heartrate"))
                if s.average_cadence is None:
                    s.average_cadence = src.get("average_cadence")
                # Overwrite GAP when we have authoritative provider value; otherwise fill only if missing.
                if gap_seconds_per_mile is not None:
                    if is_auth:
                        s.gap_seconds_per_mile = gap_seconds_per_mile
                    elif s.gap_seconds_per_mile is None:
                        s.gap_seconds_per_mile = gap_seconds_per_mile
                after = (s.average_cadence, s.gap_seconds_per_mile, s.max_heartrate, s.average_heartrate)
                if after != before:
                    updated += 1
            else:
                db.add(
                    ActivitySplit(
                        activity_id=activity.id,
                        split_number=split_num,
                        distance=src.get("distance"),
                        elapsed_time=src.get("elapsed_time"),
                        moving_time=src.get("moving_time"),
                        average_heartrate=_coerce_int(src.get("average_heartrate")),
                        max_heartrate=_coerce_int(src.get("max_heartrate")),
                        average_cadence=src.get("average_cadence"),
                        gap_seconds_per_mile=gap_seconds_per_mile,
                    )
                )
                created += 1

        db.commit()

        total = db.query(ActivitySplit).filter(ActivitySplit.activity_id == activity.id).count()
        return {
            "status": "success",
            "activity_id": str(activity_id),
            "splits_total": total,
            "splits_created": created,
            "splits_updated": updated,
            "message": f"Splits refreshed (created {created}, updated {updated})",
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error backfilling splits: {str(e)}")


@router.post("/checkins", response_model=DailyCheckinResponse, status_code=201)
def create_checkin(
    checkin: DailyCheckinCreate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new daily checkin (auth required; athlete_id from auth context only)."""
    data = checkin.model_dump() if hasattr(checkin, "model_dump") else checkin.dict()
    data.pop("athlete_id", None)
    db_checkin = DailyCheckin(athlete_id=current_user.id, **data)
    db.add(db_checkin)
    db.commit()
    db.refresh(db_checkin)
    return db_checkin
