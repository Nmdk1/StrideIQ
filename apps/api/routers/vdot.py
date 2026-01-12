"""
VDOT Calculator API Endpoints

Free tool for landing page - comprehensive VDOT calculator with:
- VDOT calculation from race time or pace
- Training paces (Easy, Marathon, Threshold, Interval, Repetition, Fast Reps)
- Equivalent race performances for all standard distances

Reference: https://vdoto2.com/calculator/
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from services.vdot_calculator import calculate_vdot_comprehensive

router = APIRouter(prefix="/v1/vdot", tags=["VDOT Calculator"])


# Request models for POST endpoints
class VDOTCalculateRequest(BaseModel):
    """Request for VDOT calculation from race result."""
    race_time_seconds: int
    distance_meters: float


class VDOTTrainingPacesRequest(BaseModel):
    """Request for training paces from VDOT."""
    vdot: float


# POST endpoints (for test compatibility and proper API design)
@router.post("/calculate")
def calculate_vdot_post(request: VDOTCalculateRequest):
    """
    Calculate VDOT from race time and distance.
    
    Free tool - no authentication required.
    """
    if request.distance_meters <= 0:
        raise HTTPException(status_code=400, detail="Distance must be positive")
    if request.race_time_seconds <= 0:
        raise HTTPException(status_code=400, detail="Time must be positive")
    
    result = calculate_vdot_comprehensive(
        distance_meters=request.distance_meters,
        time_seconds=request.race_time_seconds
    )
    
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.post("/training-paces")
def get_training_paces_post(request: VDOTTrainingPacesRequest):
    """
    Get training paces for a given VDOT.
    
    Free tool - no authentication required.
    """
    if request.vdot <= 0:
        raise HTTPException(status_code=400, detail="VDOT must be positive")
    
    from services.vdot_calculator import calculate_training_paces
    
    paces = calculate_training_paces(request.vdot)
    
    return paces


@router.get("/calculate-legacy")
def calculate_vdot(
    distance_m: Optional[float] = Query(None, description="Race distance in meters"),
    time_minutes: Optional[float] = Query(None, description="Race time in minutes (e.g., 20.5 for 20:30)"),
    time_hours: Optional[int] = Query(None, description="Hours component of race time"),
    time_min: Optional[int] = Query(None, description="Minutes component of race time"),
    time_sec: Optional[int] = Query(None, description="Seconds component of race time"),
    pace_minutes_per_mile: Optional[float] = Query(None, description="Pace in minutes per mile (for reverse calculation, e.g., 7.5 for 7:30/mi)")
):
    """
    Comprehensive VDOT calculator.
    
    Free tool - no authentication required.
    
    Can calculate from:
    1. Race time and distance (distance_m + time_minutes OR time_hours/time_min/time_sec)
    2. Pace only (pace_minutes_per_mile) - reverse calculation
    
    Returns:
        - VDOT score
        - Training paces (Easy, Marathon, Threshold, Interval, Repetition, Fast Reps) in both mi and km
        - Equivalent race performances for all standard distances
    
    Examples:
    - 5K in 20:00: distance_m=5000, time_minutes=20.0
    - 10K in 42:30: distance_m=10000, time_minutes=42.5
    - Half Marathon in 1:30:00: distance_m=21097.5, time_hours=1, time_min=30, time_sec=0
    - From pace 7:30/mi: pace_minutes_per_mile=7.5
    """
    # Parse time input
    time_seconds = None
    
    if time_minutes is not None:
        time_seconds = int(time_minutes * 60)
    elif time_hours is not None or time_min is not None:
        hours = time_hours or 0
        minutes = time_min or 0
        seconds = time_sec or 0
        time_seconds = hours * 3600 + minutes * 60 + seconds
    
    # Validate input
    if distance_m and time_seconds:
        # Calculate from race time
        if distance_m <= 0:
            raise HTTPException(status_code=400, detail="Distance must be positive")
        if time_seconds <= 0:
            raise HTTPException(status_code=400, detail="Time must be positive")
        
        result = calculate_vdot_comprehensive(
            distance_meters=distance_m,
            time_seconds=time_seconds
        )
    elif pace_minutes_per_mile:
        # Reverse calculation from pace
        if pace_minutes_per_mile <= 0:
            raise HTTPException(status_code=400, detail="Pace must be positive")
        
        result = calculate_vdot_comprehensive(
            pace_minutes_per_mile=pace_minutes_per_mile
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="Must provide either (distance_m + time) OR pace_minutes_per_mile"
        )
    
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.get("/equivalent-races")
def get_equivalent_races(
    vdot: float = Query(..., description="VDOT score")
):
    """
    Get equivalent race performances for a given VDOT score.
    
    Returns equivalent times for all standard distances.
    """
    if vdot <= 0:
        raise HTTPException(status_code=400, detail="VDOT must be positive")
    
    from services.vdot_calculator import calculate_all_equivalent_races
    
    equivalent_races = calculate_all_equivalent_races(vdot)
    
    return {
        "vdot": vdot,
        "equivalent_races": equivalent_races
    }

