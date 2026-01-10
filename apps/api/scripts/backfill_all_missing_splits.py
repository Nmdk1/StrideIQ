#!/usr/bin/env python3
"""
Backfill splits for all activities that are missing them.
This addresses the issue where older activities don't have splits.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import Activity, ActivitySplit, Athlete
from sqlalchemy import func
from services.strava_service import get_activity_laps
from routers.strava import _coerce_int
import time

LAP_FETCH_DELAY = 2  # seconds between requests

def backfill_all_missing_splits():
    """Backfill splits for all activities missing them"""
    print("=" * 60)
    print("BACKFILLING ALL MISSING SPLITS")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        # Find athlete with activities
        athlete = db.query(Athlete).join(Activity).first()
        if not athlete:
            print("❌ No athlete with activities found")
            return False
        
        if not athlete.strava_access_token:
            print("❌ Athlete missing Strava access token")
            return False
        
        print(f"\n✓ Found athlete: {athlete.id}")
        
        # Find activities missing splits
        activities = db.query(Activity).filter(
            Activity.athlete_id == athlete.id,
            Activity.provider == "strava",
            Activity.external_activity_id.isnot(None),
            Activity.distance_m.isnot(None),
            Activity.distance_m > 1600  # > 1 mile
        ).order_by(Activity.start_time.desc()).all()
        
        missing_splits = []
        for activity in activities:
            split_count = db.query(func.count(ActivitySplit.id)).filter(
                ActivitySplit.activity_id == activity.id
            ).scalar()
            
            if split_count == 0:
                missing_splits.append(activity)
        
        print(f"\n📊 Activities missing splits: {len(missing_splits)}")
        
        if not missing_splits:
            print("✅ All activities have splits!")
            return True
        
        print(f"\n🔄 Starting backfill for {len(missing_splits)} activities...")
        print(f"   Delay between requests: {LAP_FETCH_DELAY}s")
        
        successful = 0
        failed = 0
        skipped = 0
        
        for idx, activity in enumerate(missing_splits):
            try:
                strava_activity_id = int(activity.external_activity_id)
                
                # Add delay to avoid rate limiting
                if idx > 0:
                    time.sleep(LAP_FETCH_DELAY)
                
                print(f"\n[{idx+1}/{len(missing_splits)}] Processing {activity.start_time.date()} - {activity.distance_m/1609.34:.2f}mi...")
                
                laps = get_activity_laps(athlete, strava_activity_id) or []
                
                if not laps:
                    print(f"  ⚠️  No lap data available")
                    skipped += 1
                    continue
                
                # Create split records
                splits_created = 0
                for lap in laps:
                    lap_idx = lap.get("lap_index") or lap.get("split")
                    if not lap_idx:
                        continue
                    
                    split = ActivitySplit(
                        activity_id=activity.id,
                        split_number=int(lap_idx),
                        distance=lap.get("distance"),
                        elapsed_time=lap.get("elapsed_time"),
                        moving_time=lap.get("moving_time"),
                        average_heartrate=_coerce_int(lap.get("average_heartrate")),
                        max_heartrate=_coerce_int(lap.get("max_heartrate")),
                        average_cadence=lap.get("average_cadence"),
                    )
                    db.add(split)
                    splits_created += 1
                
                db.commit()
                print(f"  ✅ Created {splits_created} splits")
                successful += 1
                
            except Exception as e:
                print(f"  ❌ Error: {e}")
                db.rollback()
                failed += 1
                import traceback
                traceback.print_exc()
        
        print(f"\n✅ Backfill complete!")
        print(f"   Successful: {successful}")
        print(f"   Failed: {failed}")
        print(f"   Skipped (no data): {skipped}")
        
        return successful > 0
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = backfill_all_missing_splits()
    sys.exit(0 if success else 1)


