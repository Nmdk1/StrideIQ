"""
Recovery Metrics API Router

Endpoints for recovery-related metrics:
- Recovery half-life
- Durability index
- Consistency index
- False fitness warnings
- Masked fatigue warnings
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, List, Optional

from core.database import get_db
from core.auth import get_current_user
from models import Athlete
from services.recovery_metrics import (
    update_athlete_metrics,
    detect_false_fitness,
    detect_masked_fatigue,
)

router = APIRouter(prefix="/v1/recovery-metrics", tags=["Recovery Metrics"])


@router.get("/me")
async def get_my_recovery_metrics(
    db: Session = Depends(get_db),
    current_user: Athlete = Depends(get_current_user)
) -> Dict:
    """
    Get recovery metrics for current user.
    
    Returns cached metrics if recently calculated, otherwise calculates fresh.
    """
    from datetime import datetime, timedelta
    
    # Check if metrics are stale (> 24 hours old)
    needs_refresh = (
        current_user.last_metrics_calculation is None or
        current_user.last_metrics_calculation < datetime.utcnow() - timedelta(hours=24)
    )
    
    if needs_refresh:
        metrics = update_athlete_metrics(db, str(current_user.id))
    else:
        metrics = {
            'recovery_half_life_hours': current_user.recovery_half_life_hours,
            'durability_index': current_user.durability_index,
            'consistency_index': current_user.consistency_index,
        }
    
    return {
        'athlete_id': str(current_user.id),
        'metrics': metrics,
        'last_calculated': current_user.last_metrics_calculation.isoformat() if current_user.last_metrics_calculation else None
    }


@router.post("/refresh")
async def refresh_recovery_metrics(
    db: Session = Depends(get_db),
    current_user: Athlete = Depends(get_current_user)
) -> Dict:
    """
    Force refresh of recovery metrics for current user.
    """
    metrics = update_athlete_metrics(db, str(current_user.id))
    
    return {
        'athlete_id': str(current_user.id),
        'metrics': metrics,
        'refreshed': True
    }


@router.get("/warnings")
async def get_recovery_warnings(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: Athlete = Depends(get_current_user)
) -> Dict:
    """
    Get recovery-related warnings for current user.
    
    Detects:
    - False fitness signals
    - Masked fatigue signals
    
    These are early warning signs from the manifesto that help prevent injury
    and overtraining.
    """
    false_fitness = detect_false_fitness(db, str(current_user.id), days)
    masked_fatigue = detect_masked_fatigue(db, str(current_user.id), min(14, days))
    
    warnings = false_fitness + masked_fatigue
    
    return {
        'athlete_id': str(current_user.id),
        'analysis_period_days': days,
        'warnings': warnings,
        'warning_count': len(warnings),
        'has_warnings': len(warnings) > 0
    }


