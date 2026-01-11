"""
Plugin Registry

Central registry for all pluggable components:
- Workouts
- Phases
- Scaling rules
- Distance adapters

Allows adding new workouts/phases without code changes.
Just insert into database and reload.

Usage:
    registry = PluginRegistry.get()
    
    # Get workout by key
    workout = registry.get_workout("progressive_long_run")
    
    # Get all workouts for a phase
    workouts = registry.get_workouts_for_phase("build", "marathon")
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class WorkoutPlugin:
    """Workout definition loaded from database."""
    key: str
    name: str
    category: str
    description: str
    
    # Where this workout applies
    applicable_distances: List[str]
    applicable_phases: List[str]
    
    # Structure
    structure_template: Dict[str, Any]
    scaling_rules: Dict[str, Any]
    
    # Option A/B pairing
    option_b_key: Optional[str] = None
    
    # Metadata
    purpose: str = ""
    when_to_use: str = ""
    
    def scale(self, tier: str, weekly_volume: float) -> Dict[str, Any]:
        """Scale workout to athlete's tier and volume."""
        if tier in self.scaling_rules.get("by_tier", {}):
            return self.scaling_rules["by_tier"][tier]
        return self.structure_template


@dataclass  
class PhasePlugin:
    """Phase definition loaded from database."""
    key: str
    name: str
    
    # Where this phase applies
    applicable_distances: List[str]
    
    # Duration constraints
    default_weeks: int
    min_weeks: int
    max_weeks: int
    
    # Training focus
    focus: str
    quality_sessions_per_week: int
    allowed_workout_types: List[str]
    
    def get_weekly_structure(self, days_per_week: int) -> Dict[str, str]:
        """Get weekly workout structure template for this phase."""
        # Default structures by days per week
        structures = {
            5: {
                "sunday": "long",
                "monday": "rest",
                "tuesday": "easy",
                "wednesday": "easy",
                "thursday": "quality" if self.quality_sessions_per_week > 0 else "easy",
                "friday": "rest",
                "saturday": "easy",
            },
            6: {
                "sunday": "long",
                "monday": "rest",
                "tuesday": "medium_long",
                "wednesday": "easy",
                "thursday": "quality" if self.quality_sessions_per_week > 0 else "easy",
                "friday": "easy",
                "saturday": "easy",
            },
            7: {
                "sunday": "long",
                "monday": "recovery",
                "tuesday": "medium_long",
                "wednesday": "easy",
                "thursday": "quality" if self.quality_sessions_per_week > 0 else "easy",
                "friday": "easy",
                "saturday": "easy",
            },
        }
        return structures.get(days_per_week, structures[6])


