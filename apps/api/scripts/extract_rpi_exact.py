#!/usr/bin/env python3
"""
Extract Exact RPI Formulas and Tables from Daniels' Running Formula

Aggregates all Daniels entries from knowledge base and extracts:
1. RPI calculation formulas
2. Training pace tables (E, M, T, I, R paces)
3. Equivalent performance tables (RPI → race times)
4. Pace zone formulas (% of E/M/T/I/R relative to RPI)

Stores in structured format for use by RPI calculator.
"""
import sys
import os
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db_sync
from models import CoachingKnowledgeEntry


def aggregate_daniels_text() -> str:
    """Aggregate all Daniels entries into a single text corpus."""
    db = get_db_sync()
    try:
        entries = db.query(CoachingKnowledgeEntry).filter(
            CoachingKnowledgeEntry.methodology.ilike('%Daniels%')
        ).order_by(CoachingKnowledgeEntry.created_at).all()
        
        print(f"Found {len(entries)} Daniels entries")
        
        # Aggregate text chunks
        text_parts = []
        for entry in entries:
            if entry.text_chunk:
                text_parts.append(entry.text_chunk)
        
        full_text = "\n\n---\n\n".join(text_parts)
        print(f"Aggregated text length: {len(full_text)} characters")
        
        return full_text
        
    finally:
        db.close()


def extract_rpi_formulas(text: str) -> Dict:
    """
    Extract RPI calculation formulas from text.
    
    Looks for:
    - RPI calculation equations
    - VO2max formulas
    - Regression equations
    - Percentage-based calculations
    """
    formulas = {
        "calculation_methods": [],
        "vo2max_formulas": [],
        "regression_equations": [],
        "percentage_formulas": []
    }
    
    # Pattern 1: RPI calculation mentions
    rpi_calc_patterns = [
        r"RPI\s*[=:]\s*([^\.\n]{20,200})",
        r"calculate.*RPI[^\.\n]{10,300}",
        r"RPI.*formula[^\.\n]{10,300}",
        r"RPI.*equation[^\.\n]{10,300}",
        r"determine.*RPI[^\.\n]{10,300}",
    ]
    
    for pattern in rpi_calc_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            formula_text = match.group(0).strip()
            if len(formula_text) > 30 and formula_text not in formulas["calculation_methods"]:
                formulas["calculation_methods"].append(formula_text[:500])
    
    # Pattern 2: VO2max formulas
    vo2_patterns = [
        r"VO2\s*max[^\.\n]{10,200}",
        r"VO2max\s*[=:]\s*([^\.\n]{20,200})",
        r"oxygen\s+uptake[^\.\n]{10,200}",
    ]
    
    for pattern in vo2_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            formula_text = match.group(0).strip()
            if len(formula_text) > 30 and formula_text not in formulas["vo2max_formulas"]:
                formulas["vo2max_formulas"].append(formula_text[:500])
    
    # Pattern 3: Regression equations (often contain coefficients)
    regression_patterns = [
        r"regression[^\.\n]{10,300}",
        r"y\s*=\s*[^\.\n]{10,200}",
        r"equation.*[0-9]+\.[0-9]+[^\.\n]{10,200}",
    ]
    
    for pattern in regression_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            formula_text = match.group(0).strip()
            if len(formula_text) > 30 and formula_text not in formulas["regression_equations"]:
                formulas["regression_equations"].append(formula_text[:500])
    
    # Pattern 4: Percentage-based formulas (% of VO2max, % of pace, etc.)
    percentage_patterns = [
        r"[0-9]+%\s+of\s+[^\.\n]{10,200}",
        r"percentage\s+of\s+[^\.\n]{10,200}",
        r"%\s+VO2max[^\.\n]{10,200}",
    ]
    
    for pattern in percentage_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            formula_text = match.group(0).strip()
            if len(formula_text) > 20 and formula_text not in formulas["percentage_formulas"]:
                formulas["percentage_formulas"].append(formula_text[:500])
    
    return formulas


