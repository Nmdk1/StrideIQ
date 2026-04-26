"""Block detection backfill / refresh task.

Detects training blocks for an athlete from their activity history and
persists them to ``training_block``. Idempotent — replays delete-and-
recreate the athlete's rows so the detector stays the source of truth.

Triggered manually after deploy (`backfill_training_blocks`) and nightly
by Celery beat for incremental refresh.
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="tasks.backfill_training_blocks", bind=True, max_retries=0)
def backfill_training_blocks(
    self,
    athlete_id: Optional[str] = None,
    limit_athletes: Optional[int] = None,
):
    """Backfill (or refresh) training_block rows for one or all athletes.

    Returns: ``{"status": "ok", "athletes": int, "blocks": int, "errors": int}``
    """
    from core.database import SessionLocal
    from models import Athlete
    from services.blocks import (
        detect_blocks_for_athlete,
        persist_detected_blocks,
    )

    db = SessionLocal()
    athletes = 0
    blocks_total = 0
    errors = 0
    try:
        q = db.query(Athlete.id)
        if athlete_id:
            q = q.filter(Athlete.id == UUID(str(athlete_id)))
        if limit_athletes:
            q = q.limit(int(limit_athletes))
        athlete_ids = [row[0] for row in q.all()]

        for aid in athlete_ids:
            try:
                detected = detect_blocks_for_athlete(db, aid)
                inserted = persist_detected_blocks(db, aid, detected)
                athletes += 1
                blocks_total += inserted
            except Exception as exc:  # pragma: no cover — logged
                errors += 1
                logger.warning(
                    "training_block_backfill_failed athlete_id=%s err=%s",
                    aid,
                    exc,
                )
                db.rollback()

        return {
            "status": "ok",
            "athletes": athletes,
            "blocks": blocks_total,
            "errors": errors,
        }
    finally:
        db.close()
