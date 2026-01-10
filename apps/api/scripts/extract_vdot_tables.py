#!/usr/bin/env python3
"""
Extract VDOT Lookup Tables from Daniels' Running Formula

Extracts tabular data structures (VDOT → pace mappings) from aggregated text.
Looks for structured tables with VDOT values and corresponding training paces.
"""
import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
        
        text_parts = []
        for entry in entries:
            if entry.text_chunk:
                text_parts.append(entry.text_chunk)
        
        return "\n\n---\n\n".join(text_parts)
    finally:
        db.close()


def find_table_sections(text: str) -> List[Dict]:
    """
    Find sections that likely contain tables.
    
    Looks for:
    - "Table" mentions with numbers
    - Sections with multiple VDOT values
    - Structured pace listings
    """
    table_sections = []
    
    # Pattern 1: "Table X" mentions
    table_pattern = r"(?:Table|table)\s+[0-9]+[^\.]{50,2000}"
    matches = re.finditer(table_pattern, text, re.IGNORECASE | re.MULTILINE)
    for match in matches:
        section = match.group(0)
        if "vdot" in section.lower() or "pace" in section.lower():
            table_sections.append({
                "type": "table_mention",
                "text": section,
                "start": match.start(),
                "end": match.end()
            })
    
    # Pattern 2: Sections with multiple VDOT values (likely tables)
    vdot_table_pattern = r"(?:VDOT|vdot)\s+[0-9]+[^\.]{20,500}(?:VDOT|vdot)\s+[0-9]+"
    matches = re.finditer(vdot_table_pattern, text, re.IGNORECASE | re.MULTILINE)
    for match in matches:
        # Extract larger context around the match
        start = max(0, match.start() - 200)
        end = min(len(text), match.end() + 200)
        section = text[start:end]
        
        # Count VDOT mentions
        vdot_count = len(re.findall(r"\bVDOT\s+[0-9]+", section, re.IGNORECASE))
        if vdot_count >= 3:  # Likely a table if multiple VDOT values
            table_sections.append({
                "type": "vdot_listing",
                "text": section,
                "start": start,
                "end": end,
                "vdot_count": vdot_count
            })
    
    return table_sections


def parse_vdot_pace_line(line: str) -> Optional[Dict]:
    """
    Parse a line that might contain VDOT and pace information.
    
    Examples:
    - "VDOT 50: E 7:30, M 6:45, T 6:15, I 5:50, R 5:30"
    - "50  7:30  6:45  6:15  5:50  5:30"
    """
    # Pattern 1: "VDOT 50: E 7:30, M 6:45..."
    pattern1 = r"VDOT\s+([0-9]+(?:\.[0-9]+)?)\s*[:]?\s*(?:E|e)\s+([0-9]+:[0-9]+)[^,]*,\s*(?:M|m)\s+([0-9]+:[0-9]+)[^,]*,\s*(?:T|t)\s+([0-9]+:[0-9]+)[^,]*,\s*(?:I|i)\s+([0-9]+:[0-9]+)[^,]*,\s*(?:R|r)\s+([0-9]+:[0-9]+)"
    
    match = re.search(pattern1, line, re.IGNORECASE)
    if match:
        return {
            "vdot": float(match.group(1)),
            "e_pace": match.group(2),
            "m_pace": match.group(3),
            "t_pace": match.group(4),
            "i_pace": match.group(5),
            "r_pace": match.group(6)
        }
    
    # Pattern 2: Just numbers separated by spaces/tabs
    # "50  7:30  6:45  6:15  5:50  5:30"
    pattern2 = r"^([0-9]+(?:\.[0-9]+)?)\s+([0-9]+:[0-9]+)\s+([0-9]+:[0-9]+)\s+([0-9]+:[0-9]+)\s+([0-9]+:[0-9]+)\s+([0-9]+:[0-9]+)"
    match = re.search(pattern2, line)
    if match:
        return {
            "vdot": float(match.group(1)),
            "e_pace": match.group(2),
            "m_pace": match.group(3),
            "t_pace": match.group(4),
            "i_pace": match.group(5),
            "r_pace": match.group(6)
        }
    
    # Pattern 3: VDOT with individual pace mentions
    vdot_match = re.search(r"VDOT\s+([0-9]+(?:\.[0-9]+)?)", line, re.IGNORECASE)
    if vdot_match:
        vdot = float(vdot_match.group(1))
        paces = {}
        
        for pace_type in ["E", "M", "T", "I", "R"]:
            pace_pattern = rf"{pace_type}\s+pace[^:]*[:]?\s*([0-9]+:[0-9]+)"
            pace_match = re.search(pace_pattern, line, re.IGNORECASE)
            if pace_match:
                paces[f"{pace_type.lower()}_pace"] = pace_match.group(1)
        
        if paces:
            return {"vdot": vdot, **paces}
    
    return None


