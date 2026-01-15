"""Analyze the factor calculation problem."""

import sys
sys.path.insert(0, '/app')

from services.wma_age_factors import get_wma_age_factor

print("=" * 70)
print("FACTOR ANALYSIS")
print("=" * 70)

# The key question: Does official use 5-year groups or per-year?

# Evidence 1: User's age 57 test
# Age 57, 18:53 5K -> 80.65% (official matches our M55 group factor)
# This suggests 5-year groups for 55-59

# Evidence 2: User's age 79 test
# Age 79, 27:14 5K -> 74.3% (official)
# Our M75 group factor gives 70.20%
# Our interpolated factor gives 75.25%
# Neither matches!

print("Test Case 1: Age 57 (M55 group)")
print("-" * 40)
# If we use M55 factor (0.8425):
# Age standard = 769.8 * 1.187 = 913.8s
# Performance = 913.8 / 1133 * 100 = 80.65% ✓
print("Official: 80.65%")
print("Our M55 group factor gives: 80.65% ✓")
print()

print("Test Case 2: Age 79")
print("-" * 40)
# Official WMA factor for age 79 = 0.6334
# Time multiplier = 1/0.6334 = 1.5787
# Age standard = 769.8 * 1.5787 = 1215.5s = 20:15.5
# Performance = 1215.5 / 1634 * 100 = 74.38% ✓

official_wma_79 = 0.6334
official_time_mult_79 = 1 / official_wma_79
print(f"Official WMA factor for age 79: {official_wma_79}")
print(f"Official time multiplier: {official_time_mult_79:.4f}")

# What do we have for age 75 and 80?
our_wma_75 = 0.6711  # 1/1.4900
our_wma_80 = 0.6158  # 1/1.6240

print(f"Our WMA factor for age 75: {our_wma_75:.4f}")
print(f"Our WMA factor for age 80: {our_wma_80:.4f}")
print()

# Linear interpolation between our values
interp_wma_79 = our_wma_75 + (our_wma_80 - our_wma_75) * (79 - 75) / (80 - 75)
print(f"Linear interpolation for age 79: {interp_wma_79:.4f}")
print(f"Official age 79: 0.6334")
print(f"Difference: {abs(interp_wma_79 - 0.6334):.4f}")
print()

# The problem: Our milestone factors are WRONG
# We need to find the correct factors

print("=" * 70)
print("SOLUTION: Calculate correct milestone factors")
print("=" * 70)
print()

# From official data, we can derive:
# Age 55: WMA = 0.8425 ✓ (verified)
# Age 79: WMA = 0.6334

# Let's assume the factors follow a specific curve
# We can use the known data points to calibrate

# For now, let's add more milestone values based on official data
print("We need to get actual per-year WMA factors from official tables.")
print("The Alan Jones 2025 tables have per-year factors.")
print()

# Calculate what factor at age 75 would give age 79 = 0.6334 with linear interp
# If WMA at 80 = 0.6158 (we assume this is correct)
# 0.6334 = WMA_75 + (0.6158 - WMA_75) * 0.8
# 0.6334 = WMA_75 + 0.8 * 0.6158 - 0.8 * WMA_75
# 0.6334 = WMA_75 * (1 - 0.8) + 0.4926
# 0.6334 = 0.2 * WMA_75 + 0.4926
# 0.2 * WMA_75 = 0.6334 - 0.4926 = 0.1408
# WMA_75 = 0.704

print("To get age 79 = 0.6334 with linear interpolation:")
wma_80 = 0.6158
# 0.6334 = wma_75 + (0.6158 - wma_75) * 0.8
# 0.6334 = 0.2 * wma_75 + 0.8 * 0.6158
# 0.6334 = 0.2 * wma_75 + 0.4926
needed_wma_75 = (0.6334 - 0.8 * wma_80) / 0.2
print(f"WMA at age 75 would need to be: {needed_wma_75:.4f}")
print(f"But we have: {our_wma_75:.4f}")
print(f"And official age 75 factor is likely: 0.6711 (matches our value)")
print()

print("CONCLUSION: The official calculator does NOT use simple linear interpolation.")
print("It likely uses actual per-year factors from WMA tables.")
print()
print("We need to add per-year factors (not just 5-year milestones)")
print("OR use a polynomial curve that matches WMA methodology.")
