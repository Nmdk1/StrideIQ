"""
Plan Export Service

Exports training plans to various formats for backup and external use.

Supported formats:
- CSV (Google Sheets compatible)
- JSON (for programmatic access)

This gives athletes confidence that their plan data is portable and
they won't lose it if they want to try new features.
"""

import csv
import json
import io
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import date, datetime
from dataclasses import dataclass

from sqlalchemy.orm import Session

import logging

logger = logging.getLogger(__name__)


@dataclass
class ExportResult:
    """Result of a plan export operation."""
    success: bool
    format: str
    filename: str
    content: str  # The actual file content
    content_type: str  # MIME type
    row_count: int
    error: Optional[str] = None


def export_plan_to_csv(
    plan_id: UUID,
    athlete_id: UUID,
    db: Session,
    include_completed: bool = True,
    units: str = "imperial"  # 'imperial' (miles) or 'metric' (km)
) -> ExportResult:
    """
    Export a training plan to CSV format.
    
    Creates a Google Sheets-compatible CSV with columns:
    - Week
    - Date
    - Day
    - Phase
    - Workout Type
    - Title
    - Description
    - Target Distance
    - Target Duration
    - Target Pace
    - Completed
    - Notes
    
    Args:
        plan_id: The training plan to export
        athlete_id: The athlete (for authorization)
        db: Database session
        include_completed: Whether to include completion status
        units: 'imperial' (miles) or 'metric' (km)
        
    Returns:
        ExportResult with CSV content
    """
    from models import TrainingPlan, PlannedWorkout
    
    # Get the plan
    plan = db.query(TrainingPlan).filter(
        TrainingPlan.id == plan_id,
        TrainingPlan.athlete_id == athlete_id
    ).first()
    
    if not plan:
        return ExportResult(
            success=False,
            format="csv",
            filename="",
            content="",
            content_type="text/csv",
            row_count=0,
            error="Plan not found or access denied"
        )
    
    # Get all workouts ordered by date
    workouts = db.query(PlannedWorkout).filter(
        PlannedWorkout.plan_id == plan_id
    ).order_by(
        PlannedWorkout.scheduled_date,
        PlannedWorkout.day_of_week
    ).all()
    
    if not workouts:
        return ExportResult(
            success=False,
            format="csv",
            filename="",
            content="",
            content_type="text/csv",
            row_count=0,
            error="No workouts found in plan"
        )
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header with plan metadata
    writer.writerow([f"# {plan.name}"])
    writer.writerow([f"# Goal Race: {plan.goal_race_name or 'N/A'} - {plan.goal_race_date}"])
    if plan.goal_time_seconds:
        goal_time = _format_time(plan.goal_time_seconds)
        writer.writerow([f"# Goal Time: {goal_time}"])
    writer.writerow([f"# Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}"])
    writer.writerow([])  # Blank row
    
    # Write column headers
    distance_unit = "Distance (mi)" if units == "imperial" else "Distance (km)"
    pace_unit = "Pace (min/mi)" if units == "imperial" else "Pace (min/km)"
    
    headers = [
        "Week",
        "Date",
        "Day",
        "Phase",
        "Type",
        "Title",
        "Description",
        distance_unit,
        "Duration (min)",
        pace_unit,
    ]
    
    if include_completed:
        headers.extend(["Completed", "Skipped"])
    
    headers.append("Notes")
    
    writer.writerow(headers)
    
    # Write workout rows
    day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    
    for workout in workouts:
        # Convert distance
        if workout.target_distance_km:
            if units == "imperial":
                distance = round(workout.target_distance_km * 0.621371, 1)
            else:
                distance = round(workout.target_distance_km, 1)
        else:
            distance = ""
        
        # Convert pace
        if workout.target_pace_per_km_seconds:
            if units == "imperial":
                # Convert pace from sec/km to min:sec/mi
                pace_sec_per_mi = workout.target_pace_per_km_seconds * 1.60934
                pace = _format_pace(pace_sec_per_mi)
            else:
                pace = _format_pace(workout.target_pace_per_km_seconds)
        else:
            pace = ""
        
        row = [
            workout.week_number,
            workout.scheduled_date.strftime("%Y-%m-%d"),
            day_names[workout.day_of_week] if 0 <= workout.day_of_week <= 6 else "",
            workout.phase.capitalize() if workout.phase else "",
            workout.workout_type.capitalize() if workout.workout_type else "",
            workout.title or "",
            _clean_description(workout.description),
            distance,
            workout.target_duration_minutes or "",
            pace,
        ]
        
        if include_completed:
            row.extend([
                "Yes" if workout.completed else "",
                "Yes" if workout.skipped else ""
            ])
        
        # Combine notes
        notes = []
        if workout.coach_notes:
            notes.append(workout.coach_notes)
        if workout.athlete_notes:
            notes.append(f"[Athlete] {workout.athlete_notes}")
        row.append(" | ".join(notes) if notes else "")
        
        writer.writerow(row)
    
    content = output.getvalue()
    output.close()
    
    # Generate filename
    safe_name = _sanitize_filename(plan.name)
    filename = f"{safe_name}_{date.today().strftime('%Y%m%d')}.csv"
    
    logger.info(f"Exported plan {plan_id} to CSV: {len(workouts)} workouts")
    
    return ExportResult(
        success=True,
        format="csv",
        filename=filename,
        content=content,
        content_type="text/csv; charset=utf-8",
        row_count=len(workouts)
    )


