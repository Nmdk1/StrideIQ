"""
Redis Caching Layer

Provides caching decorators and utilities for API endpoints.
Includes graceful degradation if Redis is unavailable.
"""
import json
import logging
from functools import wraps
from typing import Optional, Callable, Any
import redis
from redis.exceptions import ConnectionError, TimeoutError, RedisError
from core.config import settings

logger = logging.getLogger(__name__)

# Redis connection pool (singleton)
_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> Optional[redis.Redis]:
    """Get Redis client with connection pooling. Returns None if Redis unavailable."""
    global _redis_client
    
    if _redis_client is not None:
        return _redis_client
    
    try:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=True,
            health_check_interval=30
        )
        # Test connection
        _redis_client.ping()
        logger.info("Redis connection established")
        return _redis_client
    except (ConnectionError, TimeoutError, RedisError) as e:
        logger.warning(f"Redis unavailable: {e}. Caching disabled.")
        _redis_client = None
        return None


def cache_key(prefix: str, *args, **kwargs) -> str:
    """Generate cache key from prefix and arguments."""
    key_parts = [prefix]
    
    # Add args (skip None values)
    for arg in args:
        if arg is not None:
            key_parts.append(str(arg))
    
    # Add kwargs (sorted for consistency, skip None values)
    for k, v in sorted(kwargs.items()):
        if v is not None:
            key_parts.append(f"{k}:{v}")
    
    return ":".join(key_parts)


def get_cache(key: str) -> Optional[Any]:
    """Get value from cache. Returns None if not found or Redis unavailable."""
    client = get_redis_client()
    if not client:
        return None
    
    try:
        value = client.get(key)
        if value:
            return json.loads(value)
        return None
    except (ConnectionError, TimeoutError, RedisError) as e:
        logger.warning(f"Cache get error for key {key}: {e}")
        return None


def set_cache(key: str, value: Any, ttl: int = None) -> bool:
    """Set value in cache. Returns True if successful, False otherwise."""
    client = get_redis_client()
    if not client:
        return False
    
    try:
        if ttl is None:
            ttl = settings.CACHE_TTL_DEFAULT
        
        client.setex(
            key,
            ttl,
            json.dumps(value, default=str)  # default=str handles datetime, UUID, etc.
        )
        return True
    except (ConnectionError, TimeoutError, RedisError) as e:
        logger.warning(f"Cache set error for key {key}: {e}")
        return False


def delete_cache(key: str) -> bool:
    """Delete key from cache. Returns True if successful, False otherwise."""
    client = get_redis_client()
    if not client:
        return False
    
    try:
        client.delete(key)
        return True
    except (ConnectionError, TimeoutError, RedisError) as e:
        logger.warning(f"Cache delete error for key {key}: {e}")
        return False


def invalidate_pattern(pattern: str) -> int:
    """Invalidate all keys matching pattern. Returns count of deleted keys."""
    client = get_redis_client()
    if not client:
        return 0
    
    try:
        keys = client.keys(pattern)
        if keys:
            return client.delete(*keys)
        return 0
    except (ConnectionError, TimeoutError, RedisError) as e:
        logger.warning(f"Cache invalidation error for pattern {pattern}: {e}")
        return 0


def cached(prefix: str, ttl: int = None):
    """
    Decorator to cache function results.
    
    Args:
        prefix: Cache key prefix
        ttl: Time to live in seconds (defaults to CACHE_TTL_DEFAULT)
    
    Usage:
        @cached("efficiency_trends", ttl=3600)
        def get_efficiency_trends(athlete_id: str, days: int):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            key = cache_key(prefix, *args, **kwargs)
            
            # Try to get from cache
            cached_value = get_cache(key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {key}")
                return cached_value
            
            # Cache miss - execute function
            logger.debug(f"Cache miss: {key}")
            result = func(*args, **kwargs)
            
            # Store in cache
            set_cache(key, result, ttl)
            
            return result
        
        return wrapper
    return decorator


# Cache invalidation helpers
def invalidate_athlete_cache(athlete_id: str):
    """Invalidate all cache entries for an athlete."""
    patterns = [
        f"efficiency_trends:*:{athlete_id}:*",
        f"efficiency_trends:{athlete_id}:*",
        f"correlations:*:{athlete_id}:*",
        f"correlations:{athlete_id}:*",
        f"activities:*:{athlete_id}:*",
        f"activities:{athlete_id}:*",
        f"athlete:{athlete_id}",
    ]
    
    total_deleted = 0
    for pattern in patterns:
        total_deleted += invalidate_pattern(pattern)
    
    logger.info(f"Invalidated {total_deleted} cache entries for athlete {athlete_id}")
    return total_deleted


def invalidate_activity_cache(athlete_id: str, activity_id: str = None):
    """Invalidate activity-related cache entries."""
    if activity_id:
        patterns = [
            f"activities:{athlete_id}:*",
            f"activity:{activity_id}",
        ]
    else:
        patterns = [
            f"activities:{athlete_id}:*",
            f"efficiency_trends:{athlete_id}:*",
        ]
    
    total_deleted = 0
    for pattern in patterns:
        total_deleted += invalidate_pattern(pattern)
    
    return total_deleted


def invalidate_correlation_cache(athlete_id: str):
    """Invalidate correlation cache entries."""
    patterns = [
        f"correlations:*:{athlete_id}:*",
        f"correlations:{athlete_id}:*",
    ]
    
    total_deleted = 0
    for pattern in patterns:
        total_deleted += invalidate_pattern(pattern)
    
    return total_deleted