def extract_vdot_pace_table(text: str) -> List[Dict]:
    """
    Extract VDOT → pace mappings from text.
    
    Returns list of dictionaries with VDOT and corresponding paces.
    """
    table_data = []
    
    # Split into lines for easier parsing
    lines = text.split('\n')
    
    for line in lines:
        parsed = parse_vdot_pace_line(line)
        if parsed:
            table_data.append(parsed)
    
    # Also look for multi-line table structures
    # Find sections with multiple VDOT values
    vdot_sections = re.finditer(r"VDOT\s+[0-9]+[^\.]{10,500}", text, re.IGNORECASE | re.MULTILINE)
    for section_match in vdot_sections:
        section = section_match.group(0)
        parsed = parse_vdot_pace_line(section)
        if parsed and parsed not in table_data:
            table_data.append(parsed)
    
    return table_data


def extract_equivalent_performance_table(text: str) -> List[Dict]:
    """
    Extract VDOT → equivalent race time mappings.
    
    Looks for VDOT values with corresponding race times for different distances.
    """
    equivalent_data = []
    
    # Pattern: VDOT X: 5K Y:MM, 10K Y:MM, Marathon Y:MM:SS
    pattern = r"VDOT\s+([0-9]+(?:\.[0-9]+)?)[^\.]{10,500}"
    matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
    
    for match in matches:
        section = match.group(0)
        vdot_match = re.search(r"VDOT\s+([0-9]+(?:\.[0-9]+)?)", section, re.IGNORECASE)
        if not vdot_match:
            continue
        
        vdot = float(vdot_match.group(1))
        race_times = {}
        
        # Extract race times for different distances
        distances = {
            "5K": r"5K[^:]*[:]?\s*([0-9]+:[0-9]+)",
            "10K": r"10K[^:]*[:]?\s*([0-9]+:[0-9]+)",
            "half_marathon": r"half[^:]*marathon[^:]*[:]?\s*([0-9]+:[0-9]+)",
            "marathon": r"marathon[^:]*[:]?\s*([0-9]+:[0-9]+:[0-9]+|[0-9]+:[0-9]+)",
        }
        
        for dist, dist_pattern in distances.items():
            time_match = re.search(dist_pattern, section, re.IGNORECASE)
            if time_match:
                race_times[dist] = time_match.group(1)
        
        if race_times:
            equivalent_data.append({
                "vdot": vdot,
                "race_times": race_times
            })
    
    return equivalent_data


def convert_pace_to_seconds(pace_str: str) -> Optional[float]:
    """Convert pace string (MM:SS) to seconds per mile."""
    try:
        parts = pace_str.split(':')
        if len(parts) == 2:
            minutes = int(parts[0])
            seconds = int(parts[1])
            return minutes * 60 + seconds
        return None
    except:
        return None


def build_lookup_table(vdot_pace_data: List[Dict]) -> Dict:
    """
    Build structured lookup table from extracted data.
    
    Creates interpolation-ready lookup tables.
    """
    lookup = {
        "vdot_to_e_pace": {},
        "vdot_to_m_pace": {},
        "vdot_to_t_pace": {},
        "vdot_to_i_pace": {},
        "vdot_to_r_pace": {},
        "vdot_range": {"min": None, "max": None}
    }
    
    vdots = []
    
    for entry in vdot_pace_data:
        vdot = entry.get("vdot")
        if vdot is None:
            continue
        
        vdots.append(vdot)
        
        # Store paces (convert to seconds for easier interpolation)
        for pace_type in ["e", "m", "t", "i", "r"]:
            pace_key = f"vdot_to_{pace_type}_pace"
            pace_str = entry.get(f"{pace_type}_pace")
            if pace_str:
                pace_seconds = convert_pace_to_seconds(pace_str)
                if pace_seconds:
                    lookup[pace_key][vdot] = {
                        "pace_string": pace_str,
                        "pace_seconds": pace_seconds
                    }
    
    if vdots:
        lookup["vdot_range"]["min"] = min(vdots)
        lookup["vdot_range"]["max"] = max(vdots)
    
    return lookup


