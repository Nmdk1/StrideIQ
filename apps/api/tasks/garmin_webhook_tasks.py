"""
Garmin Webhook Celery Tasks (D5 implemented; D6 stubs remain)

Implementation status:
  process_garmin_activity_task        — D5.1 IMPLEMENTED (activity summary ingestion)
  process_garmin_activity_detail_task — D5.2 IMPLEMENTED (stream sample ingestion)
  process_garmin_health_task          — stub (D6 implements GarminDay upsert)
  process_garmin_deregistration_task  — stub (calls existing disconnect logic)
  process_garmin_permissions_task     — stub (handles permission change events)

Task names and signatures are FROZEN — webhook router and queued tasks depend on them.
Do not rename tasks; change internal logic only.

Payload shape contract [D4.3 pending live capture]:
  Garmin push payloads may arrive as a single dict OR a list of dicts.
  Both shapes are handled defensively. D4.3 live capture will confirm the actual
  envelope; D4 _parse_and_validate_push_payload will then be updated to match.

Source contract (D0/D3.3):
  This file must NOT contain raw Garmin API field names (camelCase API names).
  All Garmin→internal translation happens exclusively in services/garmin_adapter.py.

See docs/PHASE2_GARMIN_INTEGRATION_AC.md §D5, §D6
"""

import logging
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from tasks import celery_app
from core.cache import get_redis_client
from core.database import get_db_sync
from models import Activity, ActivitySplit, ActivityStream, Athlete, CorrelationFinding, GarminDay
from services.garmin_adapter import (
    adapt_activity_summary,
    adapt_activity_detail_envelope,
    adapt_activity_detail_laps,
    adapt_activity_detail_samples,
    adapt_sleep_summary,
    adapt_hrv_summary,
    adapt_stress_detail,
    adapt_daily_summary,
    adapt_user_metrics,
    _ACCEPTED_SPORTS,
)
from services.activity_deduplication import match_activities, TIME_WINDOW_S
from services.garmin_backfill import request_deep_garmin_backfill, request_garmin_backfill

logger = logging.getLogger(__name__)
_BACKFILL_PROGRESS_TTL_S = 24 * 60 * 60
_FIRST_SESSION_SWEEP_LOCK_TTL_S = 600
_BRIEFING_COALESCE_WINDOW_S = 45
_BRIEFING_PENDING_TTL_S = 180
_DEFERRED_DETAIL_TTL_S = 6 * 60 * 60
_DEFERRED_DETAIL_MAX_PER_ACTIVITY = 8


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_athlete_in_db(athlete_id: str, db) -> Optional[Athlete]:
    """Look up an Athlete by UUID string. Returns None if not found."""
    try:
        return (
            db.query(Athlete)
            .filter(Athlete.id == athlete_id)
            .first()
        )
    except Exception:
        return None


def _activity_to_dedup_dict(activity: Activity) -> Dict[str, Any]:
    """
    Convert an Activity ORM row to the internal-field-name dict that
    activity_deduplication.match_activities() expects.

    Only the three dedup keys are populated; all others are irrelevant.
    """
    return {
        "start_time": activity.start_time,
        "distance_m": float(activity.distance_m) if activity.distance_m is not None else None,
        "avg_hr": activity.avg_hr,
    }


def _apply_garmin_fields_to_activity(existing: Activity, adapted: Dict[str, Any]) -> None:
    """
    Override an existing Activity with Garmin data (provider precedence).

    Garmin is primary, Strava is secondary [F2]. When deduplication finds a
    match between a new Garmin activity and an existing Strava activity, the
    Garmin row wins: provider is set to "garmin" and Garmin-sourced fields
    populate the existing row. No second row is created.
    """
    existing.provider = "garmin"
    existing.external_activity_id = adapted.get("external_activity_id")
    existing.garmin_activity_id = adapted.get("garmin_activity_id")
    existing.source = adapted.get("source") or "garmin"

    _set_if_not_none(existing, "name", adapted.get("name"))
    _set_if_not_none(existing, "duration_s", adapted.get("duration_s"))
    _set_if_not_none(existing, "avg_hr", adapted.get("avg_hr"))
    _set_if_not_none(existing, "max_hr", adapted.get("max_hr"))
    _set_if_not_none(existing, "total_elevation_gain", adapted.get("total_elevation_gain"))
    _set_if_not_none(existing, "average_speed", adapted.get("average_speed"))
    _set_if_not_none(existing, "max_speed", adapted.get("max_speed"))
    _set_if_not_none(existing, "avg_cadence", adapted.get("avg_cadence"))
    _set_if_not_none(existing, "max_cadence", adapted.get("max_cadence"))
    _set_if_not_none(existing, "avg_pace_min_per_km", adapted.get("avg_pace_min_per_km"))
    _set_if_not_none(existing, "max_pace_min_per_km", adapted.get("max_pace_min_per_km"))
    _set_if_not_none(existing, "active_kcal", adapted.get("active_kcal"))
    _set_if_not_none(existing, "steps", adapted.get("steps"))
    _set_if_not_none(existing, "device_name", adapted.get("device_name"))
    _set_if_not_none(existing, "start_lat", adapted.get("start_lat"))
    _set_if_not_none(existing, "start_lng", adapted.get("start_lng"))
    _set_if_not_none(existing, "total_descent_m", adapted.get("total_descent_m"))

    # distance_m column is Integer; adapt_activity_summary returns float
    raw_dist = adapted.get("distance_m")
    if raw_dist is not None:
        existing.distance_m = int(round(raw_dist))


def _set_if_not_none(obj, attr: str, value: Any) -> None:
    if value is not None:
        setattr(obj, attr, value)


def _backfill_progress_key(athlete_id: str) -> str:
    return f"backfill_progress:{athlete_id}"


def _first_session_lock_key(athlete_id: str) -> str:
    return f"first_session_sweep_lock:{athlete_id}"


def _briefing_coalesce_key(athlete_id: str) -> str:
    return f"home_briefing_coalesce:{athlete_id}"


def _briefing_pending_key(athlete_id: str) -> str:
    return f"home_briefing_pending:{athlete_id}"


def _deferred_detail_key(athlete_id: str, garmin_activity_id: int) -> str:
    return f"garmin_detail_pending:{athlete_id}:{garmin_activity_id}"


