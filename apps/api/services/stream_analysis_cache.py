"""
RSI — Stream Analysis Cache Service

Spec decision (locked 2026-02-14):
    "Cache full StreamAnalysisResult in DB. Compute once, serve many.
     Recompute on: new stream payload, analysis_version bump, manual reprocess."

Both /v1/home and /v1/activities/{id}/stream-analysis use this service
to avoid recomputing analyze_stream() on every read.

Usage:
    result_dict = get_or_compute_analysis(activity_id, stream_row, athlete_ctx, db)
    # result_dict is the full asdict(StreamAnalysisResult)
"""
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models import CachedStreamAnalysis, ActivityStream, PlannedWorkout
from services.run_stream_analysis import (
    AthleteContext,
    StreamAnalysisResult,
    analyze_stream,
)

logger = logging.getLogger(__name__)

# Bump this when analysis logic changes to invalidate all caches.
CURRENT_ANALYSIS_VERSION = 1


def get_or_compute_analysis(
    activity_id: UUID,
    stream_row: ActivityStream,
    athlete_ctx: AthleteContext,
    db: Session,
    planned_workout_dict: Optional[Dict] = None,
    force_recompute: bool = False,
) -> Dict[str, Any]:
    """Get cached analysis or compute + cache it.

    Returns the full asdict(StreamAnalysisResult).

    Args:
        activity_id: The activity UUID.
        stream_row: The ActivityStream row (must have stream_data).
        athlete_ctx: Athlete physiological context for tiering.
        db: SQLAlchemy session.
        planned_workout_dict: Optional plan data for plan comparison.
        force_recompute: If True, ignore cache and recompute.
    """
    if not force_recompute:
        cached = _get_cached(activity_id, db)
        if cached is not None:
            return cached

    # Cache miss or forced recompute — run analysis
    result = analyze_stream(
        stream_data=stream_row.stream_data,
        channels_available=stream_row.channels_available or list(stream_row.stream_data.keys()),
        planned_workout=planned_workout_dict,
        athlete_context=athlete_ctx,
    )

    result_dict = asdict(result)

    # Store in cache
    _store_cached(activity_id, result_dict, db)

    return result_dict


def invalidate_cache(activity_id: UUID, db: Session) -> None:
    """Invalidate cached analysis for an activity.

    Called when:
    - New stream payload arrives (re-ingestion)
    - Manual reprocess requested
    """
    db.query(CachedStreamAnalysis).filter(
        CachedStreamAnalysis.activity_id == activity_id,
    ).delete()
    db.commit()


def _get_cached(activity_id: UUID, db: Session) -> Optional[Dict[str, Any]]:
    """Fetch cached result if it exists and matches current version."""
    row = (
        db.query(CachedStreamAnalysis)
        .filter(
            CachedStreamAnalysis.activity_id == activity_id,
            CachedStreamAnalysis.analysis_version == CURRENT_ANALYSIS_VERSION,
        )
        .first()
    )
    if row is not None:
        return row.result_json
    return None


def _store_cached(
    activity_id: UUID,
    result_dict: Dict[str, Any],
    db: Session,
) -> None:
    """Store or update cached analysis result."""
    try:
        existing = (
            db.query(CachedStreamAnalysis)
            .filter(CachedStreamAnalysis.activity_id == activity_id)
            .first()
        )
        if existing:
            existing.result_json = result_dict
            existing.analysis_version = CURRENT_ANALYSIS_VERSION
            existing.computed_at = datetime.now(timezone.utc)
        else:
            row = CachedStreamAnalysis(
                activity_id=activity_id,
                result_json=result_dict,
                analysis_version=CURRENT_ANALYSIS_VERSION,
            )
            db.add(row)
        db.commit()
    except Exception as e:
        logger.warning(f"Failed to cache stream analysis for {activity_id}: {e}")
        db.rollback()
