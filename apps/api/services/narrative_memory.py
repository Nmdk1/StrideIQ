"""
Narrative Memory (ADR-033)

Tracks shown narratives to prevent repetition.

Key insight: Even with dynamic anchors, the same narrative can appear
if the athlete's situation is stable. Memory prevents staleness.

Storage: Redis for speed, with DB fallback for persistence.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from uuid import UUID
import logging
import json

from sqlalchemy.orm import Session
from sqlalchemy import Column, DateTime, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID

logger = logging.getLogger(__name__)


# =============================================================================
# IN-MEMORY FALLBACK (when Redis unavailable)
# =============================================================================

# Simple in-memory store for development/fallback
_memory_store: Dict[str, Dict[str, datetime]] = {}


class NarrativeMemory:
    """
    Tracks shown narratives per athlete to prevent repetition.
    
    Stores:
    - narrative_hash: The hash of the rendered text
    - signal_type: Category of narrative
    - shown_at: When it was shown
    
    Provides:
    - recently_shown(): Was this exact narrative shown recently?
    - record_shown(): Mark a narrative as shown
    - get_stale_patterns(): Which signal types are overused?
    """
    
    def __init__(self, db: Session, athlete_id: UUID, use_redis: bool = True):
        self.db = db
        self.athlete_id = str(athlete_id)
        self.use_redis = use_redis
        self._redis = None
        
        if use_redis:
            try:
                from core.redis_client import get_redis_client
                self._redis = get_redis_client()
            except Exception as e:
                logger.warning(f"Redis unavailable, using memory fallback: {e}")
                self._redis = None
    
    # =========================================================================
    # CORE OPERATIONS
    # =========================================================================
    
    def record_shown(
        self,
        narrative_hash: str,
        signal_type: str,
        surface: str = "home"
    ) -> None:
        """
        Record that a narrative was shown to the athlete.
        
        Args:
            narrative_hash: Hash of the rendered text
            signal_type: Category (load_state, workout_context, etc.)
            surface: Where shown (home, workout, plan)
        """
        key = self._make_key(narrative_hash)
        data = {
            "signal_type": signal_type,
            "surface": surface,
            "shown_at": datetime.utcnow().isoformat()
        }
        
        if self._redis:
            try:
                self._redis.setex(
                    key,
                    timedelta(days=60),  # TTL 60 days
                    json.dumps(data)
                )
                
                # Also track pattern usage
                pattern_key = self._make_pattern_key(signal_type)
                self._redis.incr(pattern_key)
                self._redis.expire(pattern_key, timedelta(days=30))
                
                return
            except Exception as e:
                logger.warning(f"Redis write failed: {e}")
        
        # Fallback to memory
        if self.athlete_id not in _memory_store:
            _memory_store[self.athlete_id] = {}
        _memory_store[self.athlete_id][narrative_hash] = datetime.utcnow()
    
    def recently_shown(
        self,
        narrative_hash: str,
        days: int = 14
    ) -> bool:
        """
        Check if this exact narrative was shown recently.
        
        Returns True if shown within `days` days.
        """
        key = self._make_key(narrative_hash)
        
        if self._redis:
            try:
                data = self._redis.get(key)
                if data:
                    record = json.loads(data)
                    shown_at = datetime.fromisoformat(record["shown_at"])
                    if datetime.utcnow() - shown_at < timedelta(days=days):
                        return True
                return False
            except Exception as e:
                logger.warning(f"Redis read failed: {e}")
        
        # Fallback to memory
        athlete_memory = _memory_store.get(self.athlete_id, {})
        shown_at = athlete_memory.get(narrative_hash)
        if shown_at:
            return datetime.utcnow() - shown_at < timedelta(days=days)
        return False
    
    def get_stale_patterns(self, threshold: int = 5) -> List[str]:
        """
        Get signal types that have been shown too frequently.
        
        Returns signal_type names that were shown >= threshold times in last 30 days.
        """
        stale = []
        
        signal_types = [
            "load_state_fresh", "load_state_coiled", "load_state_balanced",
            "workout_context", "injury_rebound", "efficiency_outlier",
            "uncertainty", "milestone", "tau_characteristic"
        ]
        
        if self._redis:
            try:
                for signal_type in signal_types:
                    key = self._make_pattern_key(signal_type)
                    count = self._redis.get(key)
                    if count and int(count) >= threshold:
                        stale.append(signal_type)
                return stale
            except Exception as e:
                logger.warning(f"Redis read failed: {e}")
        
        # Memory fallback doesn't track patterns well, return empty
        return []
    
    def get_shown_count(self, signal_type: str, days: int = 30) -> int:
        """
        Get how many times a signal type was shown in the last N days.
        """
        if self._redis:
            try:
                key = self._make_pattern_key(signal_type)
                count = self._redis.get(key)
                return int(count) if count else 0
            except Exception:
                pass
        return 0
    
    def clear_old(self, days: int = 60) -> int:
        """
        Clear records older than N days.
        
        With Redis TTL, this is automatic. Memory fallback needs manual cleanup.
        """
        if self._redis:
            # Redis TTL handles this automatically
            return 0
        
        # Memory fallback cleanup
        cutoff = datetime.utcnow() - timedelta(days=days)
        athlete_memory = _memory_store.get(self.athlete_id, {})
        
        to_remove = [
            h for h, shown_at in athlete_memory.items()
            if shown_at < cutoff
        ]
        
        for h in to_remove:
            del athlete_memory[h]
        
        return len(to_remove)
    
    # =========================================================================
    # FRESHNESS CHECK
    # =========================================================================
    
    def filter_fresh(
        self,
        narratives: List,  # List of Narrative objects
        days: int = 14
    ) -> List:
        """
        Filter narratives to only include those not recently shown.
        
        Useful for: "Show me 3 insights, but not ones I've seen this week."
        """
        fresh = []
        for narrative in narratives:
            if not self.recently_shown(narrative.hash, days):
                fresh.append(narrative)
        return fresh
    
    def pick_freshest(
        self,
        narratives: List,  # List of Narrative objects
        count: int = 1,
        fallback_days: int = 7
    ) -> List:
        """
        Pick the freshest N narratives.
        
        Strategy:
        1. First try to find narratives not shown in last 14 days
        2. Fall back to narratives not shown in last 7 days
        3. Finally return highest priority regardless
        """
        # Try strict freshness (14 days)
        fresh = self.filter_fresh(narratives, 14)
        if len(fresh) >= count:
            return sorted(fresh, key=lambda n: n.priority, reverse=True)[:count]
        
        # Try relaxed freshness (7 days)
        fresh = self.filter_fresh(narratives, fallback_days)
        if len(fresh) >= count:
            return sorted(fresh, key=lambda n: n.priority, reverse=True)[:count]
        
        # Return highest priority regardless
        return sorted(narratives, key=lambda n: n.priority, reverse=True)[:count]
    
    # =========================================================================
    # HELPERS
    # =========================================================================
    
    def _make_key(self, narrative_hash: str) -> str:
        """Make Redis key for a specific narrative."""
        return f"narrative:{self.athlete_id}:{narrative_hash}"
    
    def _make_pattern_key(self, signal_type: str) -> str:
        """Make Redis key for pattern counting."""
        return f"narrative_pattern:{self.athlete_id}:{signal_type}"


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def get_narrative_memory(db: Session, athlete_id: UUID) -> NarrativeMemory:
    """Get narrative memory for an athlete."""
    return NarrativeMemory(db, athlete_id)
