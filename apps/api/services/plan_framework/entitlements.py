"""
Entitlements Service

Clean separation of "can they access this?" logic.
Consolidates subscription, purchases, and feature flags.

Usage:
    entitlements = EntitlementsService(db, feature_flags)
    
    # Get all plan entitlements
    perms = entitlements.get_plan_entitlements(athlete)
    
    # Check specific plan access
    access = entitlements.check_plan_access(athlete, "custom", "marathon", 18)
"""

from typing import Optional, List
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from .feature_flags import FeatureFlagService, AccessResult
from .constants import PlanTier, Distance


@dataclass
class PlanEntitlements:
    """All plan-related entitlements for an athlete."""
    
    # Standard plans
    can_generate_standard: bool
    available_distances: List[str]
    available_durations: dict  # {distance: [durations]}
    
    # Semi-custom
    can_generate_semi_custom: bool
    semi_custom_price: Optional[float]
    
    # Custom
    can_generate_custom: bool
    custom_upgrade_path: Optional[str]
    
    # Features
    can_use_pace_integration: bool
    can_use_strava: bool
    can_use_option_ab: bool
    can_use_gpt_coach: bool
    can_use_dynamic_adaptation: bool


class EntitlementsService:
    """
    Central authority for what an athlete can access.
    """
    
    def __init__(self, db: Session, flags: FeatureFlagService = None):
        self.db = db
        self.flags = flags or FeatureFlagService(db)
    
    def get_plan_entitlements(self, athlete) -> PlanEntitlements:
        """Get all plan-related entitlements for athlete."""
        
        return PlanEntitlements(
            # Standard plans
            can_generate_standard=self._can_generate_standard(athlete),
            available_distances=self._get_available_distances(athlete),
            available_durations=self._get_available_durations(athlete),
            
            # Semi-custom
            can_generate_semi_custom=self._can_generate_semi_custom(athlete),
            semi_custom_price=self._get_semi_custom_price(),
            
            # Custom
            can_generate_custom=self._can_generate_custom(athlete),
            custom_upgrade_path=self._get_upgrade_path(athlete, "plan.custom"),
            
            # Features
            can_use_pace_integration=self._can_use_feature(athlete, "plan.pace_integration"),
            can_use_strava=self._can_use_feature(athlete, "plan.strava_integration"),
            can_use_option_ab=self._can_use_feature(athlete, "plan.option_ab"),
            can_use_gpt_coach=self._can_use_feature(athlete, "plan.gpt_coach"),
            can_use_dynamic_adaptation=self._can_use_feature(athlete, "plan.dynamic_adaptation"),
        )
    
    def check_plan_access(
        self,
        athlete,
        plan_type: str,  # "standard", "semi_custom", "custom"
        distance: str,
        duration: int
    ) -> AccessResult:
        """Check if athlete can generate this specific plan."""
        
        # Build the feature key
        if plan_type == "standard":
            flag_key = f"plan.standard.{distance}"
        else:
            flag_key = f"plan.{plan_type}"
        
        access = self.flags.check_access(flag_key, athlete)
        
        if not access.allowed:
            return access
        
        # Additional validation for semi/custom
        if plan_type == "semi_custom":
            return self._check_semi_custom_access(athlete, distance, duration)
        
        if plan_type == "custom":
            return self._check_custom_access(athlete, distance, duration)
        
        return AccessResult(allowed=True)
    
    def _can_generate_standard(self, athlete) -> bool:
        """Check if athlete can generate standard plans."""
        # Standard plans are free for everyone
        return self.flags.is_enabled("plan.standard", athlete.id)
    
    def _can_generate_semi_custom(self, athlete) -> bool:
        """Check if athlete can generate semi-custom plans."""
        access = self.flags.check_access("plan.semi_custom", athlete)
        return access.allowed
    
    def _can_generate_custom(self, athlete) -> bool:
        """Check if athlete can generate custom plans."""
        access = self.flags.check_access("plan.custom", athlete)
        return access.allowed
    
    def _get_available_distances(self, athlete) -> List[str]:
        """Get distances athlete can generate plans for."""
        distances = []
        for distance in ["5k", "10k", "half_marathon", "marathon"]:
            if self.flags.is_enabled(f"plan.standard.{distance}", athlete.id):
                distances.append(distance)
        return distances
    
    def _get_available_durations(self, athlete) -> dict:
        """Get available durations by distance."""
        from .constants import STANDARD_DURATIONS
        
        result = {}
        for distance in self._get_available_distances(athlete):
            try:
                dist_enum = Distance(distance)
                result[distance] = STANDARD_DURATIONS.get(dist_enum, [])
            except ValueError:
                result[distance] = []
        
        return result
    
    def _get_semi_custom_price(self) -> Optional[float]:
        """Get semi-custom plan price."""
        flag = self.flags.get_flag("plan.semi_custom")
        if flag:
            return flag.get("requires_payment")
        return None
    
    def _get_upgrade_path(self, athlete, flag_key: str) -> Optional[str]:
        """Get upgrade path for a feature."""
        access = self.flags.check_access(flag_key, athlete)
        if not access.allowed:
            return access.upgrade_path
        return None
    
    def _can_use_feature(self, athlete, flag_key: str) -> bool:
        """Check if athlete can use a feature."""
        access = self.flags.check_access(flag_key, athlete)
        return access.allowed
    
    def _check_semi_custom_access(
        self, 
        athlete, 
        distance: str, 
        duration: int
    ) -> AccessResult:
        """Additional validation for semi-custom plans."""
        # Check if distance is available
        if distance not in self._get_available_distances(athlete):
            return AccessResult(
                allowed=False,
                reason="distance_not_available"
            )
        
        # Duration validation (4-24 weeks for semi-custom)
        if duration < 4 or duration > 24:
            return AccessResult(
                allowed=False,
                reason="invalid_duration",
            )
        
        return AccessResult(allowed=True)
    
    def _check_custom_access(
        self,
        athlete,
        distance: str,
        duration: int
    ) -> AccessResult:
        """Additional validation for custom plans."""
        # Custom plans need subscription
        if not getattr(athlete, "has_active_subscription", False):
            return AccessResult(
                allowed=False,
                reason="subscription_required",
                upgrade_path="/subscribe"
            )
        
        # Duration validation (4-24 weeks for custom)
        if duration < 4 or duration > 24:
            return AccessResult(
                allowed=False,
                reason="invalid_duration",
            )
        
        return AccessResult(allowed=True)
