"""
Comprehensive audit of age-grading factors against Alan Jones 2025 Excel files.
Verifies all ages (5-100), both genders, all distances.
"""

import sys
sys.path.insert(0, '/app')

import pandas as pd
from typing import Dict, List, Tuple
import json

# Our implementation
from services.wma_age_factors import (
    WMA_1_MILE_MALE, WMA_5K_MALE, WMA_8K_MALE, WMA_10K_MALE,
    WMA_10_MILE_MALE, WMA_HALF_MARATHON_MALE, WMA_MARATHON_MALE,
    WMA_1_MILE_FEMALE, WMA_5K_FEMALE, WMA_8K_FEMALE, WMA_10K_FEMALE,
    WMA_10_MILE_FEMALE, WMA_HALF_MARATHON_FEMALE, WMA_MARATHON_FEMALE,
    WMA_OPEN_STANDARDS_SECONDS,
    get_wma_age_factor, get_wma_open_standard_seconds
)

MALE_FILE = '/app/data/MaleRoadStd2025.xlsx'
FEMALE_FILE = '/app/data/FemaleRoadStd2025.xlsx'

# Column mappings for each file
# Male file: Age, 1 Mile, 5 km, 6 km, 4 Mile, 8 km, 5 Mile, 10 km, ...
MALE_DISTANCE_COLS = {
    '1_MILE': ('1 Mile', 1),
    '5K': ('5 km', 2),
    '8K': ('8 km', 5),
    '10K': ('10 km', 7),
    '10_MILE': ('10 Mile', 11),
    'HALF_MARATHON': ('H. Mar', 13),
    'MARATHON': ('Marathon', 16),
}

# Female file has double Age column: Age, Age, 1 Mile, 5 km, ...
FEMALE_DISTANCE_COLS = {
    '1_MILE': ('1 Mile', 2),
    '5K': ('5 km', 3),
    '8K': ('8 km', 6),
    '10K': ('10 km', 8),
    '10_MILE': ('10 Mile', 12),
    'HALF_MARATHON': ('H. Mar', 14),
    'MARATHON': ('Marathon', 17),
}

OUR_FACTOR_TABLES = {
    ('M', '1_MILE'): WMA_1_MILE_MALE,
    ('M', '5K'): WMA_5K_MALE,
    ('M', '8K'): WMA_8K_MALE,
    ('M', '10K'): WMA_10K_MALE,
    ('M', '10_MILE'): WMA_10_MILE_MALE,
    ('M', 'HALF_MARATHON'): WMA_HALF_MARATHON_MALE,
    ('M', 'MARATHON'): WMA_MARATHON_MALE,
    ('F', '1_MILE'): WMA_1_MILE_FEMALE,
    ('F', '5K'): WMA_5K_FEMALE,
    ('F', '8K'): WMA_8K_FEMALE,
    ('F', '10K'): WMA_10K_FEMALE,
    ('F', '10_MILE'): WMA_10_MILE_FEMALE,
    ('F', 'HALF_MARATHON'): WMA_HALF_MARATHON_FEMALE,
    ('F', 'MARATHON'): WMA_MARATHON_FEMALE,
}

DISTANCE_METERS = {
    '1_MILE': 1609,
    '5K': 5000,
    '8K': 8000,
    '10K': 10000,
    '10_MILE': 16093,
    'HALF_MARATHON': 21097,
    'MARATHON': 42195,
}

def extract_factors_from_excel(file_path: str, distance_cols: Dict, sex: str) -> Dict[str, Dict[int, float]]:
    """Extract all factors from Excel file."""
    xl = pd.ExcelFile(file_path)
    
    # Find Age Factors sheet
    sheet_name = None
    for sheet in xl.sheet_names:
        if 'Fac' in sheet:
            sheet_name = sheet
            break
    
    if not sheet_name:
        raise ValueError(f"Could not find Age Factors sheet in {file_path}")
    
    df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
    
    # Verify column headers
    distances_row = df.iloc[1].tolist()
    
    # Get open standards (row 3)
    oc_row = df.iloc[3].tolist()
    
    # Get factor data (rows 4+)
    data = df.iloc[4:].reset_index(drop=True)
    ages_col = data.iloc[:, 0].tolist()
    
    results = {}
    open_standards = {}
    
    for dist_name, (expected_label, col_idx) in distance_cols.items():
        actual_label = distances_row[col_idx]
        if expected_label not in str(actual_label):
            print(f"WARNING: Column mismatch for {sex} {dist_name}: expected '{expected_label}', got '{actual_label}'")
        
        # Get open standard
        open_standards[dist_name] = float(oc_row[col_idx])
        
        # Get all age factors
        factors = {}
        for i, age in enumerate(ages_col):
            if age is not None and isinstance(age, (int, float)) and 5 <= age <= 100:
                factor = data.iloc[i, col_idx]
                if factor is not None and not pd.isna(factor):
                    # Convert WMA factor to time multiplier
                    time_mult = 1 / float(factor)
                    factors[int(age)] = round(time_mult, 4)
        
        results[dist_name] = factors
    
    return results, open_standards


