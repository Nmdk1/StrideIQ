"""
Normalize/repair PlannedWorkout text fields (ops utility).

This exists to repair legacy bad text in planned workouts without writing one-off,
hardcoded scripts.

Examples (inside api container):
  python scripts/normalize_planned_workout_text.py --planned-workout-id <uuid>
  python scripts/normalize_planned_workout_text.py --athlete-id <uuid> --date 2026-01-22 --commit

Default mode is DRY_RUN (no DB writes). Use --commit to persist.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from uuid import UUID


_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--planned-workout-id", type=str, default=None, help="UUID of PlannedWorkout")
    parser.add_argument("--athlete-id", type=str, default=None, help="UUID of Athlete (with an active plan)")
    parser.add_argument("--date", type=str, default=None, help="Workout scheduled date (YYYY-MM-DD)")
    parser.add_argument("--clear-description", action="store_true", help="Clear description field")
    parser.add_argument("--clear-coach-notes", action="store_true", help="Clear coach_notes field")
    parser.add_argument("--commit", action="store_true", help="Persist changes (default: dry-run)")
    args = parser.parse_args()

    planned_workout_id = UUID(args.planned_workout_id) if args.planned_workout_id else None
    athlete_id = UUID(args.athlete_id) if args.athlete_id else None
    target_date = date.fromisoformat(args.date) if args.date else None

    if planned_workout_id is None and (athlete_id is None or target_date is None):
        print("ERROR: provide --planned-workout-id OR (--athlete-id and --date)")
        return 2

    from core.database import SessionLocal
    from models import PlannedWorkout, TrainingPlan
    from services.planned_workout_text import normalize_workout_text_fields

    db = SessionLocal()
    try:
        w: PlannedWorkout | None = None

        if planned_workout_id is not None:
            w = db.query(PlannedWorkout).filter(PlannedWorkout.id == planned_workout_id).first()
        else:
            plan = (
                db.query(TrainingPlan)
                .filter(TrainingPlan.athlete_id == athlete_id, TrainingPlan.status == "active")
                .first()
            )
            if not plan:
                print("ERROR: no active plan found for athlete")
                return 2
            w = (
                db.query(PlannedWorkout)
                .filter(PlannedWorkout.plan_id == plan.id, PlannedWorkout.scheduled_date == target_date)
                .first()
            )

        if not w:
            print("ERROR: planned workout not found")
            return 2

        before = {
            "id": str(w.id),
            "scheduled_date": w.scheduled_date.isoformat() if w.scheduled_date else None,
            "title": w.title,
            "description": w.description,
            "coach_notes": w.coach_notes,
        }

        normalize_workout_text_fields(w)
        if args.clear_description:
            w.description = None
        if args.clear_coach_notes:
            w.coach_notes = None

        after = {
            "id": str(w.id),
            "scheduled_date": w.scheduled_date.isoformat() if w.scheduled_date else None,
            "title": w.title,
            "description": w.description,
            "coach_notes": w.coach_notes,
        }

        mode = "COMMIT" if args.commit else "DRY_RUN"
        print("MODE", mode)
        print("BEFORE", before)
        print("AFTER ", after)

        if args.commit:
            db.commit()
            print("OK: committed")
        else:
            db.rollback()
            print("OK: dry-run (rolled back)")

        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

