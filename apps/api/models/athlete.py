from sqlalchemy import Column, Integer, BigInteger, Boolean, CheckConstraint, Float, Date, DateTime, ForeignKey, Numeric, Text, String, Index, UniqueConstraint, text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from core.database import Base
import uuid
from typing import Optional
from datetime import datetime, timezone

class Athlete(Base):
    __tablename__ = "athlete"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    email = Column(Text, unique=True, nullable=True)
    password_hash = Column(Text, nullable=True)  # For authentication
    role = Column(Text, default="athlete", nullable=False)  # 'athlete', 'admin', 'coach'
    display_name = Column(Text, nullable=True)
    coach_thread_id = Column(String, nullable=True)
    birthdate = Column(Date, nullable=True)
    sex = Column(Text, nullable=True)
    subscription_tier = Column(Text, default="free", nullable=False)

    # --- DEMO ACCOUNTS ---
    # Demo accounts are shared credentials for prospects.  They must NOT link
    # real Strava/Garmin accounts or store real athlete data.
    is_demo = Column(Boolean, default=False, nullable=False)

    # --- PAYMENTS / ENTITLEMENTS (Phase 6-ready) ---
    # Pre-Phase-6: may be null for all users.
    stripe_customer_id = Column(Text, nullable=True)

    # --- TRIALS (Phase 6: 7-day Pro access) ---
    # Trial-based access is additive: if trial_ends_at is in the future, athlete is treated as paid.
    trial_started_at = Column(DateTime(timezone=True), nullable=True)
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    # e.g., "self_serve" | "admin_grant" | "invite" | "race:CODE"
    trial_source = Column(Text, nullable=True)
    # For race QR attribution (links to RacePromoCode.id)
    race_promo_code_id = Column(UUID(as_uuid=True), ForeignKey("race_promo_code.id"), nullable=True)

    # --- ADMIN RBAC SEAM (Phase 4) ---
    # Keep an explicit "permissions seam" so we can introduce finer-grained roles
    # without rewriting endpoint guard patterns. This is intentionally lightweight
    # (JSONB) until Phase 6+ stabilizes billing/employee auth architecture.
    admin_permissions = Column(JSONB, nullable=False, default=list)

    # --- Strength v1 baseline (strength_v1_002) ---
    # Captured during the optional ``strength_baseline`` onboarding stage.
    # All nullable; nothing in the runtime depends on these being set.
    # See docs/specs/STRENGTH_V1_SCOPE.md §5.5 / §11.1.
    lifts_currently = Column(Text, nullable=True)
    lift_days_per_week = Column(Float, nullable=True)
    lift_experience_bucket = Column(Text, nullable=True)
    
    @property
    def has_active_subscription(self) -> bool:
        """Check if athlete has an active paid subscription or active trial."""
        from core.tier_utils import tier_satisfies
        if tier_satisfies(self.subscription_tier, "subscriber"):
            return True
        try:
            ends = getattr(self, "trial_ends_at", None)
            if ends is not None:
                now = datetime.now(timezone.utc)
                if ends > now:
                    return True
        except Exception:
            pass
        return False
    
    # User preferences
    # Default rule (set 2026-04-22): country-aware via timezone signal.
    # US athletes default to imperial (miles), non-US default to metric (km).
    # Derived in `services.units_default.derive_default_units(timezone)` and
    # applied at signup AND when timezone is first written from Strava OAuth,
    # but ONLY if `preferred_units_set_explicitly` is False. Once the athlete
    # picks a side in Settings, that choice is sticky forever.
    preferred_units = Column(Text, default="imperial", nullable=False)  # 'metric' (km) or 'imperial' (miles)
    preferred_units_set_explicitly = Column(
        Boolean, default=False, nullable=False, server_default="false"
    )

    # --- ACCOUNT SAFETY (Phase 4) ---
    # Hard block a user from accessing the product (admin-only action).
    is_blocked = Column(Boolean, default=False, nullable=False)
    
    # --- COACH VIP (Phase 11) ---
    # VIP athletes get premium model (gpt-5.2) for complex queries.
    # Set via admin UI. See ADR-060 for tiering rationale.
    is_coach_vip = Column(Boolean, default=False, nullable=False)

    # --- ADMIN COMP OVERRIDE (entitlement precedence contract) ---
    # When admin_tier_override is non-null, Stripe sync/webhook MUST NOT
    # downgrade subscription_tier below this value.  Clear the field to
    # restore Stripe authority.  See admin_tier_override_001 migration.
    admin_tier_override = Column(Text, nullable=True)
    admin_tier_override_set_at = Column(DateTime(timezone=True), nullable=True)
    admin_tier_override_set_by = Column(UUID(as_uuid=True), nullable=True)
    admin_tier_override_reason = Column(Text, nullable=True)
    
    strava_athlete_id = Column(Integer, nullable=True)
    strava_access_token = Column(Text, nullable=True)  # Encrypted
    strava_refresh_token = Column(Text, nullable=True)  # Encrypted
    strava_token_expires_at = Column(DateTime(timezone=True), nullable=True)  # When access token expires
    last_strava_sync = Column(DateTime(timezone=True), nullable=True)
    timezone = Column(Text, nullable=True)  # IANA timezone from Strava (e.g. "America/New_York")
    
    # Garmin Connect Integration — OAuth 2.0 (official API)
    # Tokens encrypted at rest using the same pattern as Strava tokens.
    garmin_oauth_access_token = Column(Text, nullable=True)   # Encrypted
    garmin_oauth_refresh_token = Column(Text, nullable=True)  # Encrypted
    garmin_oauth_token_expires_at = Column(DateTime(timezone=True), nullable=True)
    garmin_user_id = Column(Text, nullable=True)              # Garmin's stable user identifier
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
    rpi = Column('vdot', Float, nullable=True)  # Current RPI (DB column: vdot for backward compat)
    
    # --- RUNNER TYPING (McMillan-inspired) ---
    # Automatically calculated from race history
    runner_type = Column(Text, nullable=True)  # 'speedster', 'endurance_monster', 'balanced'
    runner_type_confidence = Column(Float, nullable=True)  # 0-1, how confident we are in classification
    runner_type_last_calculated = Column(DateTime(timezone=True), nullable=True)
    
    # --- CONSISTENCY TRACKING (Green-inspired) ---
    current_streak_weeks = Column(Integer, default=0)  # Consecutive weeks meeting targets
    longest_streak_weeks = Column(Integer, default=0)  # All-time best streak
    last_streak_update = Column(DateTime(timezone=True), nullable=True)

    # --- AI CONSENT (Phase 1: Consent Infrastructure) ---
    # Explicit opt-in required before any LLM dispatch. Default deny.
    # See docs/PHASE1_CONSENT_INFRASTRUCTURE_AC.md for full spec.
    ai_consent = Column(Boolean, default=False, nullable=False)
    ai_consent_granted_at = Column(DateTime(timezone=True), nullable=True)
    ai_consent_revoked_at = Column(DateTime(timezone=True), nullable=True)

    # --- RELATIONSHIPS ---
    # Required for SQLAlchemy unit-of-work to know about the FK dependency
    # from Activity → Athlete. Without this, delete ordering is arbitrary
    # and can cause ForeignKeyViolation when both are deleted in one flush.
    # lazy="dynamic" prevents auto-loading (returns query, no perf impact).
    # cascade="all, delete-orphan" tells the UoW to delete child activity
    # rows rather than UPDATE ... SET athlete_id = NULL (which would violate
    # the NOT NULL constraint).  Surfaced by test_orm_delete_ordering.
    activities = relationship(
        "Activity",
        back_populates="athlete",
        lazy="dynamic",
        cascade="all, delete-orphan",
        passive_deletes=False,
    )
    garmin_days = relationship("GarminDay", back_populates="athlete", lazy="dynamic")
    athlete_photos = relationship("AthletePhoto", back_populates="athlete", lazy="dynamic")
    runtoon_images = relationship("RuntoonImage", back_populates="athlete", lazy="dynamic")

