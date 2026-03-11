"""Verify temporal_fact_001 migration ran correctly in production."""
from core.database import SessionLocal
from models import AthleteFact

db = SessionLocal()
try:
    injury = db.query(AthleteFact).filter(AthleteFact.fact_type == "injury_history").first()
    if injury:
        print(f"injury_history: temporal={injury.temporal}, ttl_days={injury.ttl_days}")
    else:
        print("No injury_history facts found")

    strength = db.query(AthleteFact).filter(AthleteFact.fact_type == "strength_pr").first()
    if strength:
        print(f"strength_pr: temporal={strength.temporal}, ttl_days={strength.ttl_days}")
    else:
        print("No strength_pr facts found")

    any_fact = db.query(AthleteFact).first()
    if any_fact:
        print(f"Any fact (columns exist): temporal={any_fact.temporal}, ttl_days={any_fact.ttl_days}")
    else:
        print("No facts in DB yet — migration ran but no facts extracted yet")

    total = db.query(AthleteFact).count()
    print(f"Total facts in DB: {total}")
finally:
    db.close()
