#!/usr/bin/env python3
"""
Test custom plan generation with tune-up race.

Scenario: Marathon March 15th with 10-mile record attempt March 7th (8 days before).
The 10-mile serves as the final threshold workout before the marathon.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta
from core.database import SessionLocal
from models import Athlete
from services.model_driven_plan_generator import generate_model_driven_plan


def main():
    db = SessionLocal()
    
    try:
        # Find athlete
        athlete = db.query(Athlete).filter(
            Athlete.display_name.ilike("%mbshaf%")
        ).first()
        
        if not athlete:
            athlete = db.query(Athlete).filter(
                Athlete.email.ilike("%michael%")
            ).first()
        
        if not athlete:
            print("Could not find athlete record")
            return
        
        print("=" * 70)
        print(f"TESTING CUSTOM PLAN FOR: {athlete.display_name or athlete.email}")
        print("=" * 70)
        
        # Your actual scenario
        marathon_date = date(2026, 3, 15)  # March 15, 2026 (Sunday)
        ten_mile_date = date(2026, 3, 7)   # March 7, 2026 (Saturday) - 8 days before
        
        days_between = (marathon_date - ten_mile_date).days
        
        print(f"\n📅 RACE SCHEDULE")
        print(f"  Goal Race: Marathon on {marathon_date.strftime('%B %d, %Y')} ({marathon_date.strftime('%A')})")
        print(f"  Tune-Up:   10 Mile Record Attempt on {ten_mile_date.strftime('%B %d, %Y')} ({ten_mile_date.strftime('%A')})")
        print(f"  Days Between: {days_between}")
        
        # Define tune-up race
        tune_up_races = [
            {
                "date": ten_mile_date,
                "distance": "10_mile",
                "name": "10 Mile Record Attempt",
                "purpose": "threshold"  # Final threshold workout
            }
        ]
        
        print(f"\n" + "=" * 70)
        print("GENERATING PLAN WITH TUNE-UP RACE")
        print("=" * 70)
        
        plan = generate_model_driven_plan(
            athlete_id=athlete.id,
            race_date=marathon_date,
            race_distance="marathon",
            db=db,
            tune_up_races=tune_up_races
        )
        
        print(f"\n📋 PLAN SUMMARY")
        print(f"  Total weeks: {plan.total_weeks}")
        print(f"  Total miles: {plan.total_miles:.1f}")
        print(f"  Model: τ1={plan.tau1:.1f}d, τ2={plan.tau2:.1f}d ({plan.model_confidence})")
        
        # Find the weeks around the tune-up and marathon
        print(f"\n📅 FINAL 3 WEEKS OF PLAN")
        for week in plan.weeks[-3:]:
            print(f"\n  WEEK {week.week_number} ({week.phase})")
            print(f"  Week starts: {week.start_date}")
            for day in week.days:
                if day.workout_type != "rest":
                    print(f"    {day.date} ({day.day_of_week}): {day.name}")
                    if day.description:
                        print(f"      → {day.description[:80]}...")
                    if day.notes:
                        for note in day.notes[:2]:
                            print(f"      • {note}")
                else:
                    print(f"    {day.date} ({day.day_of_week}): REST")
        
        # Check that tune-up race is properly inserted
        print(f"\n🏃 TUNE-UP RACE CHECK")
        tune_up_found = False
        for week in plan.weeks:
            for day in week.days:
                if day.date == ten_mile_date:
                    print(f"  ✅ Found: {day.name} on {day.date}")
                    print(f"     Type: {day.workout_type}")
                    print(f"     Distance: {day.target_miles:.1f} miles")
                    print(f"     Description: {day.description}")
                    if day.notes:
                        for note in day.notes:
                            print(f"     Note: {note}")
                    tune_up_found = True
                    break
        
        if not tune_up_found:
            print(f"  ⚠️ Tune-up race on {ten_mile_date} NOT FOUND in plan!")
        
        # Check marathon is properly placed
        print(f"\n🏁 MARATHON CHECK")
        marathon_found = False
        for week in plan.weeks:
            for day in week.days:
                if day.date == marathon_date or (day.workout_type == "race" and "marathon" in day.name.lower()):
                    print(f"  ✅ Found: {day.name} on {day.date}")
                    print(f"     Type: {day.workout_type}")
                    marathon_found = True
                    break
        
        if not marathon_found:
            print(f"  ⚠️ Marathon on {marathon_date} NOT FOUND in plan!")
        
        # Show personalized insights including tune-up notes
        print(f"\n💡 PERSONALIZED INSIGHTS")
        for note in (plan.counter_conventional_notes or []):
            print(f"  • {note}")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