class AthleteFuelingProfile(Base):
    __tablename__ = "athlete_fueling_profile"

    id = Column(Integer, primary_key=True)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("fueling_product.id"), nullable=False)
    is_active = Column(Boolean, server_default="true")
    usage_context = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    added_at = Column(DateTime(timezone=True), server_default=func.now())

    product = relationship("FuelingProduct", lazy="joined")

    __table_args__ = (
        UniqueConstraint("athlete_id", "product_id", name="uq_athlete_fueling_profile"),
    )

class AthleteRaceResultAnchor(Base):
    """
    Athlete-provided performance anchor used for prescriptive training paces.

    Trust contract:
    - We do NOT derive prescriptive paces from general training data in v1.
    - The anchor must come from a race/time-trial result (distance + time).
    """

    __tablename__ = "athlete_race_result_anchor"
    __table_args__ = (
        UniqueConstraint("athlete_id", "distance_key", name="uq_anchor_athlete_distance"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)

    # e.g., "5k" | "10k" | "half_marathon" | "marathon" | "other"
    distance_key = Column(Text, nullable=False)
    distance_meters = Column(Integer, nullable=True)

    time_seconds = Column(Integer, nullable=False)
    race_date = Column(Date, nullable=True)

    # e.g., "user" (onboarding) | "admin" (support) | "import" (future)
    source = Column(Text, nullable=False, default="user")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class AthleteTrainingPaceProfile(Base):
    """
    Derived training paces computed from a race anchor using the Training Pace Calculator.

    Safety invariant:
    - Stored separately from Athlete columns so existing plans/behavior do not change
      unless explicitly wired to use this profile.
    """

    __tablename__ = "athlete_training_pace_profile"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, unique=True, index=True)

    race_anchor_id = Column(UUID(as_uuid=True), ForeignKey("athlete_race_result_anchor.id"), nullable=False, index=True)

    # Named "fitness_score" in DB surface to avoid trademark issues in product UI.
    # Internally this is the same scalar used by the Training Pace Calculator.
    fitness_score = Column(Float, nullable=True)

    # JSON payload with paces and units, shaped for UI rendering + auditability.
    # Example keys: easy, marathon, threshold, interval, repetition, (each with mi/km)
    paces = Column(JSONB, nullable=False, default=dict)

    computed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class AthleteGoal(Base):
    """
    Athlete questionnaire responses for plan generation.
    """
    __tablename__ = "athlete_goal"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)
    
    # Required fields
    goal_distance = Column(Text, nullable=False)  # "marathon", "half_marathon", "10k", "5k"
    goal_race_date = Column(Date, nullable=False)
    current_weekly_miles = Column(Float, nullable=False)
    days_per_week = Column(Integer, nullable=False)
    
    # For pace calculation
    recent_race_distance = Column(Text, nullable=True)  # "5k", "10k", "half", "marathon"
    recent_race_time_seconds = Column(Integer, nullable=True)
    
    # Optional target
    goal_time_seconds = Column(Integer, nullable=True)
    
    # Current fitness
    current_long_run_miles = Column(Float, nullable=True)
    
    # Semi-custom fields
    race_profile = Column(Text, nullable=True)  # "flat", "hilly", "mixed", "trail"
    race_season = Column(Text, nullable=True)  # "spring", "summer", "fall", "winter"
    
    # Injury history (custom only)
    injury_history = Column(JSONB, nullable=True)
    
    # Preferences (custom only)
    training_preferences = Column(JSONB, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    __table_args__ = (
        Index("ix_athlete_goal_race_date", "goal_race_date"),
    )

class AthleteCalibratedModel(Base):
    """
    Persisted Banister model calibration for an athlete.
    
    Stores τ1/τ2 calibration results instead of recalculating each time.
    Invalidated when new race data is added.
    
    ADR-036: N=1 Learning Workout Selection Engine
    """
    __tablename__ = "athlete_calibrated_model"
    
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), primary_key=True)
    
    # Banister parameters
    tau1 = Column(Float, nullable=False)  # Fitness decay (days)
    tau2 = Column(Float, nullable=False)  # Fatigue decay (days)
    k1 = Column(Float, nullable=False)    # Fitness scaling
    k2 = Column(Float, nullable=False)    # Fatigue scaling
    p0 = Column(Float, nullable=False)    # Baseline performance
    
    # Fit quality
    r_squared = Column(Float, nullable=True)
    fit_error = Column(Float, nullable=True)
    n_performance_markers = Column(Integer, nullable=True)
    n_training_days = Column(Integer, nullable=True)
    
    # Confidence and tier
    confidence = Column(Text, nullable=False)  # 'high', 'moderate', 'low', 'uncalibrated'
    data_tier = Column(Text, nullable=False)   # 'uncalibrated', 'learning', 'calibrated'
    confidence_notes = Column(JSONB, nullable=True)  # List of notes about calibration
    
    # Lifecycle
    calibrated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    valid_until = Column(Date, nullable=True)  # Recalibrate after new race

