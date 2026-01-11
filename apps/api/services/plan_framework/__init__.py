# Plan Generation Framework
# 
# A modular, scalable system for generating personalized training plans.
# 
# Architecture:
# - Feature flags for gating any feature without deploy
# - Plugin registry for workouts, phases, and rules
# - Entitlements service for access control
# - Config-driven business logic
# - Async generation for scale
# - Aggressive caching for performance
#
# See: _AI_CONTEXT_/OPERATIONS/05_PLAN_GENERATION_ROADMAP.md

from .feature_flags import FeatureFlagService
from .registry import PluginRegistry
from .entitlements import EntitlementsService
from .config import ConfigService
from .cache import PlanCacheService
from .volume_tiers import VolumeTierClassifier
from .phase_builder import PhaseBuilder, TrainingPhase
from .workout_scaler import WorkoutScaler, ScaledWorkout
from .pace_engine import PaceEngine, TrainingPaces
from .generator import PlanGenerator, GeneratedPlan, GeneratedWorkout
from .constants import PlanTier, VolumeTier, Distance, Phase

__all__ = [
    # Core services
    'FeatureFlagService',
    'PluginRegistry', 
    'EntitlementsService',
    'ConfigService',
    'PlanCacheService',
    
    # Generator components
    'VolumeTierClassifier',
    'PhaseBuilder',
    'TrainingPhase',
    'WorkoutScaler',
    'ScaledWorkout',
    'PaceEngine',
    'TrainingPaces',
    
    # Main generator
    'PlanGenerator',
    'GeneratedPlan',
    'GeneratedWorkout',
    
    # Constants
    'PlanTier',
    'VolumeTier',
    'Distance',
    'Phase',
]