def _defer_activity_detail_payload(
    athlete_id: str,
    garmin_activity_id: int,
    raw_item: Dict[str, Any],
) -> None:
    """
    Store out-of-order Garmin detail payloads until summary ingestion creates the
    parent Activity row. This closes the detail-before-summary webhook race.
    """
    r = get_redis_client()
    if not r:
        return
    key = _deferred_detail_key(str(athlete_id), int(garmin_activity_id))
    try:
        r.rpush(key, json.dumps(raw_item))
        # Bound memory per activity in pathological retry storms.
        r.ltrim(key, -_DEFERRED_DETAIL_MAX_PER_ACTIVITY, -1)
        r.expire(key, _DEFERRED_DETAIL_TTL_S)
    except Exception as exc:
        logger.warning(
            "Failed to defer Garmin detail payload athlete=%s garmin_activity_id=%s: %s",
            athlete_id,
            garmin_activity_id,
            exc,
        )


def _pop_deferred_activity_detail_payloads(
    athlete_id: str,
    garmin_activity_id: int,
) -> List[Dict[str, Any]]:
    """
    Read and clear deferred detail payloads for one Garmin activity.
    """
    r = get_redis_client()
    if not r:
        return []
    key = _deferred_detail_key(str(athlete_id), int(garmin_activity_id))
    try:
        raw_values = r.lrange(key, 0, -1) or []
        r.delete(key)
    except Exception:
        return []

    out: List[Dict[str, Any]] = []
    for raw in raw_values:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                out.append(parsed)
        except Exception:
            continue
    return out


def _replay_deferred_activity_details(
    athlete_id: str,
    garmin_activity_ids: List[int],
) -> int:
    """
    Enqueue deferred detail payloads after summary ingestion succeeds.
    Returns the number of payload dicts replayed.
    """
    replayed = 0
    for garmin_activity_id in garmin_activity_ids:
        payloads = _pop_deferred_activity_detail_payloads(athlete_id, int(garmin_activity_id))
        if not payloads:
            continue
        process_garmin_activity_detail_task.apply_async(
            args=[str(athlete_id), payloads],
            countdown=5,
        )
        replayed += len(payloads)
    return replayed


def _progress_hincr(athlete_id: str, field: str, amount: int) -> None:
    if amount <= 0:
        return
    r = get_redis_client()
    if not r:
        return
    key = _backfill_progress_key(athlete_id)
    r.hincrby(key, field, int(amount))
    r.expire(key, _BACKFILL_PROGRESS_TTL_S)


def _progress_hset(athlete_id: str, field: str, value: str) -> None:
    r = get_redis_client()
    if not r:
        return
    key = _backfill_progress_key(athlete_id)
    r.hset(key, field, value)
    r.expire(key, _BACKFILL_PROGRESS_TTL_S)


def _try_acquire_first_session_lock(athlete_id: str) -> bool:
    """Acquire idempotency lock; False means a sweep is already in-flight/recent."""
    r = get_redis_client()
    if not r:
        return True
    return bool(
        r.set(
            _first_session_lock_key(athlete_id),
            "1",
            ex=_FIRST_SESSION_SWEEP_LOCK_TTL_S,
            nx=True,
        )
    )


def _create_activity_from_adapted(adapted: Dict[str, Any], athlete_id) -> Activity:
    """
    Construct a new Activity ORM instance from an adapt_activity_summary() output dict.

    distance_m is stored as Integer (rounded from the float the adapter returns).
    """
    raw_dist = adapted.get("distance_m")
    return Activity(
        athlete_id=athlete_id,
        provider=adapted.get("provider", "garmin"),
        external_activity_id=adapted.get("external_activity_id"),
        garmin_activity_id=adapted.get("garmin_activity_id"),
        source=adapted.get("source") or "garmin",
        sport=adapted.get("sport", "run"),
        garmin_activity_type=adapted.get("garmin_activity_type"),
        cadence_unit=adapted.get("cadence_unit"),
        name=adapted.get("name"),
        start_time=adapted["start_time"],
        duration_s=adapted.get("duration_s"),
        distance_m=int(round(raw_dist)) if raw_dist is not None else None,
        avg_hr=adapted.get("avg_hr"),
        max_hr=adapted.get("max_hr"),
        total_elevation_gain=adapted.get("total_elevation_gain"),
        total_descent_m=adapted.get("total_descent_m"),
        average_speed=adapted.get("average_speed"),
        max_speed=adapted.get("max_speed"),
        avg_pace_min_per_km=adapted.get("avg_pace_min_per_km"),
        max_pace_min_per_km=adapted.get("max_pace_min_per_km"),
        avg_cadence=adapted.get("avg_cadence"),
        max_cadence=adapted.get("max_cadence"),
        active_kcal=adapted.get("active_kcal"),
        steps=adapted.get("steps"),
        device_name=adapted.get("device_name"),
        start_lat=adapted.get("start_lat"),
        start_lng=adapted.get("start_lng"),
        is_race_candidate=False,
    )


def _coalesced_home_briefing_refresh(athlete_id: str) -> None:
    """
    Coalesce burst health events into:
      - at most one active enqueue inside the coalesce window
      - at most one queued follow-up after the window
    """
    r = get_redis_client()
    if not r:
        # Fail open if Redis unavailable.
        from tasks.home_briefing_tasks import enqueue_briefing_refresh
        enqueue_briefing_refresh(str(athlete_id), force=True)
        return

    coalesce_key = _briefing_coalesce_key(str(athlete_id))
    pending_key = _briefing_pending_key(str(athlete_id))
    try:
        first_event_in_window = bool(r.set(coalesce_key, "1", nx=True, ex=_BRIEFING_COALESCE_WINDOW_S))
        r.setex(pending_key, _BRIEFING_PENDING_TTL_S, "1")
    except Exception:
        from tasks.home_briefing_tasks import enqueue_briefing_refresh
        enqueue_briefing_refresh(str(athlete_id), force=True)
        return

    if not first_event_in_window:
        return

    from services.home_briefing_cache import is_task_lock_held
    from tasks.home_briefing_tasks import enqueue_briefing_refresh

    # First event in burst: enqueue immediately when no active task.
    if not is_task_lock_held(str(athlete_id)):
        enqueue_briefing_refresh(str(athlete_id), force=True)

    # Always queue one bounded follow-up after window to pick up late health events.
    flush_home_briefing_followup_task.apply_async(
        args=[str(athlete_id)],
        countdown=_BRIEFING_COALESCE_WINDOW_S,
    )


# ---------------------------------------------------------------------------
# D6 helpers — GarminDay upsert
# ---------------------------------------------------------------------------

