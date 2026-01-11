"""
Plan Cache Service

Multi-layer caching for plan system.
Designed for 15,000+ athletes.

Layers:
1. Standard plan templates (shared, 7-day TTL)
2. Athlete active plans (individual, 1-hour TTL)
3. Week workouts (most frequent, 1-day TTL)
4. Plugin registry (until invalidated)

Usage:
    cache = PlanCacheService(redis)
    
    # Get cached plan
    plan = cache.get_athlete_active_plan(athlete_id)
    
    # Cache a plan
    cache.set_athlete_active_plan(athlete_id, plan_dict)
"""

import json
import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime

logger = logging.getLogger(__name__)


class PlanCacheService:
    """
    Multi-layer caching for plan system.
    """
    
    # Cache TTLs in seconds
    TTL_STANDARD_TEMPLATE = 86400 * 7    # 7 days
    TTL_ATHLETE_PLAN = 3600              # 1 hour
    TTL_WEEK_WORKOUTS = 86400            # 1 day
    TTL_REGISTRY = None                  # Until invalidated
    
    def __init__(self, redis=None):
        """
        Initialize cache service.
        
        Args:
            redis: Redis client (optional, uses in-memory if not provided)
        """
        self.redis = redis
        self._local_cache: Dict[str, Any] = {}
        self._local_expiry: Dict[str, datetime] = {}
    
    # ========== Standard Plan Templates (Layer 1) ==========
    
    def get_standard_template(
        self, 
        distance: str, 
        duration: int, 
        tier: str
    ) -> Optional[dict]:
        """
        Get cached standard plan template.
        
        These are shared across all athletes using the same
        distance/duration/tier combination.
        """
        key = f"plan:standard:{distance}:{duration}:{tier}"
        return self._get(key)
    
    def set_standard_template(
        self, 
        distance: str, 
        duration: int, 
        tier: str, 
        template: dict
    ):
        """Cache a standard plan template."""
        key = f"plan:standard:{distance}:{duration}:{tier}"
        self._set(key, template, self.TTL_STANDARD_TEMPLATE)
    
    # ========== Athlete Active Plan (Layer 2) ==========
    
    def get_athlete_active_plan(self, athlete_id: UUID) -> Optional[dict]:
        """
        Get cached active plan for athlete.
        
        This is the most frequently accessed cache -
        every calendar view hits this.
        """
        key = f"plan:athlete:{athlete_id}:active"
        return self._get(key)
    
    def set_athlete_active_plan(self, athlete_id: UUID, plan: dict):
        """Cache athlete's active plan."""
        key = f"plan:athlete:{athlete_id}:active"
        self._set(key, plan, self.TTL_ATHLETE_PLAN)
    
    def invalidate_athlete_plan(self, athlete_id: UUID):
        """Invalidate athlete's plan cache."""
        key = f"plan:athlete:{athlete_id}:active"
        self._delete(key)
    
    # ========== Week Workouts (Layer 3) ==========
    
    def get_week_workouts(self, plan_id: UUID, week_num: int) -> Optional[list]:
        """
        Get cached workouts for a specific week.
        
        This is used when viewing a week in detail.
        """
        key = f"plan:{plan_id}:week:{week_num}"
        return self._get(key)
    
    def set_week_workouts(self, plan_id: UUID, week_num: int, workouts: list):
        """Cache workouts for a week."""
        key = f"plan:{plan_id}:week:{week_num}"
        self._set(key, workouts, self.TTL_WEEK_WORKOUTS)
    
    def invalidate_week(self, plan_id: UUID, week_num: int):
        """Invalidate a week's cache."""
        key = f"plan:{plan_id}:week:{week_num}"
        self._delete(key)
    
    # ========== Plugin Registry (Layer 4) ==========
    
    def get_registry(self, registry_type: str) -> Optional[dict]:
        """Get cached plugin registry data."""
        key = f"registry:{registry_type}"
        return self._get(key)
    
    def set_registry(self, registry_type: str, data: dict):
        """Cache plugin registry data (no TTL - until invalidated)."""
        key = f"registry:{registry_type}"
        self._set(key, data, None)
    
    def invalidate_registry(self):
        """Invalidate all registry caches."""
        patterns = ["registry:workouts", "registry:phases", "registry:rules"]
        for pattern in patterns:
            self._delete(pattern)
        logger.info("Plugin registry cache invalidated")
    
    # ========== Bulk Operations ==========
    
    def invalidate_all_plans(self):
        """Invalidate all plan caches (use sparingly)."""
        if self.redis:
            # Use scan to find and delete plan keys
            cursor = 0
            while True:
                cursor, keys = self.redis.scan(cursor, match="plan:*", count=100)
                if keys:
                    self.redis.delete(*keys)
                if cursor == 0:
                    break
        else:
            self._local_cache = {
                k: v for k, v in self._local_cache.items()
                if not k.startswith("plan:")
            }
        
        logger.info("All plan caches invalidated")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if self.redis:
            info = self.redis.info()
            return {
                "type": "redis",
                "connected": True,
                "used_memory": info.get("used_memory_human", "unknown"),
                "keys": self.redis.dbsize(),
            }
        else:
            return {
                "type": "local",
                "keys": len(self._local_cache),
            }
    
    # ========== Internal Methods ==========
    
    def _get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if self.redis:
            try:
                value = self.redis.get(key)
                if value:
                    return json.loads(value)
            except Exception as e:
                logger.warning(f"Cache get error for {key}: {e}")
        else:
            # Check local cache with expiry
            if key in self._local_cache:
                expiry = self._local_expiry.get(key)
                if expiry is None or expiry > datetime.utcnow():
                    return self._local_cache[key]
                else:
                    # Expired
                    del self._local_cache[key]
                    del self._local_expiry[key]
        
        return None
    
    def _set(self, key: str, value: Any, ttl: Optional[int]):
        """Set value in cache."""
        if self.redis:
            try:
                serialized = json.dumps(value, default=str)
                if ttl:
                    self.redis.setex(key, ttl, serialized)
                else:
                    self.redis.set(key, serialized)
            except Exception as e:
                logger.warning(f"Cache set error for {key}: {e}")
        else:
            self._local_cache[key] = value
            if ttl:
                from datetime import timedelta
                self._local_expiry[key] = datetime.utcnow() + timedelta(seconds=ttl)
            else:
                self._local_expiry[key] = None
    
    def _delete(self, key: str):
        """Delete value from cache."""
        if self.redis:
            try:
                self.redis.delete(key)
            except Exception as e:
                logger.warning(f"Cache delete error for {key}: {e}")
        else:
            self._local_cache.pop(key, None)
            self._local_expiry.pop(key, None)
