"""
Perception Prompts Service

Determines when and what perception questions to ask athletes post-activity.
This service integrates with activity analysis to prompt for feedback at optimal times.

Key principles:
- Always prompt after meaningful activities (races, intervals, long runs)
- Prompt immediately post-run for accuracy (within 24 hours)
- Context-aware questions based on activity type
- Build perception ↔ performance correlation dataset
"""
from sqlalchemy.orm import Session
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from uuid import UUID
from models import Activity, ActivityFeedback, Athlete
from services.activity_analysis import ActivityAnalysis

# Question templates by activity type
QUESTION_TEMPLATES = {
    "race": {
        "required": ["perceived_effort", "leg_feel", "mood_post", "energy_post"],
        "optional": ["mood_pre", "energy_pre", "notes"],
        "prompt": "How did that race feel? Rate your effort, how your legs felt, and your post-race mood."
    },
    "interval": {
        "required": ["perceived_effort", "leg_feel"],
        "optional": ["mood_pre", "mood_post", "energy_pre", "energy_post", "notes"],
        "prompt": "Intervals done. How hard did that feel? How do your legs feel now?"
    },
    "threshold": {
        "required": ["perceived_effort", "leg_feel"],
        "optional": ["mood_pre", "mood_post", "energy_pre", "energy_post", "notes"],
        "prompt": "Threshold effort complete. Rate your perceived effort and leg feel."
    },
    "tempo": {
        "required": ["perceived_effort"],
        "optional": ["leg_feel", "mood_pre", "mood_post", "energy_pre", "energy_post", "notes"],
        "prompt": "Tempo run finished. How did that effort feel?"
    },
    "long_run": {
        "required": ["perceived_effort", "leg_feel", "energy_post"],
        "optional": ["mood_pre", "mood_post", "energy_pre", "notes"],
        "prompt": "Long run complete. How was your effort? How do your legs feel? Energy level?"
    },
    "easy": {
        "required": [],
        "optional": ["perceived_effort", "leg_feel", "mood_pre", "mood_post", "energy_pre", "energy_post", "notes"],
        "prompt": "Easy run done. Optional: How did that feel?"
    },
    "default": {
        "required": ["perceived_effort"],
        "optional": ["leg_feel", "mood_pre", "mood_post", "energy_pre", "energy_post", "notes"],
        "prompt": "Run complete. How did that feel?"
    }
}


def should_prompt_for_feedback(activity: Activity, db: Session) -> bool:
    """
    Determine if we should prompt for feedback for this activity.
    
    Rules:
    - Always prompt for races
    - Prompt for intervals, threshold, tempo, long runs
    - Optional for easy runs (don't force, but offer)
    - Don't prompt if feedback already exists
    - Don't prompt if activity is too old (>24 hours)
    """
    # Check if feedback already exists
    existing = db.query(ActivityFeedback).filter(
        ActivityFeedback.activity_id == activity.id
    ).first()
    if existing:
        return False
    
    # Don't prompt for activities older than 24 hours
    if activity.start_time:
        age_hours = (datetime.utcnow() - activity.start_time.replace(tzinfo=None)).total_seconds() / 3600
        if age_hours > 24:
            return False
    
    # Get athlete for classification
    athlete = db.query(Athlete).filter(Athlete.id == activity.athlete_id).first()
    if not athlete:
        return False
    
    # Classify run type
    analysis = ActivityAnalysis(activity, athlete, db)
    run_type = analysis._classify_run_type()
    
    # Always prompt for races and high-intensity work
    if run_type in ["race", "interval", "threshold", "tempo", "long_run"]:
        return True
    
    # Optional for easy runs (return True to offer, but don't require)
    if run_type == "easy":
        return True
    
    # Default: prompt
    return True


def get_perception_prompts(activity: Activity, db: Session) -> Dict:
    """
    Get perception question prompts for an activity.
    
    Returns:
        {
            "should_prompt": bool,
            "prompt_text": str,
            "required_fields": List[str],
            "optional_fields": List[str],
            "activity_id": UUID,
            "run_type": str
        }
    """
    # Check if we should prompt
    if not should_prompt_for_feedback(activity, db):
        return {
            "should_prompt": False,
            "prompt_text": None,
            "required_fields": [],
            "optional_fields": [],
            "activity_id": str(activity.id),
            "run_type": None
        }
    
    # Get athlete for classification
    athlete = db.query(Athlete).filter(Athlete.id == activity.athlete_id).first()
    if not athlete:
        return {
            "should_prompt": False,
            "prompt_text": None,
            "required_fields": [],
            "optional_fields": [],
            "activity_id": str(activity.id),
            "run_type": None
        }
    
    # Classify run type
    analysis = ActivityAnalysis(activity, athlete, db)
    run_type = analysis._classify_run_type() or "default"
    
    # Get template
    template = QUESTION_TEMPLATES.get(run_type, QUESTION_TEMPLATES["default"])
    
    return {
        "should_prompt": True,
        "prompt_text": template["prompt"],
        "required_fields": template["required"],
        "optional_fields": template["optional"],
        "activity_id": str(activity.id),
        "run_type": run_type
    }


def get_pending_feedback_prompts(athlete_id: UUID, db: Session, limit: int = 10) -> List[Dict]:
    """
    Get list of activities that need feedback prompts.
    
    Returns activities from last 24 hours that:
    - Don't have feedback yet
    - Are meaningful (races, intervals, threshold, tempo, long runs)
    - Are recent (within 24 hours)
    """
    cutoff_time = datetime.utcnow() - timedelta(hours=24)
    
    # Get recent activities without feedback
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.start_time >= cutoff_time,
        ~Activity.id.in_(
            db.query(ActivityFeedback.activity_id).filter(
                ActivityFeedback.athlete_id == athlete_id
            )
        )
    ).order_by(Activity.start_time.desc()).limit(limit).all()
    
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        return []
    
    prompts = []
    for activity in activities:
        prompt_data = get_perception_prompts(activity, db)
        if prompt_data["should_prompt"]:
            prompts.append(prompt_data)
    
    return prompts