@dataclass
class RulePlugin:
    """Scaling/selection rule loaded from database."""
    key: str
    name: str
    category: str  # "scaling", "selection", "adaptation"
    rule_logic: Dict[str, Any]
    
    def evaluate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate rule against context."""
        # Rules are evaluated based on rule_logic
        # This is a simple implementation - can be extended
        return {"applies": True, "result": self.rule_logic}


class PluginRegistry:
    """
    Central registry for all pluggable components.
    Singleton pattern - one instance shared across application.
    """
    
    _instance: Optional['PluginRegistry'] = None
    _db: Optional[Session] = None
    _loaded_at: Optional[datetime] = None
    
    def __init__(self):
        self.workouts: Dict[str, WorkoutPlugin] = {}
        self.phases: Dict[str, PhasePlugin] = {}
        self.rules: Dict[str, RulePlugin] = {}
        self._loaded = False
    
    @classmethod
    def get(cls, db: Session = None) -> 'PluginRegistry':
        """Get singleton instance, optionally with database session."""
        if cls._instance is None:
            cls._instance = cls()
        
        if db is not None:
            cls._db = db
            if not cls._instance._loaded:
                cls._instance._load_from_database(db)
        
        return cls._instance
    
    @classmethod
    def reload(cls, db: Session = None):
        """Force reload all plugins from database."""
        if cls._instance is None:
            cls._instance = cls()
        
        session = db or cls._db
        if session:
            cls._instance._load_from_database(session)
            logger.info("Plugin registry reloaded")
    
    def register_workout(self, workout: WorkoutPlugin):
        """Register a workout plugin."""
        self.workouts[workout.key] = workout
        logger.debug(f"Registered workout: {workout.key}")
    
    def register_phase(self, phase: PhasePlugin):
        """Register a phase plugin."""
        self.phases[phase.key] = phase
        logger.debug(f"Registered phase: {phase.key}")
    
    def register_rule(self, rule: RulePlugin):
        """Register a rule plugin."""
        self.rules[rule.key] = rule
        logger.debug(f"Registered rule: {rule.key}")
    
    def get_workout(self, key: str) -> Optional[WorkoutPlugin]:
        """Get workout by key."""
        return self.workouts.get(key)
    
    def get_phase(self, key: str) -> Optional[PhasePlugin]:
        """Get phase by key."""
        return self.phases.get(key)
    
    def get_rule(self, key: str) -> Optional[RulePlugin]:
        """Get rule by key."""
        return self.rules.get(key)
    
    def get_workouts_for_phase(
        self, 
        phase: str, 
        distance: str
    ) -> List[WorkoutPlugin]:
        """Get all workouts applicable to a phase and distance."""
        return [
            w for w in self.workouts.values()
            if phase in w.applicable_phases
            and distance in w.applicable_distances
        ]
    
    def get_workouts_by_category(self, category: str) -> List[WorkoutPlugin]:
        """Get all workouts in a category."""
        return [
            w for w in self.workouts.values()
            if w.category == category
        ]
    
    def get_phases_for_distance(self, distance: str) -> List[PhasePlugin]:
        """Get all phases applicable to a distance."""
        return [
            p for p in self.phases.values()
            if distance in p.applicable_distances
        ]
    
    def get_option_b(self, workout_key: str) -> Optional[WorkoutPlugin]:
        """Get Option B workout for a given workout."""
        workout = self.get_workout(workout_key)
        if workout and workout.option_b_key:
            return self.get_workout(workout.option_b_key)
        return None
    
    def _load_from_database(self, db: Session):
        """Load all plugins from database."""
        from models import WorkoutDefinition, PhaseDefinition, ScalingRule
        
        # Clear existing
        self.workouts.clear()
        self.phases.clear()
        self.rules.clear()
        
        # Load workouts
        try:
            workout_defs = db.query(WorkoutDefinition).filter_by(active=True).all()
            for wd in workout_defs:
                plugin = WorkoutPlugin(
                    key=wd.key,
                    name=wd.name,
                    category=wd.category,
                    description=wd.description or "",
                    applicable_distances=wd.applicable_distances or [],
                    applicable_phases=wd.applicable_phases or [],
                    structure_template=wd.structure_template or {},
                    scaling_rules=wd.scaling_rules or {},
                    option_b_key=wd.option_b_key,
                    purpose=wd.purpose or "",
                    when_to_use=wd.when_to_use or "",
                )
                self.register_workout(plugin)
            
            logger.info(f"Loaded {len(self.workouts)} workout definitions")
        except Exception as e:
            logger.warning(f"Could not load workout definitions: {e}")
        
        # Load phases
        try:
            phase_defs = db.query(PhaseDefinition).filter_by(active=True).all()
            for pd in phase_defs:
                plugin = PhasePlugin(
                    key=pd.key,
                    name=pd.name,
                    applicable_distances=pd.applicable_distances or [],
                    default_weeks=pd.default_weeks,
                    min_weeks=pd.min_weeks,
                    max_weeks=pd.max_weeks,
                    focus=pd.focus or "",
                    quality_sessions_per_week=pd.quality_sessions_per_week,
                    allowed_workout_types=pd.allowed_workout_types or [],
                )
                self.register_phase(plugin)
            
            logger.info(f"Loaded {len(self.phases)} phase definitions")
        except Exception as e:
            logger.warning(f"Could not load phase definitions: {e}")
        
        # Load rules
        try:
            rule_defs = db.query(ScalingRule).filter_by(active=True).all()
            for rd in rule_defs:
                plugin = RulePlugin(
                    key=rd.key,
                    name=rd.name,
                    category=rd.category,
                    rule_logic=rd.rule_logic or {},
                )
                self.register_rule(plugin)
            
            logger.info(f"Loaded {len(self.rules)} scaling rules")
        except Exception as e:
            logger.warning(f"Could not load scaling rules: {e}")
        
        self._loaded = True
        self._loaded_at = datetime.utcnow()
    
    def stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        return {
            "workouts": len(self.workouts),
            "phases": len(self.phases),
            "rules": len(self.rules),
            "loaded": self._loaded,
            "loaded_at": self._loaded_at.isoformat() if self._loaded_at else None,
        }
