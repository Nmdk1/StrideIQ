"""
Feature Flag Helper

Simplified interface for checking feature flags.
Wraps the FeatureFlagService for convenience in routers.
"""

from sqlalchemy.orm import Session
from typing import Optional
from services.plan_framework.feature_flags import FeatureFlagService


def is_feature_enabled(flag_key: str, athlete_id: Optional[str], db: Session) -> bool:
    """
    Check if a feature flag is enabled for an athlete.
    
    Args:
        flag_key: Feature flag key (e.g., "signals.home_banner")
        athlete_id: Athlete UUID string (optional)
        db: Database session
        
    Returns:
        True if feature is enabled
    """
    try:
        service = FeatureFlagService(db)
        return service.is_enabled(flag_key, athlete_id)
    except Exception:
        # Default to True if flag service fails (fail open for features)
        return True
