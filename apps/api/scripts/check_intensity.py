"""Check intensity scoring and workout types (debug script)."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, "/app")

from core.database import SessionLocal
from models import Activity, Athlete


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default=os.getenv("STRIDEIQ_EMAIL"), help="athlete email (default: STRIDEIQ_EMAIL)")
    parser.add_argument("--days", type=int, default=60)
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

        cutoff = datetime.utcnow() - timedelta(days=args.days)
        activities = (
            db.query(Activity)
            .filter(Activity.athlete_id == athlete.id, Activity.start_time >= cutoff)
            .order_by(Activity.start_time.desc())
            .all()
        )

        print(f"Activities in last {args.days} days: {len(activities)}\n")

        hard_by_type = []
        hard_by_intensity = []

        for a in activities:
            name = (a.name or "Run")[:40]
            wt = a.workout_type or "-"
            intensity = a.intensity_score

            hard_types = ["race", "interval", "tempo", "threshold", "vo2max", "speed", "fartlek"]
            is_hard_type = any(ht in wt.lower() for ht in hard_types) if wt else False
            is_hard_intensity = bool(intensity and intensity >= 70)

            marker = ""
            if is_hard_type:
                hard_by_type.append(a)
                marker += " [TYPE:HARD]"
            if is_hard_intensity:
                hard_by_intensity.append(a)
                marker += " [INTENSITY:HARD]"

            print(f"{a.start_time.date()} | {wt:20} | IS:{intensity or '-':>3} | HR:{a.avg_hr or '-':>3} | {name}{marker}")

        print("\n--- SUMMARY ---")
        print(f"Hard by workout type: {len(hard_by_type)}")
        print(f"Hard by intensity score (>=70): {len(hard_by_intensity)}")

        types = {a.workout_type for a in activities if a.workout_type}
        print(f"\nUnique workout types: {types}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
