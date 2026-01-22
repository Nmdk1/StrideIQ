"""Check why hard runs = 0 (debug script)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, "/app")

from core.database import SessionLocal
from models import Activity, Athlete


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default=os.getenv("STRIDEIQ_EMAIL"), help="athlete email (default: STRIDEIQ_EMAIL)")
    parser.add_argument("--limit", type=int, default=15)
    args = parser.parse_args()

    if not args.email:
        print("ERROR: missing STRIDEIQ_EMAIL (or pass --email)")
        return 2

    db = SessionLocal()
    try:
        athlete = db.query(Athlete).filter(Athlete.email == args.email).first()
        if not athlete:
            print("ERROR: athlete not found")
            return 2

        print(f"Athlete: {athlete.display_name}")
        print(f"Max HR: {athlete.max_hr}")
        print(f"VDOT: {athlete.vdot}")

        activities = (
            db.query(Activity)
            .filter(Activity.athlete_id == athlete.id, Activity.avg_hr.isnot(None))
            .order_by(Activity.start_time.desc())
            .limit(args.limit)
            .all()
        )

        print(f"\nRecent activities with HR (last {args.limit}):")
        easy = moderate = hard = 0

        for a in activities:
            if athlete.max_hr:
                hr_pct = a.avg_hr / athlete.max_hr * 100
                if hr_pct < 75:
                    category = "EASY"
                    easy += 1
                elif hr_pct < 85:
                    category = "MODERATE"
                    moderate += 1
                else:
                    category = "HARD"
                    hard += 1
                print(f"  {a.start_time.date()}: HR {a.avg_hr} = {hr_pct:.0f}% max -> {category}")
            else:
                print(f"  {a.start_time.date()}: HR {a.avg_hr} - NO MAX HR SET")

        print(f"\nCounts: Easy={easy}, Moderate={moderate}, Hard={hard}")
        print(f"\n85% of max HR = {athlete.max_hr * 0.85 if athlete.max_hr else 'N/A'}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
