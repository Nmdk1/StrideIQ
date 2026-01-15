"""Verify age 79 calculation against official calculator."""

import sys
sys.path.insert(0, '/app')

from services.wma_age_factors import (
    get_wma_age_factor,
    get_wma_open_standard_seconds,
)

print("=" * 70)
print("VERIFICATION: 79yo Male, 27:14 5K")
print("=" * 70)
print()

age = 79
sex = 'M'
distance = 5000
time_seconds = 27 * 60 + 14  # 27:14 = 1634 seconds

age_factor = get_wma_age_factor(age, sex, distance)
wma_factor = 1 / age_factor
open_standard = get_wma_open_standard_seconds(sex, distance)
age_standard = open_standard * age_factor
age_graded_time = time_seconds / age_factor
performance_pct = (age_standard / time_seconds) * 100

print("Our Results:")
print(f"  Age Factor (time mult): {age_factor:.4f}")
print(f"  WMA Factor (1/mult): {wma_factor:.4f}")
print(f"  Open Standard: {open_standard:.1f}s = {int(open_standard//60)}:{open_standard%60:.1f}")
print(f"  Age Standard: {age_standard:.1f}s = {int(age_standard//60)}:{age_standard%60:.1f}")
print(f"  Age-Graded Time: {age_graded_time:.1f}s = {int(age_graded_time//60)}:{age_graded_time%60:.1f}")
print(f"  Performance %: {performance_pct:.2f}%")
print()

print("Official Calculator Results:")
print("  WMA Factor: 0.6334")
print("  Open Standard: 12:49")
print("  Age Standard: 20:14.1")
print("  Age-Graded Time: 17:15")
print("  Performance %: 74.3%")
print()

# Check differences
official_factor = 0.6334
official_pct = 74.3

print("Differences:")
print(f"  WMA Factor: {wma_factor:.4f} vs 0.6334 (diff: {abs(wma_factor - 0.6334):.4f})")
print(f"  Performance: {performance_pct:.2f}% vs 74.3% (diff: {abs(performance_pct - 74.3):.2f}%)")
print()

if abs(performance_pct - 74.3) < 0.5:
    print("RESULT: PASS (within 0.5%)")
else:
    print(f"RESULT: FAIL (off by {abs(performance_pct - 74.3):.2f}%)")
