#!/usr/bin/env python3
"""Test VDOT lookup system accuracy."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.vdot_lookup import (
    calculate_vdot_from_race_time_lookup,
    get_training_paces_from_vdot,
    get_equivalent_race_times
)

def test_vdot_calculation():
    """Test VDOT calculation accuracy."""
    print("=" * 60)
    print("VDOT LOOKUP SYSTEM TEST")
    print("=" * 60)
    
    test_cases = [
        {"distance_m": 5000, "time_s": 1200, "expected_vdot": 50.0, "desc": "5K in 20:00"},
        {"distance_m": 10000, "time_s": 2400, "expected_vdot": 50.0, "desc": "10K in 40:00"},
        {"distance_m": 5000, "time_s": 1080, "expected_vdot": 55.0, "desc": "5K in 18:00"},
        {"distance_m": 5000, "time_s": 900, "expected_vdot": 60.0, "desc": "5K in 15:00"},
    ]
    
    print("\n📊 VDOT Calculation Tests:")
    print("-" * 60)
    
    for test in test_cases:
        calculated = calculate_vdot_from_race_time_lookup(
            test["distance_m"], 
            test["time_s"]
        )
        expected = test["expected_vdot"]
        diff = abs(calculated - expected) if calculated else None
        
        status = "✅" if diff and diff < 2 else "⚠️" if diff and diff < 5 else "❌"
        
        print(f"\n{test['desc']}:")
        print(f"  Expected VDOT: ~{expected}")
        print(f"  Calculated: {calculated}")
        if diff:
            print(f"  Difference: {diff:.1f} {status}")
        
        # Get training paces
        if calculated:
            paces = get_training_paces_from_vdot(calculated)
            if paces:
                print(f"  E pace: {paces.get('e_pace')}")
                print(f"  M pace: {paces.get('m_pace')}")
                print(f"  T pace: {paces.get('t_pace')}")
    
    print("\n" + "=" * 60)
    print("✅ Testing complete")

if __name__ == "__main__":
    test_vdot_calculation()

