"""
Rate Limiting Middleware

Implements token bucket algorithm for rate limiting.
Per-user and per-endpoint limits.
"""
import time
import logging
from typing import Optional, Dict, Tuple
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from core.config import settings
from core.cache import get_redis_client

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using token bucket algorithm."""
    
    def __init__(self, app, default_limit: int = 60, window: int = 60):
        super().__init__(app)
        self.default_limit = default_limit
        self.window = window  # Time window in seconds
        
        # Per-endpoint limits (requests per window)
        self.endpoint_limits = {
            "/v1/correlations/discover": 10,  # 10 per hour
            "/v1/correlations/what-works": 10,
            "/v1/correlations/what-doesnt-work": 10,
            "/v1/admin": 50,  # Admin endpoints: 50 per minute
            "/v1/analytics/efficiency-trends": 30,  # 30 per minute
        }
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting if disabled
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)
        
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/docs", "/openapi.json", "/redoc"]:
            return await call_next(request)
        
        # Get user identifier (from auth token or IP)
        user_id = self._get_user_id(request)
        
        # Get endpoint limit
        limit = self._get_endpoint_limit(request.url.path)
        
        # Check rate limit
        allowed, remaining, reset_time = self._check_rate_limit(
            user_id=user_id,
            endpoint=request.url.path,
            limit=limit,
            window=self.window
        )
        
        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Rate limit exceeded",
                    "limit": limit,
                    "window": self.window,
                    "reset_at": reset_time
                },
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": str(remaining),
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(int(reset_time - time.time()))
                }
            )
        
        # Add rate limit headers to response
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        
        return response
    
    def _get_user_id(self, request: Request) -> str:
        """Get user identifier from request (user ID or IP address)."""
        # Try to extract user ID from Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                from core.security import decode_access_token
                payload = decode_access_token(token)
                if payload and payload.get("sub"):
                    return f"user:{payload.get('sub')}"
            except Exception:
                # Token invalid or expired - fall through to IP
                pass
        
        # Fall back to IP address
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"
    
    def _get_endpoint_limit(self, path: str) -> int:
        """Get rate limit for endpoint."""
        # Check exact match first
        if path in self.endpoint_limits:
            return self.endpoint_limits[path]
        
        # Check prefix matches
        for endpoint, limit in self.endpoint_limits.items():
            if path.startswith(endpoint):
                return limit
        
        # Default limit
        return self.default_limit
    
    def _check_rate_limit(
        self,
        user_id: str,
        endpoint: str,
        limit: int,
        window: int
    ) -> Tuple[bool, int, int]:
        """
        Check rate limit using token bucket algorithm.
        
        Returns:
            (allowed, remaining, reset_time)
        """
        redis_client = get_redis_client()
        
        if not redis_client:
            # If Redis unavailable, allow request (graceful degradation)
            logger.warning("Redis unavailable, skipping rate limit check")
            return True, limit, int(time.time()) + window
        
        # Create key: rate_limit:{user_id}:{endpoint}
        key = f"rate_limit:{user_id}:{endpoint}"
        
        try:
            # Get current count
            current = redis_client.get(key)
            
            if current is None:
                # First request - initialize bucket
                redis_client.setex(key, window, 1)
                return True, limit - 1, int(time.time()) + window
            
            current_count = int(current)
            
            if current_count >= limit:
                # Rate limit exceeded
                ttl = redis_client.ttl(key)
                reset_time = int(time.time()) + (ttl if ttl > 0 else window)
                return False, 0, reset_time
            
            # Increment counter
            new_count = redis_client.incr(key)
            
            # Set expiry if this is the first increment after expiry
            if new_count == 1:
                redis_client.expire(key, window)
            
            remaining = max(0, limit - new_count)
            ttl = redis_client.ttl(key)
            reset_time = int(time.time()) + (ttl if ttl > 0 else window)
            
            return True, remaining, reset_time
            
        except Exception as e:
            # On error, allow request (fail open)
            logger.error(f"Rate limit check error: {e}")
            return True, limit, int(time.time()) + window

