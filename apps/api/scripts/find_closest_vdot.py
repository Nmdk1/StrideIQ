#!/usr/bin/env python3
"""
Find closest integer VDOT for pace lookup.

When VDOT calculation gives non-integer values (e.g., 49.8, 56.3),
we should use the closest integer VDOT for pace lookup to ensure
we're using exact reference values rather than interpolating.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.vdot_lookup import calculate_vdot_from_race_time_lookup, get_training_paces_from_vdot

def find_closest_integer_vdot(vdot: float) -> int:
    """Find closest integer VDOT value."""
    return int(round(vdot))

def test_with_closest_vdot():
    """Test using closest integer VDOT for pace lookup."""
    print("=" * 60)
    print("TESTING WITH CLOSEST INTEGER VDOT")
    print("=" * 60)
    
    test_cases = [
        {"distance_m": 5000, "time_s": 1200, "desc": "5K in 20:00", "expected_vdot": 50.0},
        {"distance_m": 5000, "time_s": 1080, "desc": "5K in 18:00", "expected_vdot": 55.0},
    ]
    
    for test in test_cases:
        print(f"\n{test['desc']}:")
        calculated_vdot = calculate_vdot_from_race_time_lookup(
            test["distance_m"], 
            test["time_s"]
        )
        closest_vdot = find_closest_integer_vdot(calculated_vdot)
        
        print(f"  Calculated VDOT: {calculated_vdot}")
        print(f"  Closest integer: {closest_vdot}")
        print(f"  Expected: ~{test['expected_vdot']}")
        
        # Get paces using closest integer
        paces = get_training_paces_from_vdot(float(closest_vdot))
        if paces:
            print(f"  Training paces (using VDOT {closest_vdot}):")
            print(f"    E: {paces.get('e_pace')}")
            print(f"    M: {paces.get('m_pace')}")
            print(f"    T: {paces.get('t_pace')}")
            print(f"    I: {paces.get('i_pace')}")
            print(f"    R: {paces.get('r_pace')}")

if __name__ == "__main__":
    test_with_closest_vdot()

