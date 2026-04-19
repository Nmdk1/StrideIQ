"""Strength v1 — Garmin reconciliation Celery beat task.

Daily sweep that flags Garmin-ingested strength sessions which look
incomplete (zero or sparse ``StrengthExerciseSet`` rows) so the home
card can ask the athlete: "Garmin saw a strength session on Tuesday —
want to fill in details?"

Read-only sweep in v1. We don't modify activities, we don't send push
notifications, and we don't auto-classify the gap. The task simply
logs counts so we have observability; the actual nudges are computed
on-demand by ``GET /v1/strength/nudges`` so the source of truth stays
the live database state, not a denormalized card table.

Scope contract: only flags activities where ALL of:
  - sport == 'strength'
  - source != 'manual' (came from Garmin / FIT)
  - start_time within last 7 days
  - manually_augmented == False  (no athlete edit yet)
  - active set count < 3        (too sparse to be a real session)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from celery import shared_task

from core.database import SessionLocal
from core.feature_flags import is_feature_enabled
from models import Activity, Athlete, StrengthExerciseSet

logger = logging.getLogger(__name__)

STRENGTH_V1_FLAG = "strength.v1"
SPARSE_SET_THRESHOLD = 3
LOOKBACK_DAYS = 7


@shared_task(name="tasks.reconcile_garmin_strength_sessions")
def reconcile_garmin_strength_sessions() -> Dict[str, Any]:
    """Daily beat: count Garmin-ingested strength sessions missing detail.

    Returns a small dict ``{athletes_scanned, nudge_candidates}`` for
    Celery monitoring. The actual home-card surface reads from
    ``GET /v1/strength/nudges`` per request.
    """
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
        athletes_scanned = 0
        nudge_candidates = 0

        athletes = db.query(Athlete).all()
        for athlete in athletes:
            if not is_feature_enabled(STRENGTH_V1_FLAG, str(athlete.id), db):
                continue
            athletes_scanned += 1
            count = _count_sparse_garmin_strength(db, athlete.id, cutoff)
            nudge_candidates += count

        result = {
            "status": "ok",
            "athletes_scanned": athletes_scanned,
            "nudge_candidates": nudge_candidates,
            "lookback_days": LOOKBACK_DAYS,
        }
        logger.info(
            "reconcile_garmin_strength_sessions: scanned=%d candidates=%d",
            athletes_scanned,
            nudge_candidates,
        )
        return result
    finally:
        db.close()


def _count_sparse_garmin_strength(db, athlete_id, cutoff) -> int:
    """Pure helper, easy to unit test against an in-memory fixture."""
    from sqlalchemy import func

    # Subquery: number of *active* (non-superseded, set_type='active')
    # strength sets per activity for this athlete in the window.
    set_count_sq = (
        db.query(
            StrengthExerciseSet.activity_id.label("aid"),
            func.count(StrengthExerciseSet.id).label("n"),
        )
        .filter(
            StrengthExerciseSet.athlete_id == athlete_id,
            StrengthExerciseSet.superseded_at.is_(None),
            StrengthExerciseSet.set_type == "active",
        )
        .group_by(StrengthExerciseSet.activity_id)
        .subquery()
    )

    rows = (
        db.query(Activity, set_count_sq.c.n)
        .outerjoin(set_count_sq, set_count_sq.c.aid == Activity.id)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.sport == "strength",
            Activity.source != "manual",
            Activity.start_time >= cutoff,
        )
        .all()
    )

    candidates = 0
    for activity, n in rows:
        if _is_manually_augmented_via_any_set(db, activity.id):
            continue
        n_int = int(n or 0)
        if n_int < SPARSE_SET_THRESHOLD:
            candidates += 1
    return candidates


def _is_manually_augmented_via_any_set(db, activity_id) -> bool:
    """An activity is considered touched if *any* of its sets has
    ``manually_augmented = True`` (active row only)."""
    return (
        db.query(StrengthExerciseSet.id)
        .filter(
            StrengthExerciseSet.activity_id == activity_id,
            StrengthExerciseSet.superseded_at.is_(None),
            StrengthExerciseSet.manually_augmented.is_(True),
        )
        .first()
        is not None
    )
