from sqlalchemy import Column, Integer, BigInteger, Boolean, CheckConstraint, Float, Date, DateTime, ForeignKey, Numeric, Text, String, Index, UniqueConstraint, text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from core.database import Base
import uuid
from typing import Optional
from datetime import datetime, timezone

class WorkoutTemplate(Base):
    """
    Workout Template Registry (authoritative, DB-backed).

    This is the deterministic core for quality session selection (ADR-036 "3D model"):
    - Periodization: phase_compatibility
    - Progression: progression_logic (step selection)
    - Variance: variance_tags + optional dont_follow
    - Constraints: constraints JSON (e.g., min_time_min)

    Note: This is a registry of workout templates, not an athlete plan.
    """

    __tablename__ = "workout_template"

    # NOTE: Use a stable, human-readable ID (e.g., "base_aerobic_strides").
    id = Column(Text, primary_key=True)

    # Display + classification
    name = Column(Text, nullable=False)
    intensity_tier = Column(Text, nullable=False)  # RECOVERY | AEROBIC | THRESHOLD | VO2MAX | ANAEROBIC

    # Core 3D metadata
    phase_compatibility = Column(JSONB, nullable=False)  # ["base","build","peak","taper"]
    progression_logic = Column(JSONB, nullable=False)  # e.g., {"type":"steps","steps":[...]}
    variance_tags = Column(JSONB, nullable=False, default=list)  # e.g., ["TIME_CRUNCHED","TREADMILL_FRIENDLY"]
    constraints = Column(JSONB, nullable=False, default=dict)  # e.g., {"min_time_min": 45}

    # Optional variance/constraint helpers
    dont_follow = Column(JSONB, nullable=True)  # ["other_template_id", ...]

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_workout_template_intensity_tier", "intensity_tier"),
    )

class WorkoutSelectionAuditEvent(Base):
    """
    Append-only audit log for workout template selection.

    This is designed for production debugability:
    - what we selected
    - what we filtered out and why
    - which constraints/variance rules applied
    - without dumping sensitive athlete data into logs
    """

    __tablename__ = "workout_selection_audit_event"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)

    # Provenance / context
    trigger = Column(Text, nullable=False)  # plan_gen | rebuild | coach_prescription | shadow
    plan_generation_id = Column(Text, nullable=True, index=True)  # generator's run id
    plan_id = Column(UUID(as_uuid=True), ForeignKey("training_plan.id"), nullable=True, index=True)
    target_date = Column(Date, nullable=True, index=True)
    phase = Column(Text, nullable=True, index=True)  # base/build/peak/taper
    phase_week = Column(Integer, nullable=True)

    # Decision
    selected_template_id = Column(Text, ForeignKey("workout_template.id"), nullable=True, index=True)
    selection_mode = Column(Text, nullable=True)  # on | shadow | fallback

    # Bounded payload (ids, counts, reasons, diffs)
    payload = Column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_workout_selection_audit_event_created_at", "created_at"),
    )

class TrainingPlan(Base):
    """
    Training plan for an athlete.
    
    Represents a periodized training plan with a goal race.
    Plans are structured in phases (base, build, peak, taper) with
    week-by-week workout prescriptions.
    
    Philosophy: The athlete owns the plan. The system generates it,
    the athlete follows/adjusts it, and learns from it.
    """
    __tablename__ = "training_plan"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False)  # Index in __table_args__
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Plan metadata
    name = Column(Text, nullable=False)  # e.g., "Boston Marathon 2026 Build"
    status = Column(Text, default="active", nullable=False)  # 'draft', 'active', 'completed', 'cancelled'
    
    # Goal race details
    goal_race_name = Column(Text, nullable=True)  # e.g., "Boston Marathon"
    goal_race_date = Column(Date, nullable=False)
    goal_race_distance_m = Column(Integer, nullable=False)  # Distance in meters
    goal_time_seconds = Column(Integer, nullable=True)  # Target finish time
    
    # Plan structure
    plan_start_date = Column(Date, nullable=False)
    plan_end_date = Column(Date, nullable=False)  # Usually goal_race_date
    total_weeks = Column(Integer, nullable=False)
    
    # Current fitness baseline (at plan creation)
    baseline_rpi = Column('baseline_vdot', Float, nullable=True)  # DB column: baseline_vdot for backward compat
    baseline_weekly_volume_km = Column(Float, nullable=True)
    
    # Plan generation metadata
    plan_type = Column(Text, nullable=False)  # 'base_build', '5k', '10k', 'half_marathon', 'marathon'
    generation_method = Column(Text, default="ai", nullable=False)  # 'ai', 'template', 'custom'
    methodology_blend = Column(JSONB, nullable=True)  # Which coaching methodologies influenced this plan
    
    __table_args__ = (
        Index("ix_training_plan_athlete_id", "athlete_id"),
        Index("ix_training_plan_status", "status"),
        Index("ix_training_plan_goal_date", "goal_race_date"),
    )

