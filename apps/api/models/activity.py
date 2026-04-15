from sqlalchemy import Column, Integer, BigInteger, Boolean, CheckConstraint, Float, Date, DateTime, ForeignKey, Numeric, Text, String, Index, UniqueConstraint, text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from core.database import Base
import uuid
from typing import Optional
from datetime import datetime, timezone

class Activity(Base):
    __tablename__ = "activity"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)
    name = Column(Text, nullable=True)  # Activity name from Strava (e.g., "Morning Run")
    start_time = Column(DateTime(timezone=True), nullable=False)
    sport = Column(Text, default="run", nullable=False)
    source = Column(Text, default="manual", nullable=False)
    duration_s = Column(Integer, nullable=True)
    distance_m = Column(Integer, nullable=True)
    avg_hr = Column(Integer, nullable=True)
    max_hr = Column(Integer, nullable=True)
    total_elevation_gain = Column(Numeric, nullable=True)
    average_speed = Column(Numeric, nullable=True)
    
    # --- INGESTION CONTRACT COLUMNS ---
    provider = Column(Text, index=True)
    external_activity_id = Column(Text, index=True)
    strava_workout_type_raw = Column(Integer, nullable=True)
    is_race_candidate = Column(Boolean, default=False)
    race_confidence = Column(Float, nullable=True)
    user_verified_race = Column(Boolean, nullable=True)
    
    # --- PERFORMANCE PHYSICS ENGINE COLUMNS ---
    performance_percentage = Column(Float, nullable=True)  # Age-graded performance % (International/WMA standard)
    performance_percentage_national = Column(Float, nullable=True)  # Age-graded performance % (National standard)
    
    # --- WORKOUT CLASSIFICATION ---
    workout_type = Column(Text, nullable=True, index=True)  # e.g., 'easy_run', 'tempo_run', 'long_run', 'race'
    workout_zone = Column(Text, nullable=True)  # e.g., 'recovery', 'endurance', 'stamina', 'speed'
    workout_confidence = Column(Float, nullable=True)  # Classification confidence 0-1
    intensity_score = Column(Float, nullable=True)  # Calculated intensity 0-100
    
    # --- ENVIRONMENTAL CONTEXT ---
    temperature_f = Column(Float, nullable=True)  # Temperature at start
    humidity_pct = Column(Float, nullable=True)  # Humidity percentage
    weather_condition = Column(Text, nullable=True)  # e.g., 'clear', 'cloudy', 'rain'
    dew_point_f = Column(Float, nullable=True)  # Dew point in °F (Magnus formula from temp+humidity)
    heat_adjustment_pct = Column(Float, nullable=True)  # Pace slowdown fraction from Temp+DewPoint model

    # --- ACTIVITY SHAPE (Living Fingerprint) ---
    run_shape = Column(JSONB, nullable=True)  # RunShape.to_dict() — phases, accelerations, summary
    shape_sentence = Column(Text, nullable=True)  # Natural language shape description
    athlete_title = Column(Text, nullable=True)  # Athlete-edited display title (overrides shape_sentence)

    # --- INGESTION PROGRESS MARKERS ---
    # Strava only returns `best_efforts` when an activity sets PRs; we still need a
    # deterministic marker for "details fetched and extraction attempted".
    best_efforts_extracted_at = Column(DateTime(timezone=True), nullable=True)

    # --- STREAM FETCH LIFECYCLE (ADR-063) ---
    # Six-state machine: pending → fetching → success/failed/deferred/unavailable
    # See docs/adr/ADR-063-activity-stream-storage-and-fetch-lifecycle.md
    stream_fetch_status = Column(Text, nullable=False, default="pending", server_default="pending")
    stream_fetch_attempted_at = Column(DateTime(timezone=True), nullable=True)
    stream_fetch_error = Column(Text, nullable=True)
    stream_fetch_retry_count = Column(Integer, nullable=False, default=0, server_default="0")
    stream_fetch_deferred_until = Column(DateTime(timezone=True), nullable=True)

    # --- CROSS-TRAINING METADATA ---
    garmin_activity_type = Column(Text, nullable=True)
    cadence_unit = Column(Text, nullable=True)
    session_detail = Column(JSONB, nullable=True)
    strength_session_type = Column(Text, nullable=True)

    # --- GARMIN ACTIVITY OFFICIAL FIELDS (D3 / garmin_004) ---
    # From the official ClientActivity JSON schema (portal verified Feb 2026).
    # garmin_activity_id is Garmin's native int64 — different from summaryId
    # stored in external_activity_id. Used to link summary → detail payloads.
    garmin_activity_id = Column(BigInteger, nullable=True)
    avg_pace_min_per_km = Column(Float, nullable=True)
    max_pace_min_per_km = Column(Float, nullable=True)
    steps = Column(Integer, nullable=True)          # per-activity step count
    device_name = Column(Text, nullable=True)
    start_lat = Column(Float, nullable=True)
    start_lng = Column(Float, nullable=True)

    # --- GARMIN RUNNING DYNAMICS (D1.2) ---
    # Columns present in DB (nullable) but NOT populated by Tier 1 adapter.
    # Running dynamics exist only in FIT files, not in the JSON Activity API.
    # The D4.3 live webhook capture will confirm if any appear in push payloads.
    avg_cadence = Column(Integer, nullable=True)
    max_cadence = Column(Integer, nullable=True)
    avg_stride_length_m = Column(Float, nullable=True)
    avg_ground_contact_ms = Column(Float, nullable=True)
    avg_ground_contact_balance_pct = Column(Float, nullable=True)
    avg_vertical_oscillation_cm = Column(Float, nullable=True)
    avg_vertical_ratio_pct = Column(Float, nullable=True)

    # --- GARMIN POWER ---
    avg_power_w = Column(Integer, nullable=True)
    max_power_w = Column(Integer, nullable=True)

    # --- GARMIN EFFORT / GRADE ---
    avg_gap_min_per_mile = Column(Float, nullable=True)
    total_descent_m = Column(Float, nullable=True)

    # --- GARMIN TRAINING EFFECT ---
    # INFORMATIONAL ONLY — never use in training load calculations.
    # These are Garmin's proprietary model outputs. StrideIQ uses its own
    # load model. Storing for display only.
    garmin_aerobic_te = Column(Float, nullable=True)
    garmin_anaerobic_te = Column(Float, nullable=True)
    garmin_te_label = Column(Text, nullable=True)

    # --- GARMIN SELF-EVALUATION (low-fidelity — [L3]) ---
    # Athletes frequently click through post-activity ratings without genuine
    # engagement. Import if present; display with caveat; never use in
    # load or readiness calculations.
    garmin_feel = Column(Text, nullable=True)
    garmin_perceived_effort = Column(Integer, nullable=True)

    # --- GARMIN WELLNESS CROSSOVER ---
    garmin_body_battery_impact = Column(Integer, nullable=True)

    # --- PRE-ACTIVITY WELLNESS SNAPSHOT ---
    pre_sleep_h = Column(Float, nullable=True)
    pre_sleep_score = Column(Integer, nullable=True)
    pre_resting_hr = Column(Integer, nullable=True)
    pre_recovery_hrv = Column(Integer, nullable=True)
    pre_overnight_hrv = Column(Integer, nullable=True)

    # --- TIMING / ENERGY ---
    moving_time_s = Column(Integer, nullable=True)
    max_speed = Column(Float, nullable=True)
    active_kcal = Column(Integer, nullable=True)

    # --- RUNTOON SHARE FLOW ---
    share_dismissed_at = Column(DateTime(timezone=True), nullable=True)

    # --- DUPLICATE DETECTION (Racing Fingerprint Pre-Work P1) ---
    is_duplicate = Column(Boolean, default=False, nullable=False, server_default="false", index=True)
    duplicate_of_id = Column(UUID(as_uuid=True), ForeignKey("activity.id"), nullable=True)

    # --- THE ARMOR: Unique Constraint prevents duplicates at the DB level ---
    __table_args__ = (
        UniqueConstraint('provider', 'external_activity_id', name='uq_activity_provider_external_id'),
        CheckConstraint(
            "stream_fetch_status IN ('pending', 'fetching', 'success', 'failed', 'deferred', 'unavailable')",
            name='ck_activity_stream_fetch_status',
        ),
    )
    
    # --- RELATIONSHIPS ---
    athlete = relationship("Athlete", back_populates="activities")
    splits = relationship("ActivitySplit", back_populates="activity", lazy="dynamic", order_by="ActivitySplit.split_number")
    stream = relationship("ActivityStream", back_populates="activity", uselist=False)
    strength_exercise_sets = relationship("StrengthExerciseSet", back_populates="activity", cascade="all, delete-orphan")

    @property
    def pace_per_mile(self) -> Optional[float]:
        """
        Calculate pace per mile in minutes from average_speed (m/s).
        Formula: 26.8224 / average_speed
        """
        if self.average_speed is None or float(self.average_speed) == 0:
            return None
        return 26.8224 / float(self.average_speed)

