"""
Data Streams Module

Unified interface for integrating external data sources:
- Activity platforms (Strava, Garmin, Coros, Whoop, Intervals.icu)
- Recovery/wellness platforms (Apple Health, Samsung Health, Oura)
- Nutrition apps (MyFitnessPal, Cronometer, Lose It)

This module provides:
1. Abstract base classes for adapters
2. Unified data models across platforms
3. Registry for managing adapters
4. Common sync/webhook infrastructure

Design Principles:
- All adapters implement the same interface
- Data normalized to unified models before storage
- Optional inputs - never required, always helpful
- Non-intrusive sync - respects rate limits, graceful failures
"""

from .base import (
    DataStreamType,
    DataStreamAdapter,
    SyncResult,
    ConnectionStatus,
)
from .models import (
    UnifiedActivityData,
    UnifiedRecoveryData,
    UnifiedNutritionData,
)
from .registry import DataStreamRegistry

__all__ = [
    'DataStreamType',
    'DataStreamAdapter',
    'SyncResult',
    'ConnectionStatus',
    'UnifiedActivityData',
    'UnifiedRecoveryData',
    'UnifiedNutritionData',
    'DataStreamRegistry',
]


