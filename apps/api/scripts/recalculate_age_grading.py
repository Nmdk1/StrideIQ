#!/usr/bin/env python3
"""
Recalculate age-grading for all activities now that athlete has birthdate/sex.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import Activity, Athlete
from routers.strava import _calculate_performance_metrics

def recalculate_age_grading():
    """Recalculate age-grading for all activities"""
    print("=" * 60)
    print("RECALCULATING AGE-GRADING")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        # Find athlete with activities
        from models import Activity
        athlete = db.query(Athlete).join(Activity).first()
        if not athlete:
            # Fallback to first athlete
            athlete = db.query(Athlete).first()
        
        if not athlete:
            print("❌ No athlete found")
            return False
        
        if not athlete.birthdate or not athlete.sex:
            print("❌ Athlete missing birthdate or sex")
            print(f"   Birthdate: {athlete.birthdate}")
            print(f"   Sex: {athlete.sex}")
            return False
        
        print(f"\n✓ Found athlete: {athlete.id}")
        print(f"  Birthdate: {athlete.birthdate}")
        print(f"  Sex: {athlete.sex}")
        
        activities = db.query(Activity).filter(
            Activity.athlete_id == athlete.id,
            Activity.distance_m.isnot(None),
            Activity.duration_s.isnot(None)
        ).order_by(Activity.start_time.desc()).all()
        
        print(f"\n📊 Found {len(activities)} activities to recalculate")
        
        recalculated = 0
        with_performance = 0
        
        for activity in activities:
            try:
                _calculate_performance_metrics(activity, athlete, db)
                recalculated += 1
                if activity.performance_percentage:
                    with_performance += 1
            except Exception as e:
                print(f"  ⚠️  Error calculating metrics for {activity.id}: {e}")
        
        db.commit()
        
        print(f"\n✅ Recalculation complete!")
        print(f"   Activities recalculated: {recalculated}")
        print(f"   Activities with performance %: {with_performance}")
        
        # Show sample of activities with performance %
        sample = db.query(Activity).filter(
            Activity.athlete_id == athlete.id,
            Activity.performance_percentage.isnot(None)
        ).order_by(Activity.start_time.desc()).limit(5).all()
        
        if sample:
            print("\n📋 Sample activities with age-graded performance:")
            for act in sample:
                print(f"   {act.start_time.date()} - {act.distance_m/1609.34:.2f}mi - {act.performance_percentage:.1f}%")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = recalculate_age_grading()
    sys.exit(0 if success else 1)

