"""
Training Availability Service

Provides slot counting logic and grid operations for training availability.
"""
from sqlalchemy.orm import Session
from typing import Dict, List, Tuple
from models import TrainingAvailability, Athlete

# Day names for display
DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

# Time blocks
TIME_BLOCKS = ['morning', 'afternoon', 'evening']

# Total slots: 7 days × 3 blocks = 21 slots
TOTAL_SLOTS = 21


def get_availability_grid(athlete_id: str, db: Session) -> List[TrainingAvailability]:
    """
    Get full availability grid for an athlete.
    
    Returns all 21 slots (7 days × 3 blocks), creating missing slots as 'unavailable'.
    """
    # Get existing entries
    existing = db.query(TrainingAvailability).filter(
        TrainingAvailability.athlete_id == athlete_id
    ).all()
    
    # Create a map of existing entries
    existing_map = {(e.day_of_week, e.time_block): e for e in existing}
    
    # Build full grid
    grid = []
    for day in range(7):
        for block in TIME_BLOCKS:
            key = (day, block)
            if key in existing_map:
                grid.append(existing_map[key])
            else:
                # Create missing slot as unavailable
                slot = TrainingAvailability(
                    athlete_id=athlete_id,
                    day_of_week=day,
                    time_block=block,
                    status='unavailable'
                )
                db.add(slot)
                grid.append(slot)
    
    db.commit()
    
    # Refresh all entries
    for slot in grid:
        db.refresh(slot)
    
    return sorted(grid, key=lambda x: (x.day_of_week, TIME_BLOCKS.index(x.time_block)))


def get_availability_summary(athlete_id: str, db: Session) -> Dict:
    """
    Get summary statistics for availability grid.
    
    Returns:
        {
            "total_slots": 21,
            "available_slots": int,
            "preferred_slots": int,
            "unavailable_slots": int,
            "available_percentage": float,
            "preferred_percentage": float
        }
    """
    grid = get_availability_grid(athlete_id, db)
    
    available_count = sum(1 for slot in grid if slot.status == 'available')
    preferred_count = sum(1 for slot in grid if slot.status == 'preferred')
    unavailable_count = sum(1 for slot in grid if slot.status == 'unavailable')
    
    # Count preferred as available too (preferred is a subset of available)
    total_available = available_count + preferred_count
    
    return {
        "total_slots": TOTAL_SLOTS,
        "available_slots": available_count,
        "preferred_slots": preferred_count,
        "unavailable_slots": unavailable_count,
        "total_available_slots": total_available,
        "available_percentage": round((available_count / TOTAL_SLOTS) * 100, 1),
        "preferred_percentage": round((preferred_count / TOTAL_SLOTS) * 100, 1),
        "total_available_percentage": round((total_available / TOTAL_SLOTS) * 100, 1)
    }


def get_preferred_slots(athlete_id: str, db: Session) -> List[TrainingAvailability]:
    """Get all preferred time slots."""
    return db.query(TrainingAvailability).filter(
        TrainingAvailability.athlete_id == athlete_id,
        TrainingAvailability.status == 'preferred'
    ).all()


def get_available_slots(athlete_id: str, db: Session) -> List[TrainingAvailability]:
    """Get all available time slots (including preferred)."""
    return db.query(TrainingAvailability).filter(
        TrainingAvailability.athlete_id == athlete_id,
        TrainingAvailability.status.in_(['available', 'preferred'])
    ).all()


def validate_day_of_week(day: int) -> bool:
    """Validate day of week (0-6)."""
    return 0 <= day <= 6


def validate_time_block(block: str) -> bool:
    """Validate time block."""
    return block in TIME_BLOCKS


def validate_status(status: str) -> bool:
    """Validate status."""
    return status in ['available', 'preferred', 'unavailable']