def export_plan_to_json(
    plan_id: UUID,
    athlete_id: UUID,
    db: Session,
    include_segments: bool = True
) -> ExportResult:
    """
    Export a training plan to JSON format.
    
    Creates a structured JSON export with full plan and workout details.
    Useful for programmatic access or backup.
    
    Args:
        plan_id: The training plan to export
        athlete_id: The athlete (for authorization)
        db: Database session
        include_segments: Whether to include detailed workout segments
        
    Returns:
        ExportResult with JSON content
    """
    from models import TrainingPlan, PlannedWorkout
    
    # Get the plan
    plan = db.query(TrainingPlan).filter(
        TrainingPlan.id == plan_id,
        TrainingPlan.athlete_id == athlete_id
    ).first()
    
    if not plan:
        return ExportResult(
            success=False,
            format="json",
            filename="",
            content="",
            content_type="application/json",
            row_count=0,
            error="Plan not found or access denied"
        )
    
    # Get all workouts
    workouts = db.query(PlannedWorkout).filter(
        PlannedWorkout.plan_id == plan_id
    ).order_by(
        PlannedWorkout.scheduled_date
    ).all()
    
    # Build export structure
    export_data = {
        "export_version": "1.0",
        "exported_at": datetime.now().isoformat(),
        "plan": {
            "id": str(plan.id),
            "name": plan.name,
            "status": plan.status,
            "goal_race_name": plan.goal_race_name,
            "goal_race_date": plan.goal_race_date.isoformat() if plan.goal_race_date else None,
            "goal_race_distance_m": plan.goal_race_distance_m,
            "goal_time_seconds": plan.goal_time_seconds,
            "plan_start_date": plan.plan_start_date.isoformat() if plan.plan_start_date else None,
            "plan_end_date": plan.plan_end_date.isoformat() if plan.plan_end_date else None,
            "total_weeks": plan.total_weeks,
            "baseline_rpi": plan.baseline_rpi,
            "plan_type": plan.plan_type,
            "generation_method": plan.generation_method,
        },
        "workouts": []
    }
    
    for workout in workouts:
        workout_data = {
            "id": str(workout.id),
            "scheduled_date": workout.scheduled_date.isoformat(),
            "week_number": workout.week_number,
            "day_of_week": workout.day_of_week,
            "workout_type": workout.workout_type,
            "workout_subtype": workout.workout_subtype,
            "title": workout.title,
            "description": workout.description,
            "phase": workout.phase,
            "phase_week": workout.phase_week,
            "target_duration_minutes": workout.target_duration_minutes,
            "target_distance_km": workout.target_distance_km,
            "target_pace_per_km_seconds": workout.target_pace_per_km_seconds,
            "target_hr_min": workout.target_hr_min,
            "target_hr_max": workout.target_hr_max,
            "completed": workout.completed,
            "skipped": workout.skipped,
            "skip_reason": workout.skip_reason,
            "coach_notes": workout.coach_notes,
            "athlete_notes": workout.athlete_notes,
        }
        
        if include_segments and workout.segments:
            workout_data["segments"] = workout.segments
        
        export_data["workouts"].append(workout_data)
    
    content = json.dumps(export_data, indent=2, ensure_ascii=False)
    
    # Generate filename
    safe_name = _sanitize_filename(plan.name)
    filename = f"{safe_name}_{date.today().strftime('%Y%m%d')}.json"
    
    logger.info(f"Exported plan {plan_id} to JSON: {len(workouts)} workouts")
    
    return ExportResult(
        success=True,
        format="json",
        filename=filename,
        content=content,
        content_type="application/json; charset=utf-8",
        row_count=len(workouts)
    )


def export_active_plan_to_csv(
    athlete_id: UUID,
    db: Session,
    units: str = "imperial"
) -> ExportResult:
    """
    Export the athlete's active training plan to CSV.
    
    Convenience function that finds the active plan automatically.
    """
    from models import TrainingPlan
    
    # Find active plan
    plan = db.query(TrainingPlan).filter(
        TrainingPlan.athlete_id == athlete_id,
        TrainingPlan.status == "active"
    ).order_by(
        TrainingPlan.created_at.desc()
    ).first()
    
    if not plan:
        return ExportResult(
            success=False,
            format="csv",
            filename="",
            content="",
            content_type="text/csv",
            row_count=0,
            error="No active plan found"
        )
    
    return export_plan_to_csv(plan.id, athlete_id, db, units=units)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _format_time(seconds: int) -> str:
    """Format seconds as H:MM:SS or MM:SS."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def _format_pace(seconds_per_unit: float) -> str:
    """Format pace as M:SS."""
    minutes = int(seconds_per_unit // 60)
    secs = int(seconds_per_unit % 60)
    return f"{minutes}:{secs:02d}"


def _clean_description(description: Optional[str]) -> str:
    """Clean description for CSV (remove newlines, limit length)."""
    if not description:
        return ""
    
    # Replace newlines with spaces
    cleaned = description.replace("\n", " ").replace("\r", " ")
    
    # Remove multiple spaces
    while "  " in cleaned:
        cleaned = cleaned.replace("  ", " ")
    
    return cleaned.strip()


def _sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename."""
    # Remove/replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    result = name
    for char in invalid_chars:
        result = result.replace(char, "_")
    
    # Replace spaces with underscores
    result = result.replace(" ", "_")
    
    # Remove leading/trailing underscores
    result = result.strip("_")
    
    # Limit length
    if len(result) > 50:
        result = result[:50]
    
    return result or "training_plan"
