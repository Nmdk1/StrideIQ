"""
Daily Correlation Sweep

Runs analyze_correlations() for every output metric for athletes with
recent activity.  Populates CorrelationFinding rows that the Progress
page reads.  Respects existing confounder + direction quality gates.

After the first pass (correlation discovery + persistence), a second
pass runs Layers 1–4 on all confirmed findings (times_confirmed >= 3).

Schedule: daily at 08:00 UTC (after morning intelligence).
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

from tasks import celery_app
from core.database import SessionLocal
from models import Athlete, Activity, CorrelationFinding

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


def _aggregate_output_for_metric(
    metric: str,
    athlete_id: str,
    start_date: datetime,
    end_date: datetime,
    db,
) -> List[Tuple[datetime, float]]:
    """Re-aggregate output data for a specific metric."""
    from services.correlation_engine import (
        aggregate_efficiency_outputs,
        aggregate_pace_at_effort,
        aggregate_workout_completion,
        aggregate_efficiency_by_effort_zone,
        aggregate_efficiency_trend,
        aggregate_pb_events,
        aggregate_race_pace,
    )

    if metric == "efficiency":
        return aggregate_efficiency_outputs(athlete_id, start_date, end_date, db)
    elif metric == "pace_easy":
        return aggregate_pace_at_effort(athlete_id, start_date, end_date, db, "easy")
    elif metric == "pace_threshold":
        return aggregate_pace_at_effort(athlete_id, start_date, end_date, db, "threshold")
    elif metric == "completion":
        return aggregate_workout_completion(athlete_id, start_date, end_date, db)
    elif metric == "efficiency_threshold":
        return aggregate_efficiency_by_effort_zone(athlete_id, start_date, end_date, db, "threshold")
    elif metric == "efficiency_race":
        return aggregate_efficiency_by_effort_zone(athlete_id, start_date, end_date, db, "race")
    elif metric == "efficiency_trend":
        return aggregate_efficiency_trend(athlete_id, start_date, end_date, db, "threshold")
    elif metric == "pb_events":
        return aggregate_pb_events(athlete_id, start_date, end_date, db)
    elif metric == "race_pace":
        return aggregate_race_pace(athlete_id, start_date, end_date, db)
    return []


def _run_layer_pass(athlete_id: str, db) -> int:
    """
    Second pass: run Layers 1–4 on confirmed findings for one athlete.

    Returns the number of findings processed.
    """
    from services.correlation_engine import (
        aggregate_daily_inputs,
        aggregate_training_load_inputs,
        aggregate_daily_session_stress,
    )
    from services.correlation_layers import run_layer_analysis

    confirmed = db.query(CorrelationFinding).filter(
        CorrelationFinding.athlete_id == athlete_id,
        CorrelationFinding.is_active == True,  # noqa: E712
        CorrelationFinding.times_confirmed >= 3,
    ).all()

    if not confirmed:
        return 0

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=90)

    all_inputs = aggregate_daily_inputs(athlete_id, start_date, end_date, db)
    load_inputs = aggregate_training_load_inputs(athlete_id, start_date, end_date, db)
    all_inputs.update(load_inputs)
    all_inputs["daily_session_stress"] = aggregate_daily_session_stress(
        athlete_id, start_date, end_date, db,
    )

    output_cache: Dict[str, List] = {}
    processed = 0

    for finding in confirmed:
        metric = finding.output_metric
        if metric not in output_cache:
            output_cache[metric] = _aggregate_output_for_metric(
                metric, athlete_id, start_date, end_date, db,
            )

        input_data = all_inputs.get(finding.input_name)
        output_data = output_cache[metric]

        if not input_data or not output_data:
            continue

        try:
            run_layer_analysis(finding, input_data, output_data, all_inputs, db)
            processed += 1
        except Exception as exc:
            logger.warning(
                "Layer analysis failed for finding %s (%s→%s): %s",
                finding.id, finding.input_name, finding.output_metric, exc,
            )

    return processed


@celery_app.task(name="tasks.run_daily_correlation_sweep", bind=True, max_retries=0)
def run_daily_correlation_sweep(self, athlete_ids: List[str] | None = None):
    """
    Sweep all output metrics for athletes with activity in the last 24h.

    If ``athlete_ids`` is provided, runs only for those athletes (used
    for manual backfills).  Otherwise discovers eligible athletes.

    After the first pass, runs Layers 1–4 on confirmed findings.
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
            # First pass: discover and persist correlations
            for metric in ALL_OUTPUT_METRICS:
                try:
                    analyze_correlations(athlete_id, days=90, db=db, output_metric=metric)
                except Exception as exc:
                    logger.warning(
                        "Correlation sweep failed for %s/%s: %s",
                        athlete_id, metric, exc,
                    )
            db.commit()

            # Second pass: Layers 1–4 on confirmed findings
            try:
                n = _run_layer_pass(athlete_id, db)
                if n > 0:
                    db.commit()
                    logger.info("Layer analysis: %d confirmed findings processed for %s", n, athlete_id)
            except Exception as exc:
                logger.warning("Layer analysis pass failed for %s: %s", athlete_id, exc)
                db.rollback()

        logger.info("Correlation sweep complete for %d athletes", len(ids))
    finally:
        db.close()