# Maps the webhook data_type string to the adapter function NAME (not the
# function object directly). Resolved via globals() at call time so that
# test patches on "tasks.garmin_webhook_tasks.adapt_*" are honoured correctly.
# Only Tier 1 data types are handled; unknown types are logged and skipped.
_HEALTH_ADAPTER_MAP: Dict[str, str] = {
    "sleeps": "adapt_sleep_summary",
    "hrv": "adapt_hrv_summary",
    "stress": "adapt_stress_detail",
    "dailies": "adapt_daily_summary",
    "user-metrics": "adapt_user_metrics",
}


def _parse_calendar_date(value):
    """
    Convert a calendar_date string ("YYYY-MM-DD") to a datetime.date object.

    Returns None if value is absent or unparseable.
    """
    if not value:
        return None
    try:
        from datetime import date as _date
        return _date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _upsert_garmin_day(athlete_id: str, calendar_date, adapted: Dict[str, Any], db) -> None:
    """
    Upsert a GarminDay row for (athlete_id, calendar_date).

    If a row already exists for that date, update only the non-None fields
    from the adapted dict (additive — fields from other data types are preserved).
    If no row exists, create one.

    The calendar_date field is the row key and is not written via setattr.
    """
    existing = (
        db.query(GarminDay)
        .filter(
            GarminDay.athlete_id == athlete_id,
            GarminDay.calendar_date == calendar_date,
        )
        .first()
    )

    if existing is not None:
        for key, value in adapted.items():
            if key == "calendar_date":
                continue
            if value is not None:
                setattr(existing, key, value)
    else:
        new_row = GarminDay(
            athlete_id=athlete_id,
            calendar_date=calendar_date,
        )
        for key, value in adapted.items():
            if key == "calendar_date":
                continue
            if value is not None:
                setattr(new_row, key, value)
        db.add(new_row)


def _ingest_health_item(
    raw_item: Dict[str, Any],
    data_type: str,
    athlete_id: str,
    db,
) -> bool:
    """
    Process a single Garmin health/wellness payload dict.

    Steps:
      1. Look up adapter function by data_type (unknown type → skip)
      2. Call adapter → internal-field-name dict (source contract)
      3. Extract and parse calendar_date (missing → skip)
      4. Upsert GarminDay row for (athlete_id, calendar_date)

    Returns True if processed, False if skipped.
    """
    fn_name = _HEALTH_ADAPTER_MAP.get(data_type)
    if fn_name is None:
        logger.warning(
            "_ingest_health_item: unknown data_type=%s — skipping (Tier 2 or unsupported)",
            data_type,
        )
        return False

    # Resolve via globals() so test patches on module-level names are honoured
    adapter_fn = globals()[fn_name]
    adapted = adapter_fn(raw_item)

    calendar_date = _parse_calendar_date(adapted.get("calendar_date"))
    if calendar_date is None:
        logger.warning(
            "_ingest_health_item: data_type=%s payload missing calendar_date — skipping",
            data_type,
        )
        return False

    _upsert_garmin_day(athlete_id, calendar_date, adapted, db)

    try:
        from models import Activity, Athlete
        from services.wellness_stamp import stamp_wellness
        athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
        tz_name = getattr(athlete, "timezone", None) if athlete else None
        unstamped = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete_id,
                Activity.pre_recovery_hrv.is_(None),
                Activity.start_time.isnot(None),
            )
            .all()
        )
        for act in unstamped:
            from services.wellness_stamp import _resolve_date
            if _resolve_date(act.start_time, tz_name) == calendar_date:
                stamp_wellness(act, db, athlete_timezone=tz_name)
    except Exception:
        logger.warning("Retro-stamp wellness on health ingest failed — non-fatal", exc_info=True)

    return True


