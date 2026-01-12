from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from core.database import get_db
from core.auth import get_current_user
from models import Athlete, Activity, DailyCheckin, ActivitySplit
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
def get_athletes(db: Session = Depends(get_db)):
    """Get all athletes"""
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
def create_athlete(athlete: AthleteCreate, db: Session = Depends(get_db)):
    """Create a new athlete"""
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
def get_athlete(id: UUID, db: Session = Depends(get_db)):
    """Get an athlete by ID with Performance Physics Engine metrics"""
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
        # Check if email is already taken by another user
        existing = db.query(Athlete).filter(
            Athlete.email == athlete_update.email,
            Athlete.id != current_user.id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use"
            )
        current_user.email = athlete_update.email
    if athlete_update.onboarding_stage is not None:
        current_user.onboarding_stage = athlete_update.onboarding_stage
    if athlete_update.onboarding_completed is not None:
        current_user.onboarding_completed = athlete_update.onboarding_completed
    
    db.commit()
    db.refresh(current_user)
    
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
def create_activity(activity: ActivityCreate, db: Session = Depends(get_db)):
    """Create a new activity"""
    db_activity = Activity(**activity.dict())
    db.add(db_activity)
    db.commit()
    db.refresh(db_activity)
    return db_activity


@router.get("/activities/{activity_id}/splits", response_model=List[ActivitySplitResponse])
def get_activity_splits(activity_id: UUID, db: Session = Depends(get_db)):
    """Get splits for a specific activity"""
    # Verify activity exists
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    splits = db.query(ActivitySplit).filter(
        ActivitySplit.activity_id == activity_id
    ).order_by(ActivitySplit.split_number).all()
    
    return splits


@router.post("/athletes/{id}/calculate-metrics")
def calculate_athlete_metrics(id: UUID, db: Session = Depends(get_db)):
    """
    Calculate Performance Physics Engine derived signals for an athlete.
    This implements Manifesto Section 4: Derived Signals.
    """
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
def get_personal_bests_endpoint(id: UUID, db: Session = Depends(get_db)):
    """Get all personal bests for an athlete"""
    from services.personal_best import get_personal_bests as get_pbs_service
    
    athlete = db.query(Athlete).filter(Athlete.id == id).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    
    pbs = get_pbs_service(str(athlete.id), db)
    return pbs


@router.post("/athletes/{id}/recalculate-pbs")
def recalculate_pbs_endpoint(id: UUID, db: Session = Depends(get_db)):
    """
    Regenerate personal bests from stored BestEffort records.
    
    This is an instant aggregation - no external API calls.
    Best efforts are populated during Strava sync.
    
    Use /athletes/{id}/sync-best-efforts to fetch new best efforts from Strava.
    """
    from services.best_effort_service import regenerate_personal_bests
    from models import BestEffort

    athlete = db.query(Athlete).filter(Athlete.id == id).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")

    # Count stored best efforts
    effort_count = db.query(BestEffort).filter(BestEffort.athlete_id == athlete.id).count()
    
    # Regenerate PBs from BestEffort table (instant aggregation)
    result = regenerate_personal_bests(athlete, db)

    return {
        "status": "success",
        "athlete_id": str(athlete.id),
        "efforts_in_db": effort_count,
        "pbs_created": result.get('created', 0),
        "categories": result.get('categories', []),
        "message": f"Regenerated {result.get('created', 0)} PBs from {effort_count} stored efforts"
    }


@router.post("/athletes/{id}/sync-best-efforts")
def sync_best_efforts_endpoint(id: UUID, limit: int = 50, db: Session = Depends(get_db)):
    """
    Sync best efforts from Strava API into the BestEffort table.
    
    This fetches activity details from Strava - can take 30-60 seconds.
    After syncing, PersonalBest is regenerated from the stored efforts.
    
    Best efforts are also synced automatically during regular Strava sync.
    """
    from services.strava_pbs import sync_strava_best_efforts

    athlete = db.query(Athlete).filter(Athlete.id == id).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")

    if not athlete.strava_access_token:
        raise HTTPException(status_code=400, detail="No Strava connection")

    try:
        result = sync_strava_best_efforts(athlete, db, limit=limit)
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


@router.post("/activities/{activity_id}/mark-race")
def mark_activity_as_race(activity_id: UUID, is_race: bool = True, db: Session = Depends(get_db)):
    """
    Manually mark/unmark an activity as a race.
    This allows users to override the automatic race detection.
    """
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
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
def backfill_activity_splits(activity_id: UUID, db: Session = Depends(get_db)):
    """
    Backfill splits for an activity that is missing them.
    Fetches lap data from Strava API and creates split records.
    """
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    if not activity.provider == "strava" or not activity.external_activity_id:
        raise HTTPException(status_code=400, detail="Activity is not from Strava or missing external ID")
    
    athlete = db.query(Athlete).filter(Athlete.id == activity.athlete_id).first()
    if not athlete or not athlete.strava_access_token:
        raise HTTPException(status_code=404, detail="Athlete not found or missing Strava token")
    
    from services.strava_service import get_activity_laps
    from routers.strava import _coerce_int
    import time
    
    try:
        # Check if splits already exist
        existing_splits = db.query(ActivitySplit).filter(
            ActivitySplit.activity_id == activity.id
        ).count()
        
        if existing_splits > 0:
            return {
                "status": "info",
                "message": f"Activity already has {existing_splits} splits",
                "splits_count": existing_splits
            }
        
        # Fetch laps from Strava
        strava_activity_id = int(activity.external_activity_id)
        laps = get_activity_laps(athlete, strava_activity_id) or []
        
        if not laps:
            return {
                "status": "warning",
                "message": "No lap data available from Strava for this activity",
                "splits_count": 0
            }
        
        # Create split records
        splits_created = 0
        for lap in laps:
            idx = lap.get("lap_index") or lap.get("split")
            if not idx:
                continue
            
            split = ActivitySplit(
                activity_id=activity.id,
                split_number=int(idx),
                distance=lap.get("distance"),
                elapsed_time=lap.get("elapsed_time"),
                moving_time=lap.get("moving_time"),
                average_heartrate=_coerce_int(lap.get("average_heartrate")),
                max_heartrate=_coerce_int(lap.get("max_heartrate")),
                average_cadence=lap.get("average_cadence"),
            )
            db.add(split)
            splits_created += 1
        
        db.commit()
        
        return {
            "status": "success",
            "activity_id": str(activity_id),
            "splits_created": splits_created,
            "message": f"Successfully backfilled {splits_created} splits"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error backfilling splits: {str(e)}")


@router.post("/checkins", response_model=DailyCheckinResponse, status_code=201)
def create_checkin(checkin: DailyCheckinCreate, db: Session = Depends(get_db)):
    """Create a new daily checkin"""
    db_checkin = DailyCheckin(**checkin.dict())
    db.add(db_checkin)
    db.commit()
    db.refresh(db_checkin)
    return db_checkin
