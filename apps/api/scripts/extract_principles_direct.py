#!/usr/bin/env python3
"""
Direct Principle Extraction Script

Extracts coaching principles from text using pattern matching and analysis.
No external AI APIs needed - uses direct text analysis.
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


def extract_rpi_principles(text: str) -> Dict:
    """Extract RPI-related principles from text."""
    principles = {
        "rpi_formula": None,
        "pace_definitions": {},
        "training_zones": {},
        "pace_tables": {}
    }
    
    # Look for RPI calculation mentions
    rpi_patterns = [
        r"RPI\s*[=:]\s*([^\.\n]+)",
        r"calculate.*RPI[^\.\n]*",
        r"RPI.*formula[^\.\n]*"
    ]
    
    for pattern in rpi_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            if not principles["rpi_formula"]:
                principles["rpi_formula"] = match.group(0)[:500]
    
    # Extract pace definitions (E, M, T, I, R)
    pace_types = ["E", "M", "T", "I", "R", "Easy", "Marathon", "Threshold", "Interval", "Repetition"]
    
    for pace_type in pace_types:
        # Look for definitions like "E pace is..." or "Easy pace means..."
        pattern = rf"{pace_type}\s+pace[^\.\n]*?([^\.\n]{{50,300}})"
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            key = pace_type.upper() if len(pace_type) == 1 else pace_type
            if key not in principles["pace_definitions"]:
                principles["pace_definitions"][key] = match.group(0)[:500]
    
    return principles


def extract_periodization_principles(text: str) -> Dict:
    """Extract periodization and training phase principles."""
    principles = {
        "phases": [],
        "phase_duration": {},
        "progression_rules": []
    }
    
    # Look for training phases
    phase_keywords = ["base", "build", "peak", "taper", "recovery", "phase", "period"]
    
    phase_pattern = r"(?:training\s+)?(?:phase|period|stage)[^\.\n]*?([^\.\n]{50,300})"
    matches = re.finditer(phase_pattern, text, re.IGNORECASE)
    
    for match in matches:
        phase_text = match.group(0)
        if any(keyword in phase_text.lower() for keyword in phase_keywords):
            principles["phases"].append(phase_text[:500])
            if len(principles["phases"]) >= 10:  # Limit to avoid too much
                break
    
    # Look for duration guidelines
    duration_pattern = r"(\d+)\s*(?:week|month|day).*?(?:phase|period|training)[^\.\n]*"
    matches = re.finditer(duration_pattern, text, re.IGNORECASE)
    for match in matches:
        duration_text = match.group(0)
        principles["phase_duration"][duration_text[:200]] = duration_text
    
    return principles


def extract_training_principles(text: str) -> Dict:
    """Extract general training principles."""
    principles = {
        "core_principles": [],
        "workout_types": [],
        "recovery_guidelines": [],
        "intensity_guidelines": []
    }
    
    # Look for key principles (sentences with "should", "must", "important", etc.)
    principle_keywords = ["should", "must", "important", "principle", "rule", "guideline"]
    
    sentences = re.split(r'[\.!?]\s+', text)
    for sentence in sentences:
        if any(keyword in sentence.lower() for keyword in principle_keywords):
            if len(sentence) > 30 and len(sentence) < 500:
                principles["core_principles"].append(sentence.strip())
                if len(principles["core_principles"]) >= 50:
                    break
    
    # Look for workout types
    workout_keywords = ["workout", "session", "run", "training", "interval", "tempo", "long run"]
    for sentence in sentences:
        if any(keyword in sentence.lower() for keyword in workout_keywords):
            if "pace" in sentence.lower() or "intensity" in sentence.lower():
                if len(sentence) > 40 and len(sentence) < 400:
                    principles["workout_types"].append(sentence.strip())
                    if len(principles["workout_types"]) >= 30:
                        break
    
    # Look for recovery guidelines
    recovery_pattern = r"recovery[^\.\n]{20,300}"
    matches = re.finditer(recovery_pattern, text, re.IGNORECASE)
    for match in matches:
        recovery_text = match.group(0)
        if len(recovery_text) > 30:
            principles["recovery_guidelines"].append(recovery_text[:400])
            if len(principles["recovery_guidelines"]) >= 20:
                break
    
    return principles


def extract_and_store_principles(text_file: str, source: str, methodology: str):
    """Extract principles from text file and store in database."""
    db = get_db_sync()
    try:
        # Read text
        print(f"Reading {text_file}...")
        with open(text_file, 'r', encoding='utf-8') as f:
            text = f.read()
        
        print(f"Text length: {len(text)} characters")
        
        # Extract RPI principles
        print("Extracting RPI principles...")
        rpi_data = extract_rpi_principles(text)
        if rpi_data and (rpi_data.get("rpi_formula") or rpi_data.get("pace_definitions")):
            entry = CoachingKnowledgeEntry(
                source=source,
                methodology=methodology,
                source_type="book",
                text_chunk=text[:2000],  # Store context
                extracted_principles=json.dumps(rpi_data),
                principle_type="rpi_formula"
            )
            db.add(entry)
            print(f"✅ Extracted RPI principles")
        
        # Extract periodization principles
        print("Extracting periodization principles...")
        periodization_data = extract_periodization_principles(text)
        if periodization_data and (periodization_data.get("phases") or periodization_data.get("phase_duration")):
            entry = CoachingKnowledgeEntry(
                source=source,
                methodology=methodology,
                source_type="book",
                text_chunk=text[:2000],
                extracted_principles=json.dumps(periodization_data),
                principle_type="periodization"
            )
            db.add(entry)
            print(f"✅ Extracted periodization principles")
        
        # Extract general training principles
        print("Extracting general training principles...")
        training_data = extract_training_principles(text)
        if training_data and (training_data.get("core_principles") or training_data.get("workout_types")):
            entry = CoachingKnowledgeEntry(
                source=source,
                methodology=methodology,
                source_type="book",
                text_chunk=text[:2000],
                extracted_principles=json.dumps(training_data),
                principle_type="general"
            )
            db.add(entry)
            print(f"✅ Extracted general training principles")
        
        db.commit()
        print(f"✅ All principles extracted and stored!")
        
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
        print("Usage: python extract_principles_direct.py <text_file> <source> <methodology>")
        print("\nExample:")
        print("  python extract_principles_direct.py /books/daniels.txt 'Daniels Running Formula' 'Daniels'")
        sys.exit(1)
    
    text_file = sys.argv[1]
    source = sys.argv[2]
    methodology = sys.argv[3]
    
    extract_and_store_principles(text_file, source, methodology)
    print("✅ Done!")


if __name__ == "__main__":
    main()

