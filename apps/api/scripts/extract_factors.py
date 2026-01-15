"""Extract official age factors from Alan Jones 2025 tables."""

import sys
sys.path.insert(0, '/app')

import pandas as pd

# Read the Excel files
male_file = '/app/data/MaleRoadStd2025.xlsx'

print("=" * 70)
print("EXTRACTING OFFICIAL ALAN JONES 2025 AGE FACTORS")
print("=" * 70)
print()

# Read the Age Factors sheet
df = pd.read_excel(male_file, sheet_name='Age Factors', header=None)

# Get column names from row 1
distances_row = df.iloc[1].tolist()
print("Distance columns:", distances_row)

# Find column indices for key distances
col_5k = distances_row.index('5 km') if '5 km' in distances_row else 2
col_10k = distances_row.index('10 km') if '10 km' in distances_row else 7
col_hm = distances_row.index('H. Mar') if 'H. Mar' in distances_row else 13
col_marathon = distances_row.index('Marathon') if 'Marathon' in distances_row else 16

print(f"Column indices: 5K={col_5k}, 10K={col_10k}, HM={col_hm}, M={col_marathon}")
print()

# Get open class standards (row 3)
oc_row = df.iloc[3].tolist()
print(f"Open class standards (seconds):")
print(f"  5K: {oc_row[col_5k]} seconds")
print(f"  10K: {oc_row[col_10k]} seconds")
print(f"  HM: {oc_row[col_hm]} seconds")
print(f"  Marathon: {oc_row[col_marathon]} seconds")
print()

# Get factor data - skip first 4 rows (headers)
data = df.iloc[4:].reset_index(drop=True)
ages = data.iloc[:, 0].tolist()

# Extract factors for ages 30-100
print("=" * 70)
print("PYTHON CODE FOR FACTORS")
print("=" * 70)
print()

# 5K factors
print("# 5K Male Time Multipliers")
print("ALAN_JONES_5K_MALE = {")
for i, age in enumerate(ages):
    if age is not None and isinstance(age, (int, float)) and 5 <= age <= 100:
        factor = data.iloc[i, col_5k]
        if factor is not None and not pd.isna(factor):
            time_mult = 1 / float(factor)
            print(f"    {int(age)}: {time_mult:.4f},")
print("}")
print()

# 10K factors
print("# 10K Male Time Multipliers")
print("ALAN_JONES_10K_MALE = {")
for i, age in enumerate(ages):
    if age is not None and isinstance(age, (int, float)) and 5 <= age <= 100:
        factor = data.iloc[i, col_10k]
        if factor is not None and not pd.isna(factor):
            time_mult = 1 / float(factor)
            print(f"    {int(age)}: {time_mult:.4f},")
print("}")
print()

# Half Marathon factors
print("# Half Marathon Male Time Multipliers")
print("ALAN_JONES_HALF_MALE = {")
for i, age in enumerate(ages):
    if age is not None and isinstance(age, (int, float)) and 5 <= age <= 100:
        factor = data.iloc[i, col_hm]
        if factor is not None and not pd.isna(factor):
            time_mult = 1 / float(factor)
            print(f"    {int(age)}: {time_mult:.4f},")
print("}")
print()

# Marathon factors
print("# Marathon Male Time Multipliers")
print("ALAN_JONES_MARATHON_MALE = {")
for i, age in enumerate(ages):
    if age is not None and isinstance(age, (int, float)) and 5 <= age <= 100:
        factor = data.iloc[i, col_marathon]
        if factor is not None and not pd.isna(factor):
            time_mult = 1 / float(factor)
            print(f"    {int(age)}: {time_mult:.4f},")
print("}")
print()

# Verification
print("=" * 70)
print("VERIFICATION")
print("=" * 70)
print()

# Test case 1: Age 55, 5K 18:53
for i, age in enumerate(ages):
    if age == 55:
        factor_5k = data.iloc[i, col_5k]
        time_mult = 1 / float(factor_5k)
        open_std = float(oc_row[col_5k])
        age_std = open_std * time_mult
        time_seconds = 18*60 + 53
        pct = (age_std / time_seconds) * 100
        print(f"Age 55, 5K 18:53:")
        print(f"  WMA factor: {float(factor_5k):.4f}")
        print(f"  Time mult: {time_mult:.4f}")
        print(f"  Open std: {open_std:.1f}s = {open_std/60:.1f} min")
        print(f"  Age std: {age_std:.1f}s = {age_std/60:.2f} min")
        print(f"  Performance: {pct:.2f}%")
        break

print()

# Test case 2: Age 79, 5K 27:14
for i, age in enumerate(ages):
    if age == 79:
        factor_5k = data.iloc[i, col_5k]
        time_mult = 1 / float(factor_5k)
        open_std = float(oc_row[col_5k])
        age_std = open_std * time_mult
        time_seconds = 27*60 + 14
        pct = (age_std / time_seconds) * 100
        print(f"Age 79, 5K 27:14:")
        print(f"  WMA factor: {float(factor_5k):.4f}")
        print(f"  Time mult: {time_mult:.4f}")
        print(f"  Open std: {open_std:.1f}s = {open_std/60:.1f} min")
        print(f"  Age std: {age_std:.1f}s = {age_std/60:.2f} min")
        print(f"  Performance: {pct:.2f}%")
        break