class StrengthExerciseSet(Base):
    """Individual exercise set within a strength training activity.

    Parsed from Garmin exerciseSets API response. Movement pattern and muscle
    group are classified via the taxonomy in services/strength_taxonomy.py.
    Estimated 1RM is computed at write time using the Epley formula.
    """
    __tablename__ = "strength_exercise_set"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    activity_id = Column(UUID(as_uuid=True), ForeignKey("activity.id", ondelete="CASCADE"), nullable=False, index=True)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id", ondelete="CASCADE"), nullable=False)
    set_order = Column(Integer, nullable=False)
    exercise_name_raw = Column(Text, nullable=False)
    exercise_category = Column(Text, nullable=False)
    movement_pattern = Column(Text, nullable=False)
    muscle_group = Column(Text, nullable=True)
    is_unilateral = Column(Boolean, default=False, nullable=False)
    set_type = Column(Text, nullable=False, default="active")
    reps = Column(Integer, nullable=True)
    weight_kg = Column(Float, nullable=True)
    duration_s = Column(Float, nullable=True)
    estimated_1rm_kg = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_strength_set_athlete_pattern", "athlete_id", "movement_pattern"),
    )

    activity = relationship("Activity", back_populates="strength_exercise_sets")
    athlete = relationship("Athlete")

