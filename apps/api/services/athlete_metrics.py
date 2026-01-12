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


def estimate_max_hr(
    athlete: Athlete,
    db: Session,
    force_update: bool = False
) -> Optional[int]:
    """
    Estimate max heart rate for an athlete if not already set.
    
    Strategy:
    1. If user has set max_hr, respect it (user override)
    2. Otherwise, estimate from observed max HR during hard efforts (best)
    3. Fallback: 220 - age formula (rough estimate)
    
    Args:
        athlete: Athlete model instance
        db: Database session
        force_update: If True, recalculate even if already set
        
    Returns:
        Estimated max_hr or None if unable to estimate
    """
    # Don't override user-set value unless forced
    if athlete.max_hr and not force_update:
        return athlete.max_hr
    
    # Strategy 1: Get max observed HR from hard efforts (races or high-intensity workouts)
    from sqlalchemy import func
    
    # Get the 95th percentile of max_hr from activities to avoid outliers
    max_hr_result = db.query(func.percentile_cont(0.95).within_group(Activity.max_hr)).filter(
        Activity.athlete_id == athlete.id,
        Activity.max_hr.isnot(None),
        Activity.max_hr > 100  # Filter unrealistic values
    ).scalar()
    
    if max_hr_result and max_hr_result > 150:
        # Valid observed max HR
        estimated_max_hr = int(round(max_hr_result))
        
        # Update athlete if not user-set
        if not athlete.max_hr or force_update:
            athlete.max_hr = estimated_max_hr
            db.commit()
        
        return estimated_max_hr
    
    # Strategy 2: Fallback to 220 - age formula
    if athlete.birthdate:
        from services.performance_engine import calculate_age_at_date
        age = calculate_age_at_date(athlete.birthdate, datetime.now())
        
        if age and age > 0:
            # Classic formula (rough but better than nothing)
            estimated_max_hr = 220 - age
            
            # Update athlete if not user-set
            if not athlete.max_hr or force_update:
                athlete.max_hr = estimated_max_hr
                db.commit()
            
            return estimated_max_hr
    
    return None


def estimate_vdot(
    athlete: Athlete,
    db: Session,
    force_update: bool = False
) -> Optional[float]:
    """
    Estimate VDOT for an athlete from their best recent race/effort.
    
    Strategy:
    1. If user has set VDOT, respect it (user override)
    2. Otherwise, calculate from best PersonalBest record
    3. Fallback: estimate from recent running activities
    
    Args:
        athlete: Athlete model instance
        db: Database session
        force_update: If True, recalculate even if already set
        
    Returns:
        Estimated VDOT or None if unable to estimate
    """
    from services.vdot_calculator import calculate_vdot_from_race_time
    from models import PersonalBest
    
    # Don't override user-set value unless forced
    if athlete.vdot and not force_update:
        return athlete.vdot
    
    # Strategy 1: Calculate from best PersonalBest (most accurate)
    # Prefer race-verified PBs, but use any PB if no races
    best_pb = db.query(PersonalBest).filter(
        PersonalBest.athlete_id == athlete.id,
        PersonalBest.is_race == True
    ).order_by(PersonalBest.achieved_at.desc()).first()
    
    if not best_pb:
        # Fallback to any PB
        best_pb = db.query(PersonalBest).filter(
            PersonalBest.athlete_id == athlete.id
        ).order_by(PersonalBest.achieved_at.desc()).first()
    
    if best_pb and best_pb.distance_meters and best_pb.time_seconds:
        vdot = calculate_vdot_from_race_time(
            distance_meters=best_pb.distance_meters,
            time_seconds=best_pb.time_seconds
        )
        
        if vdot and vdot > 20:  # Sanity check (VDOT < 20 is unrealistic)
            # Update athlete if not user-set
            if not athlete.vdot or force_update:
                athlete.vdot = round(vdot, 1)
                db.commit()
            
            return vdot
    
    # Strategy 2: Estimate from recent running activities
    # Use best average pace from a sustained effort (30+ min runs)
    recent_runs = db.query(Activity).filter(
        Activity.athlete_id == athlete.id,
        Activity.sport == 'run',
        Activity.duration_s >= 1800,  # 30+ minutes
        Activity.distance_m >= 4000,  # 4+ km
        Activity.average_speed.isnot(None)
    ).order_by(Activity.start_time.desc()).limit(10).all()
    
    if recent_runs:
        # Find the fastest sustained effort
        best_vdot = None
        for run in recent_runs:
            if run.distance_m and run.duration_s:
                vdot = calculate_vdot_from_race_time(
                    distance_meters=run.distance_m,
                    time_seconds=run.duration_s
                )
                if vdot and (best_vdot is None or vdot > best_vdot):
                    best_vdot = vdot
        
        if best_vdot and best_vdot > 20:
            # Apply a slight discount since this isn't a race effort
            # (people typically run ~5-10% slower in training)
            estimated_vdot = round(best_vdot * 0.95, 1)
            
            # Update athlete if not user-set
            if not athlete.vdot or force_update:
                athlete.vdot = estimated_vdot
                db.commit()
            
            return estimated_vdot
    
    return None


def auto_estimate_athlete_thresholds(
    athlete: Athlete,
    db: Session,
    force_update: bool = False
) -> Dict[str, Optional[float]]:
    """
    Auto-estimate missing max_hr and VDOT for an athlete.
    
    This is an optional enhancement that fills in values if not set.
    User-provided values are always respected unless force_update=True.
    
    Args:
        athlete: Athlete model instance
        db: Database session
        force_update: If True, recalculate even if already set
        
    Returns:
        Dictionary with estimated values:
        {
            'max_hr': int or None,
            'vdot': float or None,
            'max_hr_source': 'user' | 'observed' | 'age_formula' | None,
            'vdot_source': 'user' | 'personal_best' | 'training_estimate' | None
        }
    """
    max_hr = estimate_max_hr(athlete, db, force_update)
    vdot = estimate_vdot(athlete, db, force_update)
    
    # Determine sources
    max_hr_source = None
    if athlete.max_hr:
        # Check if it matches age formula to guess source
        if athlete.birthdate:
            from services.performance_engine import calculate_age_at_date
            age = calculate_age_at_date(athlete.birthdate, datetime.now())
            if age and abs(athlete.max_hr - (220 - age)) <= 1:
                max_hr_source = 'age_formula'
            else:
                max_hr_source = 'observed'
        else:
            max_hr_source = 'observed'
    
    vdot_source = None
    if athlete.vdot:
        # If we have personal bests, assume VDOT came from there
        from models import PersonalBest
        has_pbs = db.query(PersonalBest).filter(
            PersonalBest.athlete_id == athlete.id
        ).count() > 0
        vdot_source = 'personal_best' if has_pbs else 'training_estimate'
    
    return {
        'max_hr': max_hr,
        'vdot': vdot,
        'max_hr_source': max_hr_source,
        'vdot_source': vdot_source
    }

