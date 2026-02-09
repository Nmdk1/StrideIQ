#!/usr/bin/env python3
"""
Find closest integer RPI for pace lookup.

When RPI calculation gives non-integer values (e.g., 49.8, 56.3),
we should use the closest integer RPI for pace lookup to ensure
we're using exact reference values rather than interpolating.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.rpi_lookup import calculate_rpi_from_race_time_lookup, get_training_paces_from_rpi

def find_closest_integer_rpi(rpi: float) -> int:
    """Find closest integer RPI value."""
    return int(round(rpi))

def test_with_closest_rpi():
    """Test using closest integer RPI for pace lookup."""
    print("=" * 60)
    print("TESTING WITH CLOSEST INTEGER RPI")
    print("=" * 60)
    
    test_cases = [
        {"distance_m": 5000, "time_s": 1200, "desc": "5K in 20:00", "expected_rpi": 50.0},
        {"distance_m": 5000, "time_s": 1080, "desc": "5K in 18:00", "expected_rpi": 55.0},
    ]
    
    for test in test_cases:
        print(f"\n{test['desc']}:")
        calculated_rpi = calculate_rpi_from_race_time_lookup(
            test["distance_m"], 
            test["time_s"]
        )
        closest_rpi = find_closest_integer_rpi(calculated_rpi)
        
        print(f"  Calculated RPI: {calculated_rpi}")
        print(f"  Closest integer: {closest_rpi}")
        print(f"  Expected: ~{test['expected_rpi']}")
        
        # Get paces using closest integer
        paces = get_training_paces_from_rpi(float(closest_rpi))
        if paces:
            print(f"  Training paces (using RPI {closest_rpi}):")
            print(f"    E: {paces.get('e_pace')}")
            print(f"    M: {paces.get('m_pace')}")
            print(f"    T: {paces.get('t_pace')}")
            print(f"    I: {paces.get('i_pace')}")
            print(f"    R: {paces.get('r_pace')}")

if __name__ == "__main__":
    test_with_closest_rpi()

