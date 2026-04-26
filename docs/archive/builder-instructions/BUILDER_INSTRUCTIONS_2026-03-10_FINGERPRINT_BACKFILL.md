# Builder Instructions — Fingerprint Backfill

**Date:** March 10, 2026  
**Priority:** P0 — run immediately after the correlation engine wiring deploys  
**Prerequisite:** `BUILDER_INSTRUCTIONS_2026-03-10_CORRELATION_ENGINE_FULL_WIRING.md` must be deployed first  
**Scope:** One new script, run on production after deploy. No frontend/API changes.  
**Safety contract:** Preserve `times_confirmed` trust semantics (no overlap inflation), avoid global Redis flushes.

---

## Why

The correlation engine was just expanded from 21 to 70 input signals. The
daily sweep runs once per day with `days=90`. At that rate, new findings
need 3+ days to reach the surfacing threshold (`times_confirmed >= 3`)
and the fingerprint stays thin for weeks.

The data to make it rich is already in the database — months of GarminDay
rows, hundreds of activities with cadence, elevation, weather, power. The
backfill runs the engine against multiple overlapping historical windows
to measure robustness quickly, then applies a **bounded bootstrap rule**:
if a finding is robust across multiple windows and currently below surfacing
threshold, it is promoted once to threshold (`times_confirmed = 3`) and no
higher. The fingerprint fills in on deploy day without runaway confirmation drift.

---

## What to Build

### New file: `scripts/backfill_correlation_fingerprint.py`

```python
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
    docker exec -w /app strideiq_api python scripts/backfill_correlation_fingerprint.py --athlete mbshaf@gmail.com

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

            # Clear correlation cache so each window runs fresh
            bust_correlation_cache(athlete_id)

            # Pass 1: Run correlation analysis across all windows (robustness only)
            pass_stats = {"total": 0, "errors": 0}
            window_hits = {}  # finding_key -> set(window_days)

            for window_days in BACKFILL_WINDOWS:
                for metric in ALL_OUTPUT_METRICS:
                    try:
                        # Bust cache for this specific key before each call
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

                # Commit after each window to persist confirmations
                db.commit()

            # Pass 2: bounded bootstrap promotion to surface threshold
            # SAFETY: do NOT stack overlapping window confirmations into times_confirmed.
            # Promote only once to threshold where robustness >= 3 and current < 3.
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

            # Pass 3: Layer enrichment (threshold, asymmetry, mediators, decay)
            logger.info("  Running layer enrichment (L1-L4)...")
            try:
                from tasks.correlation_tasks import _run_layer_pass
                n_layered = _run_layer_pass(athlete_id, db)
                db.commit()
                logger.info("  Layer enrichment: %d findings processed", n_layered)
            except Exception as e:
                logger.warning("  Layer enrichment failed: %s", e)
                db.rollback()

            # Pass 4: Investigation engine (full history)
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

            # Summary for this athlete
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

        # Final summary across all athletes
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
```

---

## How It Works

For each athlete, the script runs 3 passes:

**Pass 1 — Correlation discovery across 7 historical windows:**

| Window | What it covers |
|--------|---------------|
| 365 days | Full year |
| 270 days | 9 months |
| 180 days | 6 months |
| 120 days | 4 months |
| 90 days | 3 months (matches daily sweep) |
| 60 days | 2 months |
| 30 days | 1 month |

Each window × 9 output metrics = 63 analysis runs per athlete.

Backfill computes a robustness count per finding key (`# windows where significant`).
Then applies a bounded bootstrap rule:
- robust in >=3 windows + currently below threshold -> set `times_confirmed = 3`
- never increase above 3 from backfill bootstrap

This provides immediate surfacing without treating overlapping windows as
independent confirmations.

The cache is busted before each call so every run computes fresh.

**Pass 2 — Layer enrichment (L1-L4):**

After all correlation passes, runs threshold detection, asymmetry
analysis, mediator detection, and decay curve fitting on every finding
with `times_confirmed >= 3`. This adds the personal parameters:
sleep cliff value, asymmetry ratios, decay half-lives, mediation chains.

**Pass 3 — Investigation engine (full history):**

