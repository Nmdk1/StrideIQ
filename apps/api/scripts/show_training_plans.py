#!/usr/bin/env python3
"""Show extracted training plans."""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db_sync
from models import CoachingKnowledgeEntry

db = get_db_sync()

# Get all training plans
plans = db.query(CoachingKnowledgeEntry).filter(
    CoachingKnowledgeEntry.principle_type == "training_plan"
).all()

print(f"📋 Found {len(plans)} training plans:\n")

for i, plan in enumerate(plans, 1):
    print(f"{i}. Source: {plan.source}")
    print(f"   Methodology: {plan.methodology}")
    
    try:
        plan_data = json.loads(plan.extracted_principles)
        plan_type = plan_data.get("type", "unknown")
        print(f"   Type: {plan_type}")
        
        if plan_type == "weekly_plan":
            weeks = plan_data.get("weeks", [])
            print(f"   Weeks: {len(weeks)}")
            if weeks:
                print(f"   Sample week: Week {weeks[0].get('week')} - {len(weeks[0].get('workouts', []))} workouts")
        
        elif plan_type == "phase_based_plan":
            phases = plan_data.get("phases", [])
            print(f"   Phases: {len(phases)}")
            for phase in phases[:3]:
                print(f"     - {phase.get('phase')} ({phase.get('duration', 'N/A')})")
        
        elif "distance_plan" in plan_type:
            distance = plan_data.get("distance", "unknown")
            plan_list = plan_data.get("plans", [])
            print(f"   Distance: {distance}")
            print(f"   Plans found: {len(plan_list)}")
            if plan_list:
                workouts = plan_list[0].get("workouts", [])
                print(f"   Sample workouts: {len(workouts)}")
        
        elif plan_type == "training_schedule":
            workouts = plan_data.get("workouts", [])
            print(f"   Workouts found: {len(workouts)}")
            if workouts:
                print(f"   Sample: {workouts[0].get('type', 'unknown')} - {workouts[0].get('prescription', '')[:60]}...")
        
    except Exception as e:
        print(f"   Error parsing: {e}")
    
    print()

# Summary by source
daniels_plans = [p for p in plans if "Daniels" in p.source]
pfitz_plans = [p for p in plans if "Marathoning" in p.source]

print(f"\n📊 Summary:")
print(f"   Daniels' Running Formula: {len(daniels_plans)} plans")
print(f"   Advanced Marathoning: {len(pfitz_plans)} plans")

db.close()