class AthleteWorkoutResponse(Base):
    """
    Tracks how an athlete responds to different workout stimulus types.
    
    Aggregates RPE gaps, completion rates, and adaptation signals
    to learn which workout types work best for THIS athlete.
    
    Updated after each quality workout with feedback.
    
    ADR-036: N=1 Learning Workout Selection Engine
    """
    __tablename__ = "athlete_workout_response"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False)
    stimulus_type = Column(Text, nullable=False)  # 'intervals', 'continuous', 'hills', etc.
    
    # Aggregated response signals
    avg_rpe_gap = Column(Float, nullable=True)       # mean(actual_rpe - expected_rpe)
    rpe_gap_stddev = Column(Float, nullable=True)    # Consistency of RPE response
    completion_rate = Column(Float, nullable=True)   # Fraction completed as prescribed
    adaptation_signal = Column(Float, nullable=True) # EF trend post-workout (future)
    
    # Sample size
    n_observations = Column(Integer, default=0, nullable=False)
    
    # Timestamps
    first_observation = Column(DateTime(timezone=True), nullable=True)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    __table_args__ = (
        Index("ix_athlete_workout_response_athlete_id", "athlete_id"),
        Index("ix_athlete_workout_response_stimulus", "stimulus_type"),
        UniqueConstraint('athlete_id', 'stimulus_type', name='uq_athlete_stimulus_response'),
    )

