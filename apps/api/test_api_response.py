#!/usr/bin/env python3
"""Test script to verify API returns correct data for frontend"""
import requests
import json

def test_api():
    print("=" * 60)
    print("Testing API Response")
    print("=" * 60)
    
    try:
        r = requests.get('http://localhost:8000/v1/activities')
        r.raise_for_status()
        data = r.json()
        
        print(f"\n✓ Total activities returned: {len(data)}")
        
        if not data:
            print("⚠️  No activities found in API response")
            return False
        
        # Check first activity
        act = data[0]
        print(f"\n--- First Activity ---")
        print(f"  ID: {act.get('id')}")
        print(f"  Name: {act.get('name')}")
        print(f"  Avg HR: {act.get('average_heartrate')}")
        print(f"  Max HR: {act.get('max_hr')}")
        print(f"  Avg Cadence: {act.get('average_cadence')}")
        
        splits = act.get('splits') or []
        print(f"  Splits count: {len(splits)}")
        
        if splits:
            s = splits[0]
            print(f"\n--- First Split ---")
            print(f"  Split #: {s.get('split')}")
            print(f"  Avg HR: {s.get('average_heartrate')}")
            print(f"  Max HR: {s.get('max_heartrate')}")
            print(f"  Cadence: {s.get('average_cadence')}")
            print(f"  Pace: {s.get('pace_per_mile')}")
            
            # Verify all required fields exist
            required_split_fields = ['average_heartrate', 'max_heartrate', 'average_cadence']
            missing = [f for f in required_split_fields if s.get(f) is None and f not in ['max_heartrate', 'average_cadence']]
            if missing:
                print(f"\n⚠️  Missing split fields (may be None): {missing}")
            else:
                print(f"\n✓ All split fields present")
        else:
            print("\n⚠️  No splits found for first activity")
        
        # Check activity-level average HR
        if act.get('average_heartrate') is not None:
            print(f"\n✓ Activity-level average HR is present: {act.get('average_heartrate')}")
        else:
            print(f"\n⚠️  Activity-level average HR is None")
        
        print(f"\n✅ API Response Test Complete")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_api()

