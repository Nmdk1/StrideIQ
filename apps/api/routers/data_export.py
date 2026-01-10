"""
Anonymized Data Export API Endpoints

GDPR-compliant data export for:
1. Athlete consent management
2. Individual anonymized export
3. Admin bulk export (for data partnerships)

TONE: "Your choice. Data stays yours."

Privacy Principles:
- Explicit opt-in required
- Easy opt-out
- Clear explanation
- Right to erasure
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
from core.auth import get_current_user, require_admin
from models import Athlete
from services.data_export import (
    DataExportService,
    ConsentManager,
    ExportFormat,
    ExportScope,
)


router = APIRouter(prefix="/v1/data-export", tags=["Data Export"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class ConsentStatusResponse(BaseModel):
    """Current consent status."""
    athlete_id: str
    consent_given: bool
    consent_date: Optional[str]
    can_revoke: bool
    explanation: str


class ConsentUpdateRequest(BaseModel):
    """Request to update consent."""
    consent: bool = Field(..., description="True to opt-in, False to opt-out")


class ConsentUpdateResponse(BaseModel):
    """Response after consent update."""
    success: bool
    new_status: bool
    message: str


class ErasureRequestResponse(BaseModel):
    """Response to erasure request."""
    athlete_id: str
    request_received: str
    erasure_scope: list
    processing_time: str
    confirmation_method: str


class ExportSummaryResponse(BaseModel):
    """Summary of what would be exported."""
    total_athletes: int
    data_quality_score: float
    export_scope: str
    estimated_patterns: int
    estimated_correlations: int


# =============================================================================
# ATHLETE CONSENT ENDPOINTS
# =============================================================================

@router.get("/consent", response_model=ConsentStatusResponse)
async def get_consent_status(
    db: Session = Depends(get_db),
    current_user: Athlete = Depends(get_current_user),
):
    """
    Get your current consent status for anonymized data sharing.
    
    We only use your data if you explicitly opt in.
    You can opt out at any time.
    """
    manager = ConsentManager(db)
    status = manager.get_consent_status(current_user.id)
    
    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])
    
    return ConsentStatusResponse(
        athlete_id=status["athlete_id"],
        consent_given=status["consent_given"],
        consent_date=str(status["consent_date"]) if status.get("consent_date") else None,
        can_revoke=status["can_revoke"],
        explanation=status["explanation"],
    )


@router.post("/consent", response_model=ConsentUpdateResponse)
async def update_consent(
    request: ConsentUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Athlete = Depends(get_current_user),
):
    """
    Update your consent for anonymized data sharing.
    
    **Opt-in (consent: true):**
    Your training patterns will be anonymized and aggregated to improve
    our algorithms. We never share your name, email, location, or any
    identifiable information.
    
    **Opt-out (consent: false):**
    We will stop using your data in any aggregate analysis.
    Your personal account and features are not affected.
    
    **Your choice. Data stays yours.**
    """
    manager = ConsentManager(db)
    
    if request.consent:
        success = manager.grant_consent(current_user.id)
        message = "Thank you. Your anonymized patterns will help improve our algorithms."
    else:
        success = manager.revoke_consent(current_user.id)
        message = "Consent revoked. We will no longer use your data in aggregate analysis."
    
    return ConsentUpdateResponse(
        success=success,
        new_status=request.consent if success else False,
        message=message if success else "Failed to update consent.",
    )


@router.post("/erasure-request", response_model=ErasureRequestResponse)
async def request_data_erasure(
    db: Session = Depends(get_db),
    current_user: Athlete = Depends(get_current_user),
):
    """
    Request erasure of your data from anonymized exports (GDPR Article 17).
    
    This removes your patterns from any aggregate data exports.
    Your personal account data is handled separately.
    
    Processing time: Within 30 days per GDPR requirements.
    """
    manager = ConsentManager(db)
    result = manager.request_data_erasure(current_user.id)
    
    return ErasureRequestResponse(
        athlete_id=result["athlete_id"],
        request_received=result["request_received"],
        erasure_scope=result["erasure_scope"],
        processing_time=result["processing_time"],
        confirmation_method=result["confirmation_method"],
    )


# =============================================================================
# ATHLETE SELF-EXPORT ENDPOINTS
# =============================================================================

@router.get("/my-anonymized-profile")
async def get_my_anonymized_profile(
    db: Session = Depends(get_db),
    current_user: Athlete = Depends(get_current_user),
):
    """
    See what your anonymized profile looks like.
    
    This shows exactly what would be shared if you opt in:
    - Age group (not exact age)
    - Training volume category (not exact km)
    - Experience level
    - Training consistency category
    
    No names, emails, locations, or GPS data. Ever.
    """
    service = DataExportService(db)
    
    # Force show for transparency (ignore consent for self-view)
    profile = service._anonymize_athlete(current_user)
    
    if not profile:
        raise HTTPException(status_code=404, detail="Could not generate profile")
    
    return {
        "message": "This is what your anonymized profile looks like:",
        "profile": profile.to_dict(),
        "what_is_NOT_included": [
            "Your name",
            "Your email",
            "Your Strava ID",
            "Your location or GPS tracks",
            "Exact age, weight, or other measurements",
            "Activity names or descriptions",
            "Anything that could identify you",
        ],
    }


# =============================================================================
# ADMIN EXPORT ENDPOINTS
# =============================================================================

@router.get("/admin/summary", response_model=ExportSummaryResponse)
async def get_export_summary(
    db: Session = Depends(get_db),
    admin_user: Athlete = Depends(require_admin),
):
    """
    [ADMIN] Get summary of available data for export.
    
    Shows how many athletes have consented and data quality metrics.
    """
    service = DataExportService(db)
    
    # Get preview without full export
    export = service.admin_bulk_export(scope=ExportScope.CORRELATIONS)
    
    return ExportSummaryResponse(
        total_athletes=export.total_athletes,
        data_quality_score=export.data_quality_score,
        export_scope=export.export_scope.value,
        estimated_patterns=len(export.patterns),
        estimated_correlations=len(export.correlations),
    )


@router.get("/admin/export")
async def admin_bulk_export(
    scope: ExportScope = Query(ExportScope.FULL, description="What to export"),
    format: ExportFormat = Query(ExportFormat.JSON, description="Export format"),
    db: Session = Depends(get_db),
    admin_user: Athlete = Depends(require_admin),
):
    """
    [ADMIN] Export anonymized aggregate data.
    
    For data partnerships and acquisition due diligence.
    Only includes athletes who have consented.
    
    **Scopes:**
    - correlations: Discovered correlation patterns only
    - patterns: Pattern recognition results
    - training: Training metrics (anonymized)
    - full: All of the above
    
    **Formats:**
    - json: Full structured export
    - csv: Correlation data as CSV
    """
    service = DataExportService(db)
    export = service.admin_bulk_export(scope=scope, format=format)
    
    if format == ExportFormat.CSV:
        return Response(
            content=export.to_csv(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=strideiq_export_{export.export_id}.csv"
            },
        )
    else:
        return Response(
            content=export.to_json(),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=strideiq_export_{export.export_id}.json"
            },
        )


@router.get("/admin/ml-training-data")
async def get_ml_training_data(
    min_samples: int = Query(1000, ge=100, le=100000),
    db: Session = Depends(get_db),
    admin_user: Athlete = Depends(require_admin),
):
    """
    [ADMIN] Export data formatted for ML model training.
    
    Returns anonymized feature vectors suitable for training
    predictive models without exposing any PII.
    """
    service = DataExportService(db)
    return service.export_for_ml_training(min_samples=min_samples)
