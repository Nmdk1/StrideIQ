"""Extract all official age factors from Alan Jones 2025 tables."""

import sys
sys.path.insert(0, '/app')

import pandas as pd

male_file = '/app/data/MaleRoadStd2025.xlsx'
female_file = '/app/data/FemaleRoadStd2025.xlsx'

print("=" * 70)
print("EXTRACTING ALAN JONES 2025 AGE FACTORS - ALL DISTANCES")
print("=" * 70)
print()

def extract_factors(file_path, sex_label):
    """Extract factors from Excel file."""
    print(f"Processing {sex_label} factors from {file_path}")
    print()
    
    # Check available sheets
    xl = pd.ExcelFile(file_path)
    print(f"Available sheets: {xl.sheet_names}")
    
    # Find the Age Factors sheet (might have different name)
    sheet_name = None
    for name in xl.sheet_names:
        if 'Factor' in name or 'factor' in name:
            sheet_name = name
            break
    
    if sheet_name is None:
        sheet_name = xl.sheet_names[0]  # Default to first sheet
    
    print(f"Using sheet: {sheet_name}")
    df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
    
    # Get column names from row 1
    distances_row = df.iloc[1].tolist()
    print(f"Available distances: {distances_row}")
    print()
    
    # Map our desired distances to column names in the file
    distance_mapping = {
        '1_MILE': '1 Mile',
        '5K': '5 km',
        '8K': '8 km',
        '10K': '10 km',
        '10_MILE': '10 Mile',
        'HALF_MARATHON': 'H. Mar',
        'MARATHON': 'Marathon',
    }
    
    # Get open class standards (row 3)
    oc_row = df.iloc[3].tolist()
    
    # Get factor data - skip first 4 rows (headers)
    data = df.iloc[4:].reset_index(drop=True)
    ages = data.iloc[:, 0].tolist()
    
    results = {}
    open_standards = {}
    
    for our_name, file_name in distance_mapping.items():
        if file_name in distances_row:
            col_idx = distances_row.index(file_name)
            open_standards[our_name] = oc_row[col_idx]
            
            factors = {}
            for i, age in enumerate(ages):
                if age is not None and isinstance(age, (int, float)) and 5 <= age <= 100:
                    factor = data.iloc[i, col_idx]
                    if factor is not None and not pd.isna(factor):
                        time_mult = 1 / float(factor)
                        factors[int(age)] = round(time_mult, 4)
            
            results[our_name] = factors
            print(f"  {our_name}: {len(factors)} ages, open standard: {open_standards[our_name]}s")
        else:
            print(f"  {our_name}: NOT FOUND in file")
    
    return results, open_standards

# Extract male factors
print("=" * 70)
print("MALE FACTORS")
print("=" * 70)
male_factors, male_standards = extract_factors(male_file, "Male")
print()

# Extract female factors
print("=" * 70)
print("FEMALE FACTORS")
print("=" * 70)
female_factors, female_standards = extract_factors(female_file, "Female")
print()

# Output Python code
print("=" * 70)
print("PYTHON CODE FOR wma_age_factors.py")
print("=" * 70)
print()

def print_factor_dict(name, factors):
    """Print a factor dictionary as Python code."""
    print(f"{name}: Dict[int, float] = {{")
    ages = sorted(factors.keys())
    for i, age in enumerate(ages):
        factor = factors[age]
        if (i + 1) % 5 == 0 or i == len(ages) - 1:
            print(f"    {age}: {factor},")
        else:
            print(f"    {age}: {factor},", end=" ")
    print("}")
    print()

# Print male factors
for distance_name, factors in male_factors.items():
    dict_name = f"WMA_{distance_name}_MALE"
    print(f"# {distance_name} Male - Alan Jones 2025")
    print_factor_dict(dict_name, factors)

print()
print("# " + "=" * 60)
print()

# Print female factors
for distance_name, factors in female_factors.items():
    dict_name = f"WMA_{distance_name}_FEMALE"
    print(f"# {distance_name} Female - Alan Jones 2025")
    print_factor_dict(dict_name, factors)

# Print open standards
print()
print("# Open Class Standards (seconds) - Alan Jones 2025")
print("WMA_OPEN_STANDARDS_SECONDS: Dict[str, Dict[float, float]] = {")
print('    "male": {')
for name, std in male_standards.items():
    if std is not None and not pd.isna(std):
        print(f"        {name.lower()!r}: {float(std)},")
print("    },")
print('    "female": {')
for name, std in female_standards.items():
    if std is not None and not pd.isna(std):
        print(f"        {name.lower()!r}: {float(std)},")
print("    },")
print("}")
