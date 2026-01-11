"""
Configuration Service

Loads configuration from YAML files.
Allows changing business rules without code changes.

Usage:
    config = ConfigService.get()
    
    # Get volume tier thresholds
    thresholds = config.get("volume_tiers.marathon.mid")
    
    # Reload config without restart
    ConfigService.reload()
"""

import os
import yaml
import logging
from typing import Any, Optional, Dict
from pathlib import Path
from functools import reduce

logger = logging.getLogger(__name__)


class ConfigService:
    """
    Load and cache configuration from YAML files.
    """
    
    _config: Optional[Dict[str, Any]] = None
    _config_dir: Path = Path(__file__).parent.parent.parent.parent / "config"
    
    @classmethod
    def get(cls, key: str = None, default: Any = None) -> Any:
        """
        Get configuration value.
        
        Args:
            key: Dot-separated key (e.g., "volume_tiers.marathon.mid")
            default: Default value if key not found
            
        Returns:
            Configuration value or entire config if no key provided
        """
        if cls._config is None:
            cls._load()
        
        if key is None:
            return cls._config
        
        try:
            keys = key.split(".")
            value = reduce(lambda d, k: d[k], keys, cls._config)
            return value
        except (KeyError, TypeError):
            return default
    
    @classmethod
    def reload(cls):
        """Reload configuration from files."""
        cls._config = None
        cls._load()
        logger.info("Configuration reloaded")
    
    @classmethod
    def _load(cls):
        """Load all configuration files."""
        cls._config = {}
        
        config_files = [
            "plan_rules.yaml",
            "workout_library.yaml",
            "feature_flags.yaml",
            "paywall_config.yaml",
        ]
        
        for filename in config_files:
            filepath = cls._config_dir / filename
            if filepath.exists():
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f)
                        if data:
                            # Merge into config, using filename (without extension) as namespace
                            namespace = filename.rsplit('.', 1)[0]
                            cls._config[namespace] = data
                            logger.debug(f"Loaded config: {filename}")
                except Exception as e:
                    logger.error(f"Error loading {filename}: {e}")
            else:
                logger.debug(f"Config file not found: {filepath}")
        
        # Also load defaults from constants if no config found
        if not cls._config:
            cls._load_defaults()
    
    @classmethod
    def _load_defaults(cls):
        """Load default configuration from constants."""
        from .constants import (
            VOLUME_TIER_THRESHOLDS,
            LONG_RUN_PEAKS,
            WORKOUT_LIMITS,
            CUTBACK_RULES,
            TAPER_WEEKS,
        )
        
        cls._config = {
            "plan_rules": {
                "volume_tiers": {
                    k.value: {
                        tk.value: tv for tk, tv in v.items()
                    } for k, v in VOLUME_TIER_THRESHOLDS.items()
                },
                "long_run_peaks": {
                    k.value: {
                        tk.value: tv for tk, tv in v.items()
                    } for k, v in LONG_RUN_PEAKS.items()
                },
                "workout_limits": WORKOUT_LIMITS,
                "cutback_rules": {
                    k.value: v for k, v in CUTBACK_RULES.items()
                },
                "taper_weeks": {
                    k.value: v for k, v in TAPER_WEEKS.items()
                },
            }
        }
        
        logger.info("Loaded default configuration from constants")
    
    @classmethod
    def set(cls, key: str, value: Any):
        """
        Set a configuration value (in memory only).
        Useful for testing.
        """
        if cls._config is None:
            cls._load()
        
        keys = key.split(".")
        d = cls._config
        for k in keys[:-1]:
            if k not in d:
                d[k] = {}
            d = d[k]
        d[keys[-1]] = value
    
    @classmethod
    def get_volume_tier_config(cls, distance: str, tier: str) -> Dict[str, Any]:
        """Get volume tier configuration for distance and tier."""
        return cls.get(f"plan_rules.volume_tiers.{distance}.{tier}", {})
    
    @classmethod
    def get_workout_limit(cls, limit_type: str) -> float:
        """Get workout limit by type."""
        return cls.get(f"plan_rules.workout_limits.{limit_type}", 0.0)
    
    @classmethod
    def get_cutback_rules(cls, tier: str) -> Dict[str, Any]:
        """Get cutback rules for a tier."""
        return cls.get(f"plan_rules.cutback_rules.{tier}", {
            "frequency": 4,
            "reduction": 0.25
        })
    
    @classmethod
    def get_taper_weeks(cls, distance: str) -> int:
        """Get taper duration for a distance."""
        return cls.get(f"plan_rules.taper_weeks.{distance}", 2)
