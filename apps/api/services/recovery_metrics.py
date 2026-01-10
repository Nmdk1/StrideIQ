"""
Recovery Metrics Service

Calculates recovery-related metrics from the manifesto:
- Recovery Elasticity: How fast does the athlete rebound?
- Durability Index: Can progress be sustained without breaking?
- Recovery Half-Life: Time to return to baseline after hard sessions

Based on Manifesto Section 2: Secondary Signals
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from models import Activity, DailyCheckin, ActivityFeedback

import logging

logger = logging.getLogger(__name__)


# Thresholds for classification
HARD_SESSION_HR_THRESHOLD = 0.85  # 85% of max HR indicates hard session
EASY_SESSION_HR_THRESHOLD = 0.75  # Below 75% is easy
RECOVERY_BASELINE_DAYS = 7  # Days to establish recovery baseline


def calculate_recovery_half_life(
    db: Session,
    athlete_id: str,
    days: int = 90
) -> Optional[float]:
    """
    Calculate recovery half-life for an athlete.
    
    Recovery half-life is the time (in hours) it takes for:
    - HR to return to normal after a hard session
    - Efficiency to return to baseline
    - Perceived effort to normalize
    
    Lower = faster recovery. Higher = slower recovery.
    
    Returns:
        Recovery half-life in hours, or None if insufficient data
    """
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Get hard sessions and subsequent easy sessions
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.start_time >= start_date,
        Activity.avg_hr.isnot(None)
    ).order_by(Activity.start_time).all()
    
    if len(activities) < 5:
        return None
    
    # Get daily check-ins for HR data
    checkins = db.query(DailyCheckin).filter(
        DailyCheckin.athlete_id == athlete_id,
        DailyCheckin.date >= start_date.date()
    ).all()
    
    checkin_by_date = {c.date: c for c in checkins}
    
    # Find pairs of hard session followed by easy/rest days
    recovery_times = []
    
    for i, activity in enumerate(activities):
        if not activity.avg_hr:
            continue
            
        # Check if this was a hard session (simplified: high HR)
        # In a full implementation, you'd compare to athlete's max HR
        avg_hr = float(activity.avg_hr)
        
        # Look at next few activities to find recovery
        for j in range(i + 1, min(i + 5, len(activities))):
            next_activity = activities[j]
            if not next_activity.avg_hr:
                continue
                
            next_hr = float(next_activity.avg_hr)
            
            # If next activity has lower HR, calculate recovery time
            if next_hr < avg_hr * 0.9:  # 10% lower HR
                time_diff = (next_activity.start_time - activity.start_time).total_seconds() / 3600
                recovery_times.append(time_diff)
                break
    
    if len(recovery_times) < 3:
        return None
    
    # Return median recovery time
    recovery_times.sort()
    median_idx = len(recovery_times) // 2
    return recovery_times[median_idx]


def calculate_durability_index(
    db: Session,
    athlete_id: str,
    days: int = 90
) -> Optional[float]:
    """
    Calculate durability index for an athlete.
    
    Durability measures the ability to handle training load without breaking down.
    
    Signals (from manifesto):
    - Rising HR cost for easy pace → negative signal
    - Increased variability after volume ramps → negative signal
    - Micro-regressions after load spikes → negative signal
    
    Returns:
        Durability index (0-100), higher is better. None if insufficient data.
    """
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Get activities for the period
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.start_time >= start_date,
        Activity.avg_hr.isnot(None),
        Activity.average_speed.isnot(None)
    ).order_by(Activity.start_time).all()
    
    if len(activities) < 10:
        return None
    
    # Calculate weekly totals for load analysis
    weekly_loads = {}
    for activity in activities:
        week = activity.start_time.isocalendar()[1]
        year = activity.start_time.year
        key = (year, week)
        
        if key not in weekly_loads:
            weekly_loads[key] = {'distance': 0, 'duration': 0, 'activities': 0}
        
        weekly_loads[key]['distance'] += float(activity.distance_m or 0)
        weekly_loads[key]['duration'] += float(activity.duration_s or 0)
        weekly_loads[key]['activities'] += 1
    
    # Check for consistency (less variance = more durable)
    distances = [w['distance'] for w in weekly_loads.values() if w['distance'] > 0]
    
    if len(distances) < 4:
        return None
    
    avg_distance = sum(distances) / len(distances)
    variance = sum((d - avg_distance) ** 2 for d in distances) / len(distances)
    std_dev = variance ** 0.5
    
    # Coefficient of variation (lower = more consistent = more durable)
    cv = std_dev / avg_distance if avg_distance > 0 else 1
    
    # Convert to 0-100 scale (inverse - lower CV = higher durability)
    # CV of 0.1 (10% variation) = 100 durability
    # CV of 1.0 (100% variation) = 0 durability
    durability = max(0, min(100, (1 - cv) * 100))
    
    # Check for efficiency degradation during high load weeks
    # (Would need efficiency data - simplified here)
    
    return round(durability, 1)


def calculate_consistency_index(
    db: Session,
    athlete_id: str,
    days: int = 90
) -> Optional[float]:
    """
    Calculate training consistency index.
    
    Measures how consistently the athlete trains over time.
    
    Returns:
        Consistency index (0-100), higher is better. None if insufficient data.
    """
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Count activities per week
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.start_time >= start_date
    ).all()
    
    if len(activities) < 5:
        return None
    
    # Count weeks with activity
    weeks_with_activity = set()
    for activity in activities:
        week = activity.start_time.isocalendar()[1]
        year = activity.start_time.year
        weeks_with_activity.add((year, week))
    
    # Calculate expected weeks in the period
    total_weeks = days // 7
    
    if total_weeks == 0:
        return None
    
    # Consistency = percentage of weeks with activity
    consistency = (len(weeks_with_activity) / total_weeks) * 100
    
    return round(min(100, consistency), 1)


def update_athlete_metrics(db: Session, athlete_id: str) -> Dict[str, Optional[float]]:
    """
    Calculate and update all recovery/durability metrics for an athlete.
    
    Returns:
        Dict with calculated metrics
    """
    from models import Athlete
    
    recovery_half_life = calculate_recovery_half_life(db, athlete_id)
    durability_index = calculate_durability_index(db, athlete_id)
    consistency_index = calculate_consistency_index(db, athlete_id)
    
    # Update athlete record
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if athlete:
        athlete.recovery_half_life_hours = recovery_half_life
        athlete.durability_index = durability_index
        athlete.consistency_index = consistency_index
        athlete.last_metrics_calculation = datetime.utcnow()
        db.commit()
    
    logger.info(f"Updated metrics for athlete {athlete_id}: "
                f"recovery_half_life={recovery_half_life}, "
                f"durability={durability_index}, "
                f"consistency={consistency_index}")
    
    return {
        'recovery_half_life_hours': recovery_half_life,
        'durability_index': durability_index,
        'consistency_index': consistency_index
    }


def detect_false_fitness(
    db: Session,
    athlete_id: str,
    days: int = 30
) -> List[Dict]:
    """
    Detect false fitness signals (manifesto section 5).
    
    False Fitness indicators:
    - Pace improves but HR spikes
    - PBs with exploding recovery cost
    - Efficiency gains without stability
    
    Returns:
        List of warning signals detected
    """
    warnings = []
    start_date = datetime.utcnow() - timedelta(days=days)
    
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.start_time >= start_date,
        Activity.avg_hr.isnot(None),
        Activity.average_speed.isnot(None)
    ).order_by(Activity.start_time).all()
    
    if len(activities) < 5:
        return warnings
    
    # Check for pace improvement with HR spike
    first_half = activities[:len(activities)//2]
    second_half = activities[len(activities)//2:]
    
    avg_hr_first = sum(a.avg_hr for a in first_half if a.avg_hr) / len(first_half)
    avg_hr_second = sum(a.avg_hr for a in second_half if a.avg_hr) / len(second_half)
    
    avg_pace_first = sum(float(a.average_speed) for a in first_half if a.average_speed) / len(first_half)
    avg_pace_second = sum(float(a.average_speed) for a in second_half if a.average_speed) / len(second_half)
    
    # Pace improved but HR increased
    if avg_pace_second > avg_pace_first * 1.02 and avg_hr_second > avg_hr_first * 1.05:
        warnings.append({
            'type': 'false_fitness',
            'signal': 'Pace improving but HR rising',
            'severity': 'warning',
            'details': f'Pace up {((avg_pace_second/avg_pace_first)-1)*100:.1f}%, HR up {((avg_hr_second/avg_hr_first)-1)*100:.1f}%'
        })
    
    return warnings


def detect_masked_fatigue(
    db: Session,
    athlete_id: str,
    days: int = 14
) -> List[Dict]:
    """
    Detect masked fatigue signals (manifesto section 5).
    
    Masked Fatigue indicators:
    - Pace stable, HR drifting up
    - Consistency via unconscious intensity drop
    - "I feel fine" + degrading efficiency
    
    Returns:
        List of warning signals detected
    """
    warnings = []
    start_date = datetime.utcnow() - timedelta(days=days)
    
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.start_time >= start_date,
        Activity.avg_hr.isnot(None),
        Activity.average_speed.isnot(None)
    ).order_by(Activity.start_time).all()
    
    if len(activities) < 3:
        return warnings
    
    # Check for HR drift at similar pace
    # Group by similar pace, check if HR is trending up
    
    recent_activities = activities[-5:]
    earlier_activities = activities[:max(1, len(activities)-5)]
    
    if len(earlier_activities) < 2:
        return warnings
    
    avg_hr_earlier = sum(a.avg_hr for a in earlier_activities if a.avg_hr) / len(earlier_activities)
    avg_hr_recent = sum(a.avg_hr for a in recent_activities if a.avg_hr) / len(recent_activities)
    
    avg_pace_earlier = sum(float(a.average_speed) for a in earlier_activities if a.average_speed) / len(earlier_activities)
    avg_pace_recent = sum(float(a.average_speed) for a in recent_activities if a.average_speed) / len(recent_activities)
    
    # Similar pace but higher HR
    pace_change_pct = abs((avg_pace_recent - avg_pace_earlier) / avg_pace_earlier) * 100
    hr_change_pct = ((avg_hr_recent - avg_hr_earlier) / avg_hr_earlier) * 100
    
    if pace_change_pct < 3 and hr_change_pct > 5:
        warnings.append({
            'type': 'masked_fatigue',
            'signal': 'Pace stable but HR drifting up',
            'severity': 'warning',
            'details': f'Pace stable (±{pace_change_pct:.1f}%), HR up {hr_change_pct:.1f}%'
        })
    
    return warnings


