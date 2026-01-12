"""
Training Availability API Router

Provides endpoints for managing training availability grid.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List
from datetime import datetime
from core.database import get_db
from core.auth import get_current_user
from models import TrainingAvailability, Athlete
from schemas import (
    TrainingAvailabilityCreate,
    TrainingAvailabilityResponse,
    TrainingAvailabilityUpdate,
    TrainingAvailabilityGridResponse
)
from services.availability_service import (
    get_availability_grid,
    get_availability_summary,
    validate_day_of_week,
    validate_time_block,
    validate_status
)

router = APIRouter(prefix="/v1/training-availability", tags=["training-availability"])


@router.get("/grid", response_model=TrainingAvailabilityGridResponse)
def get_availability_grid_endpoint(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get full availability grid for current user.
    
    Returns all 21 slots (7 days × 3 blocks) with summary statistics.
    Missing slots are created as 'unavailable'.
    """
    grid = get_availability_grid(str(current_user.id), db)
    summary = get_availability_summary(str(current_user.id), db)
    
    return {
        "athlete_id": current_user.id,
        "grid": grid,
        "summary": summary
    }


@router.post("", response_model=TrainingAvailabilityResponse, status_code=201)
def create_availability_slot(
    availability: TrainingAvailabilityCreate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create or update a single availability slot.
    
    Validates:
    - day_of_week: 0-6 (Sunday-Saturday)
    - time_block: 'morning', 'afternoon', 'evening'
    - status: 'available', 'preferred', 'unavailable'
    """
    # Validate inputs
    if not validate_day_of_week(availability.day_of_week):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="day_of_week must be between 0 (Sunday) and 6 (Saturday)"
        )
    
    if not validate_time_block(availability.time_block):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"time_block must be one of: morning, afternoon, evening"
        )
    
    if not validate_status(availability.status):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="status must be one of: available, preferred, unavailable"
        )
    
    # Check if slot already exists
    existing = db.query(TrainingAvailability).filter(
        TrainingAvailability.athlete_id == current_user.id,
        TrainingAvailability.day_of_week == availability.day_of_week,
        TrainingAvailability.time_block == availability.time_block
    ).first()
    
    if existing:
        # Update existing
        existing.status = availability.status
        existing.notes = availability.notes
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing
    
    # Create new
    db_slot = TrainingAvailability(
        athlete_id=current_user.id,
        day_of_week=availability.day_of_week,
        time_block=availability.time_block,
        status=availability.status,
        notes=availability.notes
    )
    
    db.add(db_slot)
    db.commit()
    db.refresh(db_slot)
    
    return db_slot


# NOTE: /bulk must be defined BEFORE /{slot_id} to prevent route matching issues
@router.put("/bulk", response_model=List[TrainingAvailabilityResponse])
def update_availability_grid_bulk(
    slots: List[TrainingAvailabilityCreate],
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update multiple availability slots in one request.
    
    Useful for updating the entire grid at once.
    """
    updated_slots = []
    
    for slot_data in slots:
        # Validate inputs
        if not validate_day_of_week(slot_data.day_of_week):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid day_of_week: {slot_data.day_of_week}"
            )
        
        if not validate_time_block(slot_data.time_block):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid time_block: {slot_data.time_block}"
            )
        
        if not validate_status(slot_data.status):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {slot_data.status}"
            )
        
        # Find or create slot
        existing = db.query(TrainingAvailability).filter(
            TrainingAvailability.athlete_id == current_user.id,
            TrainingAvailability.day_of_week == slot_data.day_of_week,
            TrainingAvailability.time_block == slot_data.time_block
        ).first()
        
        if existing:
            existing.status = slot_data.status
            existing.notes = slot_data.notes
            existing.updated_at = datetime.utcnow()
            updated_slots.append(existing)
        else:
            new_slot = TrainingAvailability(
                athlete_id=current_user.id,
                day_of_week=slot_data.day_of_week,
                time_block=slot_data.time_block,
                status=slot_data.status,
                notes=slot_data.notes
            )
            db.add(new_slot)
            updated_slots.append(new_slot)
    
    db.commit()
    
    # Refresh all
    for slot in updated_slots:
        db.refresh(slot)
    
    return updated_slots


@router.put("/{slot_id}", response_model=TrainingAvailabilityResponse)
def update_availability_slot(
    slot_id: UUID,
    availability_update: TrainingAvailabilityUpdate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update an existing availability slot.
    
    Only updates provided fields.
    """
    slot = db.query(TrainingAvailability).filter(TrainingAvailability.id == slot_id).first()
    if not slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Availability slot {slot_id} not found"
        )
    
    if slot.athlete_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this availability slot"
        )
    
    # Validate status if provided
    if availability_update.status is not None:
        if not validate_status(availability_update.status):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="status must be one of: available, preferred, unavailable"
            )
        slot.status = availability_update.status
    
    if availability_update.notes is not None:
        slot.notes = availability_update.notes
    
    slot.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(slot)
    
    return slot


@router.delete("/{slot_id}", status_code=204)
def delete_availability_slot(
    slot_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete an availability slot.
    
    Sets it back to 'unavailable' rather than deleting (maintains grid structure).
    """
    slot = db.query(TrainingAvailability).filter(TrainingAvailability.id == slot_id).first()
    if not slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Availability slot {slot_id} not found"
        )
    
    if slot.athlete_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this availability slot"
        )
    
    # Set to unavailable rather than deleting
    slot.status = 'unavailable'
    slot.notes = None
    slot.updated_at = datetime.utcnow()
    
    db.commit()
    
    return None


@router.get("/summary", response_model=dict)
def get_availability_summary_endpoint(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get availability summary statistics.
    
    Returns slot counts and percentages.
    """
    return get_availability_summary(str(current_user.id), db)


