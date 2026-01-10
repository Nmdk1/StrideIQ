#!/usr/bin/env python3
"""Check Culp/Norwegian Method entries in knowledge base."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db_sync
from models import CoachingKnowledgeEntry

db = get_db_sync()
try:
    culp_entries = db.query(CoachingKnowledgeEntry).filter(
        CoachingKnowledgeEntry.methodology == 'Culp'
    ).all()
    
    print(f"Norwegian Method (Culp) entries: {len(culp_entries)}")
    print("\nBreakdown by type:")
    
    by_type = {}
    for e in culp_entries:
        ptype = e.principle_type or "unknown"
        by_type[ptype] = by_type.get(ptype, 0) + 1
    
    for ptype, count in sorted(by_type.items()):
        print(f"  {ptype}: {count}")
    
    print("\nSample entries:")
    for i, e in enumerate(culp_entries[:5], 1):
        print(f"\n{i}. Type: {e.principle_type}")
        print(f"   Source: {e.source[:80]}...")
        print(f"   Text: {e.text_chunk[:200]}...")
        print(f"   Tags: {e.tags}")
finally:
    db.close()

