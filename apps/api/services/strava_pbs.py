"""
Strava Personal Bests Integration

Pulls personal bests from Strava's "Best Efforts" feature.
Strava automatically calculates best efforts for standard distances from GPS data.
These are segments within activities (e.g., fastest mile within a 10-mile run).
"""
from typing import Dict, List, Optional
from datetime import datetime
from models import Athlete, Activity, PersonalBest
from services.strava_service import get_activity_details
from services.personal_best import get_distance_category, calculate_age_at_date
from sqlalchemy.orm import Session


# Map Strava best effort types to our distance categories
# Strava uses various naming conventions, so we check multiple variations
STRAVA_BEST_EFFORT_MAP = {
    '400m': '400m',
    '800m': '800m',
    '1k': None,  # Not in our categories
    '1 mile': 'mile',
    '1mile': 'mile',
    'mile': 'mile',
    '1/2 mile': None,  # Not in our categories
    '2 mile': '2mile',
    '2mile': '2mile',
    '5k': '5k',
    '5 k': '5k',
    '10k': '10k',
    '10 k': '10k',
    '15k': '15k',
    '15 k': '15k',
    '25k': '25k',
    '30k': '30k',
    '30 k': '30k',
    '50k': '50k',
    '100k': '100k',
    'half marathon': 'half_marathon',
    'half-marathon': 'half_marathon',
    'half_marathon': 'half_marathon',
    'marathon': 'marathon',
}


def sync_strava_best_efforts(athlete: Athlete, db: Session, limit: int = 200) -> Dict[str, int]:
    """
    Sync personal bests from Strava's best efforts.
    
    Strava's "best efforts" are segments within activities (e.g., fastest mile within a 10-mile run).
    We use activities already in our DB and fetch their best_efforts from Strava API.
    
    Args:
        athlete: Athlete with Strava connection
        db: Database session
        limit: Maximum number of activities to check
        
    Returns:
        Dict with counts: {'synced': int, 'updated': int, 'created': int, 'total_categories': int}
    """
    if not athlete.strava_access_token:
        return {'synced': 0, 'updated': 0, 'created': 0, 'total_categories': 0}
    
    # Use activities already in our database (no need to poll Strava again)
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete.id,
        Activity.provider == 'strava',
        Activity.external_activity_id.isnot(None)
    ).order_by(Activity.start_time.desc()).limit(limit).all()
    
    if not activities:
        return {'synced': 0, 'updated': 0, 'created': 0, 'total_categories': 0}
    
    best_efforts_by_category = {}  # category -> (time_seconds, activity_id, achieved_at, distance_meters)
    synced_count = 0
    
    # Load existing PBs to compare against
    existing_pbs_map = {pb.distance_category: pb for pb in db.query(PersonalBest).filter(PersonalBest.athlete_id == athlete.id).all()}
    
    import time
    for activity_idx, activity in enumerate(activities):
        try:
            activity_id = int(activity.external_activity_id)
        except (ValueError, TypeError):
            continue
        
        # Get detailed activity to access best_efforts
        # Add delay between calls to avoid rate limits
        if activity_idx > 0 and activity_idx % 10 == 0:
            time.sleep(0.3)  # Brief delay every 10 calls
        
        try:
            details = get_activity_details(athlete, activity_id)
        except Exception as e:
            # Skip on error, don't fail entire sync
            error_str = str(e).lower()
            if "429" in str(e) or "rate" in error_str or "too many" in error_str:
                print(f"Rate limited at activity {activity_idx}/{len(activities)}, stopping sync early")
                break
            continue
        
        if not details:
            continue
        
        best_efforts = details.get('best_efforts', [])
        if not best_efforts:
            continue
        
        # Extract best efforts
        for effort in best_efforts:
            effort_type = effort.get('name', '').lower()
            distance_meters = effort.get('distance', 0)
            elapsed_time = effort.get('elapsed_time', 0)
            start_date = effort.get('start_date')
            
            if not distance_meters or not elapsed_time:
                continue
            
            # Map Strava effort type to our category
            # Strava uses "1 mile", "2 mile", "5K", "10K", "Half-Marathon" etc.
            normalized = effort_type.lower().replace(' ', '').replace('-', '_').replace('/', '')
            category = STRAVA_BEST_EFFORT_MAP.get(effort_type) or STRAVA_BEST_EFFORT_MAP.get(normalized)
            if not category:
                # Try to match by distance
                category = get_distance_category(distance_meters)
            
            if not category:
                continue
            
            # Parse start date
            try:
                if isinstance(start_date, str):
                    achieved_at = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                else:
                    achieved_at = activity.start_time
            except:
                achieved_at = activity.start_time
            
            # Track best time for each category from Strava's data
            current_best_effort = best_efforts_by_category.get(category)
            if not current_best_effort or elapsed_time < current_best_effort[0]:
                best_efforts_by_category[category] = (elapsed_time, activity_id, achieved_at, distance_meters)
        
        synced_count += 1
    
    # Update/create PB records
    created = 0
    updated = 0
    
    for category, (time_seconds, strava_activity_id, achieved_at, distance_meters) in best_efforts_by_category.items():
        # Find existing PB in our DB
        existing_pb = existing_pbs_map.get(category)
        
        # Find the activity in our DB (linked by external_activity_id)
        db_activity = db.query(Activity).filter(
            Activity.external_activity_id == str(strava_activity_id),
            Activity.provider == 'strava'
        ).first()
        
        # Skip if we can't link to an activity (required field)
        if not db_activity:
            continue
        
        if existing_pb:
            # Update if this Strava effort is faster
            if time_seconds < existing_pb.time_seconds:
                existing_pb.time_seconds = time_seconds
                existing_pb.distance_meters = int(distance_meters)
                existing_pb.activity_id = db_activity.id
                existing_pb.achieved_at = achieved_at
                existing_pb.is_race = db_activity.is_race_candidate or False
                existing_pb.age_at_achievement = calculate_age_at_date(athlete.birthdate, achieved_at) if athlete.birthdate else None
                
                miles = distance_meters / 1609.34
                if miles > 0:
                    existing_pb.pace_per_mile = (time_seconds / 60.0) / miles
                
                db.add(existing_pb)
                updated += 1
        else:
            # Create new PB from Strava best effort
            pb = PersonalBest(
                athlete_id=athlete.id,
                distance_category=category,
                distance_meters=int(distance_meters),
                time_seconds=time_seconds,
                activity_id=db_activity.id,
                achieved_at=achieved_at,
                is_race=db_activity.is_race_candidate or False,
                age_at_achievement=calculate_age_at_date(athlete.birthdate, achieved_at) if athlete.birthdate else None,
            )
            
            miles = distance_meters / 1609.34
            if miles > 0:
                pb.pace_per_mile = (time_seconds / 60.0) / miles
            
            db.add(pb)
            created += 1
    
    db.flush()  # Flush to ensure changes are tracked by the session
    
    return {
        'synced': synced_count,
        'updated': updated,
        'created': created,
        'total_categories': len(best_efforts_by_category)
    }
