#!/usr/bin/env python3
"""
Validate RPI Calculator Against rpio2.com Reference

Tests RPI calculations and training paces against known reference values.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.rpi_calculator import (
    calculate_rpi_from_race_time,
    calculate_training_paces,
    calculate_equivalent_race_time
)
from services.rpi_lookup import (
    calculate_rpi_from_race_time_lookup,
    get_training_paces_from_rpi,
    get_equivalent_race_times
)


# Reference test cases (validated against rpio2.com)
REFERENCE_CASES = [
    {
        "distance_m": 5000,
        "time_s": 1200,  # 20:00
        "expected_rpi": 50.0,
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
        "expected_rpi": 55.0,
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
        "expected_rpi": 50.0,
    },
    {
        "distance_m": 42195,
        "time_s": 11220,  # 3:07:00
        "expected_rpi": 50.0,
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


def test_rpi_calculation():
    """Test RPI calculation accuracy."""
    print("=" * 70)
    print("RPI CALCULATOR VALIDATION AGAINST REFERENCE")
    print("=" * 70)
    
    print("\n📊 RPI Calculation Tests:")
    print("-" * 70)
    
    for i, test_case in enumerate(REFERENCE_CASES, 1):
        print(f"\nTest Case {i}: {test_case['distance_m']/1000:.1f}K in {test_case['time_s']//60}:{test_case['time_s']%60:02d}")
        
        # Calculate RPI
        calculated_rpi = calculate_rpi_from_race_time(
            test_case["distance_m"],
            test_case["time_s"]
        )
        
        expected_rpi = test_case.get("expected_rpi")
        if expected_rpi:
            diff = abs(calculated_rpi - expected_rpi) if calculated_rpi else None
            status = "✅" if diff and diff < 2 else "⚠️" if diff and diff < 5 else "❌"
            print(f"  RPI: Expected ~{expected_rpi}, Calculated {calculated_rpi}, Diff {diff:.1f} {status}")
        else:
            print(f"  RPI: Calculated {calculated_rpi}")
        
        # Test training paces
        if calculated_rpi and "expected_paces" in test_case:
            print(f"\n  Training Paces:")
            paces = calculate_training_paces(calculated_rpi)
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
        # Use expected RPI for lookup (not calculated) to test lookup table accuracy
        if calculated_rpi and "expected_equivalents" in test_case:
            print(f"\n  Equivalent Race Times:")
            expected_rpi = test_case.get("expected_rpi")
            # Use expected RPI if available, otherwise use calculated
            rpi_for_lookup = expected_rpi if expected_rpi else calculated_rpi
            equivalents = get_equivalent_race_times(rpi_for_lookup)
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
    test_rpi_calculation()

