#!/usr/bin/env python3
"""
Tag Knowledge Base Entries with Shared Concepts

Tags all entries with cross-methodology concepts for queryable knowledge base.
Uses pattern matching to identify shared concepts across methodologies.

Tag Taxonomy:
- Intensity zones: threshold, aerobic, anaerobic, vo2max, lactate_threshold
- Training types: long_run, tempo, intervals, fartlek, recovery_run, hill_workout
- Periodization: base_building, specific_endurance, taper, recovery_week, peak
- Load management: volume_progression, intensity_progression, load_efficiency, acute_chronic
- Recovery: recovery_time, recovery_guidelines, adaptation_period
- Concepts: vdot, pace_tables, training_zones, workout_prescription
"""
import sys
import json
import re
from pathlib import Path
from typing import List, Set, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db_sync
from models import CoachingKnowledgeEntry


# Tag taxonomy with pattern matching rules
TAG_PATTERNS = {
    # Intensity zones
    "threshold": [
        r"\bthreshold\b",
        r"\bt\s+pace\b",
        r"\btempo\s+pace\b",
        r"\blactate\s+threshold\b",
        r"\banaerobic\s+threshold\b",
    ],
    "aerobic": [
        r"\baerobic\s+pace\b",
        r"\beasy\s+pace\b",
        r"\be\s+pace\b",
        r"\baerobic\s+base\b",
        r"\baerobic\s+capacity\b",
    ],
    "anaerobic": [
        r"\banaerobic\b",
        r"\banaerobic\s+capacity\b",
        r"\banaerobic\s+power\b",
    ],
    "vo2max": [
        r"\bvo2\s*max\b",
        r"\bvo2max\b",
        r"\bmaximal\s+oxygen\s+uptake\b",
        r"\bi\s+pace\b",  # Interval pace is typically VO2max
    ],
    "lactate_threshold": [
        r"\blactate\s+threshold\b",
        r"\blt\b",
        r"\banaerobic\s+threshold\b",
    ],
    
    # Training types
    "long_run": [
        r"\blong\s+run\b",
        r"\blong\s+running\b",
        r"\blong\s+slow\s+distance\b",
        r"\blsd\b",
    ],
    "tempo": [
        r"\btempo\s+run\b",
        r"\btempo\s+pace\b",
        r"\bcomfortably\s+hard\b",
        r"\bsteady\s+state\b",
    ],
    "intervals": [
        r"\binterval\s+training\b",
        r"\binterval\s+run\b",
        r"\bi\s+pace\b",
        r"\brepetition\s+intervals\b",
    ],
    "fartlek": [
        r"\bfartlek\b",
        r"\bspeed\s+play\b",
    ],
    "recovery_run": [
        r"\brecovery\s+run\b",
        r"\brecovery\s+pace\b",
        r"\beasy\s+recovery\b",
    ],
    "hill_workout": [
        r"\bhill\s+workout\b",
        r"\bhill\s+training\b",
        r"\bhill\s+repeats\b",
        r"\buphill\s+training\b",
    ],
    
    # Periodization
    "base_building": [
        r"\bbase\s+building\b",
        r"\baerobic\s+base\b",
        r"\bbase\s+phase\b",
        r"\bfoundation\s+phase\b",
    ],
    "specific_endurance": [
        r"\bspecific\s+endurance\b",
        r"\brace\s+specific\s+training\b",
        r"\bspecial\s+endurance\b",
    ],
    "taper": [
        r"\btaper\b",
        r"\btapering\b",
        r"\bpre\s+race\s+phase\b",
    ],
    "recovery_week": [
        r"\brecovery\s+week\b",
        r"\brest\s+week\b",
        r"\beasy\s+week\b",
    ],
    "peak": [
        r"\bpeak\s+phase\b",
        r"\bpeaking\b",
        r"\bpeak\s+performance\b",
    ],
    
    # Load management
    "volume_progression": [
        r"\bvolume\s+progression\b",
        r"\bincreasing\s+mileage\b",
        r"\bweekly\s+mileage\b",
        r"\bvolume\s+increase\b",
    ],
    "intensity_progression": [
        r"\bintensity\s+progression\b",
        r"\bincreasing\s+intensity\b",
        r"\bpace\s+progression\b",
    ],
    "load_efficiency": [
        r"\bload\s+efficiency\b",
        r"\btraining\s+load\b",
        r"\bacute\s+vs\s+chronic\b",
    ],
    "acute_chronic": [
        r"\bacute\s+load\b",
        r"\bchronic\s+load\b",
        r"\bacute\s+to\s+chronic\s+ratio\b",
    ],
    
    # Recovery
    "recovery_time": [
        r"\brecovery\s+time\b",
        r"\brest\s+period\b",
        r"\brecovery\s+between\s+sessions\b",
    ],
    "recovery_guidelines": [
        r"\brecovery\s+guidelines\b",
        r"\brecovery\s+principles\b",
        r"\brest\s+guidelines\b",
    ],
    "adaptation_period": [
        r"\badaptation\s+period\b",
        r"\bsupercompensation\b",
        r"\brecovery\s+and\s+adaptation\b",
    ],
    
    # Concepts
    "vdot": [
        r"\bvdot\b",
        r"\bjack\s+daniels\b",
        r"\bvdoto2\b",
    ],
    "pace_tables": [
        r"\bpace\s+table\b",
        r"\btraining\s+pace\s+table\b",
        r"\bpace\s+chart\b",
    ],
    "training_zones": [
        r"\btraining\s+zone\b",
        r"\bpace\s+zone\b",
        r"\bintensity\s+zone\b",
    ],
    "workout_prescription": [
        r"\bworkout\s+prescription\b",
        r"\bworkout\s+design\b",
        r"\bsession\s+planning\b",
    ],
}


