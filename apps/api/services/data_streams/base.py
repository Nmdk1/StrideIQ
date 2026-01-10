"""
Base classes for data stream adapters.

All external integrations (Strava, Garmin, MyFitnessPal, etc.) implement
these interfaces to provide a consistent API for:
- Connection management
- Data synchronization
- Webhook handling
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class DataStreamType(str, Enum):
    """Types of data streams."""
    ACTIVITY = "activity"      # Running, cycling, swimming activities
    RECOVERY = "recovery"      # Sleep, HRV, recovery metrics
    NUTRITION = "nutrition"    # Food, macros, calories
    BODY_COMP = "body_comp"   # Weight, body fat, measurements


class ConnectionStatus(str, Enum):
    """Status of a platform connection."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    PENDING = "pending"        # OAuth in progress
    ERROR = "error"           # Connection failed
    EXPIRED = "expired"       # Token expired, needs refresh


@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    items_synced: int = 0
    items_failed: int = 0
    errors: List[str] = None
    last_sync_time: Optional[datetime] = None
    next_sync_available: Optional[datetime] = None  # For rate limiting
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class DataStreamAdapter(ABC):
    """
    Base class for all external data integrations.
    
    Each platform (Strava, Garmin, MyFitnessPal, etc.) implements this interface.
    This allows the core system to work with any data source uniformly.
    
    Implementation Requirements:
    - All methods must handle failures gracefully (no crashes)
    - Rate limits must be respected
    - Credentials must be encrypted
    - Logging should be verbose for debugging
    """
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """
        Return unique platform identifier.
        
        Examples: 'strava', 'garmin', 'myfitnesspal', 'apple_health'
        Must be lowercase, no spaces.
        """
        pass
    
    @property
    @abstractmethod
    def display_name(self) -> str:
        """
        Return human-readable platform name.
        
        Examples: 'Strava', 'Garmin Connect', 'MyFitnessPal'
        """
        pass
    
    @property
    @abstractmethod
    def stream_type(self) -> DataStreamType:
        """
        Return primary type of data this adapter provides.
        
        Note: Some adapters may provide multiple types (e.g., Garmin provides
        both activity and recovery data). The primary type is the main one.
        """
        pass
    
    @property
    def secondary_stream_types(self) -> List[DataStreamType]:
        """
        Return additional data types this adapter can provide.
        
        Override if adapter provides multiple data types.
        Default: empty list.
        """
        return []
    
    @property
    def requires_oauth(self) -> bool:
        """
        Return True if this platform uses OAuth for authentication.
        
        If False, assumes username/password or API key auth.
        Default: True (most platforms use OAuth).
        """
        return True
    
    @property
    def supports_webhooks(self) -> bool:
        """
        Return True if this platform supports webhooks for real-time updates.
        
        If False, sync must be triggered manually or on schedule.
        Default: False.
        """
        return False
    
    @abstractmethod
    def get_auth_url(self, state: str) -> str:
        """
        Get OAuth authorization URL.
        
        Args:
            state: State parameter for CSRF protection
            
        Returns:
            URL to redirect user for OAuth authorization
            
        Raises:
            NotImplementedError: If platform doesn't use OAuth
        """
        pass
    
    @abstractmethod
    def exchange_code(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.
        
        Args:
            code: Authorization code from OAuth callback
            
        Returns:
            Dict containing access_token, refresh_token, expires_at, etc.
            
        Raises:
            Exception: If token exchange fails
        """
        pass
    
    @abstractmethod
    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh an expired access token.
        
        Args:
            refresh_token: The refresh token
            
        Returns:
            Dict containing new access_token, refresh_token, expires_at
            
        Raises:
            Exception: If refresh fails (may require re-authorization)
        """
        pass
    
    @abstractmethod
    def get_connection_status(self, athlete_id: str) -> ConnectionStatus:
        """
        Check the status of an athlete's connection to this platform.
        
        Args:
            athlete_id: The athlete's UUID
            
        Returns:
            ConnectionStatus enum value
        """
        pass
    
    @abstractmethod
    def sync(
        self,
        athlete_id: str,
        credentials: Dict[str, Any],
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> SyncResult:
        """
        Sync data from this platform for an athlete.
        
        Args:
            athlete_id: The athlete's UUID
            credentials: Decrypted credentials (access_token, etc.)
            since: Only sync data after this time (optional)
            limit: Maximum items to sync
            
        Returns:
            SyncResult with sync statistics
        """
        pass
    
    def handle_webhook(self, payload: Dict[str, Any]) -> bool:
        """
        Handle a webhook notification from this platform.
        
        Args:
            payload: The webhook payload
            
        Returns:
            True if handled successfully, False otherwise
            
        Default implementation logs and returns False.
        Override if platform supports webhooks.
        """
        logger.warning(f"{self.platform_name}: Webhook received but not implemented")
        return False
    
    def disconnect(self, athlete_id: str) -> bool:
        """
        Disconnect an athlete from this platform.
        
        This should:
        1. Revoke tokens if possible
        2. Clear stored credentials
        3. Update connection status
        
        Args:
            athlete_id: The athlete's UUID
            
        Returns:
            True if disconnected successfully
        """
        # Default implementation - subclasses may override
        logger.info(f"{self.platform_name}: Disconnecting athlete {athlete_id}")
        return True


class ActivityStreamAdapter(DataStreamAdapter):
    """
    Specialized adapter for activity platforms (Strava, Garmin, Coros, etc.).
    
    Provides additional methods specific to activity data.
    """
    
    @property
    def stream_type(self) -> DataStreamType:
        return DataStreamType.ACTIVITY
    
    @abstractmethod
    def get_activity_details(
        self,
        credentials: Dict[str, Any],
        activity_id: str
    ) -> Dict[str, Any]:
        """
        Get detailed activity data including splits/laps.
        
        Args:
            credentials: Decrypted credentials
            activity_id: Platform-specific activity ID
            
        Returns:
            Dict with activity details and splits
        """
        pass
    
    @abstractmethod
    def get_activity_streams(
        self,
        credentials: Dict[str, Any],
        activity_id: str,
        stream_types: List[str]
    ) -> Dict[str, List[Any]]:
        """
        Get detailed activity streams (second-by-second data).
        
        Args:
            credentials: Decrypted credentials
            activity_id: Platform-specific activity ID
            stream_types: Types of streams to fetch (e.g., ['heartrate', 'distance', 'altitude'])
            
        Returns:
            Dict mapping stream type to list of values
        """
        pass


class RecoveryStreamAdapter(DataStreamAdapter):
    """
    Specialized adapter for recovery/wellness platforms (Apple Health, Oura, Whoop).
    
    Provides additional methods specific to recovery data.
    """
    
    @property
    def stream_type(self) -> DataStreamType:
        return DataStreamType.RECOVERY
    
    @abstractmethod
    def get_sleep_data(
        self,
        credentials: Dict[str, Any],
        date: datetime
    ) -> Optional[Dict[str, Any]]:
        """
        Get sleep data for a specific date.
        
        Args:
            credentials: Decrypted credentials
            date: Date to fetch sleep data for
            
        Returns:
            Dict with sleep metrics or None if no data
        """
        pass
    
    @abstractmethod
    def get_hrv_data(
        self,
        credentials: Dict[str, Any],
        date: datetime
    ) -> Optional[Dict[str, Any]]:
        """
        Get HRV data for a specific date.
        
        Args:
            credentials: Decrypted credentials
            date: Date to fetch HRV data for
            
        Returns:
            Dict with HRV metrics or None if no data
        """
        pass


class NutritionStreamAdapter(DataStreamAdapter):
    """
    Specialized adapter for nutrition apps (MyFitnessPal, Cronometer).
    
    Provides additional methods specific to nutrition data.
    """
    
    @property
    def stream_type(self) -> DataStreamType:
        return DataStreamType.NUTRITION
    
    @abstractmethod
    def get_daily_nutrition(
        self,
        credentials: Dict[str, Any],
        date: datetime
    ) -> Optional[Dict[str, Any]]:
        """
        Get nutrition data for a specific date.
        
        Args:
            credentials: Decrypted credentials
            date: Date to fetch nutrition data for
            
        Returns:
            Dict with nutrition totals and meals or None if no data
        """
        pass


