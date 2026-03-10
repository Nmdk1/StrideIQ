"""
Daily Experience Guardrail — Celery Task

Runs daily at 06:15 UTC against the founder account.
Calls endpoint functions directly (no HTTP, no auth tokens) and
writes results to experience_audit_log.
"""
import asyncio
import logging
from datetime import date, datetime, timezone

from tasks import celery_app
from core.database import get_db_sync
from core.cache import get_redis_client

logger = logging.getLogger(__name__)


def _to_dict(response):
    """Convert a Pydantic model or dict to dict."""
    if response is None:
        return None
    if isinstance(response, dict):
        return response
    if hasattr(response, "model_dump"):
        return response.model_dump()
    if hasattr(response, "dict"):
        return response.dict()
    return None


def _run_async(coro):
    """Run an async coroutine from sync context."""
    return asyncio.run(coro)


def _fetch_home(athlete, db) -> dict:
    """Call the home endpoint directly."""
    from routers.home import get_home_data
    resp = _run_async(get_home_data(db=db, current_user=athlete))
    return _to_dict(resp)


def _fetch_activities(athlete, db) -> list:
    """Get most recent 5 activities as DB objects."""
    from models import Activity
    return (
        db.query(Activity)
        .filter(Activity.athlete_id == athlete.id, Activity.is_duplicate.is_(False))
        .order_by(Activity.start_time.desc())
        .limit(5)
        .all()
    )


def _fetch_activity_detail(athlete, activity_id, db) -> dict:
    """Call the activity detail endpoint directly."""
    from routers.activities import get_activity
    resp = get_activity(activity_id=activity_id, current_user=athlete, db=db)
    return _to_dict(resp) if resp else resp


def _fetch_activity_findings(athlete, activity_id, db) -> list:
    """Call the activity findings endpoint directly."""
    try:
        from routers.activities import get_activity_findings
        resp = get_activity_findings(activity_id=activity_id, current_user=athlete, db=db)
        return resp if isinstance(resp, list) else []
    except Exception as exc:
        logger.warning("Failed to fetch activity findings: %s", exc)
        return []


def _fetch_progress_summary(athlete, db) -> dict:
    """Call the progress summary endpoint directly."""
    from routers.progress import get_progress_summary
    resp = _run_async(get_progress_summary(days=28, db=db, current_user=athlete))
    return _to_dict(resp)


def _safe_fetch(name, fn, *args, **kwargs):
    """Wrap endpoint fetch in try/except for graceful degradation."""
    try:
        result = fn(*args, **kwargs)
        return _to_dict(result) if result is not None else None
    except Exception as exc:
        logger.warning("Experience guardrail: failed to fetch %s: %s", name, exc)
        return None


def _fetch_tier2_endpoints(athlete, most_recent_activity, db) -> dict:
    """Fetch all Tier 2 endpoint responses."""
    responses = {}
    activity_id = most_recent_activity.id if most_recent_activity else None

    tier2_fetchers = {
        "progress/narrative": lambda: _fetch_async("routers.progress", "get_progress_narrative", db=db, current_user=athlete),
        "progress/knowledge": lambda: _fetch_async("routers.progress", "get_progress_knowledge", db=db, current_user=athlete),
        "progress/training-patterns": lambda: _fetch_sync("routers.progress", "get_training_patterns", db=db, current_user=athlete),
        "intelligence/today": lambda: _fetch_sync("routers.daily_intelligence", "get_today_intelligence", db=db, current_user=athlete),
        "insights/active": lambda: _fetch_sync("routers.insights", "get_insights", current_user=athlete, db=db),
        "fingerprint/findings": lambda: _fetch_async("routers.fingerprint", "get_fingerprint_findings", db=db, current_user=athlete),
    }

    if activity_id:
        tier2_fetchers["run-analysis"] = lambda: _fetch_async(
            "routers.run_analysis", "analyze_run", activity_id=activity_id, db=db, current_user=athlete,
        )
        tier2_fetchers["activities/attribution"] = lambda: _fetch_sync(
            "routers.activities", "get_activity_attribution", activity_id=activity_id, current_user=athlete, db=db,
        )
        tier2_fetchers["activities/findings"] = lambda: _fetch_sync(
            "routers.activities", "get_activity_findings", activity_id=activity_id, current_user=athlete, db=db,
        )

    for name, fetcher in tier2_fetchers.items():
        responses[name] = _safe_fetch(name, fetcher)

    return responses


