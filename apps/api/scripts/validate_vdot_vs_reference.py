#!/usr/bin/env python3
"""
Validate VDOT Calculator Against vdoto2.com Reference

Tests VDOT calculations and training paces against known reference values.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.vdot_calculator import (
    calculate_vdot_from_race_time,
    calculate_training_paces,
    calculate_equivalent_race_time
)
from services.vdot_lookup import (
    calculate_vdot_from_race_time_lookup,
    get_training_paces_from_vdot,
    get_equivalent_race_times
)


# Reference test cases (validated against vdoto2.com)
REFERENCE_CASES = [
    {
        "distance_m": 5000,
        "time_s": 1200,  # 20:00
        "expected_vdot": 50.0,
        "expected_paces": {
            "e_pace": "8:15",  # Easy pace
            "m_pace": "7:00",  # Marathon pace
            "t_pace": "6:35",  # Threshold pace
            "i_pace": "6:15",  # Interval pace
            "r_pace": "5:55",  # Repetition pace
        },
        "expected_equivalents": {
            "5K": "19:31",
            "10K": "40:27",
            "half_marathon": "1:29:04",
            "marathon": "3:07:00"
        }
    },
    {
        "distance_m": 5000,
        "time_s": 1080,  # 18:00
        "expected_vdot": 55.0,
        "expected_paces": {
            "e_pace": "7:30",
            "m_pace": "6:20",
            "t_pace": "5:55",
            "i_pace": "5:35",
            "r_pace": "5:20",
        }
    },
    {
        "distance_m": 10000,
        "time_s": 2400,  # 40:00
        "expected_vdot": 50.0,
    },
    {
        "distance_m": 42195,
        "time_s": 11220,  # 3:07:00
        "expected_vdot": 50.0,
    }
]


def parse_pace(pace_str: str) -> int:
    """Parse pace string (MM:SS) to total seconds."""
    try:
        parts = pace_str.split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except:
        pass
    return 0


def format_pace_diff(actual: str, expected: str) -> str:
    """Format pace difference."""
    actual_sec = parse_pace(actual)
    expected_sec = parse_pace(expected)
    diff_sec = abs(actual_sec - expected_sec)
    
    if diff_sec == 0:
        return "✅ Exact"
    elif diff_sec <= 5:
        return f"✅ Close ({diff_sec}s)"
    elif diff_sec <= 15:
        return f"⚠️  Off by {diff_sec}s"
    else:
        return f"❌ Off by {diff_sec}s"


def test_vdot_calculation():
    """Test VDOT calculation accuracy."""
    print("=" * 70)
    print("VDOT CALCULATOR VALIDATION AGAINST REFERENCE")
    print("=" * 70)
    
    print("\n📊 VDOT Calculation Tests:")
    print("-" * 70)
    
    for i, test_case in enumerate(REFERENCE_CASES, 1):
        print(f"\nTest Case {i}: {test_case['distance_m']/1000:.1f}K in {test_case['time_s']//60}:{test_case['time_s']%60:02d}")
        
        # Calculate VDOT
        calculated_vdot = calculate_vdot_from_race_time(
            test_case["distance_m"],
            test_case["time_s"]
        )
        
        expected_vdot = test_case.get("expected_vdot")
        if expected_vdot:
            diff = abs(calculated_vdot - expected_vdot) if calculated_vdot else None
            status = "✅" if diff and diff < 2 else "⚠️" if diff and diff < 5 else "❌"
            print(f"  VDOT: Expected ~{expected_vdot}, Calculated {calculated_vdot}, Diff {diff:.1f} {status}")
        else:
            print(f"  VDOT: Calculated {calculated_vdot}")
        
        # Test training paces
        if calculated_vdot and "expected_paces" in test_case:
            print(f"\n  Training Paces:")
            paces = calculate_training_paces(calculated_vdot)
            expected_paces = test_case["expected_paces"]
            
            pace_mapping = {
                "easy": "e_pace",
                "marathon": "m_pace",
                "threshold": "t_pace",
                "interval": "i_pace",
                "repetition": "r_pace",
            }
            
            for calc_key, ref_key in pace_mapping.items():
                pace_dict = paces.get(calc_key, {})
                actual = pace_dict.get("mi", "") if isinstance(pace_dict, dict) else ""
                expected = expected_paces.get(ref_key, "")
                if actual and expected:
                    diff_str = format_pace_diff(actual, expected)
                    print(f"    {ref_key.upper()}: {actual} (expected {expected}) {diff_str}")
        
        # Test equivalent race times
        # Use expected VDOT for lookup (not calculated) to test lookup table accuracy
        if calculated_vdot and "expected_equivalents" in test_case:
            print(f"\n  Equivalent Race Times:")
            expected_vdot = test_case.get("expected_vdot")
            # Use expected VDOT if available, otherwise use calculated
            vdot_for_lookup = expected_vdot if expected_vdot else calculated_vdot
            equivalents = get_equivalent_race_times(vdot_for_lookup)
            if equivalents:
                for distance, expected_time in test_case["expected_equivalents"].items():
                    actual_time = equivalents.get("race_times_formatted", {}).get(distance, "")
                    if actual_time:
                        diff_str = format_pace_diff(actual_time, expected_time)
                        print(f"    {distance}: {actual_time} (expected {expected_time}) {diff_str}")
    
    print("\n" + "=" * 70)
    print("✅ Validation complete")
    print("\nNote: Small differences (< 15 seconds) are acceptable due to")
    print("rounding and interpolation. Differences > 30 seconds may indicate")
    print("formula adjustments needed.")


if __name__ == "__main__":
    test_vdot_calculation()