def _ingest_activity_item(
    raw_item: Dict[str, Any],
    athlete: Athlete,
    db,
) -> str:
    """
    Process a single Garmin activity summary dict.

    Returns one of: "created", "updated", "skipped".

    Steps:
      1. adapt_activity_summary() → internal dict (adapter contract)
      2. Filter: sport must be "run"
      3. Idempotency: skip if already synced as Garmin activity (same external_activity_id)
      4. Time-window dedup against existing activities (for Strava precedence)
      5. Garmin wins if Strava duplicate found: update existing row, provider→"garmin"
      6. Otherwise: create new Activity row
    """
    adapted = adapt_activity_summary(raw_item)

    if adapted.get("sport") not in _ACCEPTED_SPORTS:
        logger.debug(
            "Skipping unmapped activity (sport=%s, type=%s, external_id=%s)",
            adapted.get("sport"),
            adapted.get("garmin_activity_type"),
            adapted.get("external_activity_id"),
        )
        return "skipped"

    external_id = adapted.get("external_activity_id")
    if not external_id:
        logger.warning("Activity missing external_activity_id — skipping")
        return "skipped"

    start_time = adapted.get("start_time")
    if start_time is None:
        logger.warning("Activity %s missing start_time — skipping", external_id)
        return "skipped"

    # --- Idempotency: already ingested as a Garmin activity ---
    existing_garmin = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete.id,
            Activity.provider == "garmin",
            Activity.external_activity_id == external_id,
        )
        .first()
    )
    if existing_garmin is not None:
        logger.debug("Garmin activity %s already ingested — skipping", external_id)
        return "skipped"

    # --- Time-window dedup: find any existing activity within ±1 hour ---
    from datetime import timedelta
    window_start = start_time - timedelta(seconds=TIME_WINDOW_S)
    window_end = start_time + timedelta(seconds=TIME_WINDOW_S)

    candidates = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete.id,
            Activity.start_time >= window_start,
            Activity.start_time <= window_end,
        )
        .all()
    )

    for candidate in candidates:
        candidate_dict = _activity_to_dedup_dict(candidate)
        if match_activities(adapted, candidate_dict):
            # Match found — Garmin is primary, update existing row regardless of provider
            logger.info(
                "Garmin activity %s matches existing %s activity (id=%s) — Garmin wins",
                external_id,
                candidate.provider,
                candidate.id,
            )
            _apply_garmin_fields_to_activity(candidate, adapted)
            try:
                from services.wellness_stamp import stamp_wellness
                tz_name = getattr(athlete, "timezone", None)
                stamp_wellness(candidate, db, athlete_timezone=tz_name)
            except Exception:
                logger.warning("Wellness stamp failed on garmin-update for %s — non-fatal", external_id, exc_info=True)
            if candidate.dew_point_f is None and candidate.start_lat is not None:
                try:
                    from services.weather_backfill import enrich_activity_weather
                    enrich_activity_weather(candidate, db)
                except Exception:
                    logger.warning("Weather enrichment failed on garmin-update for %s — non-fatal", external_id, exc_info=True)
            return "updated"

    # --- No match: create new Activity row ---
    new_activity = _create_activity_from_adapted(adapted, athlete.id)
    db.add(new_activity)
    try:
        from services.hr_backfill import backfill_hr_from_garmin
        backfill_hr_from_garmin(db, athlete.id, new_activity)
    except Exception:
        logger.warning("HR backfill failed for garmin activity %s — non-fatal", external_id, exc_info=True)

    try:
        from services.wellness_stamp import stamp_wellness
        tz_name = getattr(athlete, "timezone", None)
        stamp_wellness(new_activity, db, athlete_timezone=tz_name)
    except Exception:
        logger.warning("Wellness stamp failed for garmin activity %s — non-fatal", external_id, exc_info=True)

    try:
        from services.weather_backfill import enrich_activity_weather
        enrich_activity_weather(new_activity, db)
    except Exception:
        logger.warning("Weather enrichment failed for garmin activity %s — non-fatal", external_id, exc_info=True)

    # Race detection + workout classification — same logic as the Strava path.
    # Without this, Garmin activities are born with is_race_candidate=False and
    # workout_type=None, which means marathons, 5Ks, etc. are invisible to the
    # fitness bank's race performance tracking.
    try:
        from services.performance_engine import detect_race_candidate
        dist_m = float(new_activity.distance_m or 0)
        dur_s = new_activity.duration_s or new_activity.moving_time_s
        avg_hr = new_activity.avg_hr
        max_hr = new_activity.max_hr
        pace = None
        if dist_m > 0 and dur_s and dur_s > 0:
            pace = (dur_s / 60.0) / (dist_m / 1609.344)
        is_candidate, confidence = detect_race_candidate(
            activity_pace=pace,
            distance_meters=dist_m,
            duration_seconds=dur_s,
            avg_hr=avg_hr,
            max_hr=max_hr,
            splits=[],
            activity_name=new_activity.name,
        )
        if is_candidate:
            new_activity.is_race_candidate = True
            new_activity.race_confidence = confidence
            logger.info("Garmin activity %s flagged as race candidate (conf=%.2f)", external_id, confidence)
    except Exception:
        logger.warning("Race detection failed for garmin activity %s — non-fatal", external_id, exc_info=True)

    # Classify workout type (long_run, easy_run, threshold_run, race, etc.)
    # This is what populates `activity.workout_type` for the comparison
    # service to find same-type matches.  Previously this was called as a
    # class method without instantiation -- it threw TypeError on every
    # Garmin ingest, was swallowed by the broad except, and every Garmin
    # activity went to disk with workout_type=NULL.  That single bug is
    # what made the Compare tab return "no similar runs" for every Garmin-
    # primary athlete, because tiers 3 and 4 both gate on workout_type.
    try:
        from services.workout_classifier import WorkoutClassifierService

        classifier = WorkoutClassifierService(db)
        classification = classifier.classify_activity(new_activity)
        new_activity.workout_type = classification.workout_type.value
        new_activity.workout_zone = classification.workout_zone.value
        new_activity.workout_confidence = classification.confidence
        new_activity.intensity_score = classification.intensity_score
    except Exception:
        logger.warning(
            "Workout classification failed for garmin activity %s — non-fatal",
            external_id,
            exc_info=True,
        )

    return "created"


def _ingest_activity_detail_item(
    raw_item: Dict[str, Any],
    athlete_id: str,
    db,
) -> bool:
    """Bool wrapper around :func:`_ingest_activity_detail_item_full`.

    Existing call sites and tests (e.g. ``test_garmin_splits.py``) treat the
    return value as a strict bool (``assert result is True``). The richer
    helper below additionally returns the resolved Activity row so the
    Celery task can chain follow-up work without re-querying.
    """
    _, was_processed = _ingest_activity_detail_item_full(raw_item, athlete_id, db)
    return was_processed


