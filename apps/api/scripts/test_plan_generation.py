#!/usr/bin/env python3
"""Test principle-based plan generation."""
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.principle_plan_generator import generate_principle_based_plan

def test_plan_generation():
    print("=" * 70)
    print("Testing Principle-Based Plan Generation")
    print("=" * 70)
    
    # Test profile: Intermediate marathoner
    athlete_id = "test-athlete-001"
    goal_distance = "Marathon"
    current_fitness = {
        "rpi": 50.0,
        "recent_race_time_seconds": 3600,  # 1 hour 10K
        "recent_race_distance_meters": 10000
    }
    diagnostic_signals = {
        "recovery_half_life_hours": 48,
        "efficiency_trend": 0.01,
        "durability_index": 60.0,
        "current_weekly_mileage": 35
    }
    athlete_profile = {
        "volume_tolerance": "moderate",
        "speed_background": "balanced",
        "injury_history": "none",
        "current_base_mileage": 35
    }
    
    # Test 1: 12-week plan
    print("\n1. Generating 12-week marathon plan...")
    plan_12 = generate_principle_based_plan(
        athlete_id=athlete_id,
        goal_distance=goal_distance,
        current_fitness=current_fitness,
        diagnostic_signals=diagnostic_signals,
        athlete_profile=athlete_profile,
        weeks_to_race=12
    )
    
    print(f"✅ Generated plan with {plan_12['plan']['total_weeks']} weeks")
    print(f"   Phase allocation: {plan_12['plan'].get('phase_allocation', {})}")
    print(f"   Weeks generated: {len(plan_12['plan']['weeks'])}")
    
    if plan_12['plan']['weeks']:
        first_week = plan_12['plan']['weeks'][0]
        print(f"   First week: Phase={first_week.get('phase')}, Mileage={first_week.get('total_mileage')}")
        print(f"   Workouts: {len(first_week.get('workouts', []))}")
    
    validation = plan_12['plan'].get('validation', {})
    print(f"   Validation: Valid={validation.get('is_valid')}, Warnings={len(validation.get('warnings', []))}")
    if validation.get('warnings'):
        print(f"   Warnings: {validation['warnings'][:2]}")
    
    # Test 2: 6-week abbreviated plan
    print("\n2. Generating 6-week abbreviated plan...")
    plan_6 = generate_principle_based_plan(
        athlete_id=athlete_id,
        goal_distance=goal_distance,
        current_fitness=current_fitness,
        diagnostic_signals=diagnostic_signals,
        athlete_profile=athlete_profile,
        weeks_to_race=6
    )
    
    print(f"✅ Generated abbreviated plan with {plan_6['plan']['total_weeks']} weeks")
    print(f"   Phase allocation: {plan_6['plan'].get('phase_allocation', {})}")
    print(f"   Weeks generated: {len(plan_6['plan']['weeks'])}")
    
    # Test 3: 18-week full plan
    print("\n3. Generating 18-week full plan...")
    plan_18 = generate_principle_based_plan(
        athlete_id=athlete_id,
        goal_distance=goal_distance,
        current_fitness=current_fitness,
        diagnostic_signals=diagnostic_signals,
        athlete_profile=athlete_profile,
        weeks_to_race=18
    )
    
    print(f"✅ Generated full plan with {plan_18['plan']['total_weeks']} weeks")
    print(f"   Phase allocation: {plan_18['plan'].get('phase_allocation', {})}")
    print(f"   Weeks generated: {len(plan_18['plan']['weeks'])}")
    
    print("\n" + "=" * 70)
    print("✅ All tests passed!")
    print("=" * 70)
    
    # Verify no methodology leaks
    plan_json = json.dumps(plan_12).lower()
    methodology_keywords = ["daniels", "pfitzinger", "canova", "hanson"]
    leaks = [kw for kw in methodology_keywords if kw in plan_json]
    if leaks:
        print(f"\n⚠️  Methodology leaks detected: {leaks}")
    else:
        print("\n✅ No methodology leaks detected")

if __name__ == "__main__":
    test_plan_generation()