Runs `mine_race_inputs()` across the athlete's complete activity
history. This refreshes the `AthleteFinding` table (heat resilience,
stride economy, interval recovery, etc.). These investigations already
use activity-level data — this just ensures they're current.

---

## Run Instructions (on production, after wiring deploy)

```bash
# SSH to server
ssh root@strideiq.run

# Run for founder account first (verify it works)
docker exec -w /app strideiq_api python scripts/backfill_correlation_fingerprint.py --athlete mbshaf@gmail.com

# Check the output — should see findings accumulating across windows
# Look for "DONE" line showing active/surfaceable counts

# If good, run for all athletes
docker exec -w /app strideiq_api python scripts/backfill_correlation_fingerprint.py

# Refresh home briefing safely (targeted; DO NOT FLUSHALL)
docker exec -w /app strideiq_api python -c "
from core.database import SessionLocal
from models import Athlete
from services.home_briefing_cache import mark_briefing_dirty
from tasks.home_briefing_tasks import enqueue_briefing_refresh
db = SessionLocal()
for a in db.query(Athlete).all():
    aid = str(a.id)
    mark_briefing_dirty(aid)
    enqueue_briefing_refresh(aid, force=True, allow_circuit_probe=True)
print('Targeted briefing refresh queued for all athletes')
db.close()
"
```

---

## Expected Output

For an athlete with 6+ months of data and Garmin connected:

```
[1/1] Athlete abc-123 — starting backfill
  window=365 metric=efficiency → 12 correlations
  window=365 metric=pace_easy → 8 correlations
  ...
  window=90 metric=efficiency → 9 correlations
  ...
  Running layer enrichment (L1-L4)...
  Layer enrichment: 15 findings processed
  Running investigation engine (full history)...
  Investigations: 22 findings (created=3, updated=19, superseded=0)
  Bootstrap promotion: 8 findings promoted to confirmed=3
  DONE in 45.2s — 28 active findings, 22 surfaceable (confirmed >= 3, bounded bootstrap)
```

If the surfaceable count is under 10 for an athlete with 6+ months
of Garmin data, something is wrong with the input wiring — debug
before running for all athletes.

---

## Estimated Runtime

- ~45-90 seconds per athlete (63 analysis runs + layers + investigations)
- 10 athletes: ~10-15 minutes
- 100 athletes: ~1.5-2.5 hours

The script logs progress per athlete. Safe to interrupt and resume —
findings already persisted survive. Re-running for the same athlete is
idempotent with respect to bootstrap promotion (no confirmation inflation).

---

## What This Does NOT Do

- Does not change any code, models, or migrations
- Does not affect the daily sweep schedule (still runs at 08:00 UTC)
- Does not touch frontend
- Does not modify the investigation registry
- Safe to run multiple times (idempotent bounded bootstrap; no stacking above 3)

---

## Verification After Backfill

```bash
docker exec -w /app strideiq_api python -c "
from core.database import SessionLocal
from models import Athlete, CorrelationFinding

db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()

findings = db.query(CorrelationFinding).filter(
    CorrelationFinding.athlete_id == user.id,
    CorrelationFinding.is_active == True,
).order_by(CorrelationFinding.times_confirmed.desc()).all()

print(f'Total active findings: {len(findings)}')
print(f'Surfaceable (confirmed >= 3): {sum(1 for f in findings if f.times_confirmed >= 3)}')
print()
print('Top findings:')
for f in findings[:20]:
    parts = [f'{f.input_name} → {f.output_metric}: {f.direction} (confirmed {f.times_confirmed}x, r={f.correlation_coefficient:.2f}, n={f.sample_size})']
    if f.threshold_value is not None:
        parts.append(f'  threshold: {f.threshold_value:.1f}')
    if f.asymmetry_ratio is not None:
        parts.append(f'  asymmetry: {f.asymmetry_ratio:.1f}x')
    if f.decay_half_life_days is not None:
        parts.append(f'  decay: {f.decay_half_life_days:.1f} days')
    print('  ' + ' | '.join(parts))

db.close()
"
```

This should show findings from the NEW signals (garmin_sleep_score,
garmin_body_battery_end, avg_cadence, dew_point_f, etc.) alongside
the existing ones — with real confirmation counts and layer parameters.
