#!/usr/bin/env python3
"""
Check which activities are missing splits.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import Activity, ActivitySplit
from sqlalchemy import func

def check_missing_splits():
    """Find activities missing splits"""
    print("=" * 60)
    print("CHECKING FOR MISSING SPLITS")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        # Get all activities with distance > 1 mile
        activities = db.query(Activity).filter(
            Activity.distance_m.isnot(None),
            Activity.distance_m > 1600  # > 1 mile
        ).order_by(Activity.start_time.desc()).all()
        
        print(f"\n📊 Total activities > 1 mile: {len(activities)}")
        
        missing_splits = []
        for activity in activities:
            split_count = db.query(func.count(ActivitySplit.id)).filter(
                ActivitySplit.activity_id == activity.id
            ).scalar()
            
            if split_count == 0:
                missing_splits.append(activity)
        
        print(f"\n⚠️  Activities missing splits: {len(missing_splits)}")
        
        if missing_splits:
            print("\n📋 First 20 activities missing splits:")
            for act in missing_splits[:20]:
                print(f"  {act.start_time.date()} - {act.distance_m/1609.34:.2f}mi - ID: {act.external_activity_id}")
            
            # Group by date range
            from datetime import datetime, timedelta, timezone
            now = datetime.now(timezone.utc)
            ranges = {
                'Last 30 days': (now - timedelta(days=30), now),
                '31-90 days ago': (now - timedelta(days=90), now - timedelta(days=30)),
                '91-180 days ago': (now - timedelta(days=180), now - timedelta(days=90)),
                'Older than 180 days': (datetime(2020, 1, 1, tzinfo=timezone.utc), now - timedelta(days=180)),
            }
            
            print("\n📊 Missing splits by date range:")
            for range_name, (start, end) in ranges.items():
                count = sum(1 for a in missing_splits if start <= a.start_time <= end)
                print(f"  {range_name}: {count}")
        
        return len(missing_splits) > 0
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    has_missing = check_missing_splits()
    sys.exit(0 if not has_missing else 1)