class PerformanceEvent(Base):
    __tablename__ = "performance_event"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"),
                        nullable=False, index=True)
    activity_id = Column(UUID(as_uuid=True), ForeignKey("activity.id"),
                         nullable=False, index=True)

    distance_category = Column(Text, nullable=False)
    event_date = Column(Date, nullable=False, index=True)
    event_type = Column(Text, nullable=False)

    # Performance
    time_seconds = Column(Integer, nullable=False)
    chip_time_seconds = Column(Integer, nullable=True)
    pace_per_mile = Column(Float, nullable=True)
    rpi_at_event = Column(Float, nullable=True)
    performance_percentage = Column(Float, nullable=True)
    is_personal_best = Column(Boolean, default=False)

    # Training state at event
    ctl_at_event = Column(Float, nullable=True)
    atl_at_event = Column(Float, nullable=True)
    tsb_at_event = Column(Float, nullable=True)
    fitness_relative_performance = Column(Float, nullable=True)

    # Block signature (the fingerprint)
    block_signature = Column(JSONB, nullable=True)

    # Campaign data (replaces fixed-window block_signature for analysis)
    campaign_data = Column(JSONB, nullable=True)

    @property
    def effective_time_seconds(self) -> int:
        """Chip time if available, otherwise GPS time."""
        return self.chip_time_seconds or self.time_seconds

    # Wellness state
    pre_event_wellness = Column(JSONB, nullable=True)

    # Classification
    race_role = Column(Text, nullable=True)
    user_classified_role = Column(Text, nullable=True)
    cycle_id = Column(UUID(as_uuid=True), nullable=True)

    # Source / verification
    detection_source = Column(Text, nullable=False, default='algorithm')
    detection_confidence = Column(Float, nullable=True)
    user_confirmed = Column(Boolean, nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now())
    computation_version = Column(Integer, nullable=False, default=1)

    __table_args__ = (
        UniqueConstraint('athlete_id', 'activity_id',
                         name='uq_performance_event_athlete_activity'),
        Index('ix_performance_event_athlete_date',
              'athlete_id', 'event_date'),
    )

    athlete = relationship("Athlete")
    activity = relationship("Activity")

class ActivitySplit(Base):
    __tablename__ = "activity_split"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    activity_id = Column(UUID(as_uuid=True), ForeignKey("activity.id"), nullable=False)  # Index in __table_args__
    split_number = Column(Integer, nullable=False)
    distance = Column(Numeric, nullable=True)
    elapsed_time = Column(Integer, nullable=True)
    moving_time = Column(Integer, nullable=True)
    average_heartrate = Column(Integer, nullable=True)
    max_heartrate = Column(Integer, nullable=True)
    average_cadence = Column(Numeric, nullable=True)
    gap_seconds_per_mile = Column(Numeric, nullable=True)  # Grade Adjusted Pace (NGP) in seconds per mile
    lap_type = Column(Text, nullable=True)  # warm_up, work, rest, cool_down
    interval_number = Column(Integer, nullable=True)  # 1-indexed for work intervals only

    # --- RELATIONSHIPS ---
    activity = relationship("Activity", back_populates="splits")

    # --- THE ARMOR: Prevent duplicate splits for the same activity ---
    __table_args__ = (
        Index("ix_activity_split_activity_id", "activity_id"),
        UniqueConstraint('activity_id', 'split_number', name='uq_activity_split_number'),
    )

