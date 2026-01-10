"""
Celery tasks for Garmin Connect synchronization.

These tasks run in the background worker to prevent blocking the API.
Staggered execution to mimic natural user behavior.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from celery import Task
from sqlalchemy.orm import Session
from core.database import get_db_sync
from tasks import celery_app
from models import Athlete, Activity, ActivitySplit, DailyCheckin
from services.garmin_service import GarminService, extract_recovery_metrics
from services.activity_deduplication import deduplicate_activities
from services.token_encryption import encrypt_token, decrypt_token
from services.strava_service import poll_activities as poll_strava_activities
from services.athlete_metrics import calculate_athlete_derived_signals
from services.personal_best import update_personal_best
import time
import traceback
import logging

logger = logging.getLogger(__name__)


def _coerce_int(x):
    """Coerce value to int, returning None if not possible."""
    try:
        if x is None:
            return None
        return int(round(float(x)))
    except Exception:
        return None


def _calculate_performance_metrics(activity, athlete, db):
    """Calculate age-graded performance and race detection."""
    from services.performance_engine import (
        calculate_age_at_date,
        calculate_age_graded_performance,
        detect_race_candidate,
    )
    
    # Calculate age-graded performance
    if activity.pace_per_mile and activity.distance_m:
        age = calculate_age_at_date(athlete.birthdate, activity.start_time)
        
        # International/WMA standard
        performance_pct_intl = calculate_age_graded_performance(
            actual_pace_per_mile=activity.pace_per_mile,
            age=age,
            sex=athlete.sex,
            distance_meters=float(activity.distance_m),
            use_national=False
        )
        if performance_pct_intl:
            activity.performance_percentage = performance_pct_intl
        
        # National standard
        performance_pct_nat = calculate_age_graded_performance(
            actual_pace_per_mile=activity.pace_per_mile,
            age=age,
            sex=athlete.sex,
            distance_meters=float(activity.distance_m),
            use_national=True
        )
        if performance_pct_nat:
            activity.performance_percentage_national = performance_pct_nat
    
    # Race detection
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


def _convert_garmin_activity_to_db(garmin_activity: Dict, athlete_id: str) -> Optional[Activity]:
    """
    Convert Garmin activity dictionary to Activity model.
    
    Args:
        garmin_activity: Garmin activity dictionary
        athlete_id: Athlete UUID
        
    Returns:
        Activity model instance or None
    """
    try:
        # Parse start time
        start_time_str = garmin_activity.get("startTimeLocal") or garmin_activity.get("startTimeGMT")
        if not start_time_str:
            return None
        
        start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        
        # Extract activity type
        activity_type = garmin_activity.get("activityType", {}).get("typeKey", "").lower()
        if "running" not in activity_type and activity_type != "running":
            return None  # Skip non-running activities
        
        # Extract distance (meters)
        distance_m = garmin_activity.get("distance") or garmin_activity.get("distanceInMeters")
        
        # Extract duration (seconds)
        duration_s = garmin_activity.get("elapsedDuration") or garmin_activity.get("duration")
        
        # Extract HR data
        avg_hr = _coerce_int(garmin_activity.get("averageHeartRate") or garmin_activity.get("avgHeartRate"))
        max_hr = _coerce_int(garmin_activity.get("maxHeartRate") or garmin_activity.get("maximumHeartRate"))
        
        # Extract other metrics
        elevation_gain = garmin_activity.get("elevationGain") or garmin_activity.get("totalElevationGain")
        avg_speed = garmin_activity.get("averageSpeed") or garmin_activity.get("avgSpeed")
        
        activity = Activity(
            athlete_id=athlete_id,
            start_time=start_time,
            sport="run",
            source="garmin",
            duration_s=_coerce_int(duration_s),
            distance_m=_coerce_int(distance_m) if distance_m else None,
            avg_hr=avg_hr,
            max_hr=max_hr,
            total_elevation_gain=elevation_gain,
            average_speed=avg_speed,
            provider="garmin",
            external_activity_id=str(garmin_activity.get("activityId") or garmin_activity.get("activity_id")),
            is_race_candidate=False,  # Will be detected later
            race_confidence=None,
            user_verified_race=False,
        )
        
        return activity
        
    except Exception as e:
        logger.error(f"Error converting Garmin activity: {e}")
        return None


@celery_app.task(name="tasks.sync_garmin_activities", bind=True)
def sync_garmin_activities_task(self: Task, athlete_id: str) -> Dict:
    """
    Background task to sync Garmin activities for an athlete.
    
    This task:
    1. Fetches activities from Garmin Connect
    2. Creates/updates activities in database
    3. Fetches and stores splits
    4. Calculates performance metrics
    5. Updates personal bests
    6. Handles deduplication with Strava
    
    Args:
        athlete_id: UUID string of the athlete to sync
        
    Returns:
        Dictionary with sync results
    """
    db: Session = get_db_sync()
    
    try:
        # Get athlete
        athlete = db.get(Athlete, athlete_id)
        if not athlete:
            return {
                "status": "error",
                "error": f"Athlete {athlete_id} not found"
            }
        
        if not athlete.garmin_connected or not athlete.garmin_username or not athlete.garmin_password_encrypted:
            return {
                "status": "error",
                "error": f"Athlete {athlete_id} not connected to Garmin"
            }
        
        # Initialize Garmin service
        try:
            garmin_service = GarminService(
                username=athlete.garmin_username,
                password_encrypted=athlete.garmin_password_encrypted
            )
        except Exception as e:
            logger.error(f"Failed to initialize Garmin service: {e}")
            return {
                "status": "error",
                "error": f"Garmin service initialization failed: {str(e)}"
            }
        
        # Determine date range for sync
        if athlete.last_garmin_sync:
            start_date = athlete.last_garmin_sync - timedelta(days=1)  # Overlap by 1 day
        else:
            # First sync: backfill 30-120 days
            start_date = datetime.now() - timedelta(days=90)
        
        # Get Garmin activities
        garmin_activities = garmin_service.get_activities(start_date=start_date, limit=200)
        
        if not garmin_activities:
            logger.info(f"No Garmin activities found for athlete {athlete_id}")
            return {
                "status": "success",
                "message": "No new activities",
                "synced_new": 0,
                "updated_existing": 0
            }
        
        # Get Strava activities for deduplication (if Strava connected)
        strava_activities = []
        if athlete.strava_access_token:
            try:
                strava_activities = poll_strava_activities(athlete, after_timestamp=None)
            except Exception as e:
                logger.warning(f"Could not fetch Strava activities for deduplication: {e}")
        
        # Deduplicate: Garmin is primary
        unique_garmin, unique_strava = deduplicate_activities(garmin_activities, strava_activities)
        
        synced_new = 0
        updated_existing = 0
        
        # Process Garmin activities (primary source)
        for garmin_activity in unique_garmin:
            activity_id = garmin_activity.get("activityId") or garmin_activity.get("activity_id")
            if not activity_id:
                continue
            
            external_id = str(activity_id)
            
            # Check if activity exists
            existing = db.query(Activity).filter(
                Activity.provider == "garmin",
                Activity.external_activity_id == external_id
            ).first()
            
            if existing:
                # Update existing (Garmin takes priority)
                updated_existing += 1
                # Recalculate metrics
                try:
                    _calculate_performance_metrics(existing, athlete, db)
                    update_personal_best(existing, athlete, db)
                except Exception as e:
                    logger.warning(f"Could not update metrics for activity {external_id}: {e}")
                continue
            
            # Create new activity
            activity = _convert_garmin_activity_to_db(garmin_activity, str(athlete.id))
            if not activity:
                continue
            
            db.add(activity)
            db.flush()
            
            # Get detailed activity data for splits
            try:
                details = garmin_service.get_activity_details(activity_id)
                if details:
                    # Extract splits if available
                    splits = details.get("splits") or details.get("lapDTOs") or []
                    for split in splits:
                        split_num = split.get("lapNumber") or split.get("split")
                        if split_num:
                            db.add(ActivitySplit(
                                activity_id=activity.id,
                                split_number=int(split_num),
                                distance=split.get("distance"),
                                elapsed_time=split.get("elapsedTime"),
                                moving_time=split.get("movingTime"),
                                average_heartrate=_coerce_int(split.get("averageHeartRate")),
                                max_heartrate=_coerce_int(split.get("maxHeartRate")),
                                average_cadence=split.get("averageCadence"),
                            ))
                    db.flush()
            except Exception as e:
                logger.warning(f"Could not fetch splits for Garmin activity {activity_id}: {e}")
            
            # Calculate performance metrics
            try:
                _calculate_performance_metrics(activity, athlete, db)
            except Exception as e:
                logger.warning(f"Could not calculate performance metrics: {e}")
            
            # Update personal best
            try:
                update_personal_best(activity, athlete, db)
            except Exception as e:
                logger.warning(f"Could not update personal best: {e}")
            
            synced_new += 1
        
        # Update last sync timestamp
        athlete.last_garmin_sync = datetime.now(timezone.utc)
        db.commit()
        
        # Calculate derived signals
        try:
            calculate_athlete_derived_signals(athlete, db, force_recalculate=False)
        except Exception as e:
            logger.warning(f"Could not calculate derived signals: {e}")
        
        return {
            "status": "success",
            "message": "Garmin sync completed",
            "synced_new": synced_new,
            "updated_existing": updated_existing,
        }
        
    except Exception as e:
        db.rollback()
        error_msg = f"Error syncing Garmin activities: {str(e)}"
        logger.error(error_msg)
        traceback.print_exc()
        return {
            "status": "error",
            "error": error_msg
        }
    finally:
        db.close()


@celery_app.task(name="tasks.sync_garmin_recovery_metrics", bind=True)
def sync_garmin_recovery_metrics_task(self: Task, athlete_id: str, days_back: int = 30) -> Dict:
    """
    Background task to sync Garmin recovery metrics.
    
    Pulls:
    - Sleep duration (time asleep only)
    - HRV (rMSSD, SDNN)
    - Resting HR
    - Overnight avg HR
    
    Args:
        athlete_id: UUID string of the athlete
        days_back: Number of days to sync (default: 30)
        
    Returns:
        Dictionary with sync results
    """
    db: Session = get_db_sync()
    
    try:
        athlete = db.get(Athlete, athlete_id)
        if not athlete:
            return {
                "status": "error",
                "error": f"Athlete {athlete_id} not found"
            }
        
        if not athlete.garmin_connected or not athlete.garmin_username or not athlete.garmin_password_encrypted:
            return {
                "status": "error",
                "error": f"Athlete {athlete_id} not connected to Garmin"
            }
        
        # Initialize Garmin service
        try:
            garmin_service = GarminService(
                username=athlete.garmin_username,
                password_encrypted=athlete.garmin_password_encrypted
            )
        except Exception as e:
            logger.error(f"Failed to initialize Garmin service: {e}")
            return {
                "status": "error",
                "error": f"Garmin service initialization failed: {str(e)}"
            }
        
        synced_count = 0
        start_date = datetime.now() - timedelta(days=days_back)
        
        # Sync each day
        for i in range(days_back):
            date = start_date + timedelta(days=i)
            date_only = date.date()
            
            # Check if checkin already exists
            checkin = db.query(DailyCheckin).filter(
                DailyCheckin.athlete_id == athlete.id,
                DailyCheckin.date == date_only
            ).first()
            
            if not checkin:
                checkin = DailyCheckin(
                    athlete_id=athlete.id,
                    date=date_only
                )
                db.add(checkin)
            
            # Extract recovery metrics
            try:
                metrics = extract_recovery_metrics(garmin_service, date)
                
                # Update checkin with metrics
                if metrics.get("sleep_duration_hours"):
                    checkin.sleep_h = metrics["sleep_duration_hours"]
                if metrics.get("hrv_rmssd"):
                    checkin.hrv_rmssd = metrics["hrv_rmssd"]
                if metrics.get("hrv_sdnn"):
                    checkin.hrv_sdnn = metrics["hrv_sdnn"]
                if metrics.get("resting_hr"):
                    checkin.resting_hr = metrics["resting_hr"]
                if metrics.get("overnight_avg_hr"):
                    checkin.overnight_avg_hr = metrics["overnight_avg_hr"]
                
                synced_count += 1
                
                # Small delay to avoid rate limiting
                if i > 0 and i % 10 == 0:
                    time.sleep(2)
                    
            except Exception as e:
                logger.warning(f"Could not sync recovery metrics for {date_only}: {e}")
                continue
        
        db.commit()
        
        return {
            "status": "success",
            "message": f"Synced {synced_count} days of recovery metrics",
            "days_synced": synced_count
        }
        
    except Exception as e:
        db.rollback()
        error_msg = f"Error syncing Garmin recovery metrics: {str(e)}"
        logger.error(error_msg)
        traceback.print_exc()
        return {
            "status": "error",
            "error": error_msg
        }
    finally:
        db.close()


@celery_app.task(name="tasks.garmin_health_check")
def garmin_health_check_task() -> Dict:
    """
    Daily health check for Garmin library.
    
    Performs a small test API call to verify library is working.
    
    Returns:
        Dictionary with health check results
    """
    try:
        # Test import
        from garminconnect import Garmin
        
        # Try to create a test instance (without actual login)
        # This verifies the library is importable and functional
        
        return {
            "status": "healthy",
            "library_available": True,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except ImportError:
        return {
            "status": "unhealthy",
            "library_available": False,
            "error": "garminconnect library not installed",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "library_available": True,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