def extract_pace_tables(text: str) -> Dict:
    """
    Extract training pace tables from text.
    
    Looks for:
    - E pace (Easy pace) tables
    - M pace (Marathon pace) tables
    - T pace (Threshold pace) tables
    - I pace (Interval pace) tables
    - R pace (Repetition pace) tables
    - RPI to pace mappings
    """
    pace_tables = {
        "e_pace": [],  # Easy pace
        "m_pace": [],  # Marathon pace
        "t_pace": [],  # Threshold pace
        "i_pace": [],  # Interval pace
        "r_pace": [],  # Repetition pace
        "rpi_to_pace": [],  # RPI → pace mappings
        "pace_definitions": {}  # Definitions of each pace type
    }
    
    # Extract pace definitions
    pace_definitions = {
        "E": ["easy pace", "e pace", "easy running"],
        "M": ["marathon pace", "m pace", "marathon"],
        "T": ["threshold pace", "t pace", "threshold", "tempo"],
        "I": ["interval pace", "i pace", "interval"],
        "R": ["repetition pace", "r pace", "repetition"]
    }
    
    for pace_type, keywords in pace_definitions.items():
        for keyword in keywords:
            # Look for definitions
            pattern = rf"{keyword}[^\.\n]{{20,400}}"
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                definition = match.group(0).strip()
                if len(definition) > 40:
                    key = f"{pace_type.lower()}_pace"
                    if key not in pace_tables["pace_definitions"]:
                        pace_tables["pace_definitions"][key] = []
                    if definition[:500] not in pace_tables["pace_definitions"][key]:
                        pace_tables["pace_definitions"][key].append(definition[:500])
    
    # Extract pace tables (look for tabular structures)
    # Pattern: RPI followed by paces (e.g., "RPI 50: E 7:30, M 6:45, T 6:15...")
    table_patterns = [
        r"RPI\s+[0-9]+\s*[:]\s*[^\.\n]{20,500}",  # RPI 50: E pace, M pace...
        r"[0-9]+\s+[EMTIR]\s+pace[^\.\n]{10,300}",  # "50 E pace..."
        r"pace\s+table[^\.\n]{50,2000}",  # "pace table" sections
        r"table\s+[0-9]+[^\.\n]{50,2000}",  # "Table 1", "Table 2", etc.
        r"RPI.*?[0-9]+:[0-9]+[^\.\n]{20,500}",  # RPI with time formats
    ]
    
    # Also look for multi-line tabular structures (RPI values with corresponding paces)
    # Pattern: Lines with RPI numbers followed by pace values
    multiline_table_pattern = r"(?:RPI|rpi)\s*[0-9]+.*?(?:\n[^\n]{10,100}){3,20}"
    multiline_matches = re.finditer(multiline_table_pattern, text, re.IGNORECASE | re.MULTILINE)
    for match in multiline_matches:
        table_text = match.group(0).strip()
        if len(table_text) > 100 and re.search(r"[0-9]+:[0-9]+", table_text):  # Contains time format
            pace_tables["tabular_data"].append(table_text[:2000])
    
    for pattern in table_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            table_text = match.group(0).strip()
            # Try to identify which pace type
            if re.search(r"\bE\s+pace|\beasy\s+pace", table_text, re.IGNORECASE):
                pace_tables["e_pace"].append(table_text[:1000])
            elif re.search(r"\bM\s+pace|\bmarathon\s+pace", table_text, re.IGNORECASE):
                pace_tables["m_pace"].append(table_text[:1000])
            elif re.search(r"\bT\s+pace|\bthreshold\s+pace", table_text, re.IGNORECASE):
                pace_tables["t_pace"].append(table_text[:1000])
            elif re.search(r"\bI\s+pace|\binterval\s+pace", table_text, re.IGNORECASE):
                pace_tables["i_pace"].append(table_text[:1000])
            elif re.search(r"\bR\s+pace|\brepetition\s+pace", table_text, re.IGNORECASE):
                pace_tables["r_pace"].append(table_text[:1000])
            else:
                # Generic RPI to pace mapping
                pace_tables["rpi_to_pace"].append(table_text[:1000])
    
    # Extract pace percentages (% of VO2max, % of pace)
    percentage_patterns = [
        r"E\s+pace.*?([0-9]+)%[^\.\n]{10,200}",
        r"M\s+pace.*?([0-9]+)%[^\.\n]{10,200}",
        r"T\s+pace.*?([0-9]+)%[^\.\n]{10,200}",
        r"I\s+pace.*?([0-9]+)%[^\.\n]{10,200}",
        r"R\s+pace.*?([0-9]+)%[^\.\n]{10,200}",
    ]
    
    for pattern in percentage_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            percentage_text = match.group(0).strip()
            if len(percentage_text) > 30:
                # Determine pace type
                if "E pace" in percentage_text or "easy" in percentage_text.lower():
                    pace_tables["e_pace"].append(percentage_text[:500])
                elif "M pace" in percentage_text or "marathon" in percentage_text.lower():
                    pace_tables["m_pace"].append(percentage_text[:500])
                elif "T pace" in percentage_text or "threshold" in percentage_text.lower():
                    pace_tables["t_pace"].append(percentage_text[:500])
                elif "I pace" in percentage_text or "interval" in percentage_text.lower():
                    pace_tables["i_pace"].append(percentage_text[:500])
                elif "R pace" in percentage_text or "repetition" in percentage_text.lower():
                    pace_tables["r_pace"].append(percentage_text[:500])
    
    return pace_tables


