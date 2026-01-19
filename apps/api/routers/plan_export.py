"""
Plan Export API Router

Provides endpoints for exporting training plans to various formats.

Supported formats:
- CSV (Google Sheets compatible)
- JSON (programmatic access / full backup)

This gives athletes confidence that their plan data is portable.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional

from core.database import get_db
from core.auth import get_current_user
from models import Athlete
from services.plan_export import (
    export_plan_to_csv,
    export_plan_to_json,
    export_active_plan_to_csv,
)

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/plans", tags=["plan-export"])


@router.get("/{plan_id}/export/csv")
def export_plan_csv(
    plan_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
    units: str = Query(default="imperial", description="'imperial' (miles) or 'metric' (km)"),
    include_completed: bool = Query(default=True, description="Include completion status columns")
):
    """
    Export a training plan to CSV format (Google Sheets compatible).
    
    The CSV includes:
    - Plan metadata as header comments
    - Week, Date, Day, Phase, Type, Title, Description
    - Target distance, duration, pace
    - Completion status (optional)
    - Notes
    
    Returns:
        CSV file download
    """
    if units not in ("imperial", "metric"):
        raise HTTPException(
            status_code=400,
            detail="units must be 'imperial' or 'metric'"
        )
    
    result = export_plan_to_csv(
        plan_id=plan_id,
        athlete_id=current_user.id,
        db=db,
        include_completed=include_completed,
        units=units
    )
    
    if not result.success:
        raise HTTPException(
            status_code=404,
            detail=result.error
        )
    
    logger.info(f"User {current_user.id} exported plan {plan_id} to CSV ({result.row_count} workouts)")
    
    return Response(
        content=result.content,
        media_type=result.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{result.filename}"'
        }
    )


@router.get("/{plan_id}/export/json")
def export_plan_json(
    plan_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
    include_segments: bool = Query(default=True, description="Include detailed workout segments")
):
    """
    Export a training plan to JSON format.
    
    The JSON includes full plan structure with all workout details.
    Useful for programmatic access or complete backup.
    
    Returns:
        JSON file download
    """
    result = export_plan_to_json(
        plan_id=plan_id,
        athlete_id=current_user.id,
        db=db,
        include_segments=include_segments
    )
    
    if not result.success:
        raise HTTPException(
            status_code=404,
            detail=result.error
        )
    
    logger.info(f"User {current_user.id} exported plan {plan_id} to JSON ({result.row_count} workouts)")
    
    return Response(
        content=result.content,
        media_type=result.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{result.filename}"'
        }
    )


@router.get("/active/export/csv")
def export_active_plan_csv(
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
    units: str = Query(default="imperial", description="'imperial' (miles) or 'metric' (km)")
):
    """
    Export the active training plan to CSV format.
    
    Convenience endpoint that automatically finds the active plan.
    
    Returns:
        CSV file download
    """
    if units not in ("imperial", "metric"):
        raise HTTPException(
            status_code=400,
            detail="units must be 'imperial' or 'metric'"
        )
    
    result = export_active_plan_to_csv(
        athlete_id=current_user.id,
        db=db,
        units=units
    )
    
    if not result.success:
        raise HTTPException(
            status_code=404,
            detail=result.error
        )
    
    logger.info(f"User {current_user.id} exported active plan to CSV ({result.row_count} workouts)")
    
    return Response(
        content=result.content,
        media_type=result.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{result.filename}"'
        }
    )
