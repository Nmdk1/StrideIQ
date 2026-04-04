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
from core.cache import get_redis_client
from core.database import SessionLocal
from models import Athlete, Activity, CorrelationFinding

logger = logging.getLogger(__name__)
_BACKFILL_PROGRESS_TTL_S = 24 * 60 * 60

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


def _backfill_progress_key(athlete_id: str) -> str:
    return f"backfill_progress:{athlete_id}"


def _progress_hset(athlete_id: str, field: str, value: str) -> None:
    r = get_redis_client()
    if not r:
        return
    key = _backfill_progress_key(athlete_id)
    r.hset(key, field, value)
    r.expire(key, _BACKFILL_PROGRESS_TTL_S)


def _refresh_living_fingerprint_for_athlete(athlete_id: str, db) -> int:
    """
    Refresh fingerprint findings for one athlete only.
    """
    from services.race_input_analysis import mine_race_inputs
    from services.finding_persistence import store_all_findings

    findings, _gaps = mine_race_inputs(athlete_id, db)
    if findings:
        store_all_findings(athlete_id, findings, db)
        db.commit()
    return len(findings or [])


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

            # Lifecycle classification pass (Phase 3)
            try:
                from services.plan_framework.limiter_classifier import classify_lifecycle_states
                lc_results = classify_lifecycle_states(athlete_id, db)
                if lc_results:
                    db.commit()
                    logger.info("Lifecycle classification: %d findings classified for %s", len(lc_results), athlete_id)
            except Exception as exc:
                logger.warning("Lifecycle classification failed for %s: %s", athlete_id, exc)
                db.rollback()

            # Phase 5: Transition detection (active→resolving→closed)
            try:
                from services.plan_framework.limiter_classifier import check_transitions
                tr = check_transitions(athlete_id, db)
                any_transitions = sum(len(v) for v in tr.values())
                if any_transitions > 0:
                    db.commit()
                    logger.info(
                        "Transition check: %d transitions for %s "
                        "(a→r=%d, r→c=%d, r→a=%d, frontier=%d)",
                        any_transitions, athlete_id,
                        len(tr["active_to_resolving"]),
                        len(tr["resolving_to_closed"]),
                        len(tr["resolving_to_active"]),
                        len(tr["next_frontier"]),
                    )
            except Exception as exc:
                logger.warning("Transition check failed for %s: %s", athlete_id, exc)
                db.rollback()

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


@celery_app.task(
    name="tasks.run_athlete_first_session_sweep",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    soft_time_limit=240,
    time_limit=300,
)
def run_athlete_first_session_sweep(self, athlete_id: str) -> Dict:
    """
    Targeted first-session sweep for one athlete after Garmin backfill bursts.
    """
    db = SessionLocal()
    try:
        run_count = (
            db.query(Activity.id)
            .filter(
                Activity.athlete_id == athlete_id,
                Activity.sport == "run",
                Activity.is_duplicate == False,  # noqa: E712
            )
            .count()
        )
        if run_count < 10:
            try:
                _progress_hset(athlete_id, "sweep_complete", "true")
                _progress_hset(athlete_id, "findings_count", "0")
            except Exception:
                pass
            logger.info(
                "First-session sweep skipped for athlete %s (insufficient runs=%d)",
                athlete_id,
                run_count,
            )
            return {"status": "insufficient_data", "runs": run_count}

        from services.correlation_engine import analyze_correlations

        for metric in ALL_OUTPUT_METRICS:
            try:
                analyze_correlations(athlete_id, days=90, db=db, output_metric=metric)
            except Exception as exc:
                logger.warning("First-session metric failed for %s/%s: %s", athlete_id, metric, exc)
        db.commit()

        try:
            processed = _run_layer_pass(athlete_id, db)
            if processed > 0:
                db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning("First-session layer pass failed for %s: %s", athlete_id, exc)

        # Refresh fingerprint findings for this athlete only.
        try:
            _refresh_living_fingerprint_for_athlete(athlete_id, db)
        except Exception as exc:
            logger.warning("First-session fingerprint refresh failed for %s: %s", athlete_id, exc)

        # Always refresh briefing cache so first-session voice can pick up new data.
        try:
            from services.home_briefing_cache import mark_briefing_dirty
            from tasks.home_briefing_tasks import enqueue_briefing_refresh

            mark_briefing_dirty(str(athlete_id))
            enqueue_briefing_refresh(str(athlete_id), force=True, allow_circuit_probe=True)
        except Exception as exc:
            logger.warning("First-session briefing refresh failed for %s: %s", athlete_id, exc)

        findings_count = (
            db.query(CorrelationFinding.id)
            .filter(
                CorrelationFinding.athlete_id == athlete_id,
                CorrelationFinding.is_active == True,  # noqa: E712
            )
            .count()
        )
        try:
            _progress_hset(athlete_id, "sweep_complete", "true")
            _progress_hset(athlete_id, "findings_count", str(int(findings_count)))
        except Exception:
            pass

        return {
            "status": "ok",
            "runs": run_count,
            "findings_count": int(findings_count),
        }
    except Exception as exc:
        db.rollback()
        logger.exception("First-session sweep failed for %s: %s", athlete_id, exc)
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(name="tasks.backfill_lifecycle_states", bind=True, max_retries=0)
def backfill_lifecycle_states(self):
    """One-time backfill: classify lifecycle_state for all existing findings.

    Transitional task for Phase 3 deployment. Runs classify_lifecycle_states
    for every athlete who has CorrelationFinding rows with lifecycle_state IS NULL.
    After this runs once, the daily sweep + persist_correlation_findings keep
    states current. This task can be removed once all NULL states are resolved.
    """
    from services.plan_framework.limiter_classifier import classify_lifecycle_states

    db = SessionLocal()
    try:
        null_athletes = (
            db.query(CorrelationFinding.athlete_id)
            .filter(
                CorrelationFinding.lifecycle_state.is_(None),
                CorrelationFinding.is_active == True,  # noqa: E712
                CorrelationFinding.times_confirmed >= 3,
            )
            .distinct()
            .all()
        )
        athlete_ids = [str(r[0]) for r in null_athletes]
        logger.info("Lifecycle backfill: %d athletes with NULL lifecycle_state", len(athlete_ids))

        classified_total = 0
        for athlete_id in athlete_ids:
            try:
                results = classify_lifecycle_states(athlete_id, db)
                if results:
                    db.commit()
                    classified_total += len(results)
            except Exception as exc:
                db.rollback()
                logger.warning("Lifecycle backfill failed for %s: %s", athlete_id, exc)

        logger.info("Lifecycle backfill complete: %d findings classified across %d athletes",
                     classified_total, len(athlete_ids))
    finally:
        db.close()
