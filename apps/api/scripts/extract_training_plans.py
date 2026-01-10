#!/usr/bin/env python3
"""
Extract Training Plans Script

Extracts structured training plans from coaching books.
Looks for week-by-week schedules, phase-based plans, and workout prescriptions.
"""
import sys
import os
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db_sync
from models import CoachingKnowledgeEntry


def find_training_plan_sections(text: str) -> List[Dict]:
    """
    Find training plan sections in text.
    
    Looks for:
    - Week-by-week schedules
    - Phase-based plans (base, build, peak, taper)
    - Structured workout prescriptions
    - Distance/time targets
    """
    plans = []
    
    # Pattern 1: Week-by-week plans
    # Look for "Week 1", "Week 2", etc. followed by structured content
    week_pattern = r"(?:Week|WEEK)\s+(\d+)[:\-]?\s*([^\n]{50,2000})"
    week_matches = list(re.finditer(week_pattern, text, re.IGNORECASE | re.MULTILINE))
    
    if len(week_matches) >= 4:  # At least 4 weeks indicates a plan
        weeks = []
        for match in week_matches:
            week_num = match.group(1)
            week_content = match.group(2).strip()
            # Look for workout details in this week
            workouts = extract_workouts_from_text(week_content)
            weeks.append({
                "week": int(week_num),
                "content": week_content[:1000],  # Limit length
                "workouts": workouts
            })
        
        if weeks:
            plans.append({
                "type": "weekly_plan",
                "weeks": weeks,
                "total_weeks": len(weeks)
            })
    
    # Pattern 2: Phase-based plans
    # Look for phases like "Base Phase", "Build Phase", "Peak Phase", "Taper Phase"
    phase_keywords = ["base", "build", "peak", "taper", "recovery", "sharpening", "maintenance"]
    phase_pattern = r"((?:{})\s+phase[^\.\n]{{20,1500}})".format("|".join(phase_keywords))
    phase_matches = list(re.finditer(phase_pattern, text, re.IGNORECASE))
    
    if len(phase_matches) >= 2:  # At least 2 phases
        phases = []
        for match in phase_matches:
            phase_text = match.group(1)
            phase_name = extract_phase_name(phase_text)
            workouts = extract_workouts_from_text(phase_text)
            duration = extract_duration(phase_text)
            
            phases.append({
                "phase": phase_name,
                "duration": duration,
                "content": phase_text[:1000],
                "workouts": workouts
            })
        
        if phases:
            plans.append({
                "type": "phase_based_plan",
                "phases": phases
            })
    
    # Pattern 3: Structured training schedules
    # Look for tables or structured lists with distances, paces, times
    schedule_patterns = [
        r"(?:training\s+)?schedule[^\.\n]{50,2000}",
        r"(?:training\s+)?program[^\.\n]{50,2000}",
        r"(?:race\s+)?preparation[^\.\n]{50,2000}"
    ]
    
    for pattern in schedule_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            schedule_text = match.group(0)
            # Check if it contains structured data (numbers, distances, paces)
            if has_structured_data(schedule_text):
                workouts = extract_workouts_from_text(schedule_text)
                plans.append({
                    "type": "training_schedule",
                    "content": schedule_text[:1500],
                    "workouts": workouts
                })
                break  # Only take first match per pattern
    
    # Pattern 4: Specific distance plans (5K, 10K, Marathon, etc.)
    distance_pattern = r"((?:\d+[kmKM]|marathon|half[\s-]?marathon|5K|10K)[^\.\n]{50,2000})"
    distance_matches = re.finditer(distance_pattern, text, re.IGNORECASE)
    
    distance_plans = {}
    for match in distance_matches:
        plan_text = match.group(1)
        # Extract distance type
        distance_type = extract_distance_type(plan_text)
        if distance_type and has_structured_data(plan_text):
            if distance_type not in distance_plans:
                distance_plans[distance_type] = []
            workouts = extract_workouts_from_text(plan_text)
            distance_plans[distance_type].append({
                "content": plan_text[:1000],
                "workouts": workouts
            })
    
    for distance, plan_list in distance_plans.items():
        if len(plan_list) > 0:
            plans.append({
                "type": f"distance_plan_{distance}",
                "distance": distance,
                "plans": plan_list
            })
    
    return plans