def _ingest_activity_detail_item_full(
    raw_item: Dict[str, Any],
    athlete_id: str,
    db,
):
    """
    Process a single Garmin ClientActivityDetail dict: extract samples,
    build ActivityStream row, link to parent Activity via garmin_activity_id.

    Returns ``(activity, was_processed)`` where ``activity`` is the matched
    Activity row (or ``None`` if no row was matched) and ``was_processed``
    is True if work was performed (stream upsert, lap split write, or the
    "unavailable" fail-closed path), False if the item was skipped.
    """
    # All Garmin→internal field name translation delegated to adapter (source contract)
    envelope = adapt_activity_detail_envelope(raw_item)
    garmin_activity_id_int = envelope.get("garmin_activity_id")

    if garmin_activity_id_int is None:
        logger.warning("Activity detail missing or invalid garmin_activity_id — skipping")
        return None, False

    # Find parent Activity by garmin_activity_id
    activity = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.garmin_activity_id == garmin_activity_id_int,
        )
        .first()
    )
    if activity is None:
        _defer_activity_detail_payload(athlete_id, garmin_activity_id_int, raw_item)
        logger.warning(
            "Activity detail for unknown garmin_activity_id=%s (athlete=%s) — deferred",
            garmin_activity_id_int,
            athlete_id,
        )
        return None, False

    if activity.sport != "run":
        activity.session_detail = {
            **(activity.session_detail or {}),
            "detail_webhook_raw": raw_item,
        }
        logger.info(
            "Non-run detail stored in session_detail for garmin_activity_id=%s (sport=%s)",
            garmin_activity_id_int,
            activity.sport,
        )
        return activity, True

    samples = envelope.get("samples") or []

    # Determine early whether laps exist — both samples and laps are optional,
    # but at least one must be present to do useful work.
    lap_splits = adapt_activity_detail_laps(raw_item, samples)

    if not samples and not lap_splits:
        logger.info(
            "garmin_activity_detail_empty garmin_activity_id=%s activity_id=%s — marking unavailable and enqueueing strava fallback",
            garmin_activity_id_int,
            activity.id,
        )
        activity.stream_fetch_status = "unavailable"
        activity.stream_fetch_error = "garmin_detail_empty_no_samples_or_laps"
        # Mirror the cleanup-beat behavior: every fail-closed Garmin row gets
        # one shot at Strava-side repair.  Without this, the webhook path
        # silently accepts permanent emptiness while the timeout path heals
        # itself — that asymmetry is the regression that broke Larry's run
        # and lit up "no chart" for athletes whose detail webhook returns
        # an empty envelope.  Best-effort enqueue: a broker hiccup must not
        # roll back the activity row.
        try:
            from tasks.strava_fallback_tasks import (
                repair_garmin_activity_from_strava_task,
            )

            repair_garmin_activity_from_strava_task.delay(str(activity.id))
        except Exception as enqueue_exc:  # pragma: no cover - logged only
            logger.warning(
                "strava_fallback_enqueue_failed_from_webhook activity_id=%s error=%s",
                activity.id,
                enqueue_exc,
            )
        return activity, True

    # All Garmin→internal channel translation delegated to adapter (source contract)
    if samples:
        activity_start_unix = (
            activity.start_time.timestamp() if activity.start_time else 0.0
        )
        stream_data = adapt_activity_detail_samples(samples, activity_start_unix)
        channels = list(stream_data.keys())
        point_count = max((len(v) for v in stream_data.values()), default=0)

        # Upsert ActivityStream (one row per activity)
        existing_stream = (
            db.query(ActivityStream)
            .filter(ActivityStream.activity_id == activity.id)
            .first()
        )
        if existing_stream is not None:
            existing_stream.stream_data = stream_data
            existing_stream.channels_available = channels
            existing_stream.point_count = point_count
            existing_stream.source = "garmin"
        else:
            new_stream = ActivityStream(
                activity_id=activity.id,
                stream_data=stream_data,
                channels_available=channels,
                point_count=point_count,
                source="garmin",
            )
            db.add(new_stream)

    activity.stream_fetch_status = "success"

    # Living Fingerprint: extract shape + generate sentence
    if samples and stream_data:
        try:
            from services.shape_extractor import (
                extract_shape, generate_shape_sentence,
                pace_profile_from_training_paces, pace_profile_from_rpi,
            )
            from models import Athlete as _AthModel
            from tasks.strava_tasks import _resolve_pace_profile, _get_median_duration

            ath = db.query(_AthModel).filter(_AthModel.id == athlete_id).first()
            pace_prof = _resolve_pace_profile(ath, db) if ath else None

            heat_adj = float(activity.heat_adjustment_pct) if activity.heat_adjustment_pct else None
            median_dur = _get_median_duration(athlete_id, db)
            shape = extract_shape(stream_data, pace_profile=pace_prof, heat_adjustment_pct=heat_adj, median_duration_s=median_dur)
            if shape:
                activity.run_shape = shape.to_dict()
                total_dist = float(activity.distance_m) if activity.distance_m else 0
                total_dur = float(activity.duration_s or 0)
                median_dur = _get_median_duration(athlete_id, db)
                use_km = getattr(ath, 'preferred_units', 'imperial') == 'metric' if ath else False
                activity.shape_sentence = generate_shape_sentence(
                    shape, total_dist, total_dur,
                    pace_profile=pace_prof,
                    median_duration_s=median_dur,
                    use_km=use_km,
                )
        except Exception as shape_exc:
            logger.warning("Garmin shape extraction failed for %s: %s", garmin_activity_id_int, shape_exc)

    # --- Lap splits (idempotent: delete-then-create) ---
    # lap_splits was computed before the samples block to allow early-return logic above.
    if lap_splits:
        db.query(ActivitySplit).filter(
            ActivitySplit.activity_id == activity.id
        ).delete(synchronize_session=False)
        from services.interval_detector import detect_interval_structure
        analysis = detect_interval_structure(lap_splits)

        for ls in analysis.labeled_splits:
            db.add(ActivitySplit(
                activity_id=activity.id,
                split_number=ls.split_number,
                distance=ls.distance,
                elapsed_time=ls.elapsed_time,
                moving_time=ls.moving_time,
                average_heartrate=ls.average_heartrate,
                max_heartrate=ls.max_heartrate,
                average_cadence=ls.average_cadence,
                gap_seconds_per_mile=ls.gap_seconds_per_mile,
                lap_type=ls.lap_type,
                interval_number=ls.interval_number,
            ))
        logger.info(
            "Created %d splits (structured=%s) for garmin_activity_id=%s",
            len(lap_splits), analysis.summary.is_structured, garmin_activity_id_int,
        )

        # Re-run race detection now that splits are available.
        # The summary webhook runs detection with splits=[] (they don't exist yet),
        # so this is the first opportunity to score pace consistency and effort profile.
        if not activity.is_race_candidate:
            try:
                from services.performance_engine import detect_race_candidate
                _dist_m = float(activity.distance_m or 0)
                _dur_s = activity.duration_s or activity.moving_time_s
                _pace = None
                if _dist_m > 0 and _dur_s and _dur_s > 0:
                    _pace = (_dur_s / 60.0) / (_dist_m / 1609.344)
                is_candidate, confidence = detect_race_candidate(
                    activity_pace=_pace,
                    distance_meters=_dist_m,
                    duration_seconds=_dur_s,
                    avg_hr=activity.avg_hr,
                    max_hr=activity.max_hr,
                    splits=lap_splits,
                    activity_name=activity.name,
                )
                if is_candidate:
                    activity.is_race_candidate = True
                    activity.race_confidence = confidence
                    logger.info(
                        "Race re-detection with splits: garmin_activity_id=%s flagged (conf=%.2f)",
                        garmin_activity_id_int, confidence,
                    )
            except Exception:
                logger.warning(
                    "Race re-detection failed for garmin_activity_id=%s — non-fatal",
                    garmin_activity_id_int, exc_info=True,
                )

    return activity, True


# ---------------------------------------------------------------------------
# D5.1: Activity summary ingestion task
# ---------------------------------------------------------------------------

