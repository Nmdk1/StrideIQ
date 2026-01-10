from sqlalchemy import Column, Integer, Boolean, Float, Date, DateTime, ForeignKey, Numeric, Text, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from core.database import Base
import uuid
from typing import Optional


class Athlete(Base):
    __tablename__ = "athlete"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    email = Column(Text, unique=True, nullable=True)
    password_hash = Column(Text, nullable=True)  # For authentication
    role = Column(Text, default="athlete", nullable=False)  # 'athlete', 'admin', 'coach'
    display_name = Column(Text, nullable=True)
    birthdate = Column(Date, nullable=True)
    sex = Column(Text, nullable=True)
    subscription_tier = Column(Text, default="free", nullable=False)
    
    # User preferences
    preferred_units = Column(Text, default="metric", nullable=False)  # 'metric' (km) or 'imperial' (miles)
    
    strava_athlete_id = Column(Integer, nullable=True)
    strava_access_token = Column(Text, nullable=True)  # Encrypted
    strava_refresh_token = Column(Text, nullable=True)  # Encrypted
    last_strava_sync = Column(DateTime(timezone=True), nullable=True)
    
    # Garmin Connect Integration
    garmin_username = Column(Text, nullable=True)  # For login (not encrypted - username only)
    garmin_password_encrypted = Column(Text, nullable=True)  # Encrypted password (for python-garminconnect)
    garmin_connected = Column(Boolean, default=False, nullable=False)
    last_garmin_sync = Column(DateTime(timezone=True), nullable=True)
    garmin_sync_enabled = Column(Boolean, default=True, nullable=False)
    
    # --- PERFORMANCE PHYSICS ENGINE: DERIVED SIGNALS (Manifesto Section 4) ---
    durability_index = Column(Float, nullable=True)  # Volume handling without injury (0-100+)
    recovery_half_life_hours = Column(Float, nullable=True)  # Recovery time post-intense effort (hours)
    consistency_index = Column(Float, nullable=True)  # Long-term training consistency (0-100)
    last_metrics_calculation = Column(DateTime(timezone=True), nullable=True)  # When metrics were last calculated
    
    # --- COMPLETE HEALTH & FITNESS MANAGEMENT ---
    height_cm = Column(Numeric, nullable=True)  # Height in centimeters (required for BMI)
    onboarding_stage = Column(Text, nullable=True)  # 'initial', 'basic_profile', 'goals', 'nutrition_setup', 'work_setup', 'complete'
    onboarding_completed = Column(Boolean, default=False, nullable=False)
    
    # --- PHYSIOLOGICAL BASELINE METRICS ---
    max_hr = Column(Integer, nullable=True)  # Maximum heart rate (bpm)
    resting_hr = Column(Integer, nullable=True)  # Resting heart rate (bpm)
    threshold_pace_per_km = Column(Float, nullable=True)  # Lactate threshold pace (seconds/km)
    threshold_hr = Column(Integer, nullable=True)  # Lactate threshold heart rate (bpm)
    vdot = Column(Float, nullable=True)  # Current VDOT (from recent race or test)
    
    # --- RUNNER TYPING (McMillan-inspired) ---
    # Automatically calculated from race history
    runner_type = Column(Text, nullable=True)  # 'speedster', 'endurance_monster', 'balanced'
    runner_type_confidence = Column(Float, nullable=True)  # 0-1, how confident we are in classification
    runner_type_last_calculated = Column(DateTime(timezone=True), nullable=True)
    
    # --- CONSISTENCY TRACKING (Green-inspired) ---
    current_streak_weeks = Column(Integer, default=0)  # Consecutive weeks meeting targets
    longest_streak_weeks = Column(Integer, default=0)  # All-time best streak
    last_streak_update = Column(DateTime(timezone=True), nullable=True)


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

    # --- THE ARMOR: Unique Constraint prevents duplicates at the DB level ---
    __table_args__ = (
        UniqueConstraint('provider', 'external_activity_id', name='uq_activity_provider_external_id'),
    )
    
    # --- RELATIONSHIPS ---
    splits = relationship("ActivitySplit", back_populates="activity", lazy="dynamic", order_by="ActivitySplit.split_number")

    @property
    def pace_per_mile(self) -> Optional[float]:
        """
        Calculate pace per mile in minutes from average_speed (m/s).
        Formula: 26.8224 / average_speed
        """
        if self.average_speed is None or float(self.average_speed) == 0:
            return None
        return 26.8224 / float(self.average_speed)


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
    
    # --- RELATIONSHIPS ---
    activity = relationship("Activity", back_populates="splits")

    # --- THE ARMOR: Prevent duplicate splits for the same activity ---
    __table_args__ = (
        Index("ix_activity_split_activity_id", "activity_id"),
        UniqueConstraint('activity_id', 'split_number', name='uq_activity_split_number'),
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


class DailyCheckin(Base):
    __tablename__ = "daily_checkin"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    sleep_h = Column(Numeric, nullable=True)  # Total sleep duration (time asleep only)
    stress_1_5 = Column(Integer, nullable=True)
    soreness_1_5 = Column(Integer, nullable=True)
    rpe_1_10 = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Garmin recovery metrics
    hrv_rmssd = Column(Numeric, nullable=True)  # HRV rMSSD value
    hrv_sdnn = Column(Numeric, nullable=True)  # HRV SDNN value
    resting_hr = Column(Integer, nullable=True)  # Resting heart rate (bpm)
    overnight_avg_hr = Column(Numeric, nullable=True)  # Overnight average HR (bpm)
    
    # --- ENJOYMENT TRACKING (Green-inspired) ---
    # "If you don't enjoy it, you won't be consistent"
    enjoyment_1_5 = Column(Integer, nullable=True)  # 1=dreaded it, 5=loved it
    
    # --- MINDSET TRACKING (Snow-inspired) ---
    # "The mind is the limiter of performance"
    confidence_1_5 = Column(Integer, nullable=True)  # 1=doubtful, 5=unstoppable
    motivation_1_5 = Column(Integer, nullable=True)  # 1=forcing myself, 5=fired up

    __table_args__ = (
        Index("uq_athlete_date", "athlete_id", "date", unique=True),
    )


class BodyComposition(Base):
    """
    Body composition tracking including BMI.
    
    BMI is calculated automatically when weight is recorded.
    Strategy: Internal metric initially, revealed when correlations are found.
    """
    __tablename__ = "body_composition"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    weight_kg = Column(Numeric, nullable=True)
    body_fat_pct = Column(Numeric, nullable=True)
    muscle_mass_kg = Column(Numeric, nullable=True)
    bmi = Column(Numeric, nullable=True)  # Calculated automatically: weight_kg / (height_m)²
    measurements_json = Column(JSONB, nullable=True)  # Flexible for various measurements
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_body_composition_athlete_date", "athlete_id", "date"),
        UniqueConstraint('athlete_id', 'date', name='uq_body_composition_athlete_date'),
    )


