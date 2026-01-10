#!/usr/bin/env python3
"""
Calibrate VDOT Formula Against Reference Values

Tests VDOT formula accuracy and adjusts if needed to match reference values.
"""
import sys
import math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.vdot_lookup import calculate_vdot_from_race_time_lookup

# Reference test cases: race time -> expected VDOT
REFERENCE_CASES = [
    {"distance_m": 5000, "time_s": 1200, "expected_vdot": 50.0},  # 5K in 20:00
    {"distance_m": 5000, "time_s": 1080, "expected_vdot": 55.0},  # 5K in 18:00
    {"distance_m": 10000, "time_s": 2400, "expected_vdot": 50.0},  # 10K in 40:00
    {"distance_m": 42195, "time_s": 11220, "expected_vdot": 50.0},  # Marathon in 3:07:00
]

def calculate_vdot_formula(distance_meters: float, time_seconds: int) -> float:
    """Calculate VDOT using the formula."""
    velocity_m_per_min = (distance_meters / time_seconds) * 60
    time_minutes = time_seconds / 60.0
    
    numerator = -4.60 + 0.182258 * velocity_m_per_min + 0.000104 * (velocity_m_per_min ** 2)
    exp1 = math.exp(-0.012778 * time_minutes)
    exp2 = math.exp(-0.1932605 * time_minutes)
    denominator = 0.8 + 0.1894393 * exp1 + 0.2989558 * exp2
    
    return numerator / denominator

def find_vdot_adjustment():
    """Find if VDOT formula needs adjustment."""
    print("=" * 60)
    print("VDOT FORMULA CALIBRATION")
    print("=" * 60)
    
    print("\nTesting VDOT formula accuracy:")
    print("-" * 60)
    
    adjustments = []
    
    for case in REFERENCE_CASES:
        calculated = calculate_vdot_formula(case["distance_m"], case["time_s"])
        expected = case["expected_vdot"]
        diff = calculated - expected
        adjustment_factor = expected / calculated if calculated > 0 else 1.0
        
        print(f"\n{case['distance_m']/1000:.1f}K in {case['time_s']//60}:{case['time_s']%60:02d}:")
        print(f"  Expected VDOT: {expected}")
        print(f"  Calculated: {calculated:.2f}")
        print(f"  Difference: {diff:+.2f}")
        print(f"  Adjustment factor: {adjustment_factor:.4f}")
        
        adjustments.append({
            "case": case,
            "calculated": calculated,
            "expected": expected,
            "diff": diff,
            "adjustment": adjustment_factor
        })
    
    # Calculate average adjustment
    avg_adjustment = sum(a["adjustment"] for a in adjustments) / len(adjustments)
    print(f"\n{'='*60}")
    print(f"Average adjustment factor: {avg_adjustment:.4f}")
    print(f"\nNote: If adjustment factor is close to 1.0, formula is accurate.")
    print(f"If significantly different, may need formula correction.")

if __name__ == "__main__":
    find_vdot_adjustment()

