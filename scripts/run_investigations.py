"""Run all investigations against founder's data and display results."""
import json
from core.database import SessionLocal
from models import Athlete
from services.race_input_analysis import mine_race_inputs

db = SessionLocal()
a = db.query(Athlete).filter(Athlete.email == 'mbshaf@gmail.com').first()

print(f"Running investigations for {a.email} (RPI: {a.rpi})")
print("=" * 80)

findings = mine_race_inputs(a.id, db)

print(f"\n{len(findings)} findings produced\n")

for i, f in enumerate(findings, 1):
    print(f"{'=' * 80}")
    print(f"FINDING {i} [{f.layer}] [{f.finding_type}] confidence={f.confidence}")
    print(f"{'=' * 80}")
    print(f"\n{f.sentence}\n")
    print(f"Receipts:")
    for k, v in f.receipts.items():
        if isinstance(v, list) and len(v) > 3:
            print(f"  {k}: [{len(v)} items]")
            for item in v[:3]:
                print(f"    {item}")
            print(f"    ... and {len(v) - 3} more")
        elif isinstance(v, dict):
            print(f"  {k}:")
            for dk, dv in v.items():
                print(f"    {dk}: {dv}")
        else:
            print(f"  {k}: {v}")
    print()

db.close()
