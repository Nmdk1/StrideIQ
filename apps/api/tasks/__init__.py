"""
Celery tasks for background processing.

Tasks are defined here and imported by both the API (to enqueue) and
the worker (to execute).
"""
from celery import Celery
from celery.schedules import crontab
from core.config import settings

# Create Celery app instance
celery_app = Celery(
    "performance_engine",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes max per task
    task_soft_time_limit=25 * 60,  # 25 minutes soft limit
)

# Import tasks to register them
from . import strava_tasks  # noqa: E402
from . import digest_tasks  # noqa: E402
from . import best_effort_tasks  # noqa: E402
from . import import_tasks  # noqa: E402
from . import intelligence_tasks  # noqa: E402
from . import home_briefing_tasks  # noqa: E402

# SEV-1 guardrail: fail worker startup if home briefing imports are broken.
try:
    from routers.home import (
        _VOICE_FALLBACK,
        _call_gemini_briefing_sync,
        _call_opus_briefing_sync,
        _valid_home_briefing_contract,
        generate_coach_home_briefing,
        validate_voice_output,
    )  # noqa: F401,E402

    # Validate symbol shape at startup so worker refuses to boot if the import
    # contract drifts.
    if not all([
        callable(generate_coach_home_briefing),
        callable(_call_gemini_briefing_sync),
        callable(_call_opus_briefing_sync),
        callable(_valid_home_briefing_contract),
        callable(validate_voice_output),
        isinstance(_VOICE_FALLBACK, str),
    ]):
        raise ImportError("routers.home briefing symbol contract invalid")
except ImportError as e:
    import logging
    logging.getLogger(__name__).critical(
        "FATAL: Worker cannot import briefing generator: %s. "
        "Home briefings will fail for all users.", e
    )
    raise SystemExit(1)

# garmin_tasks.py was retired in Phase 2 (Feb 2026). Replaced by
# garmin_webhook_tasks.py (webhook-push driven) and D5/D6 task modules.
from . import garmin_webhook_tasks  # noqa: E402  # D4: Celery task stubs

# SEV-1 guardrail: fail worker startup if home briefing imports are broken.
try:
    from routers.home import (
        _VOICE_FALLBACK,
        _call_gemini_briefing_sync,
        _call_opus_briefing_sync,
        _valid_home_briefing_contract,
        generate_coach_home_briefing,
        validate_voice_output,
    )  # noqa: F401,E402

    # Validate symbol shape at startup so worker refuses to boot if the import
    # contract drifts.
    if not all([
        callable(generate_coach_home_briefing),
        callable(_call_gemini_briefing_sync),
        callable(_call_opus_briefing_sync),
        callable(_valid_home_briefing_contract),
        callable(validate_voice_output),
        isinstance(_VOICE_FALLBACK, str),
    ]):
        raise ImportError("routers.home briefing symbol contract invalid")
except ImportError as e:
    import logging
    logging.getLogger(__name__).critical(
        "FATAL: Worker cannot import briefing generator: %s. "
        "Home briefings will fail for all users.", e
    )
    raise SystemExit(1)

__all__ = ["celery_app"]

