"""
BMI Configuration

Backend-configurable settings for BMI correlation analysis and display.
Allows adjustment of correlation thresholds and display logic without code changes.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class BMIConfig(BaseSettings):
    """
    Configurable BMI settings.
    
    These can be adjusted via environment variables or admin panel
    without requiring code changes.
    """
    # Minimum correlation coefficient to show BMI insights
    # Range: 0.0 to 1.0
    # Default: 0.3 (moderate correlation)
    min_correlation_threshold: float = 0.3
    
    # Minimum data points required before showing trend line
    # Default: 3 entries (need at least 3 points for a trend)
    min_data_points_for_trend: int = 3
    
    # Minimum days of data before showing trend line
    # Default: 7 days (one week)
    min_days_for_trend: int = 7
    
    # Enable BMI toggle by default (if False, toggle exists but default is OFF)
    # Default: False (user must opt-in)
    bmi_toggle_default_on: bool = False
    
    class Config:
        env_prefix = "BMI_"
        case_sensitive = False


# Global config instance
bmi_config = BMIConfig()


