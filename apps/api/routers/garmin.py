"""
Garmin Connect Integration Router

Handles Garmin Connect OAuth and sync endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
from pydantic import BaseModel

from core.database import get_db
from models import Athlete
from services.token_encryption import encrypt_token
from tasks.garmin_tasks import sync_garmin_activities_task, sync_garmin_recovery_metrics_task
from core.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/garmin", tags=["garmin"])


class GarminConnectRequest(BaseModel):
    """Request model for Garmin connection."""
    username: str
    password: str
    athlete_id: Optional[UUID] = None


@router.post("/connect")
def connect_garmin(
    request: GarminConnectRequest,
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
        
        # Get or create athlete
        if request.athlete_id:
            athlete = db.query(Athlete).filter(Athlete.id == request.athlete_id).first()
            if not athlete:
                raise HTTPException(status_code=404, detail="Athlete not found")
        else:
            # Create new athlete if not specified
            athlete = Athlete()
            db.add(athlete)
            db.flush()
        
        # Store Garmin credentials (encrypted)
        athlete.garmin_username = request.username
        athlete.garmin_password_encrypted = encrypted_password
        athlete.garmin_connected = True
        athlete.garmin_sync_enabled = True
        
        db.commit()
        
        # Trigger initial sync
        try:
            # Sync activities
            sync_garmin_activities_task.delay(str(athlete.id))
            # Sync recovery metrics (last 30 days)
            sync_garmin_recovery_metrics_task.delay(str(athlete.id), days_back=30)
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
    db: Session = Depends(get_db)
):
    """
    Disconnect athlete's Garmin account.
    
    Removes credentials and disables sync.
    """
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
    db: Session = Depends(get_db)
):
    """
    Manually trigger Garmin sync for an athlete.
    
    Args:
        athlete_id: Athlete UUID
        
    Returns:
        Task ID for tracking sync status
    """
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
    db: Session = Depends(get_db)
):
    """
    Get Garmin connection status for an athlete.
    
    Returns:
        Connection status and last sync time
    """
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    
    return {
        "connected": athlete.garmin_connected or False,
        "sync_enabled": athlete.garmin_sync_enabled or False,
        "last_sync": athlete.last_garmin_sync.isoformat() if athlete.last_garmin_sync else None,
        "username": athlete.garmin_username if athlete.garmin_connected else None
    }

