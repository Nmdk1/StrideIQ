"""Extract CORRECT female factors from Alan Jones 2025 tables."""

import sys
sys.path.insert(0, '/app')

import pandas as pd

female_file = '/app/data/FemaleRoadStd2025.xlsx'

print("=" * 70)
print("EXTRACTING CORRECT FEMALE FACTORS")
print("=" * 70)
print()

xl = pd.ExcelFile(female_file)
sheet_name = 'Age Facctors'  # Note the typo in the file
df = pd.read_excel(female_file, sheet_name=sheet_name, header=None)

# Get distances from row 1
distances_row = df.iloc[1].tolist()
print(f"All columns: {distances_row}")
print()

# Map our desired distances - accounting for double "Age" column
# Columns: Age, Age, 1 Mile, 5 km, 6 km, 4 Mile, 8 km, 5 Mile, 10 km, ...
distance_mapping = {
    '1_MILE': ('1 Mile', 2),      # Column index 2
    '5K': ('5 km', 3),            # Column index 3
    '8K': ('8 km', 6),            # Column index 6
    '10K': ('10 km', 8),          # Column index 8
    '10_MILE': ('10 Mile', 12),   # Column index 12
    'HALF_MARATHON': ('H. Mar', 14),  # Column index 14
    'MARATHON': ('Marathon', 17),     # Column index 17
}

# Get open class standards (row 3)
oc_row = df.iloc[3].tolist()

# Get factor data - skip first 4 rows (headers)
data = df.iloc[4:].reset_index(drop=True)
ages = data.iloc[:, 0].tolist()

print("Verifying column indices:")
for our_name, (file_name, col_idx) in distance_mapping.items():
    actual = distances_row[col_idx]
    print(f"  {our_name}: column {col_idx} = '{actual}' (expected '{file_name}')")
print()

# Extract and print factors for each distance
for our_name, (file_name, col_idx) in distance_mapping.items():
    print(f"# {our_name} Female - Alan Jones 2025")
    print(f"WMA_{our_name}_FEMALE: Dict[int, float] = {{")
    
    line = "    "
    count = 0
    for i, age in enumerate(ages):
        if age is not None and isinstance(age, (int, float)) and 5 <= age <= 100:
            factor = data.iloc[i, col_idx]
            if factor is not None and not pd.isna(factor):
                time_mult = 1 / float(factor)
                line += f"{int(age)}: {time_mult:.4f}, "
                count += 1
                if count % 5 == 0:
                    print(line.rstrip(", ") + ",")
                    line = "    "
    if line.strip():
        print(line.rstrip(", ") + ",")
    print("}")
    print()

# Print open standards
print("# Female Open Standards")
for our_name, (file_name, col_idx) in distance_mapping.items():
    std = oc_row[col_idx]
    if std is not None and not pd.isna(std):
        print(f"  {our_name}: {float(std):.0f} seconds")