def extract_workouts_from_text(text: str) -> List[Dict]:
    """Extract workout prescriptions from text."""
    workouts = []
    seen = set()
    
    # Look for workout patterns:
    # - Distance + pace (e.g., "5 miles at 7:00 pace")
    # - Time + intensity (e.g., "30 minutes easy")
    # - Intervals (e.g., "6 x 800m at 5K pace")
    # - Tempo runs (e.g., "20 minutes tempo")
    
    # Interval pattern - more flexible
    interval_patterns = [
        r"(\d+)\s*x\s*([\d\.]+)\s*(?:mile|mi|km|m|meter|minute|min)[^\.\n]{0,150}",
        r"(\d+)\s*(?:x|×)\s*([\d\.]+)[^\.\n]{0,100}(?:pace|speed|effort)",
        r"(\d+)\s*repeats?[^\.\n]{0,150}",
        r"(\d+)\s*intervals?[^\.\n]{0,150}"
    ]
    
    for pattern in interval_patterns:
        intervals = re.finditer(pattern, text, re.IGNORECASE)
        for match in intervals:
            workout_text = match.group(0)[:250].strip()
            if workout_text not in seen and len(workout_text) > 10:
                seen.add(workout_text)
                workouts.append({
                    "type": "interval",
                    "prescription": workout_text
                })
    
    # Tempo pattern - more flexible
    tempo_patterns = [
        r"(\d+)\s*(?:minute|min|mile|mi|km)[^\.\n]{0,80}(?:tempo|threshold|T pace|T-pace|LT)[^\.\n]{0,100}",
        r"tempo[^\.\n]{0,150}",
        r"threshold[^\.\n]{0,150}"
    ]
    
    for pattern in tempo_patterns:
        tempos = re.finditer(pattern, text, re.IGNORECASE)
        for match in tempos:
            workout_text = match.group(0)[:250].strip()
            if workout_text not in seen and len(workout_text) > 10:
                seen.add(workout_text)
                workouts.append({
                    "type": "tempo",
                    "prescription": workout_text
                })
    
    # Long run pattern
    long_run_patterns = [
        r"(\d+)[\s\-]?(?:mile|mi|km|minute|min)[^\.\n]{0,80}(?:long|easy|E pace|LSD|aerobic)[^\.\n]{0,100}",
        r"long\s+run[^\.\n]{0,150}",
        r"(\d+)[\s\-]?mile[^\.\n]{0,100}"
    ]
    
    for pattern in long_run_patterns:
        long_runs = re.finditer(pattern, text, re.IGNORECASE)
        for match in long_runs:
            workout_text = match.group(0)[:250].strip()
            if workout_text not in seen and len(workout_text) > 10:
                seen.add(workout_text)
                workouts.append({
                    "type": "long_run",
                    "prescription": workout_text
                })
    
    # Pace-based workouts
    pace_patterns = [
        r"([\d\.]+)\s*(?:mile|mi|km)[^\.\n]{0,80}(?:at|@|pace)[^\.\n]{0,100}([\d:]+/[^\s]+)",
        r"([\d:]+)\s*(?:per|/)\s*(?:mile|mi|km)[^\.\n]{0,150}",
        r"pace[^\.\n]{0,150}(?:[\d:]+|E|M|T|I|R)"
    ]
    
    for pattern in pace_patterns:
        paces = re.finditer(pattern, text, re.IGNORECASE)
        for match in paces:
            workout_text = match.group(0)[:250].strip()
            if workout_text not in seen and len(workout_text) > 10:
                seen.add(workout_text)
                workouts.append({
                    "type": "pace_based",
                    "prescription": workout_text
                })
    
    # Look for structured workout lines (often in tables)
    # Pattern: Day + workout description
    structured_pattern = r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)[^\.\n]{20,200}"
    structured = re.finditer(structured_pattern, text, re.IGNORECASE)
    for match in structured:
        workout_text = match.group(0)[:250].strip()
        # Check if it contains workout indicators
        if any(keyword in workout_text.lower() for keyword in ["mile", "km", "pace", "tempo", "interval", "easy", "run"]):
            if workout_text not in seen and len(workout_text) > 20:
                seen.add(workout_text)
                workouts.append({
                    "type": "structured_workout",
                    "prescription": workout_text
                })
    
    return workouts[:30]  # Limit to 30 workouts per section


