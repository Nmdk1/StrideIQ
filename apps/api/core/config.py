"""
Centralized configuration management with validation.

All environment variables are loaded and validated here.
This ensures consistent configuration across the application.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application settings with validation."""
    
    # Pydantic v2 configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )
    
    # Database Configuration
    POSTGRES_USER: str = Field(default="postgres")
    POSTGRES_PASSWORD: str = Field(default="postgres")
    POSTGRES_DB: str = Field(default="running_app")
    POSTGRES_HOST: str = Field(default="postgres")
    POSTGRES_PORT: int = Field(default=5432)
    
    # Database Pool Configuration
    DB_POOL_SIZE: int = Field(default=20)
    DB_MAX_OVERFLOW: int = Field(default=10)
    DB_POOL_TIMEOUT: int = Field(default=30)
    DB_POOL_RECYCLE: int = Field(default=3600)  # 1 hour
    
    # Redis Configuration
    REDIS_URL: str = Field(default="redis://redis:6379/0")
    
    # Strava API Configuration
    STRAVA_CLIENT_ID: Optional[str] = Field(default=None)
    STRAVA_CLIENT_SECRET: Optional[str] = Field(default=None)
    STRAVA_REDIRECT_URI: Optional[str] = Field(default=None)
    STRAVA_WEBHOOK_VERIFY_TOKEN: Optional[str] = Field(default=None)

    # Strava Ingestion Throttling (viral-safe scaling)
    # Caps concurrent Strava *detail* fetches across all workers.
    STRAVA_DETAIL_FETCH_CONCURRENCY: int = Field(default=4)
    # How long a worker will wait to acquire a detail-fetch slot before failing the attempt.
    STRAVA_DETAIL_FETCH_ACQUIRE_TIMEOUT_S: int = Field(default=60)
    # Poll interval while waiting for a slot.
    STRAVA_DETAIL_FETCH_ACQUIRE_POLL_S: float = Field(default=1.0)
    
    # Token Encryption
    TOKEN_ENCRYPTION_KEY: Optional[str] = Field(default=None)
    
    # JWT Authentication - REQUIRED for token signing
    # Must be set via environment variable, never use default in production
    SECRET_KEY: str = Field(
        default=...,  # Required - no default
        description="JWT signing key. Must be cryptographically secure (32+ chars). "
                    "Generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
    )
    
    # Garmin Configuration (for future official API)
    GARMIN_CLIENT_ID: Optional[str] = Field(default=None)
    GARMIN_CLIENT_SECRET: Optional[str] = Field(default=None)
    
    # API Configuration
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8000)
    API_RELOAD: bool = Field(default=False)
    
    # Logging Configuration
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FORMAT: str = Field(default="json")  # json or text
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(default=True)
    RATE_LIMIT_PER_MINUTE: int = Field(default=60)
    
    # External API Configuration
    EXTERNAL_API_TIMEOUT: int = Field(default=30)
    EXTERNAL_API_RETRY_ATTEMPTS: int = Field(default=3)
    
    # Celery Configuration
    CELERY_BROKER_URL: str = Field(default="redis://redis:6379/0")
    CELERY_RESULT_BACKEND: str = Field(default="redis://redis:6379/0")
    
    # Email Configuration
    EMAIL_ENABLED: bool = Field(default=False)
    SMTP_SERVER: str = Field(default="localhost")
    SMTP_PORT: int = Field(default=587)
    SMTP_USERNAME: Optional[str] = Field(default=None)
    SMTP_PASSWORD: Optional[str] = Field(default=None)
    FROM_EMAIL: str = Field(default="noreply@performancefocused.com")
    FROM_NAME: str = Field(default="Performance Focused")
    
    # Cache Configuration
    CACHE_TTL_DEFAULT: int = Field(default=300)  # 5 minutes
    CACHE_TTL_ATHLETE: int = Field(default=600)  # 10 minutes
    CACHE_TTL_ACTIVITIES: int = Field(default=60)  # 1 minute
    
    # Environment
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=False)
    
    # CORS - comma-separated list of allowed origins for production
    # e.g., "https://strideiq.run,https://www.strideiq.run"
    CORS_ORIGINS: Optional[str] = Field(default=None)

    # Web app base URL (for OAuth redirects back to the UI).
    # e.g., "http://localhost:3000" or "https://strideiq.run"
    WEB_APP_BASE_URL: str = Field(default="http://localhost:3000")

    # OAuth state TTL for provider callbacks (seconds).
    OAUTH_STATE_TTL_S: int = Field(default=600)

    # Impersonation (owner-only) controls
    # Short-lived tokens reduce blast radius if leaked.
    IMPERSONATION_TOKEN_TTL_MINUTES: int = Field(default=20, ge=5, le=120)

    # Stripe (Phase 6: hosted checkout/portal)
    STRIPE_SECRET_KEY: Optional[str] = Field(default=None)
    STRIPE_WEBHOOK_SECRET: Optional[str] = Field(default=None)
    STRIPE_PRICE_PRO_MONTHLY_ID: Optional[str] = Field(default=None)
    STRIPE_CHECKOUT_SUCCESS_URL: Optional[str] = Field(default=None)
    STRIPE_CHECKOUT_CANCEL_URL: Optional[str] = Field(default=None)
    STRIPE_PORTAL_RETURN_URL: Optional[str] = Field(default=None)
    
    # Sentry Error Tracking
    SENTRY_DSN: Optional[str] = Field(default=None)
    SENTRY_TRACES_SAMPLE_RATE: float = Field(default=0.1)  # 10% of transactions
    SENTRY_PROFILES_SAMPLE_RATE: float = Field(default=0.1)


# Global settings instance
settings = Settings()
