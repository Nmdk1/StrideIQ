"""
Celery tasks for Strava synchronization.

These tasks run in the background worker to prevent blocking the API.
"""
from datetime import datetime, timezone
from typing import Dict
from celery import Task
from sqlalchemy.orm import Session
from sqlalchemy import text
from core.database import get_db_sync
from tasks import celery_app
from models import Athlete, Activity, ActivitySplit
from services.strava_service import poll_activities, get_activity_laps
from services.strava_pbs import sync_strava_best_efforts
from services.athlete_metrics import calculate_athlete_derived_signals
from services.personal_best import update_personal_best
from services.pace_normalization import calculate_ngp_from_split
# Helper functions (moved from routers.strava to avoid circular imports)
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
from sqlalchemy import func
import time
import traceback


@celery_app.task(name="tasks.sync_strava_activities", bind=True)
def sync_strava_activities_task(self: Task, athlete_id: str) -> Dict:
    """
    Background task to sync Strava activities for an athlete.
    
    This task:
    1. Fetches activities from Strava API
    2. Creates/updates activities in database
    3. Fetches and stores splits
    4. Calculates performance metrics
    5. Updates personal bests
    6. Syncs Strava best efforts
    
    Args:
        athlete_id: UUID string of the athlete to sync
        
    Returns:
        Dictionary with sync results:
        {
            "status": "success" | "error",
            "synced_new": int,
            "updated_existing": int,
            "splits_backfilled": int,
            "strava_pbs": dict,
            "error": str (if error)
        }
    """
    db: Session = get_db_sync()
    print(f"DEBUG: Starting sync for athlete_id={athlete_id}")
    
    try:
        # Get athlete
        print(f"DEBUG: Looking up athlete in database...")
        athlete = db.get(Athlete, athlete_id)
        print(f"DEBUG: db.get returned: {athlete}")
        if not athlete:
            print(f"DEBUG: Athlete not found!")
            return {
                "status": "error",
                "error": f"Athlete {athlete_id} not found"
            }
        
        print(f"DEBUG: Found athlete email={athlete.email}, strava_id={athlete.strava_athlete_id}")
        if not athlete.strava_access_token:
            print(f"DEBUG: No strava access token!")
            return {
                "status": "error",
                "error": f"Athlete {athlete_id} has no Strava access token"
            }
        
        # CRITICAL: Use raw SQL to get last_strava_sync to bypass identity map cache
        result = db.execute(
            text("""
                SELECT last_strava_sync 
                FROM athlete 
                WHERE id = :athlete_id
            """),
            {"athlete_id": athlete_id}
        ).first()
        
        last_sync_raw = result[0] if result else None
        
        # Determine after_timestamp
        if last_sync_raw is None:
            after_timestamp = 0
        else:
            if isinstance(last_sync_raw, datetime):
                after_timestamp = int(last_sync_raw.timestamp())
            else:
                after_timestamp = int(last_sync_raw)
        
        # Poll activities from Strava
        print(f"DEBUG: Polling activities with after_timestamp={after_timestamp}")
        strava_activities = poll_activities(athlete, after_timestamp)
        print(f"DEBUG: Got {len(strava_activities)} activities from Strava")
        
        synced_new = 0
        updated_existing = 0
        splits_backfilled = 0
        skipped_non_runs = 0
        total_from_api = len(strava_activities)
        
        print(f"DEBUG: Starting to process {total_from_api} activities...")
        
        LAP_FETCH_DELAY = 2.0  # 2 second delay between lap fetches
        
        # Process each activity
        for activity_idx, a in enumerate(strava_activities):
            activity_type = a.get("type", "").lower()
            if activity_type != "run":
                skipped_non_runs += 1
                continue
            
            strava_activity_id = a.get("id")
            if not strava_activity_id:
                continue
            
            start_time_str = a.get("start_date")
            if not start_time_str:
                continue
            
            start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
            
            provider = "strava"
            external_activity_id = str(strava_activity_id)
            
            # Check if activity exists
            existing = (
                db.query(Activity)
                .filter(
                    Activity.provider == provider,
                    Activity.external_activity_id == external_activity_id,
                )
                .first()
            )
            
            # Update existing activity
            if existing:
                changed = False
                
                # Ensure ingestion-contract fields exist
                if not existing.provider:
                    existing.provider = provider
                    changed = True
                
                if not existing.external_activity_id:
                    existing.external_activity_id = external_activity_id
                    changed = True
                
                if existing.is_race_candidate is None:
                    existing.is_race_candidate = False
                    changed = True
                
                if existing.user_verified_race is None:
                    existing.user_verified_race = False
                    changed = True
                
                # Fill optional metrics if missing
                if existing.max_hr is None and a.get("max_heartrate") is not None:
                    existing.max_hr = a.get("max_heartrate")
                    changed = True
                
                if existing.total_elevation_gain is None and a.get("total_elevation_gain") is not None:
                    existing.total_elevation_gain = a.get("total_elevation_gain")
                    changed = True
                
                if existing.average_speed is None and a.get("average_speed") is not None:
                    existing.average_speed = a.get("average_speed")
                    changed = True
                
                # Backfill activity name if missing
                if existing.name is None and a.get("name") is not None:
                    existing.name = a.get("name")
                    changed = True
                
                if changed:
                    updated_existing += 1
                
                # Check if splits need backfilling
                split_count = (
                    db.query(func.count(ActivitySplit.id))
                    .filter(ActivitySplit.activity_id == existing.id)
                    .scalar()
                )
                
                if split_count == 0:
                    # Backfill splits
                    try:
                        if activity_idx > 0:
                            time.sleep(LAP_FETCH_DELAY)
                        
                        laps = get_activity_laps(athlete, strava_activity_id) or []
                        
                        if laps:
                            lap_count = 0
                            for lap in laps:
                                idx = lap.get("lap_index") or lap.get("split")
                                if not idx:
                                    continue
                                
                                # Calculate GAP (Grade Adjusted Pace) using Minetti's equation
                                distance_m = lap.get("distance")
                                moving_time_s = lap.get("moving_time")
                                elevation_gain_m = lap.get("total_elevation_gain")  # Elevation gain for this lap
                                
                                gap_seconds_per_mile = None
                                if distance_m and moving_time_s:
                                    gap_seconds_per_mile = calculate_ngp_from_split(
                                        distance_m=distance_m,
                                        moving_time_s=moving_time_s,
                                        elevation_gain_m=elevation_gain_m
                                    )
                                
                                db.add(
                                    ActivitySplit(
                                        activity_id=existing.id,
                                        split_number=int(idx),
                                        distance=distance_m,
                                        elapsed_time=lap.get("elapsed_time"),
                                        moving_time=moving_time_s,
                                        average_heartrate=_coerce_int(lap.get("average_heartrate")),
                                        max_heartrate=_coerce_int(lap.get("max_heartrate")),
                                        average_cadence=lap.get("average_cadence"),
                                        gap_seconds_per_mile=gap_seconds_per_mile,
                                    )
                                )
                                lap_count += 1
                            
                            if lap_count > 0:
                                db.flush()
                                splits_backfilled += 1
                    except Exception as e:
                        print(f"ERROR: Could not fetch laps for existing activity {strava_activity_id}: {e}")
                else:
                    # Update existing splits with missing values
                    try:
                        if activity_idx > 0:
                            time.sleep(LAP_FETCH_DELAY)
                        
                        laps = get_activity_laps(athlete, strava_activity_id) or []
                        if laps:
                            lap_map = {}
                            for l in laps:
                                idx = l.get("lap_index") or l.get("split")
                                if idx:
                                    lap_map[int(idx)] = l
                            
                            splits = db.query(ActivitySplit).filter(ActivitySplit.activity_id == existing.id).all()
                            
                            for s in splits:
                                lap = lap_map.get(int(s.split_number))
                                if not lap:
                                    continue
                                if s.max_heartrate is None:
                                    s.max_heartrate = _coerce_int(lap.get("max_heartrate"))
                                if s.average_cadence is None:
                                    s.average_cadence = lap.get("average_cadence")
                                if s.average_heartrate is None:
                                    s.average_heartrate = _coerce_int(lap.get("average_heartrate"))
                                
                                # Calculate GAP if missing
                                if s.gap_seconds_per_mile is None:
                                    distance_m = s.distance
                                    moving_time_s = s.moving_time
                                    elevation_gain_m = lap.get("total_elevation_gain")
                                    if distance_m and moving_time_s:
                                        s.gap_seconds_per_mile = calculate_ngp_from_split(
                                            distance_m=float(distance_m),
                                            moving_time_s=moving_time_s,
                                            elevation_gain_m=elevation_gain_m
                                        )
                    except Exception as e:
                        print(f"Warning: Could not update splits for activity {strava_activity_id}: {e}")
                
                # Recalculate performance metrics
                try:
                    _calculate_performance_metrics(existing, athlete, db)
                except Exception as e:
                    print(f"Warning: Could not recalculate performance metrics: {e}")
                
                # Update personal best
                try:
                    pb = update_personal_best(existing, athlete, db)
                except Exception as e:
                    print(f"Warning: Could not update personal best: {e}")
                
                continue
            
            # Create new activity
            print(f"DEBUG: Creating new activity {strava_activity_id} - {a.get('name')}")
            activity = Activity(
                athlete_id=athlete.id,
                name=a.get("name"),  # Store the activity name from Strava
                start_time=start_time,
                sport="run",
                source="strava",
                duration_s=a.get("moving_time") or a.get("elapsed_time"),
                distance_m=a.get("distance"),
                avg_hr=a.get("average_heartrate"),
                max_hr=a.get("max_heartrate"),
                total_elevation_gain=a.get("total_elevation_gain"),
                average_speed=a.get("average_speed"),
                provider=provider,
                external_activity_id=external_activity_id,
                is_race_candidate=bool(a.get("workout_type") == 3),
                race_confidence=None,
                user_verified_race=False,
            )
            
            try:
                db.add(activity)
                db.flush()
                print(f"DEBUG: Activity {strava_activity_id} created with id={activity.id}")
            except Exception as e:
                print(f"ERROR: Failed to create activity {strava_activity_id}: {e}")
                db.rollback()
                continue
            
            # Fetch splits
            try:
                if activity_idx > 0:
                    time.sleep(LAP_FETCH_DELAY)
                
                laps = get_activity_laps(athlete, strava_activity_id) or []
                if laps:
                    for lap in laps:
                        lap_idx = lap.get("lap_index") or lap.get("split")
                        if not lap_idx:
                            continue
                        
                        # Calculate GAP (Grade Adjusted Pace) using Minetti's equation
                        distance_m = lap.get("distance")
                        moving_time_s = lap.get("moving_time")
                        elevation_gain_m = lap.get("total_elevation_gain")  # Elevation gain for this lap
                        
                        gap_seconds_per_mile = None
                        if distance_m and moving_time_s:
                            gap_seconds_per_mile = calculate_ngp_from_split(
                                distance_m=distance_m,
                                moving_time_s=moving_time_s,
                                elevation_gain_m=elevation_gain_m
                            )
                        
                        db.add(
                            ActivitySplit(
                                activity_id=activity.id,
                                split_number=int(lap_idx),
                                distance=distance_m,
                                elapsed_time=lap.get("elapsed_time"),
                                moving_time=moving_time_s,
                                average_heartrate=_coerce_int(lap.get("average_heartrate")),
                                max_heartrate=_coerce_int(lap.get("max_heartrate")),
                                average_cadence=lap.get("average_cadence"),
                                gap_seconds_per_mile=gap_seconds_per_mile,
                            )
                        )
                    db.flush()
            except Exception as e:
                print(f"Warning: Could not fetch laps for activity {strava_activity_id}: {e}")
            
            # Calculate performance metrics
            try:
                _calculate_performance_metrics(activity, athlete, db)
            except Exception as e:
                print(f"Warning: Could not calculate performance metrics: {e}")
            
            # Update personal best
            try:
                pb = update_personal_best(activity, athlete, db)
            except Exception as e:
                print(f"Warning: Could not update personal best: {e}")
            
            synced_new += 1
        
        # Update last sync timestamp
        athlete.last_strava_sync = datetime.now(timezone.utc)
        db.commit()
        
        # Calculate derived signals
        try:
            metrics = calculate_athlete_derived_signals(athlete, db, force_recalculate=False)
        except Exception as e:
            print(f"WARNING: Could not calculate derived signals: {e}")
        
        # Sync Strava best efforts
        strava_pb_result = {}
        try:
            strava_pb_result = sync_strava_best_efforts(athlete, db, limit=200)
        except Exception as e:
            print(f"Warning: Could not sync Strava best efforts: {e}")
        
        return {
            "status": "success",
            "message": "Sync completed.",
            "synced_new": synced_new,
            "updated_existing": updated_existing,
            "splits_backfilled": splits_backfilled,
            "strava_pbs": strava_pb_result,
        }
        
    except Exception as e:
        db.rollback()
        error_msg = f"Error syncing activities: {str(e)}"
        print(f"ERROR: {error_msg}")
        traceback.print_exc()
        return {
            "status": "error",
            "error": error_msg
        }
    finally:
        db.close()

