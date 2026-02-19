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
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Optional
from uuid import UUID

from celery import Task
from sqlalchemy import desc
from sqlalchemy.orm import Session

from tasks import celery_app
from core.database import get_db_sync
from services.home_briefing_cache import (
    acquire_task_lock,
    record_task_failure,
    release_task_lock,
    reset_circuit,
    write_briefing_cache,
)

logger = logging.getLogger(__name__)

PROVIDER_TIMEOUT_S = 12
TASK_HARD_TIMEOUT_S = 15


def _build_data_fingerprint(
    athlete_id: str,
    db: Session,
) -> str:
    """Build a fingerprint of the athlete's current data state."""
    from models import Activity, DailyCheckin, TrainingPlan

    today = date.today()
    parts = [athlete_id]

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

    Returns (prompt, schema_fields, required_fields) or None on error.
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
            motivation_map = {5: "Great", 4: "Fine", 2: "Tired", 1: "Rough"}
            sleep_quality_map = {5: "Great", 4: "Good", 3: "OK", 2: "Poor", 1: "Awful"}
            sleep_legacy_map = {8: "Great", 7: "OK", 5: "Poor"}
            soreness_map = {1: "None", 2: "Mild", 4: "Yes"}

            sleep_quality_val = getattr(existing_checkin, "sleep_quality_1_5", None)
            if sleep_quality_val is not None:
                sleep_label = sleep_quality_map.get(int(sleep_quality_val))
            elif existing_checkin.sleep_h is not None:
                sleep_label = sleep_legacy_map.get(int(existing_checkin.sleep_h))
            else:
                sleep_label = None

            checkin_data_dict = {
                "motivation_label": motivation_map.get(
                    int(existing_checkin.motivation_1_5)
                    if existing_checkin.motivation_1_5 is not None
                    else -1
                ),
                "sleep_label": sleep_label,
                "soreness_label": soreness_map.get(
                    int(existing_checkin.soreness_1_5)
                    if existing_checkin.soreness_1_5 is not None
                    else -1
                ),
            }

        from routers.home import generate_coach_home_briefing

        prep = generate_coach_home_briefing(
            athlete_id=athlete_id,
            db=db,
            today_completed=today_completed,
            planned_workout=planned_workout_dict,
            checkin_data=checkin_data_dict,
            race_data=race_data_dict,
        )

        if len(prep) == 1:
            # Redis cache hit from the old cache key — use it
            return None  # Already cached, nothing to do

        _, prompt, schema_fields, required_fields, _ = prep
        return prompt, schema_fields, required_fields, checkin_data_dict, race_data_dict

    except Exception as e:
        logger.error(f"Failed to build briefing prompt for {athlete_id}: {e}")
        return None


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
        _call_gemini_briefing_sync, prompt, schema_fields, required_fields, google_key
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
) -> Optional[dict]:
    """Call Opus with PROVIDER_TIMEOUT_S enforced (feature-flagged path)."""
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
    from routers.home import _call_opus_briefing_sync

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_key:
        return None

    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(
        _call_opus_briefing_sync, prompt, schema_fields, required_fields, anthropic_key
    )
    try:
        return future.result(timeout=PROVIDER_TIMEOUT_S)
    except FuturesTimeout:
        logger.warning(
            "Opus home briefing provider timeout (%ss)", PROVIDER_TIMEOUT_S
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
    use_opus: bool = False,
) -> Optional[dict]:
    """
    Single LLM dispatch point for home briefing generation.

    This wrapper exists so consent gating in generate_home_briefing_task
    can be verified by tests via patching this function.  All actual LLM
    calls go through _call_opus_briefing or _call_gemini_briefing.
    """
    if use_opus:
        result = _call_opus_briefing(prompt, schema_fields, required_fields)
        if result is not None:
            return result
    return _call_gemini_briefing(prompt, schema_fields, required_fields)


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

        prompt_result = _build_briefing_prompt(athlete_id, db)
        if prompt_result is None:
            return {"status": "skipped", "reason": "prompt_build_failed_or_cached"}

        prompt, schema_fields, required_fields, checkin_data, race_data = prompt_result

        use_opus = False
        try:
            from core.feature_flags import is_feature_enabled
            use_opus = is_feature_enabled("home_briefing_use_opus", athlete_id, db)
        except Exception:
            pass

        source_model = "claude-opus-4-5" if use_opus else "gemini-2.5-flash"
        result = _call_llm_for_briefing(prompt, schema_fields, required_fields, use_opus=use_opus)

        if result is None:
            record_task_failure(athlete_id)
            raise RuntimeError(f"All LLM providers failed for {athlete_id}")

        from routers.home import _valid_home_briefing_contract, validate_voice_output, _VOICE_FALLBACK

        if not _valid_home_briefing_contract(result, checkin_data=checkin_data, race_data=race_data):
            logger.warning(f"Home briefing failed A->I->A contract for {athlete_id}")
            record_task_failure(athlete_id)
            return {"status": "error", "reason": "contract_validation_failed"}

        raw_voice = result.get("morning_voice")
        if raw_voice:
            voice_check = validate_voice_output(raw_voice, field="morning_voice")
            if not voice_check["valid"]:
                result["morning_voice"] = voice_check["fallback"]
        else:
            result["morning_voice"] = _VOICE_FALLBACK

        raw_why = result.get("workout_why")
        if raw_why:
            why_check = validate_voice_output(raw_why, field="workout_why")
            if not why_check["valid"]:
                result["workout_why"] = None

        write_briefing_cache(
            athlete_id=athlete_id,
            payload=result,
            source_model=source_model,
            data_fingerprint=fingerprint,
        )

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


def enqueue_briefing_refresh(athlete_id: str) -> bool:
    """
    Fire-and-forget enqueue for home briefing refresh.
    Respects cooldown and circuit breaker.

    Called by triggers (check-in, activity sync, plan change, etc.)
    and by the /v1/home endpoint when cache is stale/missing.
    """
    from services.home_briefing_cache import should_enqueue_refresh, set_enqueue_cooldown

    if not should_enqueue_refresh(athlete_id):
        return False

    set_enqueue_cooldown(athlete_id)
    generate_home_briefing_task.delay(athlete_id)
    logger.info(f"Home briefing refresh enqueued for {athlete_id}")
    return True