def extract_tags(text: str, methodology: str) -> Set[str]:
    """
    Extract tags from text using pattern matching.
    
    Returns set of tag strings that match patterns in the text.
    """
    tags = set()
    text_lower = text.lower()
    
    # Add methodology as a tag
    tags.add(methodology.lower())
    
    # Check each tag pattern
    for tag, patterns in TAG_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                tags.add(tag)
                break  # Found one match, move to next tag
    
    return tags


def tag_all_entries():
    """Tag all knowledge base entries."""
    db = get_db_sync()
    try:
        entries = db.query(CoachingKnowledgeEntry).all()
        print(f"Found {len(entries)} entries to tag")
        
        tagged_count = 0
        total_tags = 0
        
        for entry in entries:
            # Combine text sources for tagging
            text_sources = []
            if entry.text_chunk:
                text_sources.append(entry.text_chunk)
            if entry.extracted_principles:
                try:
                    principles = json.loads(entry.extracted_principles)
                    # Extract text from principles JSON
                    principles_text = json.dumps(principles)
                    text_sources.append(principles_text)
                except:
                    pass
            
            combined_text = " ".join(text_sources)
            
            if not combined_text:
                continue
            
            # Extract tags
            tags = extract_tags(combined_text, entry.methodology)
            
            # Convert to sorted list for JSONB storage
            tags_list = sorted(list(tags))
            
            if tags_list:
                entry.tags = tags_list
                total_tags += len(tags_list)
                tagged_count += 1
                
                if tagged_count % 50 == 0:
                    print(f"  Tagged {tagged_count}/{len(entries)} entries...")
        
        db.commit()
        
        print(f"\n✅ Tagging complete!")
        print(f"   Tagged {tagged_count} entries")
        print(f"   Total tags assigned: {total_tags}")
        print(f"   Average tags per entry: {total_tags / tagged_count if tagged_count > 0 else 0:.1f}")
        
    except Exception as e:
        print(f"❌ Error tagging entries: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


def show_tag_statistics():
    """Show statistics about tags."""
    db = get_db_sync()
    try:
        entries = db.query(CoachingKnowledgeEntry).all()
        
        tag_counts = {}
        methodology_tags = {}
        
        for entry in entries:
            if entry.tags:
                tags = entry.tags if isinstance(entry.tags, list) else json.loads(entry.tags) if isinstance(entry.tags, str) else []
                
                for tag in tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
                
                methodology = entry.methodology
                if methodology not in methodology_tags:
                    methodology_tags[methodology] = {}
                for tag in tags:
                    methodology_tags[methodology][tag] = methodology_tags[methodology].get(tag, 0) + 1
        
        print("\n" + "=" * 60)
        print("TAG STATISTICS")
        print("=" * 60)
        
        print(f"\n📊 Top Tags (by frequency):")
        sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
        for tag, count in sorted_tags[:20]:
            print(f"   {tag}: {count} entries")
        
        print(f"\n📚 Tags by Methodology:")
        for methodology, tags in methodology_tags.items():
            print(f"   {methodology}: {len(tags)} unique tags")
        
    finally:
        db.close()


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Tag knowledge base entries")
    parser.add_argument("--stats", action="store_true", help="Show tag statistics only")
    args = parser.parse_args()
    
    if args.stats:
        show_tag_statistics()
    else:
        print("=" * 60)
        print("TAGGING KNOWLEDGE BASE ENTRIES")
        print("=" * 60)
        tag_all_entries()
        print("\n" + "=" * 60)
        show_tag_statistics()


if __name__ == "__main__":
    main()

