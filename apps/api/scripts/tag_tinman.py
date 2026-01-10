#!/usr/bin/env python3
"""Tag Tinman pace chart entry."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db_sync
from models import CoachingKnowledgeEntry

db = get_db_sync()
try:
    entry = db.query(CoachingKnowledgeEntry).filter(
        CoachingKnowledgeEntry.methodology == 'Tinman'
    ).first()
    
    if entry:
        entry.tags = ['pace_chart', 'equivalent_times', 'tinman', 'reference']
        db.commit()
        print('✅ Tagged Tinman entry')
    else:
        print('❌ Tinman entry not found')
finally:
    db.close()

