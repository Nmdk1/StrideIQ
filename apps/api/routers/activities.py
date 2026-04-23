"""
Activities API Router

Provides endpoints for activity management with proper filtering, pagination, and authentication.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
from typing import Optional, List
from datetime import datetime, timedelta
from uuid import UUID
from core.database import get_db
from core.auth import get_current_user
from core.feature_flags import is_feature_enabled
from models import Activity, Athlete, ActivitySplit, ActivityStream, StrengthExerciseSet
from services.intelligence.narration_tiers import (
    evidence_phrase as _af_evidence_phrase,
    tier_for as _af_tier_for,
)
from services.n1_insight_generator import friendly_signal_name
from schemas import ActivityResponse

router = APIRouter(prefix="/v1/activities", tags=["activities"])


_STRAVA_AUTO_NAMES = frozenset({
    "morning run", "afternoon run", "evening run", "night run", "lunch run",
    "morning walk", "afternoon walk", "evening walk", "lunch walk",
    "morning ride", "afternoon ride", "evening ride", "lunch ride",
    "long run", "race",
})

_GARMIN_AUTO_SUFFIXES = (" Running", " Walking", " Cycling", " Hiking")


def _is_auto_generated_name(name: Optional[str], provider: Optional[str]) -> bool:
    """Return True if the activity name is platform-generated, not athlete-authored."""
    if not name or not name.strip():
        return True
    if provider == "demo":
        return True
    if name.strip().lower() in _STRAVA_AUTO_NAMES:
        return True
    if provider == "garmin":
        for suffix in _GARMIN_AUTO_SUFFIXES:
            if name.endswith(suffix):
                return True
    return False


def resolve_activity_title(activity) -> Optional[str]:
    """Single source of truth for activity display title.

    Priority:
      1. athlete_title  — edited in StrideIQ, always wins
      2. race name      — athlete's title for a race is sacred
      3. authored name  — non-auto Strava/Garmin title beats shape_sentence
      4. shape_sentence — system's structural understanding
      5. name           — fallback (auto-generated platform title)
    """
    if getattr(activity, 'athlete_title', None):
        return activity.athlete_title

    name = getattr(activity, 'name', None)
    sentence = getattr(activity, 'shape_sentence', None)
    provider = getattr(activity, 'provider', None) or ''
    is_race = (
        getattr(activity, 'user_verified_race', False)
        or getattr(activity, 'is_race_candidate', False)
    )

    if is_race and name:
        return name

    if name and not _is_auto_generated_name(name, provider):
        return name

    return sentence or name


class ActivityTitleUpdate(BaseModel):
    title: Optional[str] = None

    @field_validator('title')
    @classmethod
    def normalize_empty(cls, v):
        if v is not None and v.strip() == '':
            return None
        if v and len(v) > 200:
            raise ValueError('Title must be 200 characters or fewer')
        return v.strip() if v else v


@router.get("", response_model=List[ActivityResponse])
def list_activities(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=100, description="Number of activities to return"),
    offset: int = Query(0, ge=0, description="Number of activities to skip"),
    start_date: Optional[str] = Query(None, description="Filter activities from this date (ISO format)"),
    end_date: Optional[str] = Query(None, description="Filter activities until this date (ISO format)"),
    min_distance_m: Optional[int] = Query(None, ge=0, description="Minimum distance in meters"),
    max_distance_m: Optional[int] = Query(None, ge=0, description="Maximum distance in meters"),
    sport: Optional[str] = Query(None, description="Filter by sport type"),
    is_race: Optional[bool] = Query(None, description="Filter by race status"),
    workout_type: Optional[str] = Query(
        None,
        description="Filter by workout_type. Comma-separated list for multi-select (e.g., 'long_run,threshold').",
    ),
    temp_min: Optional[float] = Query(None, description="Minimum temperature °F (inclusive). NULL temp activities excluded when set."),
    temp_max: Optional[float] = Query(None, description="Maximum temperature °F (inclusive). NULL temp activities excluded when set."),
    dew_min: Optional[float] = Query(None, description="Minimum dew point °F (inclusive). NULL dew activities excluded when set."),
    dew_max: Optional[float] = Query(None, description="Maximum dew point °F (inclusive). NULL dew activities excluded when set."),
    elev_gain_min: Optional[float] = Query(None, description="Minimum elevation gain (meters). NULL excluded when set."),
    elev_gain_max: Optional[float] = Query(None, description="Maximum elevation gain (meters). NULL excluded when set."),
    sort_by: str = Query("start_time", description="Sort field: start_time, distance_m, duration_s"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
):
    """
    List activities for current user with filtering and pagination.
    
    Returns only activities belonging to the authenticated user.
    Supports filtering by date range, distance, sport type, and race status.

    Phase 1 additions (comparison product family):
        workout_type, temp_min/max, dew_min/max, elev_gain_min/max.
        Suppression rule: when a range filter is active, activities with
        NULL on that field are excluded — we never claim a value we don't
        have.
    """
    # Build query - always filter by athlete_id
    query = db.query(Activity).filter(Activity.athlete_id == current_user.id)
    
    # Date filtering
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query = query.filter(Activity.start_time >= start_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"
            )
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.filter(Activity.start_time <= end_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"
            )
    
    # Distance filtering
    if min_distance_m is not None:
        query = query.filter(Activity.distance_m >= min_distance_m)
    
    if max_distance_m is not None:
        query = query.filter(Activity.distance_m <= max_distance_m)
    
    # Sport filtering
    if sport:
        query = query.filter(Activity.sport == sport)

    # --- Phase 1 filters ---------------------------------------------------
    # workout_type: comma-separated multi-select. NULL workout_type rows are
    # excluded when this filter is active (suppression principle: don't include
    # a row in a typed filter when its type is unknown).
    if workout_type:
        types = [t.strip() for t in workout_type.split(",") if t.strip()]
        if types:
            query = query.filter(Activity.workout_type.in_(types))

    # Range filters share a helper to enforce min<=max and NULL exclusion.
    def _apply_range(col, lo, hi, label: str):
        if lo is not None and hi is not None and lo > hi:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{label}: min cannot exceed max ({lo} > {hi})",
            )
        nonlocal query
        if lo is not None:
            query = query.filter(col >= lo, col.isnot(None))
        if hi is not None:
            query = query.filter(col <= hi, col.isnot(None))

    _apply_range(Activity.temperature_f, temp_min, temp_max, "temp")
    _apply_range(Activity.dew_point_f, dew_min, dew_max, "dew")
    _apply_range(Activity.total_elevation_gain, elev_gain_min, elev_gain_max, "elev_gain")
    # ----------------------------------------------------------------------

    # Race filtering
    # When filtering for races (is_race=True): include if EITHER flag is True
    # When filtering for training (is_race=False): exclude if EITHER flag is True
    if is_race is not None:
        if is_race:
            # Show races: either user verified OR candidate
            query = query.filter(
                or_(
                    Activity.user_verified_race.is_(True),
                    Activity.is_race_candidate.is_(True),
                )
            )
        else:
            # Show training only: NOT a race (both flags must be False/None)
            query = query.filter(
                and_(
                    or_(Activity.user_verified_race.is_(False), Activity.user_verified_race.is_(None)),
                    or_(Activity.is_race_candidate.is_(False), Activity.is_race_candidate.is_(None)),
                )
            )
    
    # Sorting
    sort_field_map = {
        "start_time": Activity.start_time,
        "distance_m": Activity.distance_m,
        "duration_s": Activity.duration_s,
    }
    
    sort_field = sort_field_map.get(sort_by, Activity.start_time)
    if sort_order.lower() == "asc":
        query = query.order_by(asc(sort_field))
    else:
        query = query.order_by(desc(sort_field))
    
    # Pagination
    activities = query.offset(offset).limit(limit).all()
    
    # Convert to response format
    result = []
    for activity in activities:
        # Use actual activity name if available, otherwise generate default
        activity_name = activity.name or f"{activity.sport.title()} Activity"
        
        activity_dict = {
            "id": str(activity.id),
            "strava_id": None,  # Add if needed
            "name": activity_name,
            "sport": activity.sport or "run",
            "distance": float(activity.distance_m) if activity.distance_m else 0.0,
            "moving_time": activity.duration_s or 0,
            "start_date": activity.start_time.isoformat(),
            "average_speed": float(activity.average_speed) if activity.average_speed else 0.0,
            "max_hr": activity.max_hr,
            "average_heartrate": activity.avg_hr,
            "average_cadence": None,  # Calculate from splits if needed
            "total_elevation_gain": float(activity.total_elevation_gain) if activity.total_elevation_gain else None,
            "pace_s_per_km": None,
            "duration_formatted": None,  # Format if needed
            "splits": None,  # Load splits if needed
            "performance_percentage": activity.performance_percentage,
            "performance_percentage_national": activity.performance_percentage_national,
            "is_race_candidate": activity.is_race_candidate,
            "race_confidence": activity.race_confidence,
            "shape_sentence": activity.shape_sentence,
            "athlete_title": activity.athlete_title,
            "resolved_title": resolve_activity_title(activity),
        }
        
        if activity.average_speed and float(activity.average_speed) > 0:
            activity_dict["pace_s_per_km"] = round(1000 / float(activity.average_speed), 1)
        
        # Format duration
        if activity.duration_s:
            hours = activity.duration_s // 3600
            minutes = (activity.duration_s % 3600) // 60
            secs = activity.duration_s % 60
            if hours > 0:
                activity_dict["duration_formatted"] = f"{hours}:{minutes:02d}:{secs:02d}"
            else:
                activity_dict["duration_formatted"] = f"{minutes}:{secs:02d}"
        
        result.append(ActivityResponse(**activity_dict))
    
    return result


@router.get("/summary", response_model=dict)
def get_activities_summary(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
):
    """
    Sport-aware activity summary.

    Returns three views so the UI can show running, other-sport, or combined
    independently — never silently mixed:

    - `running`:  sport=='run' only. This is the canonical training metric.
                  Average pace and race count live here (running concepts).
    - `other`:    everything else, broken down `by_sport`. No average pace
                  (not meaningful across walking + strength + cycling).
    - `combined`: every activity. Useful for "how active was I overall?"
                  Distance is intentionally not the headline here — it
                  conflates units (running km vs walking km vs cycling km).

    Backwards-compatible top-level fields mirror `running` so existing
    consumers keep working until they migrate.
    """
    from sqlalchemy import func, case

    cutoff_date = datetime.utcnow() - timedelta(days=days)

    base_filter = [
        Activity.athlete_id == current_user.id,
        Activity.start_time >= cutoff_date,
        Activity.is_duplicate.is_(False),
    ]

    def _agg(*extra_filters):
        q = db.query(
            func.count(Activity.id).label('total_activities'),
            func.sum(Activity.distance_m).label('total_distance_m'),
            func.sum(Activity.duration_s).label('total_duration_s'),
            func.avg(
                case(
                    (Activity.average_speed > 0, 26.8224 / Activity.average_speed),
                    else_=None,
                )
            ).label('avg_pace_per_mile'),
            func.sum(
                case(
                    (Activity.user_verified_race.is_(True) | Activity.is_race_candidate.is_(True), 1),
                    else_=0,
                )
            ).label('race_count'),
        ).filter(*base_filter, *extra_filters)
        return q.first()

    running = _agg(Activity.sport == "run")
    combined = _agg()

    # Per-sport breakdown for the "other" bucket.
    by_sport_rows = db.query(
        Activity.sport,
        func.count(Activity.id).label('count'),
        func.sum(Activity.distance_m).label('distance_m'),
        func.sum(Activity.duration_s).label('duration_s'),
    ).filter(*base_filter, Activity.sport != "run").group_by(Activity.sport).all()

    other_by_sport: dict[str, dict] = {}
    other_total_count = 0
    other_total_dist_m = 0
    other_total_dur_s = 0
    for sport, count, dist_m, dur_s in by_sport_rows:
        key = sport or "unknown"
        d = int(dist_m or 0)
        t = int(dur_s or 0)
        other_by_sport[key] = {
            "total_activities": int(count or 0),
            "total_distance_m": d,
            "total_duration_s": t,
        }
        other_total_count += int(count or 0)
        other_total_dist_m += d
        other_total_dur_s += t

    # Counts grouped by sport (running included) — keeps backward compat.
    sports_count_rows = db.query(
        Activity.sport,
        func.count(Activity.id).label('count'),
    ).filter(*base_filter).group_by(Activity.sport).all()
    sports = {sport or "unknown": count for sport, count in sports_count_rows}

    def _bucket(row):
        d = int(row.total_distance_m or 0)
        t = int(row.total_duration_s or 0)
        avg_pace = round(float(row.avg_pace_per_mile), 2) if row.avg_pace_per_mile else None
        avg_pace_s_km = round(avg_pace * 1609.344 / 1000, 1) if avg_pace else None
        return {
            "total_activities": int(row.total_activities or 0),
            "total_distance_m": d,
            "total_duration_s": t,
            "avg_pace_s_per_km": avg_pace_s_km,
            "race_count": int(row.race_count or 0),
        }

    running_bucket = _bucket(running)
    combined_bucket = _bucket(combined)
    other_bucket = {
        "total_activities": other_total_count,
        "total_distance_m": other_total_dist_m,
        "total_duration_s": other_total_dur_s,
        "by_sport": other_by_sport,
    }

    return {
        "running": running_bucket,
        "other": other_bucket,
        "combined": combined_bucket,
        "total_activities": running_bucket["total_activities"],
        "total_distance_m": running_bucket["total_distance_m"],
        "total_duration_s": running_bucket["total_duration_s"],
        "avg_pace_s_per_km": running_bucket["avg_pace_s_per_km"],
        "activities_by_sport": sports,
        "race_count": running_bucket["race_count"],
        "period_days": days,
    }


@router.get("/filter-distributions", response_model=dict)
def get_filter_distributions(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return per-dimension distributions for the activities-list filter UI.

    For each filterable dimension, returns either:
      - {available: True, min, max, buckets: [{lo, hi, count}, ...]}  (16 buckets)
      - {available: False}  when fewer than 5 activities have a value
        in that dimension (suppression rule: don't render a histogram
        the athlete can't meaningfully brush on).

    workout_types lists the types the athlete actually has, with counts.
    NULL workout_type rows are excluded — they're not selectable.

    See docs/specs/phase1_filters_design.md for the full design.
    """
    from sqlalchemy import func

    AVAILABILITY_THRESHOLD = 5
    BUCKET_COUNT = 16

    workout_type_rows = (
        db.query(Activity.workout_type, func.count(Activity.id))
        .filter(
            Activity.athlete_id == current_user.id,
            Activity.workout_type.isnot(None),
        )
        .group_by(Activity.workout_type)
        .order_by(func.count(Activity.id).desc(), Activity.workout_type.asc())
        .all()
    )
    workout_types = [
        {"value": value, "count": int(count)}
        for value, count in workout_type_rows
        if value
    ]

    def _distribution(column) -> dict:
        """Build histogram metadata for a numeric column."""
        rows = (
            db.query(column)
            .filter(
                Activity.athlete_id == current_user.id,
                column.isnot(None),
            )
            .all()
        )
        values = [float(v[0]) for v in rows if v[0] is not None]
        if len(values) < AVAILABILITY_THRESHOLD:
            return {"available": False}

        lo = min(values)
        hi = max(values)
        if hi == lo:
            # All identical — single-bucket histogram is meaningless; degrade
            # gracefully by reporting the single value with count.
            return {
                "available": True,
                "min": lo,
                "max": hi,
                "buckets": [{"lo": lo, "hi": hi, "count": len(values)}],
            }

        bucket_width = (hi - lo) / BUCKET_COUNT
        buckets = []
        for i in range(BUCKET_COUNT):
            b_lo = lo + i * bucket_width
            b_hi = lo + (i + 1) * bucket_width
            buckets.append({"lo": b_lo, "hi": b_hi, "count": 0})

        for v in values:
            # Last bucket is inclusive on the upper bound; others are [lo, hi).
            if v >= hi:
                idx = BUCKET_COUNT - 1
            else:
                idx = int((v - lo) / bucket_width)
                if idx < 0:
                    idx = 0
                if idx >= BUCKET_COUNT:
                    idx = BUCKET_COUNT - 1
            buckets[idx]["count"] += 1

        return {
            "available": True,
            "min": lo,
            "max": hi,
            "buckets": buckets,
        }

    return {
        "workout_types": workout_types,
        "distance_m": _distribution(Activity.distance_m),
        "temp_f": _distribution(Activity.temperature_f),
        "dew_point_f": _distribution(Activity.dew_point_f),
        "elevation_gain_m": _distribution(Activity.total_elevation_gain),
    }


