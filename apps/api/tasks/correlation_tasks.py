"""
Daily Correlation Sweep

Runs analyze_correlations() for every output metric for athletes with
recent activity.  Populates CorrelationFinding rows that the Progress
page reads.  Respects existing confounder + direction quality gates.

Schedule: daily at 08:00 UTC (after morning intelligence).
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List

from tasks import celery_app
from core.database import SessionLocal
from models import Athlete, Activity

logger = logging.getLogger(__name__)

ALL_OUTPUT_METRICS = [
    "efficiency",
    "pace_easy",
    "pace_threshold",
    "completion",
    "efficiency_threshold",
    "efficiency_race",
    "efficiency_trend",
    "pb_events",
    "race_pace",
]


@celery_app.task(name="tasks.run_daily_correlation_sweep", bind=True, max_retries=0)
def run_daily_correlation_sweep(self, athlete_ids: List[str] | None = None):
    """
    Sweep all output metrics for athletes with activity in the last 24h.

    If ``athlete_ids`` is provided, runs only for those athletes (used
    for manual backfills).  Otherwise discovers eligible athletes.
    """
    db = SessionLocal()
    try:
        if athlete_ids:
            ids = athlete_ids
        else:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            rows = (
                db.query(Activity.athlete_id)
                .filter(Activity.start_time >= cutoff)
                .distinct()
                .all()
            )
            ids = [str(r[0]) for r in rows]

        logger.info("Correlation sweep: %d athletes, %d metrics", len(ids), len(ALL_OUTPUT_METRICS))

        from services.correlation_engine import analyze_correlations

        for athlete_id in ids:
            for metric in ALL_OUTPUT_METRICS:
                try:
                    analyze_correlations(athlete_id, days=90, db=db, output_metric=metric)
                except Exception as exc:
                    logger.warning(
                        "Correlation sweep failed for %s/%s: %s",
                        athlete_id, metric, exc,
                    )
            db.commit()

        logger.info("Correlation sweep complete for %d athletes", len(ids))
    finally:
        db.close()
