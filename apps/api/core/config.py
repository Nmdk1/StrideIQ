"""
Centralized configuration management with validation.

All environment variables are loaded and validated here.
This ensures consistent configuration across the application.
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application settings with validation."""
    
    # Database Configuration
    POSTGRES_USER: str = Field(default="postgres", env="POSTGRES_USER")
    POSTGRES_PASSWORD: str = Field(default="postgres", env="POSTGRES_PASSWORD")
    POSTGRES_DB: str = Field(default="running_app", env="POSTGRES_DB")
    POSTGRES_HOST: str = Field(default="postgres", env="POSTGRES_HOST")
    POSTGRES_PORT: int = Field(default=5432, env="POSTGRES_PORT")
    
    # Database Pool Configuration
    DB_POOL_SIZE: int = Field(default=20, env="DB_POOL_SIZE")
    DB_MAX_OVERFLOW: int = Field(default=10, env="DB_MAX_OVERFLOW")
    DB_POOL_TIMEOUT: int = Field(default=30, env="DB_POOL_TIMEOUT")
    DB_POOL_RECYCLE: int = Field(default=3600, env="DB_POOL_RECYCLE")  # 1 hour
    
    # Redis Configuration
    REDIS_URL: str = Field(default="redis://redis:6379/0", env="REDIS_URL")
    
    # Strava API Configuration
    STRAVA_CLIENT_ID: Optional[str] = Field(default=None, env="STRAVA_CLIENT_ID")
    STRAVA_CLIENT_SECRET: Optional[str] = Field(default=None, env="STRAVA_CLIENT_SECRET")
    STRAVA_REDIRECT_URI: Optional[str] = Field(default=None, env="STRAVA_REDIRECT_URI")
    STRAVA_WEBHOOK_VERIFY_TOKEN: Optional[str] = Field(default=None, env="STRAVA_WEBHOOK_VERIFY_TOKEN")
    
    # Token Encryption
    TOKEN_ENCRYPTION_KEY: Optional[str] = Field(default=None, env="TOKEN_ENCRYPTION_KEY")
    
    # JWT Authentication
    SECRET_KEY: Optional[str] = Field(default=None, env="SECRET_KEY")
    
    # Garmin Configuration (for future official API)
    GARMIN_CLIENT_ID: Optional[str] = Field(default=None, env="GARMIN_CLIENT_ID")
    GARMIN_CLIENT_SECRET: Optional[str] = Field(default=None, env="GARMIN_CLIENT_SECRET")
    
    # API Configuration
    API_HOST: str = Field(default="0.0.0.0", env="API_HOST")
    API_PORT: int = Field(default=8000, env="API_PORT")
    API_RELOAD: bool = Field(default=False, env="API_RELOAD")
    
    # Logging Configuration
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(default="json", env="LOG_FORMAT")  # json or text
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(default=True, env="RATE_LIMIT_ENABLED")
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, env="RATE_LIMIT_PER_MINUTE")
    
    # External API Configuration
    EXTERNAL_API_TIMEOUT: int = Field(default=30, env="EXTERNAL_API_TIMEOUT")
    EXTERNAL_API_RETRY_ATTEMPTS: int = Field(default=3, env="EXTERNAL_API_RETRY_ATTEMPTS")
    
    # Celery Configuration
    CELERY_BROKER_URL: str = Field(default="redis://redis:6379/0", env="CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND: str = Field(default="redis://redis:6379/0", env="CELERY_RESULT_BACKEND")
    
    # Email Configuration
    EMAIL_ENABLED: bool = Field(default=False, env="EMAIL_ENABLED")
    SMTP_SERVER: str = Field(default="localhost", env="SMTP_SERVER")
    SMTP_PORT: int = Field(default=587, env="SMTP_PORT")
    SMTP_USERNAME: Optional[str] = Field(default=None, env="SMTP_USERNAME")
    SMTP_PASSWORD: Optional[str] = Field(default=None, env="SMTP_PASSWORD")
    FROM_EMAIL: str = Field(default="noreply@performancefocused.com", env="FROM_EMAIL")
    FROM_NAME: str = Field(default="Performance Focused", env="FROM_NAME")
    
    # Cache Configuration
    CACHE_TTL_DEFAULT: int = Field(default=300, env="CACHE_TTL_DEFAULT")  # 5 minutes
    CACHE_TTL_ATHLETE: int = Field(default=600, env="CACHE_TTL_ATHLETE")  # 10 minutes
    CACHE_TTL_ACTIVITIES: int = Field(default=60, env="CACHE_TTL_ACTIVITIES")  # 1 minute
    
    # Environment
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    DEBUG: bool = Field(default=False, env="DEBUG")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()

