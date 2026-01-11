"""
Public Tools API Endpoints

Free running calculators - no authentication required.
These tools demonstrate expertise and drive user acquisition.

Calculators use the Daniels/Gilbert oxygen cost equations (1979) -
the foundational exercise physiology behind most training methodologies.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from services.vdot_calculator import calculate_vdot_comprehensive
from services.vdot_enhanced import calculate_vdot_enhanced
from services.performance_engine import calculate_age_graded_performance

router = APIRouter(prefix="/v1/public", tags=["Public Tools"])


@router.get("/pace-calculator/about")
def get_methodology():
    """
    Get information about RPI and how paces are calculated.
    
    Returns methodology explanation for display in UI.
    """
    return {
        "title": "How We Calculate Your Paces",
        "rpi_explanation": {
            "name": "RPI",
            "full_name": "Running Performance Index",
            "description": (
                "Your RPI is a measure of your current running performance capability, "
                "calculated from your race result using the Daniels/Gilbert oxygen cost "
                "equations. It predicts your optimal training paces and equivalent times "
                "for other race distances."
            )
        },
        "summary": (
            "Your training paces are derived from the Daniels/Gilbert oxygen cost equations — "
            "peer-reviewed exercise physiology published in 1979. This mathematical model "
            "calculates your running performance from race results and determines precise "
            "intensities for each training zone."
        ),
        "details": (
            "This is the foundational science behind most running calculators and training "
            "methodologies, including approaches from coaches like Pfitzinger, Hudson, "
            "Fitzgerald, and Magness. We calculate continuous, personalized paces from your "
            "data — not rounded values from static tables."
        ),
        "note": (
            "Your paces will be consistent with other science-based training systems. "
            "The math is universal; your body's response is what makes it personal."
        ),
        "training_zones": {
            "easy": {
                "name": "Easy",
                "purpose": "Aerobic development, recovery",
                "intensity": "59-74% of RPI",
                "feel": "Conversational pace"
            },
            "marathon": {
                "name": "Marathon",
                "purpose": "Race-specific endurance",
                "intensity": "79-88% of RPI",
                "feel": "Controlled, sustainable"
            },
            "threshold": {
                "name": "Threshold",
                "purpose": "Lactate clearance, stamina",
                "intensity": "85-92% of RPI",
                "feel": "Comfortably hard"
            },
            "interval": {
                "name": "Interval",
                "purpose": "VO2max development",
                "intensity": "95-105% of RPI",
                "feel": "Hard, controlled"
            },
            "repetition": {
                "name": "Repetition",
                "purpose": "Speed, running economy",
                "intensity": "105-115% of RPI",
                "feel": "Fast, relaxed form"
            }
        }
    }


class PaceCalculatorRequest(BaseModel):
    """Request for pace/fitness calculation from race result."""
    distance_meters: float
    time_seconds: int


# Keep old name for backward compatibility
VDOTRequest = PaceCalculatorRequest


class AgeGradeRequest(BaseModel):
    """Request for WMA age-graded performance calculation."""
    age: int
    sex: str  # "M" or "F"
    distance_meters: float
    time_seconds: int


@router.post("/vdot/calculate")
def calculate_paces(request: PaceCalculatorRequest):
    """
    Calculate RPI (Running Performance Index) and training paces from race time.
    
    Uses the Daniels/Gilbert oxygen cost equations (1979) to derive:
    - RPI: measure of current running performance capability
    - Training Paces: Easy, Marathon, Threshold, Interval, Repetition
    - Race Equivalents: predicted times for other distances
    
    This is the foundational science behind most running calculators.
    Results align with methodologies from Pfitzinger, Hudson, Magness, etc.
    
    Free tool - no authentication required.
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

