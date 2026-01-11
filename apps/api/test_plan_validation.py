"""Quick validation test for plan generator."""

from services.plan_framework import PlanGenerator

def validate_plan(plan):
    errors = []
    warnings = []
    
    # 1. Check volume progression
    volumes = plan.weekly_volumes
    for i in range(1, len(volumes) - 2):
        prev = volumes[i - 1]
        curr = volumes[i]
        
        # Skip if previous week was a cutback (return from cutback is expected)
        if i >= 2 and volumes[i - 2] > prev:
            continue  # Previous was cutback, skip this check
        
        if curr > prev:
            increase = (curr - prev) / prev if prev > 0 else 0
            if increase > 0.15:
                errors.append(f"Week {i+1}: Volume increase {increase:.0%} exceeds 15%")
    
    # 2. Check taper reduction
    peak = max(volumes[:-2])
    if volumes[-1] > peak * 0.5:
        warnings.append(f"Race week volume ({volumes[-1]:.0f}) may be too high (>{peak*0.5:.0f})")
    
    # 3. Check MP progression
    mp_runs = [w for w in plan.workouts if w.workout_type == "long_mp"]
    if len(mp_runs) >= 2:
        for i in range(1, len(mp_runs)):
            prev_seg = mp_runs[i-1].segments
            curr_seg = mp_runs[i].segments
            if prev_seg and curr_seg:
                prev_mp = next((s.get("distance_miles", 0) for s in prev_seg if s.get("pace") == "MP"), 0)
                curr_mp = next((s.get("distance_miles", 0) for s in curr_seg if s.get("pace") == "MP"), 0)
                if curr_mp < prev_mp:
                    errors.append(f"MP progression regressed: {prev_mp}mi to {curr_mp}mi")
    
    # 4. Check no MP in base phase
    base_weeks = [p.weeks for p in plan.phases if "base" in p.phase_type.value.lower()]
    base_weeks_flat = [w for weeks in base_weeks for w in weeks]
    for workout in plan.workouts:
        if workout.week in base_weeks_flat and "mp" in workout.workout_type.lower():
            errors.append(f"Week {workout.week}: MP work in base phase")
    
    # 5. Check total volume is reasonable
    if not (400 <= plan.total_miles <= 1200):
        warnings.append(f"Total volume {plan.total_miles:.0f}mi outside expected range")
    
    # 6. Check easy running proportion
    easy_types = ["easy", "recovery", "long", "medium_long"]
    hard_types = ["threshold", "tempo", "intervals", "long_mp"]
    easy_miles = sum(w.distance_miles or 0 for w in plan.workouts 
                     if any(e in w.workout_type for e in easy_types)
                     and not any(h in w.workout_type for h in hard_types))
    if plan.total_miles > 0 and easy_miles / plan.total_miles < 0.60:
        warnings.append(f"Easy running only {easy_miles/plan.total_miles:.0%} (target >60%)")
    
    return errors, warnings


if __name__ == "__main__":
    # Test multiple configurations
    configs = [
        ("marathon", 18, "mid", 6),
        ("marathon", 18, "high", 6),
        ("marathon", 12, "mid", 6),
        ("half_marathon", 16, "mid", 6),
        ("10k", 12, "mid", 6),
        ("5k", 8, "mid", 6),
        ("marathon", 18, "builder", 5),
    ]
    
    gen = PlanGenerator()
    all_passed = True
    
    for distance, weeks, tier, days in configs:
        print(f"Testing: {distance} {weeks}w {tier} {days}d...")
        try:
            plan = gen.generate_standard(distance, weeks, tier, days)
            errors, warnings = validate_plan(plan)
            
            if errors:
                print(f"  ERRORS:")
                for e in errors:
                    print(f"    - {e}")
                all_passed = False
            
            if warnings:
                print(f"  Warnings:")
                for w in warnings:
                    print(f"    - {w}")
            
            if not errors and not warnings:
                print(f"  PASSED (total: {plan.total_miles:.0f}mi, peak: {plan.peak_volume:.0f}mi)")
        except Exception as e:
            print(f"  EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False
    
    print()
    print("=" * 60)
    if all_passed:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS HAD ISSUES - Review above")