def extract_phase_name(text: str) -> str:
    """Extract phase name from text."""
    phase_keywords = ["base", "build", "peak", "taper", "recovery", "sharpening", "maintenance"]
    for keyword in phase_keywords:
        if keyword.lower() in text.lower():
            return keyword.capitalize()
    return "Unknown"


def extract_duration(text: str) -> Optional[str]:
    """Extract duration from text (e.g., '4 weeks', '2 months')."""
    duration_pattern = r"(\d+)\s*(?:week|month|day)"
    match = re.search(duration_pattern, text, re.IGNORECASE)
    if match:
        return match.group(0)
    return None


def extract_distance_type(text: str) -> Optional[str]:
    """Extract distance type from text."""
    distances = {
        "5K": r"5[\s\-]?K|5k",
        "10K": r"10[\s\-]?K|10k",
        "half_marathon": r"half[\s\-]?marathon|21\.1|13\.1",
        "marathon": r"marathon|26\.2|42\.2",
        "mile": r"mile",
        "1500m": r"1500[\s\-]?m"
    }
    
    for dist_name, pattern in distances.items():
        if re.search(pattern, text, re.IGNORECASE):
            return dist_name
    return None


def has_structured_data(text: str) -> bool:
    """Check if text contains structured training data."""
    # Look for numbers (distances, times, paces)
    numbers = re.findall(r'\d+', text)
    if len(numbers) < 3:  # Need at least 3 numbers
        return False
    
    # Look for workout indicators
    workout_keywords = ["mile", "km", "minute", "pace", "tempo", "interval", "repeat", "x"]
    has_keywords = any(keyword in text.lower() for keyword in workout_keywords)
    
    return has_keywords


def extract_and_store_plans(text_file: str, source: str, methodology: str):
    """Extract training plans from text file and store in database."""
    db = get_db_sync()
    try:
        # Read text
        print(f"Reading {text_file}...")
        with open(text_file, 'r', encoding='utf-8') as f:
            text = f.read()
        
        # Remove NUL characters
        text = text.replace('\x00', '')
        
        print(f"Text length: {len(text)} characters")
        print("Searching for training plans...")
        
        # Extract plans
        plans = find_training_plan_sections(text)
        
        if not plans:
            print("⚠️  No structured training plans found")
            print("   Trying alternative extraction method...")
            # Try extracting any section with "plan" or "schedule" in title
            plan_sections = re.finditer(
                r"([^\n]{0,100}(?:plan|schedule|program)[^\n]{50,2000})",
                text,
                re.IGNORECASE
            )
            alt_plans = []
            for match in plan_sections:
                plan_text = match.group(1)
                if has_structured_data(plan_text):
                    alt_plans.append({
                        "type": "general_plan",
                        "content": plan_text[:1500]
                    })
            plans = alt_plans
        
        print(f"Found {len(plans)} training plan sections")
        
        # Store each plan
        for i, plan in enumerate(plans):
            entry = CoachingKnowledgeEntry(
                source=source,
                methodology=methodology,
                source_type="book",
                text_chunk=json.dumps(plan)[:2000],  # Store plan structure
                extracted_principles=json.dumps(plan),
                principle_type="training_plan"
            )
            db.add(entry)
            print(f"  ✅ Stored plan {i+1}: {plan.get('type', 'unknown')} type")
        
        db.commit()
        print(f"\n✅ Stored {len(plans)} training plans!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


def main():
    """Main function."""
    if len(sys.argv) < 4:
        print("Usage: python extract_training_plans.py <text_file> <source> <methodology>")
        print("\nExample:")
        print("  python extract_training_plans.py /books/daniels.txt 'Daniels Running Formula' 'Daniels'")
        sys.exit(1)
    
    text_file = sys.argv[1]
    source = sys.argv[2]
    methodology = sys.argv[3]
    
    extract_and_store_plans(text_file, source, methodology)
    print("✅ Done!")


if __name__ == "__main__":
    main()

