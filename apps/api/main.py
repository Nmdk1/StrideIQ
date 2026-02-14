"""
FastAPI application entry point.

This module sets up the FastAPI application with all middleware,
routers, and configuration for production use.
"""
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from routers import v1, strava, strava_webhook, feedback, body_composition, nutrition, work_pattern, auth, activity_analysis, activity_feedback, training_availability, run_delivery, activities, analytics, correlations, insight_feedback, recovery_metrics, daily_checkin, admin, run_analysis, training_load, population_insights, athlete_profile, training_plans, ai_coach, coach_actions, preferences, compare, activity_workout_type, athlete_insights, contextual_compare, attribution, causal, data_export, calendar, insights, diagnostics, plan_generation, home, plan_export, onboarding, billing, progress, daily_intelligence, stream_analysis
from routers import imports as provider_imports
try:
    from routers import garmin
    GARMIN_AVAILABLE = True
except ImportError:
    GARMIN_AVAILABLE = False
from core.config import settings
from core.database import check_db_connection
from core.database import engine
from core.logging import setup_logging
from core.exceptions import APIException
from core.rate_limit import RateLimitMiddleware
from core.security_headers import SecurityHeadersMiddleware
import logging
import time
import os
from sqlalchemy import text

# Setup logging first
setup_logging()
logger = logging.getLogger(__name__)

# Initialize Sentry for error tracking (production)
if settings.SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.redis import RedisIntegration
        
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            profiles_sample_rate=settings.SENTRY_PROFILES_SAMPLE_RATE,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                RedisIntegration(),
            ],
            # Don't send PII
            send_default_pii=False,
            # Filter sensitive data
            before_send=lambda event, hint: _filter_sensitive_data(event),
        )
        logger.info(f"Sentry initialized for environment: {settings.ENVIRONMENT}")
    except ImportError:
        logger.warning("sentry-sdk not installed, error tracking disabled")
    except Exception as e:
        logger.error(f"Failed to initialize Sentry: {e}")


def _filter_sensitive_data(event):
    """Filter sensitive data before sending to Sentry."""
    # Remove Authorization headers
    if "request" in event and "headers" in event["request"]:
        headers = event["request"]["headers"]
        if isinstance(headers, dict):
            headers.pop("authorization", None)
            headers.pop("cookie", None)
    return event

# Create FastAPI app
app = FastAPI(
    title="Performance Physics Engine API",
    description="Complete health and fitness management system with correlation analysis and run delivery",
    version="3.0.0",
    docs_url="/docs" if (settings.DEBUG or settings.EXPOSE_API_DOCS) else None,
    redoc_url="/redoc" if (settings.DEBUG or settings.EXPOSE_API_DOCS) else None,
)


@app.on_event("startup")
async def backfill_missing_rpi():
    """Backfill RPI for athletes who have PBs but missing RPI."""
    try:
        from database import SessionLocal
        from services.personal_best import backfill_rpi_from_pbs
        
        db = SessionLocal()
        try:
            result = backfill_rpi_from_pbs(db)
            if result['updated'] > 0:
                logger.info(f"RPI backfill complete: {result}")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"RPI backfill failed (non-critical): {e}")


# CORS middleware
# Production: set CORS_ORIGINS env var (comma-separated)
# Development: DEBUG=True allows all origins
if settings.DEBUG:
    allowed_origins = ["*"]
    allow_origin_regex = None
elif settings.CORS_ORIGINS:
    # Production - use configured origins
    allowed_origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",")]
    allow_origin_regex = None
