#!/usr/bin/env python3
"""
Simple test script to verify the sync fix works correctly.
This resets last_strava_sync to None and then runs the sync.
"""
import sys
from database import SessionLocal
from models import Athlete
from routers.strava import strava_sync

def test_sync():
    print("=" * 60)
    print("TEST: Verifying Sync Fix")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        # Step 1: Find the athlete WITH Strava token (same query as strava_sync uses)
        athlete = db.query(Athlete).filter(Athlete.strava_access_token.isnot(None)).first()
        if not athlete:
            print("ERROR: No athlete with Strava connection found in database!")
            return False
        
        print(f"\n✓ Found athlete with Strava token: {athlete.id}")
        
        # Step 2: Check current state
        print(f"\nBEFORE RESET:")
        print(f"  last_strava_sync = {athlete.last_strava_sync}")
        
        # Step 3: Reset to None
        print(f"\n🔄 Resetting last_strava_sync to None...")
        athlete.last_strava_sync = None
        db.commit()
        print(f"✓ Committed to database")
        
        # Step 4: Verify it's None
        db.refresh(athlete)
        print(f"\nAFTER RESET (in same session):")
        print(f"  last_strava_sync = {athlete.last_strava_sync}")
        print(f"  is None? {athlete.last_strava_sync is None}")
        
        # Step 5: Run sync (this should see None and fetch all activities)
        print(f"\n🚀 Running strava_sync()...")
        print("-" * 60)
        result = strava_sync(db=db)
        print("-" * 60)
        
        # Step 6: Show results
        print(f"\n✅ SYNC COMPLETE!")
        print(f"  New activities synced: {result.get('synced_new', 0)}")
        print(f"  Existing activities updated: {result.get('updated_existing', 0)}")
        print(f"  Splits backfilled: {result.get('splits_backfilled', 0)}")
        
        # Check if we got activities
        if result.get('synced_new', 0) > 0 or result.get('updated_existing', 0) > 0:
            print(f"\n🎉 SUCCESS! The fix is working - activities were fetched!")
            return True
        else:
            print(f"\n⚠️  WARNING: No activities were synced. Check the debug output above.")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = test_sync()
    sys.exit(0 if success else 1)

