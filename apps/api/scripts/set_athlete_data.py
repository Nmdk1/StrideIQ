#!/usr/bin/env python3
"""
Set athlete birthdate and sex for age-grading calculations.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import Athlete
from datetime import date

def set_athlete_data():
    """Set athlete birthdate and sex"""
    print("=" * 60)
    print("SETTING ATHLETE DATA")
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
        print(f"  Current birthdate: {athlete.birthdate}")
        print(f"  Current sex: {athlete.sex}")
        
        # Set to 57 year old male (born 1968)
        athlete.birthdate = date(1968, 1, 1)
        athlete.sex = 'M'
        
        db.commit()
        
        print(f"\n✅ Updated athlete:")
        print(f"  Birthdate: {athlete.birthdate}")
        print(f"  Sex: {athlete.sex}")
        print(f"  Age: {2025 - 1968}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = set_athlete_data()
    sys.exit(0 if success else 1)

