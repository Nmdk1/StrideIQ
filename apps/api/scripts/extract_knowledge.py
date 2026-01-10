#!/usr/bin/env python3
"""
Knowledge Extraction Script

Helper script to extract coaching principles from text using AI.
Can be used with book excerpts, web content, or any text source.
"""
import sys
import os
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db_sync
from models import CoachingKnowledgeEntry
from services.knowledge_extraction_ai import (
    extract_vdot_formula,
    extract_periodization_principles,
    extract_general_principles
)


def extract_and_store(text: str, source: str, methodology: str, source_type: str = "book"):
    """
    Extract principles from text and store in knowledge base.
    
    Args:
        text: Text content to extract from
        source: Source identifier (book title, URL, etc.)
        methodology: Coaching methodology (e.g., "Daniels", "Pfitzinger")
        source_type: Type of source ("book", "article", "research")
    """
    db = get_db_sync()
    try:
        # Extract VDOT formula if relevant
        if "vdot" in text.lower() or "daniels" in methodology.lower():
            print(f"Extracting VDOT formula from {source}...")
            vdot_data = extract_vdot_formula(text)
            if vdot_data:
                print(f"✅ Extracted VDOT formula")
                # Store in knowledge base
                entry = CoachingKnowledgeEntry(
                    source=source,
                    methodology=methodology,
                    source_type=source_type,
                    text_chunk=text[:1000],  # Store first 1000 chars
                    extracted_principles=json.dumps(vdot_data),
                    principle_type="vdot_formula"
                )
                db.add(entry)
                db.commit()
                print(f"✅ Stored VDOT formula entry: {entry.id}")
        
        # Extract periodization principles
        if "periodization" in text.lower() or "phase" in text.lower():
            print(f"Extracting periodization principles from {source}...")
            periodization_data = extract_periodization_principles(text, methodology)
            if periodization_data:
                print(f"✅ Extracted periodization principles")
                entry = CoachingKnowledgeEntry(
                    source=source,
                    methodology=methodology,
                    source_type=source_type,
                    text_chunk=text[:1000],
                    extracted_principles=json.dumps(periodization_data),
                    principle_type="periodization"
                )
                db.add(entry)
                db.commit()
                print(f"✅ Stored periodization entry: {entry.id}")
        
        # Extract general principles
        print(f"Extracting general principles from {source}...")
        general_data = extract_general_principles(text, source, methodology)
        if general_data:
            print(f"✅ Extracted general principles")
            entry = CoachingKnowledgeEntry(
                source=source,
                methodology=methodology,
                source_type=source_type,
                text_chunk=text[:1000],
                extracted_principles=json.dumps(general_data),
                principle_type="general"
            )
            db.add(entry)
            db.commit()
            print(f"✅ Stored general principles entry: {entry.id}")
        
        print(f"✅ Extraction complete for {source}")
        
    except Exception as e:
        print(f"❌ Error extracting from {source}: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


def main():
    """Main function for command-line usage."""
    if len(sys.argv) < 4:
        print("Usage: python extract_knowledge.py <text_file> <source> <methodology> [source_type]")
        print("\nExample:")
        print("  python extract_knowledge.py daniels_excerpt.txt 'Daniels Running Formula' 'Daniels' book")
        sys.exit(1)
    
    text_file = sys.argv[1]
    source = sys.argv[2]
    methodology = sys.argv[3]
    source_type = sys.argv[4] if len(sys.argv) > 4 else "book"
    
    # Read text file
    try:
        with open(text_file, 'r', encoding='utf-8') as f:
            text = f.read()
    except Exception as e:
        print(f"❌ Error reading file {text_file}: {e}")
        sys.exit(1)
    
    # Extract and store
    extract_and_store(text, source, methodology, source_type)
    print("✅ Done!")


if __name__ == "__main__":
    main()

