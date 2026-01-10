#!/usr/bin/env python3
"""Audit training plan structure in knowledge base."""
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db_sync
from models import CoachingKnowledgeEntry

def audit_plans():
    db = get_db_sync()
    try:
        plans = db.query(CoachingKnowledgeEntry).filter(
            CoachingKnowledgeEntry.principle_type == 'training_plan'
        ).limit(5).all()
        
        print(f'Found {len(plans)} training plans\n')
        print('=' * 70)
        print('PLAN STRUCTURE AUDIT')
        print('=' * 70)
        
        structured_count = 0
        unstructured_count = 0
        
        for i, plan in enumerate(plans, 1):
            print(f'\nPlan {i}:')
            print(f'  Source: {plan.source}')
            print(f'  Methodology: {plan.methodology}')
            print(f'  Has extracted_principles: {plan.extracted_principles is not None}')
            
            if plan.extracted_principles:
                try:
                    principles = json.loads(plan.extracted_principles)
                    print(f'  Principles type: {type(principles).__name__}')
                    
                    if isinstance(principles, dict):
                        print(f'  Keys: {list(principles.keys())[:10]}')
                        has_weeks = "weeks" in principles or "week" in str(principles.keys()).lower()
                        has_phases = "phases" in principles or "phase" in str(principles.keys()).lower()
                        has_workouts = "workout" in str(principles.keys()).lower()
                        
                        print(f'  Has weeks structure: {has_weeks}')
                        print(f'  Has phases: {has_phases}')
                        print(f'  Has workouts: {has_workouts}')
                        
                        if has_weeks or has_phases:
                            structured_count += 1
                            print(f'  ✅ STRUCTURED')
                        else:
                            unstructured_count += 1
                            print(f'  ⚠️  UNSTRUCTURED (has principles but no week structure)')
                    else:
                        unstructured_count += 1
                        print(f'  ⚠️  UNSTRUCTURED (principles not a dict)')
                except Exception as e:
                    unstructured_count += 1
                    print(f'  ❌ Parse error: {e}')
            else:
                unstructured_count += 1
                print(f'  ⚠️  UNSTRUCTURED (no extracted_principles)')
            
            text_len = len(plan.text_chunk) if plan.text_chunk else 0
            print(f'  Text chunk length: {text_len} chars')
            if plan.text_chunk:
                preview = plan.text_chunk[:150].replace('\n', ' ')
                print(f'  Preview: {preview}...')
        
        print('\n' + '=' * 70)
        print('SUMMARY')
        print('=' * 70)
        print(f'Structured plans: {structured_count}')
        print(f'Unstructured plans: {unstructured_count}')
        print(f'Total audited: {len(plans)}')
        
        if structured_count > 0:
            print('\n✅ Some plans are structured - can build synthesis')
        elif unstructured_count == len(plans):
            print('\n⚠️  All plans are unstructured - need to enhance extraction or generate from principles')
        
    finally:
        db.close()

if __name__ == "__main__":
    audit_plans()

