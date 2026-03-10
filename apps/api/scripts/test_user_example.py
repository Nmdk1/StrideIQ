#!/usr/bin/env python3
"""Test calculator with user's race example."""
import sys
sys.path.insert(0, '/app')

from services.rpi_calculator import calculate_rpi_from_race_time, calculate_training_paces

def format_pace(secs):
    return f'{secs // 60}:{secs % 60:02d}'

# User's example: Half Marathon 1:27:14
half_marathon_meters = 21097.5
time_seconds = 1*3600 + 27*60 + 14  # 1:27:14

fitness_score = calculate_rpi_from_race_time(half_marathon_meters, time_seconds)
paces = calculate_training_paces(fitness_score)

print("YOUR EXAMPLE: Half Marathon 1:27:14")
print("=" * 60)
print(f"RPI (Running Performance Index): {fitness_score}")
print()
print("TRAINING PACES (per mile / per km):")
print(f"  Easy:       {paces['easy']['mi']} / {paces['easy']['km']}")
print(f"  Marathon:   {paces['marathon']['mi']} / {paces['marathon']['km']}")
print(f"  Threshold:  {paces['threshold']['mi']} / {paces['threshold']['km']}")
print(f"  Interval:   {paces['interval']['mi']} / {paces['interval']['km']}")
print(f"  Repetition: {paces['repetition']['mi']} / {paces['repetition']['km']}")
print(f"  Fast Reps:  {paces['fast_reps']['mi']} / {paces['fast_reps']['km']}")
print()
print("RAW SECONDS (for distance calculations):")
print(f"  Easy range: {paces['easy_pace_low']}s - {paces['easy_pace_high']}s")
print(f"  Marathon:   {paces['marathon_pace']}s")
print(f"  Threshold:  {paces['threshold_pace']}s")
print(f"  Interval:   {paces['interval_pace']}s")
print(f"  Repetition: {paces['repetition_pace']}s")
print()

# Compare to screenshot values
print("COMPARISON TO COMPETITOR SCREENSHOT:")
print("-" * 60)
print("                    Competitor    Ours        Diff")
print("-" * 60)

comparisons = [
    ("Easy (fast)", "7:53", format_pace(paces['easy_pace_low'])),
    ("Easy (slow)", "8:41", format_pace(paces['easy_pace_high'])),
    ("Marathon", "6:57", paces['marathon']['mi']),
    ("Threshold", "6:33", paces['threshold']['mi']),
    ("Interval", "6:01", paces['interval']['mi']),
    ("Repetition", "5:37", paces['repetition']['mi']),
]

def pace_to_sec(p):
    parts = p.split(":")
    return int(parts[0]) * 60 + int(parts[1])

for label, competitor, ours in comparisons:
    diff = pace_to_sec(ours) - pace_to_sec(competitor)
    diff_str = f"{diff:+d}s" if diff != 0 else "EXACT"
    print(f"  {label:14} {competitor:12} {ours:12} {diff_str}")

print()
print("=" * 60)
