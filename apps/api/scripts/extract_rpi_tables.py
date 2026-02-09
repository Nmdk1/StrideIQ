#!/usr/bin/env python3
"""
Extract RPI Lookup Tables from Daniels' Running Formula

Extracts tabular data structures (RPI → pace mappings) from aggregated text.
Looks for structured tables with RPI values and corresponding training paces.
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
    - Sections with multiple RPI values
    - Structured pace listings
    """
    table_sections = []
    
    # Pattern 1: "Table X" mentions
    table_pattern = r"(?:Table|table)\s+[0-9]+[^\.]{50,2000}"
    matches = re.finditer(table_pattern, text, re.IGNORECASE | re.MULTILINE)
    for match in matches:
        section = match.group(0)
        if "rpi" in section.lower() or "pace" in section.lower():
            table_sections.append({
                "type": "table_mention",
                "text": section,
                "start": match.start(),
                "end": match.end()
            })
    
    # Pattern 2: Sections with multiple RPI values (likely tables)
    rpi_table_pattern = r"(?:RPI|rpi)\s+[0-9]+[^\.]{20,500}(?:RPI|rpi)\s+[0-9]+"
    matches = re.finditer(rpi_table_pattern, text, re.IGNORECASE | re.MULTILINE)
    for match in matches:
        # Extract larger context around the match
        start = max(0, match.start() - 200)
        end = min(len(text), match.end() + 200)
        section = text[start:end]
        
        # Count RPI mentions
        rpi_count = len(re.findall(r"\bRPI\s+[0-9]+", section, re.IGNORECASE))
        if rpi_count >= 3:  # Likely a table if multiple RPI values
            table_sections.append({
                "type": "rpi_listing",
                "text": section,
                "start": start,
                "end": end,
                "rpi_count": rpi_count
            })
    
    return table_sections


def parse_rpi_pace_line(line: str) -> Optional[Dict]:
    """
    Parse a line that might contain RPI and pace information.
    
    Examples:
    - "RPI 50: E 7:30, M 6:45, T 6:15, I 5:50, R 5:30"
    - "50  7:30  6:45  6:15  5:50  5:30"
    """
    # Pattern 1: "RPI 50: E 7:30, M 6:45..."
    pattern1 = r"RPI\s+([0-9]+(?:\.[0-9]+)?)\s*[:]?\s*(?:E|e)\s+([0-9]+:[0-9]+)[^,]*,\s*(?:M|m)\s+([0-9]+:[0-9]+)[^,]*,\s*(?:T|t)\s+([0-9]+:[0-9]+)[^,]*,\s*(?:I|i)\s+([0-9]+:[0-9]+)[^,]*,\s*(?:R|r)\s+([0-9]+:[0-9]+)"
    
    match = re.search(pattern1, line, re.IGNORECASE)
    if match:
        return {
            "rpi": float(match.group(1)),
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
            "rpi": float(match.group(1)),
            "e_pace": match.group(2),
            "m_pace": match.group(3),
            "t_pace": match.group(4),
            "i_pace": match.group(5),
            "r_pace": match.group(6)
        }
    
    # Pattern 3: RPI with individual pace mentions
    rpi_match = re.search(r"RPI\s+([0-9]+(?:\.[0-9]+)?)", line, re.IGNORECASE)
    if rpi_match:
        rpi = float(rpi_match.group(1))
        paces = {}
        
        for pace_type in ["E", "M", "T", "I", "R"]:
            pace_pattern = rf"{pace_type}\s+pace[^:]*[:]?\s*([0-9]+:[0-9]+)"
            pace_match = re.search(pace_pattern, line, re.IGNORECASE)
            if pace_match:
                paces[f"{pace_type.lower()}_pace"] = pace_match.group(1)
        
        if paces:
            return {"rpi": rpi, **paces}
    
    return None


def extract_rpi_pace_table(text: str) -> List[Dict]:
    """
    Extract RPI → pace mappings from text.
    
    Returns list of dictionaries with RPI and corresponding paces.
    """
    table_data = []
    
    # Split into lines for easier parsing
    lines = text.split('\n')
    
    for line in lines:
        parsed = parse_rpi_pace_line(line)
        if parsed:
            table_data.append(parsed)
    
    # Also look for multi-line table structures
    # Find sections with multiple RPI values
    rpi_sections = re.finditer(r"RPI\s+[0-9]+[^\.]{10,500}", text, re.IGNORECASE | re.MULTILINE)
    for section_match in rpi_sections:
        section = section_match.group(0)
        parsed = parse_rpi_pace_line(section)
        if parsed and parsed not in table_data:
            table_data.append(parsed)
    
    return table_data


def extract_equivalent_performance_table(text: str) -> List[Dict]:
    """
    Extract RPI → equivalent race time mappings.
    
    Looks for RPI values with corresponding race times for different distances.
    """
    equivalent_data = []
    
    # Pattern: RPI X: 5K Y:MM, 10K Y:MM, Marathon Y:MM:SS
    pattern = r"RPI\s+([0-9]+(?:\.[0-9]+)?)[^\.]{10,500}"
    matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
    
    for match in matches:
        section = match.group(0)
        rpi_match = re.search(r"RPI\s+([0-9]+(?:\.[0-9]+)?)", section, re.IGNORECASE)
        if not rpi_match:
            continue
        
        rpi = float(rpi_match.group(1))
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
                "rpi": rpi,
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


