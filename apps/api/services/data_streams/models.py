"""
Unified data models for external data streams.

These models normalize data from any platform into a consistent format
that can be stored and analyzed uniformly.

Design Principles:
- All fields are optional (different platforms provide different data)
- Platform-specific data preserved in `platform_specific_data`
- All models are dataclasses for easy serialization
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Any, Dict, List, Optional


@dataclass
class UnifiedActivityData:
    """
    Unified model for activities from any platform.
    
    Normalizes activity data from Strava, Garmin, Coros, etc.
    into a consistent format for storage and analysis.
    """
    
    # Source identification
    platform: str  # 'strava', 'garmin', 'coros', etc.
    external_activity_id: str  # Platform-specific ID
    
    # Core metrics
    activity_type: str = "run"  # 'run', 'cycle', 'swim', 'walk', etc.
    start_time: Optional[datetime] = None
    duration_s: Optional[int] = None
    distance_m: Optional[float] = None
    
    # Heart rate
    avg_hr: Optional[int] = None
    max_hr: Optional[int] = None
    
    # Pace/Speed
    average_speed: Optional[float] = None  # m/s
    max_speed: Optional[float] = None  # m/s
    
    # Cadence
    avg_cadence: Optional[float] = None
    
    # Elevation
    total_elevation_gain: Optional[float] = None  # meters
    total_elevation_loss: Optional[float] = None  # meters
    
    # Splits/Laps
    splits: List[Dict[str, Any]] = field(default_factory=list)
    
    # Activity streams (second-by-second data)
    has_streams: bool = False
    streams: Optional[Dict[str, List[Any]]] = None  # 'heartrate', 'distance', 'altitude', 'grade_smooth'
    
    # Weather (if available)
    temperature_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    wind_speed_mps: Optional[float] = None
    
    # Classification
    is_race_candidate: bool = False
    race_confidence: Optional[float] = None
    terrain: Optional[str] = None  # 'road', 'trail', 'track', 'treadmill'
    
    # Platform-specific raw data (for debugging/future use)
    platform_specific_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            'platform': self.platform,
            'external_activity_id': self.external_activity_id,
            'activity_type': self.activity_type,
            'start_time': self.start_time,
            'duration_s': self.duration_s,
            'distance_m': self.distance_m,
            'avg_hr': self.avg_hr,
            'max_hr': self.max_hr,
            'average_speed': self.average_speed,
            'max_speed': self.max_speed,
            'avg_cadence': self.avg_cadence,
            'total_elevation_gain': self.total_elevation_gain,
            'total_elevation_loss': self.total_elevation_loss,
            'splits': self.splits,
            'has_streams': self.has_streams,
            'temperature_c': self.temperature_c,
            'humidity_pct': self.humidity_pct,
            'wind_speed_mps': self.wind_speed_mps,
            'is_race_candidate': self.is_race_candidate,
            'race_confidence': self.race_confidence,
            'terrain': self.terrain,
            'platform_specific_data': self.platform_specific_data,
        }


@dataclass
class UnifiedRecoveryData:
    """
    Unified model for recovery/wellness data from any platform.
    
    Normalizes data from Garmin, Apple Health, Whoop, Oura, etc.
    into a consistent format for correlation analysis.
    
    Key insight: Recovery data is essential for the correlation engine.
    Sleep → efficiency, HRV → performance, etc.
    """
    
    # Source identification
    platform: str  # 'garmin', 'apple_health', 'whoop', 'oura', etc.
    date: date
    
    # Sleep metrics
    sleep_hours: Optional[float] = None
    sleep_quality: Optional[float] = None  # 0-100 scale
    deep_sleep_hours: Optional[float] = None
    rem_sleep_hours: Optional[float] = None
    light_sleep_hours: Optional[float] = None
    awake_time_hours: Optional[float] = None
    sleep_score: Optional[float] = None  # Platform-specific score (0-100)
    
    # Heart rate variability
    hrv_rmssd: Optional[float] = None
    hrv_sdnn: Optional[float] = None
    hrv_score: Optional[float] = None  # Platform-specific score (0-100)
    
    # Heart rate
    resting_hr: Optional[int] = None
    overnight_avg_hr: Optional[float] = None
    overnight_min_hr: Optional[int] = None
    
    # Respiratory
    respiratory_rate: Optional[float] = None  # breaths per minute
    spo2: Optional[float] = None  # Blood oxygen %
    
    # Recovery scores (platform-specific)
    recovery_score: Optional[float] = None  # 0-100 scale
    readiness_score: Optional[float] = None  # Oura-style (0-100)
    strain_score: Optional[float] = None  # Whoop-style
    body_battery: Optional[float] = None  # Garmin-style (0-100)
    
    # Stress
    stress_score: Optional[float] = None  # 0-100 scale
    stress_level: Optional[int] = None  # 1-5 scale (our internal)
    
    # Platform-specific raw data
    platform_specific_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            'platform': self.platform,
            'date': self.date,
            'sleep_hours': self.sleep_hours,
            'sleep_quality': self.sleep_quality,
            'deep_sleep_hours': self.deep_sleep_hours,
            'rem_sleep_hours': self.rem_sleep_hours,
            'light_sleep_hours': self.light_sleep_hours,
            'awake_time_hours': self.awake_time_hours,
            'sleep_score': self.sleep_score,
            'hrv_rmssd': self.hrv_rmssd,
            'hrv_sdnn': self.hrv_sdnn,
            'hrv_score': self.hrv_score,
            'resting_hr': self.resting_hr,
            'overnight_avg_hr': self.overnight_avg_hr,
            'overnight_min_hr': self.overnight_min_hr,
            'respiratory_rate': self.respiratory_rate,
            'spo2': self.spo2,
            'recovery_score': self.recovery_score,
            'readiness_score': self.readiness_score,
            'strain_score': self.strain_score,
            'body_battery': self.body_battery,
            'stress_score': self.stress_score,
            'stress_level': self.stress_level,
            'platform_specific_data': self.platform_specific_data,
        }
    
    def to_daily_checkin_dict(self) -> Dict[str, Any]:
        """
        Convert to DailyCheckin model format for storage.
        
        This allows recovery data from any platform to be stored
        in our existing DailyCheckin table for correlation analysis.
        """
        return {
            'date': self.date,
            'sleep_h': self.sleep_hours,
            'hrv_rmssd': self.hrv_rmssd,
            'hrv_sdnn': self.hrv_sdnn,
            'resting_hr': self.resting_hr,
            'overnight_avg_hr': self.overnight_avg_hr,
            'stress_1_5': self.stress_level,
        }


@dataclass
class UnifiedNutritionData:
    """
    Unified model for nutrition data from any platform.
    
    Normalizes data from MyFitnessPal, Cronometer, Lose It, etc.
    into a consistent format for correlation analysis.
    
    Key insight: Nutrition timing relative to activities is critical
    for discovering personal response curves.
    """
    
    # Source identification
    platform: str  # 'myfitnesspal', 'cronometer', 'loseit', etc.
    date: date
    
    # Entry type (matches our NutritionEntry model)
    entry_type: str = "daily"  # 'daily', 'pre_activity', 'during_activity', 'post_activity'
    
    # Core macros
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    fiber_g: Optional[float] = None
    
    # Micronutrients (optional, for advanced users)
    sodium_mg: Optional[float] = None
    potassium_mg: Optional[float] = None
    iron_mg: Optional[float] = None
    vitamin_d_iu: Optional[float] = None
    calcium_mg: Optional[float] = None
    
    # Hydration
    water_ml: Optional[float] = None
    
    # Meal details
    meal_type: Optional[str] = None  # 'breakfast', 'lunch', 'dinner', 'snack'
    meal_time: Optional[datetime] = None
    
    # Activity linking (for pre/during/post)
    activity_id: Optional[str] = None  # Our internal activity ID
    timing_relative_to_activity: Optional[str] = None  # 'pre', 'during', 'post'
    minutes_before_activity: Optional[int] = None
    minutes_after_activity: Optional[int] = None
    
    # Notes
    notes: Optional[str] = None
    
    # Platform-specific raw data
    platform_specific_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            'platform': self.platform,
            'date': self.date,
            'entry_type': self.entry_type,
            'calories': self.calories,
            'protein_g': self.protein_g,
            'carbs_g': self.carbs_g,
            'fat_g': self.fat_g,
            'fiber_g': self.fiber_g,
            'sodium_mg': self.sodium_mg,
            'potassium_mg': self.potassium_mg,
            'iron_mg': self.iron_mg,
            'vitamin_d_iu': self.vitamin_d_iu,
            'calcium_mg': self.calcium_mg,
            'water_ml': self.water_ml,
            'meal_type': self.meal_type,
            'meal_time': self.meal_time,
            'activity_id': self.activity_id,
            'timing_relative_to_activity': self.timing_relative_to_activity,
            'minutes_before_activity': self.minutes_before_activity,
            'minutes_after_activity': self.minutes_after_activity,
            'notes': self.notes,
            'platform_specific_data': self.platform_specific_data,
        }
    
    def to_nutrition_entry_dict(self) -> Dict[str, Any]:
        """
        Convert to NutritionEntry model format for storage.
        
        This allows nutrition data from any platform to be stored
        in our existing NutritionEntry table for correlation analysis.
        """
        return {
            'date': self.date,
            'entry_type': self.entry_type,
            'activity_id': self.activity_id,
            'calories': self.calories,
            'protein_g': self.protein_g,
            'carbs_g': self.carbs_g,
            'fat_g': self.fat_g,
            'fiber_g': self.fiber_g,
            'timing': self.meal_time,
            'notes': self.notes,
        }