@router.get("/{activity_id}", response_model=dict)
def get_activity(
    activity_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a single activity by ID with full details.
    
    Includes workout classification, expected RPE, and narrative context.
    Only returns activity if it belongs to the current user.
    """
    from services.workout_classifier import WorkoutClassifierService
    
    activity = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.athlete_id == current_user.id
    ).first()
    
    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found"
        )
    
    # Calculate expected RPE if we have workout classification
    expected_rpe_range = None
    if activity.workout_type:
        try:
            classifier = WorkoutClassifierService(db)
            from services.workout_classifier import WorkoutType
            workout_type = WorkoutType(activity.workout_type)
            duration_min = (activity.duration_s or 0) / 60
            expected_rpe_range = classifier.get_expected_rpe(workout_type, duration_min)
        except (ValueError, Exception):
            pass
    
    # Generate narrative context (ADR-033)
    narrative = None
    if is_feature_enabled("narrative.translation_enabled", str(current_user.id), db):
        try:
            from services.narrative_translator import NarrativeTranslator
            from services.narrative_memory import NarrativeMemory
            
            translator = NarrativeTranslator(db, current_user.id)
            memory = NarrativeMemory(db, current_user.id, use_redis=False)
            
            # Generate workout context narrative
            if activity.workout_type:
                pace = None
                if activity.average_speed and float(activity.average_speed) > 0:
                    pace = 26.8224 / float(activity.average_speed)
                
                narrative_obj = translator.narrate_workout_context(
                    activity.workout_type,
                    activity.name or "Run",
                    pace
                )
                
                if narrative_obj and not memory.recently_shown(narrative_obj.hash, days=7):
                    narrative = narrative_obj.text
                    memory.record_shown(narrative_obj.hash, narrative_obj.signal_type, "activity_detail")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Activity narrative generation failed for activity {activity_id}: {type(e).__name__}: {e}")
            try:
                from services.audit_logger import log_narrative_error
                log_narrative_error(current_user.id, "activity_detail", str(e))
            except Exception:
                pass
    
    # Build response
    # Derive cadence from stored splits (Strava cadence isn't stored on Activity yet).
    cadence_weighted_sum = 0.0
    cadence_weight_s = 0.0
    try:
        split_rows = (
            db.query(ActivitySplit.average_cadence, ActivitySplit.moving_time, ActivitySplit.elapsed_time)
            .filter(ActivitySplit.activity_id == activity.id)
            .all()
        )
        for avg_cadence, moving_time, elapsed_time in split_rows:
            if avg_cadence is None:
                continue
            w = float(moving_time or elapsed_time or 0)
            if w <= 0:
                continue
            cadence_weighted_sum += float(avg_cadence) * w
            cadence_weight_s += w
    except Exception:
        # Best-effort only; do not break activity detail if cadence derivation fails.
        cadence_weighted_sum = 0.0
        cadence_weight_s = 0.0

    derived_avg_cadence = None
    if cadence_weight_s > 0:
        derived_avg_cadence = cadence_weighted_sum / cadence_weight_s

    result = {
        "id": str(activity.id),
        "name": activity.name or "Run",
        "sport_type": activity.sport,
        "start_time": activity.start_time.isoformat() if activity.start_time else None,
        "distance_m": activity.distance_m,
        "elapsed_time_s": activity.duration_s,
        # `moving_time_s` from FIT is true moving time (excludes auto-pause).
        # Falls back to elapsed time for activities ingested before the FIT
        # pipeline existed.
        "moving_time_s": activity.moving_time_s if activity.moving_time_s else activity.duration_s,
        "average_hr": activity.avg_hr,
        "max_hr": activity.max_hr,
        "average_cadence": derived_avg_cadence,
        "total_elevation_gain_m": float(activity.total_elevation_gain) if activity.total_elevation_gain else None,
        "total_descent_m": float(activity.total_descent_m) if activity.total_descent_m else None,
        "average_temp_c": float(activity.temperature_f - 32) * 5/9 if activity.temperature_f else None,
        "provider": activity.provider,
        "strava_activity_id": activity.external_activity_id if activity.provider == "strava" else None,
        "device_name": activity.device_name,
        
        # Workout classification
        "workout_type": activity.workout_type,
        "workout_zone": activity.workout_zone,
        "workout_confidence": activity.workout_confidence,
        "intensity_score": activity.intensity_score,
        
        # Expected RPE based on workout type
        "expected_rpe_range": expected_rpe_range,
        
        # Race info
        "is_race": activity.user_verified_race or activity.is_race_candidate,
        "race_confidence": activity.race_confidence,
        "performance_percentage": activity.performance_percentage,
        
        # Environmental context
        "temperature_f": activity.temperature_f,
        "humidity_pct": activity.humidity_pct,
        "weather_condition": activity.weather_condition,
        "dew_point_f": activity.dew_point_f,
        "heat_adjustment_pct": activity.heat_adjustment_pct,
        
        # Narrative context (ADR-033)
        "narrative": narrative,
        
        # Shape sentence (Living Fingerprint)
        "shape_sentence": activity.shape_sentence,
        "athlete_title": activity.athlete_title,
        "resolved_title": resolve_activity_title(activity),

        # Pre-activity wellness snapshot
        "pre_sleep_h": activity.pre_sleep_h,
        "pre_sleep_score": activity.pre_sleep_score,
        "pre_resting_hr": activity.pre_resting_hr,
        "pre_recovery_hrv": activity.pre_recovery_hrv,
        "pre_overnight_hrv": activity.pre_overnight_hrv,

        # Cross-training fields
        "strength_session_type": activity.strength_session_type,
        "session_detail": None,

        # Missing metrics (device-level, not split-derived)
        "steps": activity.steps,
        "active_kcal": activity.active_kcal,
        "avg_cadence_device": activity.avg_cadence,
        "max_cadence": activity.max_cadence,

        # FIT-derived activity-level metrics (fit_run_001).
        # All nullable: present iff a FIT file landed for this activity.
        "avg_power_w": activity.avg_power_w,
        "max_power_w": activity.max_power_w,
        "avg_stride_length_m": (
            float(activity.avg_stride_length_m)
            if activity.avg_stride_length_m is not None else None
        ),
        "avg_ground_contact_ms": (
            float(activity.avg_ground_contact_ms)
            if activity.avg_ground_contact_ms is not None else None
        ),
        "avg_ground_contact_balance_pct": (
            float(activity.avg_ground_contact_balance_pct)
            if activity.avg_ground_contact_balance_pct is not None else None
        ),
        "avg_vertical_oscillation_cm": (
            float(activity.avg_vertical_oscillation_cm)
            if activity.avg_vertical_oscillation_cm is not None else None
        ),
        "avg_vertical_ratio_pct": (
            float(activity.avg_vertical_ratio_pct)
            if activity.avg_vertical_ratio_pct is not None else None
        ),
        # Garmin self-evaluation (low-confidence fallback only — the
        # athlete's own ActivityFeedback always wins on the UI surface;
        # see effort_resolver in Phase 3).
        "garmin_feel": activity.garmin_feel,
        "garmin_perceived_effort": activity.garmin_perceived_effort,
    }

    # --- Cross-training enrichment (non-run only) ---
    if activity.sport and activity.sport != "run":
        result["session_detail"] = activity.session_detail

        # TSS computation
        try:
            from services.training_load import TrainingLoadCalculator
            calc = TrainingLoadCalculator(db)
            stress = calc.calculate_workout_tss(activity, current_user)
            result["tss"] = stress.tss
            result["tss_method"] = stress.calculation_method
            result["intensity_factor"] = stress.intensity_factor
        except Exception:
            result["tss"] = None
            result["tss_method"] = None
            result["intensity_factor"] = None

        # Weekly TSS split (running vs cross-training for the 7-day window)
        try:
            from services.timezone_utils import get_athlete_timezone, local_day_bounds_utc
            _ath_tz = get_athlete_timezone(current_user)
            _today = datetime.now().date()
            _week_start = _today - timedelta(days=6)
            _w_start_utc = local_day_bounds_utc(_week_start, _ath_tz)[0]
            _w_end_utc = local_day_bounds_utc(_today, _ath_tz)[1]

            from sqlalchemy import func, case
            tss_rows = (
                db.query(
                    case((Activity.sport == "run", "running"), else_="cross_training").label("bucket"),
                    func.count(Activity.id).label("count"),
                )
                .filter(
                    Activity.athlete_id == current_user.id,
                    Activity.start_time >= _w_start_utc,
                    Activity.start_time < _w_end_utc,
                )
                .group_by("bucket")
                .all()
            )
            weekly = {"running_activities": 0, "cross_training_activities": 0}
            for bucket, count in tss_rows:
                if bucket == "running":
                    weekly["running_activities"] = count
                else:
                    weekly["cross_training_activities"] = count
            result["weekly_context"] = weekly
        except Exception:
            result["weekly_context"] = None

        # Strength exercise sets
        if activity.sport == "strength":
            sets = (
                db.query(StrengthExerciseSet)
                .filter(StrengthExerciseSet.activity_id == activity.id)
                .order_by(StrengthExerciseSet.set_order)
                .all()
            )
            result["exercise_sets"] = [
                {
                    "set_order": s.set_order,
                    "exercise_name": s.exercise_name_raw,
                    "exercise_category": s.exercise_category,
                    "movement_pattern": s.movement_pattern,
                    "muscle_group": s.muscle_group,
                    "is_unilateral": s.is_unilateral,
                    "set_type": s.set_type,
                    "reps": s.reps,
                    "weight_kg": s.weight_kg,
                    "duration_s": s.duration_s,
                    "estimated_1rm_kg": s.estimated_1rm_kg,
                }
                for s in sets
            ]

    # --- GPS track for map rendering ---
    gps_track = None
    start_coords = None

    if activity.start_lat is not None and activity.start_lng is not None:
        start_coords = [activity.start_lat, activity.start_lng]

    try:
        if activity.sport == "run":
            stream = db.query(ActivityStream).filter(
                ActivityStream.activity_id == activity.id
            ).first()
            if stream and "latlng" in (stream.channels_available or []):
                raw = stream.stream_data.get("latlng", [])
                gps_track = [pt for pt in raw if pt is not None]
        else:
            sd = activity.session_detail or {}
            samples = (sd.get("detail_webhook_raw") or {}).get("samples") or []
            if samples:
                gps_track = [
                    [s["latitudeInDegree"], s["longitudeInDegree"]]
                    for s in samples
                    if s.get("latitudeInDegree") is not None
                    and s.get("longitudeInDegree") is not None
                ]

        if gps_track and len(gps_track) > 50:
            try:
                from simplification.cutil import simplify_coords
                dist_m = float(activity.distance_m or 0)
                epsilon = max(dist_m / 5_000_000, 0.00002)
                gps_track = simplify_coords(gps_track, epsilon)
                if len(gps_track) > 2000:
                    step = len(gps_track) // 2000
                    gps_track = gps_track[::step]
            except ImportError:
                if len(gps_track) > 2000:
                    step = len(gps_track) // 2000
                    gps_track = gps_track[::step]

        if gps_track is not None:
            gps_track = [[round(pt[0], 6), round(pt[1], 6)] for pt in gps_track]
    except Exception:
        gps_track = None

    result["gps_track"] = gps_track
    result["start_coords"] = start_coords

    return result


@router.get("/{activity_id}/comparables")
def get_activity_comparables(
    activity_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Tier-based comparable runs for the activity-page comparison view.

    See ``services/comparison/comparable_runs.py`` for tier rules and
    suppression discipline. Returns:

    ```
    {
      "activity_id": "...",
      "activity_summary": {...},
      "block_summary": {...} | null,
      "tiers": [{"kind": "...", "label": "...", "entries": [...]}, ...],
      "suppressions": [{"kind": "...", "reason": "..."}, ...]
    }
    ```

    Empty ``tiers`` with populated ``suppressions`` is the honest answer
    when the activity has no comparable runs (fresh athlete, indoor
    workout, etc.). The frontend MUST NOT invent comparables when this
    endpoint is suppressing them.
    """
    from dataclasses import asdict
    from services.comparison import find_comparables_for_activity

    # Authorize: athlete must own the activity.
    activity = (
        db.query(Activity)
        .filter(Activity.id == activity_id, Activity.athlete_id == current_user.id)
        .first()
    )
    if activity is None:
        raise HTTPException(status_code=404, detail="activity not found")

    result = find_comparables_for_activity(db, activity_id)
    if result is None:
        raise HTTPException(status_code=404, detail="activity not found")

    # Convert dataclasses → JSON-friendly dicts (entries are nested dataclasses)
    return {
        "activity_id": result.activity_id,
        "activity_summary": result.activity_summary,
        "block_summary": result.block_summary,
        "tiers": [
            {
                "kind": t.kind,
                "label": t.label,
                "entries": [asdict(e) for e in t.entries],
            }
            for t in result.tiers
        ],
        "suppressions": result.suppressions,
    }


@router.get("/{activity_id}/route-siblings")
def get_route_siblings(
    activity_id: UUID,
    include_tracks: bool = Query(default=False),
    limit: int = Query(default=50, le=100),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Find activities from the same starting area at similar distance.

    Default: metadata only (count, dates, workout types).
    With ``include_tracks=true``: includes GPS polylines for ghost rendering.
    """
    from sqlalchemy import func

    activity = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.athlete_id == current_user.id,
    ).first()
    if not activity or activity.start_lat is None or activity.start_lng is None:
        return {"siblings": [], "count": 0, "conditions_match_count": 0}

    dist_m = float(activity.distance_m or 0)
    if dist_m <= 0:
        return {"siblings": [], "count": 0, "conditions_match_count": 0}

    siblings = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == current_user.id,
            Activity.sport == activity.sport,
            Activity.id != activity_id,
            Activity.is_duplicate == False,  # noqa: E712
            Activity.start_lat.isnot(None),
            func.abs(Activity.start_lat - activity.start_lat) < 0.005,
            func.abs(Activity.start_lng - activity.start_lng) < 0.005,
            func.abs(Activity.distance_m - dist_m) < dist_m * 0.15,
        )
        .order_by(Activity.start_time.desc())
        .limit(limit)
        .all()
    )

    conditions_match = 0
    for s in siblings:
        if s.start_time and activity.start_time:
            days_ago = (activity.start_time - s.start_time).days
            if days_ago <= 90:
                temp_match = (
                    s.dew_point_f is not None
                    and activity.dew_point_f is not None
                    and abs(s.dew_point_f - activity.dew_point_f) <= 10
                )
                type_match = s.workout_type == activity.workout_type
                if temp_match and type_match:
                    conditions_match += 1

    result_siblings = []
    for s in siblings:
        entry = {
            "id": str(s.id),
            "start_time": s.start_time.isoformat() if s.start_time else None,
            "distance_m": s.distance_m,
            "duration_s": s.duration_s,
            "temperature_f": s.temperature_f,
            "dew_point_f": s.dew_point_f,
            "heat_adjustment_pct": s.heat_adjustment_pct,
            "workout_type": s.workout_type,
            "avg_hr": s.avg_hr,
            "name": s.name,
            "total_elevation_gain": s.total_elevation_gain,
        }
        result_siblings.append(entry)

    resp = {
        "count": len(siblings),
        "conditions_match_count": conditions_match,
        "siblings": result_siblings,
    }

    if include_tracks:
        tracks = {}
        sibling_ids = [s.id for s in siblings[:30]]
        if sibling_ids:
            streams = (
                db.query(ActivityStream)
                .filter(ActivityStream.activity_id.in_(sibling_ids))
                .all()
            )
            for stream in streams:
                if "latlng" not in (stream.channels_available or []):
                    continue
                raw = stream.stream_data.get("latlng", [])
                pts = [pt for pt in raw if pt is not None]
                if not pts:
                    continue
                try:
                    from simplification.cutil import simplify_coords
                    dist = 0.0
                    for sib in siblings:
                        if sib.id == stream.activity_id:
                            dist = float(sib.distance_m or 0)
                            break
                    epsilon = max(dist / 3_000_000, 0.00003)
                    pts = simplify_coords(pts, epsilon)
                    if len(pts) > 500:
                        step = len(pts) // 500
                        pts = pts[::step]
                except ImportError:
                    if len(pts) > 500:
                        step = len(pts) // 500
                        pts = pts[::step]
                tracks[str(stream.activity_id)] = [
                    [round(p[0], 6), round(p[1], 6)] for p in pts
                ]
        resp["tracks"] = tracks

    return resp


@router.get("/{activity_id}/route-siblings/splits")
def get_route_sibling_splits(
    activity_id: UUID,
    sibling_ids: str = Query(..., description="Comma-separated sibling activity IDs"),
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lazy-load per-mile splits for route siblings.
    Called on expand of the route history panel to keep initial page load fast.
    """
    activity = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.athlete_id == current_user.id,
    ).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    ids = []
    for sid in sibling_ids.split(","):
        sid = sid.strip()
        if sid:
            try:
                ids.append(UUID(sid))
            except ValueError:
                continue

    ids = ids[:6]

    splits_by_activity = {}
    if ids:
        rows = (
            db.query(ActivitySplit)
            .filter(
                ActivitySplit.activity_id.in_(ids),
            )
            .order_by(ActivitySplit.activity_id, ActivitySplit.split_number)
            .all()
        )
        for row in rows:
            aid = str(row.activity_id)
            if aid not in splits_by_activity:
                splits_by_activity[aid] = []
            splits_by_activity[aid].append({
                "split_number": row.split_number,
                "distance": float(row.distance) if row.distance else None,
                "elapsed_time": row.elapsed_time,
                "moving_time": row.moving_time,
                "average_heartrate": row.average_heartrate,
                "gap_s_per_km": round(float(row.gap_seconds_per_mile) * 1000 / 1609.34, 2) if row.gap_seconds_per_mile else None,
            })

    current_splits = (
        db.query(ActivitySplit)
        .filter(ActivitySplit.activity_id == activity_id)
        .order_by(ActivitySplit.split_number)
        .all()
    )
    splits_by_activity[str(activity_id)] = [
        {
            "split_number": row.split_number,
            "distance": float(row.distance) if row.distance else None,
            "elapsed_time": row.elapsed_time,
            "moving_time": row.moving_time,
            "average_heartrate": row.average_heartrate,
            "gap_s_per_km": round(float(row.gap_seconds_per_mile) * 1000 / 1609.34, 2) if row.gap_seconds_per_mile else None,
        }
        for row in current_splits
    ]

    return {"splits_by_activity": splits_by_activity}


@router.put("/{activity_id}/title")
def update_activity_title(
    activity_id: UUID,
    body: ActivityTitleUpdate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the athlete's custom title for an activity."""
    activity = db.query(Activity).filter(
        Activity.id == activity_id,
    ).first()

    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found",
        )

    if activity.athlete_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not your activity",
        )

    activity.athlete_title = body.title
    db.commit()
    db.refresh(activity)

    return {
        "id": str(activity.id),
        "name": activity.name,
        "shape_sentence": activity.shape_sentence,
        "athlete_title": activity.athlete_title,
        "resolved_title": resolve_activity_title(activity),
    }