class ActivityStream(Base):
    """
    Per-second resolution stream data for an activity (ADR-063).

    Stores raw time-series from Strava (or Garmin) as a single JSONB blob
    containing all channels.  One row per activity.  The frontend reads the
    entire blob for chart rendering; the coach tool reads it for stream
    analysis.

    Example stream_data:
        {
            "time": [0, 1, 2, ...],
            "distance": [0.0, 2.8, 5.6, ...],
            "heartrate": [140, 141, 142, ...],
            "velocity_smooth": [3.1, 3.2, 3.1, ...],
            "altitude": [100.5, 100.7, 101.0, ...],
            "grade_smooth": [0.0, 0.2, 0.5, ...],
            "cadence": [88, 89, 88, ...],
            "latlng": [[38.60, -122.86], [38.61, -122.87], ...]
        }
    """
    __tablename__ = "activity_stream"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    activity_id = Column(UUID(as_uuid=True), ForeignKey("activity.id"), nullable=False)

    # Dict of channel_name → array of values
    stream_data = Column(JSONB, nullable=False)

    # Which channels are present (cheap filtering without parsing JSONB)
    channels_available = Column(JSONB, nullable=False, default=list)

    # Number of data points (length of time array)
    point_count = Column(Integer, nullable=False)

    # Provenance
    source = Column(Text, nullable=False, default="strava")
    fetched_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # --- RELATIONSHIPS ---
    activity = relationship("Activity", back_populates="stream")

    # --- THE ARMOR: One stream row per activity ---
    __table_args__ = (
        UniqueConstraint("activity_id", name="uq_activity_stream_activity_id"),
        Index("ix_activity_stream_activity_id", "activity_id"),
    )

class PersonalBest(Base):
    """
    Personal Best (PB) records for an athlete across standard distances.
    
    Tracks fastest time for each distance category, allowing for GPS tolerance
    (e.g., 5K races may be 3.08-3.3 miles due to measurement variations).
    """
    __tablename__ = "personal_best"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False)  # Index in __table_args__
    
    # Distance category (standardized name)
    distance_category = Column(Text, nullable=False)  # '400m', '800m', 'mile', '2mile', '5k', '10k', '15k', '25k', '30k', '50k', '100k', 'half_marathon', 'marathon'
    
    # The actual distance and time from the activity
    distance_meters = Column(Integer, nullable=False)  # Actual distance in meters
    time_seconds = Column(Integer, nullable=False)  # Fastest time in seconds
    pace_per_mile = Column(Float, nullable=True)  # Calculated pace per mile
    
    # Link to the activity that set this PB
    activity_id = Column(UUID(as_uuid=True), ForeignKey("activity.id"), nullable=False)
    
    # When this PB was set
    achieved_at = Column(DateTime(timezone=True), nullable=False)
    
    # Metadata
    is_race = Column(Boolean, default=False)  # Was this PB set in a race?
    age_at_achievement = Column(Integer, nullable=True)  # Athlete's age when PB was set
    
    __table_args__ = (
        Index("ix_personal_best_athlete_id", "athlete_id"),
        Index("ix_personal_best_distance_category", "distance_category"),
        UniqueConstraint('athlete_id', 'distance_category', name='uq_personal_best_athlete_distance'),
    )

class BestEffort(Base):
    """
    Individual best effort records from Strava.
    
    Strava calculates 'best efforts' for standard distances WITHIN any activity.
    For example, your fastest mile might be from within a 10k run.
    
    This table stores ALL efforts, not just the fastest. PersonalBest is then
    a simple aggregation: MIN(elapsed_time) per distance_category.
    
    Architecture:
    - Populated during Strava activity sync (extract best_efforts from API response)
    - PersonalBest table is regenerated by aggregating this table
    - Enables historical tracking, trends, age-grading, etc.
    """
    __tablename__ = "best_effort"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False)
    activity_id = Column(UUID(as_uuid=True), ForeignKey("activity.id"), nullable=False)
    
    # Distance category (standardized)
    distance_category = Column(Text, nullable=False)  # 'mile', '5k', '10k', 'half_marathon', 'marathon', etc.
    
    # The effort data
    distance_meters = Column(Integer, nullable=False)
    elapsed_time = Column(Integer, nullable=False)  # Seconds
    
    # When this effort occurred
    achieved_at = Column(DateTime(timezone=True), nullable=False)
    
    # Source tracking
    strava_effort_id = Column(BigInteger, nullable=True)  # Strava's best effort ID (BigInteger for large Strava IDs)
    
    __table_args__ = (
        Index("ix_best_effort_athlete_id", "athlete_id"),
        Index("ix_best_effort_activity_id", "activity_id"),
        Index("ix_best_effort_distance_category", "distance_category"),
        # Prevent duplicate efforts from same Strava source
        UniqueConstraint('activity_id', 'strava_effort_id', name='uq_best_effort_activity_strava'),
    )

