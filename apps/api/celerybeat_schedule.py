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
    # Stale stream fetch cleanup (ADR-063): reset activities stuck in
    # 'fetching' for >10 minutes (worker died mid-fetch).
    'cleanup-stale-stream-fetches': {
        'task': 'tasks.cleanup_stale_stream_fetches',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    # ADR-065: refresh home briefings for athletes active in last 24h
    'refresh-home-briefings': {
        'task': 'tasks.refresh_active_home_briefings',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    # Garmin ingestion health check — daily at 07:00 UTC
    # Logs underfed athletes (sleep/HRV < 50% coverage over last 7 days).
    'garmin-ingestion-health-check': {
        'task': 'tasks.check_garmin_ingestion_health',
        'schedule': crontab(hour=7, minute=0),
    },
    # Daily correlation sweep — after morning intelligence.
    # Runs analyze_correlations() for all 9 output metrics for athletes
    # with new data in the last 24h.
    'daily-correlation-sweep': {
        'task': 'tasks.run_daily_correlation_sweep',
        'schedule': crontab(hour=8, minute=0),
    },
    # Living Fingerprint refresh — daily at 06:00 UTC.
    # Re-runs all investigations for athletes with new data in the last 24h,
    # persists updated findings, and refreshes training story cache.
    'fingerprint-refresh': {
        'task': 'tasks.refresh_living_fingerprint',
        'schedule': crontab(hour=6, minute=0),
    },
    # Daily experience guardrail — 06:15 UTC.
    # Runs after morning intelligence (05:00 local) and Garmin sync.
    # Audits all athlete-facing surfaces for data truth, language hygiene,
    # structural integrity, and trust violations. Founder-only in v1.
    'daily-experience-guardrail': {
        'task': 'tasks.run_experience_guardrail',
        'schedule': crontab(hour=6, minute=15),
    },
}