@router.get("/{activity_id}/attribution")
def get_activity_attribution(
    activity_id: str,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get attribution analysis for a specific activity - "Why This Run?"
    
    Aggregates signals from all analytics methods to explain the run's quality.
    Includes pace decay, TSB status, pre-run state, efficiency comparison, and CS analysis.
    
    ADR-015: Why This Run? Activity Attribution
    
    Requires feature flag: analytics.run_attribution
    """
    from services.run_attribution import get_run_attribution, run_attribution_to_dict
    
    # Check feature flag
    flag_enabled = is_feature_enabled("analytics.run_attribution", str(current_user.id), db)
    
    if not flag_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Run attribution feature is not enabled"
        )
    
    # Validate activity_id format
    try:
        UUID(activity_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid activity ID format"
        )
    
    # Get attribution
    result = get_run_attribution(activity_id, str(current_user.id), db)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found or no attribution available"
        )
    
    return run_attribution_to_dict(result)


@router.get("/{activity_id}/intelligence")
def get_activity_intelligence(
    activity_id: str,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Synthesized coaching summary for a single run.
    Assembles stream analysis, attribution, splits, classification,
    pre-state, and historical comparison into a headline + body.
    """
    from services.run_intelligence import generate_run_intelligence

    try:
        UUID(activity_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid activity ID format",
        )

    result = generate_run_intelligence(activity_id, str(current_user.id), db)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No intelligence available for this activity",
        )

    return {
        "headline": result.headline,
        "body": result.body,
        "highlights": [
            {"label": h.label, "value": h.value, "color": h.color}
            for h in result.highlights
        ],
    }


