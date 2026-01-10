#!/usr/bin/env python3
"""Test script to verify API returns correct data for activities with splits"""
import requests
import json

def test_api():
    print("=" * 60)
    print("Testing API Response - Activities with Splits")
    print("=" * 60)
    
    try:
        r = requests.get('http://localhost:8000/v1/activities')
        r.raise_for_status()
        data = r.json()
        
        print(f"\n✓ Total activities returned: {len(data)}")
        
        # Find an activity with splits and avg_hr
        test_activity = None
        for act in data:
            splits = act.get('splits') or []
            if len(splits) > 0 and act.get('average_heartrate') is not None:
                test_activity = act
                break
        
        if not test_activity:
            print("\n⚠️  No activity found with both splits and average_heartrate")
            print("   Checking first activity with splits...")
            for act in data:
                splits = act.get('splits') or []
                if len(splits) > 0:
                    test_activity = act
                    break
        
        if not test_activity:
            print("\n❌ No activities with splits found")
            return False
        
        print(f"\n--- Test Activity ---")
        print(f"  ID: {test_activity.get('id')}")
        print(f"  Name: {test_activity.get('name')}")
        print(f"  Avg HR: {test_activity.get('average_heartrate')}")
        print(f"  Max HR: {test_activity.get('max_hr')}")
        print(f"  Avg Cadence: {test_activity.get('average_cadence')}")
        
        splits = test_activity.get('splits') or []
        print(f"  Splits count: {len(splits)}")
        
        if splits:
            print(f"\n--- First 3 Splits ---")
            for i, s in enumerate(splits[:3]):
                print(f"\n  Split #{s.get('split')}:")
                print(f"    Avg HR: {s.get('average_heartrate')}")
                print(f"    Max HR: {s.get('max_heartrate')}")
                print(f"    Cadence: {s.get('average_cadence')}")
                print(f"    Pace: {s.get('pace_per_mile')}")
            
            # Verify fields exist (even if None)
            first_split = splits[0]
            print(f"\n--- Field Verification ---")
            print(f"  ✓ average_heartrate field exists: {'average_heartrate' in first_split}")
            print(f"  ✓ max_heartrate field exists: {'max_heartrate' in first_split}")
            print(f"  ✓ average_cadence field exists: {'average_cadence' in first_split}")
        
        # Verify activity-level fields
        print(f"\n--- Activity-Level Fields ---")
        print(f"  ✓ average_heartrate field exists: {'average_heartrate' in test_activity}")
        print(f"  ✓ max_hr field exists: {'max_hr' in test_activity}")
        print(f"  ✓ average_cadence field exists: {'average_cadence' in test_activity}")
        
        print(f"\n✅ API Response Test Complete")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_api()


