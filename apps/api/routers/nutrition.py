"""
Nutrition API Endpoints

Handles nutrition tracking (pre/during/post activity + daily) for correlation analysis.
Nutrition patterns are correlated with performance efficiency to identify personal response curves.
"""
import os
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from decimal import Decimal
from datetime import date, datetime

from core.database import get_db
from core.auth import get_current_user
from core.cache import invalidate_athlete_cache, invalidate_correlation_cache
from models import Athlete, NutritionEntry, Activity
from schemas import NutritionEntryCreate, NutritionEntryResponse
from pydantic import BaseModel

from services import nutrition_parser

router = APIRouter(prefix="/v1", tags=["nutrition"])


@router.get("/nutrition/parse/available")
def nutrition_parse_available():
    """
    Capability check for NL nutrition parsing.

    No auth required: UI uses this to decide whether to render the NL input.
    """
    return {"available": bool(os.getenv("OPENAI_API_KEY"))}


class NutritionParseRequest(BaseModel):
    text: str


@router.post("/nutrition/parse", response_model=NutritionEntryCreate, status_code=status.HTTP_200_OK)
def parse_nutrition(
    payload: NutritionParseRequest,
    current_user: Athlete = Depends(get_current_user),
):
    """
    Parse natural-language nutrition text into structured macros.

    Phase 1:
    - Accepts { text: string }
    - Uses OpenAI to estimate macros
    - Returns a NutritionEntryCreate payload prefilled for the current user (daily entry, today)

    Notes:
    - Manual entry remains the fallback if parsing is unavailable.
    """
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="text is required")

    try:
        parsed = nutrition_parser.parse_nutrition_text(text)
    except Exception as e:
        # Keep failure mode user-friendly and non-fatal for manual fallback.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Nutrition parsing unavailable: {str(e)}",
        )

    return NutritionEntryCreate(
        athlete_id=current_user.id,
        date=date.today(),
        entry_type="daily",
        activity_id=None,
        calories=parsed.get("calories"),
        protein_g=parsed.get("protein_g"),
        carbs_g=parsed.get("carbs_g"),
        fat_g=parsed.get("fat_g"),
        fiber_g=parsed.get("fiber_g"),
        timing=None,
        notes=parsed.get("notes") or text,
    )


