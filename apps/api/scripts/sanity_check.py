#!/usr/bin/env python3
"""Backend sanity check script."""
import sys
sys.path.insert(0, '/app')

print('=== BACKEND SANITY CHECK ===')
print()

# 1. Check all routers can import
print('1. Checking router imports...')
router_errors = []
routers = [
    'activities', 'auth', 'calendar', 'insights', 'nutrition',
    'plan_generation', 'preferences', 'public_tools', 'training_load',
    'rpi', 'attribution', 'causal', 'contextual_compare', 'data_export',
    'strava', 'admin', 'analytics', 'athlete_profile', 'daily_checkin',
    'knowledge', 'training_plans', 'ai_coach'
]
for router in routers:
    try:
        __import__(f'routers.{router}', fromlist=[router])
    except Exception as e:
        router_errors.append(f'{router}: {e}')

if router_errors:
    for err in router_errors:
        print(f'   ✗ {err}')
else:
    print(f'   ✓ All {len(routers)} routers import successfully')

# 2. Check key services
print()
print('2. Checking key services...')
service_errors = []
services = [
    'rpi_calculator', 'rpi_enhanced', 'rpi_lookup',
    'plan_generator', 'plan_generator_v2', 'athlete_context',
    'attribution_engine', 'causal_attribution', 'contextual_comparison',
    'efficiency_calculation', 'pattern_recognition', 'plan_audit'
]
for svc in services:
    try:
        __import__(f'services.{svc}', fromlist=[svc])
    except Exception as e:
        service_errors.append(f'{svc}: {e}')

if service_errors:
    for err in service_errors:
        print(f'   ✗ {err}')
else:
    print(f'   ✓ All {len(services)} services import successfully')

# 3. Check models
print()
print('3. Checking models...')
try:
    from models import (
        Athlete, Activity, TrainingPlan, PlannedWorkout,
        PlanModificationLog, CoachingKnowledgeEntry, CalendarNote,
        DailyCheckin, FeatureFlag
    )
    print('   ✓ All key models import successfully')
except Exception as e:
    print(f'   ✗ Model import error: {e}')

# 4. Check database connection
print()
print('4. Checking database connection...')
try:
    from core.database import get_db, engine
    from sqlalchemy import text
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print('   ✓ Database connection successful')
except Exception as e:
    print(f'   ✗ Database error: {e}')

# 5. Check alembic
print()
print('5. Checking alembic migrations...')
try:
    import subprocess
    result = subprocess.run(
        ['alembic', 'current'], 
        capture_output=True, 
        text=True,
        cwd='/app'
    )
    if result.returncode == 0:
        current = result.stdout.strip().split('\n')[-1] if result.stdout else 'unknown'
        print(f'   ✓ Current migration: {current[:50]}...')
    else:
        print(f'   ✗ Alembic error: {result.stderr}')
except Exception as e:
    print(f'   ✗ Alembic check error: {e}')

print()
print('=== CHECK COMPLETE ===')