class PlannedWorkout(Base):
    """
    A single planned workout within a training plan.
    
    Represents what the athlete SHOULD do on a given day.
    Compared against actual Activity records to track adherence.
    
    Workout types align with our methodology knowledge base.
    """
    __tablename__ = "planned_workout"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("training_plan.id"), nullable=False)  # Index in __table_args__
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False)  # Index in __table_args__
    
    # Scheduling
    scheduled_date = Column(Date, nullable=False)
    week_number = Column(Integer, nullable=False)  # Week 1, 2, 3... of the plan
    day_of_week = Column(Integer, nullable=False)  # 0=Sunday, 6=Saturday
    
    # Workout definition
    # Canonical naming: avoid ambiguous "tempo" (use threshold + subtype/segments instead).
    workout_type = Column(Text, nullable=False)  # 'easy', 'long', 'threshold', 'threshold_intervals', 'intervals', 'recovery', 'rest', 'race'
    workout_subtype = Column(Text, nullable=True)  # e.g., 'progression', 'fartlek', 'cruise_intervals'
    title = Column(Text, nullable=False)  # e.g., "Easy Run", "Long Run with Fast Finish"
    description = Column(Text, nullable=True)  # Detailed workout description
    
    # Training phase context
    phase = Column(Text, nullable=False)  # 'base', 'build', 'peak', 'taper', 'recovery'
    phase_week = Column(Integer, nullable=True)  # Week 1, 2, 3... within the phase
    
    # Target metrics (what to aim for)
    target_duration_minutes = Column(Integer, nullable=True)
    target_distance_km = Column(Float, nullable=True)
    target_pace_per_km_seconds = Column(Integer, nullable=True)  # Target pace range (low)
    target_pace_per_km_seconds_max = Column(Integer, nullable=True)  # Target pace range (high)
    target_hr_min = Column(Integer, nullable=True)
    target_hr_max = Column(Integer, nullable=True)
    
    # Structured workout segments (for intervals, etc.)
    # Format: [{"type": "warmup", "duration_min": 10}, {"type": "interval", "reps": 6, "distance_m": 800, "rest_min": 2}, ...]
    segments = Column(JSONB, nullable=True)

    # Workout fluency: registry variant id when framework generation resolves one (nullable)
    workout_variant_id = Column(Text, nullable=True)
    
    # Execution tracking
    completed = Column(Boolean, default=False, nullable=False)
    completed_activity_id = Column(UUID(as_uuid=True), ForeignKey("activity.id"), nullable=True)
    skipped = Column(Boolean, default=False, nullable=False)
    skip_reason = Column(Text, nullable=True)

    # Phase 2B: Self-regulation tracking
    # What the athlete actually did (may differ from plan)
    actual_workout_type = Column(Text, nullable=True)          # What they actually did (e.g., "tempo_run" when "easy" was planned)
    planned_vs_actual_delta = Column(JSONB, nullable=True)     # {distance_delta_km, pace_delta_s, intensity_delta, type_changed}
    readiness_at_execution = Column(Float, nullable=True)      # Readiness score when workout was done
    execution_state = Column(Text, nullable=True)              # SCHEDULED, COMPLETED, SKIPPED, MODIFIED_BY_ATHLETE

    # Notes
    coach_notes = Column(Text, nullable=True)  # AI-generated guidance
    athlete_notes = Column(Text, nullable=True)  # Athlete's own notes
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        Index("ix_planned_workout_plan_id", "plan_id"),
        Index("ix_planned_workout_athlete_id", "athlete_id"),
        Index("ix_planned_workout_date", "scheduled_date"),
        Index("ix_planned_workout_plan_date", "plan_id", "scheduled_date"),
        UniqueConstraint('plan_id', 'scheduled_date', name='uq_planned_workout_plan_date'),
    )