class AthleteOverride(Base):
    """
    Athlete-specified overrides for fitness bank values.

    The algorithm computes peaks and RPI from activity history, but the athlete
    knows context the data can't capture: compromised races, illness, returning
    from injury with zero quality work, etc.  These overrides let the athlete
    (or coach) tell the system "I know better on this metric."

    When set, the fitness bank substitutes the override for the computed value.
    """
    __tablename__ = "athlete_override"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, unique=True)
    peak_weekly_miles = Column(Float, nullable=True)
    peak_long_run_miles = Column(Float, nullable=True)
    rpi = Column(Float, nullable=True)
    reason = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_athlete_override_athlete_id", "athlete_id"),
    )

class AthleteLearning(Base):
    """
    Banked learnings about what works/doesn't work for an athlete.
    
    Explicit intelligence that compounds over time:
    - what_works: Templates/patterns that produced positive outcomes
    - what_doesnt_work: Templates/patterns that failed or caused issues
    - injury_trigger: Patterns that preceded injuries
    
    ADR-036: N=1 Learning Workout Selection Engine
    """
    __tablename__ = "athlete_learning"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False)
    
    # Learning classification
    learning_type = Column(Text, nullable=False)  # 'what_works', 'what_doesnt_work', 'injury_trigger', 'preference'
    subject = Column(Text, nullable=False)        # template_id, stimulus_type, or pattern description
    
    # Evidence and confidence
    evidence = Column(JSONB, nullable=True)       # Supporting data (build_ids, outcomes, etc.)
    confidence = Column(Float, default=0.5, nullable=False)  # 0-1, increases with repeated observations
    
    # Provenance
    discovered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    source = Column(Text, nullable=False)         # 'rpe_analysis', 'race_outcome', 'user_feedback', 'injury_correlation'
    
    # Lifecycle
    is_active = Column(Boolean, default=True, nullable=False)  # Can be invalidated
    invalidated_at = Column(DateTime(timezone=True), nullable=True)
    invalidation_reason = Column(Text, nullable=True)
    
    __table_args__ = (
        Index("ix_athlete_learning_athlete_id", "athlete_id"),
        Index("ix_athlete_learning_type", "learning_type"),
        Index("ix_athlete_learning_athlete_type", "athlete_id", "learning_type"),
    )

