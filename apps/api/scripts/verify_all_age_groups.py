"""
Comprehensive verification of ALL age groups against official WMA standards.
Tests M35 through M100 for 5K male.
"""

import sys
sys.path.insert(0, '/app')

from services.wma_age_factors import (
    get_wma_age_factor,
    get_wma_open_standard_seconds,
    _get_age_group_start,
)

# Official WMA 2023 road running factors for 5K Male
# Source: runningagegrading.com / Alan Jones 2025 tables
# These are PERFORMANCE FACTORS (what % of open standard you retain)
OFFICIAL_WMA_FACTORS_5K_MALE = {
    35: 0.9891,  # M35
    40: 0.9634,  # M40
    45: 0.9234,  # M45
    50: 0.8741,  # M50
    55: 0.8425,  # M55 (verified)
    60: 0.8077,  # M60
    65: 0.7675,  # M65
    70: 0.7220,  # M70
    75: 0.6711,  # M75
    80: 0.6158,  # M80
    85: 0.5574,  # M85
    90: 0.4980,  # M90
    95: 0.4392,  # M95
    100: 0.3818, # M100
}

print("=" * 70)
print("COMPREHENSIVE AGE GROUP VERIFICATION")
print("Testing ALL age groups M35-M100 for 5K Male")
print("=" * 70)
print()

all_passed = True
failures = []

print(f"{'Age Group':<12} {'Our Factor':<12} {'WMA Factor':<12} {'Expected':<12} {'Diff':<10} {'Status'}")
print("-" * 70)

for group_start, expected_wma in OFFICIAL_WMA_FACTORS_5K_MALE.items():
    # Get our factor (time multiplier)
    our_factor = get_wma_age_factor(group_start, 'M', 5000)
    
    # Convert to WMA performance factor for comparison
    our_wma = 1.0 / our_factor if our_factor else 0
    
    # Calculate difference
    diff = abs(our_wma - expected_wma)
    
    # Check if within tolerance (0.5%)
    passed = diff < 0.005
    status = "PASS" if passed else "FAIL"
    
    if not passed:
        all_passed = False
        failures.append((group_start, our_wma, expected_wma))
    
    print(f"M{group_start:<11} {our_factor:<12.4f} {our_wma:<12.4f} {expected_wma:<12.4f} {diff:<10.4f} {status}")

print()
print("=" * 70)
print("TESTING AGES WITHIN EACH GROUP")
print("Verifying all ages in a group get the same factor")
print("=" * 70)
print()

group_consistency_passed = True

for group_start in [35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95]:
    group_end = group_start + 4
    base_factor = get_wma_age_factor(group_start, 'M', 5000)
    
    all_same = True
    for age in range(group_start, group_end + 1):
        factor = get_wma_age_factor(age, 'M', 5000)
        if factor != base_factor:
            all_same = False
            group_consistency_passed = False
            print(f"  FAIL: Age {age} has factor {factor}, expected {base_factor} (M{group_start} group)")
    
    if all_same:
        print(f"M{group_start}: Ages {group_start}-{group_end} all use factor {base_factor:.4f} - PASS")

print()
print("=" * 70)
print("EDGE CASE TESTING")
print("=" * 70)
print()

# Test ages at boundaries
boundary_tests = [
    (34, 30, "Age 34 should use M30 (open standard)"),
    (35, 35, "Age 35 should use M35"),
    (39, 35, "Age 39 should use M35"),
    (40, 40, "Age 40 should use M40"),
    (99, 95, "Age 99 should use M95"),
    (100, 100, "Age 100 should use M100"),
    (105, 100, "Age 105 should use M100 (capped)"),
]

for age, expected_group, description in boundary_tests:
    actual_group = _get_age_group_start(age)
    passed = actual_group == expected_group
    status = "PASS" if passed else "FAIL"
    if not passed:
        all_passed = False
    print(f"{description}: {status} (got group {actual_group})")

print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)

if all_passed and group_consistency_passed:
    print("ALL TESTS PASSED!")
else:
    print("SOME TESTS FAILED!")
    if failures:
        print()
        print("Factor mismatches:")
        for group, got, expected in failures:
            print(f"  M{group}: got {got:.4f}, expected {expected:.4f}")
