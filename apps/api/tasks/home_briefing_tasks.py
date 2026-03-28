"""
Home Briefing Celery Task (ADR-065 / Lane 2A)

Generates home coach briefings asynchronously. The /v1/home endpoint
never calls this directly — it reads from Redis cache and enqueues
a refresh via .delay() when stale or missing.

Task contract:
- Idempotent by athlete + data fingerprint
- Deduplicated via Redis lock
- Provider timeout: 12s
- Task hard timeout: 15s
- Retry: up to 3 attempts with exponential backoff
- Circuit breaker: stops after 3 consecutive failures
"""

import hashlib
import json
import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Optional
from uuid import UUID

from celery import Task
from sqlalchemy import desc
from sqlalchemy.orm import Session

from tasks import celery_app
from core.database import get_db_sync
from core.cache import get_redis_client
from services.home_briefing_cache import (
    BriefingState,
    acquire_task_lock,
    read_briefing_cache,
    read_briefing_cache_with_meta,
    record_task_failure,
    release_task_lock,
    reset_circuit,
    write_briefing_cache,
)

logger = logging.getLogger(__name__)

# SEV-1 hardening: Celery worker import path can differ from uvicorn runtime.
# Ensure the app root (apps/api) is present so deferred imports like
# `from routers.home import ...` are always resolvable in worker processes.
_app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _app_root not in sys.path:
    sys.path.insert(0, _app_root)

PROVIDER_TIMEOUT_S = 45   # Rich prompt (5 intelligence sources) needs more generation time
TASK_HARD_TIMEOUT_S = 55  # Must exceed PROVIDER_TIMEOUT_S + DB work headroom
BRIEFING_FINGERPRINT_VERSION = "v2"