def _fetch_tier3_endpoints(athlete, db) -> dict:
    """Fetch all Tier 3 endpoint responses (Mondays only)."""
    responses = {}

    tier3_fetchers = {
        "progress/training-story": lambda: _fetch_sync("routers.progress", "get_training_story", db=db, current_user=athlete),
        "athlete-profile/runner-type": lambda: _fetch_async("routers.athlete_profile", "get_runner_type", db=db, current_user=athlete),
        "athlete-profile/streak": lambda: _fetch_async("routers.athlete_profile", "get_consistency_streak", db=db, current_user=athlete),
        "coach/suggestions": lambda: _fetch_async("routers.ai_coach", "get_suggested_questions", db=db, current_user=athlete),
    }

    for name, fetcher in tier3_fetchers.items():
        responses[name] = _safe_fetch(name, fetcher)

    return responses


def _fetch_sync(module_path, func_name, **kwargs):
    """Import and call a sync endpoint function."""
    import importlib
    mod = importlib.import_module(module_path)
    fn = getattr(mod, func_name)
    return fn(**kwargs)


def _fetch_async(module_path, func_name, **kwargs):
    """Import and call an async endpoint function."""
    import importlib
    mod = importlib.import_module(module_path)
    fn = getattr(mod, func_name)
    return _run_async(fn(**kwargs))


@celery_app.task(name="tasks.run_experience_guardrail", bind=True, max_retries=1)
def run_experience_guardrail(self):
    """Daily production experience audit."""
    from models import Athlete, ExperienceAuditLog
    from services.experience_guardrail import ExperienceGuardrail

    started_at = datetime.now(timezone.utc)
    db = get_db_sync()

    try:
        founder = db.query(Athlete).filter(Athlete.email == "mbshaf@gmail.com").first()
        if not founder:
            logger.error("Experience guardrail: founder account not found")
            return {"status": "error", "reason": "founder_not_found"}

        redis_client = get_redis_client()
        guardrail = ExperienceGuardrail(str(founder.id), db, redis_client)

        # --- Preflight ---
        guardrail.run_preflight()

        # --- Fetch Tier 1 data ---
        home_response = _safe_fetch("home", _fetch_home, founder, db)
        activities = _fetch_activities(founder, db)
        most_recent = activities[0] if activities else None

        activity_detail = None
        if most_recent:
            activity_detail = _safe_fetch("activity_detail", _fetch_activity_detail, founder, most_recent.id, db)
            findings = _fetch_activity_findings(founder, most_recent.id, db)
            if activity_detail and findings:
                activity_detail["_findings"] = findings

        progress_summary = _safe_fetch("progress_summary", _fetch_progress_summary, founder, db)

        # --- Run Tier 1 ---
        if home_response:
            guardrail.run_tier1(home_response, activities, activity_detail, progress_summary)
        else:
            logger.error("Experience guardrail: could not fetch home response — aborting tier1")

        # --- Fetch and run Tier 2 ---
        tier2_responses = _fetch_tier2_endpoints(founder, most_recent, db)
        guardrail.run_tier2(tier2_responses)

        # --- Tier 3: Mondays only ---
        if date.today().weekday() == 0:
            tier3_responses = _fetch_tier3_endpoints(founder, db)
            guardrail.run_tier3(tier3_responses)

        # --- Summarize and persist ---
        summary = guardrail.summarize()
        today = date.today()
        is_monday = today.weekday() == 0
        tier_label = "daily_t1_t2_t3" if is_monday else "daily_t1_t2"

        log_entry = ExperienceAuditLog(
            athlete_id=founder.id,
            run_date=today,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            tier=tier_label,
            passed=summary["passed"],
            total_assertions=summary["total_assertions"],
            passed_count=summary["passed_count"],
            failed_count=summary["failed_count"],
            skipped_count=summary["skipped_count"],
            results=summary["results"],
            summary=summary["summary"],
        )
        db.add(log_entry)
        db.commit()

        if summary["passed"]:
            logger.info("Experience guardrail PASSED: %s", summary["summary"])
        else:
            logger.error("Experience guardrail FAILED: %s", summary["summary"])

        return {"status": "completed", **summary}

    except Exception as exc:
        logger.exception("Experience guardrail task failed: %s", exc)
        db.rollback()
        raise
    finally:
        db.close()
