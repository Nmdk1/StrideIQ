"""Debug PB calculations for specific distances (debug script)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, "/app")

from core.database import SessionLocal
from models import Activity, Athlete, PersonalBest
from services.personal_best import DISTANCE_CATEGORIES, get_distance_category


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default=os.getenv("STRIDEIQ_EMAIL"), help="athlete email (default: STRIDEIQ_EMAIL)")
    args = parser.parse_args()

    if not args.email:
        print("ERROR: missing STRIDEIQ_EMAIL (or pass --email)")
        return 2

    db = SessionLocal()
    try:
        athlete = db.query(Athlete).filter(Athlete.email == args.email).first()
        if not athlete:
            print("ERROR: no athlete found")
            return 2

        print(f"Athlete: {athlete.display_name}")
        print("\n=== DISTANCE CATEGORY RANGES ===")
        for cat, (min_m, max_m) in sorted(DISTANCE_CATEGORIES.items(), key=lambda x: x[1][0]):
            print(f"  {cat}: {min_m}m - {max_m}m ({min_m/1609.34:.2f}mi - {max_m/1609.34:.2f}mi)")

        print("\n=== CURRENT PBs ===")
        pbs = db.query(PersonalBest).filter(PersonalBest.athlete_id == athlete.id).all()
        for pb in pbs:
            print(
                f"  {pb.distance_category}: {pb.time_seconds}s ({pb.time_seconds/60:.1f}min), "
                f"distance={pb.distance_meters}m, date={pb.achieved_at}"
            )

        print("\n=== ACTIVITIES MATCHING 'mile' (1570m-1660m) ===")
        mile_activities = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete.id,
                Activity.distance_m >= 1570,
                Activity.distance_m <= 1660,
                Activity.duration_s > 0,
            )
            .order_by(Activity.duration_s.asc())
            .limit(10)
            .all()
        )
        for a in mile_activities:
            print(f"  {a.name}: {a.distance_m:.0f}m, {a.duration_s}s ({a.duration_s/60:.1f}min), date={a.start_time}")

        print("\n=== ACTIVITIES MATCHING '25k' (24750m-25250m) ===")
        activities_25k = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete.id,
                Activity.distance_m >= 24750,
                Activity.distance_m <= 25250,
                Activity.duration_s > 0,
            )
            .order_by(Activity.duration_s.asc())
            .limit(10)
            .all()
        )
        for a in activities_25k:
            print(f"  {a.name}: {a.distance_m:.0f}m, {a.duration_s}s ({a.duration_s/60:.1f}min), date={a.start_time}")

        print("\n=== FASTEST MILE ACTIVITIES (any distance 1500-1700m) ===")
        near_mile = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete.id,
                Activity.distance_m >= 1500,
                Activity.distance_m <= 1700,
                Activity.duration_s > 0,
            )
            .order_by(Activity.duration_s.asc())
            .limit(10)
            .all()
        )
        for a in near_mile:
            cat = get_distance_category(a.distance_m)
            print(f"  {a.name}: {a.distance_m:.0f}m → category={cat}, {a.duration_s}s ({a.duration_s/60:.1f}min)")

        print("\n=== ACTIVITIES 24-26km range ===")
        near_25k = (
            db.query(Activity)
            .filter(
                Activity.athlete_id == athlete.id,
                Activity.distance_m >= 24000,
                Activity.distance_m <= 26000,
                Activity.duration_s > 0,
            )
            .order_by(Activity.distance_m.asc())
            .limit(15)
            .all()
        )
        for a in near_25k:
            cat = get_distance_category(a.distance_m)
            print(f"  {a.name}: {a.distance_m:.0f}m → category={cat}, {a.duration_s}s ({a.duration_s/60:.1f}min)")

        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
