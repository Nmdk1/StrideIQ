"""Debug PB calculations for specific distances"""
import sys
sys.path.insert(0, '/app')

from sqlalchemy.orm import Session
from database import SessionLocal
from models import Athlete, Activity, PersonalBest
from services.personal_best import DISTANCE_CATEGORIES, get_distance_category

db = SessionLocal()

# Get athlete
athlete = db.query(Athlete).filter(Athlete.email == 'mbshaf@gmail.com').first()
if not athlete:
    print("No athlete found")
    exit(1)

print(f"Athlete: {athlete.display_name}")
print(f"\n=== DISTANCE CATEGORY RANGES ===")
for cat, (min_m, max_m) in sorted(DISTANCE_CATEGORIES.items(), key=lambda x: x[1][0]):
    print(f"  {cat}: {min_m}m - {max_m}m ({min_m/1609.34:.2f}mi - {max_m/1609.34:.2f}mi)")

print(f"\n=== CURRENT PBs ===")
pbs = db.query(PersonalBest).filter(PersonalBest.athlete_id == athlete.id).all()
for pb in pbs:
    print(f"  {pb.distance_category}: {pb.time_seconds}s ({pb.time_seconds/60:.1f}min), distance={pb.distance_meters}m, date={pb.achieved_at}")

print(f"\n=== ACTIVITIES MATCHING 'mile' (1570m-1660m) ===")
mile_activities = db.query(Activity).filter(
    Activity.athlete_id == athlete.id,
    Activity.distance_m >= 1570,
    Activity.distance_m <= 1660,
    Activity.duration_s > 0
).order_by(Activity.duration_s.asc()).limit(10).all()

for a in mile_activities:
    print(f"  {a.name}: {a.distance_m:.0f}m, {a.duration_s}s ({a.duration_s/60:.1f}min), date={a.start_time}")

print(f"\n=== ACTIVITIES MATCHING '25k' (24750m-25250m) ===")
activities_25k = db.query(Activity).filter(
    Activity.athlete_id == athlete.id,
    Activity.distance_m >= 24750,
    Activity.distance_m <= 25250,
    Activity.duration_s > 0
).order_by(Activity.duration_s.asc()).limit(10).all()

for a in activities_25k:
    print(f"  {a.name}: {a.distance_m:.0f}m, {a.duration_s}s ({a.duration_s/60:.1f}min), date={a.start_time}")

# Check what's actually being shown for these categories
print(f"\n=== FASTEST MILE ACTIVITIES (any distance 1500-1700m) ===")
near_mile = db.query(Activity).filter(
    Activity.athlete_id == athlete.id,
    Activity.distance_m >= 1500,
    Activity.distance_m <= 1700,
    Activity.duration_s > 0
).order_by(Activity.duration_s.asc()).limit(10).all()

for a in near_mile:
    cat = get_distance_category(a.distance_m)
    print(f"  {a.name}: {a.distance_m:.0f}m → category={cat}, {a.duration_s}s ({a.duration_s/60:.1f}min)")

# Check marathons + long runs that might be matching 25k
print(f"\n=== ACTIVITIES 24-26km range ===")
near_25k = db.query(Activity).filter(
    Activity.athlete_id == athlete.id,
    Activity.distance_m >= 24000,
    Activity.distance_m <= 26000,
    Activity.duration_s > 0
).order_by(Activity.distance_m.asc()).limit(15).all()

for a in near_25k:
    cat = get_distance_category(a.distance_m)
    print(f"  {a.name}: {a.distance_m:.0f}m → category={cat}, {a.duration_s}s ({a.duration_s/60:.1f}min)")

db.close()
