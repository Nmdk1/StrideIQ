"""
Celery Beat Schedule Configuration

Defines periodic tasks that run on a schedule.
"""

from celery.schedules import crontab

# Schedule configuration
beat_schedule = {
    # Morning intelligence — every 15 minutes, checks which athletes
    # are at their 5 AM local window and runs the intelligence pipeline.
    # See docs/TRAINING_PLAN_REBUILD_PLAN.md Phase 2D.
    'morning-intelligence': {
        'task': 'tasks.run_morning_intelligence',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes, 24/7
    },
    # Weekly digest - every Monday at 9 AM UTC
    'send-weekly-digests': {
        'task': 'tasks.send_all_weekly_digests',
        'schedule': crontab(hour=9, minute=0, day_of_week=1),  # Monday
    },
}


