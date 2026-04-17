"""Route fingerprint backfill task.

For every activity that has a stored ``ActivityStream`` but no
``route_id``, compute the geohash fingerprint and attach it to a route
(creating new routes as needed). Safe to re-run — idempotent.

Operates per-athlete to keep transaction scope small. Triggered manually
or by a one-off boot job after deploying the migration.
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="tasks.backfill_route_fingerprints", bind=True, max_retries=0)
def backfill_route_fingerprints(self, athlete_id: Optional[str] = None, batch_size: int = 200):
    """Backfill route fingerprints for activities lacking one.

    Args:
        athlete_id: If provided, only backfill this athlete. Otherwise
            walk all athletes with at least one stream-bearing activity.
        batch_size: Activities per athlete batch (cap to avoid long txns).

    Returns:
        ``{"status": "ok", "processed": int, "matched": int, "created": int}``
    """
    from core.database import SessionLocal
    from models import Activity, ActivityStream, Athlete, AthleteRoute
    from services.routes.route_fingerprint import compute_for_activity

    db = SessionLocal()
    processed = 0
    matched = 0
    created = 0
    errors = 0
    try:
        athlete_q = db.query(Athlete.id)
        if athlete_id:
            athlete_q = athlete_q.filter(Athlete.id == UUID(str(athlete_id)))
        athlete_ids = [row[0] for row in athlete_q.all()]

        for aid in athlete_ids:
            existing_routes_count = (
                db.query(AthleteRoute).filter(AthleteRoute.athlete_id == aid).count()
            )
            ids_q = (
                db.query(Activity.id)
                .join(ActivityStream, ActivityStream.activity_id == Activity.id)
                .filter(
                    Activity.athlete_id == aid,
                    Activity.route_id.is_(None),
                    Activity.route_geohash_set.is_(None),
                    Activity.sport == "run",
                )
                .order_by(Activity.start_time.asc())
                .limit(batch_size)
            )
            ids = [r[0] for r in ids_q.all()]
            for act_id in ids:
                try:
                    route = compute_for_activity(db, act_id)
                    processed += 1
                    if route is not None:
                        matched += 1
                except Exception as exc:  # pragma: no cover — logged
                    errors += 1
                    logger.warning(
                        "route_backfill_failed activity_id=%s err=%s",
                        act_id,
                        exc,
                    )
                    db.rollback()

            new_routes_count = (
                db.query(AthleteRoute).filter(AthleteRoute.athlete_id == aid).count()
            )
            created += max(0, new_routes_count - existing_routes_count)

        logger.info(
            "route_backfill_complete processed=%d matched=%d created=%d errors=%d",
            processed,
            matched,
            created,
            errors,
        )
        return {
            "status": "ok",
            "processed": processed,
            "matched": matched,
            "created": created,
            "errors": errors,
        }
    finally:
        db.close()
