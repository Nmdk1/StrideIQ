"""
Data Stream Registry

Central registry for all data stream adapters.
Allows the system to discover and use adapters dynamically.
"""

from typing import Dict, List, Optional, Type
import logging

from .base import (
    DataStreamAdapter,
    DataStreamType,
    ActivityStreamAdapter,
    RecoveryStreamAdapter,
    NutritionStreamAdapter,
)

logger = logging.getLogger(__name__)


class DataStreamRegistry:
    """
    Registry for all data stream adapters.
    
    Usage:
        # Register an adapter
        @DataStreamRegistry.register
        class StravaAdapter(ActivityStreamAdapter):
            ...
        
        # Get an adapter
        adapter = DataStreamRegistry.get_adapter('strava')
        
        # Get all activity adapters
        activity_adapters = DataStreamRegistry.get_adapters_by_type(DataStreamType.ACTIVITY)
    """
    
    _adapters: Dict[str, DataStreamAdapter] = {}
    _initialized: bool = False
    
    @classmethod
    def register(cls, adapter_class: Type[DataStreamAdapter]) -> Type[DataStreamAdapter]:
        """
        Register a new adapter class.
        
        Can be used as a decorator:
            @DataStreamRegistry.register
            class MyAdapter(DataStreamAdapter):
                ...
        
        Or called directly:
            DataStreamRegistry.register(MyAdapter)
        """
        instance = adapter_class()
        platform_name = instance.platform_name
        
        if platform_name in cls._adapters:
            logger.warning(f"Overwriting existing adapter for platform: {platform_name}")
        
        cls._adapters[platform_name] = instance
        logger.info(f"Registered data stream adapter: {platform_name} ({instance.display_name})")
        
        return adapter_class
    
    @classmethod
    def get_adapter(cls, platform_name: str) -> Optional[DataStreamAdapter]:
        """Get adapter by platform name."""
        return cls._adapters.get(platform_name)
    
    @classmethod
    def get_adapters_by_type(cls, stream_type: DataStreamType) -> List[DataStreamAdapter]:
        """Get all adapters that provide a specific type of data."""
        result = []
        for adapter in cls._adapters.values():
            if adapter.stream_type == stream_type:
                result.append(adapter)
            elif stream_type in adapter.secondary_stream_types:
                result.append(adapter)
        return result
    
    @classmethod
    def get_all_adapters(cls) -> Dict[str, DataStreamAdapter]:
        """Get all registered adapters."""
        return cls._adapters.copy()
    
    @classmethod
    def get_activity_adapters(cls) -> List[ActivityStreamAdapter]:
        """Get all activity stream adapters."""
        return [
            a for a in cls._adapters.values()
            if isinstance(a, ActivityStreamAdapter)
        ]
    
    @classmethod
    def get_recovery_adapters(cls) -> List[RecoveryStreamAdapter]:
        """Get all recovery stream adapters."""
        return [
            a for a in cls._adapters.values()
            if isinstance(a, RecoveryStreamAdapter)
        ]
    
    @classmethod
    def get_nutrition_adapters(cls) -> List[NutritionStreamAdapter]:
        """Get all nutrition stream adapters."""
        return [
            a for a in cls._adapters.values()
            if isinstance(a, NutritionStreamAdapter)
        ]
    
    @classmethod
    def list_platforms(cls) -> List[Dict[str, str]]:
        """
        List all available platforms with their info.
        
        Useful for displaying to users in settings.
        """
        return [
            {
                'platform_name': a.platform_name,
                'display_name': a.display_name,
                'stream_type': a.stream_type.value,
                'requires_oauth': a.requires_oauth,
                'supports_webhooks': a.supports_webhooks,
            }
            for a in cls._adapters.values()
        ]
    
    @classmethod
    def is_platform_available(cls, platform_name: str) -> bool:
        """Check if a platform adapter is available."""
        return platform_name in cls._adapters
    
    @classmethod
    def initialize(cls):
        """
        Initialize the registry by importing all adapter modules.
        
        This should be called at app startup to ensure all adapters
        are registered before use.
        """
        if cls._initialized:
            return
        
        try:
            # Import adapters to trigger registration
            # Strava adapter (existing, needs refactoring to use new pattern)
            # from .adapters.strava import StravaAdapter
            
            # Future adapters
            # from .adapters.garmin import GarminAdapter
            # from .adapters.myfitnesspal import MyFitnessPalAdapter
            # from .adapters.apple_health import AppleHealthAdapter
            
            cls._initialized = True
            logger.info(f"Data stream registry initialized with {len(cls._adapters)} adapters")
            
        except ImportError as e:
            logger.warning(f"Some adapters could not be loaded: {e}")
            cls._initialized = True


