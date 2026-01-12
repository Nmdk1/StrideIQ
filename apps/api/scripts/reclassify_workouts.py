"""Reclassify workouts using improved classifier"""
import sys
sys.path.insert(0, '/app')
from core.database import SessionLocal
from models import Athlete, Activity
from services.workout_classifier import WorkoutClassifierService
from datetime import datetime, timedelta

db = SessionLocal()
classifier = WorkoutClassifierService(db)

athlete = db.query(Athlete).filter(Athlete.email == 'mbshaf@gmail.com').first()

# Get last 90 days of activities
cutoff = datetime.utcnow() - timedelta(days=90)
activities = db.query(Activity).filter(
    Activity.athlete_id == athlete.id,
    Activity.start_time >= cutoff
).order_by(Activity.start_time.desc()).all()

print(f'Reclassifying {len(activities)} activities...\n')

changed = 0
for a in activities:
    old_type = a.workout_type
    old_intensity = a.intensity_score
    
    # Reclassify
    classification = classifier.classify_activity(a)
    
    new_type = classification.workout_type.value
    new_intensity = classification.intensity_score
    
    if old_type != new_type or (old_intensity or 0) != new_intensity:
        print(f'{a.start_time.date()} | {(a.name or "Run")[:35]:35} | {old_type or "-":20} -> {new_type:20} | IS: {old_intensity or "-"} -> {new_intensity:.0f}')
        
        # Update the activity
        a.workout_type = new_type
        a.intensity_score = new_intensity
        changed += 1

db.commit()
print(f'\n--- DONE ---')
print(f'Updated {changed} activities')

db.close()