class PlanModificationLog(Base):
    """
    Audit log for all training plan modifications.
    
    Tracks every change made to plans and workouts with full before/after state.
    Enables rollback, analytics, and accountability.
    
    Actions:
    - 'move_workout': Workout moved to new date
    - 'edit_workout': Workout details changed (type, distance, etc.)
    - 'delete_workout': Workout marked as skipped
    - 'add_workout': New workout added
    - 'swap_workouts': Two workouts swapped
    - 'adjust_load': Weekly load adjusted
    - 'pause_plan': Plan paused
    - 'resume_plan': Plan resumed
    """
    __tablename__ = "plan_modification_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("training_plan.id"), nullable=False)
    workout_id = Column(UUID(as_uuid=True), ForeignKey("planned_workout.id"), nullable=True)  # Null for plan-level actions
    
    # Action details
    action = Column(Text, nullable=False)  # move_workout, edit_workout, delete_workout, add_workout, etc.
    
    # State snapshots (for rollback capability)
    before_state = Column(JSONB, nullable=True)  # JSON snapshot before change
    after_state = Column(JSONB, nullable=True)   # JSON snapshot after change
    
    # Context
    reason = Column(Text, nullable=True)  # Optional athlete-provided reason
    source = Column(Text, default="web", nullable=False)  # 'web', 'mobile', 'api', 'coach'
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ip_address = Column(Text, nullable=True)  # For security auditing
    user_agent = Column(Text, nullable=True)  # Browser/device info
    
    __table_args__ = (
        Index("ix_plan_modification_log_athlete_id", "athlete_id"),
        Index("ix_plan_modification_log_plan_id", "plan_id"),
        Index("ix_plan_modification_log_created_at", "created_at"),
    )

class TrainingAvailability(Base):
    """
    Training availability grid for athletes.
    
    Tracks when athletes are available and prefer to train.
    Used to inform custom training plan generation.
    
    Grid structure:
    - Day of week: Sunday (0) through Saturday (6)
    - Time block: 'morning', 'afternoon', 'evening'
    - Status: 'available' (can train), 'preferred' (ideal time), 'unavailable' (cannot train)
    
    This enables smart scheduling that respects athlete's life constraints
    while optimizing training distribution.
    """
    __tablename__ = "training_availability"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False)  # Index in __table_args__
    
    # Day of week: 0=Sunday, 1=Monday, ..., 6=Saturday
    day_of_week = Column(Integer, nullable=False)  # 0-6
    
    # Time block: 'morning', 'afternoon', 'evening'
    time_block = Column(Text, nullable=False)  # 'morning', 'afternoon', 'evening'
    
    # Status: 'available', 'preferred', 'unavailable'
    status = Column(Text, nullable=False, default='unavailable')  # 'available', 'preferred', 'unavailable'
    
    # Optional notes for this slot
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        Index("ix_training_availability_athlete_id", "athlete_id"),
        Index("ix_training_availability_day_block", "athlete_id", "day_of_week", "time_block"),
        UniqueConstraint('athlete_id', 'day_of_week', 'time_block', name='uq_training_availability_athlete_day_block'),
    )


# =============================================================================
# CALENDAR SYSTEM MODELS
# =============================================================================

