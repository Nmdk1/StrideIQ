"""
Fingerprint Backfill — run after correlation engine input wiring deploy.

Runs analyze_correlations() across multiple overlapping historical windows
for all athletes to compute robustness counts per finding key.

IMPORTANT: multi-window overlap must NOT directly stack into `times_confirmed`.
Instead, apply a bounded bootstrap promotion:
- if `times_confirmed >= 3`: unchanged
- if `times_confirmed < 3` and robustness_windows >= 3: set `times_confirmed = 3`
- never set above 3 from backfill bootstrap

This keeps reruns idempotent and prevents trust inflation.

After all correlation passes, runs Layer 1-4 enrichment (threshold,
asymmetry, mediators, decay) and the investigation engine.

Usage (on production server):
    docker exec -w /app strideiq_api python scripts/backfill_correlation_fingerprint.py

    # Specific athlete only:
    docker exec -w /app strideiq_api python scripts/backfill_correlation_fingerprint.py --athlete user@example.com

    # Dry run (show what would run, don't persist):
    docker exec -w /app strideiq_api python scripts/backfill_correlation_fingerprint.py --dry-run
"""

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
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

BACKFILL_WINDOWS = [365, 270, 180, 120, 90, 60, 30]


def get_all_athlete_ids(db) -> List[str]:
    """Get all athletes with at least 30 activities."""
    from models import Activity
    from sqlalchemy import func

    rows = (
        db.query(Activity.athlete_id)
        .group_by(Activity.athlete_id)
        .having(func.count(Activity.id) >= 30)
        .all()
    )
    return [str(r[0]) for r in rows]


def get_athlete_by_email(db, email: str) -> Optional[str]:
    """Look up athlete ID by email."""
    from models import Athlete
    athlete = db.query(Athlete).filter(Athlete.email == email).first()
    return str(athlete.id) if athlete else None


def bust_correlation_cache(athlete_id: str):
    """Clear all cached correlation results for this athlete."""
    try:
        from core.cache import get_redis_client
        redis = get_redis_client()
        pattern = f"correlations:{athlete_id}:*"
        keys = list(redis.scan_iter(match=pattern))
        if keys:
            redis.delete(*keys)
            logger.info("Cleared %d cache keys for %s", len(keys), athlete_id)
    except Exception as e:
        logger.warning("Cache bust failed (non-fatal): %s", e)


def _finding_key(c: dict) -> str:
    """Stable key for robustness counting across windows."""
    return f"{c.get('input_name')}|{c.get('output_metric')}|{c.get('direction')}"


