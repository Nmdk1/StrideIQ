"""
One-time backfill: populate AthleteRaceResultAnchor from authoritative race signals.

Usage:
  python scripts/_backfill_race_anchors.py
"""

from database import SessionLocal
from models import Activity
from services.fitness_bank import FitnessBankCalculator


def main() -> None:
    db = SessionLocal()
    try:
        athlete_ids = [
            row[0]
            for row in db.query(Activity.athlete_id).distinct().all()
            if row and row[0] is not None
        ]
        calc = FitnessBankCalculator(db)
        touched = 0
        for athlete_id in athlete_ids:
            calc.calculate(athlete_id)
            touched += 1
            if touched % 100 == 0:
                db.commit()
        db.commit()
        print(f"Backfill completed for {touched} athletes.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