def build_lookup_table(rpi_pace_data: List[Dict]) -> Dict:
    """
    Build structured lookup table from extracted data.
    
    Creates interpolation-ready lookup tables.
    """
    lookup = {
        "rpi_to_e_pace": {},
        "rpi_to_m_pace": {},
        "rpi_to_t_pace": {},
        "rpi_to_i_pace": {},
        "rpi_to_r_pace": {},
        "rpi_range": {"min": None, "max": None}
    }
    
    rpis = []
    
    for entry in rpi_pace_data:
        rpi = entry.get("rpi")
        if rpi is None:
            continue
        
        rpis.append(rpi)
        
        # Store paces (convert to seconds for easier interpolation)
        for pace_type in ["e", "m", "t", "i", "r"]:
            pace_key = f"rpi_to_{pace_type}_pace"
            pace_str = entry.get(f"{pace_type}_pace")
            if pace_str:
                pace_seconds = convert_pace_to_seconds(pace_str)
                if pace_seconds:
                    lookup[pace_key][rpi] = {
                        "pace_string": pace_str,
                        "pace_seconds": pace_seconds
                    }
    
    if rpis:
        lookup["rpi_range"]["min"] = min(rpis)
        lookup["rpi_range"]["max"] = max(rpis)
    
    return lookup


def store_rpi_tables(rpi_tables: Dict):
    """Store extracted RPI tables in knowledge base."""
    db = get_db_sync()
    try:
        # Check if RPI tables entry already exists
        existing = db.query(CoachingKnowledgeEntry).filter(
            CoachingKnowledgeEntry.principle_type == "rpi_lookup_tables",
            CoachingKnowledgeEntry.methodology == "Daniels"
        ).first()
        
        if existing:
            existing.extracted_principles = json.dumps(rpi_tables, indent=2)
            existing.text_chunk = json.dumps(rpi_tables, indent=2)[:5000]
            print("✅ Updated existing RPI tables entry")
        else:
            entry = CoachingKnowledgeEntry(
                source="Daniels' Running Formula - RPI Lookup Tables",
                methodology="Daniels",
                source_type="extracted",
                text_chunk=json.dumps(rpi_tables, indent=2)[:5000],
                extracted_principles=json.dumps(rpi_tables, indent=2),
                principle_type="rpi_lookup_tables"
            )
            db.add(entry)
            print("✅ Created new RPI tables entry")
        
        db.commit()
        print(f"✅ Stored RPI lookup tables")
        
    except Exception as e:
        print(f"❌ Error storing RPI tables: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


def main():
    """Main extraction function."""
    print("=" * 60)
    print("RPI TABLE EXTRACTION FROM DANIELS' RUNNING FORMULA")
    print("=" * 60)
    
    # Step 1: Aggregate text
    print("\n1. Aggregating Daniels entries...")
    text = aggregate_daniels_text()
    print(f"   Text length: {len(text)} characters")
    
    # Step 2: Find table sections
    print("\n2. Finding table sections...")
    table_sections = find_table_sections(text)
    print(f"   Found {len(table_sections)} potential table sections")
    
    # Step 3: Extract RPI pace tables
    print("\n3. Extracting RPI → pace mappings...")
    rpi_pace_data = extract_rpi_pace_table(text)
    print(f"   Found {len(rpi_pace_data)} RPI pace entries")
    
    if rpi_pace_data:
        print("   Sample entries:")
        for entry in rpi_pace_data[:3]:
            print(f"     RPI {entry.get('rpi')}: {entry}")
    
    # Step 4: Extract equivalent performance tables
    print("\n4. Extracting RPI → race time mappings...")
    equivalent_data = extract_equivalent_performance_table(text)
    print(f"   Found {len(equivalent_data)} equivalent performance entries")
    
    # Step 5: Build lookup tables
    print("\n5. Building structured lookup tables...")
    lookup_table = build_lookup_table(rpi_pace_data)
    print(f"   RPI range: {lookup_table['rpi_range']['min']} - {lookup_table['rpi_range']['max']}")
    print(f"   E pace entries: {len(lookup_table['rpi_to_e_pace'])}")
    print(f"   M pace entries: {len(lookup_table['rpi_to_m_pace'])}")
    print(f"   T pace entries: {len(lookup_table['rpi_to_t_pace'])}")
    print(f"   I pace entries: {len(lookup_table['rpi_to_i_pace'])}")
    print(f"   R pace entries: {len(lookup_table['rpi_to_r_pace'])}")
    
    # Step 6: Store
    print("\n6. Storing extracted tables...")
    rpi_tables = {
        "pace_lookup": lookup_table,
        "equivalent_performances": equivalent_data,
        "raw_extracted_data": rpi_pace_data,
        "table_sections_found": len(table_sections),
        "extraction_metadata": {
            "source": "Daniels' Running Formula",
            "methodology": "Daniels",
            "extraction_method": "pattern_matching_and_parsing"
        }
    }
    
    store_rpi_tables(rpi_tables)
    
    print("\n" + "=" * 60)
    print("✅ RPI TABLE EXTRACTION COMPLETE")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Review extracted tables")
    print("2. Build lookup-based RPI calculator")
    print("3. Validate against reference calculators")


if __name__ == "__main__":
    main()