class NutritionEntry(Base):
    """
    Nutrition tracking for correlation analysis.
    
    Tracks nutrition pre/during/post activity and daily intake.
    Used to correlate nutrition patterns with performance efficiency.
    """
    __tablename__ = "nutrition_entry"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    entry_type = Column(Text, nullable=False)  # 'pre_activity', 'during_activity', 'post_activity', 'daily'
    activity_id = Column(UUID(as_uuid=True), ForeignKey("activity.id"), nullable=True)  # Links to activity if pre/during/post
    calories = Column(Numeric, nullable=True)
    protein_g = Column(Numeric, nullable=True)
    carbs_g = Column(Numeric, nullable=True)
    fat_g = Column(Numeric, nullable=True)
    fiber_g = Column(Numeric, nullable=True)
    timing = Column(DateTime(timezone=True), nullable=True)  # When consumed
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_nutrition_athlete_date", "athlete_id", "date"),
    )


class WorkPattern(Base):
    """
    Work pattern tracking for correlation analysis.
    
    Tracks work type, hours, and stress levels.
    Used to correlate work patterns with performance and recovery.
    """
    __tablename__ = "work_pattern"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    work_type = Column(Text, nullable=True)  # 'desk', 'physical', 'shift', 'travel', etc.
    hours_worked = Column(Numeric, nullable=True)
    stress_level = Column(Integer, nullable=True)  # 1-5 scale
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_work_pattern_athlete_date", "athlete_id", "date"),
        UniqueConstraint('athlete_id', 'date', name='uq_work_pattern_athlete_date'),
    )


class IntakeQuestionnaire(Base):
    """
    Waterfall intake questionnaire responses.
    
    Progressive information collection aligned with manifesto's continuous feedback loop.
    Stages: initial, basic_profile, goals, nutrition_setup, work_setup
    """
    __tablename__ = "intake_questionnaire"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)
    stage = Column(Text, nullable=False)  # 'initial', 'basic_profile', 'goals', 'nutrition_setup', 'work_setup'
    responses = Column(JSONB, nullable=False)  # Flexible structure for stage-specific questions
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_intake_questionnaire_athlete_stage", "athlete_id", "stage"),
    )


