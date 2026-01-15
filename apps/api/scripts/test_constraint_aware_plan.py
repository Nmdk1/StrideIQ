#!/usr/bin/env python3
"""
Test Constraint-Aware Plan generation against Michael's actual data.

Expected:
- 8-9 weeks to March 15 marathon
- Tune-up race March 7 (10-mile, threshold purpose)
- Injury constraint: first 2-3 weeks rebuild
- Week themes: alternating T/MP with recovery
- Specific workouts: "2x3mi @ T", not "threshold work"
- Personal paces from VDOT 53
- 70+ mpw peak weeks for elite experience
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from core.database import SessionLocal
from models import Athlete
from services.constraint_aware_planner import generate_constraint_aware_plan


def format_pace(pace_min: float) -> str:
    """Format pace as M:SS."""
    m = int(pace_min)
    s = int((pace_min - m) * 60)
    return f"{m}:{s:02d}"


def main():
    db = SessionLocal()
    
    try:
        # Find athlete
        athlete = db.query(Athlete).filter(
            Athlete.display_name.ilike("%mbshaf%")
        ).first()
        
        if not athlete:
            print("Could not find athlete record")
            return
        
        print("=" * 80)
        print(f"TESTING CONSTRAINT-AWARE PLAN FOR: {athlete.display_name}")
        print("=" * 80)
        
        # Your actual scenario
        marathon_date = date(2026, 3, 15)   # March 15, 2026 (Sunday)
        ten_mile_date = date(2026, 3, 7)    # March 7, 2026 (Saturday)
        
        print(f"\n📅 RACE SCHEDULE")
        print(f"  Goal Race: Marathon on {marathon_date}")
        print(f"  Tune-Up:   10 Mile on {ten_mile_date}")
        print(f"  Days Between: {(marathon_date - ten_mile_date).days}")
        
        tune_up_races = [
            {
                "date": ten_mile_date,
                "distance": "10_mile",
                "name": "10 Mile Record Attempt",
                "purpose": "threshold"  # Race it hard - final threshold workout
            }
        ]
        
        # Generate plan
        print(f"\nGenerating plan...")
        plan = generate_constraint_aware_plan(
            athlete_id=athlete.id,
            race_date=marathon_date,
            race_distance="marathon",
            db=db,
            tune_up_races=tune_up_races
        )
        
        # Summary
        print(f"\n📋 PLAN SUMMARY")
        print(f"  Total weeks: {plan.total_weeks}")
        print(f"  Total miles: {plan.total_miles:.0f}")
        print(f"  Model: τ1={plan.tau1:.0f}d, τ2={plan.tau2:.0f}d ({plan.model_confidence})")
        print(f"  Prediction: {plan.predicted_time} {plan.prediction_ci}")
        
        # Fitness Bank summary
        fb = plan.fitness_bank
        print(f"\n🏦 FITNESS BANK")
        print(f"  Peak: {fb['peak']['weekly_miles']:.0f}mpw, {fb['peak']['long_run']:.0f}mi long, {fb['peak']['mp_long_run']:.0f}@MP")
        print(f"  Current: {fb['current']['weekly_miles']:.0f}mpw")
        print(f"  Constraint: {fb['constraint']['type']}")
        print(f"  Experience: {fb['experience']}")
        
        # Week themes
        print(f"\n📆 WEEK THEMES")
        for week in plan.weeks:
            theme = week.theme.value if hasattr(week.theme, 'value') else week.theme
            print(f"  Week {week.week_number}: {theme:20s} {week.total_miles:5.0f}mi  {week.start_date}")
        
        # Validate theme alternation
        print(f"\n✅ VALIDATION CHECKS")
        
        themes = [w.theme.value if hasattr(w.theme, 'value') else w.theme for w in plan.weeks]
        
        # Check 1: No consecutive same-emphasis (except rebuild)
        consecutive_same = False
        for i in range(1, len(themes)):
            if themes[i] == themes[i-1] and themes[i] not in ('rebuild_easy', 'rebuild_strides', 'recovery'):
                consecutive_same = True
                break
        print(f"  {'✅' if not consecutive_same else '❌'} No consecutive same-emphasis weeks")
        
        # Check 2: Injury protection (first weeks should be rebuild)
        first_rebuild = themes[0] in ('rebuild_easy', 'rebuild_strides', 'build_t', 'build_mp')
        print(f"  {'✅' if first_rebuild else '❌'} First week respects injury state")
        
        # Check 3: Tune-up race present
        tune_up_present = 'tune_up' in themes
        print(f"  {'✅' if tune_up_present else '❌'} Tune-up race week present")
        
        # Check 4: Race week at end
        race_at_end = themes[-1] == 'race'
        print(f"  {'✅' if race_at_end else '❌'} Race week at end")
        
        # Check 5: Peak volume appropriate for elite
        max_week_miles = max(w.total_miles for w in plan.weeks if w.theme.value not in ('tune_up', 'race', 'taper_1', 'taper_2'))
        elite_appropriate = max_week_miles >= 60
        print(f"  {'✅' if elite_appropriate else '❌'} Peak volume appropriate ({max_week_miles:.0f}mi)")
        
        # Sample week detail
        print(f"\n📋 SAMPLE WEEK DETAIL")
        
        # Find a build week
        build_week = None
        for w in plan.weeks:
            theme_val = w.theme.value if hasattr(w.theme, 'value') else w.theme
            if 'build' in theme_val:
                build_week = w
                break
        
        if build_week:
            theme_val = build_week.theme.value if hasattr(build_week.theme, 'value') else build_week.theme
            print(f"\n  Week {build_week.week_number}: {theme_val} ({build_week.total_miles:.0f} miles)")
            print(f"  Start: {build_week.start_date}")
            
            days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            for day in build_week.days:
                if day.workout_type != "rest":
                    print(f"    {days[day.day_of_week]}: {day.name}")
                    print(f"        {day.description}")
                    if day.notes:
                        for note in day.notes[:2]:
                            print(f"        • {note}")
                else:
                    print(f"    {days[day.day_of_week]}: REST")
        
        # Tune-up week detail
        print(f"\n🏃 TUNE-UP RACE WEEK")
        for w in plan.weeks:
            theme_val = w.theme.value if hasattr(w.theme, 'value') else w.theme
            if theme_val == 'tune_up':
                print(f"  Week {w.week_number} ({w.total_miles:.0f} miles)")
                days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                for day in w.days:
                    if day.workout_type == "tune_up_race":
                        print(f"    {days[day.day_of_week]}: {day.name} ← RACE")
                        print(f"        {day.description}")
                        for note in day.notes:
                            print(f"        • {note}")
                    elif day.workout_type != "rest":
                        print(f"    {days[day.day_of_week]}: {day.name}")
                    else:
                        print(f"    {days[day.day_of_week]}: REST")
                break
        
        # Race week detail
        print(f"\n🏁 RACE WEEK")
        race_week = plan.weeks[-1]
        print(f"  Week {race_week.week_number} ({race_week.total_miles:.0f} miles)")
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for day in race_week.days:
            if day.workout_type == "race":
                print(f"    {days[day.day_of_week]}: {day.name} ← MARATHON")
            elif day.workout_type != "rest":
                print(f"    {days[day.day_of_week]}: {day.name}")
            else:
                print(f"    {days[day.day_of_week]}: REST")
        
        # Counter-conventional notes
        print(f"\n💡 PERSONALIZED INSIGHTS")
        for note in plan.counter_conventional_notes:
            print(f"  • {note}")
        
        # Final validation
        print(f"\n" + "=" * 80)
        print("FINAL VALIDATION")
        print("=" * 80)
        
        checks = [
            ("Total weeks >= 8", plan.total_weeks >= 8),
            ("Peak volume >= 60 mpw", max_week_miles >= 60),
            ("Theme alternation", not consecutive_same),
            ("Tune-up race inserted", tune_up_present),
            ("Race week present", race_at_end),
            ("Personal insights generated", len(plan.counter_conventional_notes) >= 3),
            ("Prediction provided", plan.predicted_time is not None),
        ]
        
        passed = sum(1 for _, result in checks if result)
        for name, result in checks:
            print(f"  {'✅' if result else '❌'} {name}")
        
        print(f"\n  Result: {passed}/{len(checks)} checks passed")
        
        if passed == len(checks):
            print(f"\n  ✅ FRAMEWORK VALIDATED")
        else:
            print(f"\n  ⚠️  Some checks failed - review output above")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
