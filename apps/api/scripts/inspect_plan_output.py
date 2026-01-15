#!/usr/bin/env python3
"""
Inspect actual plan generation output for logical correctness.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta
from uuid import uuid4
from unittest.mock import MagicMock

# Import the generator
from services.model_driven_plan_generator import generate_model_driven_plan

# Create mock DB
mock_db = MagicMock()
mock_db.query.return_value.filter.return_value.all.return_value = []
mock_db.query.return_value.filter.return_value.first.return_value = None

# Generate a plan
athlete_id = uuid4()
race_date = date.today() + timedelta(days=84)  # 12 weeks

try:
    plan = generate_model_driven_plan(
        athlete_id=athlete_id,
        race_date=race_date,
        race_distance='marathon',
        db=mock_db
    )
    
    print('='*60)
    print('PLAN GENERATED SUCCESSFULLY')
    print('='*60)
    print(f'Race: {plan.race_distance} on {plan.race_date}')
    print(f'Total weeks: {plan.total_weeks}')
    print(f'Total miles: {plan.total_miles:.1f}')
    print(f'Total TSS: {plan.total_tss:.0f}')
    print(f'Model: tau1={plan.tau1:.1f}d, tau2={plan.tau2:.1f}d ({plan.model_confidence})')
    print(f'Taper starts week: {plan.taper_start_week}')
    print()
    
    if plan.prediction:
        pred = plan.prediction
        print('PREDICTION:')
        time_s = pred.predicted_time_seconds if pred.predicted_time_seconds else 0
        print(f'  Time: {time_s}s ({time_s//3600}:{(time_s%3600)//60:02d}:{time_s%60:02d})')
        print(f'  Confidence: {pred.prediction_confidence}')
        print(f'  CI: +/-{pred.confidence_interval_seconds}s')
    
    print()
    print('COUNTER-CONVENTIONAL NOTES:')
    if plan.counter_conventional_notes:
        for note in plan.counter_conventional_notes:
            print(f'  - {note}')
    else:
        print('  (none)')
    
    print()
    print('PERSONALIZATION SUMMARY:')
    print(f'  {plan.personalization_summary}')
    
    print()
    print('='*60)
    print('WEEKLY BREAKDOWN (all weeks)')
    print('='*60)
    
    for week in plan.weeks:
        cutback = " [CUTBACK]" if week.is_cutback else ""
        print(f'\nWeek {week.week_number} ({week.phase}){cutback}:')
        print(f'  Target TSS: {week.target_tss:.0f}, Miles: {week.target_miles:.1f}')
        if week.notes:
            for note in week.notes:
                print(f'  Note: {note}')
        
        for day in week.days:
            if day.workout_type == 'rest':
                print(f'  {day.day_of_week}: REST')
            else:
                pace_str = f' @ {day.target_pace}' if day.target_pace else ''
                miles_str = f' ({day.target_miles:.1f}mi)' if day.target_miles else ''
                print(f'  {day.day_of_week}: {day.workout_type.upper()} - {day.name}{miles_str}{pace_str}')
                if day.notes:
                    for note in day.notes:
                        print(f'    -> {note}')
    
    # Validation checks
    print()
    print('='*60)
    print('LOGICAL VALIDATION CHECKS')
    print('='*60)
    
    issues = []
    
    # Check 1: Total weeks should match race date
    expected_weeks = (race_date - date.today()).days // 7
    if plan.total_weeks != len(plan.weeks):
        issues.append(f'Week count mismatch: total_weeks={plan.total_weeks} but len(weeks)={len(plan.weeks)}')
    
    # Check 2: TSS should generally increase then taper
    weekly_tss = [w.target_tss for w in plan.weeks]
    peak_week_idx = weekly_tss.index(max(weekly_tss))
    if peak_week_idx > len(weekly_tss) - 2:
        issues.append(f'Peak week too late: week {peak_week_idx+1} of {len(weekly_tss)}')
    
    # Check 3: Taper should reduce volume
    if len(plan.weeks) >= 2:
        last_week_tss = plan.weeks[-1].target_tss
        pre_taper_tss = plan.weeks[-3].target_tss if len(plan.weeks) >= 3 else plan.weeks[-2].target_tss
        if last_week_tss >= pre_taper_tss:
            issues.append(f'Taper not reducing: last={last_week_tss}, pre-taper={pre_taper_tss}')
    
    # Check 4: Long run should be on weekend
    for week in plan.weeks:
        for day in week.days:
            if day.workout_type == 'long':
                if day.day_of_week not in ('Saturday', 'Sunday', 'Sat', 'Sun'):
                    issues.append(f'Week {week.week_number}: Long run on {day.day_of_week}')
    
    # Check 5: Race day should be last day
    last_day = plan.weeks[-1].days[-1]
    if 'race' not in last_day.workout_type.lower() and 'race' not in last_day.name.lower():
        issues.append(f'Last day is not race: {last_day.workout_type} - {last_day.name}')
    
    # Check 6: No long runs in final 2 weeks (taper)
    for week in plan.weeks[-2:]:
        for day in week.days:
            if day.workout_type == 'long' and day.target_miles and day.target_miles > 15:
                issues.append(f'Week {week.week_number}: Long run ({day.target_miles}mi) during taper')
    
    # Check 7: Reasonable total mileage for marathon
    if plan.total_miles < 200 or plan.total_miles > 800:
        issues.append(f'Total mileage unusual: {plan.total_miles:.0f}mi')
    
    # Check 8: Easy days should be easy
    for week in plan.weeks:
        for day in week.days:
            if day.workout_type == 'easy' and day.intensity and day.intensity not in ('easy', 'low', 'recovery'):
                issues.append(f'Week {week.week_number} {day.day_of_week}: Easy day marked as {day.intensity}')
    
    if issues:
        print('ISSUES FOUND:')
        for issue in issues:
            print(f'  ! {issue}')
    else:
        print('All checks passed!')
    
    print()
    print('TSS PROGRESSION:')
    print('  ', ' -> '.join([f'{w.target_tss:.0f}' for w in plan.weeks]))

except Exception as e:
    print(f'ERROR: {e}')
    import traceback
    traceback.print_exc()
