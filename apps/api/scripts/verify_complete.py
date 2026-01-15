"""
Complete verification of WMA age-grading implementation.
Tests all age groups, distances, and sexes.
"""

import sys
sys.path.insert(0, '/app')

from services.wma_age_factors import (
    get_wma_age_factor,
    get_wma_open_standard_seconds,
)

print("=" * 70)
print("COMPLETE WMA AGE-GRADING VERIFICATION")
print("=" * 70)
print()

all_passed = True

# ============================================================================
# Test 1: All male age groups for 5K
# ============================================================================
print("TEST 1: Male 5K Age Factors (M35-M100)")
print("-" * 50)

EXPECTED_5K_MALE = {
    35: 1.0110, 40: 1.0380, 45: 1.0830, 50: 1.1440,
    55: 1.1870, 60: 1.2380, 65: 1.3030, 70: 1.3850,
    75: 1.4900, 80: 1.6240, 85: 1.7940, 90: 2.0080,
    95: 2.2770, 100: 2.6190
}

for group, expected in EXPECTED_5K_MALE.items():
    actual = get_wma_age_factor(group, 'M', 5000)
    passed = abs(actual - expected) < 0.001
    status = "PASS" if passed else "FAIL"
    if not passed:
        all_passed = False
    print(f"  M{group}: {actual:.4f} (expected {expected:.4f}) - {status}")

print()

# ============================================================================
# Test 2: All male age groups for 10K
# ============================================================================
print("TEST 2: Male 10K Age Factors (M35-M100)")
print("-" * 50)

EXPECTED_10K_MALE = {
    35: 1.0150, 40: 1.0450, 45: 1.0900, 50: 1.1500,
    55: 1.1950, 60: 1.2500, 65: 1.3200, 70: 1.4050,
    75: 1.5150, 80: 1.6550, 85: 1.8300, 90: 2.0500,
    95: 2.3300, 100: 2.6800
}

for group, expected in EXPECTED_10K_MALE.items():
    actual = get_wma_age_factor(group, 'M', 10000)
    passed = abs(actual - expected) < 0.001
    status = "PASS" if passed else "FAIL"
    if not passed:
        all_passed = False
    print(f"  M{group}: {actual:.4f} (expected {expected:.4f}) - {status}")

print()

# ============================================================================
# Test 3: Open Standards
# ============================================================================
print("TEST 3: Open Standards (Male)")
print("-" * 50)

EXPECTED_STANDARDS = [
    ('5K', 5000, 769.8),      # 12:49.8
    ('10K', 10000, 1571.0),   # 26:11.0
    ('Half', 21097.5, 3451.0), # 57:31
    ('Marathon', 42195, 7377.0), # 2:02:57
]

for name, meters, expected_seconds in EXPECTED_STANDARDS:
    actual = get_wma_open_standard_seconds('M', meters)
    passed = abs(actual - expected_seconds) < 1.0
    status = "PASS" if passed else "FAIL"
    if not passed:
        all_passed = False
    
    actual_formatted = f"{int(actual // 60)}:{int(actual % 60):02d}"
    expected_formatted = f"{int(expected_seconds // 60)}:{int(expected_seconds % 60):02d}"
    print(f"  {name}: {actual_formatted} (expected {expected_formatted}) - {status}")

print()

# ============================================================================
# Test 4: Female factors (should be higher than male)
# ============================================================================
print("TEST 4: Female vs Male Factors (sanity check)")
print("-" * 50)

for age in [40, 55, 70]:
    male_factor = get_wma_age_factor(age, 'M', 5000)
    female_factor = get_wma_age_factor(age, 'F', 5000)
    passed = female_factor > male_factor
    status = "PASS" if passed else "FAIL"
    if not passed:
        all_passed = False
    print(f"  Age {age}: M={male_factor:.4f}, F={female_factor:.4f}, F>M: {status}")

print()

# ============================================================================
# Test 5: Age group consistency
# ============================================================================
print("TEST 5: Age Group Consistency")
print("-" * 50)

for group_start in [35, 50, 55, 70, 85, 95]:
    base_factor = get_wma_age_factor(group_start, 'M', 5000)
    all_same = True
    for age in range(group_start, min(group_start + 5, 101)):
        if get_wma_age_factor(age, 'M', 5000) != base_factor:
            all_same = False
    status = "PASS" if all_same else "FAIL"
    if not all_same:
        all_passed = False
    print(f"  M{group_start}: All ages use same factor - {status}")

print()

# ============================================================================
# Test 6: Real calculation verification (the user's case)
# ============================================================================
print("TEST 6: Real Calculation Verification (Official Calculator Match)")
print("-" * 50)

# User's case: 57yo male, 18:53 5K
age = 57
sex = 'M'
distance = 5000
time_seconds = 1133  # 18:53

age_factor = get_wma_age_factor(age, sex, distance)
open_standard = get_wma_open_standard_seconds(sex, distance)
age_standard = open_standard * age_factor
age_graded_time = time_seconds / age_factor
performance_pct = (age_standard / time_seconds) * 100

print(f"  Input: {age}yo {sex}, 18:53 5K")
print(f"  Age Factor: {age_factor:.4f} (expected: 1.1870)")
print(f"  Open Standard: {open_standard:.1f}s = {int(open_standard//60)}:{open_standard%60:.1f}")
print(f"  Age Standard: {age_standard:.1f}s = {int(age_standard//60)}:{age_standard%60:.1f}")
print(f"  Age-Graded Time: {age_graded_time:.1f}s = {int(age_graded_time//60)}:{age_graded_time%60:.1f}")
print(f"  Performance %: {performance_pct:.2f}% (expected: 80.65%)")

pct_passed = abs(performance_pct - 80.65) < 0.1
print(f"  Match official calculator: {'PASS' if pct_passed else 'FAIL'}")
if not pct_passed:
    all_passed = False

print()
print("=" * 70)
print("FINAL RESULT:", "ALL TESTS PASSED!" if all_passed else "SOME TESTS FAILED!")
print("=" * 70)