class AthleteAdaptationThresholds(Base):
    """
    Per-athlete adaptation thresholds.

    Cold-start defaults are conservative (system rarely intervenes early on).
    Over time, calibrated from outcome data using the same pattern as the
    HRV correlation engine: collect, study, report, then act.
    """
    __tablename__ = "athlete_adaptation_thresholds"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, unique=True, index=True)

    # Readiness thresholds — parameters, not constants
    swap_quality_threshold = Column(Float, nullable=False, default=35.0)
    reduce_volume_threshold = Column(Float, nullable=False, default=25.0)
    skip_day_threshold = Column(Float, nullable=False, default=15.0)
    increase_volume_threshold = Column(Float, nullable=False, default=80.0)

    # Calibration metadata
    calibration_data_points = Column(Integer, nullable=False, default=0)
    last_calibrated_at = Column(DateTime(timezone=True), nullable=True)
    calibration_confidence = Column(Float, nullable=True)  # 0-1, None until first calibration

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class AthletePhoto(Base):
    """
    Reference photos uploaded by the athlete for Runtoon generation.

    Privacy invariant: storage_key is an R2 object key, NEVER a public URL.
    All access is via signed URLs generated server-side (15-min TTL).

    Consent is required before any photo is accepted. consent_at records
    when the athlete agreed; consent_version records which policy they agreed to.
    """
    __tablename__ = "athlete_photo"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id", ondelete="CASCADE"), nullable=False, index=True)
    storage_key = Column(Text, nullable=False)          # R2 object key — never a public URL
    photo_type = Column(Text, nullable=False)            # "face" | "running" | "full_body" | "additional"
    mime_type = Column(Text, nullable=False)             # "image/jpeg" | "image/png" | "image/webp"
    size_bytes = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Consent tracking (required for biometric-adjacent data)
    consent_at = Column(DateTime(timezone=True), nullable=False)
    consent_version = Column(Text, nullable=False, default="1.0")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    athlete = relationship("Athlete", back_populates="athlete_photos")

    __table_args__ = (
        Index("ix_athlete_photo_athlete_id", "athlete_id"),
    )

class AthleteFact(Base):
    """
    Structured memory: structured facts extracted from coach conversations.

    Layer 1 is athlete-stated only — facts the athlete explicitly told the coach.
    Supersession: same (athlete_id, fact_key) with a new value deactivates the old row.
    Temporal facts (injuries, symptoms, equipment, training phase) have a TTL
    and are excluded from athlete-facing surfaces after expiry.

    Governance: medical-adjacent facts acceptable during founder-only beta.
    Before public launch, add retention policy (max age, athlete-triggered deletion,
    access audit logging).
    """
    __tablename__ = "athlete_fact"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)

    fact_type = Column(Text, nullable=False)
    fact_key = Column(Text, nullable=False)
    fact_value = Column(Text, nullable=False)
    numeric_value = Column(Float, nullable=True)

    confidence = Column(Text, nullable=False, server_default="athlete_stated")
    source_chat_id = Column(UUID(as_uuid=True), ForeignKey("coach_chat.id"), nullable=True)
    source_excerpt = Column(Text, nullable=False)

    confirmed_by_athlete = Column(Boolean, nullable=False, default=False)

    extracted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    superseded_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    temporal = Column(Boolean, nullable=False, default=False, server_default="false")
    ttl_days = Column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_athlete_fact_athlete_active", "athlete_id", "is_active"),
        Index("ix_athlete_fact_key_lookup", "athlete_id", "fact_key"),
        Index(
            "uq_athlete_fact_active_key",
            "athlete_id", "fact_key",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )

class AthleteInvestigationConfig(Base):
    """Per-athlete investigation parameter overrides produced by tuning loop."""
    __tablename__ = "athlete_investigation_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), nullable=False)
    investigation_name = Column(Text, nullable=False)
    param_overrides = Column(JSONB, nullable=False)
    applied_from_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auto_discovery_run.id", ondelete="SET NULL"),
        nullable=True,
    )
    applied_change_log_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auto_discovery_change_log.id", ondelete="SET NULL"),
        nullable=True,
    )
    applied_at = Column(DateTime(timezone=True), nullable=False)
    reverted = Column(Boolean, nullable=False, default=False)
    reverted_at = Column(DateTime(timezone=True), nullable=True)
    reverted_by = Column(Text, nullable=True)
    revert_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index(
            "ix_aic_athlete_investigation_active",
            "athlete_id", "investigation_name", "reverted",
        ),
    )