class FindingAnnotation(BaseModel):
    """A correlation finding relevant to a specific activity."""
    text: str
    domain: str
    confidence_tier: str
    evidence_summary: Optional[str] = None


_INPUT_TO_CHECKIN_FIELD = {
    "sleep_hours": "sleep_h",
    "sleep_quality_1_5": "sleep_quality_1_5",
    "hrv_rmssd": "hrv_rmssd",
    "stress_1_5": "stress_1_5",
    "readiness_1_5": "readiness_1_5",
    "soreness_1_5": "soreness_1_5",
    "motivation_1_5": "motivation_1_5",
    "resting_hr": "resting_hr",
}

_INPUT_TO_ACTIVITY_FIELD = {
    "sleep_hours": "pre_sleep_h",
    "hrv_rmssd": "pre_recovery_hrv",
}


def _build_prestate(activity: Activity, db: Session) -> dict:
    """Build actual pre-state values for this activity from checkin + activity fields."""
    from models import DailyCheckin
    from services.timezone_utils import get_athlete_timezone_from_db, to_activity_local_date

    values: dict = {}

    if activity.start_time:
        tz = get_athlete_timezone_from_db(db, activity.athlete_id)
        checkin = (
            db.query(DailyCheckin)
            .filter(
                DailyCheckin.athlete_id == activity.athlete_id,
                DailyCheckin.date == to_activity_local_date(activity, tz),
            )
            .first()
        )
        if checkin:
            for input_name, field in _INPUT_TO_CHECKIN_FIELD.items():
                val = getattr(checkin, field, None)
                if val is not None:
                    values[input_name] = float(val)

    for input_name, field in _INPUT_TO_ACTIVITY_FIELD.items():
        if input_name not in values:
            val = getattr(activity, field, None)
            if val is not None:
                values[input_name] = float(val)

    return values


