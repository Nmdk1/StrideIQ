"""
Workout Template Schema and Loader

Defines the schema for workout templates and provides loading/validation.
Templates are stored in external JSON for non-developer editability.

ADR-036: N=1 Learning Workout Selection Engine
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================

class TrainingPhase(str, Enum):
    BASE = "base"
    BUILD = "build"
    PEAK = "peak"
    TAPER = "taper"


class FatigueCost(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class StimulusType(str, Enum):
    """
    Stimulus categories for variance enforcement.
    
    Templates with the same stimulus_type should not be scheduled
    back-to-back to ensure varied training stress.
    """
    INTERVALS = "intervals"          # Repeated hard efforts with recovery
    CONTINUOUS = "continuous"        # Sustained effort without breaks
    HILLS = "hills"                  # Hill-based work
    STRIDES = "strides"              # Short acceleration efforts
    RACE_PACE = "race_pace"          # Goal race pace work
    FARTLEK = "fartlek"              # Unstructured speed play


class DataTier(str, Enum):
    """Data sufficiency tier for selection logic."""
    UNCALIBRATED = "uncalibrated"    # < 30 activities or < 60 days
    LEARNING = "learning"            # 30-100 activities, 60-180 days, < 3 races
    CALIBRATED = "calibrated"        # 100+ activities, 180+ days, 3+ races


# =============================================================================
# SCHEMA
# =============================================================================

class RPERange(BaseModel):
    """Expected RPE range for a workout."""
    min: int = Field(ge=1, le=10)
    max: int = Field(ge=1, le=10)
    midpoint: float = Field(ge=1, le=10)
    
    @model_validator(mode='after')
    def validate_range(self):
        if self.min > self.max:
            raise ValueError('min must be <= max')
        if not (self.min <= self.midpoint <= self.max):
            raise ValueError('midpoint must be between min and max')
        return self


class WorkoutTemplate(BaseModel):
    """
    Single workout template definition.
    
    Templates are HYPOTHESES about what works, not prescriptions.
    Selection weights toward templates that have proven effective
    for THIS athlete based on response history.
    
    Three-dimensional selection uses:
    - phases: Periodization filter (when in training cycle)
    - progression_week_range: Progression filter (when in phase)
    - stimulus_type + dont_follow: Variance filter (avoid repeats)
    """
    
    # === Identity ===
    id: str = Field(
        ..., 
        description="Unique template identifier, e.g. 'threshold_3x10'",
        pattern=r"^[a-z][a-z0-9_]*$"
    )
    
    name: str = Field(
        ..., 
        description="Human-readable name, e.g. 'Threshold Intervals 3×10'"
    )
    
    workout_type: str = Field(
        ...,
        description="Category: threshold, strides, hill_sprints, sharpening, race_pace"
    )
    
    # === Dimension 1: Periodization ===
    phases: List[TrainingPhase] = Field(
        ...,
        min_length=1,
        description="Training phases where this template is valid"
    )
    
    # === Dimension 2: Progression ===
    progression_week_range: Tuple[float, float] = Field(
        ...,
        description="[min, max] as fraction of phase (0.0-1.0). E.g. [0.0, 0.33] = early phase"
    )
    
    @field_validator('progression_week_range')
    @classmethod
    def validate_progression_range(cls, v):
        if not (0.0 <= v[0] <= v[1] <= 1.0):
            raise ValueError('progression_week_range must be [min, max] where 0 <= min <= max <= 1')
        return v
    
    # === Dimension 3: Variance ===
    stimulus_type: StimulusType = Field(
        ...,
        description="Stimulus category for variance enforcement"
    )
    
    dont_follow: List[str] = Field(
        default_factory=list,
        description="Template IDs that should not immediately precede this workout"
    )
    
    # === Constraints ===
    requires: List[str] = Field(
        default_factory=list,
        description="Required capabilities: 'hill_access', 'track_access', etc."
    )
    
    # === Load/Fatigue ===
    fatigue_cost: FatigueCost = Field(
        ...,
        description="Relative fatigue impact for selection tiebreaking"
    )
    
    total_quality_minutes: int = Field(
        ...,
        ge=0,
        le=120,
        description="Minutes at quality effort (for TSS estimation)"
    )
    
    # === Expected Response ===
    expected_rpe_range: RPERange = Field(
        ...,
        description="Expected RPE range for gap analysis. Initial values are population defaults; "
                    "should be updated per-athlete as feedback accumulates via AthleteWorkoutResponse."
    )
    
    # === Prescription ===
    structure: str = Field(
        ...,
        description="Workout structure, e.g. '3×10min @ T-pace, 2min jog recovery'"
    )
    
    description_template: str = Field(
        ...,
        description="Full description with {t_pace}, {m_pace}, {e_pace} placeholders"
    )
    
    # === N=1 Learning ===
    hypothesis: str = Field(
        ...,
        description="What we hypothesize this workout achieves (to be validated)"
    )
    
    validation_criteria: str = Field(
        ...,
        description="How to validate the hypothesis from athlete data"
    )
    
    fallback_if_fails: Optional[str] = Field(
        default=None,
        description="Template ID to try if this template consistently fails validation for an athlete. "
                    "If null, selection will simply avoid this template."
    )
    
    # === Optional ===
    rationale: Optional[str] = Field(
        default=None,
        description="Why this workout, for athlete education"
    )
    
    notes: List[str] = Field(
        default_factory=list,
        description="Additional notes for the athlete"
    )
    
    def render_description(self, paces: Dict[str, str]) -> str:
        """Render description with athlete-specific paces."""
        description = self.description_template
        for pace_key, pace_value in paces.items():
            description = description.replace(f"{{{pace_key}}}", pace_value)
        return description


class WorkoutTemplateLibrary(BaseModel):
    """
    Complete template library loaded from JSON.
    Validated as a unit at startup.
    """
    
    version: str = Field(
        ...,
        description="Schema version for migration support"
    )
    
    templates: List[WorkoutTemplate] = Field(
        ...,
        min_length=1,
        description="All available workout templates"
    )
    
    @field_validator('templates')
    @classmethod
    def validate_unique_ids(cls, v):
        ids = [t.id for t in v]
        if len(ids) != len(set(ids)):
            duplicates = [id for id in ids if ids.count(id) > 1]
            raise ValueError(f'Duplicate template IDs: {set(duplicates)}')
        return v
    
    @field_validator('templates')
    @classmethod
    def validate_dont_follow_references(cls, v):
        all_ids = {t.id for t in v}
        for t in v:
            invalid = [ref for ref in t.dont_follow if ref not in all_ids]
            if invalid:
                raise ValueError(f"Template '{t.id}' has invalid dont_follow refs: {invalid}")
        return v
    
    def get_template(self, template_id: str) -> Optional[WorkoutTemplate]:
        """Get template by ID."""
        for t in self.templates:
            if t.id == template_id:
                return t
        return None
    
    def filter_by_phase(self, phase: TrainingPhase) -> List[WorkoutTemplate]:
        """Get templates valid for a phase."""
        return [t for t in self.templates if phase in t.phases]
    
    def filter_by_stimulus(self, stimulus_type: StimulusType) -> List[WorkoutTemplate]:
        """Get templates of a specific stimulus type."""
        return [t for t in self.templates if t.stimulus_type == stimulus_type]


# =============================================================================
# LOADER
# =============================================================================

_cached_library: Optional[WorkoutTemplateLibrary] = None


def load_template_library(
    path: Optional[Path] = None,
    force_reload: bool = False
) -> WorkoutTemplateLibrary:
    """
    Load and validate template library from JSON.
    
    Caches the loaded library for performance.
    
    Args:
        path: Path to template JSON file (defaults to data/workout_templates.json)
        force_reload: Force reload even if cached
        
    Returns:
        Validated WorkoutTemplateLibrary
        
    Raises:
        FileNotFoundError: If template file doesn't exist
        ValidationError: If templates fail schema validation
    """
    global _cached_library
    
    if _cached_library is not None and not force_reload:
        return _cached_library
    
    if path is None:
        # Default path relative to this file
        path = Path(__file__).parent.parent / "data" / "workout_templates.json"
    
    if not path.exists():
        raise FileNotFoundError(f"Template library not found: {path}")
    
    logger.info(f"Loading workout template library from {path}")
    
    with open(path, "r") as f:
        data = json.load(f)
    
    library = WorkoutTemplateLibrary(**data)
    
    logger.info(f"Loaded {len(library.templates)} workout templates, version {library.version}")
    
    _cached_library = library
    return library


def get_template(template_id: str) -> Optional[WorkoutTemplate]:
    """Get a specific template by ID."""
    library = load_template_library()
    return library.get_template(template_id)


def get_stimulus_type(template_id: str) -> Optional[StimulusType]:
    """Get stimulus type for a template ID."""
    template = get_template(template_id)
    return template.stimulus_type if template else None


# =============================================================================
# DATA SUFFICIENCY ASSESSMENT
# =============================================================================

@dataclass
class DataSufficiencyAssessment:
    """Assessment of athlete's data sufficiency for N=1 selection."""
    tier: DataTier
    total_activities: int
    days_of_data: int
    quality_sessions: int
    rpe_coverage: float  # Fraction of activities with RPE feedback
    race_count: int
    days_since_last_activity: int  # For staleness detection
    notes: List[str]