def _build_data_fingerprint(
    athlete_id: str,
    db: Session,
) -> str:
    """Build a fingerprint of the athlete's current data state."""
    from models import Activity, DailyCheckin, TrainingPlan

    today = date.today()
    parts = [athlete_id, f"schema:{BRIEFING_FINGERPRINT_VERSION}", f"date:{today.isoformat()}"]

    try:
        latest_activity = (
            db.query(Activity.id, Activity.start_time)
            .filter(Activity.athlete_id == athlete_id)
            .order_by(desc(Activity.start_time))
            .first()
        )
        if latest_activity:
            parts.append(f"act:{latest_activity.id}:{latest_activity.start_time}")
    except Exception:
        pass

    try:
        checkin = (
            db.query(DailyCheckin.id, DailyCheckin.date)
            .filter(
                DailyCheckin.athlete_id == athlete_id,
                DailyCheckin.date == today,
            )
            .first()
        )
        if checkin:
            parts.append(f"checkin:{checkin.id}")
    except Exception:
        pass

    try:
        plan = (
            db.query(TrainingPlan.id, TrainingPlan.updated_at)
            .filter(
                TrainingPlan.athlete_id == athlete_id,
                TrainingPlan.status == "active",
            )
            .first()
        )
        if plan:
            parts.append(f"plan:{plan.id}:{plan.updated_at}")
    except Exception:
        pass

    raw = "|".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _build_briefing_prompt(athlete_id: str, db: Session) -> Optional[tuple]:
    """
    Build the LLM prompt from DB data. Reuses the existing
    generate_coach_home_briefing() prompt builder.

    Returns
      (prompt, schema_fields, required_fields, checkin_data_dict, race_data_dict, garmin_sleep_h)
    on success, ``None`` when legacy cache short-circuits, and ``False`` on hard failure.
    """
    from models import Activity, DailyCheckin, PlannedWorkout, TrainingPlan

    today = date.today()

    try:
        active_plan = (
            db.query(TrainingPlan)
            .filter(
                TrainingPlan.athlete_id == athlete_id,
                TrainingPlan.status == "active",
            )
            .first()
        )

        today_completed = None
        today_actual = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete_id,
                Activity.start_time >= today,
                Activity.start_time < today + timedelta(days=1),
            )
            .order_by(desc(Activity.start_time))
            .first()
        )
        if today_actual:
            actual_mi = (
                round(today_actual.distance_m / 1609.344, 1)
                if today_actual.distance_m
                else None
            )
            actual_pace = None
            if today_actual.distance_m and today_actual.duration_s:
                pace_s = today_actual.duration_s / (today_actual.distance_m / 1609.344)
                mins = int(pace_s // 60)
                secs = int(pace_s % 60)
                actual_pace = f"{mins}:{secs:02d}/mi"
            today_completed = {
                "name": today_actual.name or "Run",
                "distance_mi": actual_mi,
                "pace": actual_pace,
                "avg_hr": int(today_actual.avg_hr) if today_actual.avg_hr else None,
                "duration_min": (
                    round(today_actual.duration_s / 60, 0)
                    if today_actual.duration_s
                    else None
                ),
            }
            try:
                from routers.home import _summarize_workout_structure
                ws = _summarize_workout_structure(today_actual.id, db)
                if ws:
                    today_completed["workout_structure"] = ws
            except Exception as _ws_err:
                logger.debug("Workout structure detection skipped: %s", _ws_err)

        planned_workout_dict = None
        if active_plan:
            planned = (
                db.query(PlannedWorkout)
                .filter(
                    PlannedWorkout.plan_id == active_plan.id,
                    PlannedWorkout.scheduled_date == today,
                )
                .first()
            )
            if planned:
                distance_mi = None
                if planned.target_distance_km:
                    distance_mi = round(planned.target_distance_km * 0.621371, 1)
                planned_workout_dict = {
                    "has_workout": True,
                    "workout_type": planned.workout_type,
                    "title": planned.title,
                    "distance_mi": distance_mi,
                }

        race_data_dict = None
        if active_plan and active_plan.goal_race_date:
            days_remaining = (active_plan.goal_race_date - today).days
            if days_remaining >= 0:
                goal_time = None
                if active_plan.goal_time_seconds:
                    h = active_plan.goal_time_seconds // 3600
                    m = (active_plan.goal_time_seconds % 3600) // 60
                    s = active_plan.goal_time_seconds % 60
                    goal_time = f"{h}:{m:02d}:{s:02d}"
                race_data_dict = {
                    "race_name": active_plan.goal_race_name or active_plan.name,
                    "days_remaining": days_remaining,
                    "goal_time": goal_time,
                }

        checkin_data_dict = None
        existing_checkin = (
            db.query(DailyCheckin)
            .filter(
                DailyCheckin.athlete_id == athlete_id,
                DailyCheckin.date == today,
            )
            .first()
        )
        if existing_checkin:
            from routers.home import _build_checkin_data_dict
            checkin_data_dict = _build_checkin_data_dict(existing_checkin)

        from routers.home import generate_coach_home_briefing

        # skip_cache=True: bypass the legacy coach_home_briefing:{athlete_id}:{hash}
        # key. The worker must always generate fresh output and write to the Lane 2A
        # home_briefing:{athlete_id} key. Without this, a stale legacy key causes
        # _build_briefing_prompt to return None (already_cached), silently skipping
        # the Lane 2A write — the home page shows no morning voice.
        prep = generate_coach_home_briefing(
            athlete_id=athlete_id,
            db=db,
            today_completed=today_completed,
            planned_workout=planned_workout_dict,
            checkin_data=checkin_data_dict,
            race_data=race_data_dict,
            skip_cache=True,
        )

        if len(prep) == 1:
            # Should never be reached now that skip_cache=True, but kept as a guard.
            logger.warning(
                f"generate_coach_home_briefing returned cached 1-tuple despite "
                f"skip_cache=True for {athlete_id} — defensive guard hit"
            )
            return None  # Sentinel: already cached, normal skip

        _, prompt, schema_fields, required_fields, _, garmin_sleep_h = prep
        if garmin_sleep_h is not None:
            if checkin_data_dict is None:
                checkin_data_dict = {}
            checkin_data_dict["garmin_sleep_h"] = garmin_sleep_h
        return prompt, schema_fields, required_fields, checkin_data_dict, race_data_dict, garmin_sleep_h

    except Exception as e:
        logger.error(f"Failed to build briefing prompt for {athlete_id}: {e}", exc_info=True)
        return False  # Sentinel: build failed — caller must record failure, not silently skip


def _call_gemini_briefing(
    prompt: str,
    schema_fields: dict,
    required_fields: list,
) -> Optional[dict]:
    """Call Gemini 2.5 Flash with PROVIDER_TIMEOUT_S enforced."""
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
    from routers.home import _call_gemini_briefing_sync

    google_key = os.getenv("GOOGLE_AI_API_KEY")
    if not google_key:
        logger.warning("GOOGLE_AI_API_KEY not set — cannot generate home briefing")
        return None

    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(
        _call_gemini_briefing_sync, prompt, schema_fields, required_fields, google_key,
        PROVIDER_TIMEOUT_S,  # llm_timeout — worker path gets full budget
    )
    try:
        return future.result(timeout=PROVIDER_TIMEOUT_S)
    except FuturesTimeout:
        logger.warning(
            "Gemini home briefing provider timeout (%ss)", PROVIDER_TIMEOUT_S
        )
        future.cancel()
        pool.shutdown(wait=False)
        return None
    finally:
        pool.shutdown(wait=False)


def _call_opus_briefing(
    prompt: str,
    schema_fields: dict,
    required_fields: list,
    athlete_id: Optional[str] = None,
) -> Optional[dict]:
    """Call Sonnet (via _call_opus_briefing_sync) with PROVIDER_TIMEOUT_S enforced.
    
    Function name retained for compatibility — runtime model is claude-sonnet-4-6
    unless Kimi canary is active for this athlete.
    """
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
    from routers.home import _call_opus_briefing_sync

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_key:
        return None

    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(
        _call_opus_briefing_sync, prompt, schema_fields, required_fields, anthropic_key,
        PROVIDER_TIMEOUT_S,  # llm_timeout — worker path gets full budget
        athlete_id,          # pass through for canary routing
    )
    try:
        return future.result(timeout=PROVIDER_TIMEOUT_S)
    except FuturesTimeout:
        logger.warning(
            "Sonnet home briefing provider timeout (%ss)", PROVIDER_TIMEOUT_S
        )
        future.cancel()
        pool.shutdown(wait=False)
        return None
    finally:
        pool.shutdown(wait=False)


def _call_llm_for_briefing(
    prompt: str,
    schema_fields: dict,
    required_fields: list,
    athlete_id: Optional[str] = None,
) -> Optional[dict]:
    """
    Single LLM dispatch point for home briefing generation.

    Always tries primary model first (Sonnet or Kimi canary), falls back to
    Gemini Flash. Matches the behaviour of _fetch_llm_briefing_sync in
    home.py. The use_opus feature flag has been retired — the model
    selection is driven by API key availability and canary config.

    This wrapper exists so consent gating in generate_home_briefing_task
    can be verified by tests via patching this function.  All actual LLM
    calls go through _call_opus_briefing (Sonnet/Kimi) or _call_gemini_briefing.
    """
    result = _call_opus_briefing(prompt, schema_fields, required_fields, athlete_id=athlete_id)
    if result is not None:
        return result
    return _call_gemini_briefing(prompt, schema_fields, required_fields)


def _build_deterministic_briefing(athlete_id: str, db: Session) -> Dict[str, str]:
    """
    Build a non-LLM fallback briefing so one athlete never stays stale.

    This is used when provider calls or contract validation fail.
    """
    from models import Activity

    latest = (
        db.query(Activity)
        .filter(Activity.athlete_id == athlete_id)
        .order_by(desc(Activity.start_time))
        .first()
    )

    if latest and latest.distance_m and latest.duration_s:
        distance_mi = round(float(latest.distance_m) / 1609.344, 1)
        pace_s = float(latest.duration_s) / max(float(latest.distance_m) / 1609.344, 0.1)
        pace_str = f"{int(pace_s // 60)}:{int(pace_s % 60):02d}/mi"
        coach_noticed = (
            f"Latest run synced: {distance_mi} mi at {pace_str}. "
            "Signals will refine as more data arrives."
        )
        morning_voice = (
            f"{distance_mi} miles in your latest run at {pace_str}. "
            "Your home briefing is refreshed from synced activity data."
        )
        today_context = "Sync completed. Use this as your current baseline for today's effort."
        week_assessment = "Data is current; evaluate today's workload against this latest run."
    else:
        coach_noticed = "Your sync completed and your data timeline is current."
        morning_voice = (
            "Sync completed. Your briefing is refreshed from current account data."
        )
        today_context = "Data is refreshed. Follow your planned workout and re-check after your next run."
        week_assessment = "Current data is available for this week; confidence improves with each new activity."

    return {
        "coach_noticed": coach_noticed,
        "today_context": today_context,
        "week_assessment": week_assessment,
        "morning_voice": morning_voice,
        "workout_why": "Fresh synced data keeps your training decisions anchored to what just happened.",
    }


@celery_app.task(
    name="tasks.generate_home_briefing",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=3,
    time_limit=TASK_HARD_TIMEOUT_S,
    soft_time_limit=TASK_HARD_TIMEOUT_S - 2,
)
def generate_home_briefing_task(self: Task, athlete_id: str) -> Dict:
    """
    Generate a home briefing for an athlete and cache it in Redis.
    Called via .delay() — the /v1/home endpoint never awaits this.
    """
    if not acquire_task_lock(athlete_id):
        logger.info(f"Home briefing task skipped (lock held): {athlete_id}")
        return {"status": "skipped", "reason": "lock_held"}

    db: Optional[Session] = None
    try:
        db = get_db_sync()

        # P1-D: Consent gate — check at task execution time (not enqueue time).
        # An athlete may revoke consent after a task is enqueued.
        from uuid import UUID as _UUID
        from services.consent import has_ai_consent as _has_consent
        if not _has_consent(athlete_id=_UUID(athlete_id), db=db):
            logger.info(f"Home briefing task skipped (no consent): {athlete_id}")
            return {"status": "skipped", "reason": "no_consent"}

        fingerprint = _build_data_fingerprint(athlete_id, db)

        cached_payload, cached_state, cached_meta = read_briefing_cache_with_meta(athlete_id)
        cached_is_interim = bool(cached_meta.get("briefing_is_interim", False))
        if cached_state in (BriefingState.FRESH, BriefingState.STALE) and cached_payload:
            r = get_redis_client()
            if r:
                try:
                    raw = r.get(f"home_briefing:{athlete_id}")
                    if raw:
                        entry = json.loads(raw)
                        if entry.get("data_fingerprint") == fingerprint:
                            entry_source = str(entry.get("briefing_source") or "").strip().lower()
                            source_model = str(entry.get("source_model") or "").strip().lower()
                            entry_is_interim = bool(
                                entry.get("briefing_is_interim", cached_is_interim)
                            )
                            is_deterministic = (
                                entry_source == "deterministic_fallback"
                                or "deterministic" in source_model
                            )
                            if not entry_is_interim and not is_deterministic:
                                logger.info(
                                    "Home briefing fingerprint unchanged for %s — refreshing cache without LLM call",
                                    athlete_id,
                                )
                                # Critical: refresh generated_at/expires_at so unchanged
                                # fingerprints do not decay into stale->missing.
                                # This keeps morning voice + coach insight available
                                # when source data has not changed.
                                cached_source_model = entry.get("source_model") or "cache-refresh"
                                write_briefing_cache(
                                    athlete_id=athlete_id,
                                    payload=cached_payload,
                                    source_model=str(cached_source_model),
                                    data_fingerprint=fingerprint,
                                    briefing_source=str(cached_meta.get("briefing_source") or "llm"),
                                    briefing_is_interim=bool(cached_meta.get("briefing_is_interim")),
                                )
                                reset_circuit(athlete_id)
                                return {
                                    "status": "success",
                                    "reason": "fingerprint_unchanged_cache_refreshed",
                                }
                            logger.info(
                                "Home briefing fingerprint unchanged for %s but cached briefing is interim; forcing LLM regeneration",
                                athlete_id,
                            )
                except (json.JSONDecodeError, TypeError, Exception):
                    pass

        prompt_result = _build_briefing_prompt(athlete_id, db)
        if prompt_result is None:
            # Normal skip — briefing was already cached under the old cache key
            return {"status": "skipped", "reason": "already_cached"}
        if prompt_result is False:
            logger.error(f"Prompt build failed for {athlete_id}; writing deterministic fallback")
            fallback_payload = _build_deterministic_briefing(athlete_id, db)
            write_briefing_cache(
                athlete_id=athlete_id,
                payload=fallback_payload,
                source_model="deterministic-fallback",
                data_fingerprint=fingerprint,
                briefing_source="deterministic_fallback",
                briefing_is_interim=True,
            )
            reset_circuit(athlete_id)
            return {"status": "degraded", "reason": "prompt_build_failed", "model": "deterministic-fallback"}

        prompt, schema_fields, required_fields, checkin_data, race_data, garmin_sleep_h = prompt_result

        use_opus = bool(os.getenv("ANTHROPIC_API_KEY"))
        source_model = "claude-sonnet-4-6" if use_opus else "gemini-2.5-flash"
        result = _call_llm_for_briefing(prompt, schema_fields, required_fields, athlete_id=athlete_id)

        if result is None:
            logger.warning("All LLM providers failed for %s; writing deterministic fallback", athlete_id)
            fallback_payload = _build_deterministic_briefing(athlete_id, db)
            write_briefing_cache(
                athlete_id=athlete_id,
                payload=fallback_payload,
                source_model="deterministic-fallback",
                data_fingerprint=fingerprint,
                briefing_source="deterministic_fallback",
                briefing_is_interim=True,
            )
            reset_circuit(athlete_id)
            return {"status": "degraded", "reason": "llm_unavailable", "model": "deterministic-fallback"}

        from routers.home import (
            _valid_home_briefing_contract,
            validate_voice_output,
            validate_sleep_claims,
            _strip_ungrounded_sleep_sentences,
            _VOICE_FALLBACK,
        )

        if not _valid_home_briefing_contract(result, checkin_data=checkin_data, race_data=race_data):
            logger.warning(f"Home briefing failed A->I->A contract for {athlete_id}")
            fallback_payload = _build_deterministic_briefing(athlete_id, db)
            write_briefing_cache(
                athlete_id=athlete_id,
                payload=fallback_payload,
                source_model="deterministic-fallback",
                data_fingerprint=fingerprint,
                briefing_source="deterministic_fallback",
                briefing_is_interim=True,
            )
            reset_circuit(athlete_id)
            return {"status": "degraded", "reason": "contract_validation_failed", "model": "deterministic-fallback"}

        raw_voice = result.get("morning_voice")
        if raw_voice:
            voice_check = validate_voice_output(raw_voice, field="morning_voice")
            if not voice_check["valid"]:
                logger.warning(
                    f"morning_voice failed validation ({voice_check.get('reason')}) "
                    f"for {athlete_id}; using fallback"
                )
                result["morning_voice"] = voice_check["fallback"]
            elif voice_check.get("truncated_text"):
                result["morning_voice"] = voice_check["truncated_text"]
        else:
            result["morning_voice"] = _VOICE_FALLBACK

        # Sleep claim grounding validator
        _garmin_h = checkin_data.get("garmin_sleep_h") if checkin_data else None
        _checkin_h = checkin_data.get("sleep_h") if checkin_data else None
        final_voice = result.get("morning_voice", "")
        if final_voice and final_voice != _VOICE_FALLBACK:
            sleep_check = validate_sleep_claims(final_voice, _garmin_h, _checkin_h)
            if not sleep_check["valid"]:
                stripped = _strip_ungrounded_sleep_sentences(
                    final_voice, _garmin_h, _checkin_h
                )
                candidate = stripped.get("text") or ""
                if candidate:
                    candidate_voice_check = validate_voice_output(candidate, field="morning_voice")
                    candidate_sleep_check = validate_sleep_claims(candidate, _garmin_h, _checkin_h)
                    if candidate_voice_check.get("valid") and candidate_sleep_check.get("valid"):
                        logger.warning(
                            "morning_voice sleep claim ungrounded (%s) for %s; removed offending sentence(s)",
                            sleep_check.get("reason"),
                            athlete_id,
                        )
                        result["morning_voice"] = candidate
                    else:
                        logger.warning(
                            "morning_voice sleep claim ungrounded (%s) for %s; candidate invalid (voice=%s sleep=%s), using deterministic fallback",
                            sleep_check.get("reason"),
                            athlete_id,
                            candidate_voice_check.get("reason"),
                            candidate_sleep_check.get("reason"),
                        )
                        result["morning_voice"] = _build_deterministic_briefing(athlete_id, db).get("morning_voice", _VOICE_FALLBACK)
                else:
                    logger.warning(
                        "morning_voice sleep claim ungrounded (%s) for %s; no valid content remained, using deterministic fallback",
                        sleep_check.get("reason"),
                        athlete_id,
                    )
                    result["morning_voice"] = _build_deterministic_briefing(athlete_id, db).get("morning_voice", _VOICE_FALLBACK)

        raw_noticed = result.get("coach_noticed")
        if raw_noticed:
            noticed_check = validate_voice_output(raw_noticed, field="coach_noticed")
            if not noticed_check["valid"]:
                logger.warning(
                    f"coach_noticed failed validation ({noticed_check.get('reason')}) "
                    f"for {athlete_id}; clearing field"
                )
                result["coach_noticed"] = None

        raw_why = result.get("workout_why")
        if raw_why:
            why_check = validate_voice_output(raw_why, field="workout_why")
            if not why_check["valid"]:
                result["workout_why"] = None

        # write_briefing_cache raises RuntimeError on any failure (setex error or
        # verification-read mismatch). This propagates to the except block which
        # records the failure and re-raises, triggering Celery's autoretry.
        # Silent cache misses are structurally impossible from this point forward.
        write_briefing_cache(
            athlete_id=athlete_id,
            payload=result,
            source_model=source_model,
            data_fingerprint=fingerprint,
            briefing_source="llm",
            briefing_is_interim=False,
        )

        # Finding-level cooldown: after briefing generation, set cooldown keys
        # for any correlation findings that appear in the output text.
        try:
            from routers.home import _set_finding_cooldowns
            briefing_text = " ".join(str(v) for v in result.values() if v)
            injected = kwargs.get("injected_findings", [])
            if not injected:
                from services.correlation_engine import analyze_correlations
                try:
                    corr_result = analyze_correlations(athlete_id, days=60, db=db)
                    injected = [
                        {"input_name": c.get("input_name", ""), "output_metric": c.get("output_metric", "efficiency")}
                        for c in corr_result.get("correlations", [])
                        if c.get("is_significant")
                    ]
                except Exception:
                    pass
            _set_finding_cooldowns(athlete_id, briefing_text, injected)
        except Exception as _e:
            logger.debug("Finding cooldown write failed (non-blocking): %s", _e)

        reset_circuit(athlete_id)

        logger.info(
            f"Home briefing generated for {athlete_id} "
            f"(model={source_model}, fingerprint={fingerprint[:8]})"
        )
        return {"status": "success", "model": source_model, "fingerprint": fingerprint}

    except Exception as e:
        record_task_failure(athlete_id)
        logger.error(f"Home briefing task failed for {athlete_id}: {e}")
        raise
    finally:
        release_task_lock(athlete_id)
        if db:
            db.close()


@celery_app.task(name="tasks.refresh_active_home_briefings", bind=True)
def refresh_active_home_briefings(self: Task) -> Dict:
    """
    Celery beat task: refresh home briefings for athletes active in last 24h.
    Runs every 15 minutes via celerybeat_schedule.
    """
    db: Optional[Session] = None
    try:
        db = get_db_sync()
        from models import Athlete, Activity
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        active_ids = (
            db.query(Activity.athlete_id)
            .filter(Activity.start_time >= cutoff)
            .distinct()
            .all()
        )

        enqueued = 0
        for (athlete_id,) in active_ids:
            if enqueue_briefing_refresh(str(athlete_id)):
                enqueued += 1

        logger.info(f"Home briefing beat: {enqueued}/{len(active_ids)} athletes enqueued")
        return {"status": "success", "enqueued": enqueued, "total_active": len(active_ids)}
    except Exception as e:
        logger.error(f"Home briefing beat failed: {e}")
        return {"status": "error", "error": str(e)}
    finally:
        if db:
            db.close()


def enqueue_briefing_refresh(
    athlete_id: str,
    force: bool = False,
    allow_circuit_probe: bool = False,
    priority: str = "normal",
) -> bool:
    """
    Fire-and-forget enqueue for home briefing refresh.

    force=False (default): respects cooldown + circuit breaker.
    force=True: bypasses cooldown, still honors circuit breaker unless
                allow_circuit_probe=True.
    allow_circuit_probe=True: for real data-change events, enqueue one
                probe even if circuit is open so a stuck athlete can recover.
    priority="high": route to briefing_high queue (live page loads).
    priority="normal": route to briefing queue (background pre-warm).
    """
    from services.home_briefing_cache import (
        should_enqueue_refresh,
        set_enqueue_cooldown,
        is_circuit_open,
        is_enqueue_cooldown_active,
        is_task_lock_held,
    )

    if is_task_lock_held(athlete_id):
        logger.debug("Home briefing enqueue skipped (task lock held): %s", athlete_id)
        return False

    if force:
        # Force mode is intended for data-change recovery, not burst replay.
        # Suppress repeated force-enqueues during cooldown for background traffic.
        if priority != "high" and is_enqueue_cooldown_active(athlete_id):
            logger.debug(
                "Home briefing force-enqueue skipped (cooldown active): %s",
                athlete_id,
            )
            return False
        if is_circuit_open(athlete_id) and not allow_circuit_probe:
            logger.debug("Home briefing force-enqueue blocked (circuit open): %s", athlete_id)
            return False
        if is_circuit_open(athlete_id) and allow_circuit_probe:
            logger.warning(
                "Home briefing force-enqueue probe allowed despite open circuit: %s",
                athlete_id,
            )
    else:
        if not should_enqueue_refresh(athlete_id):
            return False

    set_enqueue_cooldown(athlete_id)
    queue = "briefing_high" if priority == "high" else "briefing"
    generate_home_briefing_task.apply_async(args=[athlete_id], queue=queue)
    logger.info(
        "Home briefing refresh enqueued for %s (force=%s, probe=%s, queue=%s)",
        athlete_id, force, allow_circuit_probe, queue,
    )
    return True
