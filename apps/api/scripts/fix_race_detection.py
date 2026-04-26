#!/usr/bin/env python3
"""
Fix Race Detection - Reset all race flags and recalculate with improved logic.

This script:
1. Resets all is_race_candidate flags to False
2. Recalculates race detection for all activities using improved conservative logic
3. Only marks activities as races if they:
   - Match standard race distances (5K, 10K, Half, Full Marathon)
   - Have high HR intensity (>88% of max)
   - Have consistent pace
   - Meet confidence threshold of 0.80
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SessionLocal
from models import Activity, Athlete
from routers.strava import _calculate_performance_metrics

def fix_race_detection():
    """Reset and recalculate race detection for all activities"""
    print("=" * 60)
    print("FIXING RACE DETECTION")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        # Get athlete
        athlete = db.query(Athlete).first()
        if not athlete:
            print("❌ No athlete found")
            return False
        
        print(f"\n✓ Found athlete: {athlete.id}")
        print(f"  Birthdate: {athlete.birthdate}")
        print(f"  Sex: {athlete.sex}")
        
        if not athlete.birthdate or not athlete.sex:
            print("\n⚠️  WARNING: Athlete missing birthdate or sex - age-grading will not work")
            print("   Age-grading requires birthdate and sex to calculate")
        
        # Get all activities
        activities = db.query(Activity).order_by(Activity.start_time.desc()).all()
        print(f"\n📊 Found {len(activities)} activities")
        
        # Step 1: Reset all race flags
        print("\n🔄 Step 1: Resetting all race flags...")
        db.query(Activity).update({
            Activity.is_race_candidate: False,
            Activity.race_confidence: None
        })
        db.commit()
        print("✓ All race flags reset")
        
        # Step 2: Recalculate with improved logic
        print("\n🔄 Step 2: Recalculating race detection with improved logic...")
        recalculated = 0
        races_found = 0
        
        for activity in activities:
            try:
                _calculate_performance_metrics(activity, athlete, db)
                recalculated += 1
                
                if activity.is_race_candidate:
                    races_found += 1
                    print(f"  ✓ Race detected: {activity.start_time.date()} - {activity.distance_m/1609.34:.2f}mi - Confidence: {activity.race_confidence:.2f}")
            except Exception as e:
                print(f"  ⚠️  Error calculating metrics for {activity.id}: {e}")
        
        db.commit()
        
        print("\n✅ Recalculation complete!")
        print(f"   Activities recalculated: {recalculated}")
        print(f"   Races detected: {races_found}")
        
        # Show races found
        if races_found > 0:
            print("\n📋 Activities marked as races:")
            race_activities = db.query(Activity).filter(
                Activity.is_race_candidate.is_(True)
            ).order_by(Activity.start_time.desc()).all()
            
            for race in race_activities:
                print(f"   {race.start_time.date()} - {race.distance_m/1609.34:.2f}mi ({race.distance_m:.0f}m) - {race.duration_s/60:.1f}min - Confidence: {race.race_confidence:.2f}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = fix_race_detection()
    sys.exit(0 if success else 1)

