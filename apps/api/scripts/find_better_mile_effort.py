"""
Find and store a better Strava "1 mile" best effort.

Problem:
- After restoring BestEffort/PersonalBest, we may still be missing the true all-time
  mile best effort if not all activities have had their Strava `best_efforts` extracted yet.
  Backfilling every activity can be slow due to Strava rate limits.

Strategy:
- Look at activities that *don't yet have any BestEffort rows*.
- Fetch Strava activity details for them (one by one) and inspect the returned `best_efforts`.
- Stop as soon as we find a mile effort that beats the current stored best.

Usage (inside api container):
  python scripts/find_better_mile_effort.py 4368ec7f-c30d-45ff-a6ee-58db7716be24 --scan 120
"""

from __future__ import annotations

import random
import os
import sys
import time
from uuid import UUID

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("athlete_id", type=str, help="UUID of athlete")
    parser.add_argument("--scan", type=int, default=120, help="max unprocessed activities to scan")
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
    from sqlalchemy import select
    from models import Athlete, Activity, BestEffort
    from services.strava_service import get_activity_details
    from services.best_effort_service import normalize_effort_name, extract_best_efforts_from_activity, regenerate_personal_bests

    db = SessionLocal()
    try:
        athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete or not athlete.strava_access_token:
            print("ERROR: athlete missing or not connected to Strava")
            return 2

        current_best = (
            db.query(BestEffort)
            .filter(BestEffort.athlete_id == athlete.id, BestEffort.distance_category == "mile")
            .order_by(BestEffort.elapsed_time.asc())
            .first()
        )
        current_best_s = current_best.elapsed_time if current_best else None
        print("CURRENT_BEST_MILE_S", current_best_s)
        mode = "COMMIT" if args.commit else "DRY_RUN"
        print(f"MODE={mode} athlete_id={athlete.id} scan={args.scan}")

        processed_ids = select(BestEffort.activity_id).where(BestEffort.athlete_id == athlete.id).distinct()

        candidates = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete.id,
                Activity.provider == "strava",
                Activity.external_activity_id.isnot(None),
                ~Activity.id.in_(processed_ids),
            )
            .order_by(Activity.start_time.desc())
            .limit(args.scan)
            .all()
        )

        print("CANDIDATES", len(candidates))
        errors = 0

        for idx, a in enumerate(candidates):
            ext = a.external_activity_id
            try:
                details = get_activity_details(athlete, int(ext))
            except Exception as e:
                print("DETAILS_FAIL", ext, str(e)[:200])
                try:
                    db.rollback()
                except Exception:
                    pass
                errors += 1
                if errors >= args.max_errors:
                    print(f"STOP: reached max errors ({args.max_errors})")
                    break
                continue

            best_efforts = (details or {}).get("best_efforts", []) or []
            mile_effort = None
            for eff in best_efforts:
                name = eff.get("name") or ""
                cat = normalize_effort_name(name)
                if cat == "mile":
                    mile_effort = eff
                    break

            if not mile_effort:
                time.sleep(max(0.0, float(args.sleep)) + random.random() * max(0.0, float(args.jitter)))
                continue

            mile_s = int(mile_effort.get("elapsed_time") or 0)
            if mile_s <= 0:
                time.sleep(max(0.0, float(args.sleep)) + random.random() * max(0.0, float(args.jitter)))
                continue

            if current_best_s is None or mile_s < current_best_s:
                if args.commit:
                    stored = extract_best_efforts_from_activity(details or {}, a, athlete, db)
                    db.commit()
                    pb = regenerate_personal_bests(athlete, db)
                    print(
                        "FOUND_BETTER_MILE",
                        {
                            "mode": mode,
                            "activity_external_id": ext,
                            "activity_id": str(a.id),
                            "activity_date": a.start_time.date().isoformat(),
                            "new_mile_s": mile_s,
                            "stored_efforts": stored,
                            "pbs_created": pb.get("created"),
                        },
                    )
                    return 0
                else:
                    print(
                        "FOUND_BETTER_MILE",
                        {
                            "mode": mode,
                            "activity_external_id": ext,
                            "activity_id": str(a.id),
                            "activity_date": a.start_time.date().isoformat(),
                            "new_mile_s": mile_s,
                            "action": "dry-run (no DB writes)",
                        },
                    )
                    return 0

            if idx % 25 == 0 and idx > 0:
                print("SCANNED", idx, "no improvement yet; current_best", current_best_s)
            time.sleep(max(0.0, float(args.sleep)) + random.random() * max(0.0, float(args.jitter)))

        print("NO_BETTER_MILE_FOUND_IN_SCAN")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

