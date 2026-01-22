"""
Backfill Strava best-efforts for PB correctness (fast path).

Why this exists:
- PersonalBest should be derived from Strava "best_efforts" segments (BestEffort table),
  not from whole-activity distances (which are often slightly long and slower).
- The normal `/v1/athletes/{id}/sync-best-efforts` endpoint can take a long time and
  may hit Strava rate limits; for recovery/debug, it's useful to backfill from the
  most-likely activities first (fastest runs).

Usage (inside api container):
  python scripts/backfill_best_efforts_fast.py 4368ec7f-c30d-45ff-a6ee-58db7716be24 --limit 25
"""

from __future__ import annotations

import random
import os
import sys
import time
from uuid import UUID


# Ensure /app is on sys.path when run as a script inside the container.
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("athlete_id", type=str, help="UUID of athlete")
    parser.add_argument("--limit", type=int, default=15, help="number of likely PB-source activities to inspect")
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Persist extracted BestEffort rows + regenerate PBs. Default is dry-run (no DB writes).",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.25,
        help="Base sleep between Strava requests (seconds).",
    )
    parser.add_argument(
        "--jitter",
        type=float,
        default=0.25,
        help="Random jitter added to sleep between Strava requests (seconds).",
    )
    parser.add_argument(
        "--max-errors",
        type=int,
        default=10,
        help="Stop after this many request failures.",
    )
    args = parser.parse_args()

    athlete_id = UUID(args.athlete_id)

    from core.database import SessionLocal
    from models import Athlete, Activity
    from services.strava_service import get_activity_details
    from services.best_effort_service import extract_best_efforts_from_activity, regenerate_personal_bests

    db = SessionLocal()
    try:
        athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            print("ERROR: athlete not found")
            return 2
        if not athlete.strava_access_token:
            print("ERROR: athlete has no Strava access token")
            return 2

        # Prioritize likely sources of best efforts:
        # - Fastest runs by average_speed (m/s)
        # - Only Strava-backed activities with external IDs
        acts = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete.id,
                Activity.provider == "strava",
                Activity.external_activity_id.isnot(None),
                Activity.average_speed.isnot(None),
            )
            .order_by(Activity.average_speed.desc(), Activity.start_time.desc())
            .limit(args.limit)
            .all()
        )

        checked = 0
        stored_total = 0
        errors = 0

        mode = "COMMIT" if args.commit else "DRY_RUN"
        print(f"MODE={mode} athlete_id={athlete.id} limit={args.limit}")

        for a in acts:
            checked += 1
            try:
                details = get_activity_details(athlete, int(a.external_activity_id))
            except Exception as e:
                print(f"DETAILS_FAIL external_activity_id={a.external_activity_id}: {e}")
                # Make sure a failed request doesn't poison the session
                try:
                    db.rollback()
                except Exception:
                    pass
                errors += 1
                if errors >= args.max_errors:
                    print(f"STOP: reached max errors ({args.max_errors})")
                    break
                continue

            if args.commit:
                stored = extract_best_efforts_from_activity(details or {}, a, athlete, db)
                stored_total += stored
                # Commit per activity so progress persists even if we get rate-limited later.
                db.commit()
                print(f"ACT {a.external_activity_id} stored_best_efforts={stored}")
            else:
                # Dry-run: exercise extraction in a nested transaction and roll it back.
                try:
                    db.begin_nested()
                    stored = extract_best_efforts_from_activity(details or {}, a, athlete, db)
                    stored_total += stored
                    db.rollback()
                    print(f"ACT {a.external_activity_id} would_store_best_efforts={stored}")
                except Exception as e:
                    print(f"EXTRACT_FAIL external_activity_id={a.external_activity_id}: {e}")
                    try:
                        db.rollback()
                    except Exception:
                        pass

            # Light backoff to reduce Strava rate pressure.
            time.sleep(max(0.0, float(args.sleep)) + random.random() * max(0.0, float(args.jitter)))

        if args.commit:
            # Finally, regenerate PersonalBest from BestEffort.
            pb_res = regenerate_personal_bests(athlete, db)
            print(
                "DONE",
                {
                    "mode": mode,
                    "activities_checked": checked,
                    "efforts_stored": stored_total,
                    "pbs_created": pb_res.get("created"),
                    "categories": pb_res.get("categories"),
                },
            )
        else:
            print(
                "DONE",
                {
                    "mode": mode,
                    "activities_checked": checked,
                    "efforts_would_store": stored_total,
                    "pbs_regenerated": False,
                },
            )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

