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
    
    # Token Encryption
    TOKEN_ENCRYPTION_KEY: Optional[str] = Field(default=None)
    
    # JWT Authentication
    SECRET_KEY: Optional[str] = Field(default=None)
    
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
    
    # Sentry Error Tracking
    SENTRY_DSN: Optional[str] = Field(default=None)
    SENTRY_TRACES_SAMPLE_RATE: float = Field(default=0.1)  # 10% of transactions
    SENTRY_PROFILES_SAMPLE_RATE: float = Field(default=0.1)


# Global settings instance
settings = Settings()
