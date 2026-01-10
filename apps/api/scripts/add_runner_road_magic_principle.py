"""
Add "Runner Road (or Trail) Magic Alternation" Principle to Knowledge Base

This is a custom principle derived from real-world athlete data (founder: 57, full-time work, 70 mpw).
Treats as high-weight custom principle alongside Daniels, Pfitzinger, Canova, etc.
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

# Add the parent directory to the sys.path to allow imports from apps.api
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db_sync
from models import CoachingKnowledgeEntry

def add_runner_road_magic_principle():
    """Add the Runner Road Magic Alternation principle to the knowledge base."""
    db = get_db_sync()
    
    try:
        # Check if entry already exists
        existing = db.query(CoachingKnowledgeEntry).filter(
            CoachingKnowledgeEntry.methodology == "Runner Road Magic",
            CoachingKnowledgeEntry.principle_type == "periodization_principle"
        ).first()
        
        if existing:
            print("✅ Runner Road Magic principle already exists in knowledge base.")
            print(f"   Entry ID: {existing.id}")
            return
        
        # Create the principle entry
        principle_text = """
Runner Road (or Trail) Magic Alternation

DESCRIPTION:
Alternate training focus to achieve deeper adaptation, prevent staleness, and sustain high mileage with lower overreach risk.

CORE PRINCIPLES:
1. Monthly or weekly alternation: Cycle between threshold-focused blocks (lactate clearance, tempo/threshold work) and interval-focused blocks (VO2max/speed, 5K/10K pace intervals).

2. Long run restraint: Avoid marathon-pace or faster segments in long runs during quality-heavy weeks. Reserve MP+ longs for every 3rd week (or less) to protect recovery and allow full effort in weekly quality sessions.

BENEFITS (from real-world data):
- Greater sustainability at high mileage (70+ mpw with full-time work)
- Deeper adaptation per stimulus type (threshold vs. intervals)
- Reduced chronic stress and injury risk
- Consistent efficiency gains and enjoyment

APPLICATION:
- Tier 2 Fixed Plans: Apply as default "sustainable rotation" template when user volume is high or risk tolerance is conservative/balanced.
  Example cycle: Week 1 threshold focus, Week 2 interval focus, Week 3 mixed/recovery with MP long.
  Scale frequency based on user input (runs/week, mileage history).

- Tier 3/4 Subscription Coaching: Analyze Strava history for response to threshold vs. interval weeks. If alternation shows superior efficiency gains, bias plan toward this pattern.

EVIDENCE BASE:
Derived from athlete data: 57 years old, full-time work, 70 mpw sustained with consistent efficiency gains and injury-free training.
"""
        
        extracted_principles = {
            "principle_name": "Runner Road Magic Alternation",
            "alternation_pattern": {
                "threshold_week": {
                    "focus": "Lactate clearance, tempo/threshold work",
                    "long_run": "Easy to moderate pace, no MP+ segments"
                },
                "interval_week": {
                    "focus": "VO2max/speed, 5K/10K pace intervals",
                    "long_run": "Easy to moderate pace, no MP+ segments"
                },
                "mp_long_week": {
                    "frequency": "Every 3rd week or less",
                    "long_run": "Marathon pace or faster segments included",
                    "quality_sessions": "Reduced intensity to allow full effort in long run"
                }
            },
            "application_rules": {
                "high_volume": "Apply as default for 60+ mpw",
                "masters_athletes": "Higher weight for athletes 50+",
                "full_time_work": "Favor for athletes with work constraints",
                "conservative_risk": "Apply when risk tolerance is balanced/conservative"
            },
            "benefits": [
                "Greater sustainability at high mileage",
                "Deeper adaptation per stimulus type",
                "Reduced chronic stress and injury risk",
                "Consistent efficiency gains"
            ]
        }
        
        entry = CoachingKnowledgeEntry(
            source="Runner Road Magic (Custom Principle)",
            source_type="custom_principle",
            methodology="Runner Road Magic",
            principle_type="periodization_principle",
            text_chunk=principle_text.strip(),
            extracted_principles=json.dumps(extracted_principles),
            tags=["alternation", "periodization", "long_run", "threshold", "intervals", "sustainability", "high_mileage", "masters", "work_life_balance"]
        )
        
        db.add(entry)
        db.commit()
        db.refresh(entry)
        
        print("======================================================================")
        print("✅ Runner Road Magic Alternation Principle Added to Knowledge Base")
        print("======================================================================")
        print(f"Entry ID: {entry.id}")
        print(f"Methodology: {entry.methodology}")
        print(f"Principle Type: {entry.principle_type}")
        print(f"Tags: {entry.tags}")
        print("======================================================================")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error adding Runner Road Magic principle: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    add_runner_road_magic_principle()

