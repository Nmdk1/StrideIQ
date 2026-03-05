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
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from tasks import celery_app
from core.database import get_db_sync
from models import Activity, ActivitySplit, ActivityStream, Athlete, GarminDay
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
)
from services.activity_deduplication import match_activities, TIME_WINDOW_S
from services.garmin_backfill import request_garmin_backfill

logger = logging.getLogger(__name__)


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

    if adapted.get("sport") != "run":
        logger.debug(
            "Skipping non-run activity (sport=%s, external_id=%s)",
            adapted.get("sport"),
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
            return "updated"

    # --- No match: create new Activity row ---
    new_activity = _create_activity_from_adapted(adapted, athlete.id)
    db.add(new_activity)
    return "created"


def _ingest_activity_detail_item(
    raw_item: Dict[str, Any],
    athlete_id: str,
    db,
) -> bool:
    """
    Process a single Garmin ClientActivityDetail dict: extract samples,
    build ActivityStream row, link to parent Activity via garmin_activity_id.

    Returns True if processed, False if skipped.
    """
    # All Garmin→internal field name translation delegated to adapter (source contract)
    envelope = adapt_activity_detail_envelope(raw_item)
    garmin_activity_id_int = envelope.get("garmin_activity_id")

    if garmin_activity_id_int is None:
        logger.warning("Activity detail missing or invalid garmin_activity_id — skipping")
        return False

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
        logger.warning(
            "Activity detail for unknown garmin_activity_id=%s (athlete=%s) — skipping",
            garmin_activity_id_int,
            athlete_id,
        )
        return False

    samples = envelope.get("samples") or []

    # Determine early whether laps exist — both samples and laps are optional,
    # but at least one must be present to do useful work.
    lap_splits = adapt_activity_detail_laps(raw_item, samples)

    if not samples and not lap_splits:
        logger.debug(
            "Activity detail garmin_activity_id=%s has no samples or laps",
            garmin_activity_id_int,
        )
        activity.stream_fetch_status = "unavailable"
        return True

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

    # Living Fingerprint: extract and store run_shape after stream ingestion
    if samples and stream_data:
        try:
            from services.shape_extractor import extract_shape, PaceProfile, pace_profile_from_training_paces
            from models import AthleteTrainingPaceProfile, Athlete as _AthModel

            pace_prof = None
            profile_row = (
                db.query(AthleteTrainingPaceProfile)
                .filter(AthleteTrainingPaceProfile.athlete_id == athlete_id)
                .order_by(AthleteTrainingPaceProfile.created_at.desc())
                .first()
            )
            if profile_row and profile_row.paces:
                pace_prof = pace_profile_from_training_paces(profile_row.paces)

            if not pace_prof:
                ath = db.query(_AthModel).filter(_AthModel.id == athlete_id).first()
                if ath and ath.threshold_pace_per_km:
                    thr_sec_km = float(ath.threshold_pace_per_km)
                    if thr_sec_km < 30:
                        thr_sec_km = thr_sec_km * 60
                    thr_v = 1000.0 / thr_sec_km
                    thr_sec_mi = 1609.34 / thr_v if thr_v > 0 else 450
                    pace_prof = PaceProfile(
                        easy_sec=int(thr_sec_mi * 1.35),
                        marathon_sec=int(thr_sec_mi * 1.10),
                        threshold_sec=int(thr_sec_mi),
                        interval_sec=int(thr_sec_mi * 0.88),
                        repetition_sec=int(thr_sec_mi * 0.80),
                    )

            heat_adj = float(activity.heat_adjustment_pct) if activity.heat_adjustment_pct else None
            shape = extract_shape(stream_data, pace_profile=pace_prof, heat_adjustment_pct=heat_adj)
            if shape:
                activity.run_shape = shape.to_dict()
        except Exception as shape_exc:
            logger.warning("Garmin shape extraction failed for %s: %s", garmin_activity_id_int, shape_exc)

    # --- Lap splits (idempotent: delete-then-create) ---
    # lap_splits was computed before the samples block to allow early-return logic above.
    if lap_splits:
        db.query(ActivitySplit).filter(
            ActivitySplit.activity_id == activity.id
        ).delete(synchronize_session=False)
        for lap in lap_splits:
            db.add(ActivitySplit(
                activity_id=activity.id,
                split_number=lap["split_number"],
                distance=lap["distance"],
                elapsed_time=lap["elapsed_time"],
                moving_time=lap["moving_time"],
                average_heartrate=lap["average_heartrate"],
                max_heartrate=lap["max_heartrate"],
                average_cadence=lap["average_cadence"],
                gap_seconds_per_mile=lap["gap_seconds_per_mile"],
            ))
        logger.info(
            "Created %d splits for garmin_activity_id=%s",
            len(lap_splits), garmin_activity_id_int,
        )

    return True


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
      2. Filter: sport="run" only (RUNNING, TRAIL_RUNNING, TREADMILL_RUNNING, etc.)
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

        for raw_item in items:
            result = _ingest_activity_item(raw_item, athlete, db)
            if result == "created":
                created += 1
            elif result == "updated":
                updated += 1
            else:
                skipped += 1

        athlete.last_garmin_sync = datetime.now(tz=timezone.utc)
        db.commit()
        from core.cache import invalidate_athlete_cache
        invalidate_athlete_cache(str(athlete_id))
        # Ensure home coach briefing reflects newly ingested activities.
        # We only trigger when data actually changed (created/updated), not for all-skipped payloads.
        if created > 0 or updated > 0:
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

        # Runtoon generation is on-demand only (athlete taps "Share Your Run").
        # Auto-generation removed per RUNTOON_SHARE_FLOW_SPEC.md — Mar 2026.

        logger.info(
            "process_garmin_activity_task: athlete=%s created=%d updated=%d skipped=%d",
            athlete_id,
            created,
            updated,
            skipped,
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
        for raw_item in items:
            if _ingest_activity_detail_item(raw_item, athlete_id, db):
                processed += 1
                db.commit()

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
            try:
                from services.home_briefing_cache import mark_briefing_dirty
                from tasks.home_briefing_tasks import enqueue_briefing_refresh

                mark_briefing_dirty(str(athlete_id))
                enqueue_briefing_refresh(str(athlete_id))
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
