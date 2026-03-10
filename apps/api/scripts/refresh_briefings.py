"""Targeted home briefing refresh for all athletes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import SessionLocal
from models import Athlete
from services.home_briefing_cache import mark_briefing_dirty
from tasks.home_briefing_tasks import enqueue_briefing_refresh

db = SessionLocal()
for a in db.query(Athlete).all():
    aid = str(a.id)
    mark_briefing_dirty(aid)
    enqueue_briefing_refresh(aid, force=True, allow_circuit_probe=True)
print("Targeted briefing refresh queued for all athletes")
db.close()
