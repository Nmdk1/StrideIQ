"""
Celery Beat Schedule Configuration

Defines periodic tasks that run on a schedule.
"""

from celery.schedules import crontab

# Schedule configuration
beat_schedule = {
    # Weekly digest - every Monday at 9 AM UTC
    'send-weekly-digests': {
        'task': 'tasks.send_all_weekly_digests',
        'schedule': crontab(hour=9, minute=0, day_of_week=1),  # Monday
    },
}


