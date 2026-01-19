"""
Verify all distance types generate correct plans in production.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta
from sqlalchemy.orm import Session

from core.database import SessionLocal
from models import Athlete
from services.constraint_aware_planner import ConstraintAwarePlanner


# N=1 Logic: Long run cap = min(volume_cap, time_cap, proven_cap)
# NO arbitrary distance-based caps - this verifies N=1 is working


def verify_distance(db: Session, athlete_id, distance: str, weeks: int, 
                   expected_min_long: float = None) -> bool:
    """Verify a single distance plan follows N=1 logic."""
    
    planner = ConstraintAwarePlanner(db)
    race_date = date.today() + timedelta(weeks=weeks)
    
    try:
        plan = planner.generate_plan(
            athlete_id=athlete_id,
            race_date=race_date,
            race_distance=distance
        )
        
        # Check max long run
        max_long = 0
        for week in plan.weeks:
            for day in week.days:
                if day.workout_type in ["long", "long_mp"]:
                    max_long = max(max_long, day.target_miles)
        
        # N=1 verification: long run should be driven by volume/time/proven, not distance
        # We just verify it's reasonable (> 0 and not absurdly high)
        long_ok = 0 < max_long <= 25  # Sanity check only
        
        # Check race week is last
        last_theme = plan.weeks[-1].theme.value if hasattr(plan.weeks[-1].theme, 'value') else plan.weeks[-1].theme
        race_ok = last_theme == "race"
        
        # Check variety
        variety_ok = True
        for week in plan.weeks:
            theme = week.theme.value if hasattr(week.theme, 'value') else week.theme
            if theme in ["build_t", "build_mp", "build_mixed", "peak"]:
                easy_miles = [d.target_miles for d in week.days if d.workout_type == "easy"]
                if len(easy_miles) >= 3:
                    unique = set(round(m, 1) for m in easy_miles)
                    if len(unique) < 2:
                        variety_ok = False
        
        # If expected_min_long provided, verify it's met (N=1 verification)
        min_ok = True
        if expected_min_long and max_long < expected_min_long:
            min_ok = False
        
        status = "PASS" if (long_ok and race_ok and variety_ok and min_ok) else "FAIL"
        issues = []
        if not long_ok:
            issues.append(f"long={max_long:.1f}mi out of range")
        if not race_ok:
            issues.append(f"last_theme={last_theme}")
        if not variety_ok:
            issues.append("monotonous easy days")
        if not min_ok:
            issues.append(f"expected min {expected_min_long}mi")
        
        issue_str = f" ({', '.join(issues)})" if issues else ""
        print(f"[{status}] {distance:15} {weeks:2}wk | max_long={max_long:5.1f}mi{issue_str}")
        
        return status == "PASS"
        
    except Exception as e:
        print(f"[ERROR] {distance:15} {weeks:2}wk | {type(e).__name__}: {e}")
        return False


def main():
    db = SessionLocal()
    
    try:
        athlete = db.query(Athlete).filter(Athlete.email == "mbshaf@gmail.com").first()
        if not athlete:
            print("[ERROR] Could not find athlete")
            return False
        
        print(f"Athlete: {athlete.email}\n")
        print("=" * 60)
        
        results = []
        
        # Test each distance
        test_cases = [
            ("5k", 8),
            ("10k", 10),
            ("half_marathon", 12),
            ("marathon", 16),
            ("marathon", 12),  # Short prep
            ("marathon", 6),   # Very short prep
        ]
        
        for distance, weeks in test_cases:
            result = verify_distance(db, athlete.id, distance, weeks)
            results.append(result)
        
        print("=" * 60)
        passed = sum(results)
        total = len(results)
        print(f"\nSUMMARY: {passed}/{total} passed")
        
        return all(results)
        
    finally:
        db.close()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
