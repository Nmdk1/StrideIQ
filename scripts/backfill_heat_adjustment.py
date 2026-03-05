"""Backfill dew_point_f and heat_adjustment_pct for all activities with weather data.

Living Fingerprint Spec — Capability 1: Weather Normalization.
One-time migration: computes from existing temperature_f + humidity_pct.
"""
import sys
sys.path.insert(0, '.')

from core.database import SessionLocal
from models import Activity
from services.heat_adjustment import compute_activity_heat_fields

db = SessionLocal()

activities = db.query(Activity).filter(
    Activity.temperature_f.isnot(None),
    Activity.humidity_pct.isnot(None),
    Activity.dew_point_f.is_(None),
).all()

print(f"Found {len(activities)} activities to backfill")

updated = 0
for act in activities:
    fields = compute_activity_heat_fields(act.temperature_f, act.humidity_pct)
    act.dew_point_f = fields['dew_point_f']
    act.heat_adjustment_pct = fields['heat_adjustment_pct']
    updated += 1

    if updated % 100 == 0:
        db.flush()
        print(f"  Processed {updated}/{len(activities)}")

db.commit()
print(f"Done. Updated {updated} activities.")

# Summary stats
import statistics
adjs = [a.heat_adjustment_pct for a in activities if a.heat_adjustment_pct and a.heat_adjustment_pct > 0]
if adjs:
    print(f"\nHeat adjustment stats (non-zero):")
    print(f"  Count: {len(adjs)}")
    print(f"  Mean:  {statistics.mean(adjs)*100:.1f}%")
    print(f"  Max:   {max(adjs)*100:.1f}%")
    print(f"  Min:   {min(adjs)*100:.1f}%")

db.close()
