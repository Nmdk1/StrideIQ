"""
Finding eligibility — the single chokepoint for which CorrelationFinding rows
are allowed to reach an athlete-facing surface.

Why this module exists
----------------------
Before this module, every surface (home briefing, chat coach brief, daily
intelligence, Operating Manual, Activity findings, Progress page, first
insights) loaded CorrelationFinding rows with its own filter set. Each
surface implemented a different subset of the rules. The result, in
production, was that the engine produced findings flagged
``direction_counterintuitive=True`` precisely so consumers could suppress
them, and consumers happily narrated them to athletes anyway.

This module is the answer to that. Every athlete-facing surface that
selects findings goes through ``select_eligible_findings``. New gates are
added here once and inherited everywhere.

Gates applied (in order)
------------------------
1. ``is_active`` is True.
2. ``times_confirmed >= min_confirmations``.
3. ``input_name`` is not in the per-athlete suppression set, the global
   passive-noise set, or the universally-true environment set.
4. ``direction_counterintuitive`` is False — the engine flagged the row
   as physiologically backwards, the narrator must not surface it as
   truth. This stops "higher resting heart rate means better efficiency"
   from reaching an athlete.
5. ``is_confounded`` is False — defensive. Confounded rows are already
   deactivated at persistence time but we re-check here in case the row
   was activated by a later code path.
6. Sleep-derived inputs (``garmin_sleep_*``, ``sleep_hours``, ``sleep_h``,
   ``sleep_quality_1_5``) are dropped when the athlete's recent sleep
   data is not trustworthy (mostly ``ENHANCED_TENTATIVE`` or missing
   ``sleep_score`` over the recent window). The same gate that strips
   sleep claims from briefings now strips sleep-derived correlations
   from every consumer.
7. Contradictory-signs deduplication — if two active rows describe the
   same ``(input_name, output_metric)`` pair (within a small lag window)
   with opposite directions, both are dropped until one is reconciled.
   The athlete's body does not respond two opposite ways to the same
   input on the same day; presenting both as confirmed truth is a
   trust rupture.

What this module does not do
----------------------------
It does not change persistence. Counterintuitive, confounded, or
contradictory rows still live in the DB and are still available to the
correlation engine for internal analysis, audit, and future reconciliation.
This module is a display-time gate.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, List, Optional, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from models import CorrelationFinding, GarminDay

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Suppressed signal sets (mirrors fingerprint_context for backward-compat,
# kept here so this module can stand alone if fingerprint_context is later
# refactored).
# ---------------------------------------------------------------------------

PASSIVE_NOISE_SIGNALS: frozenset = frozenset(
    {
        "active_kcal",
        "daily_active_kcal",
        "garmin_active_kcal",
        "garmin_steps",
        "daily_step_count",
        "garmin_active_time_s",
        "garmin_body_battery_end",
        "garmin_avg_stress",
        "garmin_max_stress",
        "garmin_aerobic_te",
        "garmin_anaerobic_te",
        "garmin_body_battery_impact",
    }
)

ENVIRONMENT_SIGNALS: frozenset = frozenset(
    {
        "dew_point_f",
        "temperature_f",
        "humidity_pct",
        "heat_adjustment_pct",
    }
)

SUPPRESSED_INTERACTION_SIGNALS: frozenset = frozenset(
    {
        "heat_stress_index",
    }
)


SLEEP_DERIVED_INPUTS: frozenset = frozenset(
    {
        "sleep_hours",
        "sleep_h",
        "sleep_quality_1_5",
        "garmin_sleep_total_s",
        "garmin_sleep_deep_s",
        "garmin_sleep_light_s",
        "garmin_sleep_rem_s",
        "garmin_sleep_awake_s",
        "garmin_sleep_score",
    }
)

# Sleep validity window — number of recent days to inspect when deciding
# whether sleep-derived correlations are trustworthy enough to surface.
SLEEP_VALIDITY_WINDOW_DAYS = 14

# If more than this fraction of the recent window has tentative or missing
# sleep data, sleep-derived findings are gated out.
SLEEP_VALIDITY_INVALID_THRESHOLD = 0.5

# Lag tolerance (days) for the contradictory-signs check. Two active
# findings on the same (input_name, output_metric) with opposite directions
# and lags within this window are considered concurrent.
CONTRADICTORY_LAG_TOLERANCE_DAYS = 3


def is_signal_suppressed(input_name: str) -> bool:
    """True if ``input_name`` should never reach an athlete-facing surface.

    Derived signals and interaction terms inherit suppression from their
    parent signals. The engine still computes them — suppression is a
    display-time decision, not a computation-time decision.
    """
    if input_name in PASSIVE_NOISE_SIGNALS or input_name in ENVIRONMENT_SIGNALS:
        return True
    if input_name in SUPPRESSED_INTERACTION_SIGNALS:
        return True
    for parent in PASSIVE_NOISE_SIGNALS | ENVIRONMENT_SIGNALS:
        if input_name.startswith(parent + "_"):
            return True
    return False


def is_sleep_derived(input_name: str) -> bool:
    """True if ``input_name`` reads from athlete sleep data.

    Used to decide whether to apply the sleep-validity gate to a finding.
    """
    if input_name in SLEEP_DERIVED_INPUTS:
        return True
    return input_name.startswith("garmin_sleep_") or input_name.startswith("sleep_")


def is_recent_sleep_invalid(
    athlete_id: UUID,
    db: Session,
    *,
    today: Optional[date] = None,
    window_days: int = SLEEP_VALIDITY_WINDOW_DAYS,
    invalid_threshold: float = SLEEP_VALIDITY_INVALID_THRESHOLD,
) -> bool:
    """True if the athlete's recent sleep data is not trustworthy.

    A day counts as invalid when ``sleep_validation`` is one of the Garmin
    tentative markers OR ``sleep_score`` is missing. If the fraction of
    invalid days in the recent window exceeds ``invalid_threshold``, the
    window is treated as untrustworthy.

    Returns False when there is no GarminDay data at all — the gate fires
    only when there is enough data to decide it is bad. Surfaces that need
    a stricter rule (e.g. "no recent sleep data at all means no sleep
    findings") can compose this with their own check.
    """
    today = today or date.today()
    window_start = today - timedelta(days=window_days)

    rows = (
        db.query(GarminDay)
        .filter(
            GarminDay.athlete_id == athlete_id,
            GarminDay.calendar_date >= window_start,
            GarminDay.calendar_date <= today,
        )
        .all()
    )

    if not rows:
        return False

    invalid_markers = {"ENHANCED_TENTATIVE", "TENTATIVE", "INVALID"}
    invalid_count = 0
    for row in rows:
        validation = (row.sleep_validation or "").upper()
        if validation in invalid_markers:
            invalid_count += 1
            continue
        if row.sleep_score is None:
            invalid_count += 1
            continue

    fraction_invalid = invalid_count / len(rows)
    return fraction_invalid > invalid_threshold


def _drop_contradictory_pairs(
    findings: Sequence[CorrelationFinding],
    *,
    lag_tolerance_days: int = CONTRADICTORY_LAG_TOLERANCE_DAYS,
) -> List[CorrelationFinding]:
    """Drop both rows in any pair with the same input+output but opposite signs.

    Two findings are considered contradictory when they share
    ``(input_name, output_metric)``, have opposite ``direction`` values,
    and their ``time_lag_days`` differ by no more than
    ``lag_tolerance_days``.

    The intent is to suppress the trust rupture where the same input is
    surfaced to the athlete twice with opposite physiological meanings.
    Reconciliation happens upstream — this layer only refuses to narrate
    the conflict.
    """
    if not findings:
        return list(findings)

    keep_ids = {f.id for f in findings}

    by_pair: dict[tuple[str, str], list[CorrelationFinding]] = {}
    for f in findings:
        by_pair.setdefault((f.input_name, f.output_metric), []).append(f)

    for pair_findings in by_pair.values():
        if len(pair_findings) < 2:
            continue
        for i, a in enumerate(pair_findings):
            for b in pair_findings[i + 1 :]:
                if (a.direction or "").lower() == (b.direction or "").lower():
                    continue
                lag_a = int(a.time_lag_days or 0)
                lag_b = int(b.time_lag_days or 0)
                if abs(lag_a - lag_b) > lag_tolerance_days:
                    continue
                keep_ids.discard(a.id)
                keep_ids.discard(b.id)

    return [f for f in findings if f.id in keep_ids]


def select_eligible_findings(
    athlete_id: UUID,
    db: Session,
    *,
    min_confirmations: int = 3,
    limit: Optional[int] = None,
    output_metrics: Optional[Iterable[str]] = None,
    additional_suppressed_inputs: Optional[Iterable[str]] = None,
    today: Optional[date] = None,
    cooldown_days: Optional[int] = None,
    sleep_invalid_override: Optional[bool] = None,
) -> List[CorrelationFinding]:
    """Return the CorrelationFinding rows allowed on an athlete-facing surface.

    Parameters
    ----------
    athlete_id:
        The athlete whose findings are being surfaced.
    db:
        Active SQLAlchemy session.
    min_confirmations:
        Minimum ``times_confirmed``. Surfaces that show emerging patterns
        explicitly (e.g. fingerprint context with ``min_confirmed=1``) can
        pass a lower value, but the default mirrors the production
        surfacing threshold.
    limit:
        Optional cap on returned rows. Applied after sorting by reproducibility.
    output_metrics:
        Optional restriction on ``output_metric`` values.
    additional_suppressed_inputs:
        Per-call suppression of specific input names (e.g. an athlete-set
        suppression list).
    today:
        Override today (used by tests).
    cooldown_days:
        If provided, exclude findings surfaced within the cooldown window.
        Surfaces that do not need cooldown semantics (e.g. Operating
        Manual, fingerprint prompt injection) leave this as None.
    sleep_invalid_override:
        Test hook. When None, the helper computes recent sleep validity
        from GarminDay rows. Pass a bool to bypass the DB lookup.

    Returns
    -------
    A list of CorrelationFinding rows sorted by
    ``times_confirmed * confidence`` descending.
    """
    today = today or date.today()
    suppressed: set[str] = set(additional_suppressed_inputs or [])

    query = db.query(CorrelationFinding).filter(
        CorrelationFinding.athlete_id == athlete_id,
        CorrelationFinding.is_active.is_(True),
        CorrelationFinding.times_confirmed >= min_confirmations,
        CorrelationFinding.is_confounded.is_(False),
        CorrelationFinding.direction_counterintuitive.is_(False),
    )

    if output_metrics:
        query = query.filter(CorrelationFinding.output_metric.in_(list(output_metrics)))

    rows: List[CorrelationFinding] = query.all()

    if not rows:
        return []

    if sleep_invalid_override is None:
        sleep_invalid = is_recent_sleep_invalid(athlete_id, db, today=today)
    else:
        sleep_invalid = bool(sleep_invalid_override)

    eligible: List[CorrelationFinding] = []
    for row in rows:
        if row.input_name in suppressed:
            continue
        if is_signal_suppressed(row.input_name):
            continue
        if sleep_invalid and is_sleep_derived(row.input_name):
            continue
        if cooldown_days is not None and row.last_surfaced_at is not None:
            cooldown_cutoff = datetime.now(timezone.utc) - timedelta(days=cooldown_days)
            if row.last_surfaced_at >= cooldown_cutoff:
                continue
        eligible.append(row)

    eligible = _drop_contradictory_pairs(eligible)

    eligible.sort(
        key=lambda f: (f.times_confirmed or 0) * (f.confidence or 0.0),
        reverse=True,
    )

    if limit is not None:
        eligible = eligible[:limit]

    return eligible
