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


def _format_time(seconds: float) -> str:
    """Format seconds to HH:MM:SS or MM:SS.t string."""
    if seconds <= 0:
        return "0:00"
    hours = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours}:{mins:02d}:{int(secs):02d}"
    elif secs == int(secs):
        return f"{mins}:{int(secs):02d}"
    else:
        # Show tenths for sub-minute precision
        return f"{mins}:{secs:04.1f}"


def _get_classification(pct: float) -> dict:
    """Get performance classification based on age-grading percentage."""
    if pct >= 100:
        return {"level": "world_record", "label": "World Record", "color": "gold"}
    elif pct >= 90:
        return {"level": "world_class", "label": "World Class", "color": "purple"}
    elif pct >= 80:
        return {"level": "national_class", "label": "National Class", "color": "blue"}
    elif pct >= 70:
        return {"level": "regional_class", "label": "Regional Class", "color": "green"}
    elif pct >= 60:
        return {"level": "local_class", "label": "Local Class", "color": "teal"}
    else:
        return {"level": "recreational", "label": "Recreational", "color": "slate"}


@router.post("/age-grade")
def calculate_age_grade(request: AgeGradeRequest):
    """
    Calculate WMA age-graded performance percentage.
    
    Free tool - no authentication required.
    Returns comprehensive age-grading analysis including:
    - Performance percentage
    - Open-class standard (world record for distance/sex)
    - Age standard (world record for age/sex/distance)
    - Age factor
    - Age-graded time
    - Equivalent performances at other distances
    - Close performances (nearby percentage levels)
    - Classification
    """
    if request.age < 0 or request.age > 120:
        raise HTTPException(status_code=400, detail="Age must be between 0 and 120")
    if request.sex not in ["M", "F"]:
        raise HTTPException(status_code=400, detail="Sex must be 'M' or 'F'")
    if request.distance_meters <= 0:
        raise HTTPException(status_code=400, detail="Distance must be positive")
    if request.time_seconds <= 0:
        raise HTTPException(status_code=400, detail="Time must be positive")
    
    from services.performance_engine import get_wma_age_factor
    from services.wma_age_factors import get_wma_open_standard_seconds, get_wma_world_record_pace
    
    # Calculate pace per mile from time and distance
    distance_miles = request.distance_meters / 1609.34
    pace_per_mile = request.time_seconds / 60 / distance_miles
    
    # Get age factor
    age_factor = get_wma_age_factor(request.age, request.sex, request.distance_meters)
    if age_factor is None or age_factor <= 0:
        age_factor = 1.0
    
    # Get open-class standard (WMA world record time for this distance)
    open_class_standard_seconds = get_wma_open_standard_seconds(request.sex, request.distance_meters)
    
    if open_class_standard_seconds is None:
        # Fallback to pace-based calculation
        record_pace_30yo = get_wma_world_record_pace(request.sex, request.distance_meters)
        if record_pace_30yo:
            open_class_standard_seconds = record_pace_30yo * distance_miles * 60
        else:
            # Last resort fallback
            open_class_standard_seconds = request.time_seconds * 0.7
    
    # Calculate age standard (world record for this age)
    # age_standard = open_class_standard * age_factor
    age_standard_seconds = open_class_standard_seconds * age_factor
    
    # Calculate age-graded time (athlete time adjusted to open equivalent)
    # age_graded_time = actual_time / age_factor
    age_graded_time_seconds = request.time_seconds / age_factor
    
    # Calculate performance percentage
    # performance_pct = age_standard / actual_time * 100
    performance_pct = (age_standard_seconds / request.time_seconds) * 100
    
    # Get classification
    classification = _get_classification(performance_pct)
    
    # Calculate equivalent performances at other distances
    # For same age-grading %, time = age_standard / (pct/100)
    equivalent_distances = [
        {"name": "5K", "meters": 5000},
        {"name": "10K", "meters": 10000},
        {"name": "10 Miles", "meters": 16093.4},
        {"name": "Half Marathon", "meters": 21097.5},
        {"name": "Marathon", "meters": 42195},
    ]
    
    equivalent_performances = []
    for dist in equivalent_distances:
        dist_open_standard = get_wma_open_standard_seconds(request.sex, dist["meters"])
        dist_age_factor = get_wma_age_factor(request.age, request.sex, dist["meters"]) or 1.0
        
        if dist_open_standard is None:
            # Fallback to pace-based calculation
            dist_miles = dist["meters"] / 1609.34
            dist_record_pace = get_wma_world_record_pace(request.sex, dist["meters"])
            if dist_record_pace:
                dist_open_standard = dist_record_pace * dist_miles * 60
        
        if dist_open_standard:
            dist_age_standard = dist_open_standard * dist_age_factor
            # Time to achieve same percentage at this distance
            equiv_time = dist_age_standard / (performance_pct / 100)
            equivalent_performances.append({
                "distance": dist["name"],
                "distance_meters": dist["meters"],
                "time_seconds": round(equiv_time),
                "time_formatted": _format_time(equiv_time)
            })
    
    # Calculate close performances (times for nearby percentages)
    close_performances = []
    for target_pct in [84, 83, 82, 81, 80, 79, 78, 77]:
        # Time for target percentage = age_standard / (target_pct/100)
        target_time = age_standard_seconds / (target_pct / 100)
        close_performances.append({
            "percentage": target_pct,
            "time_seconds": round(target_time, 1),
            "time_formatted": _format_time(target_time),
            "is_current": abs(target_pct - performance_pct) < 0.5
        })
    
    # Insert actual performance in the right place
    actual_entry = {
        "percentage": round(performance_pct, 2),
        "time_seconds": request.time_seconds,
        "time_formatted": _format_time(request.time_seconds),
        "is_current": True
    }
    
    # Find insertion point and add actual
    inserted = False
    for i, entry in enumerate(close_performances):
        if performance_pct > entry["percentage"]:
            close_performances.insert(i, actual_entry)
            inserted = True
            break
        elif entry.get("is_current"):
            # Replace the placeholder
            close_performances[i] = actual_entry
            inserted = True
            break
    if not inserted:
        close_performances.append(actual_entry)
    
    # Remove duplicate is_current flags
    seen_current = False
    for entry in close_performances:
        if entry.get("is_current") and entry["percentage"] != round(performance_pct, 2):
            entry["is_current"] = False
    
    return {
        # Core results (backwards compatible)
        "performance_percentage": round(performance_pct, 2),
        "equivalent_time": _format_time(age_graded_time_seconds),
        "equivalent_time_seconds": int(age_graded_time_seconds),
        "age": request.age,
        "sex": request.sex,
        "distance_meters": request.distance_meters,
        "actual_time_seconds": request.time_seconds,
        
        # Enhanced results (new in v2)
        "athlete_time_formatted": _format_time(request.time_seconds),
        "open_class_standard_seconds": round(open_class_standard_seconds, 1),
        "open_class_standard_formatted": _format_time(open_class_standard_seconds),
        "age_standard_seconds": round(age_standard_seconds, 1),
        "age_standard_formatted": _format_time(age_standard_seconds),
        "age_factor": round(age_factor, 4),
        "age_graded_time_seconds": round(age_graded_time_seconds, 1),
        "age_graded_time_formatted": _format_time(age_graded_time_seconds),
        "classification": classification,
        "equivalent_performances": equivalent_performances,
        "close_performances": close_performances[:9],  # Limit to 9 entries
    }

