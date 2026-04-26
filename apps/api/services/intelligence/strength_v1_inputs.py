"""Strength v1 — additive engine inputs (phase I).

This module adds the two engine input families specified in
``docs/specs/STRENGTH_V1_SCOPE.md`` §8.1:

  1. **Per-set RPE rollups** — average and max RPE per strength
     session, exposed to the correlation engine so it can detect
     things like "high-RPE sessions correlate with worse next-day
     run efficiency" purely from this athlete's data.

  2. **Symptom-log counts** — rolling 28-day counts of niggles,
     aches, pains, plus a 0/1 active-injury flag, derived from
     ``BodyAreaSymptomLog`` rows. Lets the engine relate symptom
     burden to running outputs.

Both families are **additive**: they extend the inputs dict produced
by :func:`aggregate_cross_training_inputs` without mutating any
existing series. Adding more candidate inputs cannot change the
statistics of pre-existing input/output pairs.

Surface gating (n ≥ 4 sample size **AND** p < 0.05 before any
strength-domain finding renders to athletes) lives in
:mod:`services.operating_manual` — the engine still records every
finding for tuning analysis. See ``test_operating_manual_strength_phase_h.py``
and the new ``test_strength_v1_engine_inputs_phase_i.py``.

Design contract: this module never writes athlete-facing copy.
It produces numeric series only.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date as date_type, datetime, timedelta
from typing import Dict, List, Tuple
from uuid import UUID

from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Per-set RPE rollups
# ---------------------------------------------------------------------------


def aggregate_per_set_rpe_inputs(
    athlete_id: str | UUID,
    start_date: datetime,
    end_date: datetime,
    db: Session,
) -> Dict[str, List[Tuple[date_type, float]]]:
    """Return per-day RPE rollups for strength sessions in the window.

    Output series (only included when at least one session in the
    window has at least one RPE-tagged set):

      ``ct_strength_avg_rpe_per_session``
          One value per session date; mean RPE across active sets
          that recorded an ``rpe`` value. Skips sessions with no
          RPE data instead of imputing zero — imputation would
          poison the correlation.

      ``ct_strength_max_rpe_per_session``
          Per-session max RPE (peak intensity proxy).

    These are time series in the same shape as the rest of
    :func:`aggregate_cross_training_inputs` output.
    """
    from models import Activity, StrengthExerciseSet

    strength_activities = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.sport == "strength",
            Activity.start_time >= start_date,
            Activity.start_time <= end_date,
        )
        .order_by(Activity.start_time)
        .all()
    )
    if not strength_activities:
        return {}

    activity_ids = [a.id for a in strength_activities]

    sets_with_rpe = (
        db.query(
            StrengthExerciseSet.activity_id,
            StrengthExerciseSet.rpe,
        )
        .filter(
            StrengthExerciseSet.activity_id.in_(activity_ids),
            StrengthExerciseSet.set_type == "active",
            StrengthExerciseSet.rpe.isnot(None),
            StrengthExerciseSet.superseded_at.is_(None),
        )
        .all()
    )
    if not sets_with_rpe:
        return {}

    rpe_by_activity: Dict = defaultdict(list)
    for activity_id, rpe in sets_with_rpe:
        if rpe is None:
            continue
        rpe_by_activity[activity_id].append(float(rpe))

    avg_series: List[Tuple[date_type, float]] = []
    max_series: List[Tuple[date_type, float]] = []

    for act in strength_activities:
        rpes = rpe_by_activity.get(act.id)
        if not rpes:
            continue
        d = act.start_time.date()
        avg_series.append((d, round(sum(rpes) / len(rpes), 2)))
        max_series.append((d, round(max(rpes), 2)))

    out: Dict[str, List[Tuple[date_type, float]]] = {}
    if avg_series:
        out["ct_strength_avg_rpe_per_session"] = sorted(avg_series)
    if max_series:
        out["ct_strength_max_rpe_per_session"] = sorted(max_series)
    return out


# ---------------------------------------------------------------------------
# Symptom-log inputs
# ---------------------------------------------------------------------------

# The four severity tiers exactly as declared on
# ``BodyAreaSymptomLog.severity``. Order matters for the active-injury
# check below (any open log at the top tier counts as an active injury).
_SEVERITIES = ("niggle", "ache", "pain", "injury")


def aggregate_symptom_inputs(
    athlete_id: str | UUID,
    start_date: datetime,
    end_date: datetime,
    db: Session,
) -> Dict[str, List[Tuple[date_type, float]]]:
    """Return per-day symptom-burden series across the window.

    For every day ``d`` in ``[start_date, end_date]`` we emit:

      - ``niggle_count_28d``
      - ``ache_count_28d``
      - ``pain_count_28d``
          Number of distinct symptom logs of that severity that
          were *active* at any point in the trailing 28 days
          ending at ``d``. A log is active between ``started_at``
          and ``resolved_at`` (or the present, if unresolved).

      - ``injury_active_flag``
          1.0 on days where at least one ``injury``-severity log
          was active, 0.0 otherwise.

    Days with no symptom history at all return an empty dict (we
    do not seed zero rows — that would make the correlation engine
    spuriously detect "running on rainy days has no symptoms" type
    patterns from the absence of data).
    """
    from models import BodyAreaSymptomLog

    rows = (
        db.query(
            BodyAreaSymptomLog.severity,
            BodyAreaSymptomLog.started_at,
            BodyAreaSymptomLog.resolved_at,
        )
        .filter(
            BodyAreaSymptomLog.athlete_id == athlete_id,
            # Limit to logs that could possibly be active in the analysis
            # window: started before window end, and not resolved before
            # 28 days prior to window start (the 28-day rolling lookback).
            BodyAreaSymptomLog.started_at <= end_date.date(),
        )
        .all()
    )
    if not rows:
        return {}

    window_start_date = start_date.date()
    window_end_date = end_date.date()

    cutoff_lookback = window_start_date - timedelta(days=28)
    relevant = [
        (sev, started, resolved)
        for sev, started, resolved in rows
        if (resolved is None or resolved >= cutoff_lookback)
    ]
    if not relevant:
        return {}

    out: Dict[str, List[Tuple[date_type, float]]] = {
        "niggle_count_28d": [],
        "ache_count_28d": [],
        "pain_count_28d": [],
        "injury_active_flag": [],
    }

    day = window_start_date
    while day <= window_end_date:
        lookback_start = day - timedelta(days=28)

        counts = {sev: 0 for sev in _SEVERITIES}
        injury_active = 0.0

        for sev, started, resolved in relevant:
            if sev not in counts:
                continue
            effective_resolved = resolved or day
            if started <= day and effective_resolved >= lookback_start:
                counts[sev] += 1
            if sev == "injury":
                if started <= day and (resolved is None or resolved >= day):
                    injury_active = 1.0

        out["niggle_count_28d"].append((day, float(counts["niggle"])))
        out["ache_count_28d"].append((day, float(counts["ache"])))
        out["pain_count_28d"].append((day, float(counts["pain"])))
        out["injury_active_flag"].append((day, injury_active))

        day = day + timedelta(days=1)

    cleaned: Dict[str, List[Tuple[date_type, float]]] = {}
    for key, series in out.items():
        if any(v > 0 for _, v in series):
            cleaned[key] = series
    return cleaned


# ---------------------------------------------------------------------------
# Convenience: produce both families in one call
# ---------------------------------------------------------------------------


def aggregate_strength_v1_inputs(
    athlete_id: str | UUID,
    start_date: datetime,
    end_date: datetime,
    db: Session,
) -> Dict[str, List[Tuple[date_type, float]]]:
    """Run both Phase I aggregators and return their merged output.

    Either family may be empty (no RPE-tagged sets / no symptom
    logs) — the merged dict simply omits those series, keeping
    ``aggregate_cross_training_inputs`` callers safe to ``.update``
    the result.
    """
    out: Dict[str, List[Tuple[date_type, float]]] = {}
    out.update(aggregate_per_set_rpe_inputs(athlete_id, start_date, end_date, db))
    out.update(aggregate_symptom_inputs(athlete_id, start_date, end_date, db))
    return out
