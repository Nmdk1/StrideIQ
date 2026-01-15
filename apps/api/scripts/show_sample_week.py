#!/usr/bin/env python3
"""Show a detailed sample build week with specific prescriptions."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from core.database import SessionLocal
from models import Athlete
from services.constraint_aware_planner import generate_constraint_aware_plan


def main():
    db = SessionLocal()
    
    try:
        athlete = db.query(Athlete).filter(
            Athlete.display_name.ilike("%mbshaf%")
        ).first()
        
        if not athlete:
            print("Could not find athlete")
            return
        
        marathon_date = date(2026, 3, 15)
        ten_mile_date = date(2026, 3, 7)
        
        tune_up_races = [
            {
                "date": ten_mile_date,
                "distance": "10_mile",
                "name": "10 Mile Record Attempt",
                "purpose": "threshold"
            }
        ]
        
        plan = generate_constraint_aware_plan(
            athlete_id=athlete.id,
            race_date=marathon_date,
            race_distance="marathon",
            db=db,
            tune_up_races=tune_up_races
        )
        
        print("=" * 80)
        print("SAMPLE WEEKS WITH SPECIFIC PRESCRIPTIONS")
        print("=" * 80)
        
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        
        # Show weeks 4, 5, 6 (build weeks with quality)
        for week in plan.weeks:
            theme_val = week.theme.value if hasattr(week.theme, 'value') else week.theme
            
            if theme_val in ('build_t', 'build_mp', 'peak'):
                print(f"\n{'='*80}")
                print(f"WEEK {week.week_number}: {theme_val.upper()} ({week.total_miles:.0f} miles)")
                print(f"{'='*80}")
                
                for day in week.days:
                    day_name = days[day.day_of_week]
                    
                    if day.workout_type == "rest":
                        print(f"\n  {day_name}: REST")
                    else:
                        print(f"\n  {day_name}: {day.name}")
                        print(f"    {day.description}")
                        if day.paces:
                            pace_str = ", ".join(f"{k}={v}" for k, v in day.paces.items())
                            print(f"    Paces: {pace_str}")
                        print(f"    Miles: {day.target_miles:.1f}, TSS: {day.tss_estimate:.0f}")
                        if day.notes:
                            for note in day.notes:
                                print(f"    • {note}")
                
                if week.notes:
                    print(f"\n  Week notes: {', '.join(week.notes)}")
        
        # Summary table
        print(f"\n{'='*80}")
        print("PLAN OVERVIEW")
        print("=" * 80)
        print(f"\n{'Week':<6} {'Theme':<20} {'Miles':<8} {'Start Date'}")
        print("-" * 50)
        for week in plan.weeks:
            theme_val = week.theme.value if hasattr(week.theme, 'value') else week.theme
            print(f"{week.week_number:<6} {theme_val:<20} {week.total_miles:<8.0f} {week.start_date}")
        
        print(f"\n{'='*80}")
        print("KEY METRICS")
        print("=" * 80)
        print(f"  Prediction: {plan.predicted_time} ({plan.prediction_ci})")
        print(f"  Total Miles: {plan.total_miles:.0f}")
        print(f"  Peak Week: {max(w.total_miles for w in plan.weeks):.0f} miles")
        print(f"  Model Confidence: {plan.model_confidence}")
        print(f"  τ1 = {plan.tau1:.0f} days (fitness time constant)")
        print(f"  τ2 = {plan.tau2:.0f} days (fatigue time constant)")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
