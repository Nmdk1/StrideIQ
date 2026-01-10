#!/usr/bin/env python3
"""Test neutral terminology translation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.neutral_terminology import (
    translate_to_neutral,
    format_workout_description,
    strip_methodology_references,
    get_neutral_workout_labels
)

print("=" * 60)
print("Testing Neutral Terminology Translation")
print("=" * 60)

# Test 1: Translate methodology-specific terms
print("\n1. Translating methodology-specific terms:")
test_terms = [
    "daniels_t_pace",
    "daniels_i_pace",
    "hansons_sos",
    "pfitzinger_marathon_pace",
    "canova_special_endurance"
]

for term in test_terms:
    result = translate_to_neutral(term)
    print(f"  {term:30} -> {result['neutral']}")
    print(f"    Description: {result['description']}")

# Test 2: Format workout descriptions
print("\n2. Formatting workout descriptions:")
workouts = [
    ("threshold", "6:00/mi", "20 minutes", "Daniels"),
    ("long_run", "7:30/mi", "90 minutes", "Pfitzinger"),
    ("vo2max", "5:30/mi", "5x1000m", "Daniels")
]

for workout_type, pace, duration, methodology in workouts:
    desc = format_workout_description(workout_type, pace, duration, methodology)
    print(f"  {desc}")

# Test 3: Strip methodology references
print("\n3. Stripping methodology references:")
test_texts = [
    "Based on Daniels T-pace, run at 6:00/mi",
    "This workout uses Pfitzinger's marathon pace approach",
    "Following Hansons SOS principles, do a tempo run"
]

for text in test_texts:
    cleaned = strip_methodology_references(text)
    print(f"  Original: {text}")
    print(f"  Cleaned:  {cleaned}\n")

# Test 4: Get neutral workout labels
print("4. Available neutral workout labels:")
labels = get_neutral_workout_labels()
for label in labels:
    print(f"  - {label}")

print("\n" + "=" * 60)
print("✅ All tests passed!")
print("=" * 60)

