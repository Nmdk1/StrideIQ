"""
Garmin Connect Integration Router

Handles Garmin Connect OAuth and sync endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Body, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
from pydantic import BaseModel

from core.database import get_db
from core.auth import require_admin
from models import Athlete
from services.token_encryption import encrypt_token
from tasks.garmin_tasks import sync_garmin_activities_task, sync_garmin_recovery_metrics_task
from services.plan_framework.feature_flags import FeatureFlagService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/garmin", tags=["garmin"])

# Phase 7: Credential-based Garmin Connect is deprecated. Keep it owner/admin-only,
# and behind an explicit flag so it can be disabled in production by default.
LEGACY_GARMIN_PASSWORD_FLAG = "integrations.garmin_password_connect_legacy"


def _ensure_legacy_enabled(db: Session, athlete_id: UUID) -> None:
    svc = FeatureFlagService(db)
    if not svc.is_enabled(LEGACY_GARMIN_PASSWORD_FLAG, athlete_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")


class GarminConnectRequest(BaseModel):
    """Request model for Garmin connection."""
    username: str
    password: str
    athlete_id: UUID


@router.post("/connect")
def connect_garmin(
    request: GarminConnectRequest,
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Connect athlete's Garmin account.
    
    Uses python-garminconnect library which requires username/password.
    Credentials are encrypted before storage.
    
    Args:
        request: Garmin credentials and optional athlete_id
        
    Returns:
        Connection status
    """
    _ensure_legacy_enabled(db, current_user.id)
    try:
        from services.garmin_service import GarminService
        
        # Encrypt password
        encrypted_password = encrypt_token(request.password)
        if not encrypted_password:
            raise HTTPException(status_code=500, detail="Failed to encrypt password")
        
        # Test connection
        try:
            garmin_service = GarminService(
                username=request.username,
                password_encrypted=encrypted_password
            )
            if not garmin_service.login():
                raise HTTPException(status_code=401, detail="Garmin login failed. Please check credentials.")
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Garmin authentication failed: {str(e)}")
        
        athlete = db.query(Athlete).filter(Athlete.id == request.athlete_id).first()
        if not athlete:
            raise HTTPException(status_code=404, detail="Athlete not found")
        
        # Store Garmin credentials (encrypted)
        athlete.garmin_username = request.username
        athlete.garmin_password_encrypted = encrypted_password
        athlete.garmin_connected = True
        athlete.garmin_sync_enabled = True
        
        db.commit()
        
        initial_sync_triggered = False
        try:
            sync_garmin_activities_task.delay(str(athlete.id))
            sync_garmin_recovery_metrics_task.delay(str(athlete.id), days_back=30)
            initial_sync_triggered = True
        except Exception as e:
            logger.warning(f"Could not trigger initial sync: {e}")
        
        return {
            "status": "success",
            "message": "Garmin account connected successfully",
            "athlete_id": str(athlete.id),
            "initial_sync_triggered": initial_sync_triggered
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error connecting Garmin: {str(e)}")


@router.post("/disconnect")
def disconnect_garmin(
    athlete_id: UUID = Body(..., embed=True),
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Disconnect athlete's Garmin account.
    
    Removes credentials and disables sync.
    """
    _ensure_legacy_enabled(db, current_user.id)
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    
    athlete.garmin_connected = False
    athlete.garmin_sync_enabled = False
    athlete.garmin_username = None
    athlete.garmin_password_encrypted = None
    
    db.commit()
    
    return {
        "status": "success",
        "message": "Garmin account disconnected"
    }


@router.post("/sync")
def trigger_garmin_sync(
    athlete_id: UUID = Body(..., embed=True),
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Manually trigger Garmin sync for an athlete.
    
    Args:
        athlete_id: Athlete UUID
        
    Returns:
        Task ID for tracking sync status
    """
    _ensure_legacy_enabled(db, current_user.id)
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    
    if not athlete.garmin_connected:
        raise HTTPException(status_code=400, detail="Athlete not connected to Garmin")
    
    # Trigger sync tasks
    activity_task = sync_garmin_activities_task.delay(str(athlete.id))
    recovery_task = sync_garmin_recovery_metrics_task.delay(str(athlete.id), days_back=30)
    
    return {
        "status": "success",
        "message": "Garmin sync triggered",
        "activity_sync_task_id": activity_task.id,
        "recovery_sync_task_id": recovery_task.id
    }


@router.get("/status/{athlete_id}")
def get_garmin_status(
    athlete_id: UUID,
    current_user: Athlete = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get Garmin connection status for an athlete.
    
    Returns:
        Connection status and last sync time
    """
    _ensure_legacy_enabled(db, current_user.id)
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    
    return {
        "connected": athlete.garmin_connected or False,
        "sync_enabled": athlete.garmin_sync_enabled or False,
        "last_sync": athlete.last_garmin_sync.isoformat() if athlete.last_garmin_sync else None,
        "username": athlete.garmin_username if athlete.garmin_connected else None
    }

