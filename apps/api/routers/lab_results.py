"""
Lab Results Router

Endpoints for managing athlete blood work and biomarker data.
Supports manual entry and future AI-powered parsing of lab PDFs.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

from core.database import get_db
from core.auth import get_current_athlete
from models import Athlete

router = APIRouter(prefix="/v1/lab-results", tags=["Lab Results"])


# ============ Pydantic Schemas ============

class BiomarkerCreate(BaseModel):
    """Single biomarker value"""
    marker_name: str = Field(..., description="e.g., 'ferritin', 'vitamin_d', 'hemoglobin'")
    marker_category: str = Field(..., description="e.g., 'iron', 'vitamin', 'blood', 'hormone'")
    value: float
    unit: str = Field(..., description="e.g., 'ng/mL', 'g/dL'")
    reference_low: Optional[float] = None
    reference_high: Optional[float] = None
    flag: Optional[str] = None  # 'low', 'high', 'normal'
    notes: Optional[str] = None


class LabResultCreate(BaseModel):
    """Create a new lab result with biomarkers"""
    test_date: date
    lab_name: Optional[str] = None
    provider: Optional[str] = None
    raw_text: Optional[str] = None  # For AI parsing later
    biomarkers: List[BiomarkerCreate]


class BiomarkerResponse(BaseModel):
    """Biomarker in response"""
    id: UUID
    marker_name: str
    marker_category: str
    value: float
    unit: str
    reference_low: Optional[float]
    reference_high: Optional[float]
    flag: Optional[str]
    notes: Optional[str]
    
    model_config = ConfigDict(from_attributes=True)


class LabResultResponse(BaseModel):
    """Lab result response"""
    id: UUID
    test_date: date
    lab_name: Optional[str]
    provider: Optional[str]
    biomarkers: List[BiomarkerResponse]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class BiomarkerTrendPoint(BaseModel):
    """Single point in a biomarker trend"""
    test_date: date
    value: float
    flag: Optional[str]


class BiomarkerTrend(BaseModel):
    """Trend data for a single biomarker over time"""
    marker_name: str
    marker_category: str
    unit: str
    data_points: List[BiomarkerTrendPoint]
    current_value: float
    change_percent: Optional[float]  # vs previous test
    trend_direction: Optional[str]  # 'up', 'down', 'stable'


# ============ Common Biomarker Definitions ============

COMMON_BIOMARKERS = {
    # Iron panel
    "ferritin": {"category": "iron", "unit": "ng/mL", "athlete_optimal_low": 50, "athlete_optimal_high": 150},
    "iron": {"category": "iron", "unit": "μg/dL", "athlete_optimal_low": 60, "athlete_optimal_high": 170},
    "tibc": {"category": "iron", "unit": "μg/dL", "athlete_optimal_low": 250, "athlete_optimal_high": 370},
    "transferrin_saturation": {"category": "iron", "unit": "%", "athlete_optimal_low": 20, "athlete_optimal_high": 50},
    
    # Blood counts
    "hemoglobin": {"category": "blood", "unit": "g/dL", "athlete_optimal_low": 14, "athlete_optimal_high": 18},  # varies by sex
    "hematocrit": {"category": "blood", "unit": "%", "athlete_optimal_low": 42, "athlete_optimal_high": 52},
    "rbc": {"category": "blood", "unit": "M/μL", "athlete_optimal_low": 4.5, "athlete_optimal_high": 5.5},
    "mcv": {"category": "blood", "unit": "fL", "athlete_optimal_low": 80, "athlete_optimal_high": 100},
    
    # Vitamins
    "vitamin_d": {"category": "vitamin", "unit": "ng/mL", "athlete_optimal_low": 40, "athlete_optimal_high": 80},
    "vitamin_b12": {"category": "vitamin", "unit": "pg/mL", "athlete_optimal_low": 400, "athlete_optimal_high": 1000},
    "folate": {"category": "vitamin", "unit": "ng/mL", "athlete_optimal_low": 10, "athlete_optimal_high": 25},
    
    # Hormones
    "testosterone": {"category": "hormone", "unit": "ng/dL", "athlete_optimal_low": 400, "athlete_optimal_high": 900},  # male
    "cortisol_am": {"category": "hormone", "unit": "μg/dL", "athlete_optimal_low": 10, "athlete_optimal_high": 20},
    "dhea_s": {"category": "hormone", "unit": "μg/dL", "athlete_optimal_low": 100, "athlete_optimal_high": 400},
    
    # Thyroid
    "tsh": {"category": "thyroid", "unit": "mIU/L", "athlete_optimal_low": 0.5, "athlete_optimal_high": 2.5},
    "free_t4": {"category": "thyroid", "unit": "ng/dL", "athlete_optimal_low": 0.9, "athlete_optimal_high": 1.7},
    "free_t3": {"category": "thyroid", "unit": "pg/mL", "athlete_optimal_low": 2.5, "athlete_optimal_high": 4.2},
    
    # Inflammation
    "crp": {"category": "inflammation", "unit": "mg/L", "athlete_optimal_low": 0, "athlete_optimal_high": 1},
    "esr": {"category": "inflammation", "unit": "mm/hr", "athlete_optimal_low": 0, "athlete_optimal_high": 10},
    
    # Metabolic
    "glucose_fasting": {"category": "metabolic", "unit": "mg/dL", "athlete_optimal_low": 70, "athlete_optimal_high": 100},
    "hba1c": {"category": "metabolic", "unit": "%", "athlete_optimal_low": 4.5, "athlete_optimal_high": 5.6},
    "creatinine": {"category": "metabolic", "unit": "mg/dL", "athlete_optimal_low": 0.7, "athlete_optimal_high": 1.3},
}


# ============ Endpoints ============

@router.get("/biomarkers", response_model=dict)
async def get_common_biomarkers():
    """
    Get list of common biomarkers with athlete-optimal ranges.
    Use this to populate form dropdowns and validate entries.
    """
    return {
        "biomarkers": COMMON_BIOMARKERS,
        "categories": list(set(b["category"] for b in COMMON_BIOMARKERS.values())),
    }


@router.post("", response_model=LabResultResponse, status_code=status.HTTP_201_CREATED)
async def create_lab_result(
    data: LabResultCreate,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Create a new lab result with biomarkers.
    """
    from models import LabResult, LabBiomarker
    
    # Create lab result
    lab_result = LabResult(
        athlete_id=athlete.id,
        test_date=data.test_date,
        lab_name=data.lab_name,
        provider=data.provider,
        raw_text=data.raw_text,
    )
    db.add(lab_result)
    db.flush()  # Get the ID
    
    # Add biomarkers
    for bio in data.biomarkers:
        # Auto-flag if outside athlete optimal range
        flag = bio.flag
        if not flag and bio.marker_name.lower() in COMMON_BIOMARKERS:
            optimal = COMMON_BIOMARKERS[bio.marker_name.lower()]
            if bio.value < optimal.get("athlete_optimal_low", 0):
                flag = "low"
            elif bio.value > optimal.get("athlete_optimal_high", float('inf')):
                flag = "high"
            else:
                flag = "normal"
        
        biomarker = LabBiomarker(
            lab_result_id=lab_result.id,
            marker_name=bio.marker_name.lower(),
            marker_category=bio.marker_category.lower(),
            value=bio.value,
            unit=bio.unit,
            reference_low=bio.reference_low,
            reference_high=bio.reference_high,
            flag=flag,
            notes=bio.notes,
        )
        db.add(biomarker)
    
    db.commit()
    db.refresh(lab_result)
    
    return lab_result


