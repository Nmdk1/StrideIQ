"""
GDPR Compliance Endpoints

Provides data export and account deletion endpoints for GDPR compliance.
Tone: Neutral, empowering, no guilt-inducing language.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Dict, List
from datetime import datetime
import json

from core.database import get_db
from core.auth import get_current_user
from core.cache import invalidate_athlete_cache
from models import (
    Athlete, Activity, ActivitySplit, NutritionEntry, BodyComposition,
    WorkPattern, DailyCheckin, ActivityFeedback, TrainingAvailability,
    InsightFeedback
)

router = APIRouter(prefix="/v1/gdpr", tags=["gdpr"])


@router.get("/export")
def export_user_data(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict:
    """
    Export all user data in JSON format.
    
    Returns comprehensive data export including:
    - Profile information
    - Activities and splits
    - Nutrition entries
    - Body composition
    - Work patterns
    - Daily check-ins
    - Activity feedback
    - Training availability
    - Insight feedback
    
    Tone: Neutral, empowering. No guilt-inducing language.
    """
    athlete_id = current_user.id
    
    # Collect all data
    export_data = {
        "export_date": datetime.utcnow().isoformat(),
        "athlete_id": str(athlete_id),
        "profile": {
            "email": current_user.email,
            "display_name": current_user.display_name,
            "birthdate": current_user.birthdate.isoformat() if current_user.birthdate else None,
            "sex": current_user.sex,
            "height_cm": current_user.height_cm,
            "subscription_tier": current_user.subscription_tier,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        },
        "activities": [],
        "nutrition_entries": [],
        "body_composition": [],
        "work_patterns": [],
        "daily_checkins": [],
        "activity_feedback": [],
        "training_availability": [],
        "insight_feedback": [],
    }
    
    # Activities
    activities = db.query(Activity).filter(Activity.athlete_id == athlete_id).all()
    for activity in activities:
        splits = db.query(ActivitySplit).filter(
            ActivitySplit.activity_id == activity.id
        ).order_by(ActivitySplit.split_number).all()
        
        export_data["activities"].append({
            "id": str(activity.id),
            "start_time": activity.start_time.isoformat() if activity.start_time else None,
            "sport": activity.sport,
            "distance_m": float(activity.distance_m) if activity.distance_m else None,
            "duration_s": activity.duration_s,
            "avg_hr": activity.avg_hr,
            "max_hr": activity.max_hr,
            "average_speed": float(activity.average_speed) if activity.average_speed else None,
            "performance_percentage": float(activity.performance_percentage) if activity.performance_percentage else None,
            "splits": [
                {
                    "split_number": split.split_number,
                    "distance": float(split.distance) if split.distance else None,
                    "elapsed_time": split.elapsed_time,
                    "average_heartrate": split.average_heartrate,
                    "gap_seconds_per_mile": float(split.gap_seconds_per_mile) if split.gap_seconds_per_mile else None,
                }
                for split in splits
            ]
        })
    
    # Nutrition entries
    nutrition_entries = db.query(NutritionEntry).filter(
        NutritionEntry.athlete_id == athlete_id
    ).all()
    for entry in nutrition_entries:
        export_data["nutrition_entries"].append({
            "id": str(entry.id),
            "date": entry.date.isoformat() if entry.date else None,
            "entry_type": entry.entry_type,
            "calories": float(entry.calories) if entry.calories else None,
            "protein_g": float(entry.protein_g) if entry.protein_g else None,
            "carbs_g": float(entry.carbs_g) if entry.carbs_g else None,
            "fat_g": float(entry.fat_g) if entry.fat_g else None,
            "fiber_g": float(entry.fiber_g) if entry.fiber_g else None,
            "timing": entry.timing,
            "notes": entry.notes,
        })
    
    # Body composition
    body_comp = db.query(BodyComposition).filter(
        BodyComposition.athlete_id == athlete_id
    ).all()
    for entry in body_comp:
        export_data["body_composition"].append({
            "id": str(entry.id),
            "date": entry.date.isoformat() if entry.date else None,
            "weight_kg": float(entry.weight_kg) if entry.weight_kg else None,
            "body_fat_pct": float(entry.body_fat_pct) if entry.body_fat_pct else None,
            "muscle_mass_kg": float(entry.muscle_mass_kg) if entry.muscle_mass_kg else None,
            "bmi": float(entry.bmi) if entry.bmi else None,
            "notes": entry.notes,
        })
    
    # Work patterns
    work_patterns = db.query(WorkPattern).filter(
        WorkPattern.athlete_id == athlete_id
    ).all()
    for pattern in work_patterns:
        export_data["work_patterns"].append({
            "id": str(pattern.id),
            "date": pattern.date.isoformat() if pattern.date else None,
            "work_type": pattern.work_type,
            "hours_worked": float(pattern.hours_worked) if pattern.hours_worked else None,
            "stress_level": pattern.stress_level,
            "notes": pattern.notes,
        })
    
    # Daily check-ins
    checkins = db.query(DailyCheckin).filter(
        DailyCheckin.athlete_id == athlete_id
    ).all()
    for checkin in checkins:
        export_data["daily_checkins"].append({
            "id": str(checkin.id),
            "date": checkin.date.isoformat() if checkin.date else None,
            "sleep_h": float(checkin.sleep_h) if checkin.sleep_h else None,
            "stress_1_5": checkin.stress_1_5,
            "soreness_1_5": checkin.soreness_1_5,
            "rpe_1_10": checkin.rpe_1_10,
            "notes": checkin.notes,
        })
    
    # Activity feedback
    feedback = db.query(ActivityFeedback).filter(
        ActivityFeedback.athlete_id == athlete_id
    ).all()
    for fb in feedback:
        export_data["activity_feedback"].append({
            "id": str(fb.id),
            "activity_id": str(fb.activity_id),
            "perceived_effort": fb.perceived_effort,
            "leg_feel": fb.leg_feel,
            "mood": fb.mood,
            "energy_level": fb.energy_level,
            "notes": fb.notes,
            "submitted_at": fb.submitted_at.isoformat() if fb.submitted_at else None,
        })
    
    # Training availability
    availability = db.query(TrainingAvailability).filter(
        TrainingAvailability.athlete_id == athlete_id
    ).all()
    for avail in availability:
        export_data["training_availability"].append({
            "id": str(avail.id),
            "day_of_week": avail.day_of_week,
            "time_block": avail.time_block,
            "available": avail.available,
            "preferred": avail.preferred,
        })
    
    # Insight feedback
    insight_feedback = db.query(InsightFeedback).filter(
        InsightFeedback.athlete_id == athlete_id
    ).all()
    for fb in insight_feedback:
        export_data["insight_feedback"].append({
            "id": str(fb.id),
            "insight_type": fb.insight_type,
            "insight_text": fb.insight_text,
            "helpful": fb.helpful,
            "feedback_text": fb.feedback_text,
            "created_at": fb.created_at.isoformat() if fb.created_at else None,
        })
    
    return export_data


@router.delete("/delete-account")
def delete_account(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict:
    """
    Delete user account and all associated data.
    
    This action is permanent and cannot be undone.
    All data will be deleted including:
    - Profile
    - Activities
    - Nutrition entries
    - Body composition
    - Work patterns
    - Daily check-ins
    - Activity feedback
    - Training availability
    - Insight feedback
    
    Tone: Neutral, clear, no guilt-inducing language.
    """
    athlete_id = current_user.id
    
    # Delete all associated data (cascade deletes handled by foreign keys)
    # But we'll be explicit for clarity
    
    # Delete insight feedback
    db.query(InsightFeedback).filter(InsightFeedback.athlete_id == athlete_id).delete()
    
    # Delete training availability
    db.query(TrainingAvailability).filter(TrainingAvailability.athlete_id == athlete_id).delete()
    
    # Delete activity feedback
    db.query(ActivityFeedback).filter(ActivityFeedback.athlete_id == athlete_id).delete()
    
    # Delete daily check-ins
    db.query(DailyCheckin).filter(DailyCheckin.athlete_id == athlete_id).delete()
    
    # Delete work patterns
    db.query(WorkPattern).filter(WorkPattern.athlete_id == athlete_id).delete()
    
    # Delete body composition
    db.query(BodyComposition).filter(BodyComposition.athlete_id == athlete_id).delete()
    
    # Delete nutrition entries
    db.query(NutritionEntry).filter(NutritionEntry.athlete_id == athlete_id).delete()
    
    # Delete activity splits (cascade from activities, but explicit for clarity)
    activities = db.query(Activity).filter(Activity.athlete_id == athlete_id).all()
    for activity in activities:
        db.query(ActivitySplit).filter(ActivitySplit.activity_id == activity.id).delete()
    
    # Delete activities
    db.query(Activity).filter(Activity.athlete_id == athlete_id).delete()
    
    # Delete athlete (this will cascade to any remaining relationships)
    db.delete(current_user)
    
    db.commit()
    
    # Invalidate cache
    invalidate_athlete_cache(str(athlete_id))
    
    return {
        "message": "Account deleted successfully",
        "deleted_at": datetime.utcnow().isoformat()
    }


