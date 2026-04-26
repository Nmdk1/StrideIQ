"""Clear bad lap_type labels on Michael's recent half marathon so the
corrected interval detector re-classifies at read time."""
from core.database import SessionLocal
from models import Activity, ActivitySplit, Athlete
from sqlalchemy import desc

db = SessionLocal()
a = db.query(Athlete).filter(Athlete.email == "mbshaf@gmail.com").first()
print(f"Athlete: {a.display_name}, id={a.id}")

acts = (
    db.query(Activity)
    .filter(Activity.athlete_id == a.id)
    .order_by(desc(Activity.start_date))
    .limit(5)
    .all()
)
for act in acts:
    splits_count = db.query(ActivitySplit).filter(ActivitySplit.activity_id == act.id).count()
    dist_mi = round(act.distance / 1609.34, 2) if act.distance else 0
    print(f"  {act.start_date} | {act.name} | {dist_mi} mi | {splits_count} splits | id={act.id}")

# Find the ~13mi activity (half marathon)
hm = None
for act in acts:
    dist_mi = (act.distance or 0) / 1609.34
    if 12.5 < dist_mi < 14.5:
        hm = act
        break

if hm:
    print(f"\nClearing labels on: {hm.name} ({round(hm.distance/1609.34, 2)} mi)")
    updated = (
        db.query(ActivitySplit)
        .filter(ActivitySplit.activity_id == hm.id)
        .update({"lap_type": None, "interval_number": None})
    )
    db.commit()
    print(f"Cleared {updated} split labels")
else:
    print("No half marathon found in recent activities")

db.close()
