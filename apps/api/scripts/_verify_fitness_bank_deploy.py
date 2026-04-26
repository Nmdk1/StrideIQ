"""Verify fitness bank returns correct values after deploy."""
import sys
sys.path.insert(0, "/app")

from database import SessionLocal
from models import Athlete
from services.fitness_bank import get_fitness_bank

db = SessionLocal()
try:
    founder_email = "mbshaf" + "@" + "gmail.com"
    athlete = db.query(Athlete).filter(Athlete.email == founder_email).first()
    if not athlete:
        print("ERROR: Athlete not found")
        sys.exit(1)

    bank = get_fitness_bank(athlete.id, db)
    print(f"peak_weekly_miles:         {bank.peak_weekly_miles:.2f}")
    print(f"current_weekly_miles:      {bank.current_weekly_miles:.1f}")
    print(f"current_long_run_miles:    {bank.current_long_run_miles:.1f}")
    print(f"best_rpi:                  {bank.best_rpi:.2f}")
    if bank.best_race:
        print(f"best_race:                 {bank.best_race.distance} on {bank.best_race.date} (RPI {bank.best_race.rpi:.2f})")
    print(f"experience_level:          {bank.experience_level.value}")
    print(f"peak_confidence:           {bank.peak_confidence}")
    print(f"recent_quality_sessions:   {bank.recent_quality_sessions_28d}")

    ok = True
    if bank.peak_weekly_miles > 80:
        print(f"\nFAIL: peak_weekly_miles {bank.peak_weekly_miles:.1f} still inflated (expected ~68)")
        ok = False
    if bank.best_rpi < 50:
        print(f"\nFAIL: best_rpi {bank.best_rpi:.2f} still wrong (expected ~53.18)")
        ok = False

    if ok:
        print("\nVERIFIED: Fitness bank values are correct.")
    else:
        print("\nFIXES NOT LIVE — check deployment.")
        sys.exit(1)
finally:
    db.close()
