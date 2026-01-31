"""
Personal Best (PB) Tracking Service

Tracks fastest times for athletes across standard distances with GPS tolerance handling.
Implements distance category matching with tolerances for imperfect race measurements.
"""
import logging
from datetime import datetime
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from models import Activity, PersonalBest, Athlete
from services.performance_engine import calculate_age_at_date
from services.vdot_calculator import calculate_vdot_from_race_time

logger = logging.getLogger(__name__)


# Distance categories with tolerance ranges (in meters)
DISTANCE_CATEGORIES = {
    '400m': (380, 420),  # 400m ± 20m
    '800m': (780, 820),  # 800m ± 20m
    'mile': (1570, 1660),  # 1609.34m ± 50m (GPS can be off, especially on tracks)
    '2mile': (3180, 3270),  # 3218.68m ± 45m
    '5k': (4957, 5311),  # 5000m, tolerance: 3.08-3.3 miles (4957-5311m)
    '10k': (9914, 10622),  # 10000m, tolerance: 6.16-6.6 miles (9914-10622m)
    '15k': (14850, 15150),  # 15000m ± 150m
    '25k': (24750, 25250),  # 25000m ± 250m
    '30k': (29700, 30300),  # 30000m ± 300m
    '50k': (49500, 50500),  # 50000m ± 500m
    '100k': (99000, 101000),  # 100000m ± 1000m
    'half_marathon': (21000, 21300),  # 21097.5m ± 150m (GPS can be off)
    'marathon': (42000, 42400),  # 42195m ± 200m
}


def get_distance_category(distance_meters: float) -> Optional[str]:
    """
    Determine which distance category an activity matches, accounting for GPS tolerance.
    
    Args:
        distance_meters: Activity distance in meters
        
    Returns:
        Distance category name or None if no match
    """
    if not distance_meters or distance_meters <= 0:
        return None
    
    # Check each category (check longer distances first to avoid false matches)
    # Sort by distance descending to match longest first
    sorted_categories = sorted(
        DISTANCE_CATEGORIES.items(),
        key=lambda x: x[1][1],  # Sort by upper bound
        reverse=True
    )
    
    for category, (min_m, max_m) in sorted_categories:
        if min_m <= distance_meters <= max_m:
            return category
    
    return None


def _update_vdot_from_pb(athlete: Athlete, pb: PersonalBest, db: Session) -> None:
    """
    Update athlete's VDOT from a new personal best if it's better than current.
    
    Uses standard race distances (5K, 10K, half marathon, marathon) for VDOT calculation.
    Shorter distances (400m, 800m, mile) are less reliable for VDOT estimation.
    """
    # Only use standard race distances for VDOT (short distances less reliable)
    VDOT_ELIGIBLE_DISTANCES = {'5k', '10k', '15k', 'half_marathon', 'marathon', '25k', '30k'}
    
    if pb.distance_category not in VDOT_ELIGIBLE_DISTANCES:
        return
    
    if not pb.distance_meters or not pb.time_seconds:
        return
    
    try:
        new_vdot = calculate_vdot_from_race_time(
            distance_meters=pb.distance_meters,
            time_seconds=pb.time_seconds
        )
        
        if not new_vdot or new_vdot < 20:  # Sanity check
            return
        
        new_vdot = round(new_vdot, 1)
        
        # Update if no VDOT or new one is higher (better)
        if not athlete.vdot or new_vdot > athlete.vdot:
            logger.info(f"Updating VDOT for {athlete.id}: {athlete.vdot} -> {new_vdot} from {pb.distance_category} PB")
            athlete.vdot = new_vdot
            db.flush()
    except Exception as e:
        logger.warning(f"Failed to calculate VDOT from PB for {athlete.id}: {e}")


