#!/usr/bin/env python3
"""Check knowledge base status."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db_sync
from models import CoachingKnowledgeEntry

db = get_db_sync()

total = db.query(CoachingKnowledgeEntry).count()
pfitz = db.query(CoachingKnowledgeEntry).filter(
    CoachingKnowledgeEntry.source == 'Advanced Marathoning 4th Edition'
).count()
daniels = db.query(CoachingKnowledgeEntry).filter(
    CoachingKnowledgeEntry.source == "Daniels' Running Formula"
).count()

pfitz_principles = db.query(CoachingKnowledgeEntry).filter(
    CoachingKnowledgeEntry.source == 'Advanced Marathoning 4th Edition',
    CoachingKnowledgeEntry.extracted_principles.isnot(None)
).count()

daniels_principles = db.query(CoachingKnowledgeEntry).filter(
    CoachingKnowledgeEntry.source == "Daniels' Running Formula",
    CoachingKnowledgeEntry.extracted_principles.isnot(None)
).count()

print(f"📚 Knowledge Base Status:")
print(f"   Total entries: {total}")
print(f"")

# Get all unique sources
all_sources = db.query(CoachingKnowledgeEntry.source).distinct().all()
for source_tuple in all_sources:
    source = source_tuple[0]
    source_total = db.query(CoachingKnowledgeEntry).filter(
        CoachingKnowledgeEntry.source == source
    ).count()
    source_principles = db.query(CoachingKnowledgeEntry).filter(
        CoachingKnowledgeEntry.source == source,
        CoachingKnowledgeEntry.extracted_principles.isnot(None)
    ).count()
    source_plans = db.query(CoachingKnowledgeEntry).filter(
        CoachingKnowledgeEntry.source == source,
        CoachingKnowledgeEntry.principle_type == 'training_plan'
    ).count()
    
    print(f"   📖 {source}:")
    print(f"      - Total entries: {source_total}")
    print(f"      - Principle entries: {source_principles}")
    print(f"      - Training plans: {source_plans}")
    print(f"")

db.close()