class ActivityFeedback(Base):
    """
    Perceptual feedback for activities.
    
    Captures subjective data (perceived effort, leg feel, mood) to correlate
    with objective performance metrics. This builds the perception ↔ performance
    correlation dataset that is a unique signal in our system.
    
    Research-backed fields:
    - RPE (Rate of Perceived Exertion): 1-10 scale (modified Borg scale)
    - Leg feel: Categorical (fresh, normal, tired, heavy, sore)
    - Mood/energy: Pre and post activity
    - Notes: Free-form context
    
    Timing: Collected immediately post-run or within 24 hours for accuracy.
    """
    __tablename__ = "activity_feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    activity_id = Column(UUID(as_uuid=True), ForeignKey("activity.id"), nullable=False)  # Index in __table_args__
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False)  # Index in __table_args__
    
    # Perceived exertion (RPE 1-10 scale)
    perceived_effort = Column(Integer, nullable=True)  # 1-10 scale
    
    # Leg feel (categorical)
    leg_feel = Column(Text, nullable=True)  # 'fresh', 'normal', 'tired', 'heavy', 'sore', 'injured'
    
    # Mood/energy (pre and post)
    mood_pre = Column(Text, nullable=True)  # 'energetic', 'normal', 'tired', 'stressed', 'motivated', etc.
    mood_post = Column(Text, nullable=True)
    
    # Energy level (pre and post, 1-10 scale)
    energy_pre = Column(Integer, nullable=True)  # 1-10 scale
    energy_post = Column(Integer, nullable=True)  # 1-10 scale
    
    # Additional context
    notes = Column(Text, nullable=True)  # Free-form notes about the run
    
    # Timing
    submitted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        Index("ix_activity_feedback_activity_id", "activity_id"),
        Index("ix_activity_feedback_athlete_id", "athlete_id"),
        Index("ix_activity_feedback_submitted_at", "submitted_at"),
        UniqueConstraint('activity_id', name='uq_activity_feedback_activity'),  # One feedback per activity
    )

class ActivityReflection(Base):
    """
    RSI Layer 2 — Simplified post-run reflection.
    
    Three-option prompt: harder | expected | easier.
    Replaces the heavier PerceptionPrompt on the activity detail page.
    One reflection per activity. No free text in v1.
    """
    __tablename__ = "activity_reflection"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    activity_id = Column(UUID(as_uuid=True), ForeignKey("activity.id"), nullable=False)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False)
    response = Column(Text, nullable=False)  # 'harder' | 'expected' | 'easier'
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_activity_reflection_activity_id", "activity_id"),
        Index("ix_activity_reflection_athlete_id", "athlete_id"),
        UniqueConstraint('activity_id', name='uq_activity_reflection_activity'),
        CheckConstraint("response IN ('harder', 'expected', 'easier')", name='ck_reflection_response_enum'),
    )

class CachedStreamAnalysis(Base):
    """
    RSI — Cached StreamAnalysisResult for an activity.

    Spec decision (locked 2026-02-14): "Cache full StreamAnalysisResult in DB.
    Compute once at ingest time, serve on every Home + Activity page load.
    Recompute only on: new stream payload, analysis version bump, manual reprocess."

    The result_json column stores the full asdict(StreamAnalysisResult) so both
    /v1/home and /v1/activities/{id}/stream-analysis can serve without re-computing.
    """
    __tablename__ = "cached_stream_analysis"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    activity_id = Column(UUID(as_uuid=True), ForeignKey("activity.id"), nullable=False, unique=True)

    # Full StreamAnalysisResult as JSON (segments, drift, moments, etc.)
    result_json = Column(JSONB, nullable=False)

    # Deterministic invalidation: bump when analysis logic changes
    analysis_version = Column(Integer, nullable=False, default=1)

    # Provenance
    computed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_cached_stream_analysis_activity_id", "activity_id"),
    )

