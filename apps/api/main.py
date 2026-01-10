"""
FastAPI application entry point.

This module sets up the FastAPI application with all middleware,
routers, and configuration for production use.
"""
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from routers import v1, strava, strava_webhook, feedback, body_composition, nutrition, work_pattern, auth, activity_analysis, activity_feedback, training_availability, run_delivery, activities, analytics, correlations, insight_feedback, recovery_metrics, daily_checkin, admin, run_analysis, training_load, population_insights, athlete_profile, training_plans, ai_coach, preferences, compare, activity_workout_type, athlete_insights, contextual_compare, attribution, causal, data_export
try:
    from routers import garmin
    GARMIN_AVAILABLE = True
except ImportError:
    GARMIN_AVAILABLE = False
from core.config import settings
from core.database import check_db_connection
from core.logging import setup_logging
from core.exceptions import APIException
from core.rate_limit import RateLimitMiddleware
from core.security_headers import SecurityHeadersMiddleware
import logging
import time

# Setup logging first
setup_logging()
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Performance Physics Engine API",
    description="Complete health and fitness management system with correlation analysis and run delivery",
    version="3.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# CORS middleware
# Allow localhost origins for development, or all origins if DEBUG is True
allowed_origins = (
    ["*"] if settings.DEBUG 
    else [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security headers middleware (first in chain)
app.add_middleware(SecurityHeadersMiddleware)

# Rate limiting middleware (after CORS and security headers)
if settings.RATE_LIMIT_ENABLED:
    app.add_middleware(
        RateLimitMiddleware,
        default_limit=settings.RATE_LIMIT_PER_MINUTE,
        window=60  # 1 minute window
    )


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with timing information."""
    start_time = time.time()
    
    # Log request
    logger.info(
        f"Request: {request.method} {request.url.path}",
        extra={
            "extra_fields": {
                "method": request.method,
                "path": request.url.path,
                "client_ip": request.client.host if request.client else None,
            }
        }
    )
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Log response
        logger.info(
            f"Response: {request.method} {request.url.path} - {response.status_code}",
            extra={
                "extra_fields": {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "process_time_ms": round(process_time * 1000, 2),
                }
            }
        )
        
        # Add timing header
        response.headers["X-Process-Time"] = str(process_time)
        return response
    except Exception as e:
        logger.error(
            f"Request failed: {request.method} {request.url.path}",
            exc_info=True,
            extra={
                "extra_fields": {
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                }
            }
        )
        raise


# Error handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error(
        f"Unhandled exception: {exc}",
        exc_info=True,
        extra={
            "extra_fields": {
                "method": request.method,
                "path": request.url.path,
            }
        }
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


@app.get("/health")
async def health():
    """
    Health check endpoint.
    
    Returns:
        - 200: All systems healthy
        - 503: Service degraded (database unavailable)
    """
    db_healthy = check_db_connection()
    
    if not db_healthy:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "degraded",
                "database": "unavailable",
            }
        )
    
    return {
        "status": "ok",
        "database": "healthy",
        "version": "1.0.0",
    }


# Include routers
app.include_router(auth.router)
app.include_router(v1.router)
app.include_router(strava.router)
app.include_router(strava_webhook.router)
app.include_router(feedback.router)
app.include_router(body_composition.router)
app.include_router(nutrition.router)
app.include_router(work_pattern.router)
app.include_router(activity_analysis.router)
app.include_router(activity_feedback.router)
app.include_router(training_availability.router)
app.include_router(run_delivery.router)
app.include_router(activities.router)
app.include_router(analytics.router)
app.include_router(correlations.router)
app.include_router(insight_feedback.router)
app.include_router(recovery_metrics.router)
app.include_router(daily_checkin.router)
app.include_router(admin.router)
app.include_router(run_analysis.router)
app.include_router(training_load.router)
app.include_router(population_insights.router)
app.include_router(athlete_profile.router)
app.include_router(training_plans.router)
app.include_router(ai_coach.router)
app.include_router(preferences.router)
app.include_router(compare.router)
app.include_router(contextual_compare.router)
app.include_router(attribution.router)
app.include_router(causal.router)
app.include_router(data_export.router)
app.include_router(activity_workout_type.router)
app.include_router(athlete_insights.router)

# GDPR endpoints
try:
    from routers import gdpr
    app.include_router(gdpr.router)
except ImportError:
    pass  # GDPR router not available

# Public tools (free, no auth required)
try:
    from routers import public_tools
    app.include_router(public_tools.router)
except ImportError:
    pass  # Public tools router not available yet

# Garmin router (if available)
# TEMPORARILY DISABLED: Garmin username/password auth blocked by Garmin (Jan 2026)
# Will re-enable when official OAuth flow is implemented post-launch
# if GARMIN_AVAILABLE:
#     try:
#         app.include_router(garmin.router)
#     except Exception as e:
#         logger.warning(f"Could not include Garmin router: {e}")

# VDOT Calculator (free tool)
try:
    from routers import vdot
    app.include_router(vdot.router)
except ImportError:
    pass  # VDOT router not available yet

# Knowledge Base Query API (Tier 3+)
try:
    from routers import knowledge
    app.include_router(knowledge.router)
except ImportError:
    pass  # Knowledge router not available yet


