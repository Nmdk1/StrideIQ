"""Verify female age 81 factor using the implementation."""

import sys
sys.path.insert(0, '/app')

from services.wma_age_factors import WMA_5K_FEMALE, get_wma_age_factor, get_wma_open_standard_seconds

print("=" * 70)
print("VERIFYING FEMALE AGE 81 5K FACTOR")
print("=" * 70)
print()

age = 81
sex = 'F'
distance = 5000
time_seconds = 31 * 60 + 25  # 31:25

time_mult = get_wma_age_factor(age, sex, distance)
wma_factor = 1 / time_mult
open_std = get_wma_open_standard_seconds(sex, distance)
age_std = open_std * time_mult
pct = (age_std / time_seconds) * 100

print(f"Our Implementation:")
print(f"  WMA_5K_FEMALE[81] = {WMA_5K_FEMALE.get(81)}")
print(f"  Time Multiplier: {time_mult:.4f}")
print(f"  WMA Factor: {wma_factor:.4f}")
print(f"  Open Standard: {open_std:.0f}s = {int(open_std//60)}:{int(open_std%60):02d}")
print(f"  Age Standard: {age_std:.1f}s = {int(age_std//60)}:{age_std%60:.1f}")
print(f"  Performance: {pct:.2f}%")
print()

print("Official Calculator:")
print("  WMA Factor: 0.5515")
print("  Time Multiplier: 1.8132")
print("  Open Standard: 13:54")
print("  Age Standard: 25:12.2")
print("  Performance: 80.22%")
print()

if abs(pct - 80.22) < 0.5:
    print("RESULT: PASS ✓")
else:
    print(f"RESULT: FAIL (diff: {abs(pct - 80.22):.2f}%)")
