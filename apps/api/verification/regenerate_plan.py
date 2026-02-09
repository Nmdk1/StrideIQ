"""
Regenerate and save a new plan with ADR-038 fix.
"""

import os
from core.database import SessionLocal
from models import Athlete, TrainingPlan, PlannedWorkout
from services.constraint_aware_planner import generate_constraint_aware_plan
from datetime import date
from sqlalchemy import text

db = SessionLocal()

try:
    athlete_email = os.getenv("STRIDEIQ_TEST_EMAIL")
    if not athlete_email:
        print("Set STRIDEIQ_TEST_EMAIL to target a test athlete (no hardcoded emails in repo).")
        exit()

    athlete = db.query(Athlete).filter(Athlete.email == athlete_email).first()
    if not athlete:
        print('Athlete not found')
        exit()
    
    # Deactivate old plans
    db.execute(
        text("UPDATE training_plan SET status = 'replaced' WHERE athlete_id = :aid AND status = 'active'"),
        {'aid': str(athlete.id)}
    )
    db.commit()
    
    # Generate new plan with ADR-038 fix
    print('Generating new plan...')
    race_date = date(2026, 3, 15)
    tune_up = [{'date': date(2026, 3, 7), 'distance': '10_mile', 'name': 'B 2 W', 'purpose': 'threshold'}]
    
    plan = generate_constraint_aware_plan(
        athlete_id=athlete.id,
        race_date=race_date,
        race_distance='marathon',
        db=db,
        tune_up_races=tune_up
    )
    
    # Save to database
    plan_record = TrainingPlan(
        athlete_id=athlete.id,
        name='Tobacco Road v21 (ADR-038 Fix)',
        status='active',
        goal_race_name='Tobacco Road Marathon',
        goal_race_date=race_date,
        goal_race_distance_m=42195,
        plan_start_date=plan.weeks[0].start_date,
        plan_end_date=race_date,  # Use race date as end date
        total_weeks=plan.total_weeks,
        baseline_rpi=plan.bank.best_rpi if hasattr(plan, 'bank') else 50.0,
        baseline_weekly_volume_km=plan.bank.current_weekly_miles * 1.60934 if hasattr(plan, 'bank') else 100.0,
        plan_type='marathon',
        generation_method='constraint_aware'
    )
    db.add(plan_record)
    db.flush()
    
    # Save workouts
    from datetime import timedelta
    for week in plan.weeks:
        for day in week.days:
            if day.target_miles > 0:
                # Calculate actual date from week start + day_of_week
                workout_date = week.start_date + timedelta(days=day.day_of_week)
                workout = PlannedWorkout(
                    plan_id=plan_record.id,
                    athlete_id=athlete.id,
                    scheduled_date=workout_date,
                    day_of_week=day.day_of_week,
                    workout_type=day.workout_type,
                    title=day.name,
                    description=day.description,
                    target_distance_km=day.target_miles * 1.60934,
                    phase=week.theme.value,
                    week_number=week.week_number,
                )
                db.add(workout)
    
    db.commit()
    
    print(f'Plan saved: {plan_record.name}')
    print(f'Plan ID: {plan_record.id}')
    print(f'Total weeks: {plan.total_weeks}')
    print(f'Total miles: {plan.total_miles:.1f}')
    
    # Show long run progression
    print()
    print('Long Run Progression:')
    for week in plan.weeks:
        long_run = None
        for day in week.days:
            if day.workout_type in ('long', 'long_mp', 'easy_long'):
                long_run = day.target_miles
                break
        if long_run:
            print(f'  Week {week.week_number} ({week.theme.value}): {long_run:.1f} mi')
    
    print()
    print('Frontend URL: http://localhost:3000/calendar')
    print('Plan is now active and should appear on the calendar.')
    
except Exception as e:
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()