def audit_factors() -> Tuple[List[Dict], List[Dict]]:
    """Compare our factors against Excel files. Returns (errors, warnings)."""
    errors = []
    warnings = []
    
    print("=" * 80)
    print("COMPREHENSIVE AGE-GRADING FACTOR AUDIT")
    print("=" * 80)
    print()
    
    # Extract from Excel
    print("Extracting factors from Excel files...")
    male_factors, male_standards = extract_factors_from_excel(MALE_FILE, MALE_DISTANCE_COLS, 'M')
    female_factors, female_standards = extract_factors_from_excel(FEMALE_FILE, FEMALE_DISTANCE_COLS, 'F')
    print("Done.\n")
    
    excel_factors = {
        'M': male_factors,
        'F': female_factors
    }
    excel_standards = {
        'M': male_standards,
        'F': female_standards
    }
    
    # Audit open standards
    print("Auditing Open Standards...")
    for sex in ['M', 'F']:
        sex_key = 'male' if sex == 'M' else 'female'
        for dist_name, excel_std in excel_standards[sex].items():
            dist_meters = DISTANCE_METERS[dist_name]
            our_standards = WMA_OPEN_STANDARDS_SECONDS.get(sex_key, {})
            
            # Find matching distance (allow small tolerance for mile conversions)
            our_std = None
            for our_dist, our_time in our_standards.items():
                if abs(our_dist - dist_meters) < 500:
                    our_std = our_time
                    break
            
            if our_std is None:
                errors.append({
                    'type': 'MISSING_STANDARD',
                    'sex': sex,
                    'distance': dist_name,
                    'expected': excel_std
                })
            elif abs(our_std - excel_std) > 0.5:
                errors.append({
                    'type': 'STANDARD_MISMATCH',
                    'sex': sex,
                    'distance': dist_name,
                    'expected': excel_std,
                    'actual': our_std,
                    'diff': abs(our_std - excel_std)
                })
    print("Done.\n")
    
    # Audit all factors
    print("Auditing Age Factors...")
    total_checked = 0
    total_errors = 0
    
    for sex in ['M', 'F']:
        sex_name = 'Male' if sex == 'M' else 'Female'
        
        for dist_name in excel_factors[sex].keys():
            our_table = OUR_FACTOR_TABLES.get((sex, dist_name), {})
            excel_table = excel_factors[sex][dist_name]
            
            for age in range(5, 101):
                total_checked += 1
                
                excel_factor = excel_table.get(age)
                our_factor = our_table.get(age)
                
                if excel_factor is None:
                    warnings.append({
                        'type': 'EXCEL_MISSING',
                        'sex': sex,
                        'distance': dist_name,
                        'age': age
                    })
                    continue
                
                if our_factor is None:
                    errors.append({
                        'type': 'OUR_MISSING',
                        'sex': sex,
                        'distance': dist_name,
                        'age': age,
                        'expected': excel_factor
                    })
                    total_errors += 1
                    continue
                
                # Allow small floating point differences (0.0002)
                diff = abs(our_factor - excel_factor)
                if diff > 0.0002:
                    errors.append({
                        'type': 'FACTOR_MISMATCH',
                        'sex': sex,
                        'distance': dist_name,
                        'age': age,
                        'expected': excel_factor,
                        'actual': our_factor,
                        'diff': diff
                    })
                    total_errors += 1
    
    print(f"Checked {total_checked} factor combinations.")
    print(f"Found {total_errors} errors.")
    print()
    
    return errors, warnings


def print_errors(errors: List[Dict], warnings: List[Dict]):
    """Print error summary."""
    print("=" * 80)
    print("AUDIT RESULTS")
    print("=" * 80)
    print()
    
    if not errors:
        print("✅ NO ERRORS FOUND - All factors match Excel files!")
    else:
        print(f"❌ FOUND {len(errors)} ERRORS:")
        print()
        
        # Group by type
        by_type = {}
        for err in errors:
            err_type = err['type']
            if err_type not in by_type:
                by_type[err_type] = []
            by_type[err_type].append(err)
        
        for err_type, errs in by_type.items():
            print(f"\n{err_type} ({len(errs)} occurrences):")
            print("-" * 40)
            
            # Show first 10 of each type
            for err in errs[:10]:
                if err_type == 'FACTOR_MISMATCH':
                    print(f"  {err['sex']} {err['distance']} Age {err['age']}: "
                          f"expected {err['expected']:.4f}, got {err['actual']:.4f} "
                          f"(diff: {err['diff']:.4f})")
                elif err_type == 'STANDARD_MISMATCH':
                    print(f"  {err['sex']} {err['distance']}: "
                          f"expected {err['expected']:.0f}s, got {err['actual']:.0f}s")
                elif err_type == 'OUR_MISSING':
                    print(f"  {err['sex']} {err['distance']} Age {err['age']}: "
                          f"missing (should be {err['expected']:.4f})")
                else:
                    print(f"  {err}")
            
            if len(errs) > 10:
                print(f"  ... and {len(errs) - 10} more")
    
    print()
    if warnings:
        print(f"⚠️  {len(warnings)} WARNINGS (Excel data missing - may be expected)")
    
    return len(errors) == 0


def generate_correction_code(errors: List[Dict]):
    """Generate Python code to fix any errors found."""
    if not errors:
        return
    
    print("\n" + "=" * 80)
    print("CORRECTION CODE")
    print("=" * 80)
    print()
    
    # Group factor mismatches by table
    mismatches = [e for e in errors if e['type'] == 'FACTOR_MISMATCH']
    by_table = {}
    for err in mismatches:
        key = (err['sex'], err['distance'])
        if key not in by_table:
            by_table[key] = []
        by_table[key].append(err)
    
    for (sex, dist), errs in by_table.items():
        table_name = f"WMA_{dist}_{'MALE' if sex == 'M' else 'FEMALE'}"
        print(f"# Corrections for {table_name}:")
        for err in errs:
            print(f"    {err['age']}: {err['expected']:.4f},  # was {err['actual']:.4f}")
        print()


if __name__ == '__main__':
    errors, warnings = audit_factors()
    success = print_errors(errors, warnings)
    
    if not success:
        generate_correction_code(errors)
        sys.exit(1)
    else:
        print("\n✅ AUDIT PASSED - Implementation is accurate!")
        sys.exit(0)
