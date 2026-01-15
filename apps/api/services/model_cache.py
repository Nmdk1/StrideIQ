"""
Model Cache Service (ADR-024)

Caches calibrated individual performance model parameters in database.

Features:
- User-scoped caching
- 7-day TTL with intelligent invalidation
- Automatic recalibration on expiry
- Invalidation hooks for activity sync

Usage:
    cache = ModelCache(db)
    model = cache.get_or_calibrate(athlete_id)
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
import hashlib
import json
import logging

from sqlalchemy.orm import Session
from sqlalchemy import text

from services.individual_performance_model import (
    IndividualPerformanceModel,
    BanisterModel,
    ModelConfidence,
    DEFAULT_TAU1,
    DEFAULT_TAU2
)

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

CACHE_TTL_DAYS = 7
ACTIVITY_THRESHOLD = 10  # Invalidate after this many new activities


# =============================================================================
# DATABASE OPERATIONS
# =============================================================================

def ensure_model_table_exists(db: Session) -> None:
    """Create individual_model table if it doesn't exist."""
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS individual_model (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                athlete_id UUID NOT NULL UNIQUE,
                
                -- Calibrated parameters
                tau1 NUMERIC NOT NULL,
                tau2 NUMERIC NOT NULL,
                k1 NUMERIC NOT NULL,
                k2 NUMERIC NOT NULL,
                p0 NUMERIC NOT NULL,
                
                -- Fit quality
                fit_error NUMERIC,
                r_squared NUMERIC,
                n_performance_markers INTEGER,
                n_training_days INTEGER,
                
                -- Confidence
                confidence TEXT NOT NULL,
                confidence_notes JSONB DEFAULT '[]',
                
                -- Cache metadata
                input_data_hash TEXT,
                last_activity_date DATE,
                calibrated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                
                -- Audit
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))
        
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_individual_model_athlete_id 
            ON individual_model(athlete_id)
        """))
        
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_individual_model_expires_at 
            ON individual_model(expires_at)
        """))
        
        db.commit()
    except Exception as e:
        logger.warning(f"Could not ensure table exists: {e}")
        db.rollback()


# =============================================================================
# MODEL CACHE
# =============================================================================

