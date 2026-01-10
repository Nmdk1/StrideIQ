#!/usr/bin/env python3
"""
Test the client-facing translation layer with mock recommendations.

This simulates what the AI engine will generate internally and verifies
that the translation layer correctly strips methodology references.
"""
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.ai_coaching_engine import translate_recommendation_for_client
from services.neutral_terminology import strip_methodology_references

print("=" * 70)
print("Testing Client-Facing Translation Layer")
print("=" * 70)

# Mock internal recommendation (what AI engine generates)
mock_internal_recommendation = {
    "athlete_id": "test-athlete-123",
    "goal_distance": "Marathon",
    "generated_at": "2026-01-04T17:00:00",
    "plan": {
        "weeks": [
            {
                "week": 1,
                "workouts": [
                    {
                        "workout_type": "daniels_t_pace",
                        "methodology": "Daniels",
                        "description": "Based on Daniels T-pace principles, run 3x2 miles at threshold pace",
                        "pace": "6:00/mi",
                        "recovery": "2 min jog",
                        "rationale": "This follows Daniels' threshold training methodology for building lactate tolerance"
                    },
                    {
                        "workout_type": "pfitzinger_long_run",
                        "methodology": "Pfitzinger",
                        "description": "Pfitzinger-style long run with marathon pace segments",
                        "distance": "18 miles",
                        "segments": "Last 4 miles at marathon pace",
                        "rationale": "Following Pfitzinger's Advanced Marathoning approach for endurance"
                    }
                ],
                "total_mileage": 50,
                "rationale": "Blended Daniels threshold work with Pfitzinger volume structure"
            }
        ]
    },
    "rationale": "This plan combines Daniels' VDOT-based pacing with Pfitzinger's periodization model",
    "_internal": {
        "blending_rationale": {
            "methodologies": {"Daniels": 0.6, "Pfitzinger": 0.4},
            "reason": "Athlete responds well to Daniels pacing but needs Pfitz volume structure"
        },
        "methodologies_used": {"Daniels": 0.6, "Pfitzinger": 0.4}
    }
}

print("\n1. Mock Internal Recommendation (with methodology references):")
print(json.dumps(mock_internal_recommendation, indent=2))

# Translate to client-facing
client_facing = translate_recommendation_for_client(mock_internal_recommendation)

print("\n" + "=" * 70)
print("2. Client-Facing Output (after translation):")
print("=" * 70)
print(json.dumps(client_facing, indent=2))

# Verify no methodology leaks
print("\n" + "=" * 70)
print("3. Verification Checks:")
print("=" * 70)

methodology_keywords = ["Daniels", "Pfitzinger", "Canova", "Hanson", "Hansons", "Roche", "Bitter"]
client_text = json.dumps(client_facing).lower()

leaks_found = []
for keyword in methodology_keywords:
    if keyword.lower() in client_text:
        leaks_found.append(keyword)

if leaks_found:
    print(f"❌ METHODOLOGY LEAK DETECTED: {leaks_found}")
    print("   Client-facing output contains methodology references!")
else:
    print("✅ No methodology leaks detected")

# Check that _internal fields are removed
if "_internal" in client_facing:
    print("❌ _internal fields still present in client-facing output")
else:
    print("✅ _internal fields correctly removed")

# Check that workout types are translated
if "workouts" in client_facing.get("plan", {}).get("weeks", [{}])[0]:
    workouts = client_facing["plan"]["weeks"][0]["workouts"]
    for workout in workouts:
        if "methodology" in workout:
            print(f"❌ Workout still contains methodology field: {workout.get('methodology')}")
        else:
            print("✅ Workout methodology fields removed")
        
        # Check workout type translation
        if workout.get("workout_type") in ["daniels_t_pace", "pfitzinger_long_run"]:
            print(f"❌ Workout type not translated: {workout.get('workout_type')}")
        else:
            print(f"✅ Workout type translated: {workout.get('workout_type')}")

print("\n" + "=" * 70)
print("Translation Layer Test Complete")
print("=" * 70)

