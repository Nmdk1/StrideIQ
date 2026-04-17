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
    "morning-intelligence": {
        "task": "tasks.run_morning_intelligence",
        "schedule": crontab(minute="*/15"),  # Every 15 minutes, 24/7
    },
    # Weekly digest - every Monday at 9 AM UTC
    "send-weekly-digests": {
        "task": "tasks.send_all_weekly_digests",
        "schedule": crontab(hour=9, minute=0, day_of_week=1),  # Monday
    },
    # Stale stream fetch cleanup (ADR-063): reset activities stuck in
    # 'fetching' for >10 minutes (worker died mid-fetch).
    "cleanup-stale-stream-fetches": {
        "task": "tasks.cleanup_stale_stream_fetches",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
    # Strava activity stream backfill (ADR-063): eligible activities without streams.
    # Task discovers athletes with pending work; loops batches until read budget < 20.
    "backfill-strava-streams": {
        "task": "tasks.backfill_strava_streams",
        "schedule": crontab(minute="*/30"),
        "kwargs": {"batch_size": 10},
    },
    # ADR-065: refresh home briefings for athletes active in last 24h
    "refresh-home-briefings": {
        "task": "tasks.refresh_active_home_briefings",
        "schedule": crontab(minute="*/15"),  # Every 15 minutes
    },
    # Garmin ingestion health check — daily at 07:00 UTC
    # Logs underfed athletes (sleep/HRV < 50% coverage over last 7 days).
    "garmin-ingestion-health-check": {
        "task": "tasks.check_garmin_ingestion_health",
        "schedule": crontab(hour=7, minute=0),
    },
    # Garmin stream backlog auto-heal — every 10 minutes.
    # Fail-closes stale push-driven pending/fetching/failed rows with no stream
    # to unavailable so chart surfaces do not remain in perpetual "analyzing".
    "garmin-stream-stale-cleanup": {
        "task": "tasks.cleanup_stale_garmin_pending_streams",
        "schedule": crontab(minute="*/10"),
    },
    # Garmin -> Strava fallback sweep — every 15 minutes.
    # Defense-in-depth: catches any 'unavailable' Garmin row that the
    # webhook handler or cleanup beat failed to enqueue (e.g. broker hiccup,
    # future code path that adds a third transition, or one-time backfill of
    # historically affected rows).  Idempotent: the repair task's atomic
    # claim makes duplicate enqueues harmless.  Bounded per-run so a large
    # backfill spreads across cycles.
    "garmin-fallback-sweep": {
        "task": "tasks.sweep_unavailable_garmin_streams",
        "schedule": crontab(minute="*/15"),
    },
    # Daily correlation sweep — after morning intelligence.
    # Runs analyze_correlations() for all 9 output metrics for athletes
    # with new data in the last 24h.
    "daily-correlation-sweep": {
        "task": "tasks.run_daily_correlation_sweep",
        "schedule": crontab(hour=8, minute=0),
    },
    # Living Fingerprint refresh — daily at 06:00 UTC.
    # Re-runs all investigations for athletes with new data in the last 24h,
    # persists updated findings, and refreshes training story cache.
    "fingerprint-refresh": {
        "task": "tasks.refresh_living_fingerprint",
        "schedule": crontab(hour=6, minute=0),
    },
    # Daily experience guardrail — 06:15 UTC.
    # Runs after morning intelligence (05:00 local) and Garmin sync.
    # Audits all athlete-facing surfaces for data truth, language hygiene,
    # structural integrity, and trust violations. Founder-only in v1.
    "daily-experience-guardrail": {
        "task": "tasks.run_experience_guardrail",
        "schedule": crontab(hour=6, minute=15),
    },
    # AutoDiscovery nightly shadow pass — 04:00 UTC, founder-only.
    # Gated by feature flag 'auto_discovery.enabled'.
    # Phase 0A: correlation multi-window rescan only.
    "auto-discovery-nightly": {
        "task": "tasks.run_auto_discovery_nightly",
        "schedule": crontab(hour=4, minute=0),
    },
    # Timezone backfill — daily at 03:00 UTC.
    # Infers and persists IANA timezone for athletes with NULL/invalid timezone
    # using GPS coordinates from their most recent activity. Idempotent.
    "timezone-backfill": {
        "task": "tasks.backfill_athlete_timezones",
        "schedule": crontab(hour=3, minute=0),
    },
    # Plan lifecycle cleanup — complete active plans once race date has passed.
    "complete-expired-plans": {
        "task": "tasks.complete_expired_plans",
        "schedule": crontab(hour=2, minute=0),
    },
    # Workout classification safety-net sweep — every 30 minutes.
    # Defense-in-depth for the Compare tab.  The Garmin webhook ingest path
    # used to silently fail to classify (TypeError on bad call signature,
    # swallowed by broad except).  That left workout_type=NULL for every
    # Garmin-primary athlete and broke tiers 3 and 4 of the Compare service
    # for the population.  Even after fixing the call site, this sweep
    # guarantees that any future code path which creates an activity
    # without classifying it (or classification raises on a malformed row)
    # gets healed within one cycle so the population-level breakage cannot
    # silently recur.
    "workout-classify-sweep": {
        "task": "tasks.sweep_unclassified_runs",
        "schedule": crontab(minute="*/30"),
    },
}
