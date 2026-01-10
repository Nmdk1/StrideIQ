#!/usr/bin/env python3
"""
Verify VDOT Formula Accuracy

Checks extracted formulas against known VDOT calculation methods and tests accuracy.
"""
import sys
import json
import re
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db_sync
from models import CoachingKnowledgeEntry


def extract_formula_details(text: str) -> Dict:
    """Extract actual mathematical formulas from text."""
    formulas = {
        "equations": [],
        "coefficients": [],
        "lookup_mentions": []
    }
    
    # Look for actual equations (y = ..., VDOT = ..., etc.)
    equation_patterns = [
        r"VDOT\s*=\s*([^\.\n]{10,200})",
        r"y\s*=\s*([^\.\n]{10,200})",
        r"([a-zA-Z]+)\s*=\s*([0-9]+\.[0-9]+)\s*\*\s*[^\.\n]{5,100}",
        r"([0-9]+\.[0-9]+)\s*\*\s*[^\.\n]{5,100}",
    ]
    
    for pattern in equation_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            eq = match.group(0).strip()
            if len(eq) > 15 and eq not in formulas["equations"]:
                formulas["equations"].append(eq[:300])
    
    # Look for coefficients (numbers that might be formula constants)
    coefficient_patterns = [
        r"coefficient[^\.\n]{5,100}",
        r"([0-9]+\.[0-9]{3,})\s*(?:is|equals|=\s*)[^\.\n]{5,50}",
    ]
    
    for pattern in coefficient_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            coeff = match.group(0).strip()
            if len(coeff) > 20:
                formulas["coefficients"].append(coeff[:300])
    
    # Look for mentions of lookup tables
    lookup_patterns = [
        r"lookup\s+table[^\.\n]{5,100}",
        r"table\s+[0-9]+[^\.\n]{10,200}",
        r"refer\s+to\s+table[^\.\n]{5,100}",
    ]
    
    for pattern in lookup_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            lookup = match.group(0).strip()
            if len(lookup) > 20:
                formulas["lookup_mentions"].append(lookup[:300])
    
    return formulas


def test_vdot_calculation():
    """Test VDOT calculation with known race times."""
    # Known test cases: race time -> expected VDOT (approximate)
    test_cases = [
        {"distance_m": 5000, "time_s": 1200, "expected_vdot": 50.0},  # 5K in 20:00
        {"distance_m": 10000, "time_s": 2400, "expected_vdot": 50.0},  # 10K in 40:00
        {"distance_m": 5000, "time_s": 1080, "expected_vdot": 55.0},  # 5K in 18:00
    ]
    
    from services.vdot_calculator import calculate_vdot_from_race_time
    
    print("\n🧪 Testing VDOT Calculator Accuracy:")
    print("-" * 60)
    
    for test in test_cases:
        calculated = calculate_vdot_from_race_time(test["distance_m"], test["time_s"])
        expected = test["expected_vdot"]
        diff = abs(calculated - expected) if calculated else None
        
        print(f"  {test['distance_m']/1000:.1f}K in {test['time_s']//60}:{test['time_s']%60:02d}")
        print(f"    Expected VDOT: ~{expected}")
        print(f"    Calculated: {calculated}")
        if diff:
            print(f"    Difference: {diff:.1f} ({'✅ Good' if diff < 2 else '⚠️ Needs improvement'})")
        print()


def main():
    print("=" * 60)
    print("VDOT FORMULA VERIFICATION")
    print("=" * 60)
    
    db = get_db_sync()
    try:
        # Get extracted VDOT data
        entry = db.query(CoachingKnowledgeEntry).filter(
            CoachingKnowledgeEntry.principle_type == "vdot_exact"
        ).first()
        
        if not entry:
            print("❌ No VDOT extraction found")
            return
        
        data = json.loads(entry.extracted_principles) if entry.extracted_principles else {}
        
        print("\n📋 EXTRACTED FORMULA SUMMARY:")
        formulas = data.get("formulas", {})
        print(f"  Calculation methods: {len(formulas.get('calculation_methods', []))}")
        print(f"  Regression equations: {len(formulas.get('regression_equations', []))}")
        print(f"  Percentage formulas: {len(formulas.get('percentage_formulas', []))}")
        
        # Show sample formulas
        print("\n📐 SAMPLE CALCULATION METHODS:")
        for i, method in enumerate(formulas.get('calculation_methods', [])[:3], 1):
            print(f"  {i}. {method[:200]}...")
        
        print("\n📐 SAMPLE REGRESSION EQUATIONS:")
        for i, eq in enumerate(formulas.get('regression_equations', [])[:3], 1):
            print(f"  {i}. {eq[:200]}...")
        
        # Extract actual mathematical formulas
        print("\n🔍 EXTRACTING MATHEMATICAL FORMULAS:")
        all_text = entry.text_chunk if entry.text_chunk else ""
        if entry.extracted_principles:
            all_text += " " + json.dumps(data)
        
        formula_details = extract_formula_details(all_text)
        print(f"  Found {len(formula_details['equations'])} equations")
        print(f"  Found {len(formula_details['coefficients'])} coefficient mentions")
        print(f"  Found {len(formula_details['lookup_mentions'])} lookup table mentions")
        
        if formula_details['equations']:
            print("\n  Sample Equations:")
            for i, eq in enumerate(formula_details['equations'][:3], 1):
                print(f"    {i}. {eq}")
        
        if formula_details['lookup_mentions']:
            print("\n  Lookup Table Mentions:")
            for i, lookup in enumerate(formula_details['lookup_mentions'][:3], 1):
                print(f"    {i}. {lookup[:150]}...")
        
        # Check if formulas mention lookup tables (Daniels uses lookup tables primarily)
        has_lookup_mentions = len(formula_details['lookup_mentions']) > 0
        has_equations = len(formula_details['equations']) > 0
        
        print("\n" + "=" * 60)
        print("VERIFICATION ASSESSMENT:")
        print("=" * 60)
        
        if has_lookup_mentions:
            print("✅ Found mentions of lookup tables")
            print("   Note: Daniels' VDOT system primarily uses lookup tables,")
            print("   not simple formulas. This is expected.")
        else:
            print("⚠️  No lookup table mentions found")
            print("   Daniels' VDOT uses lookup tables - may need deeper extraction")
        
        if has_equations:
            print("✅ Found mathematical equations")
            print("   These may be regression equations or approximations")
        else:
            print("⚠️  No clear mathematical equations found")
            print("   May need to extract from tables or more detailed text analysis")
        
        print("\n📊 CURRENT STATUS:")
        print("   - Extracted text chunks: ✅")
        print("   - Pattern-matched formulas: ✅")
        print("   - Exact mathematical formulas: ⚠️  Limited")
        print("   - Lookup table data: ⚠️  Mentions found, but tables not extracted")
        
        print("\n💡 RECOMMENDATIONS:")
        print("   1. Extract actual pace tables from Daniels book (tabular data)")
        print("   2. Use lookup table approach rather than formulas")
        print("   3. Cross-reference with vdoto2.com calculator for validation")
        print("   4. Consider using open-source VDOT implementations as reference")
        
        # Test current calculator
        test_vdot_calculation()
        
    finally:
        db.close()


if __name__ == "__main__":
    main()

