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
from services.strava_service import poll_activities, poll_activities_page, get_activity_laps, get_activity_details
from services.strava_pbs import sync_strava_best_efforts
from services.athlete_metrics import calculate_athlete_derived_signals
from services.personal_best import update_personal_best
from services.pace_normalization import calculate_ngp_from_split
from services.insight_aggregator import generate_insights_for_athlete
# Helper functions (moved from routers.strava to avoid circular imports)
def _coerce_int(x):
    """Coerce value to int, returning None if not possible."""
    try:
        if x is None:
            return None
        return int(round(float(x)))
    except Exception:
        return None


def _gap_seconds_per_mile_from_lap(lap: dict) -> tuple[float | None, bool]:
    """
    Prefer Strava's grade-adjusted speed when present; fallback to NGP approximation.

    Returns: (gap_seconds_per_mile, is_authoritative_from_provider)
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
    """
    Strava activity details often contain `splits_standard` (mile) with
    `average_grade_adjusted_speed`. This matches what Strava shows in the UI
    for mile laps/GAP.
    """
    splits = details.get("splits_standard") or []
    if not isinstance(splits, list):
        return []
    # Normalize to the fields we already store in ActivitySplit.
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
from sqlalchemy import func, desc
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
    
    from services.strava_service import StravaRateLimitError
    from services.ingestion_state import mark_ingestion_deferred
    from datetime import timedelta

    from celery.exceptions import Retry

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
        #
        # IMPORTANT:
        # Strava's `/athlete/activities?after=` filter uses the activity *start time*,
        # not the upload time. If we use "last sync clicked" as the cursor, we can
        # permanently miss runs that started before the click but were uploaded later.
        #
        # To avoid this, we always use an overlap window when polling.
        SYNC_OVERLAP_SECONDS = 36 * 60 * 60  # 36h overlap (covers late uploads + timezone edges)
        if last_sync_raw is None:
            after_timestamp = 0
        else:
            if isinstance(last_sync_raw, datetime):
                after_timestamp = int(last_sync_raw.timestamp())
            else:
                after_timestamp = int(last_sync_raw)
            after_timestamp = max(0, int(after_timestamp) - int(SYNC_OVERLAP_SECONDS))
        
        # Poll activities from Strava (viral-safe: do not sleep on 429; defer + retry).
        print(f"DEBUG: Polling activities with after_timestamp={after_timestamp}")
        try:
            strava_activities = poll_activities(athlete, after_timestamp, allow_rate_limit_sleep=False)
        except StravaRateLimitError as e:
            retry_after_s = int(getattr(e, "retry_after_s", 900) or 900)
            countdown = max(60, min(retry_after_s, 60 * 60))
            until = datetime.now(timezone.utc) + timedelta(seconds=countdown)
            mark_ingestion_deferred(
                db,
                athlete.id,
                "strava",
                scope="index",
                deferred_until=until,
                reason="rate_limit",
                task_id=str(self.request.id),
            )
            db.commit()
            raise self.retry(countdown=countdown)
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
            # Report progress to Celery so frontend can show progress bar
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': activity_idx + 1,
                    'total': total_from_api,
                    'message': f"Syncing activity {activity_idx + 1} of {total_from_api}..."
                }
            )
            
            # Strava uses a few run-like types; treat them as runs.
            activity_type = (a.get("type") or "").lower()
            if activity_type not in {"run", "virtualrun", "trailrun"}:
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

                        # Fetch both: details (canonical GA speed) + laps (canonical segmentation)
                        # Viral-safe: do not sleep on 429; defer + retry.
                        try:
                            details = get_activity_details(athlete, int(strava_activity_id), allow_rate_limit_sleep=False) or {}
                        except StravaRateLimitError as e:
                            retry_after_s = int(getattr(e, "retry_after_s", 900) or 900)
                            countdown = max(60, min(retry_after_s, 60 * 60))
                            until = datetime.now(timezone.utc) + timedelta(seconds=countdown)
                            mark_ingestion_deferred(
                                db,
                                athlete.id,
                                "strava",
                                scope="index",
                                deferred_until=until,
                                reason="rate_limit",
                                task_id=str(self.request.id),
                            )
                            db.commit()
                            raise self.retry(countdown=countdown)
                        mile_splits = _extract_strava_mile_splits_from_details(details)
                        mile_map = {}
                        for ms in mile_splits:
                            try:
                                mile_map[int(ms["split_number"])] = ms
                            except Exception:
                                continue

                        try:
                            laps = get_activity_laps(athlete, strava_activity_id, allow_rate_limit_sleep=False) or []
                        except StravaRateLimitError as e:
                            retry_after_s = int(getattr(e, "retry_after_s", 900) or 900)
                            countdown = max(60, min(retry_after_s, 60 * 60))
                            until = datetime.now(timezone.utc) + timedelta(seconds=countdown)
                            mark_ingestion_deferred(
                                db,
                                athlete.id,
                                "strava",
                                scope="index",
                                deferred_until=until,
                                reason="rate_limit",
                                task_id=str(self.request.id),
                            )
                            db.commit()
                            raise self.retry(countdown=countdown)
                        source_splits = []
                        if laps:
                            for lap in laps:
                                idx = lap.get("lap_index") or lap.get("split")
                                if not idx:
                                    continue
                                split_num = int(idx)
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

                        if source_splits:
                            lap_count = 0
                            for s in source_splits:
                                idx = s.get("split_number")
                                if not idx:
                                    continue
                                try:
                                    if s.get("distance") is not None and float(s.get("distance")) < 50:
                                        continue
                                    if s.get("moving_time") is not None and int(s.get("moving_time")) < 10:
                                        continue
                                except Exception:
                                    pass
                                gap_val = None
                                is_auth = False
                                try:
                                    ga = s.get("average_grade_adjusted_speed")
                                    if ga is not None:
                                        ga = float(ga)
                                        if ga > 0:
                                            gap_val = 1609.34 / ga
                                            is_auth = True
                                except Exception:
                                    pass
                                if gap_val is None:
                                    gap_val, is_auth = _gap_seconds_per_mile_from_lap(s)

                                db.add(
                                    ActivitySplit(
                                        activity_id=existing.id,
                                        split_number=int(idx),
                                        distance=s.get("distance"),
                                        elapsed_time=s.get("elapsed_time"),
                                        moving_time=s.get("moving_time"),
                                        average_heartrate=_coerce_int(s.get("average_heartrate")),
                                        max_heartrate=_coerce_int(s.get("max_heartrate")),
                                        average_cadence=s.get("average_cadence"),
                                        gap_seconds_per_mile=gap_val,
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

                        # Prefer laps as segmentation; enrich with canonical GA speed from details.
                        details = get_activity_details(athlete, int(strava_activity_id), allow_rate_limit_sleep=True) or {}
                        mile_splits = _extract_strava_mile_splits_from_details(details)
                        mile_map: dict[int, dict] = {}
                        for ms in mile_splits:
                            try:
                                mile_map[int(ms["split_number"])] = ms
                            except Exception:
                                continue

                        split_map: dict[int, dict] = {}
                        laps = get_activity_laps(athlete, strava_activity_id) or []
                        if laps:
                            for l in laps:
                                idx = l.get("lap_index") or l.get("split")
                                if idx:
                                    split_num = int(idx)
                                    ms = mile_map.get(split_num) or {}
                                    merged = dict(l)
                                    if ms.get("average_grade_adjusted_speed") is not None:
                                        merged["average_grade_adjusted_speed"] = ms.get("average_grade_adjusted_speed")
                                    split_map[split_num] = merged
                        else:
                            split_map = mile_map

                        splits = db.query(ActivitySplit).filter(ActivitySplit.activity_id == existing.id).all()

                        for s in splits:
                            src = split_map.get(int(s.split_number))
                            if not src:
                                continue
                            try:
                                if src.get("distance") is not None and float(src.get("distance")) < 50:
                                    continue
                                if src.get("moving_time") is not None and int(src.get("moving_time")) < 10:
                                    continue
                            except Exception:
                                pass
                            if s.max_heartrate is None:
                                s.max_heartrate = _coerce_int(src.get("max_heartrate"))
                            if s.average_cadence is None:
                                s.average_cadence = src.get("average_cadence")
                            if s.average_heartrate is None:
                                s.average_heartrate = _coerce_int(src.get("average_heartrate"))

                            # Overwrite GAP when we have authoritative grade-adjusted speed.
                            gap_val = None
                            is_auth = False
                            try:
                                ga = src.get("average_grade_adjusted_speed")
                                if ga is not None:
                                    ga = float(ga)
                                    if ga > 0:
                                        gap_val = 1609.34 / ga
                                        is_auth = True
                            except Exception:
                                pass
                            if gap_val is None:
                                gap_val, is_auth = _gap_seconds_per_mile_from_lap(src)

                            if is_auth and gap_val is not None:
                                s.gap_seconds_per_mile = gap_val
                            elif s.gap_seconds_per_mile is None and gap_val is not None:
                                s.gap_seconds_per_mile = gap_val
                    except Exception as e:
                        print(f"Warning: Could not update splits for activity {strava_activity_id}: {e}")
                
                # Backfill avg_hr from details if missing
                if existing.avg_hr is None and details.get("average_heartrate"):
                    existing.avg_hr = _coerce_int(details.get("average_heartrate"))
                    db.flush()
                
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

                details = get_activity_details(athlete, int(strava_activity_id), allow_rate_limit_sleep=True) or {}
                mile_splits = _extract_strava_mile_splits_from_details(details)
                mile_map = {}
                for ms in mile_splits:
                    try:
                        mile_map[int(ms["split_number"])] = ms
                    except Exception:
                        continue

                laps = get_activity_laps(athlete, strava_activity_id) or []
                source_splits = []
                if laps:
                    for lap in laps:
                        lap_idx = lap.get("lap_index") or lap.get("split")
                        if not lap_idx:
                            continue
                        split_num = int(lap_idx)
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

                if source_splits:
                    for s in source_splits:
                        idx = s.get("split_number")
                        if not idx:
                            continue
                        try:
                            if s.get("distance") is not None and float(s.get("distance")) < 50:
                                continue
                            if s.get("moving_time") is not None and int(s.get("moving_time")) < 10:
                                continue
                        except Exception:
                            pass

                        gap_val = None
                        is_auth = False
                        try:
                            ga = s.get("average_grade_adjusted_speed")
                            if ga is not None:
                                ga = float(ga)
                                if ga > 0:
                                    gap_val = 1609.34 / ga
                                    is_auth = True
                        except Exception:
                            pass
                        if gap_val is None:
                            gap_val, is_auth = _gap_seconds_per_mile_from_lap(s)

                        db.add(
                            ActivitySplit(
                                activity_id=activity.id,
                                split_number=int(idx),
                                distance=s.get("distance"),
                                elapsed_time=s.get("elapsed_time"),
                                moving_time=s.get("moving_time"),
                                average_heartrate=_coerce_int(s.get("average_heartrate")),
                                max_heartrate=_coerce_int(s.get("max_heartrate")),
                                average_cadence=s.get("average_cadence"),
                                gap_seconds_per_mile=gap_val,
                            )
                        )
                    db.flush()
                
                # Backfill avg_hr from details if missing (list endpoint often omits it)
                if activity.avg_hr is None and details.get("average_heartrate"):
                    activity.avg_hr = _coerce_int(details.get("average_heartrate"))
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
                try:
                    db.rollback()
                except Exception:
                    pass
            
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
            # If the sync attempt raised due to a DB issue (or rate limiting logic),
            # ensure the session is usable for subsequent work in this task.
            try:
                db.rollback()
            except Exception:
                pass
        
        # Generate insights based on new activity
        insights_generated = 0
        try:
            # Get the most recent activity for insight generation context
            most_recent = (
                db.query(Activity)
                .filter(Activity.athlete_id == athlete.id)
                .order_by(Activity.start_time.desc())
                .first()
            )
            insights = generate_insights_for_athlete(db, athlete, most_recent, persist=True)
            insights_generated = len(insights)
            print(f"DEBUG: Generated {insights_generated} insights")
        except Exception as e:
            print(f"Warning: Could not generate insights: {e}")
        
        return {
            "status": "success",
            "message": "Sync completed.",
            "synced_new": synced_new,
            "updated_existing": updated_existing,
            "splits_backfilled": splits_backfilled,
            "strava_pbs": strava_pb_result,
            "insights_generated": insights_generated,
        }
        
    except Retry:
        # Phase 5 armor: allow Celery retries to propagate (not an error).
        raise
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


@celery_app.task(name="tasks.backfill_strava_activity_index", bind=True)
def backfill_strava_activity_index_task(self: Task, athlete_id: str, pages: int = 5) -> Dict:
    """
    Backfill the Strava activity index (Activity rows) using paged /athlete/activities.

    This is the cheapest way to ensure missing activities exist locally so they can be
    followed by best-effort extraction and other downstream processing.
    """
    from services.strava_index import upsert_strava_activity_summaries
    from services.ingestion_state import (
        mark_index_started,
        mark_index_finished,
        mark_index_error,
        mark_ingestion_deferred,
    )
    from services.strava_service import StravaRateLimitError
    from datetime import timedelta

    from celery.exceptions import Retry

    db: Session = get_db_sync()
    try:
        athlete = db.get(Athlete, athlete_id)
        if not athlete:
            return {"status": "error", "error": f"Athlete {athlete_id} not found"}
        if not athlete.strava_access_token:
            return {"status": "error", "error": "No Strava connection"}

        mark_index_started(db, athlete.id, "strava", task_id=str(self.request.id))
        db.commit()

        created = 0
        already = 0
        skipped_non_runs = 0
        pages_fetched = 0

        for page in range(1, max(1, int(pages)) + 1):
            try:
                summaries = poll_activities_page(
                    athlete,
                    after_timestamp=0,
                    before_timestamp=None,
                    page=page,
                    per_page=200,
                    max_retries=3,
                    allow_rate_limit_sleep=False,
                )
            except StravaRateLimitError as e:
                # Phase 5 armor: treat 429 as deferral (not an error) and re-queue.
                retry_after_s = int(getattr(e, "retry_after_s", 900) or 900)
                countdown = max(60, min(retry_after_s, 60 * 60))  # bound: 1m..60m
                until = datetime.now(timezone.utc) + timedelta(seconds=countdown)

                mark_ingestion_deferred(
                    db,
                    athlete.id,
                    "strava",
                    scope="index",
                    deferred_until=until,
                    reason="rate_limit",
                    task_id=str(self.request.id),
                )
                db.commit()
                raise self.retry(countdown=countdown)
            pages_fetched += 1
            if not summaries:
                break

            res = upsert_strava_activity_summaries(athlete, db, summaries)
            created += res.created
            already += res.already_present
            skipped_non_runs += res.skipped_non_runs

            db.commit()

        result = {
            "status": "success",
            "athlete_id": athlete_id,
            "pages_fetched": pages_fetched,
            "created": created,
            "already_present": already,
            "skipped_non_runs": skipped_non_runs,
        }
        mark_index_finished(db, athlete.id, "strava", result)
        db.commit()
        return result
    except Retry:
        # Phase 5 armor: allow Celery retries to propagate (not an error).
        raise
    except Exception as e:
        db.rollback()
        try:
            athlete = db.get(Athlete, athlete_id)
            if athlete:
                mark_index_error(db, athlete.id, "strava", error=str(e), task_id=str(self.request.id))
                db.commit()
        except Exception:
            db.rollback()
        traceback.print_exc()
        return {"status": "error", "error": str(e)}
    finally:
        db.close()