def store_vdot_tables(vdot_tables: Dict):
    """Store extracted VDOT tables in knowledge base."""
    db = get_db_sync()
    try:
        # Check if VDOT tables entry already exists
        existing = db.query(CoachingKnowledgeEntry).filter(
            CoachingKnowledgeEntry.principle_type == "vdot_lookup_tables",
            CoachingKnowledgeEntry.methodology == "Daniels"
        ).first()
        
        if existing:
            existing.extracted_principles = json.dumps(vdot_tables, indent=2)
            existing.text_chunk = json.dumps(vdot_tables, indent=2)[:5000]
            print("✅ Updated existing VDOT tables entry")
        else:
            entry = CoachingKnowledgeEntry(
                source="Daniels' Running Formula - VDOT Lookup Tables",
                methodology="Daniels",
                source_type="extracted",
                text_chunk=json.dumps(vdot_tables, indent=2)[:5000],
                extracted_principles=json.dumps(vdot_tables, indent=2),
                principle_type="vdot_lookup_tables"
            )
            db.add(entry)
            print("✅ Created new VDOT tables entry")
        
        db.commit()
        print(f"✅ Stored VDOT lookup tables")
        
    except Exception as e:
        print(f"❌ Error storing VDOT tables: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


def main():
    """Main extraction function."""
    print("=" * 60)
    print("VDOT TABLE EXTRACTION FROM DANIELS' RUNNING FORMULA")
    print("=" * 60)
    
    # Step 1: Aggregate text
    print("\n1. Aggregating Daniels entries...")
    text = aggregate_daniels_text()
    print(f"   Text length: {len(text)} characters")
    
    # Step 2: Find table sections
    print("\n2. Finding table sections...")
    table_sections = find_table_sections(text)
    print(f"   Found {len(table_sections)} potential table sections")
    
    # Step 3: Extract VDOT pace tables
    print("\n3. Extracting VDOT → pace mappings...")
    vdot_pace_data = extract_vdot_pace_table(text)
    print(f"   Found {len(vdot_pace_data)} VDOT pace entries")
    
    if vdot_pace_data:
        print("   Sample entries:")
        for entry in vdot_pace_data[:3]:
            print(f"     VDOT {entry.get('vdot')}: {entry}")
    
    # Step 4: Extract equivalent performance tables
    print("\n4. Extracting VDOT → race time mappings...")
    equivalent_data = extract_equivalent_performance_table(text)
    print(f"   Found {len(equivalent_data)} equivalent performance entries")
    
    # Step 5: Build lookup tables
    print("\n5. Building structured lookup tables...")
    lookup_table = build_lookup_table(vdot_pace_data)
    print(f"   VDOT range: {lookup_table['vdot_range']['min']} - {lookup_table['vdot_range']['max']}")
    print(f"   E pace entries: {len(lookup_table['vdot_to_e_pace'])}")
    print(f"   M pace entries: {len(lookup_table['vdot_to_m_pace'])}")
    print(f"   T pace entries: {len(lookup_table['vdot_to_t_pace'])}")
    print(f"   I pace entries: {len(lookup_table['vdot_to_i_pace'])}")
    print(f"   R pace entries: {len(lookup_table['vdot_to_r_pace'])}")
    
    # Step 6: Store
    print("\n6. Storing extracted tables...")
    vdot_tables = {
        "pace_lookup": lookup_table,
        "equivalent_performances": equivalent_data,
        "raw_extracted_data": vdot_pace_data,
        "table_sections_found": len(table_sections),
        "extraction_metadata": {
            "source": "Daniels' Running Formula",
            "methodology": "Daniels",
            "extraction_method": "pattern_matching_and_parsing"
        }
    }
    
    store_vdot_tables(vdot_tables)
    
    print("\n" + "=" * 60)
    print("✅ VDOT TABLE EXTRACTION COMPLETE")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Review extracted tables")
    print("2. Build lookup-based VDOT calculator")
    print("3. Validate against reference calculators")


if __name__ == "__main__":
    main()

