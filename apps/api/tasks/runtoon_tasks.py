"""
Runtoon Celery Tasks — async AI image generation, fire-and-forget.

Called post-sync from both Strava and Garmin pipelines. Never blocks the
sync pipeline or any request thread. Silent on all failures.

Task design:
    generate_runtoon_for_latest(athlete_id):
        1. Check feature flag + entitlement
        2. Check daily generation cap (max 5)
        3. Find most recent Activity without a Runtoon (attempt_number=1)
        4. Verify athlete has ≥3 active AthletePhoto records
        5. Load photo bytes from R2
        6. Assemble + call Gemini via runtoon_service
        7. Upload result to R2
        8. Write RuntoonImage record (UniqueConstraint catches any race)
        9. On ANY failure: log + return, never raise, no retry

Idempotency:
    DB-level: UniqueConstraint("activity_id", "attempt_number") prevents
    duplicates from concurrent Strava + Garmin hooks. App-level check (step 3)
    avoids paying for an API call before hitting the constraint.

Rate limits (all enforced by DB queries, not prose):
    - 1 auto-generate per activity (attempt_number=1)
    - Max 5 total generations per athlete per day
    - Max 3 total per activity (1 auto + 2 manual regen)
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from celery import Task
from sqlalchemy import func as sa_func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.database import get_db_sync
from tasks import celery_app

logger = logging.getLogger(__name__)

RUNTOON_DAILY_CAP = 5
RUNTOON_PER_ACTIVITY_CAP = 3
RUNTOON_MIN_PHOTOS = 3


def _today_utc_start() -> datetime:
    """Return midnight UTC for today as a timezone-aware datetime."""
    now = datetime.now(tz=timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _check_feature_flag(db: Session, athlete_id) -> bool:
    """
    Return True if Runtoon is enabled for this athlete.
    Checks FeatureFlag(key='runtoon.enabled'):
      - If flag doesn't exist → False (fail-closed)
      - If flag exists but enabled=False → False
      - If flag enabled=True and allowed_athlete_ids is null → True (all)
      - If allowed_athlete_ids is a list → athlete_id must be in it
    """
    from models import FeatureFlag
    flag = db.query(FeatureFlag).filter(FeatureFlag.key == "runtoon.enabled").first()
    if not flag or not flag.enabled:
        return False
    if flag.allowed_athlete_ids is None:
        return True
    # allowed_athlete_ids is JSONB — list of UUID strings
    allowed = flag.allowed_athlete_ids or []
    return str(athlete_id) in [str(a) for a in allowed]


def _check_entitlement(athlete) -> str:
    """
    Return entitlement level:
        "unlimited"   — guided or premium tier
        "first_only"  — free tier, no Runtoon generated yet
        "blocked"     — free tier, already used their one free Runtoon
    (One-time purchasers keep subscription_tier="free" and get no Runtoon access.)
    """
    from core.tier_utils import tier_satisfies
    if tier_satisfies(athlete.subscription_tier, "guided"):
        return "unlimited"
    return "free_pending"  # resolved after checking count below


@celery_app.task(bind=True, max_retries=0, soft_time_limit=60, time_limit=90)
def generate_runtoon_for_latest(self: Task, athlete_id: str) -> None:
    """
    Generate a Runtoon for the athlete's most recent activity without one.
    Fire-and-forget. Silent on failure.
    """
    db: Session = get_db_sync()
    try:
        _run_generation(db, athlete_id, attempt_number=1, activity_id=None)
    except Exception as e:
        logger.warning("generate_runtoon_for_latest: unhandled error athlete=%s: %s", athlete_id, e)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=0, soft_time_limit=60, time_limit=90)
def generate_runtoon_for_activity(self: Task, athlete_id: str, activity_id: str) -> None:
    """
    Manual regeneration — called from the API endpoint.
    Supports attempt_number 2 and 3 (after the auto-generated attempt_number=1).
    """
    db: Session = get_db_sync()
    try:
        _run_generation(db, athlete_id, attempt_number=None, activity_id=activity_id)
    except Exception as e:
        logger.warning("generate_runtoon_for_activity: unhandled error athlete=%s activity=%s: %s",
                       athlete_id, activity_id, e)
    finally:
        db.close()


def _run_generation(
    db: Session,
    athlete_id: str,
    attempt_number: Optional[int],
    activity_id: Optional[str],
) -> None:
    """
    Core generation logic shared by auto and manual tasks.

    All DB reads happen before ANY external calls. Session is closed cleanly
    before the Gemini API call to avoid passing a session across async boundaries.
    """
    from models import Athlete, Activity, AthletePhoto, RuntoonImage
    from services import runtoon_service, storage_service

    # -----------------------------------------------------------------------
    # 1. Load athlete
    # -----------------------------------------------------------------------
    athlete = db.get(Athlete, athlete_id)
    if not athlete:
        logger.warning("runtoon: athlete %s not found", athlete_id)
        return

    # -----------------------------------------------------------------------
    # 2. Feature flag check
    # -----------------------------------------------------------------------
    if not _check_feature_flag(db, athlete_id):
        logger.debug("runtoon: feature flag disabled for athlete %s", athlete_id)
        return

    # -----------------------------------------------------------------------
    # 3. Entitlement check
    # -----------------------------------------------------------------------
    from models import RuntoonImage as RuntoonImageModel
    entitlement = _check_entitlement(athlete)

    if entitlement == "free_pending":
        # Free tier: only one Runtoon ever — check if they've used it
        existing_count = (
            db.query(sa_func.count(RuntoonImageModel.id))
            .filter(RuntoonImageModel.athlete_id == athlete.id)
            .scalar()
        ) or 0
        if existing_count >= 1:
            logger.info("runtoon: free-tier athlete %s already used their one free Runtoon", athlete_id)
            return
        entitlement = "first_only"

    # -----------------------------------------------------------------------
    # 4. Daily cap check (max 5/day, all tiers)
    # -----------------------------------------------------------------------
    today_count = (
        db.query(sa_func.count(RuntoonImageModel.id))
        .filter(
            RuntoonImageModel.athlete_id == athlete.id,
            RuntoonImageModel.created_at >= _today_utc_start(),
        )
        .scalar()
    ) or 0
    if today_count >= RUNTOON_DAILY_CAP:
        logger.info("runtoon: daily cap (%d) reached for athlete %s", RUNTOON_DAILY_CAP, athlete_id)
        return

    # -----------------------------------------------------------------------
    # 5. Resolve activity
    # -----------------------------------------------------------------------
    from sqlalchemy import desc as sa_desc

    if activity_id:
        activity = db.get(Activity, activity_id)
        if not activity or str(activity.athlete_id) != str(athlete.id):
            logger.warning("runtoon: activity %s not found or not owned by %s", activity_id, athlete_id)
            return
    else:
        # Auto-mode: most recent activity without an auto Runtoon
        activity = (
            db.query(Activity)
            .filter(Activity.athlete_id == athlete.id)
            .filter(
                ~Activity.id.in_(
                    db.query(RuntoonImageModel.activity_id)
                    .filter(
                        RuntoonImageModel.athlete_id == athlete.id,
                        RuntoonImageModel.attempt_number == 1,
                    )
                )
            )
            .order_by(sa_desc(Activity.start_time))
            .first()
        )
        if not activity:
            logger.debug("runtoon: no eligible activity found for athlete %s", athlete_id)
            return

    # -----------------------------------------------------------------------
    # 6. Per-activity cap and attempt numbering
    # -----------------------------------------------------------------------
    activity_count = (
        db.query(sa_func.count(RuntoonImageModel.id))
        .filter(
            RuntoonImageModel.activity_id == activity.id,
            RuntoonImageModel.athlete_id == athlete.id,
        )
        .scalar()
    ) or 0

    if activity_count >= RUNTOON_PER_ACTIVITY_CAP:
        logger.info("runtoon: per-activity cap (%d) reached for activity %s", RUNTOON_PER_ACTIVITY_CAP, activity.id)
        return

    # Determine attempt_number
    if attempt_number is None:
        attempt_number = activity_count + 1  # 1, 2, or 3

    # -----------------------------------------------------------------------
    # 7. Check photos
    # -----------------------------------------------------------------------
    photos = (
        db.query(AthletePhoto)
        .filter(
            AthletePhoto.athlete_id == athlete.id,
            AthletePhoto.is_active == True,
        )
        .limit(10)
        .all()
    )
    if len(photos) < RUNTOON_MIN_PHOTOS:
        logger.info("runtoon: athlete %s has %d photos (min %d), skipping",
                    athlete_id, len(photos), RUNTOON_MIN_PHOTOS)
        return

    # -----------------------------------------------------------------------
    # 8. Read InsightLog for coaching narrative (same-day as activity)
    # -----------------------------------------------------------------------
    insight_narrative = None
    try:
        from models import InsightLog
        act_date = activity.start_time.date() if activity.start_time else None
        if act_date:
            insight = (
                db.query(InsightLog)
                .filter(
                    InsightLog.athlete_id == athlete.id,
                    InsightLog.trigger_date == act_date,
                )
                .order_by(sa_desc(InsightLog.trigger_date))
                .first()
            )
            if insight:
                insight_narrative = getattr(insight, 'narrative', None) or getattr(insight, 'message', None)
    except Exception as e:
        logger.debug("runtoon: could not load InsightLog: %s", e)

    # -----------------------------------------------------------------------
    # 8b. Gather training context (weekly mileage, upcoming race, phase)
    # -----------------------------------------------------------------------
    weekly_miles = 0.0
    race_name = None
    days_to_race = None
    training_phase = None

    try:
        from datetime import timedelta
        act_date = activity.start_time.date() if activity.start_time else None
        if act_date:
            week_start = act_date - timedelta(days=6)
            weekly_distance_m = (
                db.query(sa_func.sum(Activity.distance_m))
                .filter(
                    Activity.athlete_id == athlete.id,
                    sa_func.date(Activity.start_time) >= week_start,
                    sa_func.date(Activity.start_time) <= act_date,
                )
                .scalar()
            ) or 0
            weekly_miles = round(weekly_distance_m / 1609.344, 1)
    except Exception as e:
        logger.debug("runtoon: weekly mileage query failed: %s", e)

    try:
        from models import TrainingPlan
        from datetime import date as date_type
        today = date_type.today()
        plan = (
            db.query(TrainingPlan)
            .filter(
                TrainingPlan.athlete_id == athlete.id,
                TrainingPlan.status == "active",
                TrainingPlan.goal_race_date >= today,
            )
            .order_by(TrainingPlan.goal_race_date)
            .first()
        )
        if plan:
            race_name = plan.goal_race_name or plan.name
            days_to_race = (plan.goal_race_date - today).days
    except Exception as e:
        logger.debug("runtoon: race lookup failed: %s", e)

    try:
        from models import PlannedWorkout
        act_date = activity.start_time.date() if activity.start_time else None
        if act_date:
            pw = (
                db.query(PlannedWorkout)
                .filter(
                    PlannedWorkout.athlete_id == athlete.id,
                    PlannedWorkout.scheduled_date == act_date,
                )
                .first()
            )
            if pw and pw.phase:
                training_phase = pw.phase
    except Exception as e:
        logger.debug("runtoon: training phase lookup failed: %s", e)

    # -----------------------------------------------------------------------
    # 9. Snapshot all data needed BEFORE closing DB session
    # -----------------------------------------------------------------------
    photo_keys = [(p.storage_key, p.mime_type) for p in photos]

    act_snapshot = {
        "id": activity.id,
        "distance_meters": activity.distance_m,
        "moving_time_s": activity.moving_time_s or activity.duration_s,
        "average_hr": activity.avg_hr,
        "start_time": activity.start_time,
        "workout_type": activity.workout_type,
        "total_elevation_gain": float(activity.total_elevation_gain) if activity.total_elevation_gain else 0,
        "name": getattr(activity, 'name', None),
        "shape_sentence": getattr(activity, 'shape_sentence', None),
        "athlete_title": getattr(activity, 'athlete_title', None),
        "is_race_candidate": getattr(activity, 'is_race_candidate', False),
    }

    training_context = {
        "weekly_miles": weekly_miles,
        "race_name": race_name,
        "days_to_race": days_to_race,
        "training_phase": training_phase,
    }

    # -----------------------------------------------------------------------
    # 10. Load photo bytes from R2
    # -----------------------------------------------------------------------
    photo_bytes_list = []
    try:
        for storage_key, mime_type in photo_keys:
            url = storage_service.generate_signed_url(storage_key, expires_in=120)
            import urllib.request
            with urllib.request.urlopen(url, timeout=15) as resp:
                photo_bytes_list.append((resp.read(), mime_type))
    except Exception as e:
        logger.warning("runtoon: failed to load photos for athlete %s: %s", athlete_id, e)
        return

    # -----------------------------------------------------------------------
    # 11. Initialize Gemini client
    # -----------------------------------------------------------------------
    try:
        api_key = os.getenv("GOOGLE_AI_API_KEY")
        if not api_key:
            logger.warning("runtoon: GOOGLE_AI_API_KEY not set")
            return
        if not runtoon_service.GENAI_AVAILABLE:
            logger.warning("runtoon: google-genai not available")
            return
        gemini_client = runtoon_service.genai.Client(api_key=api_key)
    except Exception as e:
        logger.warning("runtoon: failed to initialize Gemini client: %s", e)
        return

    # -----------------------------------------------------------------------
    # 12. Create a simple activity proxy for runtoon_service (pure data)
    # -----------------------------------------------------------------------
    class _ActivityProxy:
        """Thin data-only proxy — no SQLAlchemy lazy loads."""
        def __init__(self, snap):
            for k, v in snap.items():
                setattr(self, k, v)

    activity_proxy = _ActivityProxy(act_snapshot)

    # -----------------------------------------------------------------------
    # 13. Call runtoon_service (no DB session passed)
    # -----------------------------------------------------------------------
    result = runtoon_service.generate_runtoon(
        activity=activity_proxy,
        athlete_photos=photo_bytes_list,
        insight_narrative=insight_narrative,
        training_context=training_context,
        gemini_client=gemini_client,
    )

    if result.error or not result.image_bytes:
        logger.warning(
            "runtoon: generation failed athlete=%s activity=%s error=%s",
            athlete_id, act_snapshot["id"], result.error,
        )
        _log_event("runtoon.generation_failed", {
            "athlete_id": str(athlete_id),
            "activity_id": str(act_snapshot["id"]),
            "error": result.error,
            "attempt_number": attempt_number,
        })
        return

    # -----------------------------------------------------------------------
    # 13b. Overlay stats/caption/watermark onto the 1:1 image (Pillow)
    # -----------------------------------------------------------------------
    try:
        final_bytes = runtoon_service.overlay_stats_1x1(
            source_image_bytes=result.image_bytes,
            stats_text=result.stats_text,
            caption_text=result.caption_text,
        )
        result.image_bytes = final_bytes
        logger.info("runtoon: 1:1 overlay applied for activity %s", act_snapshot["id"])
    except Exception as overlay_err:
        logger.warning(
            "runtoon: 1:1 overlay failed (uploading raw image): %s", overlay_err
        )

    # -----------------------------------------------------------------------
    # 14. Upload to R2
    # -----------------------------------------------------------------------
    runtoon_id = uuid.uuid4()
    storage_key = f"runtoons/{athlete_id}/{runtoon_id}.png"
    try:
        storage_service.upload_file(storage_key, result.image_bytes, "image/png")
    except Exception as e:
        logger.warning("runtoon: R2 upload failed athlete=%s: %s", athlete_id, e)
        return

    # -----------------------------------------------------------------------
    # 15. Write RuntoonImage record (UniqueConstraint catches any race)
    # -----------------------------------------------------------------------
    try:
        db2: Session = get_db_sync()
        try:
            runtoon_record = RuntoonImage(
                id=runtoon_id,
                athlete_id=athlete.id,
                activity_id=act_snapshot["id"],
                storage_key=storage_key,
                prompt_hash=result.prompt_hash,
                generation_time_ms=result.generation_time_ms,
                cost_usd=result.cost_usd,
                model_version=result.model_version,
                attempt_number=attempt_number,
                is_visible=True,
                caption_text=result.caption_text,
                stats_text=result.stats_text,
            )
            db2.add(runtoon_record)
            db2.commit()

            _log_event("runtoon.generated", {
                "athlete_id": str(athlete_id),
                "activity_id": str(act_snapshot["id"]),
                "runtoon_id": str(runtoon_id),
                "attempt_number": attempt_number,
                "cost_usd": float(result.cost_usd),
                "generation_time_ms": result.generation_time_ms,
            })

            logger.info(
                "runtoon: success athlete=%s activity=%s attempt=%d runtoon=%s latency=%dms",
                athlete_id, act_snapshot["id"], attempt_number, runtoon_id, result.generation_time_ms,
            )

        except IntegrityError:
            db2.rollback()
            logger.info(
                "runtoon: duplicate attempt (race condition) athlete=%s activity=%s attempt=%d — silently skipped",
                athlete_id, act_snapshot["id"], attempt_number,
            )
            # Clean up the R2 object since we won't reference it
            try:
                storage_service.delete_file(storage_key)
            except Exception:
                pass
        except Exception as e:
            db2.rollback()
            logger.warning("runtoon: DB write failed athlete=%s: %s", athlete_id, e)
        finally:
            db2.close()

    except Exception as e:
        logger.warning("runtoon: post-generation DB handling failed: %s", e)


def _log_event(event_name: str, payload: dict) -> None:
    """Structured analytics event logging."""
    logger.info("ANALYTICS event=%s %s", event_name, payload)
