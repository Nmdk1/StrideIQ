#!/usr/bin/env python3
"""
Extract Tinman Pace Chart

Extracts Tinman's pace chart data (equivalent race times) and stores in knowledge base.
"""
import sys
import json
import re
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db_sync
from models import CoachingKnowledgeEntry


def parse_tinman_pace_chart(text: str) -> Dict:
    """
    Parse Tinman pace chart from extracted text.
    
    Format appears to be:
    Current 5k (season PR) | 1600m equivalent | 800m equivalent | 3200m equivalent
    """
    chart_data = {
        "methodology": "Tinman",
        "source": "Tinman Pace Chart (New Testament)",
        "pace_chart": [],
        "description": "Equivalent race times based on 5K performance"
    }
    
    # Pattern to match pace chart entries
    # Format: 5K time | 1600m | 800m | 3200m
    pattern = r"(\d{1,2}:\d{2})\s+(\d{1,2}:\d{2})\s+(\d{1,2}:\d{2})\s+(\d{1,2}:\d{2})"
    
    matches = re.finditer(pattern, text)
    
    for match in matches:
        five_k_time = match.group(1)
        mile_time = match.group(2)
        eight_hundred_time = match.group(3)
        two_mile_time = match.group(4)
        
        chart_data["pace_chart"].append({
            "5K": five_k_time,
            "1600m": mile_time,
            "800m": eight_hundred_time,
            "3200m": two_mile_time
        })
    
    return chart_data


def store_tinman_pace_chart(chart_data: Dict, text_chunk: str):
    """Store Tinman pace chart in knowledge base."""
    db = get_db_sync()
    try:
        # Check if entry exists
        existing = db.query(CoachingKnowledgeEntry).filter(
            CoachingKnowledgeEntry.principle_type == "pace_chart",
            CoachingKnowledgeEntry.methodology == "Tinman"
        ).first()
        
        if existing:
            existing.extracted_principles = json.dumps(chart_data, indent=2)
            existing.text_chunk = text_chunk[:5000]
            print("✅ Updated existing Tinman pace chart entry")
        else:
            entry = CoachingKnowledgeEntry(
                source="Tinman Pace Chart (New Testament)",
                methodology="Tinman",
                source_type="reference",
                text_chunk=text_chunk[:5000],
                extracted_principles=json.dumps(chart_data, indent=2),
                principle_type="pace_chart"
            )
            db.add(entry)
            print("✅ Created new Tinman pace chart entry")
        
        db.commit()
        print(f"✅ Stored Tinman pace chart ({len(chart_data['pace_chart'])} entries)")
        
    except Exception as e:
        print(f"❌ Error storing pace chart: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


def main():
    """Main function."""
    text_file = "/books/tinman_pace_chart.txt"
    
    try:
        with open(text_file, 'r', encoding='utf-8') as f:
            text = f.read()
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return
    
    print("=" * 60)
    print("EXTRACTING TINMAN PACE CHART")
    print("=" * 60)
    
    print("\n1. Parsing pace chart...")
    chart_data = parse_tinman_pace_chart(text)
    
    print(f"   Found {len(chart_data['pace_chart'])} pace chart entries")
    
    if len(chart_data['pace_chart']) > 0:
        print("\n   Sample entries:")
        for i, entry in enumerate(chart_data['pace_chart'][:5]):
            print(f"     {i+1}. 5K: {entry['5K']}, Mile: {entry['1600m']}, 800m: {entry['800m']}, 2Mile: {entry['3200m']}")
    
    print("\n2. Storing in knowledge base...")
    store_tinman_pace_chart(chart_data, text)
    
    print("\n" + "=" * 60)
    print("✅ EXTRACTION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()