@celery_app.task(
    name="process_garmin_activity_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    rate_limit='6/m',
)
def process_garmin_activity_task(
    self,
    athlete_id: str,
    payload: Any,
) -> Dict[str, Any]:
    """
    Ingest Garmin activity summary/summaries from a push webhook.

    Handles both single-dict and list payload shapes defensively [D4.3 pending].

    Steps per activity item:
      1. adapt_activity_summary() — Garmin→internal field translation
      2. Filter: sport must be in _ACCEPTED_SPORTS (run, cycling, walking, hiking, strength, flexibility)
      3. Idempotency: skip if already synced as Garmin (same external_activity_id)
      4. Deduplication: time-window check against existing activities
      5. Garmin wins on dedup match: update existing row, provider→"garmin"
      6. No match: create new Activity row
      7. Update athlete.last_garmin_sync

    Token refresh: not required for webhook payload processing.
    Payloads arrive pre-authenticated via the webhook.

    Args:
        athlete_id: Internal athlete UUID string.
        payload: Raw Garmin push webhook payload — dict or list of dicts.

    Returns:
        {"status": "ok", "created": int, "updated": int, "skipped": int}
    """
    db = get_db_sync()
    try:
        athlete = _find_athlete_in_db(athlete_id, db)
        if athlete is None:
            logger.warning(
                "process_garmin_activity_task: athlete %s not found", athlete_id
            )
            return {"status": "skipped", "reason": "athlete_not_found"}

        # Normalize payload shape — Garmin may send dict or list [D4.3 pending]
        items: List[Dict[str, Any]] = payload if isinstance(payload, list) else [payload]

        created = 0
        updated = 0
        skipped = 0
        replay_candidates: List[int] = []

        for raw_item in items:
            result = _ingest_activity_item(raw_item, athlete, db)
            if result == "created":
                created += 1
                adapted = adapt_activity_summary(raw_item)
                garmin_activity_id = adapted.get("garmin_activity_id")
                if isinstance(garmin_activity_id, int):
                    replay_candidates.append(garmin_activity_id)
            elif result == "updated":
                updated += 1
                adapted = adapt_activity_summary(raw_item)
                garmin_activity_id = adapted.get("garmin_activity_id")
                if isinstance(garmin_activity_id, int):
                    replay_candidates.append(garmin_activity_id)
            else:
                skipped += 1

        athlete.last_garmin_sync = datetime.now(tz=timezone.utc)
        db.commit()
        from core.cache import invalidate_athlete_cache
        invalidate_athlete_cache(str(athlete_id))

        replayed_detail_payloads = 0
        if replay_candidates:
            replayed_detail_payloads = _replay_deferred_activity_details(
                str(athlete_id),
                replay_candidates,
            )
            if replayed_detail_payloads > 0:
                logger.info(
                    "Replayed %d deferred Garmin detail payload(s) for athlete=%s",
                    replayed_detail_payloads,
                    athlete_id,
                )
        # Ensure home coach briefing reflects newly ingested activities.
        # We only trigger when data actually changed (created/updated), not for all-skipped payloads.
        if created > 0 or updated > 0:
            # Progress contract for first-session UX.
            try:
                _progress_hincr(str(athlete_id), "activities_ingested", created + updated)
            except Exception:
                pass
            try:
                from services.home_briefing_cache import mark_briefing_dirty
                from tasks.home_briefing_tasks import enqueue_briefing_refresh

                mark_briefing_dirty(str(athlete_id))
                enqueue_briefing_refresh(
                    str(athlete_id),
                    force=True,
                    allow_circuit_probe=True,
                )
            except Exception as refresh_exc:
                logger.warning(
                    "Garmin briefing refresh trigger failed for athlete %s: %s",
                    athlete_id,
                    refresh_exc,
                )

            # First-session trigger: meaningful initial batch and no existing findings.
            if created + updated >= 3:
                try:
                    from tasks.correlation_tasks import run_athlete_first_session_sweep
                    has_finding = (
                        db.query(CorrelationFinding.id)
                        .filter(CorrelationFinding.athlete_id == athlete.id)
                        .first()
                    )
                    if not has_finding:
                        if _try_acquire_first_session_lock(str(athlete_id)):
                            run_athlete_first_session_sweep.apply_async(
                                args=[str(athlete_id)],
                                countdown=30,
                            )
                            logger.info(
                                "First-session sweep enqueued for athlete %s (created=%d updated=%d)",
                                athlete_id,
                                created,
                                updated,
                            )
                        else:
                            logger.info(
                                "First-session sweep enqueue skipped (lock held) for athlete %s",
                                athlete_id,
                            )
                except Exception as sweep_exc:
                    logger.warning(
                        "First-session sweep trigger failed for athlete %s: %s",
                        athlete_id,
                        sweep_exc,
                    )

        # Runtoon generation is on-demand only (athlete taps "Share Your Run").
        # Auto-generation removed per RUNTOON_SHARE_FLOW_SPEC.md — Mar 2026.

        logger.info(
            "process_garmin_activity_task: athlete=%s created=%d updated=%d skipped=%d replayed_detail_payloads=%d",
            athlete_id,
            created,
            updated,
            skipped,
            replayed_detail_payloads,
        )
        return {"status": "ok", "created": created, "updated": updated, "skipped": skipped}

    except Exception as exc:
        db.rollback()
        logger.exception(
            "process_garmin_activity_task failed for athlete %s: %s", athlete_id, exc
        )
        raise self.retry(exc=exc)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# D5.2: Activity detail / stream ingestion task
# ---------------------------------------------------------------------------

@celery_app.task(
    name="process_garmin_activity_detail_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def process_garmin_activity_detail_task(
    self,
    athlete_id: str,
    payload: Any,
) -> Dict[str, Any]:
    """
    Ingest Garmin activity detail samples from a push webhook.

    Handles both single-dict and list payload shapes defensively [D4.3 pending].

    Steps per detail item:
      1. Find parent Activity by garmin_activity_id
      2. Extract sample channels via adapt_activity_detail_samples() (adapter contract)
         Channels: time (relative), heartrate, watts, latlng, altitude,
                   velocity_smooth, cadence
      3. Upsert ActivityStream row (source="garmin")
      4. Set activity.stream_fetch_status = "success"

    Running dynamics (stride length, GCT, vertical oscillation, ratio) are
    FIT-file-only and NOT present in JSON API samples — not mapped [D5.3 resolved].

    Args:
        athlete_id: Internal athlete UUID string.
        payload: Raw Garmin ClientActivityDetail payload — dict or list of dicts.

    Returns:
        {"status": "ok", "processed": int}
    """
    db = get_db_sync()
    try:
        # Normalize payload shape
        items: List[Dict[str, Any]] = payload if isinstance(payload, list) else [payload]

        processed = 0
        processed_activity_ids: List[Any] = []
        for raw_item in items:
            # Use the richer helper so we get the Activity row back without a
            # second DB roundtrip. This also keeps Garmin field names out of
            # the task module (enforced by
            # tests/test_garmin_d5_activity_sync.py::TestSourceContract).
            activity_row, ingested = _ingest_activity_detail_item_full(
                raw_item, athlete_id, db
            )
            if ingested:
                processed += 1
                db.commit()
                if activity_row is not None:
                    processed_activity_ids.append(activity_row.id)

        # --- ROUTE FINGERPRINT (Phase 2 of comparison family) ---
        for act_id in processed_activity_ids:
            try:
                from services.routes.route_fingerprint import compute_for_activity
                compute_for_activity(db, act_id)
            except Exception as exc:  # pragma: no cover — defensive
                logger.warning("route_fingerprint_failed activity_id=%s err=%s", act_id, exc)
                db.rollback()

        logger.info(
            "process_garmin_activity_detail_task: athlete=%s processed=%d",
            athlete_id,
            processed,
        )
        return {"status": "ok", "processed": processed}

    except Exception as exc:
        db.rollback()
        logger.exception(
            "process_garmin_activity_detail_task failed for athlete %s: %s",
            athlete_id,
            exc,
        )
        raise self.retry(exc=exc)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# D7: Initial backfill task
