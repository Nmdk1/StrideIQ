"""
Work Pattern API Endpoints

Handles work pattern tracking for correlation analysis.
Work patterns (type, hours, stress) are correlated with performance and recovery.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from decimal import Decimal

from core.database import get_db
from models import Athlete, WorkPattern
from schemas import WorkPatternCreate, WorkPatternResponse

router = APIRouter(prefix="/v1", tags=["work_pattern"])


@router.post("/work-patterns", response_model=WorkPatternResponse, status_code=201)
def create_work_pattern(
    work_pattern: WorkPatternCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new work pattern entry.
    
    Tracks work type, hours worked, and stress level for correlation analysis.
    Used to identify correlations between work patterns and performance/recovery.
    """
    # Verify athlete exists
    athlete = db.query(Athlete).filter(Athlete.id == work_pattern.athlete_id).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    
    # Check for existing entry on this date
    existing = db.query(WorkPattern).filter(
        WorkPattern.athlete_id == work_pattern.athlete_id,
        WorkPattern.date == work_pattern.date
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Work pattern entry already exists for date {work_pattern.date}"
        )
    
    # Validate stress_level if provided
    if work_pattern.stress_level is not None:
        if work_pattern.stress_level < 1 or work_pattern.stress_level > 5:
            raise HTTPException(
                status_code=400,
                detail="stress_level must be between 1 and 5"
            )
    
    # Create work pattern entry
    db_entry = WorkPattern(
        athlete_id=work_pattern.athlete_id,
        date=work_pattern.date,
        work_type=work_pattern.work_type,
        hours_worked=Decimal(str(work_pattern.hours_worked)) if work_pattern.hours_worked else None,
        stress_level=work_pattern.stress_level,
        notes=work_pattern.notes
    )
    
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    
    return db_entry


@router.get("/work-patterns", response_model=List[WorkPatternResponse])
def get_work_patterns(
    athlete_id: UUID,
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Get work pattern entries for an athlete.
    
    Can filter by date range.
    """
    query = db.query(WorkPattern).filter(WorkPattern.athlete_id == athlete_id)
    
    if start_date:
        query = query.filter(WorkPattern.date >= start_date)
    if end_date:
        query = query.filter(WorkPattern.date <= end_date)
    
    entries = query.order_by(WorkPattern.date.desc()).all()
    return entries


@router.get("/work-patterns/{id}", response_model=WorkPatternResponse)
def get_work_pattern_by_id(
    id: UUID,
    db: Session = Depends(get_db)
):
    """Get a specific work pattern entry by ID."""
    entry = db.query(WorkPattern).filter(WorkPattern.id == id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Work pattern entry not found")
    return entry


@router.put("/work-patterns/{id}", response_model=WorkPatternResponse)
def update_work_pattern(
    id: UUID,
    work_pattern: WorkPatternCreate,
    db: Session = Depends(get_db)
):
    """
    Update a work pattern entry.
    """
    db_entry = db.query(WorkPattern).filter(WorkPattern.id == id).first()
    if not db_entry:
        raise HTTPException(status_code=404, detail="Work pattern entry not found")
    
    # Verify athlete exists
    athlete = db.query(Athlete).filter(Athlete.id == work_pattern.athlete_id).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    
    # Validate stress_level if provided
    if work_pattern.stress_level is not None:
        if work_pattern.stress_level < 1 or work_pattern.stress_level > 5:
            raise HTTPException(
                status_code=400,
                detail="stress_level must be between 1 and 5"
            )
    
    # Update fields
    db_entry.athlete_id = work_pattern.athlete_id
    db_entry.date = work_pattern.date
    db_entry.work_type = work_pattern.work_type
    db_entry.hours_worked = Decimal(str(work_pattern.hours_worked)) if work_pattern.hours_worked else None
    db_entry.stress_level = work_pattern.stress_level
    db_entry.notes = work_pattern.notes
    
    db.commit()
    db.refresh(db_entry)
    
    return db_entry


@router.delete("/work-patterns/{id}", status_code=204)
def delete_work_pattern(
    id: UUID,
    db: Session = Depends(get_db)
):
    """Delete a work pattern entry."""
    db_entry = db.query(WorkPattern).filter(WorkPattern.id == id).first()
    if not db_entry:
        raise HTTPException(status_code=404, detail="Work pattern entry not found")
    
    db.delete(db_entry)
    db.commit()
    return None

