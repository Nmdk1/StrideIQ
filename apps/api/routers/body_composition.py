"""
Body Composition API Endpoints

Handles body composition tracking including automatic BMI calculation.
BMI is calculated automatically when weight is recorded.

Strategy: BMI stored internally, revealed when meaningful correlations are found.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from decimal import Decimal

from core.database import get_db
from core.auth import get_current_user
from core.cache import invalidate_athlete_cache, invalidate_correlation_cache
from models import Athlete, BodyComposition
from schemas import BodyCompositionCreate, BodyCompositionResponse
from services.bmi_calculator import calculate_bmi

router = APIRouter(prefix="/v1", tags=["body_composition"])


@router.post("/body-composition", response_model=BodyCompositionResponse, status_code=201)
def create_body_composition(
    body_comp: BodyCompositionCreate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new body composition entry.
    
    BMI is calculated automatically if weight_kg and athlete height are available.
    BMI is stored internally for correlation analysis but may not be shown on dashboard
    until meaningful correlations are identified.
    """
    # Use authenticated user's ID (ignore any athlete_id in request body)
    athlete = current_user
    
    # Check for existing entry on this date
    existing = db.query(BodyComposition).filter(
        BodyComposition.athlete_id == current_user.id,
        BodyComposition.date == body_comp.date
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Body composition entry already exists for date {body_comp.date}"
        )
    
    # Calculate BMI automatically if weight and height are available
    bmi = None
    if body_comp.weight_kg is not None and athlete.height_cm is not None:
        bmi = calculate_bmi(
            weight_kg=Decimal(str(body_comp.weight_kg)),
            height_cm=Decimal(str(athlete.height_cm))
        )
    
    # Create body composition entry
    db_body_comp = BodyComposition(
        athlete_id=current_user.id,
        date=body_comp.date,
        weight_kg=Decimal(str(body_comp.weight_kg)) if body_comp.weight_kg else None,
        body_fat_pct=Decimal(str(body_comp.body_fat_pct)) if body_comp.body_fat_pct else None,
        muscle_mass_kg=Decimal(str(body_comp.muscle_mass_kg)) if body_comp.muscle_mass_kg else None,
        bmi=bmi,
        measurements_json=body_comp.measurements_json,
        notes=body_comp.notes
    )
    
    db.add(db_body_comp)
    db.commit()
    db.refresh(db_body_comp)
    
    # Invalidate cache (body comp affects correlations)
    invalidate_athlete_cache(str(current_user.id))
    invalidate_correlation_cache(str(current_user.id))
    
    return db_body_comp


@router.get("/body-composition", response_model=List[BodyCompositionResponse])
def get_body_composition(
    current_user: Athlete = Depends(get_current_user),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get body composition entries for the authenticated user.
    
    Can filter by date range.
    BMI is included in response but may not be displayed on dashboard
    until correlations are identified.
    """
    # Filter by authenticated user's ID only
    query = db.query(BodyComposition).filter(BodyComposition.athlete_id == current_user.id)
    
    if start_date:
        query = query.filter(BodyComposition.date >= start_date)
    if end_date:
        query = query.filter(BodyComposition.date <= end_date)
    
    entries = query.order_by(BodyComposition.date.desc()).all()
    return entries


@router.get("/body-composition/{id}", response_model=BodyCompositionResponse)
def get_body_composition_by_id(
    id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific body composition entry by ID."""
    entry = db.query(BodyComposition).filter(BodyComposition.id == id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Body composition entry not found")
    # Verify ownership
    if entry.athlete_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return entry


@router.put("/body-composition/{id}", response_model=BodyCompositionResponse)
def update_body_composition(
    id: UUID,
    body_comp: BodyCompositionCreate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a body composition entry.
    
    BMI is recalculated automatically if weight or athlete height changes.
    """
    db_entry = db.query(BodyComposition).filter(BodyComposition.id == id).first()
    if not db_entry:
        raise HTTPException(status_code=404, detail="Body composition entry not found")
    
    # Verify ownership
    if db_entry.athlete_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Use authenticated user for BMI recalculation
    athlete = current_user
    
    # Update fields
    db_entry.date = body_comp.date
    db_entry.weight_kg = Decimal(str(body_comp.weight_kg)) if body_comp.weight_kg else None
    db_entry.body_fat_pct = Decimal(str(body_comp.body_fat_pct)) if body_comp.body_fat_pct else None
    db_entry.muscle_mass_kg = Decimal(str(body_comp.muscle_mass_kg)) if body_comp.muscle_mass_kg else None
    db_entry.measurements_json = body_comp.measurements_json
    db_entry.notes = body_comp.notes
    
    # Recalculate BMI if weight or height available
    bmi = None
    if db_entry.weight_kg is not None and athlete.height_cm is not None:
        bmi = calculate_bmi(
            weight_kg=db_entry.weight_kg,
            height_cm=Decimal(str(athlete.height_cm))
        )
    db_entry.bmi = bmi
    
    db.commit()
    db.refresh(db_entry)
    
    # Invalidate cache
    invalidate_athlete_cache(str(current_user.id))
    invalidate_correlation_cache(str(current_user.id))
    
    return db_entry


@router.delete("/body-composition/{id}", status_code=204)
def delete_body_composition(
    id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a body composition entry."""
    db_entry = db.query(BodyComposition).filter(BodyComposition.id == id).first()
    if not db_entry:
        raise HTTPException(status_code=404, detail="Body composition entry not found")
    
    # Verify ownership
    if db_entry.athlete_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    db.delete(db_entry)
    db.commit()
    
    # Invalidate cache
    invalidate_athlete_cache(str(current_user.id))
    invalidate_correlation_cache(str(current_user.id))
    return None

