"""
Strava Best Efforts Integration

Pulls best efforts from Strava's API and stores them in the BestEffort table.
PersonalBest is then a simple aggregation of fastest per distance.

Architecture:
- sync_strava_best_efforts: Fetches and stores best efforts (runs during Strava sync)
- BestEffort table: Stores ALL efforts for history/trends
- PersonalBest: Regenerated from BestEffort (MIN per distance)
"""
from typing import Dict, List, Optional
from datetime import datetime
from models import Athlete, Activity, BestEffort
from services.strava_service import get_activity_details
from services.best_effort_service import normalize_effort_name, regenerate_personal_bests
from sqlalchemy.orm import Session
import time


def sync_strava_best_efforts(athlete: Athlete, db: Session, limit: int = 200) -> Dict[str, int]:
    """
    Sync best efforts from Strava's API into the BestEffort table.
    
    Strava's "best efforts" are segments within activities (e.g., fastest mile within a 10-mile run).
    This function fetches activity details and extracts best_efforts.
    
    After storing, it regenerates PersonalBest from the BestEffort table.
    
    Args:
        athlete: Athlete with Strava connection
        db: Database session
        limit: Maximum number of activities to check
        
    Returns:
        Dict with counts: {'activities_checked': int, 'efforts_stored': int, 'pbs_created': int}
    """
    if not athlete.strava_access_token:
        return {'activities_checked': 0, 'efforts_stored': 0, 'pbs_created': 0}
    
    # Get activities from our database that haven't had best efforts extracted
    # We check if they have any BestEffort records already
    from sqlalchemy import func, and_
    
    # Subquery: activity IDs that already have best efforts
    activities_with_efforts = db.query(BestEffort.activity_id).filter(
        BestEffort.athlete_id == athlete.id
    ).distinct().subquery()
    
    # Get activities without best efforts, ordered by most recent
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete.id,
        Activity.provider == 'strava',
        Activity.external_activity_id.isnot(None),
        ~Activity.id.in_(activities_with_efforts)  # Not already processed
    ).order_by(Activity.start_time.desc()).limit(limit).all()
    
    if not activities:
        # All activities already processed, just regenerate PBs
        pb_result = regenerate_personal_bests(athlete, db)
        return {
            'activities_checked': 0,
            'efforts_stored': 0,
            'pbs_created': pb_result.get('created', 0),
        }
    
    efforts_stored = 0
    activities_checked = 0
    
    for activity_idx, activity in enumerate(activities):
        try:
            activity_id = int(activity.external_activity_id)
        except (ValueError, TypeError):
            continue
        
        # Rate limit: brief pause every 10 activities
        if activity_idx > 0 and activity_idx % 10 == 0:
            time.sleep(0.5)
        
        try:
            details = get_activity_details(athlete, activity_id)
        except Exception as e:
            error_str = str(e).lower()
            if "429" in str(e) or "rate" in error_str or "too many" in error_str:
                print(f"Rate limited at activity {activity_idx}/{len(activities)}, stopping sync early")
                break
            continue
        
        if not details:
            continue
        
        best_efforts = details.get('best_efforts', [])
        if not best_efforts:
            activities_checked += 1
            continue
        
        # Extract and store best efforts
        for effort in best_efforts:
            effort_name = effort.get('name', '')
            category = normalize_effort_name(effort_name)
            if not category:
                continue
            
            distance_meters = effort.get('distance', 0)
            elapsed_time = effort.get('elapsed_time', 0)
            strava_effort_id = effort.get('id')
            
            if not distance_meters or not elapsed_time:
                continue
            
            # Parse start date
            start_date_str = effort.get('start_date')
            try:
                if start_date_str:
                    achieved_at = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
                else:
                    achieved_at = activity.start_time
            except:
                achieved_at = activity.start_time
            
            # Check for existing effort (avoid duplicates)
            if strava_effort_id:
                existing = db.query(BestEffort).filter(
                    BestEffort.activity_id == activity.id,
                    BestEffort.strava_effort_id == strava_effort_id
                ).first()
                if existing:
                    continue
            
            # Create BestEffort record
            best_effort = BestEffort(
                athlete_id=athlete.id,
                activity_id=activity.id,
                distance_category=category,
                distance_meters=int(distance_meters),
                elapsed_time=int(elapsed_time),
                achieved_at=achieved_at,
                strava_effort_id=strava_effort_id,
            )
            db.add(best_effort)
            efforts_stored += 1
        
        activities_checked += 1
    
    db.flush()
    
    # Regenerate PersonalBest from all BestEfforts
    pb_result = regenerate_personal_bests(athlete, db)
    
    return {
        'activities_checked': activities_checked,
        'efforts_stored': efforts_stored,
        'pbs_created': pb_result.get('created', 0),
    }
