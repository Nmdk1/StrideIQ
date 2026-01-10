"""
Consistency Streak Service (Green-inspired)

"Consistency is the leading indicator of success."

Tracks weekly training consistency and celebrates streaks.
A week counts as "consistent" if the athlete meets their training targets.
"""

from typing import Optional, Dict, List
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from uuid import UUID
import logging

from sqlalchemy.orm import Session
from sqlalchemy import func

from models import Athlete, Activity

logger = logging.getLogger(__name__)


@dataclass
class StreakInfo:
    """Current streak information"""
    current_streak_weeks: int
    longest_streak_weeks: int
    weeks_this_year: int  # Consistent weeks this calendar year
    last_consistent_week: Optional[date]
    is_at_risk: bool  # Current week at risk of breaking streak
    message: str
    celebration: Optional[str]  # Special message for milestones


# Minimum thresholds for "consistent week" by experience level
CONSISTENCY_THRESHOLDS = {
    'beginner': {
        'min_runs': 2,
        'min_distance_km': 10,
    },
    'recreational': {
        'min_runs': 3,
        'min_distance_km': 20,
    },
    'competitive': {
        'min_runs': 4,
        'min_distance_km': 40,
    }
}

# Streak milestones with celebrations
STREAK_MILESTONES = {
    4: "🔥 One month consistent! You're building a habit.",
    8: "⚡ Two months strong! The compound effect is kicking in.",
    12: "🏆 Three months! You're in the top 10% of consistent runners.",
    16: "💪 Four months! This is becoming part of who you are.",
    26: "🌟 Half a year of consistency! You're unstoppable.",
    52: "👑 ONE YEAR! You've mastered consistency. Elite mindset."
}


def get_athlete_experience_level(db: Session, athlete_id: UUID) -> str:
    """
    Determine athlete's experience level based on recent training.
    """
    cutoff = datetime.now() - timedelta(days=90)
    
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.start_time >= cutoff,
        Activity.sport == 'run',
        Activity.distance_m > 0
    ).all()
    
    if not activities:
        return 'beginner'
    
    total_distance_km = sum(a.distance_m or 0 for a in activities) / 1000
    weeks = 13  # ~90 days
    avg_weekly_km = total_distance_km / weeks
    
    if avg_weekly_km < 20:
        return 'beginner'
    elif avg_weekly_km < 45:
        return 'recreational'
    else:
        return 'competitive'


def check_week_consistency(
    db: Session, 
    athlete_id: UUID, 
    week_start: date,
    thresholds: Dict
) -> bool:
    """
    Check if a specific week meets consistency thresholds.
    """
    week_end = week_start + timedelta(days=7)
    
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.start_time >= datetime.combine(week_start, datetime.min.time()),
        Activity.start_time < datetime.combine(week_end, datetime.min.time()),
        Activity.sport == 'run',
        Activity.distance_m > 0
    ).all()
    
    run_count = len(activities)
    total_distance_km = sum(a.distance_m or 0 for a in activities) / 1000
    
    return (
        run_count >= thresholds['min_runs'] and 
        total_distance_km >= thresholds['min_distance_km']
    )


def calculate_streak(db: Session, athlete_id: UUID) -> StreakInfo:
    """
    Calculate current and longest consistency streaks.
    """
    level = get_athlete_experience_level(db, athlete_id)
    thresholds = CONSISTENCY_THRESHOLDS[level]
    
    # Start from last completed week
    today = date.today()
    # Find the Monday of this week
    current_week_start = today - timedelta(days=today.weekday())
    
    # Check if current week is at risk
    current_week_activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.start_time >= datetime.combine(current_week_start, datetime.min.time()),
        Activity.sport == 'run',
        Activity.distance_m > 0
    ).all()
    
    current_runs = len(current_week_activities)
    current_km = sum(a.distance_m or 0 for a in current_week_activities) / 1000
    
    runs_needed = max(0, thresholds['min_runs'] - current_runs)
    km_needed = max(0, thresholds['min_distance_km'] - current_km)
    
    days_left = 7 - today.weekday()
    is_at_risk = days_left <= 2 and (runs_needed > 0 or km_needed > 0)
    
    # Count streak backwards from last completed week
    streak = 0
    check_week = current_week_start - timedelta(days=7)  # Start from last week
    last_consistent = None
    
    while check_week >= date(2020, 1, 1):  # Don't go too far back
        if check_week_consistency(db, athlete_id, check_week, thresholds):
            streak += 1
            if last_consistent is None:
                last_consistent = check_week
            check_week -= timedelta(days=7)
        else:
            break
    
    # Get athlete's stored longest streak
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    longest = athlete.longest_streak_weeks or 0 if athlete else 0
    
    # Update if current is longer
    if streak > longest:
        longest = streak
    
    # Count consistent weeks this year
    year_start = date(today.year, 1, 1)
    weeks_this_year = 0
    check_week = current_week_start - timedelta(days=7)
    while check_week >= year_start:
        if check_week_consistency(db, athlete_id, check_week, thresholds):
            weeks_this_year += 1
        check_week -= timedelta(days=7)
    
    # Generate message
    if streak == 0:
        message = "Start a new streak! Every consistent week counts."
    elif is_at_risk:
        message = f"⚠️ Your {streak}-week streak is at risk! {runs_needed} more runs or {km_needed:.1f}km needed."
    else:
        message = f"{streak} weeks consistent. Keep building!"
    
    # Check for celebration
    celebration = None
    if streak in STREAK_MILESTONES:
        celebration = STREAK_MILESTONES[streak]
    
    return StreakInfo(
        current_streak_weeks=streak,
        longest_streak_weeks=longest,
        weeks_this_year=weeks_this_year,
        last_consistent_week=last_consistent,
        is_at_risk=is_at_risk,
        message=message,
        celebration=celebration
    )


def update_athlete_streak(db: Session, athlete_id: UUID) -> StreakInfo:
    """
    Calculate and store streak info for an athlete.
    """
    streak = calculate_streak(db, athlete_id)
    
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if athlete:
        athlete.current_streak_weeks = streak.current_streak_weeks
        if streak.current_streak_weeks > (athlete.longest_streak_weeks or 0):
            athlete.longest_streak_weeks = streak.current_streak_weeks
        athlete.last_streak_update = datetime.now()
        db.commit()
    
    return streak


