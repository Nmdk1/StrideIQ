#!/usr/bin/env python3
"""View extracted VDOT data from knowledge base."""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db_sync
from models import CoachingKnowledgeEntry

def main():
    db = get_db_sync()
    try:
        entry = db.query(CoachingKnowledgeEntry).filter(
            CoachingKnowledgeEntry.principle_type == "vdot_exact"
        ).first()
        
        if not entry:
            print("❌ No VDOT extraction found")
            return
        
        data = json.loads(entry.extracted_principles) if entry.extracted_principles else {}
        
        print("=" * 60)
        print("EXTRACTED VDOT DATA SUMMARY")
        print("=" * 60)
        
        formulas = data.get("formulas", {})
        print(f"\n📐 FORMULAS:")
        print(f"  Calculation methods: {len(formulas.get('calculation_methods', []))}")
        if formulas.get('calculation_methods'):
            print(f"    Sample: {formulas['calculation_methods'][0][:200]}...")
        print(f"  Regression equations: {len(formulas.get('regression_equations', []))}")
        if formulas.get('regression_equations'):
            print(f"    Sample: {formulas['regression_equations'][0][:200]}...")
        print(f"  Percentage formulas: {len(formulas.get('percentage_formulas', []))}")
        
        pace_tables = data.get("pace_tables", {})
        print(f"\n🏃 PACE TABLES:")
        print(f"  E pace entries: {len(pace_tables.get('e_pace', []))}")
        print(f"  M pace entries: {len(pace_tables.get('m_pace', []))}")
        print(f"  T pace entries: {len(pace_tables.get('t_pace', []))}")
        print(f"  I pace entries: {len(pace_tables.get('i_pace', []))}")
        print(f"  R pace entries: {len(pace_tables.get('r_pace', []))}")
        print(f"  Pace definitions: {len(pace_tables.get('pace_definitions', {}))}")
        print(f"  Tabular data: {len(pace_tables.get('tabular_data', []))}")
        
        equivalent = data.get("equivalent_tables", {})
        print(f"\n⏱️ EQUIVALENT PERFORMANCE TABLES:")
        print(f"  VDOT to race times: {len(equivalent.get('vdot_to_race_times', []))}")
        print(f"  Equivalent performances: {len(equivalent.get('equivalent_performances', []))}")
        
        zones = data.get("zone_formulas", {})
        print(f"\n📊 ZONE FORMULAS:")
        print(f"  Zone relationships: {len(zones.get('zone_relationships', []))}")
        if zones.get('zone_relationships'):
            print(f"    Sample: {zones['zone_relationships'][0][:200]}...")
        
        print("\n" + "=" * 60)
        
    finally:
        db.close()

if __name__ == "__main__":
    main()

