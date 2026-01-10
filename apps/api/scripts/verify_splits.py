"""
Verify that ActivitySplit rows are being written to the database.

Run from project root (PowerShell):
    docker compose exec api python scripts/verify_splits.py
"""

from __future__ import annotations

import os
import sys
from sqlalchemy import text

# --- Make imports work no matter how this file is executed ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database import SessionLocal  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        # 1) Count rows
        total = db.execute(text("SELECT COUNT(*) FROM activity_split;")).scalar_one()
        print(f"ActivitySplit total rows: {total}")

        if total == 0:
            print("WARNING: activity_split is empty. Splits are NOT being written.")
            return

        # 2) Print first 10 rows (using the real schema)
        rows = db.execute(
            text(
                """
                SELECT
                    activity_id,
                    split_number,
                    distance,
                    elapsed_time,
                    moving_time,
                    average_heartrate,
                    max_heartrate,
                    average_cadence
                FROM activity_split
                ORDER BY activity_id, split_number
                LIMIT 10;
                """
            )
        ).fetchall()

        print("\nFirst 10 ActivitySplit rows:")
        for r in rows:
            print(
                "activity_id={activity_id}  split_number={split_number}  "
                "distance={distance}  elapsed_time={elapsed_time}  moving_time={moving_time}  "
                "avg_hr={avg_hr}  max_hr={max_hr}  avg_cadence={avg_cadence}".format(
                    activity_id=r[0],
                    split_number=r[1],
                    distance=r[2],
                    elapsed_time=r[3],
                    moving_time=r[4],
                    avg_hr=r[5],
                    max_hr=r[6],
                    avg_cadence=r[7],
                )
            )

    finally:
        db.close()


if __name__ == "__main__":
    main()
