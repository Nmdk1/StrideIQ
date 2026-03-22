"""
Plan Export API Router

Provides endpoints for exporting training plans to various formats.

Supported formats:
- CSV (Google Sheets compatible)
- JSON (programmatic access / full backup)

This gives athletes confidence that their plan data is portable.
"""

import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional

from core.database import get_db
from core.auth import get_current_user
from models import Athlete, TrainingPlan, PlannedWorkout
from services.plan_export import (
    export_plan_to_csv,
    export_plan_to_json,
    export_active_plan_to_csv,
)

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/plans", tags=["plan-export"])


@router.get("/{plan_id}/pdf")
def export_plan_pdf(
    plan_id: UUID,
    current_user: Athlete = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Export a training plan as a PDF file.

    Access rules (mirrors pace-access entitlement):
    - 404  plan missing or not owned by this athlete
    - 403  owned but paces not unlocked (free tier)
    - 200  subscriber / active subscription / admin-owner

    Returns a streaming application/pdf response.
    """
    from core.pace_access import can_access_plan_paces
    from services.plan_pdf import generate_plan_pdf, sanitize_pdf_filename

    # 404 for missing / non-owned
    plan = db.query(TrainingPlan).filter(
        TrainingPlan.id == plan_id,
        TrainingPlan.athlete_id == current_user.id,
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # 403 for owned-but-not-entitled
    if not can_access_plan_paces(current_user, plan_id, db):
        raise HTTPException(
            status_code=403,
            detail="PDF export requires an active paid subscription.",
        )

    # Fetch workouts ordered for consistent rendering
    workouts = (
        db.query(PlannedWorkout)
        .filter(PlannedWorkout.plan_id == plan_id)
        .order_by(PlannedWorkout.week_number, PlannedWorkout.day_of_week)
        .all()
    )

    try:
        pdf_bytes = generate_plan_pdf(plan, workouts, current_user)
    except RuntimeError as exc:
        logger.error("PDF generation failed for plan=%s: %s", plan_id, exc)
        raise HTTPException(status_code=503, detail="PDF generation is temporarily unavailable.")
    except Exception as exc:
        logger.exception("Unexpected PDF generation error for plan=%s", plan_id)
        raise HTTPException(status_code=500, detail="Failed to generate PDF.")

    safe_name = sanitize_pdf_filename(plan.name or "training_plan")
    filename = f"{safe_name}_{date.today().strftime('%Y%m%d')}.pdf"

    logger.info(
        "PDF export: user=%s plan=%s bytes=%d",
        current_user.id, plan_id, len(pdf_bytes),
    )

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


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
