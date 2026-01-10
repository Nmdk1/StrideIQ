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
try:
    from . import garmin_tasks  # noqa: E402
except ImportError:
    pass  # Garmin tasks not available if library not installed

__all__ = ["celery_app"]