def _finding_relevant(finding, actual_values: dict) -> bool:
    """Check if a finding's input condition was met for this activity's pre-state."""
    if finding.input_name not in actual_values:
        return False

    if finding.threshold_value is None:
        return True

    actual = actual_values[finding.input_name]
    if finding.threshold_direction == "below_matters":
        return actual < finding.threshold_value
    elif finding.threshold_direction == "above_matters":
        return actual > finding.threshold_value

    return True


@router.get("/{activity_id}/findings", response_model=List[FindingAnnotation])
def get_activity_findings(
    activity_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return up to 3 active findings relevant to this activity's actual pre-state.
    Zero findings is a valid answer — means no known patterns were triggered today.
    """
    from models import CorrelationFinding as _CF
    from services.fingerprint_context import _SUPPRESSED_SIGNALS, _ENVIRONMENT_SIGNALS

    activity = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.athlete_id == current_user.id,
    ).first()

    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    actual_values = _build_prestate(activity, db)

    _suppressed = _SUPPRESSED_SIGNALS | _ENVIRONMENT_SIGNALS
    candidates = (
        db.query(_CF)
        .filter(
            _CF.athlete_id == current_user.id,
            _CF.is_active.is_(True),
            _CF.times_confirmed >= 3,
            ~_CF.input_name.in_(_suppressed),
        )
        .order_by(_CF.times_confirmed.desc())
        .all()
    )

    from services.n1_insight_generator import _build_insight_text, _is_obvious

    result = []
    seen_inputs: set = set()
    for f in candidates:
        if not _finding_relevant(f, actual_values):
            continue

        has_threshold = f.threshold_value is not None
        if _is_obvious(f.input_name, f.output_metric, has_threshold=has_threshold):
            continue

        # Input diversity: one finding per input signal max
        if f.input_name in seen_inputs:
            continue

        text = _build_insight_text(
            input_name=f.input_name,
            direction=f.direction,
            strength="strong" if abs(f.correlation_coefficient) >= 0.5 else "moderate",
            r=f.correlation_coefficient,
            lag_days=f.time_lag_days,
            output_metric=f.output_metric,
            threshold_value=f.threshold_value,
            threshold_direction=f.threshold_direction,
            times_confirmed=f.times_confirmed,
        )
        if text is None:
            continue

        seen_inputs.add(f.input_name)
        tier = _af_tier_for(f.times_confirmed or 0).lower()
        evidence = (
            _af_evidence_phrase(f.times_confirmed) if f.times_confirmed else None
        )
        result.append(FindingAnnotation(
            text=text,
            domain=f.output_metric,
            confidence_tier=tier,
            evidence_summary=evidence,
        ))

        if len(result) >= 3:
            break

    return result
