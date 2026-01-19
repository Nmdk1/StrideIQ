"""
Production verification script.
Generates plans using actual database connection and verifies structure.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta
from sqlalchemy.orm import Session

# Import core modules
from core.database import SessionLocal
from models import Athlete
from services.constraint_aware_planner import ConstraintAwarePlanner


def verify_marathon_plan():
    """Generate a marathon plan and verify key properties."""
    
    db = SessionLocal()
    
    try:
        # Find athlete with email mbshaf@gmail.com
        athlete = db.query(Athlete).filter(Athlete.email == "mbshaf@gmail.com").first()
        
        if not athlete:
            print("[ERROR] Could not find athlete mbshaf@gmail.com")
            return False
        
        print(f"Found athlete: {athlete.email} (ID: {athlete.id})")
        
        # Generate a marathon plan
        planner = ConstraintAwarePlanner(db)
        race_date = date.today() + timedelta(weeks=12)
        
        print(f"\nGenerating 12-week marathon plan for race date: {race_date}")
        
        plan = planner.generate_plan(
            athlete_id=athlete.id,
            race_date=race_date,
            race_distance="marathon"
        )
        
        print(f"\nPlan generated successfully!")
        print(f"  Total weeks: {plan.total_weeks}")
        print(f"  Total miles: {plan.total_miles:.1f}")
        
        # Verify key properties
        issues = []
        
        # 1. Check max long run
        max_long = 0
        for week in plan.weeks:
            for day in week.days:
                if day.workout_type in ["long", "long_mp"]:
                    max_long = max(max_long, day.target_miles)
        
        print(f"  Max long run: {max_long:.1f}mi")
        if max_long > 22:
            issues.append(f"Max long run {max_long:.1f}mi exceeds 22mi cap")
        
        # 2. Check race week is last
        last_theme = plan.weeks[-1].theme.value if hasattr(plan.weeks[-1].theme, 'value') else plan.weeks[-1].theme
        if last_theme != "race":
            issues.append(f"Last week theme is {last_theme}, not 'race'")
        else:
            print(f"  Last week theme: race [OK]")
        
        # 3. Check easy day variety in build weeks
        variety_ok = True
        for week in plan.weeks:
            theme = week.theme.value if hasattr(week.theme, 'value') else week.theme
            if theme in ["build_t", "build_mp", "build_mixed", "peak"]:
                easy_miles = [d.target_miles for d in week.days if d.workout_type == "easy"]
                if len(easy_miles) >= 3:
                    unique = set(round(m, 1) for m in easy_miles)
                    if len(unique) < 2:
                        variety_ok = False
                        issues.append(f"Week {week.week_number} has monotonous easy days")
        
        if variety_ok:
            print(f"  Easy day variety: [OK]")
        
        # 4. Print week themes
        print(f"\n  Week themes:")
        for week in plan.weeks:
            theme = week.theme.value if hasattr(week.theme, 'value') else week.theme
            print(f"    Week {week.week_number}: {theme} ({week.total_miles:.1f}mi)")
        
        # Summary
        if issues:
            print(f"\n[FAIL] Issues found:")
            for issue in issues:
                print(f"  - {issue}")
            return False
        else:
            print(f"\n[PASS] All verification checks passed")
            return True
            
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    success = verify_marathon_plan()
    sys.exit(0 if success else 1)
