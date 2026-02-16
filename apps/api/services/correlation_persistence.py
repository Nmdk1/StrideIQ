"""
Correlation Finding Persistence

Stores significant correlation findings permanently with reproducibility
tracking.  Each time the correlation engine re-confirms a relationship,
the times_confirmed counter increments, building evidence weight.

Only findings that have been confirmed multiple times (reproducible) are
eligible for surfacing to athletes through narration.

Principles:
    - Silence > noise: don't surface until the pattern is reproducible.
    - Patterns can fade: if a finding drops below significance on a later
      run, is_active is set to False.
    - Cooldown: once surfaced, a finding won't be re-surfaced until the
      cooldown period elapses.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import and_

from models import CorrelationFinding

logger = logging.getLogger(__name__)

# --- Configuration ---
# Minimum confirmations before a finding is eligible for surfacing.
SURFACING_THRESHOLD = 3

# Days after surfacing before the same finding can be shown again.
SURFACING_COOLDOWN_DAYS = 14

# Statistical gates (mirror correlation_engine thresholds).
MIN_CORRELATION_STRENGTH = 0.3
SIGNIFICANCE_LEVEL = 0.05
MIN_SAMPLE_SIZE = 10


def persist_correlation_findings(
    athlete_id: UUID,
    analysis_result: Dict,
    db: Session,
    output_metric: str = "efficiency",
) -> Dict[str, int]:
    """
    Upsert significant correlation findings from an analysis run.

    For each significant correlation in the result:
    - If a matching finding exists: increment times_confirmed, update stats.
    - If new: create with times_confirmed = 1.

    For previously-active findings not in the current result set:
    - Mark is_active = False (pattern has faded).

    Args:
        athlete_id: Athlete UUID.
        analysis_result: Output from correlation_engine.analyze_correlations().
        db: Database session.
        output_metric: The output metric used in this analysis run.

    Returns:
        Dict with counts: {"created": N, "confirmed": N, "deactivated": N}
    """
    correlations = analysis_result.get("correlations", [])
    if not correlations and "error" in analysis_result:
        return {"created": 0, "confirmed": 0, "deactivated": 0}

    now = datetime.now(timezone.utc)
    stats = {"created": 0, "confirmed": 0, "deactivated": 0}

    # Build set of (input_name, output_metric, time_lag_days) from current run
    current_keys = set()

    for corr in correlations:
        input_name = corr.get("input_name", "")
        direction = corr.get("direction", "positive")
        lag = corr.get("time_lag_days", 0)
        r = corr.get("correlation_coefficient", 0.0)
        p = corr.get("p_value", 1.0)
        n = corr.get("sample_size", 0)
        strength = corr.get("strength", "weak")

        # Only persist findings that pass significance gates
        if abs(r) < MIN_CORRELATION_STRENGTH or p >= SIGNIFICANCE_LEVEL or n < MIN_SAMPLE_SIZE:
            continue

        current_keys.add((input_name, output_metric, lag))

        # Build category and confidence from N1 insight logic
        category = _categorize_finding(direction, output_metric)
        confidence = _compute_confidence(r, p, n)
        insight_text = _build_finding_text(input_name, direction, strength, r, lag, output_metric)

        # Upsert: find existing or create
        existing = (
            db.query(CorrelationFinding)
            .filter(
                CorrelationFinding.athlete_id == athlete_id,
                CorrelationFinding.input_name == input_name,
                CorrelationFinding.output_metric == output_metric,
                CorrelationFinding.time_lag_days == lag,
            )
            .first()
        )

        if existing:
            existing.times_confirmed += 1
            existing.last_confirmed_at = now
            existing.correlation_coefficient = r
            existing.p_value = p
            existing.sample_size = n
            existing.strength = strength
            existing.direction = direction
            existing.confidence = confidence
            existing.category = category
            existing.insight_text = insight_text
            existing.is_active = True  # Re-activate if previously faded
            stats["confirmed"] += 1
        else:
            finding = CorrelationFinding(
                athlete_id=athlete_id,
                input_name=input_name,
                output_metric=output_metric,
                direction=direction,
                time_lag_days=lag,
                correlation_coefficient=r,
                p_value=p,
                sample_size=n,
                strength=strength,
                times_confirmed=1,
                first_detected_at=now,
                last_confirmed_at=now,
                insight_text=insight_text,
                category=category,
                confidence=confidence,
                is_active=True,
            )
            db.add(finding)
            stats["created"] += 1

    # Deactivate previously-active findings for this output_metric that
    # were NOT confirmed in this run (pattern has faded).
    active_findings = (
        db.query(CorrelationFinding)
        .filter(
            CorrelationFinding.athlete_id == athlete_id,
            CorrelationFinding.output_metric == output_metric,
            CorrelationFinding.is_active == True,  # noqa: E712
        )
        .all()
    )

    for finding in active_findings:
        key = (finding.input_name, finding.output_metric, finding.time_lag_days)
        if key not in current_keys:
            finding.is_active = False
            stats["deactivated"] += 1

    try:
        db.flush()
    except Exception as e:
        logger.error(f"Failed to persist correlation findings for {athlete_id}: {e}")
        db.rollback()
        return {"created": 0, "confirmed": 0, "deactivated": 0, "error": str(e)}

    logger.info(
        f"Correlation findings for {athlete_id}: "
        f"created={stats['created']}, confirmed={stats['confirmed']}, "
        f"deactivated={stats['deactivated']}"
    )
    return stats


def get_surfaceable_findings(
    athlete_id: UUID,
    db: Session,
    min_confirmations: int = SURFACING_THRESHOLD,
    cooldown_days: int = SURFACING_COOLDOWN_DAYS,
) -> List[CorrelationFinding]:
    """
    Get reproducible, active findings eligible for surfacing.

    A finding is surfaceable when:
    1. is_active is True
    2. times_confirmed >= min_confirmations
    3. It hasn't been surfaced in the last cooldown_days

    Returns findings sorted by (times_confirmed * confidence) descending,
    so the strongest, most-reproduced patterns come first.
    """
    now = datetime.now(timezone.utc)
    cooldown_cutoff = now - timedelta(days=cooldown_days)

    findings = (
        db.query(CorrelationFinding)
        .filter(
            CorrelationFinding.athlete_id == athlete_id,
            CorrelationFinding.is_active == True,  # noqa: E712
            CorrelationFinding.times_confirmed >= min_confirmations,
        )
        .all()
    )

    # Filter by cooldown: exclude findings surfaced too recently
    eligible = []
    for f in findings:
        if f.last_surfaced_at is None or f.last_surfaced_at < cooldown_cutoff:
            eligible.append(f)

    # Sort by reproducibility weight: times_confirmed * confidence
    eligible.sort(
        key=lambda f: f.times_confirmed * f.confidence,
        reverse=True,
    )

    return eligible


def mark_surfaced(finding_ids: List[UUID], db: Session) -> None:
    """Mark findings as surfaced (resets cooldown timer)."""
    now = datetime.now(timezone.utc)
    if not finding_ids:
        return
    db.query(CorrelationFinding).filter(
        CorrelationFinding.id.in_(finding_ids),
    ).update(
        {"last_surfaced_at": now},
        synchronize_session="fetch",
    )


# ---------------------------------------------------------------------------
# Internal helpers (mirror n1_insight_generator logic)
# ---------------------------------------------------------------------------

def _categorize_finding(direction: str, output_metric: str) -> str:
    """Categorize a finding as what_works, what_doesnt, or pattern."""
    try:
        from services.n1_insight_generator import _is_beneficial
        beneficial = _is_beneficial(direction, output_metric)
    except ImportError:
        beneficial = None

    if beneficial is None:
        return "pattern"
    return "what_works" if beneficial else "what_doesnt"


def _compute_confidence(r: float, p: float, n: int) -> float:
    """Compute confidence score (mirrors n1_insight_generator)."""
    import math
    effect = min(abs(r), 1.0)
    volume = min(math.log(max(n, 1)) / math.log(100), 1.0)
    sig = max(1.0 - p, 0.0)
    return round(0.4 * effect + 0.3 * volume + 0.3 * sig, 3)


def _build_finding_text(
    input_name: str,
    direction: str,
    strength: str,
    r: float,
    lag_days: int,
    output_metric: str,
) -> str:
    """Build human-readable insight text (mirrors n1_insight_generator)."""
    try:
        from services.n1_insight_generator import _build_insight_text
        return _build_insight_text(
            input_name=input_name,
            direction=direction,
            strength=strength,
            r=r,
            lag_days=lag_days,
            output_metric=output_metric,
        )
    except ImportError:
        return f"{input_name} has a {strength} {direction} correlation with {output_metric}"