@router.post("/nutrition", response_model=NutritionEntryResponse, status_code=201)
def create_nutrition_entry(
    nutrition: NutritionEntryCreate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new nutrition entry.
    
    Entry types:
    - 'pre_activity': Nutrition before an activity (requires activity_id)
    - 'during_activity': Nutrition during an activity (requires activity_id)
    - 'post_activity': Nutrition after an activity (requires activity_id)
    - 'daily': Daily nutrition intake (activity_id should be None)
    
    Used for correlation analysis: nutrition patterns vs performance efficiency.
    """
    # Use authenticated user's ID
    athlete = current_user
    
    # Validate activity_id based on entry_type
    if nutrition.entry_type in ['pre_activity', 'during_activity', 'post_activity']:
        if not nutrition.activity_id:
            raise HTTPException(
                status_code=400,
                detail=f"activity_id is required for entry_type '{nutrition.entry_type}'"
            )
        # Verify activity exists and belongs to authenticated user
        activity = db.query(Activity).filter(
            Activity.id == nutrition.activity_id,
            Activity.athlete_id == current_user.id
        ).first()
        if not activity:
            raise HTTPException(
                status_code=404,
                detail="Activity not found or does not belong to athlete"
            )
    elif nutrition.entry_type == 'daily':
        if nutrition.activity_id is not None:
            raise HTTPException(
                status_code=400,
                detail="activity_id must be None for 'daily' entry_type"
            )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entry_type: '{nutrition.entry_type}'. Must be 'pre_activity', 'during_activity', 'post_activity', or 'daily'"
        )
    
    # Create nutrition entry (use authenticated user's ID)
    db_entry = NutritionEntry(
        athlete_id=current_user.id,
        date=nutrition.date,
        entry_type=nutrition.entry_type,
        activity_id=nutrition.activity_id,
        calories=Decimal(str(nutrition.calories)) if nutrition.calories else None,
        protein_g=Decimal(str(nutrition.protein_g)) if nutrition.protein_g else None,
        carbs_g=Decimal(str(nutrition.carbs_g)) if nutrition.carbs_g else None,
        fat_g=Decimal(str(nutrition.fat_g)) if nutrition.fat_g else None,
        fiber_g=Decimal(str(nutrition.fiber_g)) if nutrition.fiber_g else None,
        timing=nutrition.timing,
        notes=nutrition.notes
    )
    
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    
    # Invalidate cache (nutrition affects correlations)
    invalidate_athlete_cache(str(current_user.id))
    invalidate_correlation_cache(str(current_user.id))
    
    return db_entry


@router.get("/nutrition", response_model=List[NutritionEntryResponse])
def get_nutrition_entries(
    current_user: Athlete = Depends(get_current_user),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    entry_type: Optional[str] = Query(None, description="Filter by entry type"),
    activity_id: Optional[UUID] = Query(None, description="Filter by activity ID"),
    db: Session = Depends(get_db)
):
    """
    Get nutrition entries for the authenticated user.
    
    Can filter by date range, entry type, and activity ID.
    """
    query = db.query(NutritionEntry).filter(NutritionEntry.athlete_id == current_user.id)
    
    if start_date:
        query = query.filter(NutritionEntry.date >= start_date)
    if end_date:
        query = query.filter(NutritionEntry.date <= end_date)
    if entry_type:
        query = query.filter(NutritionEntry.entry_type == entry_type)
    if activity_id:
        query = query.filter(NutritionEntry.activity_id == activity_id)
    
    entries = query.order_by(NutritionEntry.date.desc(), NutritionEntry.created_at.desc()).all()
    return entries


@router.get("/nutrition/{id}", response_model=NutritionEntryResponse)
def get_nutrition_entry_by_id(
    id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific nutrition entry by ID."""
    entry = db.query(NutritionEntry).filter(NutritionEntry.id == id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Nutrition entry not found")
    # Verify ownership
    if entry.athlete_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return entry


@router.put("/nutrition/{id}", response_model=NutritionEntryResponse)
def update_nutrition_entry(
    id: UUID,
    nutrition: NutritionEntryCreate,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a nutrition entry.
    
    Validates entry_type and activity_id requirements.
    """
    db_entry = db.query(NutritionEntry).filter(NutritionEntry.id == id).first()
    if not db_entry:
        raise HTTPException(status_code=404, detail="Nutrition entry not found")
    
    # Verify ownership
    if db_entry.athlete_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Validate activity_id based on entry_type
    if nutrition.entry_type in ['pre_activity', 'during_activity', 'post_activity']:
        if not nutrition.activity_id:
            raise HTTPException(
                status_code=400,
                detail=f"activity_id is required for entry_type '{nutrition.entry_type}'"
            )
        # Verify activity exists and belongs to authenticated user
        activity = db.query(Activity).filter(
            Activity.id == nutrition.activity_id,
            Activity.athlete_id == current_user.id
        ).first()
        if not activity:
            raise HTTPException(
                status_code=404,
                detail="Activity not found or does not belong to athlete"
            )
    elif nutrition.entry_type == 'daily':
        if nutrition.activity_id is not None:
            raise HTTPException(
                status_code=400,
                detail="activity_id must be None for 'daily' entry_type"
            )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entry_type: '{nutrition.entry_type}'"
        )
    
    # Update fields (keep athlete_id unchanged)
    db_entry.date = nutrition.date
    db_entry.entry_type = nutrition.entry_type
    db_entry.activity_id = nutrition.activity_id
    db_entry.calories = Decimal(str(nutrition.calories)) if nutrition.calories else None
    db_entry.protein_g = Decimal(str(nutrition.protein_g)) if nutrition.protein_g else None
    db_entry.carbs_g = Decimal(str(nutrition.carbs_g)) if nutrition.carbs_g else None
    db_entry.fat_g = Decimal(str(nutrition.fat_g)) if nutrition.fat_g else None
    db_entry.fiber_g = Decimal(str(nutrition.fiber_g)) if nutrition.fiber_g else None
    db_entry.timing = nutrition.timing
    db_entry.notes = nutrition.notes
    
    db.commit()
    db.refresh(db_entry)
    
    # Invalidate cache
    invalidate_athlete_cache(str(current_user.id))
    invalidate_correlation_cache(str(current_user.id))
    
    return db_entry


@router.delete("/nutrition/{id}", status_code=204)
def delete_nutrition_entry(
    id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a nutrition entry."""
    db_entry = db.query(NutritionEntry).filter(NutritionEntry.id == id).first()
    if not db_entry:
        raise HTTPException(status_code=404, detail="Nutrition entry not found")
    
    # Verify ownership
    if db_entry.athlete_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    db.delete(db_entry)
    db.commit()
    
    # Invalidate cache
    invalidate_athlete_cache(str(current_user.id))
    invalidate_correlation_cache(str(current_user.id))
    
    return None

