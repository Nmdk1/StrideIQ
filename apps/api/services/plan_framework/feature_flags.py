"""
Feature Flag Service

Enables gating any feature without code deploy.
All paywall logic goes through here.

Usage:
    flags = FeatureFlagService(db, cache)
    
    # Check if feature is enabled
    if flags.is_enabled("plan.semi_custom", athlete_id):
        ...
    
    # Check access with reason
    access = flags.check_access("plan.custom", athlete)
    if not access.allowed:
        return {"error": access.reason, "upgrade_path": access.upgrade_path}
"""

import json
import hashlib
from typing import Optional, List
from dataclasses import dataclass
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session


@dataclass
class AccessResult:
    """Result of access check."""
    allowed: bool
    reason: Optional[str] = None
    required_tier: Optional[str] = None
    price: Optional[float] = None
    upgrade_path: Optional[str] = None


class FeatureFlagService:
    """
    Central service for feature flag management.
    
    Features can be gated by:
    - Global enable/disable
    - Subscription requirement
    - Tier requirement (legacy tiers are mapped to Elite access)
    - One-time payment
    - Rollout percentage
    - Beta tester list
    """
    
    # Cache TTL in seconds
    CACHE_TTL = 300  # 5 minutes
    
    def __init__(self, db: Session, cache=None):
        """
        Initialize feature flag service.
        
        Args:
            db: SQLAlchemy session
            cache: Redis client (optional, uses in-memory if not provided)
        """
        self.db = db
        self.cache = cache
        self._local_cache = {}  # Fallback for no Redis
    
    def is_enabled(self, flag_key: str, athlete_id: UUID = None) -> bool:
        """
        Check if a feature flag is enabled.
        
        Args:
            flag_key: Feature flag key (e.g., "plan.semi_custom")
            athlete_id: Optional athlete ID for rollout/beta checks
            
        Returns:
            True if feature is enabled for this context
        """
        flag = self._get_flag(flag_key)
        
        if not flag:
            return False
        
        if not flag.get("enabled", False):
            return False
        
        # Check rollout percentage
        rollout = flag.get("rollout_percentage", 100)
        if rollout < 100 and athlete_id:
            if not self._in_rollout(athlete_id, rollout, flag_key):
                return False
        
        # Check beta list (always allows if on list)
        beta_list = flag.get("allowed_athlete_ids", [])
        if beta_list and athlete_id:
            if str(athlete_id) in [str(x) for x in beta_list]:
                return True
        
        return True
    
    def check_access(self, flag_key: str, athlete) -> AccessResult:
        """
        Check if athlete can access a feature, with reason if blocked.
        
        Args:
            flag_key: Feature flag key
            athlete: Athlete object with subscription info
            
        Returns:
            AccessResult with allowed status and reason
        """
        flag = self._get_flag(flag_key)
        
        if not flag:
            return AccessResult(allowed=False, reason="feature_not_found")
        
        if not flag.get("enabled", False):
            return AccessResult(allowed=False, reason="feature_disabled")
        
        # Check subscription requirement
        if flag.get("requires_subscription", False):
            if not getattr(athlete, "has_active_subscription", False):
                return AccessResult(
                    allowed=False,
                    reason="subscription_required",
                    upgrade_path="/settings"
                )
        
        # Check tier requirement
        required_tier = flag.get("requires_tier")
        if required_tier:
            athlete_tier = getattr(athlete, "subscription_tier", "free")
            if not self._tier_satisfies(athlete_tier, required_tier):
                return AccessResult(
                    allowed=False,
                    reason="tier_upgrade_required",
                    required_tier="elite",
                    upgrade_path="/settings"
                )
        
        # Check payment requirement
        price = flag.get("requires_payment")
        if price and price > 0:
            if not self._has_purchased(athlete.id, flag_key):
                return AccessResult(
                    allowed=False,
                    reason="payment_required",
                    price=float(price),
                    upgrade_path=f"/purchase/{flag_key}"
                )
        
        # Check rollout
        rollout = flag.get("rollout_percentage", 100)
        if rollout < 100:
            if not self._in_rollout(athlete.id, rollout, flag_key):
                return AccessResult(allowed=False, reason="not_in_rollout")
        
        return AccessResult(allowed=True)
    
    def get_flag(self, flag_key: str) -> Optional[dict]:
        """Get a feature flag by key."""
        return self._get_flag(flag_key)
    
    def set_flag(self, flag_key: str, updates: dict) -> bool:
        """
        Update a feature flag.
        
        Args:
            flag_key: Feature flag key
            updates: Dict of fields to update
            
        Returns:
            True if successful
        """
        from models import FeatureFlag
        
        flag = self.db.query(FeatureFlag).filter_by(key=flag_key).first()
        if not flag:
            return False
        
        for field, value in updates.items():
            if hasattr(flag, field):
                setattr(flag, field, value)
        
        flag.updated_at = datetime.utcnow()
        self.db.commit()
        
        # Invalidate cache
        self._invalidate_cache(flag_key)
        
        return True
    
    def create_flag(
        self,
        key: str,
        name: str,
        enabled: bool = False,
        requires_subscription: bool = False,
        requires_tier: str = None,
        requires_payment: float = None,
        rollout_percentage: int = 100,
        description: str = None
    ) -> dict:
        """Create a new feature flag."""
        from models import FeatureFlag
        
        flag = FeatureFlag(
            key=key,
            name=name,
            description=description,
            enabled=enabled,
            requires_subscription=requires_subscription,
            requires_tier=requires_tier,
            requires_payment=requires_payment,
            rollout_percentage=rollout_percentage,
        )
        
        self.db.add(flag)
        self.db.commit()
        
        return self._flag_to_dict(flag)
    
    def _get_flag(self, flag_key: str) -> Optional[dict]:
        """Get flag from cache or database."""
        cache_key = f"flag:{flag_key}"
        
        # Try cache first
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return json.loads(cached)
        elif flag_key in self._local_cache:
            return self._local_cache[flag_key]
        
        # Load from database
        from models import FeatureFlag
        
        flag = self.db.query(FeatureFlag).filter_by(key=flag_key).first()
        if not flag:
            return None
        
        flag_dict = self._flag_to_dict(flag)
        
        # Cache it
        if self.cache:
            self.cache.setex(cache_key, self.CACHE_TTL, json.dumps(flag_dict))
        else:
            self._local_cache[flag_key] = flag_dict
        
        return flag_dict
    
    def _flag_to_dict(self, flag) -> dict:
        """Convert FeatureFlag model to dict."""
        return {
            "key": flag.key,
            "name": flag.name,
            "description": flag.description,
            "enabled": flag.enabled,
            "requires_subscription": flag.requires_subscription,
            "requires_tier": flag.requires_tier,
            "requires_payment": float(flag.requires_payment) if flag.requires_payment else None,
            "rollout_percentage": flag.rollout_percentage,
            "allowed_athlete_ids": flag.allowed_athlete_ids or [],
        }
    
    def _invalidate_cache(self, flag_key: str):
        """Invalidate cache for a flag."""
        cache_key = f"flag:{flag_key}"
        if self.cache:
            self.cache.delete(cache_key)
        elif flag_key in self._local_cache:
            del self._local_cache[flag_key]
    
    def _in_rollout(self, athlete_id: UUID, percentage: int, flag_key: str) -> bool:
        """
        Determine if athlete is in rollout percentage.
        Uses consistent hashing so same athlete always gets same result.
        """
        if percentage >= 100:
            return True
        if percentage <= 0:
            return False
        
        # Create consistent hash
        hash_input = f"{athlete_id}:{flag_key}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        bucket = hash_value % 100
        
        return bucket < percentage
    
    def _tier_satisfies(self, athlete_tier: str, required_tier: str) -> bool:
        """Check if athlete's tier satisfies requirement."""
        # Normalize legacy paid tiers to Elite access while we converge on a single paid tier.
        normalized_athlete_tier = (athlete_tier or "free").lower()
        normalized_required_tier = (required_tier or "free").lower()

        legacy_paid = {"pro", "premium", "guided", "subscription"}
        if normalized_athlete_tier in legacy_paid:
            normalized_athlete_tier = "elite"
        if normalized_required_tier in legacy_paid:
            normalized_required_tier = "elite"

        tier_hierarchy = {
            "free": 0,
            "basic": 1,
            "elite": 2,
        }
        
        athlete_level = tier_hierarchy.get(normalized_athlete_tier, 0)
        required_level = tier_hierarchy.get(normalized_required_tier, 0)
        
        return athlete_level >= required_level
    
    def _has_purchased(self, athlete_id: UUID, flag_key: str) -> bool:
        """Check if athlete has purchased a one-time feature."""
        from models import Purchase
        
        purchase = self.db.query(Purchase).filter_by(
            athlete_id=athlete_id,
            product_key=flag_key,
            status="completed"
        ).first()
        
        return purchase is not None