@router.get("", response_model=List[LabResultResponse])
async def list_lab_results(
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
    limit: int = 50,
):
    """
    Get all lab results for the current athlete.
    """
    from models import LabResult
    
    results = (
        db.query(LabResult)
        .filter(LabResult.athlete_id == athlete.id)
        .order_by(LabResult.test_date.desc())
        .limit(limit)
        .all()
    )
    
    return results


@router.get("/trends/{marker_name}", response_model=BiomarkerTrend)
async def get_biomarker_trend(
    marker_name: str,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Get trend data for a specific biomarker over time.
    """
    from models import LabBiomarker, LabResult
    
    # Get all values for this marker, ordered by date
    results = (
        db.query(LabBiomarker, LabResult.test_date)
        .join(LabResult, LabBiomarker.lab_result_id == LabResult.id)
        .filter(
            LabResult.athlete_id == athlete.id,
            LabBiomarker.marker_name == marker_name.lower()
        )
        .order_by(LabResult.test_date.asc())
        .all()
    )
    
    if not results:
        raise HTTPException(status_code=404, detail=f"No data for biomarker: {marker_name}")
    
    data_points = [
        BiomarkerTrendPoint(
            test_date=test_date,
            value=bio.value,
            flag=bio.flag
        )
        for bio, test_date in results
    ]
    
    # Calculate trend
    current = results[-1][0]
    change_percent = None
    trend_direction = None
    
    if len(results) >= 2:
        previous = results[-2][0]
        if previous.value != 0:
            change_percent = ((current.value - previous.value) / previous.value) * 100
            if change_percent > 5:
                trend_direction = "up"
            elif change_percent < -5:
                trend_direction = "down"
            else:
                trend_direction = "stable"
    
    return BiomarkerTrend(
        marker_name=current.marker_name,
        marker_category=current.marker_category,
        unit=current.unit,
        data_points=data_points,
        current_value=current.value,
        change_percent=round(change_percent, 1) if change_percent else None,
        trend_direction=trend_direction,
    )


@router.delete("/{result_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lab_result(
    result_id: UUID,
    athlete: Athlete = Depends(get_current_athlete),
    db: Session = Depends(get_db),
):
    """
    Delete a lab result and all its biomarkers.
    """
    from models import LabResult
    
    result = (
        db.query(LabResult)
        .filter(LabResult.id == result_id, LabResult.athlete_id == athlete.id)
        .first()
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Lab result not found")
    
    db.delete(result)
    db.commit()