class ModelCache:
    """
    Caches individual performance model parameters.
    
    Provides fast retrieval of calibrated models with automatic
    invalidation and recalibration.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self._ensure_table()
    
    def _ensure_table(self) -> None:
        """Ensure the cache table exists."""
        ensure_model_table_exists(self.db)
    
    def get(self, athlete_id: UUID) -> Optional[BanisterModel]:
        """
        Get cached model if valid.
        
        Returns None if:
        - No cached model exists
        - Cached model is expired
        """
        try:
            result = self.db.execute(text("""
                SELECT 
                    tau1, tau2, k1, k2, p0,
                    fit_error, r_squared,
                    n_performance_markers, n_training_days,
                    confidence, confidence_notes,
                    calibrated_at, expires_at
                FROM individual_model
                WHERE athlete_id = :aid
                    AND expires_at > NOW()
            """), {"aid": str(athlete_id)}).fetchone()
            
            if not result:
                return None
            
            return BanisterModel(
                athlete_id=str(athlete_id),
                tau1=float(result[0]),
                tau2=float(result[1]),
                k1=float(result[2]),
                k2=float(result[3]),
                p0=float(result[4]),
                fit_error=float(result[5]) if result[5] else 0.0,
                r_squared=float(result[6]) if result[6] else 0.0,
                n_performance_markers=int(result[7]) if result[7] else 0,
                n_training_days=int(result[8]) if result[8] else 0,
                confidence=ModelConfidence(result[9]) if result[9] else ModelConfidence.UNCALIBRATED,
                confidence_notes=result[10] if result[10] else [],
                calibrated_at=result[11]
            )
            
        except Exception as e:
            logger.warning(f"Cache get failed: {e}")
            return None
    
    def set(self, athlete_id: UUID, model: BanisterModel) -> None:
        """
        Cache calibrated model.
        
        Uses upsert to handle both insert and update.
        """
        expires_at = datetime.now() + timedelta(days=CACHE_TTL_DAYS)
        
        try:
            # Get last activity date for cache key
            last_activity = self.db.execute(text("""
                SELECT MAX(DATE(start_time))
                FROM activity
                WHERE athlete_id = :aid
            """), {"aid": str(athlete_id)}).scalar()
            
            # Compute input hash for cache validation
            input_hash = self._compute_input_hash(athlete_id)
            
            # Upsert
            self.db.execute(text("""
                INSERT INTO individual_model (
                    athlete_id, tau1, tau2, k1, k2, p0,
                    fit_error, r_squared, n_performance_markers, n_training_days,
                    confidence, confidence_notes,
                    input_data_hash, last_activity_date,
                    calibrated_at, expires_at, updated_at
                ) VALUES (
                    :aid, :tau1, :tau2, :k1, :k2, :p0,
                    :fit_error, :r_squared, :n_perf, :n_days,
                    :confidence, :notes,
                    :hash, :last_act,
                    NOW(), :expires, NOW()
                )
                ON CONFLICT (athlete_id) DO UPDATE SET
                    tau1 = :tau1, tau2 = :tau2, k1 = :k1, k2 = :k2, p0 = :p0,
                    fit_error = :fit_error, r_squared = :r_squared,
                    n_performance_markers = :n_perf, n_training_days = :n_days,
                    confidence = :confidence, confidence_notes = :notes,
                    input_data_hash = :hash, last_activity_date = :last_act,
                    calibrated_at = NOW(), expires_at = :expires, updated_at = NOW()
            """), {
                "aid": str(athlete_id),
                "tau1": model.tau1,
                "tau2": model.tau2,
                "k1": model.k1,
                "k2": model.k2,
                "p0": model.p0,
                "fit_error": model.fit_error,
                "r_squared": model.r_squared,
                "n_perf": model.n_performance_markers,
                "n_days": model.n_training_days,
                "confidence": model.confidence.value,
                "notes": json.dumps(model.confidence_notes),
                "hash": input_hash,
                "last_act": last_activity,
                "expires": expires_at
            })
            
            self.db.commit()
            logger.info(f"Cached model for {athlete_id}, expires {expires_at}")
            
        except Exception as e:
            logger.error(f"Cache set failed: {e}")
            self.db.rollback()
    
    def invalidate(self, athlete_id: UUID) -> None:
        """
        Invalidate cached model.
        
        Called when:
        - New activity synced
        - User requests recalibration
        """
        try:
            self.db.execute(text("""
                UPDATE individual_model
                SET expires_at = NOW() - INTERVAL '1 second'
                WHERE athlete_id = :aid
            """), {"aid": str(athlete_id)})
            
            self.db.commit()
            logger.info(f"Invalidated cache for {athlete_id}")
            
        except Exception as e:
            logger.warning(f"Cache invalidate failed: {e}")
            self.db.rollback()
    
    def get_or_calibrate(
        self, 
        athlete_id: UUID,
        force_recalibrate: bool = False
    ) -> BanisterModel:
        """
        Get cached model or calibrate fresh.
        
        This is the main entry point for model access.
        
        Args:
            athlete_id: Athlete UUID
            force_recalibrate: Force recalibration even if cache valid
            
        Returns:
            Calibrated BanisterModel
        """
        # Check cache first (unless forcing)
        if not force_recalibrate:
            cached = self.get(athlete_id)
            if cached:
                logger.debug(f"Cache hit for {athlete_id}")
                return cached
        
        # Calibrate fresh
        logger.info(f"Calibrating model for {athlete_id}")
        engine = IndividualPerformanceModel(self.db)
        model = engine.calibrate(athlete_id)
        
        # Cache result
        self.set(athlete_id, model)
        
        return model
    
    def should_invalidate_on_sync(self, athlete_id: UUID) -> bool:
        """
        Check if cache should be invalidated after activity sync.
        
        Invalidates if:
        - A new race was added
        - >10 new activities since last calibration
        """
        try:
            result = self.db.execute(text("""
                SELECT 
                    last_activity_date,
                    (SELECT COUNT(*) FROM activity 
                     WHERE athlete_id = :aid 
                       AND DATE(start_time) > im.last_activity_date) as new_count,
                    (SELECT COUNT(*) FROM activity 
                     WHERE athlete_id = :aid 
                       AND is_race = TRUE
                       AND DATE(start_time) > im.last_activity_date) as new_races
                FROM individual_model im
                WHERE athlete_id = :aid
            """), {"aid": str(athlete_id)}).fetchone()
            
            if not result:
                return True  # No cache, will calibrate anyway
            
            new_count = result[1] or 0
            new_races = result[2] or 0
            
            # Invalidate if new race or many new activities
            return new_races > 0 or new_count >= ACTIVITY_THRESHOLD
            
        except Exception as e:
            logger.warning(f"Check invalidation failed: {e}")
            return True
    
    def _compute_input_hash(self, athlete_id: UUID) -> str:
        """Compute hash of input data for cache key."""
        try:
            # Get activity summary as hash input
            result = self.db.execute(text("""
                SELECT 
                    COUNT(*) as n_activities,
                    MAX(DATE(start_time)) as last_date,
                    SUM(distance_m) as total_distance,
                    COUNT(*) FILTER (WHERE is_race = TRUE) as n_races
                FROM activity
                WHERE athlete_id = :aid
                    AND start_time > NOW() - INTERVAL '1 year'
            """), {"aid": str(athlete_id)}).fetchone()
            
            if not result:
                return "empty"
            
            hash_input = f"{result[0]}_{result[1]}_{result[2]:.0f}_{result[3]}"
            return hashlib.md5(hash_input.encode()).hexdigest()[:12]
            
        except Exception:
            return "unknown"
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics for monitoring."""
        try:
            result = self.db.execute(text("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE expires_at > NOW()) as valid,
                    COUNT(*) FILTER (WHERE expires_at <= NOW()) as expired,
                    AVG(EXTRACT(EPOCH FROM (expires_at - calibrated_at))) / 86400 as avg_ttl_days
                FROM individual_model
            """)).fetchone()
            
            return {
                "total_cached": result[0] or 0,
                "valid": result[1] or 0,
                "expired": result[2] or 0,
                "avg_ttl_days": round(result[3], 1) if result[3] else 0
            }
            
        except Exception as e:
            logger.warning(f"Get stats failed: {e}")
            return {"error": str(e)}


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_cached_model(athlete_id: UUID, db: Session) -> Optional[BanisterModel]:
    """Get cached model if valid."""
    cache = ModelCache(db)
    return cache.get(athlete_id)


def get_or_calibrate_model_cached(
    athlete_id: UUID, 
    db: Session,
    force_recalibrate: bool = False
) -> BanisterModel:
    """Get cached model or calibrate fresh."""
    cache = ModelCache(db)
    return cache.get_or_calibrate(athlete_id, force_recalibrate)


def invalidate_model_cache(athlete_id: UUID, db: Session) -> None:
    """Invalidate cached model."""
    cache = ModelCache(db)
    cache.invalidate(athlete_id)


def on_activity_sync(athlete_id: UUID, db: Session) -> None:
    """
    Hook called after activity sync.
    
    Checks if cache should be invalidated and does so if needed.
    """
    cache = ModelCache(db)
    if cache.should_invalidate_on_sync(athlete_id):
        cache.invalidate(athlete_id)
        logger.info(f"Cache invalidated on sync for {athlete_id}")
