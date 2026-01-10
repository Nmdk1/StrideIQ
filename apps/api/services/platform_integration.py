"""
Multi-Platform Integration Structure

This module provides the foundation for integrating data from multiple platforms:
- Strava (already integrated)
- Garmin (prepared for integration)
- Coros (prepared for integration)
- Apple Health (prepared for integration)
- Samsung Health (prepared for integration)

The structure ensures a unified data model regardless of source platform.
"""

from typing import Dict, Optional, List
from datetime import datetime
from enum import Enum


class Platform(str, Enum):
    """Supported platforms"""
    STRAVA = "strava"
    GARMIN = "garmin"
    COROS = "coros"
    APPLE_HEALTH = "apple_health"
    SAMSUNG_HEALTH = "samsung_health"


class ActivityType(str, Enum):
    """Activity types"""
    RUN = "run"
    CYCLE = "cycle"
    SWIM = "swim"
    WALK = "walk"
    OTHER = "other"


class UnifiedActivityData:
    """
    Unified data model for activities from any platform.
    
    This ensures all platforms are normalized to the same structure,
    making it easy to process and analyze activities regardless of source.
    """
    
    def __init__(
        self,
        platform: Platform,
        external_activity_id: str,
        activity_type: ActivityType,
        start_time: datetime,
        duration_s: Optional[int] = None,
        distance_m: Optional[float] = None,
        avg_hr: Optional[int] = None,
        max_hr: Optional[int] = None,
        avg_cadence: Optional[float] = None,
        total_elevation_gain: Optional[float] = None,
        average_speed: Optional[float] = None,
        splits: Optional[List[Dict]] = None,
        # Platform-specific fields
        platform_specific_data: Optional[Dict] = None,
    ):
        self.platform = platform
        self.external_activity_id = external_activity_id
        self.activity_type = activity_type
        self.start_time = start_time
        self.duration_s = duration_s
        self.distance_m = distance_m
        self.avg_hr = avg_hr
        self.max_hr = max_hr
        self.avg_cadence = avg_cadence
        self.total_elevation_gain = total_elevation_gain
        self.average_speed = average_speed
        self.splits = splits or []
        self.platform_specific_data = platform_specific_data or {}
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for database storage"""
        return {
            'platform': self.platform.value,
            'external_activity_id': self.external_activity_id,
            'activity_type': self.activity_type.value,
            'start_time': self.start_time,
            'duration_s': self.duration_s,
            'distance_m': self.distance_m,
            'avg_hr': self.avg_hr,
            'max_hr': self.max_hr,
            'avg_cadence': self.avg_cadence,
            'total_elevation_gain': self.total_elevation_gain,
            'average_speed': self.average_speed,
            'splits': self.splits,
            'platform_specific_data': self.platform_specific_data,
        }


class PlatformAdapter:
    """
    Base class for platform-specific adapters.
    
    Each platform (Garmin, Coros, etc.) will have its own adapter that
    converts platform-specific data formats to the unified model.
    """
    
    def __init__(self, platform: Platform):
        self.platform = platform
    
    def normalize_activity(self, raw_data: Dict) -> UnifiedActivityData:
        """
        Convert platform-specific activity data to unified format.
        
        This method must be implemented by each platform adapter.
        
        Args:
            raw_data: Raw activity data from the platform API
            
        Returns:
            UnifiedActivityData object
        """
        raise NotImplementedError("Subclasses must implement normalize_activity")
    
    def fetch_activities(self, access_token: str, after_timestamp: Optional[int] = None) -> List[Dict]:
        """
        Fetch activities from the platform API.
        
        Args:
            access_token: Platform-specific access token
            after_timestamp: Only fetch activities after this timestamp (Unix epoch)
            
        Returns:
            List of raw activity data dictionaries
        """
        raise NotImplementedError("Subclasses must implement fetch_activities")
    
    def fetch_activity_details(self, access_token: str, activity_id: str) -> Dict:
        """
        Fetch detailed activity data including splits/laps.
        
        Args:
            access_token: Platform-specific access token
            activity_id: Platform-specific activity ID
            
        Returns:
            Detailed activity data dictionary
        """
        raise NotImplementedError("Subclasses must implement fetch_activity_details")


# ============================================================================
# Platform-Specific Adapters (Placeholders - to be implemented)
# ============================================================================

class GarminAdapter(PlatformAdapter):
    """Garmin Connect adapter - placeholder for future implementation"""
    
    def __init__(self):
        super().__init__(Platform.GARMIN)
    
    def normalize_activity(self, raw_data: Dict) -> UnifiedActivityData:
        # TODO: Implement Garmin-specific normalization
        # Garmin data may include: running dynamics, cycling power, advanced metrics
        raise NotImplementedError("Garmin adapter not yet implemented")
    
    def fetch_activities(self, access_token: str, after_timestamp: Optional[int] = None) -> List[Dict]:
        raise NotImplementedError("Garmin adapter not yet implemented")
    
    def fetch_activity_details(self, access_token: str, activity_id: str) -> Dict:
        raise NotImplementedError("Garmin adapter not yet implemented")


class CorosAdapter(PlatformAdapter):
    """Coros adapter - placeholder for future implementation"""
    
    def __init__(self):
        super().__init__(Platform.COROS)
    
    def normalize_activity(self, raw_data: Dict) -> UnifiedActivityData:
        # TODO: Implement Coros-specific normalization
        raise NotImplementedError("Coros adapter not yet implemented")
    
    def fetch_activities(self, access_token: str, after_timestamp: Optional[int] = None) -> List[Dict]:
        raise NotImplementedError("Coros adapter not yet implemented")
    
    def fetch_activity_details(self, access_token: str, activity_id: str) -> Dict:
        raise NotImplementedError("Coros adapter not yet implemented")


class AppleHealthAdapter(PlatformAdapter):
    """Apple Health adapter - placeholder for future implementation"""
    
    def __init__(self):
        super().__init__(Platform.APPLE_HEALTH)
    
    def normalize_activity(self, raw_data: Dict) -> UnifiedActivityData:
        # TODO: Implement Apple Health-specific normalization
        # Apple Health provides: HRV, sleep, wellness metrics
        raise NotImplementedError("Apple Health adapter not yet implemented")
    
    def fetch_activities(self, access_token: str, after_timestamp: Optional[int] = None) -> List[Dict]:
        raise NotImplementedError("Apple Health adapter not yet implemented")
    
    def fetch_activity_details(self, access_token: str, activity_id: str) -> Dict:
        raise NotImplementedError("Apple Health adapter not yet implemented")


class SamsungHealthAdapter(PlatformAdapter):
    """Samsung Health adapter - placeholder for future implementation"""
    
    def __init__(self):
        super().__init__(Platform.SAMSUNG_HEALTH)
    
    def normalize_activity(self, raw_data: Dict) -> UnifiedActivityData:
        # TODO: Implement Samsung Health-specific normalization
        raise NotImplementedError("Samsung Health adapter not yet implemented")
    
    def fetch_activities(self, access_token: str, after_timestamp: Optional[int] = None) -> List[Dict]:
        raise NotImplementedError("Samsung Health adapter not yet implemented")
    
    def fetch_activity_details(self, access_token: str, activity_id: str) -> Dict:
        raise NotImplementedError("Samsung Health adapter not yet implemented")


# ============================================================================
# Platform Registry
# ============================================================================

PLATFORM_ADAPTERS: Dict[Platform, PlatformAdapter] = {
    Platform.GARMIN: GarminAdapter(),
    Platform.COROS: CorosAdapter(),
    Platform.APPLE_HEALTH: AppleHealthAdapter(),
    Platform.SAMSUNG_HEALTH: SamsungHealthAdapter(),
}


def get_platform_adapter(platform: Platform) -> Optional[PlatformAdapter]:
    """Get the adapter for a specific platform"""
    return PLATFORM_ADAPTERS.get(platform)


