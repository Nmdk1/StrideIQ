"""Verify female age 81 factor against official."""

import sys
sys.path.insert(0, '/app')

import pandas as pd

female_file = '/app/data/FemaleRoadStd2025.xlsx'

print("=" * 70)
print("VERIFYING FEMALE AGE 81 5K FACTOR")
print("=" * 70)
print()

# Read the file
xl = pd.ExcelFile(female_file)
print(f"Available sheets: {xl.sheet_names}")

# Find the Age Factors sheet (note: female file has typo "Facctors")
sheet_name = xl.sheet_names[0]  # Default to first sheet
for sheet in xl.sheet_names:
    if 'Fac' in sheet:  # Match both "Factor" and "Facctor"
        sheet_name = sheet
        break

print(f"Using sheet: {sheet_name}")
df = pd.read_excel(female_file, sheet_name=sheet_name, header=None)

# Get distances from row 1
distances_row = df.iloc[1].tolist()
print(f"Distances: {distances_row}")
print()

# Find 5K column
col_5k = None
for i, d in enumerate(distances_row):
    if d == '5 km':
        col_5k = i
        break

print(f"5K column index: {col_5k}")

# Get open class standard (row 3)
oc_row = df.iloc[3].tolist()
print(f"5K Open Standard: {oc_row[col_5k]} seconds")
print()

# Get factor data
data = df.iloc[4:].reset_index(drop=True)
ages = data.iloc[:, 0].tolist()

# Find age 81
for i, age in enumerate(ages):
    if age == 81:
        factor_5k = data.iloc[i, col_5k]
        time_mult = 1 / float(factor_5k)
        print(f"Age 81 Female 5K:")
        print(f"  WMA Factor (from file): {float(factor_5k):.4f}")
        print(f"  Time Multiplier (1/factor): {time_mult:.4f}")
        print()
        
        # Calculate for 31:25 = 1885 seconds
        time_seconds = 31 * 60 + 25
        open_std = float(oc_row[col_5k])
        age_std = open_std * time_mult
        pct = (age_std / time_seconds) * 100
        
        print(f"Calculation for 31:25 5K:")
        print(f"  Open Standard: {open_std:.0f}s = {int(open_std//60)}:{int(open_std%60):02d}")
        print(f"  Age Standard: {age_std:.1f}s = {int(age_std//60)}:{age_std%60:.1f}")
        print(f"  Performance: {pct:.2f}%")
        print()
        
        print("Official Calculator:")
        print("  WMA Factor: 0.5515")
        print("  Time Multiplier: 1.8132")
        print("  Age Standard: 25:12.2")
        print("  Performance: 80.22%")
        print()
        
        print(f"Difference:")
        print(f"  WMA Factor: {float(factor_5k):.4f} vs 0.5515 (diff: {abs(float(factor_5k) - 0.5515):.4f})")
        print(f"  Time Mult: {time_mult:.4f} vs 1.8132 (diff: {abs(time_mult - 1.8132):.4f})")
        break

# Also check what's in the current factors file
print()
print("=" * 70)
print("CHECKING CURRENT IMPLEMENTATION")
print("=" * 70)
print()

from services.wma_age_factors import WMA_5K_FEMALE, get_wma_age_factor

print(f"WMA_5K_FEMALE[81] = {WMA_5K_FEMALE.get(81)}")
print(f"get_wma_age_factor(81, 'F', 5000) = {get_wma_age_factor(81, 'F', 5000)}")
