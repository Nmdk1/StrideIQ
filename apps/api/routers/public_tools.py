"""
Public Tools API Endpoints

Free tools for landing page - no authentication required.
These tools prove competence and drive acquisition.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from services.vdot_calculator import calculate_vdot_comprehensive
from services.vdot_enhanced import calculate_vdot_enhanced
from services.performance_engine import calculate_age_graded_performance

router = APIRouter(prefix="/v1/public", tags=["Public Tools"])


class VDOTRequest(BaseModel):
    distance_meters: float
    time_seconds: int


class AgeGradeRequest(BaseModel):
    age: int
    sex: str  # "M" or "F"
    distance_meters: float
    time_seconds: int


@router.post("/vdot/calculate")
def calculate_vdot_post(request: VDOTRequest):
    """
    Calculate VDOT from race time and distance.
    
    Free tool - no authentication required.
    Returns comprehensive data matching vdoto2.com functionality:
    - Race Paces tab: Paces for different distances
    - Training tab: Training paces with ranges and interval distances
    - Equivalent tab: Equivalent race times for all distances
    """
    if request.distance_meters <= 0:
        raise HTTPException(status_code=400, detail="Distance must be positive")
    if request.time_seconds <= 0:
        raise HTTPException(status_code=400, detail="Time must be positive")
    
    # Use enhanced calculator for full functionality
    try:
        result = calculate_vdot_enhanced(
            distance_meters=request.distance_meters,
            time_seconds=request.time_seconds
        )
        
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    except Exception as e:
        # Fallback to basic calculator if enhanced fails
        result = calculate_vdot_comprehensive(
            distance_meters=request.distance_meters,
            time_seconds=request.time_seconds
        )
        
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result


@router.post("/age-grade/calculate")
def calculate_age_grade(request: AgeGradeRequest):
    """
    Calculate WMA age-graded performance percentage.
    
    Free tool - no authentication required.
    Returns age-graded % and equivalent open performance.
    """
    if request.age < 0 or request.age > 120:
        raise HTTPException(status_code=400, detail="Age must be between 0 and 120")
    if request.sex not in ["M", "F"]:
        raise HTTPException(status_code=400, detail="Sex must be 'M' or 'F'")
    if request.distance_meters <= 0:
        raise HTTPException(status_code=400, detail="Distance must be positive")
    if request.time_seconds <= 0:
        raise HTTPException(status_code=400, detail="Time must be positive")
    
    # Calculate pace per mile from time and distance
    distance_miles = request.distance_meters / 1609.34
    pace_per_mile = request.time_seconds / 60 / distance_miles
    
    # Calculate age-graded performance (international/WMA standard)
    performance_pct = calculate_age_graded_performance(
        actual_pace_per_mile=pace_per_mile,
        age=request.age,
        sex=request.sex,
        distance_meters=request.distance_meters,
        use_national=False
    )
    
    if performance_pct is None:
        raise HTTPException(status_code=400, detail="Could not calculate age-graded performance")
    
    # Calculate equivalent open performance
    # Age-grading formula: equivalent_open_time = actual_time / age_factor
    # This gives the time a 30yo would need to run to achieve the same age-graded percentage
    from services.performance_engine import get_wma_age_factor
    age_factor = get_wma_age_factor(request.age, request.sex, request.distance_meters)
    
    if age_factor and age_factor > 0:
        # Equivalent open time = actual_time / age_factor
        # This is the time a 30yo would need to run to get the same percentage
        equivalent_time_seconds = request.time_seconds / age_factor
    else:
        # Fallback: use performance percentage
        # Equivalent time = (record_pace_30yo / performance_pct) * 100 * distance_miles * 60
        from services.wma_age_factors import get_wma_world_record_pace
        record_pace_30yo = get_wma_world_record_pace(request.sex, request.distance_meters)
        if record_pace_30yo:
            equivalent_pace_per_mile = (record_pace_30yo / performance_pct) * 100
            equivalent_time_seconds = (equivalent_pace_per_mile * distance_miles) * 60
        else:
            # Last resort fallback
            equivalent_time_seconds = request.time_seconds / (performance_pct / 100)
    
    # Format equivalent time
    hours = int(equivalent_time_seconds // 3600)
    minutes = int((equivalent_time_seconds % 3600) // 60)
    seconds = int(equivalent_time_seconds % 60)
    
    if hours > 0:
        equivalent_time = f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        equivalent_time = f"{minutes}:{seconds:02d}"
    
    return {
        "performance_percentage": round(performance_pct, 2),
        "equivalent_time": equivalent_time,
        "equivalent_time_seconds": int(equivalent_time_seconds),
        "age": request.age,
        "sex": request.sex,
        "distance_meters": request.distance_meters,
        "actual_time_seconds": request.time_seconds
    }