else:
    # Fallback for local development
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://10.0.0.137:3000",  # Home network access
    ]
    # When running in non-prod, allow other LAN origins without hardcoding the IP.
    # (e.g. your dad hits http://<your-ip>:3000 from his machine)
    allow_origin_regex = None
    if settings.ENVIRONMENT != "production":
        allow_origin_regex = r"^http://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+)(:\d+)?$"
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=allow_origin_regex,
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
    Simple health check for load balancers and uptime monitors.
    
    Returns:
        - 200: Core systems operational
        - 503: Critical dependency unavailable
    """
    db_healthy = check_db_connection()
    
    if not db_healthy:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "unavailable",
            }
        )
    
    return {
        "status": "healthy",
        "timestamp": time.time(),
    }


@app.get("/health/detailed")
async def health_detailed():
    """
    Detailed health check for monitoring dashboards.
    
    Checks all dependencies and returns comprehensive status.
    Not for load balancers (always returns 200).
    """
    from core.cache import get_redis_client
    
    checks = {
        "database": {"status": "unknown", "latency_ms": None},
        "redis": {"status": "unknown", "latency_ms": None},
    }
    
    # Check database
    start = time.time()
    try:
        db_healthy = check_db_connection()
        checks["database"]["status"] = "healthy" if db_healthy else "unhealthy"
        checks["database"]["latency_ms"] = round((time.time() - start) * 1000, 2)
    except Exception as e:
        checks["database"]["status"] = "error"
        checks["database"]["error"] = str(e)
    
    # Check Redis
    start = time.time()
    try:
        redis = get_redis_client()
        if redis:
            redis.ping()
            checks["redis"]["status"] = "healthy"
        else:
            checks["redis"]["status"] = "unavailable"
        checks["redis"]["latency_ms"] = round((time.time() - start) * 1000, 2)
    except Exception as e:
        checks["redis"]["status"] = "error"
        checks["redis"]["error"] = str(e)
    
    # Overall status
    all_healthy = all(c["status"] == "healthy" for c in checks.values())
    any_error = any(c["status"] == "error" for c in checks.values())
    
    return {
        "status": "healthy" if all_healthy else ("degraded" if not any_error else "unhealthy"),
        "version": "3.0.0",
        "environment": settings.ENVIRONMENT,
        "timestamp": time.time(),
        "checks": checks,
    }


@app.get("/ping")
async def ping():
    """
    Minimal ping endpoint for uptime monitors.
    No dependencies checked - just confirms the API is responding.
    """
    return {"pong": True}


@app.get("/debug")
async def debug(request: Request):
    """
    Production-safe debug endpoint.

    - Disabled by default (returns 404 unless DEBUG_ENDPOINT_TOKEN is set)
    - When enabled, requires header: X-Debug-Token == settings.DEBUG_ENDPOINT_TOKEN
    - Returns DB connectivity + alembic version state to diagnose startup/migration issues.
    """
    token = settings.DEBUG_ENDPOINT_TOKEN
    if not token:
        return JSONResponse(status_code=404, content={"detail": "Not found"})

    req_token = request.headers.get("x-debug-token")
    if not req_token or req_token != token:
        return JSONResponse(status_code=404, content={"detail": "Not found"})

    # Basic DB checks + migration version
    db_ok = False
    alembic_version = None
    feature_flag_exists = None
    error = None
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            db_ok = True
            try:
                alembic_version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            except Exception:
                alembic_version = None
            try:
                feature_flag_exists = bool(
                    conn.execute(
                        text(
                            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'feature_flag')"
                        )
                    ).scalar()
                )
            except Exception:
                feature_flag_exists = None
    except Exception as e:
        error = f"{type(e).__name__}: {e}"

    # Expected Alembic head (from repo)
    expected_head = None
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        here = os.path.dirname(os.path.abspath(__file__))
        cfg = Config(os.path.join(here, "alembic.ini"))
        script = ScriptDirectory.from_config(cfg)
        expected_head = script.get_current_head()
    except Exception:
        expected_head = None

    return {
        "environment": settings.ENVIRONMENT,
        "db_ok": db_ok,
        "alembic_version": alembic_version,
        "expected_head": expected_head,
        "feature_flag_table_exists": feature_flag_exists,
        "error": error,
        "ts": time.time(),
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
app.include_router(stream_analysis.router)
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
app.include_router(calendar.router)
app.include_router(insights.router)
app.include_router(diagnostics.router)
app.include_router(plan_generation.router)
app.include_router(home.router)
app.include_router(plan_export.router)
app.include_router(onboarding.router)
app.include_router(coach_actions.router)
app.include_router(billing.router)
app.include_router(progress.router)
app.include_router(daily_intelligence.router)
app.include_router(provider_imports.router)

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

# RPI Calculator (free tool)
try:
    from routers import rpi
    app.include_router(rpi.router)
except ImportError:
    pass  # RPI router not available yet

# Knowledge Base Query API (Tier 3+)
try:
    from routers import knowledge
    app.include_router(knowledge.router)
except ImportError:
    pass  # Knowledge router not available yet