# ---------------------------------------------------------------------------

@celery_app.task(
    name="request_garmin_backfill_task",
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5-minute retry on transient failures
)
def request_garmin_backfill_task(self, athlete_id: str) -> Dict[str, Any]:
    """
    Request a 90-day Garmin backfill for a newly connected athlete.

    Triggered automatically after a successful OAuth callback (D7.2).
    Calls each Tier 1 backfill endpoint sequentially — Garmin returns 202
    Accepted immediately and pushes historical data to the D4 webhook endpoints
    asynchronously. The D5/D6 handlers process arriving data identically to
    live webhook pushes.

    Does NOT block the OAuth callback or wait for any data to arrive.

    Args:
        athlete_id: Internal athlete UUID string.

    Returns:
        {"status": "ok"|"skipped"|"aborted", "requested": int, "failed": int}
    """
    db = get_db_sync()
    try:
        athlete = _find_athlete_in_db(athlete_id, db)
        if athlete is None:
            logger.warning(
                "request_garmin_backfill_task: athlete %s not found", athlete_id
            )
            return {"status": "skipped", "reason": "athlete_not_found"}

        result = request_garmin_backfill(athlete, db)
        logger.info(
            "request_garmin_backfill_task: athlete=%s result=%s", athlete_id, result
        )
        return result

    except Exception as exc:
        db.rollback()
        logger.exception(
            "request_garmin_backfill_task failed for athlete %s: %s", athlete_id, exc
        )
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    name="request_deep_garmin_backfill_task",
    bind=True,
    max_retries=2,
    default_retry_delay=600,
    time_limit=900,
    soft_time_limit=840,
)
def request_deep_garmin_backfill_task(
    self,
    athlete_id: str,
    target_days_back: int = 730,
) -> Dict[str, Any]:
    """
    Request deep Garmin history in rolling windows (up to target_days_back).
    """
    from datetime import timedelta

    db = get_db_sync()
    try:
        athlete = _find_athlete_in_db(athlete_id, db)
        if athlete is None:
            return {"status": "skipped", "reason": "athlete_not_found"}

        target_start = datetime.now(timezone.utc) - timedelta(days=target_days_back)
        result = request_deep_garmin_backfill(
            athlete,
            db,
            target_start=target_start,
            inter_window_delay_s=3.0,
        )
        return result
    except Exception as exc:
        db.rollback()
        logger.exception("request_deep_garmin_backfill_task failed for athlete %s: %s", athlete_id, exc)
        raise self.retry(exc=exc)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# D6: health tasks — implemented in D6
# ---------------------------------------------------------------------------

@celery_app.task(
    name="process_garmin_health_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    rate_limit='10/m',
)
def process_garmin_health_task(
    self,
    athlete_id: str,
    data_type: str,
    payload: Dict[str, Any],
) -> None:
    """
    Upsert Garmin health/wellness payload(s) into GarminDay.

    Handles both single-dict and list payload shapes defensively [D4.3 pending].

    Supported data_type values (Tier 1):
      "sleeps"       → adapt_sleep_summary()  → sleep duration, score, stages
      "hrv"          → adapt_hrv_summary()    → overnight avg, 5-min high
      "stress"       → adapt_stress_detail()  → avg/max stress, JSONB samples
      "dailies"      → adapt_daily_summary()  → steps, resting HR, active kcal
      "user-metrics" → adapt_user_metrics()   → vo2max

    Upsert contract: INSERT on (athlete_id, calendar_date) if no row exists;
    UPDATE only non-None fields from the adapter output if row exists (additive).
    Stress values are stored as-is including negatives; filter at query time.

    Calendar date rule (L1): sleep calendar_date is the wakeup morning (Saturday
    for Friday-night sleep). Adapter preserves this; task stores it directly.

    Args:
        athlete_id: Internal athlete UUID string.
        data_type: Webhook data type string matching the route path segment.
        payload: Raw Garmin health payload — dict or list of dicts.

    Returns:
        {"status": "ok", "processed": int, "skipped": int}
    """
    db = get_db_sync()
    try:
        # Normalize payload shape — Garmin may send dict or list [D4.3 pending]
        items: List[Dict[str, Any]] = payload if isinstance(payload, list) else [payload]

        processed = 0
        skipped = 0

        for raw_item in items:
            if _ingest_health_item(raw_item, data_type, athlete_id, db):
                processed += 1
                db.commit()
            else:
                skipped += 1

        # Health data can materially change home coaching context (sleep/HRV/stress).
        # Trigger a briefing refresh when new health records were processed.
        if processed > 0:
            # Progress contract for first-session UX.
            try:
                _progress_hincr(str(athlete_id), "health_records_ingested", processed)
            except Exception:
                pass
            try:
                from services.home_briefing_cache import mark_briefing_dirty

                mark_briefing_dirty(str(athlete_id))
                _coalesced_home_briefing_refresh(str(athlete_id))
            except Exception as refresh_exc:
                logger.warning(
                    "Garmin health briefing refresh trigger failed for athlete %s: %s",
                    athlete_id,
                    refresh_exc,
                )

        logger.info(
            "process_garmin_health_task: athlete=%s data_type=%s processed=%d skipped=%d",
            athlete_id,
            data_type,
            processed,
            skipped,
        )
        return {"status": "ok", "processed": processed, "skipped": skipped}

    except Exception as exc:
        db.rollback()
        logger.exception(
            "process_garmin_health_task failed for athlete %s data_type %s: %s",
            athlete_id,
            data_type,
            exc,
        )
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    name="flush_home_briefing_followup_task",
    bind=True,
    max_retries=8,
    default_retry_delay=15,
)
def flush_home_briefing_followup_task(self, athlete_id: str) -> Dict[str, Any]:
    """
    Execute one bounded follow-up refresh after a webhook burst.
    Retries while an active briefing generation lock is held.
    """
    from services.home_briefing_cache import is_task_lock_held
    from tasks.home_briefing_tasks import enqueue_briefing_refresh

    r = get_redis_client()
    if not r:
        enqueue_briefing_refresh(str(athlete_id), force=True)
        return {"status": "ok", "reason": "redis_unavailable_fail_open"}

    pending_key = _briefing_pending_key(str(athlete_id))
    try:
        if not r.exists(pending_key):
            return {"status": "ok", "reason": "no_pending"}

        if is_task_lock_held(str(athlete_id)):
            raise self.retry()

        enqueue_briefing_refresh(str(athlete_id), force=True)
        r.delete(pending_key)
        return {"status": "ok", "reason": "followup_enqueued"}
    except self.MaxRetriesExceededError:
        logger.warning("Follow-up briefing flush exceeded retries for athlete %s", athlete_id)
        return {"status": "error", "reason": "max_retries_exceeded"}


