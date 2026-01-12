"""Check intensity scoring and workout types"""
import sys
sys.path.insert(0, '/app')
from core.database import SessionLocal
from models import Athlete, Activity
from datetime import datetime, timedelta

db = SessionLocal()

athlete = db.query(Athlete).filter(Athlete.email == 'mbshaf@gmail.com').first()

# Get last 60 days of activities
cutoff = datetime.utcnow() - timedelta(days=60)
activities = db.query(Activity).filter(
    Activity.athlete_id == athlete.id,
    Activity.start_time >= cutoff
).order_by(Activity.start_time.desc()).all()

print(f'Activities in last 60 days: {len(activities)}\n')

# Check intensity scores and workout types
hard_by_type = []
hard_by_intensity = []

for a in activities:
    name = (a.name or 'Run')[:40]
    wt = a.workout_type or '-'
    intensity = a.intensity_score
    
    # Classify by workout type
    hard_types = ['race', 'interval', 'tempo', 'threshold', 'vo2max', 'speed', 'fartlek']
    is_hard_type = any(ht in wt.lower() for ht in hard_types) if wt else False
    
    # Classify by intensity score (if available)
    is_hard_intensity = intensity and intensity >= 70
    
    marker = ''
    if is_hard_type:
        hard_by_type.append(a)
        marker += ' [TYPE:HARD]'
    if is_hard_intensity:
        hard_by_intensity.append(a)
        marker += ' [INTENSITY:HARD]'
    
    print(f'{a.start_time.date()} | {wt:20} | IS:{intensity or "-":>3} | HR:{a.avg_hr or "-":>3} | {name}{marker}')

print(f'\n--- SUMMARY ---')
print(f'Hard by workout type: {len(hard_by_type)}')
print(f'Hard by intensity score (>=70): {len(hard_by_intensity)}')

# Show unique workout types
types = set(a.workout_type for a in activities if a.workout_type)
print(f'\nUnique workout types: {types}')

db.close()