def assess_data_sufficiency(
    athlete_id: str,
    db: Any  # Session
) -> DataSufficiencyAssessment:
    """
    Assess athlete's data sufficiency for workout selection.
    
    Determines whether to use cold-start, learning, or calibrated mode.
    """
    from models import Activity, ActivityFeedback, Athlete
    from sqlalchemy import func
    from datetime import datetime, timedelta, timezone
    
    # Get activity counts
    total_activities = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.sport.ilike("run")
    ).count()
    
    # Get date range
    dates = db.query(
        func.min(Activity.start_time),
        func.max(Activity.start_time)
    ).filter(
        Activity.athlete_id == athlete_id,
        Activity.sport.ilike("run")
    ).first()
    
    if dates[0] and dates[1]:
        days_of_data = (dates[1] - dates[0]).days
    else:
        days_of_data = 0
    
    # Get quality session count (threshold, tempo, intervals, race)
    quality_sessions = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.workout_type.in_([
            'threshold_run', 'tempo_run', 'tempo_intervals',
            'vo2max_intervals', 'track_workout', 'race'
        ])
    ).count()
    
    # Get RPE coverage
    activities_with_rpe = db.query(ActivityFeedback).join(Activity).filter(
        Activity.athlete_id == athlete_id,
        ActivityFeedback.perceived_effort.isnot(None)
    ).count()
    
    rpe_coverage = activities_with_rpe / total_activities if total_activities > 0 else 0
    
    # Get race count
    race_count = db.query(Activity).filter(
        Activity.athlete_id == athlete_id,
        Activity.workout_type == 'race'
    ).count()
    
    # Calculate days since last activity (for staleness detection)
    if dates[1]:
        days_since_last = (datetime.now(timezone.utc) - dates[1]).days
    else:
        days_since_last = 9999  # No activities
    
    # Determine tier (with staleness downgrade)
    notes = []
    
    # First, determine base tier from data volume
    if total_activities < 30 or days_of_data < 60:
        base_tier = DataTier.UNCALIBRATED
    elif total_activities < 100 or days_of_data < 180 or race_count < 3:
        base_tier = DataTier.LEARNING
    else:
        base_tier = DataTier.CALIBRATED
    
    # Apply staleness downgrade
    tier = base_tier
    if base_tier == DataTier.CALIBRATED and days_since_last >= 60:
        tier = DataTier.LEARNING
        notes.append(f"Downgraded from calibrated: {days_since_last} days since last activity")
    elif base_tier == DataTier.LEARNING and days_since_last >= 90:
        tier = DataTier.UNCALIBRATED
        notes.append(f"Downgraded from learning: {days_since_last} days since last activity")
    elif base_tier == DataTier.CALIBRATED and days_since_last >= 90:
        tier = DataTier.UNCALIBRATED
        notes.append(f"Downgraded from calibrated: {days_since_last} days since last activity")
    
    # Add tier-specific notes
    if tier == DataTier.UNCALIBRATED:
        notes.append("Insufficient training history for personalization")
        if total_activities < 30:
            notes.append(f"Need {30 - total_activities} more activities")
        if days_of_data < 60:
            notes.append(f"Need {60 - days_of_data} more days of data")
    elif tier == DataTier.LEARNING:
        notes.append("Building personalization model")
        if race_count < 3:
            notes.append(f"Need {3 - race_count} more races to validate model")
    else:
        notes.append("Full personalization active")
    
    if rpe_coverage < 0.3:
        notes.append(f"RPE feedback on only {rpe_coverage*100:.0f}% of activities - more feedback improves learning")
    
    return DataSufficiencyAssessment(
        tier=tier,
        total_activities=total_activities,
        days_of_data=days_of_data,
        quality_sessions=quality_sessions,
        rpe_coverage=rpe_coverage,
        race_count=race_count,
        days_since_last_activity=days_since_last,
        notes=notes
    )