def update_personal_best(
    activity: Activity,
    athlete: Athlete,
    db: Session
) -> Optional[PersonalBest]:
    """
    Check if an activity sets a new personal best and update the PB record.
    
    Args:
        activity: Activity to check
        athlete: Athlete who performed the activity
        db: Database session
        
    Returns:
        PersonalBest record if a new PB was set, None otherwise
    """
    if not activity.distance_m or not activity.duration_s:
        return None
    
    distance_meters = float(activity.distance_m)
    time_seconds = activity.duration_s
    
    # Determine distance category
    category = get_distance_category(distance_meters)
    if not category:
        return None  # Not a standard distance
    
    # Check if this is a PB (faster time for this distance category)
    existing_pb = db.query(PersonalBest).filter(
        PersonalBest.athlete_id == athlete.id,
        PersonalBest.distance_category == category
    ).first()
    
    is_new_pb = False
    if existing_pb:
        # New PB if time is faster (lower seconds)
        if time_seconds < existing_pb.time_seconds:
            is_new_pb = True
            # Update existing PB
            existing_pb.distance_meters = int(distance_meters)
            existing_pb.time_seconds = time_seconds
            existing_pb.activity_id = activity.id
            existing_pb.achieved_at = activity.start_time
            existing_pb.is_race = activity.is_race_candidate or False
            existing_pb.age_at_achievement = calculate_age_at_date(athlete.birthdate, activity.start_time)
            
            # Calculate pace
            miles = distance_meters / 1609.34
            if miles > 0:
                existing_pb.pace_per_mile = (time_seconds / 60.0) / miles
            
            db.flush()  # Use flush instead of commit to avoid nested transaction issues
            
            # Update athlete's VDOT from new PB
            _update_vdot_from_pb(athlete, existing_pb, db)
            
            return existing_pb
    else:
        # No existing PB, this is automatically a PB
        is_new_pb = True
        pb = PersonalBest(
            athlete_id=athlete.id,
            distance_category=category,
            distance_meters=int(distance_meters),
            time_seconds=time_seconds,
            activity_id=activity.id,
            achieved_at=activity.start_time,
            is_race=activity.is_race_candidate or False,
            age_at_achievement=calculate_age_at_date(athlete.birthdate, activity.start_time)
        )
        
        # Calculate pace
        miles = distance_meters / 1609.34
        if miles > 0:
            pb.pace_per_mile = (time_seconds / 60.0) / miles
        
        db.add(pb)
        db.flush()  # Use flush instead of commit to avoid nested transaction issues
        
        # Update athlete's VDOT from new PB
        _update_vdot_from_pb(athlete, pb, db)
        
        return pb
    
    return None


def get_personal_bests(athlete_id: str, db: Session) -> List[PersonalBest]:
    """
    Get all personal bests for an athlete.
    
    Args:
        athlete_id: Athlete UUID (as string)
        db: Database session
        
    Returns:
        List of PersonalBest records
    """
    from uuid import UUID
    # Convert string to UUID for proper comparison
    athlete_uuid = UUID(athlete_id) if isinstance(athlete_id, str) else athlete_id
    return db.query(PersonalBest).filter(
        PersonalBest.athlete_id == athlete_uuid
    ).order_by(PersonalBest.achieved_at.desc()).all()


def recalculate_all_pbs(athlete: Athlete, db: Session, preserve_strava_pbs: bool = True) -> Dict[str, int]:
    """
    Recalculate all personal bests for an athlete from their activity history.
    
    This ensures EVERY activity that matches a distance category creates/updates a PB.
    The fastest time for each category becomes the PB.
    
    Args:
        athlete: Athlete to recalculate PBs for
        db: Database session
        preserve_strava_pbs: If True, don't delete PBs that came from Strava (marked by activity_id linking to Strava activities)
        
    Returns:
        Dictionary with counts: {'updated': int, 'created': int, 'total': int}
    """
    # Delete all existing PBs for this athlete (but preserve Strava-sourced ones if requested)
    if preserve_strava_pbs:
        # Only delete PBs that don't have a linked activity (or linked to non-Strava activities)
        # Actually, we'll keep all PBs and just update them if faster
        pass  # Don't delete, just update
    else:
        db.query(PersonalBest).filter(PersonalBest.athlete_id == athlete.id).delete()
        db.commit()
    
    # Get all activities with distance and time, ordered by start_time ascending
    # This ensures we process chronologically
    activities = db.query(Activity).filter(
        Activity.athlete_id == athlete.id,
        Activity.distance_m.isnot(None),
        Activity.duration_s.isnot(None),
        Activity.distance_m > 0,
        Activity.duration_s > 0
    ).order_by(Activity.start_time.asc()).all()
    
    if not activities:
        return {
            'created': 0,
            'updated': 0,
            'total': 0
        }
    
    # Group activities by distance category and find fastest for each
    pbs_by_category = {}
    
    for activity in activities:
        try:
            distance_meters = float(activity.distance_m)
            time_seconds = int(activity.duration_s)
            
            if distance_meters <= 0 or time_seconds <= 0:
                continue
            
            category = get_distance_category(distance_meters)
            if not category:
                continue
            
            # Track fastest time for each category
            if category not in pbs_by_category:
                pbs_by_category[category] = activity
            else:
                # If this activity is faster, replace
                if time_seconds < pbs_by_category[category].duration_s:
                    pbs_by_category[category] = activity
        except (ValueError, TypeError) as e:
            print(f"Warning: Skipping activity {activity.id} due to invalid data: {e}")
            continue
    
    # Create/update PB records for each category
    created = 0
    updated = 0
    for category, activity in pbs_by_category.items():
        try:
            distance_meters = float(activity.distance_m)
            time_seconds = int(activity.duration_s)
            
            # Check if PB already exists
            existing_pb = db.query(PersonalBest).filter(
                PersonalBest.athlete_id == athlete.id,
                PersonalBest.distance_category == category
            ).first()
            
            if existing_pb:
                # Only update if this activity is faster
                if time_seconds < existing_pb.time_seconds:
                    existing_pb.distance_meters = int(distance_meters)
                    existing_pb.time_seconds = time_seconds
                    existing_pb.activity_id = activity.id
                    existing_pb.achieved_at = activity.start_time
                    existing_pb.is_race = activity.is_race_candidate or False
                    existing_pb.age_at_achievement = calculate_age_at_date(athlete.birthdate, activity.start_time) if athlete.birthdate else None
                    
                    miles = distance_meters / 1609.34
                    if miles > 0:
                        existing_pb.pace_per_mile = (time_seconds / 60.0) / miles
                    
                    db.add(existing_pb)
                    updated += 1
            else:
                # Create new PB
                pb = PersonalBest(
                    athlete_id=athlete.id,
                    distance_category=category,
                    distance_meters=int(distance_meters),
                    time_seconds=time_seconds,
                    activity_id=activity.id,
                    achieved_at=activity.start_time,
                    is_race=activity.is_race_candidate or False,
                    age_at_achievement=calculate_age_at_date(athlete.birthdate, activity.start_time) if athlete.birthdate else None
                )
                
                miles = distance_meters / 1609.34
                if miles > 0:
                    pb.pace_per_mile = (time_seconds / 60.0) / miles
                
                db.add(pb)
                created += 1
        except Exception as e:
            print(f"Warning: Could not create PB for category {category}: {e}")
            continue
    
    db.commit()
    
    total_pbs = db.query(PersonalBest).filter(PersonalBest.athlete_id == athlete.id).count()
    
    return {
        'created': created,
        'updated': updated,
        'total': total_pbs
    }


