#!/usr/bin/env python3
"""Verify extracted principles."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db_sync
from models import CoachingKnowledgeEntry
import json

db = get_db_sync()
entries = db.query(CoachingKnowledgeEntry).filter(
    CoachingKnowledgeEntry.source == "Daniels' Running Formula",
    CoachingKnowledgeEntry.extracted_principles.isnot(None)
).all()

print(f"Found {len(entries)} principle entries:\n")

for i, entry in enumerate(entries, 1):
    print(f"{i}. Type: {entry.principle_type}")
    data = json.loads(entry.extracted_principles)
    print(f"   Keys: {list(data.keys())}")
    
    # Show sample data
    for key, value in list(data.items())[:2]:
        if isinstance(value, list) and value:
            print(f"   {key}: {len(value)} items - {str(value[0])[:100]}...")
        elif isinstance(value, dict) and value:
            print(f"   {key}: {len(value)} items")
        elif value:
            print(f"   {key}: {str(value)[:100]}...")
    print()

db.close()