class CalendarNote(Base):
    """
    Flexible notes tied to calendar dates.
    
    Supports multiple note types:
    - pre_workout: Before the run (sleep, energy, stress, weather)
    - post_workout: After the run (feel, pain, fueling, mental)
    - free_text: General notes
    - voice_memo: Transcribed voice notes
    
    Notes are the athlete's voice in the system. They provide context
    that numbers alone cannot capture.
    """
    __tablename__ = "calendar_note"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False)
    
    # Date this note is attached to
    note_date = Column(Date, nullable=False)
    
    # Note type: 'pre_workout', 'post_workout', 'free_text', 'voice_memo'
    note_type = Column(Text, nullable=False)
    
    # Structured content for pre/post workout
    # Example pre: {"sleep_hours": 7.5, "energy": "good", "stress": "low", "weather": "52F sunny"}
    # Example post: {"feel": "strong", "pain": null, "fueling": "gel at mile 12", "mental": "confident"}
    structured_data = Column(JSONB, nullable=True)
    
    # Free text content
    text_content = Column(Text, nullable=True)
    
    # Voice memo reference (if applicable)
    voice_memo_url = Column(Text, nullable=True)
    voice_memo_transcript = Column(Text, nullable=True)
    
    # Optional link to specific activity
    activity_id = Column(UUID(as_uuid=True), ForeignKey("activity.id"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        Index("ix_calendar_note_athlete_id", "athlete_id"),
        Index("ix_calendar_note_date", "note_date"),
        Index("ix_calendar_note_athlete_date", "athlete_id", "note_date"),
    )

class CalendarInsight(Base):
    """
    Insights generated for specific calendar dates.
    
    Stores auto-generated insights tied to days/activities.
    These appear on the calendar and in day detail views.
    
    Insight types:
    - workout_comparison: How this workout compares to similar past workouts
    - efficiency_trend: EF changes over time
    - pattern_detected: Weekly/monthly patterns
    - achievement: PBs, milestones, streaks
    - warning: Recovery concerns, injury risk signals
    """
    __tablename__ = "calendar_insight"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False)
    
    # Date this insight is for
    insight_date = Column(Date, nullable=False)
    
    # Insight type
    insight_type = Column(Text, nullable=False)  # 'workout_comparison', 'efficiency_trend', 'pattern_detected', 'achievement', 'warning'
    
    # Priority for display (higher = more important)
    priority = Column(Integer, default=50, nullable=False)  # 1-100
    
    # The insight content
    title = Column(Text, nullable=False)  # Short title for display
    content = Column(Text, nullable=False)  # Full insight text
    
    # Optional link to activity
    activity_id = Column(UUID(as_uuid=True), ForeignKey("activity.id"), nullable=True)
    
    # Metadata (for re-generation, tracking)
    generation_data = Column(JSONB, nullable=True)  # Data used to generate this insight
    
    # Status
    is_dismissed = Column(Boolean, default=False, nullable=False)  # User dismissed this insight
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    __table_args__ = (
        Index("ix_calendar_insight_athlete_id", "athlete_id"),
        Index("ix_calendar_insight_date", "insight_date"),
        Index("ix_calendar_insight_athlete_date", "athlete_id", "insight_date"),
        Index("ix_calendar_insight_type", "insight_type"),
    )


# ============================================================================
# PLAN GENERATION FRAMEWORK MODELS
# ============================================================================