def extract_equivalent_performance_tables(text: str) -> Dict:
    """
    Extract equivalent performance tables (RPI → race times across distances).
    
    Looks for:
    - RPI to race time mappings
    - Equivalent performance tables
    - Race time predictions
    """
    equivalent_tables = {
        "rpi_to_race_times": [],
        "equivalent_performances": [],
        "race_time_predictions": []
    }
    
    # Pattern 1: RPI followed by race times
    rpi_race_patterns = [
        r"RPI\s+[0-9]+[^\.\n]{10,500}",  # RPI 50: 5K 20:00, 10K 41:30...
        r"equivalent\s+performance[^\.\n]{20,500}",
        r"race\s+time[^\.\n]{20,500}",
    ]
    
    for pattern in rpi_race_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            table_text = match.group(0).strip()
            if len(table_text) > 50:
                # Check if it contains distance mentions
                if re.search(r"\b5K|\b10K|\bmarathon|\bhalf", table_text, re.IGNORECASE):
                    equivalent_tables["rpi_to_race_times"].append(table_text[:1000])
    
    # Pattern 2: Distance-specific tables
    distance_patterns = [
        r"5K.*?[0-9]+:[0-9]+[^\.\n]{10,300}",
        r"10K.*?[0-9]+:[0-9]+[^\.\n]{10,300}",
        r"marathon.*?[0-9]+:[0-9]+[^\.\n]{10,300}",
        r"half.*?marathon.*?[0-9]+:[0-9]+[^\.\n]{10,300}",
    ]
    
    for pattern in distance_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            table_text = match.group(0).strip()
            if len(table_text) > 30:
                equivalent_tables["equivalent_performances"].append(table_text[:500])
    
    return equivalent_tables


def extract_pace_zone_formulas(text: str) -> Dict:
    """
    Extract pace zone formulas (% of E/M/T/I/R relative to RPI).
    
    Looks for percentage relationships between paces.
    """
    zone_formulas = {
        "pace_percentages": [],
        "zone_relationships": []
    }
    
    # Pattern: Percentage relationships
    percentage_patterns = [
        r"([0-9]+)%\s+of\s+[EMTIR]\s+pace[^\.\n]{10,200}",
        r"[EMTIR]\s+pace\s+is\s+([0-9]+)%[^\.\n]{10,200}",
        r"pace\s+zone[^\.\n]{20,300}",
    ]
    
    for pattern in percentage_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            formula_text = match.group(0).strip()
            if len(formula_text) > 30:
                zone_formulas["pace_percentages"].append(formula_text[:500])
    
    # Pattern: Relationships between paces (e.g., "T pace is 5 seconds faster than M pace")
    relationship_patterns = [
        r"[EMTIR]\s+pace.*?[EMTIR]\s+pace[^\.\n]{10,300}",
        r"pace\s+relationship[^\.\n]{20,300}",
    ]
    
    for pattern in relationship_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            formula_text = match.group(0).strip()
            if len(formula_text) > 40:
                zone_formulas["zone_relationships"].append(formula_text[:500])
    
    return zone_formulas


