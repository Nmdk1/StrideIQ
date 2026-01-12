"""
Best Effort Service

Manages extraction, storage, and aggregation of best efforts from Strava.
Best efforts are the fastest times for standard distances WITHIN any activity
(e.g., fastest mile within a 10k run).

Architecture:
- BestEffort table: Stores ALL efforts (history, trends, age-grading)
- PersonalBest table: Aggregation of fastest per distance (derived, regenerated)
"""
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Activity, Athlete, BestEffort, PersonalBest
from services.performance_engine import calculate_age_at_date


# Map Strava effort names to our standardized categories
STRAVA_EFFORT_MAP = {
    '400m': '400m',
    '1/2 mile': None,  # Not tracked
    '1k': None,  # Not tracked
    '1 mile': 'mile',
    'mile': 'mile',
    '2 mile': '2mile',
    '5k': '5k',
    '10k': '10k',
    '15k': '15k',
    '20k': None,  # Not tracked (use half marathon)
    'half marathon': 'half_marathon',
    'half-marathon': 'half_marathon',
    '25k': '25k',
    '30k': '30k',
    'marathon': 'marathon',
    '50k': '50k',
    '100k': '100k',
}

# Standard distances in meters for validation
STANDARD_DISTANCES = {
    '400m': 400,
    '800m': 800,
    'mile': 1609,
    '2mile': 3219,
    '5k': 5000,
    '10k': 10000,
    '15k': 15000,
    'half_marathon': 21097,
    '25k': 25000,
    '30k': 30000,
    'marathon': 42195,
    '50k': 50000,
    '100k': 100000,
}


def normalize_effort_name(name: str) -> Optional[str]:
    """Convert Strava effort name to our standardized category."""
    if not name:
        return None
    normalized = name.lower().strip()
    return STRAVA_EFFORT_MAP.get(normalized)


def extract_best_efforts_from_activity(
    activity_details: Dict,
    activity: Activity,
    athlete: Athlete,
    db: Session
) -> int:
    """
    Extract and store best efforts from Strava activity details.
    
    Called during activity sync. Stores all efforts in BestEffort table.
    
    Args:
        activity_details: Raw Strava API response for activity details
        activity: Our Activity model instance
        athlete: Athlete who performed the activity
        db: Database session
        
    Returns:
        Number of best efforts stored
    """
    best_efforts = activity_details.get('best_efforts', [])
    if not best_efforts:
        return 0
    
    stored = 0
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
        
        # Parse achievement time
        start_date_str = effort.get('start_date')
        if start_date_str:
            try:
                achieved_at = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
            except:
                achieved_at = activity.start_time
        else:
            achieved_at = activity.start_time
        
        # Check for existing effort (by strava_effort_id to avoid duplicates)
        if strava_effort_id:
            existing = db.query(BestEffort).filter(
                BestEffort.activity_id == activity.id,
                BestEffort.strava_effort_id == strava_effort_id
            ).first()
            if existing:
                continue  # Already stored
        
        # Create best effort record
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
        stored += 1
    
    return stored


def regenerate_personal_bests(athlete: Athlete, db: Session) -> Dict[str, int]:
    """
    Regenerate PersonalBest records from BestEffort table.
    
    This is an aggregation: for each distance category, find the fastest effort.
    Instant operation - no external API calls.
    
    Args:
        athlete: Athlete to regenerate PBs for
        db: Database session
        
    Returns:
        Dict with counts: {'cleared': int, 'created': int, 'categories': list}
    """
    from sqlalchemy import and_
    
    # Clear existing PBs
    cleared = db.query(PersonalBest).filter(
        PersonalBest.athlete_id == athlete.id
    ).delete()
    
    # Find fastest effort per distance category
    # Subquery to get min elapsed_time per category
    subq = db.query(
        BestEffort.distance_category,
        func.min(BestEffort.elapsed_time).label('min_time')
    ).filter(
        BestEffort.athlete_id == athlete.id
    ).group_by(
        BestEffort.distance_category
    ).subquery()
    
    # Join to get the actual effort records
    fastest_efforts = db.query(BestEffort).join(
        subq,
        and_(
            BestEffort.distance_category == subq.c.distance_category,
            BestEffort.elapsed_time == subq.c.min_time,
            BestEffort.athlete_id == athlete.id
        )
    ).all()
    
    # Create PersonalBest records
    created = 0
    categories = []
    
    # Track which categories we've already processed (in case of ties)
    processed_categories = set()
    
    for effort in fastest_efforts:
        if effort.distance_category in processed_categories:
            continue
        processed_categories.add(effort.distance_category)
        
        # Get the activity for additional metadata
        activity = db.query(Activity).filter(Activity.id == effort.activity_id).first()
        
        # Calculate pace
        miles = effort.distance_meters / 1609.34
        pace_per_mile = (effort.elapsed_time / 60.0) / miles if miles > 0 else None
        
        pb = PersonalBest(
            athlete_id=athlete.id,
            distance_category=effort.distance_category,
            distance_meters=effort.distance_meters,
            time_seconds=effort.elapsed_time,
            pace_per_mile=pace_per_mile,
            activity_id=effort.activity_id,
            achieved_at=effort.achieved_at,
            is_race=activity.is_race_candidate if activity else False,
            age_at_achievement=calculate_age_at_date(athlete.birthdate, effort.achieved_at) if athlete.birthdate else None,
        )
        db.add(pb)
        created += 1
        categories.append(effort.distance_category)
    
    db.commit()
    
    return {
        'cleared': cleared,
        'created': created,
        'categories': categories,
    }


def get_best_effort_history(
    athlete_id: str,
    distance_category: str,
    db: Session,
    limit: int = 20
) -> List[BestEffort]:
    """
    Get historical best efforts for a distance category.
    
    Useful for trend analysis, age-grading over time, etc.
    """
    from uuid import UUID
    athlete_uuid = UUID(athlete_id) if isinstance(athlete_id, str) else athlete_id
    
    return db.query(BestEffort).filter(
        BestEffort.athlete_id == athlete_uuid,
        BestEffort.distance_category == distance_category
    ).order_by(
        BestEffort.elapsed_time.asc()
    ).limit(limit).all()