def backfill_vdot_from_pbs(db: Session, athlete_id: Optional[str] = None) -> Dict[str, int]:
    """
    Backfill VDOT for athletes from their personal bests.
    
    Useful for fixing athletes who have PBs but missing VDOT.
    
    Args:
        db: Database session
        athlete_id: Optional specific athlete ID (if None, backfills all athletes)
        
    Returns:
        Dictionary with counts: {'updated': int, 'skipped': int, 'errors': int}
    """
    from uuid import UUID
    
    VDOT_ELIGIBLE_DISTANCES = {'5k', '10k', '15k', 'half_marathon', 'marathon', '25k', '30k'}
    
    updated = 0
    skipped = 0
    errors = 0
    
    # Get athletes to process
    if athlete_id:
        athlete_uuid = UUID(athlete_id) if isinstance(athlete_id, str) else athlete_id
        athletes = db.query(Athlete).filter(Athlete.id == athlete_uuid).all()
    else:
        # All athletes without VDOT
        athletes = db.query(Athlete).filter(Athlete.vdot.is_(None)).all()
    
    for athlete in athletes:
        try:
            # Get best PB from eligible distances
            pbs = db.query(PersonalBest).filter(
                PersonalBest.athlete_id == athlete.id,
                PersonalBest.distance_category.in_(VDOT_ELIGIBLE_DISTANCES)
            ).all()
            
            if not pbs:
                skipped += 1
                continue
            
            # Calculate VDOT from each PB and take the best
            best_vdot = None
            best_pb = None
            
            for pb in pbs:
                if not pb.distance_meters or not pb.time_seconds:
                    continue
                    
                vdot = calculate_vdot_from_race_time(
                    distance_meters=pb.distance_meters,
                    time_seconds=pb.time_seconds
                )
                
                if vdot and vdot > 20 and (best_vdot is None or vdot > best_vdot):
                    best_vdot = vdot
                    best_pb = pb
            
            if best_vdot:
                athlete.vdot = round(best_vdot, 1)
                logger.info(f"Backfilled VDOT for {athlete.id}: {athlete.vdot} from {best_pb.distance_category}")
                updated += 1
            else:
                skipped += 1
                
        except Exception as e:
            logger.error(f"Error backfilling VDOT for {athlete.id}: {e}")
            errors += 1
    
    db.commit()
    
    return {
        'updated': updated,
        'skipped': skipped,
        'errors': errors
    }

