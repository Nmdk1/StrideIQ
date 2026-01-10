"""
Athlete Metrics Service - Calculate Derived Signals

Implements the Performance Physics Engine's derived signals per Manifesto Section 4:
- Durability Index
- Recovery Half-Life
- Consistency Index

These metrics are calculated periodically and stored on the Athlete model.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from models import Athlete, Activity


def calculate_athlete_derived_signals(
    athlete: Athlete,
    db: Session,
    force_recalculate: bool = False
) -> Dict[str, Optional[float]]:
    """
    Calculate all derived signals for an athlete and update the athlete record.
    
    This implements the Performance Physics Engine's diagnostic capabilities,
    providing insights into an athlete's training capacity and recovery patterns.
    
    Args:
        athlete: Athlete model instance
        db: Database session
        force_recalculate: If True, recalculate even if recently calculated
        
    Returns:
        Dictionary with calculated metrics:
        {
            'durability_index': float or None,
            'recovery_half_life_hours': float or None,
            'consistency_index': float or None
        }
    """
    from services.performance_engine import (
        calculate_durability_index,
        calculate_recovery_half_life,
        calculate_consistency_index,
    )
    
    # Check if we need to recalculate (only if older than 24 hours or forced)
    if not force_recalculate and athlete.last_metrics_calculation:
        # Ensure timezone-aware comparison
        last_calc = athlete.last_metrics_calculation
        if last_calc.tzinfo is None:
            last_calc = last_calc.replace(tzinfo=timezone.utc)
        time_since_calc = datetime.now(timezone.utc) - last_calc
        if time_since_calc < timedelta(hours=24):
            # Return existing values
            return {
                'durability_index': athlete.durability_index,
                'recovery_half_life_hours': athlete.recovery_half_life_hours,
                'consistency_index': athlete.consistency_index,
            }
    
    # Fetch all activities for this athlete
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete.id
    ).order_by(Activity.start_time.desc()).all()
    
    if not activities:
        # No activities, can't calculate metrics
        athlete.durability_index = None
        athlete.recovery_half_life_hours = None
        athlete.consistency_index = None
        athlete.last_metrics_calculation = datetime.now(timezone.utc)
        db.commit()
        return {
            'durability_index': None,
            'recovery_half_life_hours': None,
            'consistency_index': None,
        }
    
    # Convert activities to dict format for metric functions
    activities_data = []
    for activity in activities:
        activities_data.append({
            'start_time': activity.start_time,
            'distance_m': activity.distance_m,
            'performance_percentage': activity.performance_percentage,
            'avg_hr': activity.avg_hr,
            'max_hr': activity.max_hr,
            'is_race_candidate': activity.is_race_candidate,
        })
    
    # Calculate each metric
    durability_index = calculate_durability_index(activities_data, lookback_days=90)
    recovery_half_life = calculate_recovery_half_life(activities_data, lookback_days=30)
    consistency_index = calculate_consistency_index(activities_data, lookback_days=90)
    
    # Update athlete record
    athlete.durability_index = durability_index
    athlete.recovery_half_life_hours = recovery_half_life
    athlete.consistency_index = consistency_index
    athlete.last_metrics_calculation = datetime.now(timezone.utc)
    db.commit()
    
    return {
        'durability_index': durability_index,
        'recovery_half_life_hours': recovery_half_life,
        'consistency_index': consistency_index,
    }