class CoachingKnowledgeEntry(Base):
    """
    Knowledge base entries for coaching principles.
    
    Stores extracted principles from books, articles, and other sources.
    Supports both vector search (embeddings) and structured queries.
    """
    __tablename__ = "coaching_knowledge_entry"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Source information
    source = Column(Text, nullable=False)  # Book title, URL, etc.
    methodology = Column(Text, nullable=False)  # "Daniels", "Pfitzinger", "Canova", etc.
    source_type = Column(Text, nullable=False)  # "book", "article", "research", etc.
    
    # Content
    text_chunk = Column(Text, nullable=False)  # Original text chunk
    extracted_principles = Column(Text, nullable=True)  # JSON: extracted structured principles
    principle_type = Column(Text, nullable=True)  # "formula", "periodization", "workout", etc.
    
    # Vector embedding (stored as text, will use pgvector extension)
    embedding = Column(Text, nullable=True)  # JSON array of floats, or use pgvector when available
    
    # Metadata
    metadata_json = Column(Text, nullable=True)  # JSON: additional metadata
    
    # Tags for cross-methodology querying (JSONB array of tag strings)
    tags = Column(JSONB, nullable=True)  # e.g., ["threshold", "long_run", "periodization"]
    
    __table_args__ = (
        Index("ix_knowledge_methodology", "methodology"),
        Index("ix_knowledge_principle_type", "principle_type"),
        Index("ix_knowledge_tags_gin", "tags", postgresql_using="gin"),  # GIN index for JSONB queries
    )


class CoachingRecommendation(Base):
    """
    Tracks coaching recommendations made to athletes.
    
    Enables learning system to track what works/doesn't work.
    """
    __tablename__ = "coaching_recommendation"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False)  # Index in __table_args__
    recommendation_type = Column(Text, nullable=False)  # "plan", "workout", "weekly_guidance", etc.
    
    # Recommendation details (JSON)
    recommendation_json = Column(Text, nullable=False)  # Full recommendation details
    
    # Knowledge base references
    knowledge_entry_ids = Column(Text, nullable=True)  # JSON array: IDs of knowledge entries used
    
    # Diagnostic signals at time of recommendation
    diagnostic_signals_json = Column(Text, nullable=True)  # JSON: diagnostic signals used
    
    # Status
    status = Column(Text, default="pending", nullable=False)  # "pending", "accepted", "rejected", "completed"
    outcome_tracked = Column(Boolean, default=False, nullable=False)
    
    # Internal blending rationale (INTERNAL ONLY - not exposed to clients)
    # Tracks which methodologies were blended and why
    # Example: {"methodologies": {"Daniels": 0.6, "Pfitzinger": 0.3, "Canova": 0.1}, 
    #           "reason": "Athlete responds well to Daniels pacing but needs Pfitz volume structure"}
    blending_rationale = Column(JSONB, nullable=True)
    
    __table_args__ = (
        Index("ix_recommendation_athlete_id", "athlete_id"),
        Index("ix_recommendation_type", "recommendation_type"),
        Index("ix_recommendation_status", "status"),
    )


class RecommendationOutcome(Base):
    """
    Tracks outcomes of coaching recommendations.
    
    Links recommendations to their results (efficiency changes, PBs, injuries, etc.)
    """
    __tablename__ = "recommendation_outcome"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tracked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    recommendation_id = Column(UUID(as_uuid=True), ForeignKey("coaching_recommendation.id"), nullable=False)  # Index in __table_args__
    
    outcome_type = Column(Text, nullable=False)  # "efficiency_change", "pb_achieved", "injury", "adherence", etc.
    outcome_data_json = Column(Text, nullable=False)  # JSON: outcome details
    
    # Metrics at outcome time
    efficiency_trend = Column(Float, nullable=True)
    pb_probability = Column(Float, nullable=True)
    other_metrics_json = Column(Text, nullable=True)  # JSON: other relevant metrics
    
    __table_args__ = (
        Index("ix_outcome_recommendation_id", "recommendation_id"),
        Index("ix_outcome_type", "outcome_type"),
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


class InsightFeedback(Base):
    """
    User feedback on insights to refine correlation engine thresholds.
    
    Tracks which insights users find helpful vs not helpful.
    Used to improve insight quality and correlation thresholds.
    """
    __tablename__ = "insight_feedback"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False)  # Index in __table_args__
    insight_type = Column(Text, nullable=False)  # 'correlation', 'activity_insight', 'efficiency_trend', etc.
    insight_id = Column(Text, nullable=True)  # ID of the insight (correlation ID, activity ID, etc.)
    insight_text = Column(Text, nullable=False)  # The actual insight text shown to user
    helpful = Column(Boolean, nullable=False)  # True = helpful, False = not helpful
    feedback_text = Column(Text, nullable=True)  # Optional user comment
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    __table_args__ = (
        Index("ix_insight_feedback_athlete_id", "athlete_id"),
        Index("ix_insight_feedback_insight_type", "insight_type"),
        Index("ix_insight_feedback_created_at", "created_at"),
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
    baseline_vdot = Column(Float, nullable=True)
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
    workout_type = Column(Text, nullable=False)  # 'easy', 'long', 'tempo', 'intervals', 'recovery', 'rest', 'race'
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
    
    # Execution tracking
    completed = Column(Boolean, default=False, nullable=False)
    completed_activity_id = Column(UUID(as_uuid=True), ForeignKey("activity.id"), nullable=True)
    skipped = Column(Boolean, default=False, nullable=False)
    skip_reason = Column(Text, nullable=True)
    
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
