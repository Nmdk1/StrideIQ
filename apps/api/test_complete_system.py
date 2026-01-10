#!/usr/bin/env python3
"""
Complete System Test - Verify all fixes and new features
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import Athlete, Activity, PersonalBest
from services.performance_engine import get_age_category, calculate_age_at_date

def test_complete_system():
    """Test all system components"""
    print("=" * 60)
    print("COMPLETE SYSTEM TEST")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        # Find athlete with activities
        athlete = db.query(Athlete).join(Activity).first()
        if not athlete:
            print("❌ No athlete with activities found")
            return False
        
        print(f"\n✓ Athlete: {athlete.id}")
        print(f"  Birthdate: {athlete.birthdate}")
        print(f"  Sex: {athlete.sex}")
        
        if athlete.birthdate:
            from datetime import datetime
            age = calculate_age_at_date(athlete.birthdate, datetime.now())
            category = get_age_category(age) if age else None
            print(f"  Age: {age}")
            print(f"  Category: {category}")
        
        # Test age-grading
        print("\n📊 Age-Grading Test:")
        activities_with_perf = db.query(Activity).filter(
            Activity.athlete_id == athlete.id,
            Activity.performance_percentage.isnot(None)
        ).limit(5).all()
        
        print(f"  Activities with age-grading: {len(activities_with_perf)}")
        for act in activities_with_perf[:3]:
            print(f"    {act.start_time.date()} - {act.distance_m/1609.34:.2f}mi - {act.performance_percentage:.1f}%")
        
        # Test race detection
        print("\n🏁 Race Detection Test:")
        races = db.query(Activity).filter(
            Activity.athlete_id == athlete.id,
            Activity.is_race_candidate == True
        ).order_by(Activity.start_time.desc()).all()
        
        print(f"  Races detected: {len(races)}")
        for race in races:
            print(f"    {race.start_time.date()} - {race.distance_m/1609.34:.2f}mi ({race.distance_m:.0f}m) - Confidence: {race.race_confidence:.2f}")
        
        # Test Personal Bests
        print("\n🏆 Personal Bests Test:")
        pbs = db.query(PersonalBest).filter(
            PersonalBest.athlete_id == athlete.id
        ).order_by(PersonalBest.distance_category).all()
        
        print(f"  Personal Bests: {len(pbs)}")
        for pb in pbs:
            minutes = pb.time_seconds // 60
            seconds = pb.time_seconds % 60
            race_str = " (Race)" if pb.is_race else ""
            print(f"    {pb.distance_category:15s} - {minutes}:{seconds:02d} ({pb.pace_per_mile:.2f}/mi){race_str} - {pb.achieved_at.date()}")
        
        print("\n✅ All tests complete!")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = test_complete_system()
    sys.exit(0 if success else 1)