# =============================================================================
# WORKOUT SELECTOR
# =============================================================================

@dataclass
class ScoredTemplate:
    """Template with computed selection score."""
    template: WorkoutTemplate
    phase_weight: float  # 0-1, phase match weight
    response_weight: float  # 0-1, from athlete response history
    learning_weight: float  # 0-1, from what_works/what_doesnt_work
    final_score: float  # Combined score for selection
    selection_reason: str  # Why this template was chosen (for audit)


@dataclass
class WorkoutSelectionResult:
    """Result of workout selection with full audit trail."""
    template: WorkoutTemplate
    selection_mode: str  # 'explore', 'exploit', 'fallback'
    data_tier: DataTier
    candidates_considered: int
    filtered_out_by_phase: int
    filtered_out_by_progression: int
    filtered_out_by_variance: int
    filtered_out_by_constraints: int
    final_score: float
    selection_reason: str
    audit_log: Dict[str, Any]


class WorkoutSelector:
    """
    N=1 Learning Workout Selector.
    
    Implements the three-dimensional model (Periodization, Progression, Variance)
    with phase as a SOFT weight, not hard filter, per ADR-036.
    
    Selection is weighted by:
    1. Phase match (soft weight, stronger for cold-start athletes)
    2. Progression position (τ1-informed)
    3. Variance enforcement (no immediate stimulus repeats)
    4. Athlete response history (RPE gaps, completion rates)
    5. Banked intelligence (what_works, what_doesnt_work)
    
    The explore/exploit ratio is determined by data tier:
    - Uncalibrated: 50% explore (gather data)
    - Learning: 30% explore
    - Calibrated: 10% explore (trust banked intelligence)
    """
    
    def __init__(self, db: Any):
        self.db = db
        self.library = load_template_library()
        self._random = __import__('random').Random()  # For reproducibility in tests
    
    def seed_random(self, seed: int):
        """Seed the random generator for reproducible tests."""
        self._random = __import__('random').Random(seed)
    
    def select_quality_workout(
        self,
        athlete_id: str,
        phase: TrainingPhase,
        week_in_phase: int,
        total_phase_weeks: int,
        recent_quality_ids: List[str],
        athlete_facilities: Optional[List[str]] = None
    ) -> WorkoutSelectionResult:
        """
        Select a quality workout using N=1 learning approach.
        
        Args:
            athlete_id: UUID of the athlete
            phase: Current training phase
            week_in_phase: Current week within the phase (1-indexed)
            total_phase_weeks: Total weeks in this phase
            recent_quality_ids: Template IDs of recent quality workouts (most recent last)
            athlete_facilities: Available facilities (e.g., ['hill_access', 'track_access'])
            
        Returns:
            WorkoutSelectionResult with selected template and full audit trail
        """
        import random
        
        athlete_facilities = athlete_facilities or []
        
        # Assess data sufficiency
        data_assessment = assess_data_sufficiency(athlete_id, self.db)
        
        # Get calibrated model (or defaults)
        athlete_model = self._get_athlete_model(athlete_id, data_assessment.tier)
        
        # Get athlete response history
        response_history = self._get_response_history(athlete_id, data_assessment.tier)
        
        # Get banked learnings
        learnings = self._get_athlete_learnings(athlete_id, data_assessment.tier)
        
        # Start with all templates
        all_templates = list(self.library.templates)
        
        # Initialize audit log
        audit_log = {
            "athlete_id": str(athlete_id),
            "phase": phase.value,
            "week_in_phase": week_in_phase,
            "total_phase_weeks": total_phase_weeks,
            "data_tier": data_assessment.tier.value,
            "tau1": athlete_model.get("tau1", 42.0),
            "recent_quality_ids": recent_quality_ids[-3:],
            "filters": {}
        }
        
        # Score all templates
        scored_templates: List[ScoredTemplate] = []
        
        filter_counts = {
            "phase": 0,
            "progression": 0,
            "variance": 0,
            "constraints": 0
        }
        
        # Calculate progression position
        progress_pct = week_in_phase / max(total_phase_weeks, 1)
        tau1 = athlete_model.get("tau1", 42.0)
        progression_speed = 42.0 / tau1  # Normalized to population average
        adjusted_progress = min(progress_pct * progression_speed, 1.0)
        
        # Get last stimulus type for variance
        last_stimulus: Optional[StimulusType] = None
        if recent_quality_ids:
            last_template = self.library.get_template(recent_quality_ids[-1])
            if last_template:
                last_stimulus = last_template.stimulus_type
        
        # Phase penalty is softer for calibrated athletes (they may know better)
        phase_penalty = {
            DataTier.UNCALIBRATED: 0.1,
            DataTier.LEARNING: 0.3,
            DataTier.CALIBRATED: 0.7
        }.get(data_assessment.tier, 0.3)
        
        for template in all_templates:
            # 1. Phase weight (SOFT, not hard filter)
            if phase in template.phases:
                phase_weight = 1.0
            else:
                phase_weight = phase_penalty
                filter_counts["phase"] += 1
            
            # 2. Progression filter (can be soft or hard depending on tier)
            prog_min, prog_max = template.progression_week_range
            if prog_min <= adjusted_progress <= prog_max:
                prog_weight = 1.0
            else:
                # Outside progression range - penalize but don't exclude
                distance = min(abs(adjusted_progress - prog_min), abs(adjusted_progress - prog_max))
                prog_weight = max(0.2, 1.0 - distance * 2)  # Min 0.2 weight
                filter_counts["progression"] += 1
            
            # 3. Variance filter (stimulus type + dont_follow)
            variance_weight = 1.0
            if template.stimulus_type == last_stimulus:
                variance_weight *= 0.3  # Strongly penalize same stimulus back-to-back
                filter_counts["variance"] += 1
            
            if template.id in recent_quality_ids[-2:]:
                variance_weight *= 0.2  # Very recent repeat
                filter_counts["variance"] += 1
            
            for blocked_id in template.dont_follow:
                if blocked_id in recent_quality_ids[-1:]:
                    variance_weight *= 0.4  # Direct predecessor blocked
                    filter_counts["variance"] += 1
            
            # 4. Constraint filter (HARD - can't do what you can't do)
            if template.requires:
                if not all(req in athlete_facilities for req in template.requires):
                    filter_counts["constraints"] += 1
                    continue  # Skip entirely - can't execute
            
            # 5. Response history weighting (N=1 learning)
            response_weight = 1.0
            if template.stimulus_type.value in response_history:
                resp = response_history[template.stimulus_type.value]
                avg_rpe_gap = resp.get("avg_rpe_gap", 0)
                if avg_rpe_gap < -0.5:  # Felt easier than expected = good sign
                    response_weight *= 1.0 + abs(avg_rpe_gap) * 0.2
                elif avg_rpe_gap > 1.0:  # Felt much harder than expected = caution
                    response_weight *= max(0.5, 1.0 - avg_rpe_gap * 0.2)
                
                completion = resp.get("completion_rate", 1.0)
                if completion < 0.8:
                    response_weight *= 0.7  # Low completion rate
            
            # 6. Banked learnings
            learning_weight = 1.0
            if template.id in learnings.get("what_works", []):
                learning_weight *= 1.5
            if template.id in learnings.get("what_doesnt_work", []):
                learning_weight *= 0.2
            if template.stimulus_type.value in learnings.get("what_works_stimulus", []):
                learning_weight *= 1.2
            if template.stimulus_type.value in learnings.get("what_doesnt_work_stimulus", []):
                learning_weight *= 0.5
            
            # Calculate final score
            final_score = (
                phase_weight * 
                prog_weight * 
                variance_weight * 
                response_weight * 
                learning_weight
            )
            
            # Build selection reason
            reasons = []
            if phase_weight < 1.0:
                reasons.append(f"out-of-phase({phase_weight:.1f})")
            if prog_weight < 1.0:
                reasons.append(f"progression({prog_weight:.1f})")
            if variance_weight < 1.0:
                reasons.append(f"variance({variance_weight:.1f})")
            if response_weight != 1.0:
                reasons.append(f"response({response_weight:.2f})")
            if learning_weight != 1.0:
                reasons.append(f"learning({learning_weight:.1f})")
            
            scored_templates.append(ScoredTemplate(
                template=template,
                phase_weight=phase_weight,
                response_weight=response_weight,
                learning_weight=learning_weight,
                final_score=final_score,
                selection_reason=", ".join(reasons) if reasons else "full-match"
            ))
        
        audit_log["filters"] = filter_counts
        audit_log["candidates_after_constraints"] = len(scored_templates)
        
        # Handle empty candidates
        if not scored_templates:
            fallback = self._get_phase_fallback(phase)
            return WorkoutSelectionResult(
                template=fallback,
                selection_mode="fallback",
                data_tier=data_assessment.tier,
                candidates_considered=len(all_templates),
                filtered_out_by_phase=filter_counts["phase"],
                filtered_out_by_progression=filter_counts["progression"],
                filtered_out_by_variance=filter_counts["variance"],
                filtered_out_by_constraints=filter_counts["constraints"],
                final_score=0.0,
                selection_reason="All candidates filtered out, using phase fallback",
                audit_log=audit_log
            )
        
        # Explore/exploit decision
        explore_prob = {
            DataTier.UNCALIBRATED: 0.5,
            DataTier.LEARNING: 0.3,
            DataTier.CALIBRATED: 0.1
        }.get(data_assessment.tier, 0.3)
        
        is_explore = self._random.random() < explore_prob
        
        if is_explore:
            # Explore: weighted random selection
            weights = [st.final_score for st in scored_templates]
            total_weight = sum(weights)
            if total_weight > 0:
                weights = [w / total_weight for w in weights]
                selected_idx = self._random.choices(range(len(scored_templates)), weights=weights)[0]
            else:
                selected_idx = self._random.randint(0, len(scored_templates) - 1)
            selected = scored_templates[selected_idx]
            selection_mode = "explore"
        else:
            # Exploit: highest score
            selected = max(scored_templates, key=lambda st: st.final_score)
            selection_mode = "exploit"
        
        audit_log["selected_template"] = selected.template.id
        audit_log["selection_mode"] = selection_mode
        audit_log["final_score"] = selected.final_score
        audit_log["explore_probability"] = explore_prob
        
        return WorkoutSelectionResult(
            template=selected.template,
            selection_mode=selection_mode,
            data_tier=data_assessment.tier,
            candidates_considered=len(all_templates),
            filtered_out_by_phase=filter_counts["phase"],
            filtered_out_by_progression=filter_counts["progression"],
            filtered_out_by_variance=filter_counts["variance"],
            filtered_out_by_constraints=filter_counts["constraints"],
            final_score=selected.final_score,
            selection_reason=selected.selection_reason,
            audit_log=audit_log
        )
    
    def _get_athlete_model(self, athlete_id: str, tier: DataTier) -> Dict[str, float]:
        """Get calibrated or default Banister model parameters."""
        from models import AthleteCalibratedModel
        
        if tier == DataTier.UNCALIBRATED:
            return {"tau1": 42.0, "tau2": 7.0, "k1": 1.0, "k2": 2.0, "p0": 100.0}
        
        calibration = self.db.query(AthleteCalibratedModel).filter(
            AthleteCalibratedModel.athlete_id == athlete_id
        ).first()
        
        if calibration:
            return {
                "tau1": calibration.tau1,
                "tau2": calibration.tau2,
                "k1": calibration.k1,
                "k2": calibration.k2,
                "p0": calibration.p0
            }
        
        # Default if no calibration exists
        return {"tau1": 42.0, "tau2": 7.0, "k1": 1.0, "k2": 2.0, "p0": 100.0}
    
    def _get_response_history(self, athlete_id: str, tier: DataTier) -> Dict[str, Dict[str, float]]:
        """Get athlete's response history by stimulus type."""
        from models import AthleteWorkoutResponse
        
        if tier == DataTier.UNCALIBRATED:
            return {}  # No history for cold-start
        
        responses = self.db.query(AthleteWorkoutResponse).filter(
            AthleteWorkoutResponse.athlete_id == athlete_id
        ).all()
        
        return {
            r.stimulus_type: {
                "avg_rpe_gap": r.avg_rpe_gap or 0,
                "completion_rate": r.completion_rate or 1.0,
                "n_observations": r.n_observations
            }
            for r in responses
        }
    
    def _get_athlete_learnings(self, athlete_id: str, tier: DataTier) -> Dict[str, List[str]]:
        """Get banked athlete learnings."""
        from models import AthleteLearning
        
        if tier == DataTier.UNCALIBRATED:
            return {}  # No learnings for cold-start
        
        learnings = self.db.query(AthleteLearning).filter(
            AthleteLearning.athlete_id == athlete_id,
            AthleteLearning.is_active == True
        ).all()
        
        result: Dict[str, List[str]] = {
            "what_works": [],
            "what_doesnt_work": [],
            "what_works_stimulus": [],
            "what_doesnt_work_stimulus": [],
            "injury_triggers": []
        }
        
        for learning in learnings:
            if learning.learning_type == "what_works":
                if learning.subject.startswith("template:"):
                    result["what_works"].append(learning.subject.replace("template:", ""))
                elif learning.subject.startswith("stimulus:"):
                    result["what_works_stimulus"].append(learning.subject.replace("stimulus:", ""))
            elif learning.learning_type == "what_doesnt_work":
                if learning.subject.startswith("template:"):
                    result["what_doesnt_work"].append(learning.subject.replace("template:", ""))
                elif learning.subject.startswith("stimulus:"):
                    result["what_doesnt_work_stimulus"].append(learning.subject.replace("stimulus:", ""))
            elif learning.learning_type == "injury_trigger":
                result["injury_triggers"].append(learning.subject)
        
        return result
    
    def _get_phase_fallback(self, phase: TrainingPhase) -> WorkoutTemplate:
        """Get a safe fallback template for a phase when all candidates are filtered."""
        # Safe fallbacks by phase
        fallbacks = {
            TrainingPhase.BASE: "strides_6x20",
            TrainingPhase.BUILD: "threshold_intervals_2x10",
            TrainingPhase.PEAK: "goal_pace_4mi",
            TrainingPhase.TAPER: "sharpening_6x200"
        }
        
        fallback_id = fallbacks.get(phase, "strides_6x20")
        template = self.library.get_template(fallback_id)
        
        if template:
            return template
        
        # Ultimate fallback - just return first template
        return self.library.templates[0]
