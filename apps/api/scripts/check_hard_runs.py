"""Check why hard runs = 0"""
import sys
sys.path.insert(0, '/app')
from core.database import SessionLocal
from models import Athlete, Activity
from sqlalchemy import func

db = SessionLocal()

# Get athlete
athlete = db.query(Athlete).filter(Athlete.email == 'mbshaf@gmail.com').first()
print(f'Athlete: {athlete.display_name}')
print(f'Max HR: {athlete.max_hr}')
print(f'VDOT: {athlete.vdot}')

# Get recent activities with HR
activities = db.query(Activity).filter(
    Activity.athlete_id == athlete.id,
    Activity.avg_hr != None
).order_by(Activity.start_time.desc()).limit(15).all()

print(f'\nRecent activities with HR (last 15):')
easy = moderate = hard = 0

for a in activities:
    if athlete.max_hr:
        hr_pct = a.avg_hr / athlete.max_hr * 100
        if hr_pct < 75:
            category = 'EASY'
            easy += 1
        elif hr_pct < 85:
            category = 'MODERATE'
            moderate += 1
        else:
            category = 'HARD'
            hard += 1
        print(f'  {a.start_time.date()}: HR {a.avg_hr} = {hr_pct:.0f}% max -> {category}')
    else:
        print(f'  {a.start_time.date()}: HR {a.avg_hr} - NO MAX HR SET')

print(f'\nCounts: Easy={easy}, Moderate={moderate}, Hard={hard}')
print(f'\n85% of max HR = {athlete.max_hr * 0.85 if athlete.max_hr else "N/A"}')

db.close()
