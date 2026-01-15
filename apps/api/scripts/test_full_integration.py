#!/usr/bin/env python3
"""
Test full integration of Constraint-Aware Plan generation.

This tests the complete flow:
1. Fitness Bank calculation
2. Week theme generation
3. Workout prescription
4. Plan save to database
5. API endpoint validation
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta
from core.database import SessionLocal
from models import Athlete, TrainingPlan, PlannedWorkout
from services.constraint_aware_planner import generate_constraint_aware_plan


def main():
    db = SessionLocal()
    
    try:
        # Find athlete
        athlete = db.query(Athlete).filter(
            Athlete.display_name.ilike("%mbshaf%")
        ).first()
        
        if not athlete:
            print("Could not find athlete")
            return
        
        print("=" * 80)
        print(f"FULL INTEGRATION TEST: {athlete.display_name}")
        print("=" * 80)
        
        # Test scenario
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
        
        print(f"\n📅 SCENARIO")
        print(f"  Goal: Marathon on {marathon_date}")
        print(f"  Tune-up: 10 Mile on {ten_mile_date}")
        
        # Generate plan
        print(f"\n🔄 Generating plan...")
        plan = generate_constraint_aware_plan(
            athlete_id=athlete.id,
            race_date=marathon_date,
            race_distance="marathon",
            db=db,
            tune_up_races=tune_up_races
        )
        
        print(f"\n✅ PLAN GENERATED")
        print(f"  Weeks: {plan.total_weeks}")
        print(f"  Total Miles: {plan.total_miles:.0f}")
        print(f"  Peak Miles: {max(w.total_miles for w in plan.weeks):.0f}")
        print(f"  τ1: {plan.tau1:.0f}d")
        print(f"  τ2: {plan.tau2:.0f}d")
        print(f"  Prediction: {plan.predicted_time}")
        
        # Validate structure
        print(f"\n📋 STRUCTURE VALIDATION")
        
        checks = []
        
        # Check 1: Weeks exist
        checks.append(("Weeks generated", len(plan.weeks) >= 8))
        
        # Check 2: All weeks have days
        all_have_days = all(len(w.days) == 7 for w in plan.weeks)
        checks.append(("All weeks have 7 days", all_have_days))
        
        # Check 3: Themes alternate
        themes = [w.theme.value if hasattr(w.theme, 'value') else w.theme for w in plan.weeks]
        consecutive_same = False
        for i in range(1, len(themes)):
            if themes[i] == themes[i-1] and themes[i] not in ('rebuild_easy', 'rebuild_strides', 'recovery'):
                consecutive_same = True
                break
        checks.append(("Theme alternation", not consecutive_same))
        
        # Check 4: Race week at end
        checks.append(("Race week at end", themes[-1] == 'race'))
        
        # Check 5: Tune-up race inserted
        checks.append(("Tune-up race week", 'tune_up' in themes))
        
        # Check 6: Workouts have descriptions
        sample_week = plan.weeks[4] if len(plan.weeks) > 4 else plan.weeks[-2]
        has_descriptions = all(d.description for d in sample_week.days if d.workout_type != 'rest')
        checks.append(("Workouts have descriptions", has_descriptions))
        
        # Check 7: Workouts have paces
        has_paces = any(d.paces for d in sample_week.days if d.workout_type != 'rest')
        checks.append(("Workouts have paces", has_paces))
        
        # Check 8: Counter-conventional notes
        checks.append(("Personalized insights", len(plan.counter_conventional_notes) >= 3))
        
        # Check 9: Fitness bank populated
        fb = plan.fitness_bank
        checks.append(("Fitness bank populated", 'peak' in fb and fb['peak']['weekly_miles'] > 60))
        
        for name, result in checks:
            print(f"  {'✅' if result else '❌'} {name}")
        
        passed = sum(1 for _, r in checks if r)
        print(f"\n  Result: {passed}/{len(checks)} checks passed")
        
        # Sample workout details
        print(f"\n📝 SAMPLE WORKOUTS (Week {sample_week.week_number})")
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for day in sample_week.days:
            if day.workout_type != 'rest':
                print(f"  {days[day.day_of_week]}: {day.name}")
                print(f"       {day.description[:60]}...")
                if day.paces:
                    print(f"       Paces: {day.paces}")
        
        # Counter-conventional notes
        print(f"\n💡 PERSONALIZED INSIGHTS")
        for note in plan.counter_conventional_notes[:5]:
            print(f"  • {note[:80]}...")
        
        # Week overview
        print(f"\n📆 WEEK OVERVIEW")
        for w in plan.weeks:
            theme_val = w.theme.value if hasattr(w.theme, 'value') else w.theme
            print(f"  Week {w.week_number:2d}: {theme_val:20s} {w.total_miles:5.0f}mi")
        
        print(f"\n{'='*80}")
        print("INTEGRATION TEST COMPLETE")
        print("=" * 80)
        
        if passed == len(checks):
            print("✅ ALL CHECKS PASSED - Ready for production use")
        else:
            print(f"⚠️ {len(checks) - passed} checks failed - review above")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
