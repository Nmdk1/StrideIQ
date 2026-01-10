"""
Celery worker entry point.

This imports the Celery app and tasks from the API module.
"""
import sys
import os

# Add API directory to path so we can import tasks
sys.path.insert(0, '/api')

# Import Celery app and tasks from API
from tasks import celery_app  # noqa: E402

# This makes Celery discover tasks
celery_app.autodiscover_tasks(['tasks'])

# Health check task (kept for compatibility)
@celery_app.task(name="worker.health_check")
def health_check():
    """Health check task"""
    return {"status": "ok"}