def run_backfill(athlete_ids: List[str], dry_run: bool = False):
    """Run the full backfill for given athletes."""
    from core.database import SessionLocal
    from services.correlation_engine import analyze_correlations

    db = SessionLocal()

    try:
        total_athletes = len(athlete_ids)
        logger.info(
            "=== FINGERPRINT BACKFILL START === "
            "%d athletes, %d windows, %d metrics per window",
            total_athletes, len(BACKFILL_WINDOWS), len(ALL_OUTPUT_METRICS),
        )

        for idx, athlete_id in enumerate(athlete_ids, 1):
            athlete_start = time.time()
            logger.info(
                "[%d/%d] Athlete %s — starting backfill",
                idx, total_athletes, athlete_id,
            )

            if dry_run:
                logger.info("  DRY RUN — would run %d windows × %d metrics = %d passes",
                            len(BACKFILL_WINDOWS), len(ALL_OUTPUT_METRICS),
                            len(BACKFILL_WINDOWS) * len(ALL_OUTPUT_METRICS))
                continue

            bust_correlation_cache(athlete_id)

            pass_stats = {"total": 0, "errors": 0}
            window_hits = {}

            for window_days in BACKFILL_WINDOWS:
                for metric in ALL_OUTPUT_METRICS:
                    try:
                        try:
                            from core.cache import get_redis_client
                            redis = get_redis_client()
                            redis.delete(f"correlations:{athlete_id}:{window_days}:{metric}")
                        except Exception:
                            pass

                        result = analyze_correlations(
                            athlete_id,
                            days=window_days,
                            db=db,
                            output_metric=metric,
                        )

                        corrs = result.get("correlations", []) or []
                        n_corr = result.get("total_correlations_found", 0)
                        if n_corr > 0:
                            logger.info(
                                "  window=%d metric=%s → %d correlations",
                                window_days, metric, n_corr,
                            )
                            for c in corrs:
                                if not c.get("is_significant"):
                                    continue
                                key = _finding_key(c)
                                if key not in window_hits:
                                    window_hits[key] = set()
                                window_hits[key].add(window_days)
                        pass_stats["total"] += 1

                    except Exception as e:
                        pass_stats["errors"] += 1
                        logger.warning(
                            "  window=%d metric=%s FAILED: %s",
                            window_days, metric, e,
                        )

                db.commit()

            # Bounded bootstrap promotion
            try:
                from models import CorrelationFinding
                promoted = 0
                for f in db.query(CorrelationFinding).filter(
                    CorrelationFinding.athlete_id == athlete_id,
                    CorrelationFinding.is_active == True,  # noqa: E712
                ).all():
                    key = f"{f.input_name}|{f.output_metric}|{f.direction}"
                    robust_count = len(window_hits.get(key, set()))
                    if (f.times_confirmed or 0) < 3 and robust_count >= 3:
                        f.times_confirmed = 3
                        promoted += 1
                db.commit()
                logger.info("  Bootstrap promotion: %d findings promoted to confirmed=3", promoted)
            except Exception as e:
                logger.warning("  Bootstrap promotion failed: %s", e)
                db.rollback()

            # Layer enrichment (L1-L4)
            logger.info("  Running layer enrichment (L1-L4)...")
            try:
                from tasks.correlation_tasks import _run_layer_pass
                n_layered = _run_layer_pass(athlete_id, db)
                db.commit()
                logger.info("  Layer enrichment: %d findings processed", n_layered)
            except Exception as e:
                logger.warning("  Layer enrichment failed: %s", e)
                db.rollback()

            # Investigation engine (full history)
            logger.info("  Running investigation engine (full history)...")
            try:
                from services.race_input_analysis import mine_race_inputs
                from services.finding_persistence import store_all_findings
                from uuid import UUID

                findings, gaps = mine_race_inputs(UUID(athlete_id), db)
                if findings:
                    stats = store_all_findings(UUID(athlete_id), findings, db)
                    db.commit()
                    logger.info(
                        "  Investigations: %d findings (created=%d, updated=%d, superseded=%d)",
                        len(findings), stats.get("created", 0),
                        stats.get("updated", 0), stats.get("superseded", 0),
                    )
                else:
                    logger.info("  Investigations: no findings produced")
            except Exception as e:
                logger.warning("  Investigation engine failed: %s", e)
                db.rollback()

            elapsed = time.time() - athlete_start
            try:
                from models import CorrelationFinding
                active_count = db.query(CorrelationFinding).filter(
                    CorrelationFinding.athlete_id == athlete_id,
                    CorrelationFinding.is_active == True,  # noqa: E712
                ).count()
                surfaceable_count = db.query(CorrelationFinding).filter(
                    CorrelationFinding.athlete_id == athlete_id,
                    CorrelationFinding.is_active == True,  # noqa: E712
                    CorrelationFinding.times_confirmed >= 3,
                ).count()
                logger.info(
                    "  DONE in %.1fs — %d active findings, %d surfaceable (confirmed >= 3, bounded bootstrap)",
                    elapsed, active_count, surfaceable_count,
                )
            except Exception:
                logger.info("  DONE in %.1fs", elapsed)

        logger.info("=== FINGERPRINT BACKFILL COMPLETE ===")

        try:
            from models import CorrelationFinding
            total_active = db.query(CorrelationFinding).filter(
                CorrelationFinding.is_active == True,  # noqa: E712
            ).count()
            total_surfaceable = db.query(CorrelationFinding).filter(
                CorrelationFinding.is_active == True,  # noqa: E712
                CorrelationFinding.times_confirmed >= 3,
            ).count()
            logger.info(
                "FINAL: %d total active findings, %d surfaceable across all athletes",
                total_active, total_surfaceable,
            )
        except Exception:
            pass

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fingerprint backfill")
    parser.add_argument(
        "--athlete", type=str, default=None,
        help="Email of specific athlete to backfill (default: all with 30+ activities)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would run without persisting",
    )
    args = parser.parse_args()

    from core.database import SessionLocal
    db = SessionLocal()

    if args.athlete:
        aid = get_athlete_by_email(db, args.athlete)
        if not aid:
            logger.error("Athlete not found: %s", args.athlete)
            sys.exit(1)
        athlete_ids = [aid]
        logger.info("Backfill for single athlete: %s → %s", args.athlete, aid)
    else:
        athlete_ids = get_all_athlete_ids(db)
        logger.info("Backfill for all athletes with 30+ activities: %d found", len(athlete_ids))

    db.close()

    run_backfill(athlete_ids, dry_run=args.dry_run)