class WorkoutDefinition(Base):
    """
    Workout definitions for the plugin registry.
    
    Allows adding new workout types without code changes.
    """
    __tablename__ = "workout_definition"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(Text, unique=True, nullable=False, index=True)  # e.g., "progressive_long_run"
    name = Column(Text, nullable=False)  # "Progressive Long Run"
    category = Column(Text, nullable=False, index=True)  # "long_run", "threshold", "easy"
    description = Column(Text, nullable=True)
    
    # Applicability
    applicable_distances = Column(JSONB, nullable=True)  # ["marathon", "half_marathon"]
    applicable_phases = Column(JSONB, nullable=True)  # ["build", "specific"]
    
    # Structure
    structure_template = Column(JSONB, nullable=True)  # Parameterized workout structure
    scaling_rules = Column(JSONB, nullable=True)  # How to scale by tier
    
    # Option A/B pairing
    option_b_key = Column(Text, nullable=True)  # Key of alternative workout
    
    # Metadata
    purpose = Column(Text, nullable=True)  # Physiological purpose
    when_to_use = Column(Text, nullable=True)  # Selection criteria
    
    # Status
    active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class PhaseDefinition(Base):
    """
    Phase definitions for the plugin registry.
    """
    __tablename__ = "phase_definition"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(Text, unique=True, nullable=False, index=True)  # e.g., "base_speed"
    name = Column(Text, nullable=False)  # "Base + Speed"
    
    # Applicability
    applicable_distances = Column(JSONB, nullable=True)  # ["marathon", "half_marathon"]
    
    # Duration constraints
    default_weeks = Column(Integer, nullable=False)
    min_weeks = Column(Integer, nullable=False)
    max_weeks = Column(Integer, nullable=False)
    
    # Training focus
    focus = Column(Text, nullable=True)  # "aerobic_foundation", "threshold_development"
    quality_sessions_per_week = Column(Integer, default=0, nullable=False)
    allowed_workout_types = Column(JSONB, nullable=True)  # ["easy", "threshold", "long"]
    
    # Status
    active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class ScalingRule(Base):
    """
    Scaling rules for the plugin registry.
    """
    __tablename__ = "scaling_rule"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(Text, unique=True, nullable=False, index=True)
    name = Column(Text, nullable=False)
    category = Column(Text, nullable=False, index=True)  # "scaling", "selection", "adaptation"
    
    # Rule logic (JSON-encoded)
    rule_logic = Column(JSONB, nullable=True)
    
    # Status
    active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class PlanTemplate(Base):
    """
    Base templates for standard plans.
    """
    __tablename__ = "plan_template"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Identification
    key = Column(Text, unique=True, nullable=False, index=True)  # "marathon_18w_mid"
    name = Column(Text, nullable=False)  # "18-Week Marathon (Mid Volume)"
    
    # Classification
    distance = Column(Text, nullable=False, index=True)  # "marathon", "half", "10k", "5k"
    duration_weeks = Column(Integer, nullable=False)
    volume_tier = Column(Text, nullable=False, index=True)  # "builder", "low", "mid", "high"
    
    # Volume parameters
    starting_volume_miles = Column(Float, nullable=False)
    peak_volume_miles = Column(Float, nullable=False)
    long_run_start_miles = Column(Float, nullable=False)
    long_run_peak_miles = Column(Float, nullable=False)
    
    # Structure
    phases = Column(JSONB, nullable=False)  # Phase definitions for this template
    weekly_structures = Column(JSONB, nullable=True)  # By days_per_week
    
    # Status
    active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        Index("ix_plan_template_distance_duration", "distance", "duration_weeks"),
    )


# =============================================================================
# N=1 LEARNING ENGINE MODELS (ADR-036)
# =============================================================================

class PlanAdaptationProposal(Base):
    """Proposed plan adjustment from the adaptive replanner.

    Lifecycle: pending → accepted | rejected | expired.
    The athlete sees a diff card on the home page and decides.
    Silence = keep original (expires_at enforced by nightly task).
    """
    __tablename__ = "plan_adaptation_proposal"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("training_plan.id"), nullable=False)

    trigger_type = Column(Text, nullable=False)
    trigger_detail = Column(JSONB, nullable=True)

    proposed_changes = Column(JSONB, nullable=False)
    original_snapshot = Column(JSONB, nullable=False)
    affected_week_start = Column(Integer, nullable=False)
    affected_week_end = Column(Integer, nullable=False)

    status = Column(Text, nullable=False, server_default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    responded_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    adaptation_number = Column(Integer, nullable=False, server_default="1")

    __table_args__ = (
        Index("ix_pap_athlete_status", "athlete_id", "status"),
        Index("ix_pap_plan_id", "plan_id"),
        Index("ix_pap_expires_at", "expires_at"),
    )

class PlanPreview(Base):
    """Plan Engine V2 output — preview plans stored as JSON.

    V2 writes here, leaving V1's training_plan untouched.
    Each row is one generated plan (one block). Build-over-build
    seeding reads peak_workout_state from the previous block.
    """
    __tablename__ = "plan_preview"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id", ondelete="CASCADE"),
                        nullable=False, index=True)

    mode = Column(Text, nullable=False)
    goal_event = Column(Text, nullable=True)
    block_number = Column(Integer, nullable=False, server_default="1")
    total_weeks = Column(Integer, nullable=False)

    plan_json = Column(JSONB, nullable=False)

    peak_workout_state = Column(JSONB, nullable=True)

    engine_version = Column(Text, nullable=False, server_default="v2")
    anchor_type = Column(Text, nullable=True)
    athlete_type = Column(Text, nullable=True)
    phase_structure = Column(JSONB, nullable=True)
    pace_ladder = Column(JSONB, nullable=True)

    status = Column(Text, nullable=False, server_default="preview")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    promoted_plan_id = Column(UUID(as_uuid=True),
                              ForeignKey("training_plan.id", ondelete="SET NULL"),
                              nullable=True)

    __table_args__ = (
        Index("ix_plan_preview_athlete_status", "athlete_id", "status"),
    )

