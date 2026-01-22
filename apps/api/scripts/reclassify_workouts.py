"""Reclassify activities using the workout classifier (ops script).

Safety:
- Requires an athlete selection (email via env/arg).
- DRY_RUN by default; use --commit to persist changes.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, "/app")

from core.database import SessionLocal
from models import Activity, Athlete
from services.workout_classifier import WorkoutClassifierService


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default=os.getenv("STRIDEIQ_EMAIL"), help="athlete email (default: STRIDEIQ_EMAIL)")
    parser.add_argument("--days", type=int, default=90, help="how many days back to scan (default: 90)")
    parser.add_argument("--commit", action="store_true", help="Persist updates (default: dry-run)")
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

        classifier = WorkoutClassifierService(db)

        cutoff = datetime.utcnow() - timedelta(days=args.days)
        activities = (
            db.query(Activity)
            .filter(Activity.athlete_id == athlete.id, Activity.start_time >= cutoff)
            .order_by(Activity.start_time.desc())
            .all()
        )

        mode = "COMMIT" if args.commit else "DRY_RUN"
        print(f"MODE={mode} athlete_id={athlete.id} days={args.days} activities={len(activities)}\n")

        changed = 0
        for a in activities:
            old_type = a.workout_type
            old_intensity = a.intensity_score

            classification = classifier.classify_activity(a)
            new_type = classification.workout_type.value
            new_intensity = classification.intensity_score

            if old_type != new_type or (old_intensity or 0) != new_intensity:
                print(
                    f"{a.start_time.date()} | {(a.name or 'Run')[:35]:35} | "
                    f"{old_type or '-':20} -> {new_type:20} | IS: {old_intensity or '-'} -> {new_intensity:.0f}"
                )
                if args.commit:
                    a.workout_type = new_type
                    a.intensity_score = new_intensity
                changed += 1

        if args.commit:
            db.commit()
            print(f"\n--- DONE ---\nUpdated {changed} activities")
        else:
            db.rollback()
            print(f"\n--- DONE (dry-run) ---\nWould update {changed} activities")

        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
