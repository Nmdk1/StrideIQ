"""One-time: backfill an athlete's Strava activities with HR from matching Garmin activities."""
import sys
import argparse
import os
sys.path.insert(0, "/app")

from datetime import timedelta
from core.database import SessionLocal
from models import Athlete, Activity

db = SessionLocal()
parser = argparse.ArgumentParser(description="Backfill Strava HR from Garmin matches")
parser.add_argument(
    "--athlete-email",
    default=os.getenv("STRIDEIQ_ATHLETE_EMAIL"),
    help="Athlete email (or set STRIDEIQ_ATHLETE_EMAIL).",
)
args = parser.parse_args()
if not args.athlete_email:
    raise SystemExit("Missing athlete email. Provide --athlete-email or STRIDEIQ_ATHLETE_EMAIL.")

user = db.query(Athlete).filter(Athlete.email == args.athlete_email).first()
if not user:
    db.close()
    raise SystemExit(f"Athlete not found: {args.athlete_email}")

strava_no_hr = (
    db.query(Activity)
    .filter(
        Activity.athlete_id == user.id,
        Activity.provider == "strava",
        Activity.avg_hr.is_(None),
    )
    .all()
)

filled = 0
for sa in strava_no_hr:
    window = timedelta(minutes=30)
    candidates = (
        db.query(Activity)
        .filter(
            Activity.athlete_id == user.id,
            Activity.provider == "garmin",
            Activity.avg_hr.isnot(None),
            Activity.start_time >= sa.start_time - window,
            Activity.start_time <= sa.start_time + window,
        )
        .all()
    )
    if not candidates:
        continue

    matched = []
    for g in candidates:
        if sa.distance_m and g.distance_m:
            ratio = sa.distance_m / g.distance_m
            if ratio < 0.9 or ratio > 1.1:
                continue
        matched.append(g)

    if not matched:
        continue

    garmin = min(matched, key=lambda g: abs((g.start_time - sa.start_time).total_seconds()))
    sa.avg_hr = garmin.avg_hr
    sa.max_hr = garmin.max_hr
    filled += 1
    print(f"  Filled: {sa.start_time.date()} {sa.name} <- HR {garmin.avg_hr}/{garmin.max_hr}")

db.commit()
print(f"\nDone: {filled}/{len(strava_no_hr)} activities enriched")
db.close()
