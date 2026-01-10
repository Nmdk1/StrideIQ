#!/usr/bin/env python3
"""
Recalculate all Personal Bests for an athlete from their activity history.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import Athlete
from services.personal_best import recalculate_all_pbs

def recalculate_pbs():
    """Recalculate all PBs"""
    print("=" * 60)
    print("RECALCULATING PERSONAL BESTS")
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
        
        print(f"\n✓ Found athlete: {athlete.id}")
        
        print("\n🔄 Recalculating all Personal Bests...")
        result = recalculate_all_pbs(athlete, db)
        
        print(f"\n✅ Recalculation complete!")
        print(f"   PBs created: {result['created']}")
        print(f"   Total PBs: {result['total']}")
        
        # Show all PBs
        from models import PersonalBest
        pbs = db.query(PersonalBest).filter(
            PersonalBest.athlete_id == athlete.id
        ).order_by(PersonalBest.distance_category).all()
        
        if pbs:
            print("\n📋 Personal Bests:")
            for pb in pbs:
                minutes = pb.time_seconds // 60
                seconds = pb.time_seconds % 60
                pace_str = f"{pb.pace_per_mile:.2f}/mi" if pb.pace_per_mile else "N/A"
                race_str = " (Race)" if pb.is_race else ""
                print(f"   {pb.distance_category:15s} - {minutes}:{seconds:02d} ({pace_str}){race_str} - {pb.achieved_at.date()}")
        else:
            print("\n⚠️  No Personal Bests found")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = recalculate_pbs()
    sys.exit(0 if success else 1)