@celery_app.task(
    name="process_garmin_deregistration_task",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def process_garmin_deregistration_task(
    self,
    athlete_id: str,
    payload: Dict[str, Any],
) -> None:
    """
    Handle a Garmin deregistration ping.

    Garmin sends this when a user disconnects from StrideIQ via the Garmin
    Connect app (not via StrideIQ's disconnect flow). Triggers the same
    soft-disconnect logic as POST /v1/garmin/disconnect but initiated by Garmin.

    Implementation: call the existing disconnect endpoint logic:
      - Clear OAuth tokens
      - Set garmin_connected=False
      - Write consent_audit_log entry (source="garmin_initiated")
      - Do NOT delete GarminDay or activities (soft disconnect)
    """
    logger.info(
        "[D5 STUB] process_garmin_deregistration_task",
        extra={"athlete_id": athlete_id},
    )


@celery_app.task(
    name="process_garmin_permissions_task",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def process_garmin_permissions_task(
    self,
    athlete_id: str,
    payload: Dict[str, Any],
) -> None:
    """
    Handle a Garmin user permissions change ping.

    Garmin sends this when an athlete changes their data sharing permissions
    in the Garmin Connect app (e.g., revokes ACTIVITY_EXPORT). Triggers a
    permission re-check and adjusts sync scope accordingly.

    Implementation:
      - Call GET /rest/user/permissions via garmin_oauth.get_user_permissions()
      - If ACTIVITY_EXPORT or HEALTH_EXPORT revoked: log warning, adjust sync
      - Write a note to the athlete's account (non-blocking)
    """
    logger.info(
        "[D5 STUB] process_garmin_permissions_task",
        extra={"athlete_id": athlete_id},
    )


# ---------------------------------------------------------------------------
# Activity File Processing — FIT file pipeline
# ---------------------------------------------------------------------------

_FIT_DOWNLOAD_TIMEOUT_S = 30


@celery_app.task(
    name="process_garmin_activity_file_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    rate_limit="5/m",
)
def process_garmin_activity_file_task(
    self,
    athlete_id: str,
    record: Dict[str, Any],
) -> Dict[str, Any]:
    """Download FIT file from Garmin callback URL and extract exercise sets.

    Triggered by the activity-files webhook.  The record contains a
    callbackURL with a temporary download token.  We download the binary
    FIT file, parse exercise sets via fitparse, match to the existing
    Activity, and feed into the strength parser pipeline.
    """
    import requests as http_requests
    from services.garmin_adapter import adapt_activity_file_record

    adapted = adapt_activity_file_record(record)
    callback_url = adapted["callback_url"]
    if not callback_url:
        logger.warning(
            "process_activity_file: no callbackURL in record for athlete %s — keys: %s",
            athlete_id,
            list(record.keys()),
        )
        return {"status": "skipped", "reason": "no_callback_url"}

    summary_id = adapted["summary_id"]
    file_type = adapted["file_type"]

    logger.info(
        "process_activity_file: downloading %s file for athlete=%s summary=%s",
        file_type, athlete_id, summary_id,
    )

    try:
        resp = http_requests.get(callback_url, timeout=_FIT_DOWNLOAD_TIMEOUT_S)
    except Exception as exc:
        logger.error(
            "process_activity_file: download failed for athlete=%s summary=%s: %s",
            athlete_id, summary_id, exc,
        )
        raise self.retry(exc=exc)

    if resp.status_code != 200:
        logger.warning(
            "process_activity_file: download returned %d for athlete=%s summary=%s",
            resp.status_code, athlete_id, summary_id,
        )
        if resp.status_code >= 500:
            raise self.retry(countdown=60)
        return {"status": "error", "http_code": resp.status_code}

    fit_bytes = resp.content
    logger.info(
        "process_activity_file: downloaded %d bytes for athlete=%s summary=%s",
        len(fit_bytes), athlete_id, summary_id,
    )

    from services.fit_parser import extract_exercise_sets_from_fit
    parsed_data = extract_exercise_sets_from_fit(fit_bytes)

    exercise_sets = parsed_data.get("exerciseSets", [])
    active_sets = [s for s in exercise_sets if s.get("setType") == "ACTIVE"]

    if not active_sets:
        logger.info(
            "process_activity_file: no active exercise sets in FIT file for athlete=%s summary=%s (total messages: %d)",
            athlete_id, summary_id, len(exercise_sets),
        )
        return {"status": "ok", "reason": "no_exercise_sets", "file_type": file_type}

    db = get_db_sync()
    try:
        activity = None

        if summary_id:
            activity = (
                db.query(Activity)
                .filter(
                    Activity.athlete_id == athlete_id,
                    Activity.garmin_activity_id == str(summary_id),
                )
                .first()
            )

        if activity is None and summary_id:
            activity = (
                db.query(Activity)
                .filter(
                    Activity.athlete_id == athlete_id,
                    Activity.external_id == str(summary_id),
                )
                .first()
            )

        if activity is None:
            logger.warning(
                "process_activity_file: no matching activity for athlete=%s summary=%s — retrying",
                athlete_id, summary_id,
            )
            raise self.retry(countdown=30)

        if activity.sport != "strength":
            logger.info(
                "process_activity_file: activity %s is %s, not strength — skipping exercise parsing",
                activity.id, activity.sport,
            )
            return {"status": "ok", "reason": "not_strength", "sport": activity.sport}

        from services.strength_parser import process_strength_activity
        result = process_strength_activity(db, activity, parsed_data)
        db.commit()

        logger.info(
            "Exercise sets from FIT file processed for activity=%s: %d sets, type=%s",
            activity.id,
            result["sets_written"],
            result["session_type"],
        )

        if result.get("unknown_exercises"):
            logger.warning(
                "Unknown exercises in FIT file for activity=%s: %s",
                activity.id,
                result["unknown_exercises"],
            )

        return {
            "status": "ok",
            "activity_id": str(activity.id),
            "sets_written": result["sets_written"],
            "session_type": result["session_type"],
        }

    except self.MaxRetriesExceededError:
        logger.error(
            "process_activity_file: max retries for athlete=%s summary=%s",
            athlete_id, summary_id,
        )
        return {"status": "error", "reason": "max_retries_exceeded"}
    finally:
        db.close()