def store_rpi_extraction(rpi_data: Dict):
    """Store extracted RPI data in knowledge base."""
    db = get_db_sync()
    try:
        # Check if RPI extraction entry already exists
        existing = db.query(CoachingKnowledgeEntry).filter(
            CoachingKnowledgeEntry.principle_type == "rpi_exact",
            CoachingKnowledgeEntry.methodology == "Daniels"
        ).first()
        
        if existing:
            # Update existing entry
            existing.extracted_principles = json.dumps(rpi_data, indent=2)
            existing.text_chunk = json.dumps(rpi_data, indent=2)[:5000]  # Store summary
            print("✅ Updated existing RPI extraction entry")
        else:
            # Create new entry
            entry = CoachingKnowledgeEntry(
                source="Daniels' Running Formula - Extracted RPI Data",
                methodology="Daniels",
                source_type="extracted",
                text_chunk=json.dumps(rpi_data, indent=2)[:5000],  # Store summary
                extracted_principles=json.dumps(rpi_data, indent=2),
                principle_type="rpi_exact"
            )
            db.add(entry)
            print("✅ Created new RPI extraction entry")
        
        db.commit()
        print(f"✅ Stored RPI extraction data")
        
    except Exception as e:
        print(f"❌ Error storing RPI extraction: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


def main():
    """Main extraction function."""
    print("=" * 60)
    print("RPI EXACT EXTRACTION FROM DANIELS' RUNNING FORMULA")
    print("=" * 60)
    
    # Step 1: Aggregate all Daniels text
    print("\n1. Aggregating Daniels entries...")
    text = aggregate_daniels_text()
    
    if not text or len(text) < 100:
        print("❌ Error: Insufficient Daniels text found")
        return
    
    # Step 2: Extract RPI formulas
    print("\n2. Extracting RPI calculation formulas...")
    formulas = extract_rpi_formulas(text)
    print(f"   Found {len(formulas['calculation_methods'])} calculation methods")
    print(f"   Found {len(formulas['vo2max_formulas'])} VO2max formulas")
    print(f"   Found {len(formulas['regression_equations'])} regression equations")
    print(f"   Found {len(formulas['percentage_formulas'])} percentage formulas")
    
    # Step 3: Extract pace tables
    print("\n3. Extracting training pace tables...")
    pace_tables = extract_pace_tables(text)
    print(f"   Found {len(pace_tables['e_pace'])} E pace entries")
    print(f"   Found {len(pace_tables['m_pace'])} M pace entries")
    print(f"   Found {len(pace_tables['t_pace'])} T pace entries")
    print(f"   Found {len(pace_tables['i_pace'])} I pace entries")
    print(f"   Found {len(pace_tables['r_pace'])} R pace entries")
    print(f"   Found {len(pace_tables['pace_definitions'])} pace definitions")
    
    # Step 4: Extract equivalent performance tables
    print("\n4. Extracting equivalent performance tables...")
    equivalent_tables = extract_equivalent_performance_tables(text)
    print(f"   Found {len(equivalent_tables['rpi_to_race_times'])} RPI to race time entries")
    print(f"   Found {len(equivalent_tables['equivalent_performances'])} equivalent performance entries")
    
    # Step 5: Extract pace zone formulas
    print("\n5. Extracting pace zone formulas...")
    zone_formulas = extract_pace_zone_formulas(text)
    print(f"   Found {len(zone_formulas['pace_percentages'])} pace percentage entries")
    print(f"   Found {len(zone_formulas['zone_relationships'])} zone relationship entries")
    
    # Step 6: Combine and store
    print("\n6. Storing extracted data...")
    rpi_data = {
        "formulas": formulas,
        "pace_tables": pace_tables,
        "equivalent_tables": equivalent_tables,
        "zone_formulas": zone_formulas,
        "extraction_metadata": {
            "source": "Daniels' Running Formula",
            "methodology": "Daniels",
            "extracted_at": str(Path(__file__).stat().st_mtime)
        }
    }
    
    store_rpi_extraction(rpi_data)
    
    print("\n" + "=" * 60)
    print("✅ RPI EXTRACTION COMPLETE")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Review extracted data in knowledge base")
    print("2. Refine RPI calculator with exact formulas")
    print("3. Create structured pace tables from extracted data")


if __name__ == "__main__":
    main()

