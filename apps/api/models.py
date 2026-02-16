from sqlalchemy import Column, Integer, BigInteger, Boolean, CheckConstraint, Float, Date, DateTime, ForeignKey, Numeric, Text, String, Index, UniqueConstraint
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
    
    # Paid subscription tiers that grant Elite access.
    # We keep legacy values for backward compatibility while converging on a single paid tier ("elite").
    PAID_TIERS = {'elite', 'pro', 'premium', 'guided', 'subscription'}
    
    @property
    def has_active_subscription(self) -> bool:
        """Check if athlete has an active paid subscription."""
        # Stripe / DB-tier based access (legacy + current)
        if self.subscription_tier in self.PAID_TIERS:
            return True
        # Trial access (time-bound)
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
    # Product default: imperial (US-first). Athlete can switch in Settings.
    preferred_units = Column(Text, default="imperial", nullable=False)  # 'metric' (km) or 'imperial' (miles)

    # --- ACCOUNT SAFETY (Phase 4) ---
    # Hard block a user from accessing the product (admin-only action).
    is_blocked = Column(Boolean, default=False, nullable=False)
    
    # --- COACH VIP (Phase 11) ---
    # VIP athletes get premium model (gpt-5.2) for complex queries.
    # Set via admin UI. See ADR-060 for tiering rationale.
    is_coach_vip = Column(Boolean, default=False, nullable=False)
    
    strava_athlete_id = Column(Integer, nullable=True)
    strava_access_token = Column(Text, nullable=True)  # Encrypted
    strava_refresh_token = Column(Text, nullable=True)  # Encrypted
    strava_token_expires_at = Column(DateTime(timezone=True), nullable=True)  # When access token expires
    last_strava_sync = Column(DateTime(timezone=True), nullable=True)
    timezone = Column(Text, nullable=True)  # IANA timezone from Strava (e.g. "America/New_York")
    
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

    # --- RELATIONSHIPS ---
    # Required for SQLAlchemy unit-of-work to know about the FK dependency
    # from Activity → Athlete. Without this, delete ordering is arbitrary
    # and can cause ForeignKeyViolation when both are deleted in one flush.
    # lazy="dynamic" prevents auto-loading (returns query, no perf impact).
    activities = relationship("Activity", back_populates="athlete", lazy="dynamic")


class InviteAllowlist(Base):
    """
    Invite allowlist entry (Phase 3: onboarding gating).

    Invites are first-class, auditable domain objects:
    - One row per invited email (stored lowercased).
    - Can be revoked.
    - Marked as used when a matching account is created.
    - Optional grant_tier: if set, user gets this subscription tier on signup.
    """

    __tablename__ = "invite_allowlist"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(Text, unique=True, nullable=False, index=True)  # stored lowercased

    is_active = Column(Boolean, default=True, nullable=False)
    note = Column(Text, nullable=True)
    
    # If set, user gets this subscription tier automatically on signup (e.g., "pro" for beta testers)
    grant_tier = Column(Text, nullable=True)

    invited_by_athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=True)
    invited_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by_athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=True)

    used_at = Column(DateTime(timezone=True), nullable=True)
    used_by_athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Subscription(Base):
    """
    Stripe subscription mirror (Phase 6).

    Stripe is the billing source of truth; this table stores a minimal, queryable
    mirror for entitlement decisions and admin/support visibility.
    """

    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, unique=True, index=True)

    stripe_customer_id = Column(Text, nullable=True, index=True)
    stripe_subscription_id = Column(Text, nullable=True, index=True)
    stripe_price_id = Column(Text, nullable=True)

    status = Column(Text, nullable=True, index=True)  # active|trialing|past_due|canceled|...
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    athlete = relationship("Athlete", lazy="joined")

    __table_args__ = (
        Index("ix_subscriptions_stripe_customer_id", "stripe_customer_id"),
        Index("ix_subscriptions_stripe_subscription_id", "stripe_subscription_id"),
    )


class StripeEvent(Base):
    """
    Processed Stripe events (idempotency guard).

    Stripe retries webhook deliveries; storing event ids makes webhook handling safe.
    """

    __tablename__ = "stripe_events"

    event_id = Column(Text, primary_key=True)  # Stripe event id (e.g., evt_*)
    event_type = Column(Text, nullable=False, index=True)
    stripe_created = Column(Integer, nullable=True)

    received_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_stripe_events_event_type", "event_type"),
    )


class InviteAuditEvent(Base):
    """
    Audit log for invite operations.
    """

    __tablename__ = "invite_audit_event"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invite_id = Column(UUID(as_uuid=True), ForeignKey("invite_allowlist.id"), nullable=False, index=True)
    actor_athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=True, index=True)
    action = Column(Text, nullable=False, index=True)  # invite.created | invite.revoked | invite.used
    target_email = Column(Text, nullable=False, index=True)  # lowercased
    event_metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AdminAuditEvent(Base):
    """
    Append-only audit log for admin actions (Phase 4).

    Non-negotiable invariants:
    - write-only from the application (no update/delete in code paths)
    - bounded payload (no secrets; minimal PII)
    """

    __tablename__ = "admin_audit_event"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    actor_athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)
    action = Column(Text, nullable=False, index=True)  # e.g., billing.comp | athlete.block | ingest.retry

    target_athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=True, index=True)
    reason = Column(Text, nullable=True)

    ip_address = Column(Text, nullable=True)
    user_agent = Column(Text, nullable=True)

    payload = Column(JSONB, nullable=False, default=dict)


class AthleteIngestionState(Base):
    """
    Durable per-athlete ingestion state for operational visibility.

    This is intentionally lightweight and append-free:
    - One row per (athlete, provider)
    - Stores last run metadata, last error, and last task ids
    """
    __tablename__ = "athlete_ingestion_state"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)
    provider = Column(Text, nullable=False, default="strava")

    # --- Best-effort backfill run state ---
    last_best_efforts_task_id = Column(Text, nullable=True)
    last_best_efforts_started_at = Column(DateTime(timezone=True), nullable=True)
    last_best_efforts_finished_at = Column(DateTime(timezone=True), nullable=True)
    # 'running' | 'success' | 'error' | 'rate_limited'
    last_best_efforts_status = Column(Text, nullable=True)
    last_best_efforts_error = Column(Text, nullable=True)
    last_best_efforts_retry_after_s = Column(Integer, nullable=True)
    last_best_efforts_activities_checked = Column(Integer, nullable=True)
    last_best_efforts_efforts_stored = Column(Integer, nullable=True)
    last_best_efforts_pbs_created = Column(Integer, nullable=True)

    # --- Activity index backfill run state ---
    last_index_task_id = Column(Text, nullable=True)
    last_index_started_at = Column(DateTime(timezone=True), nullable=True)
    last_index_finished_at = Column(DateTime(timezone=True), nullable=True)
    # 'running' | 'success' | 'error'
    last_index_status = Column(Text, nullable=True)
    last_index_error = Column(Text, nullable=True)
    last_index_pages_fetched = Column(Integer, nullable=True)
    last_index_created = Column(Integer, nullable=True)
    last_index_already_present = Column(Integer, nullable=True)
    last_index_skipped_non_runs = Column(Integer, nullable=True)

    # --- Phase 5: Viral-safe deferral (rate limit / global pause) ---
    # When set, ingestion is intentionally deferred until this timestamp.
    deferred_until = Column(DateTime(timezone=True), nullable=True)
    # e.g., "rate_limit" | "paused"
    deferred_reason = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("athlete_id", "provider", name="uq_ingestion_state_athlete_provider"),
        Index("ix_ingestion_state_provider", "provider"),
    )


class AthleteDataImportJob(Base):
    """
    Phase 7: Athlete-initiated data import job (Garmin/Coros file upload).

    This is the operational truth for import runs:
    - created/started/finished timestamps
    - deterministic status
    - bounded stats + error message

    Files are stored out-of-band (shared uploads directory / object storage),
    referenced by stored_path and verified by sha256.
    """

    __tablename__ = "athlete_data_import_job"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)

    # 'garmin' | 'coros'
    provider = Column(Text, nullable=False, index=True)
    # 'queued' | 'running' | 'success' | 'error'
    status = Column(Text, nullable=False, index=True)

    original_filename = Column(Text, nullable=True)
    stored_path = Column(Text, nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)
    file_sha256 = Column(Text, nullable=True, index=True)

    # Bounded counters + metadata (no raw file content).
    stats = Column(JSONB, nullable=False, default=dict)
    error = Column(Text, nullable=True)


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


class DailyCheckin(Base):
    __tablename__ = "daily_checkin"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    sleep_h = Column(Numeric, nullable=True)  # Total sleep duration in hours (explicit athlete input)
    sleep_quality_1_5 = Column(Integer, nullable=True)  # Sleep quality 1-5 (1=poor, 5=great)
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


class AthleteRaceResultAnchor(Base):
    """
    Athlete-provided performance anchor used for prescriptive training paces.

    Trust contract:
    - We do NOT derive prescriptive paces from general training data in v1.
    - The anchor must come from a race/time-trial result (distance + time).
    """

    __tablename__ = "athlete_race_result_anchor"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, unique=True, index=True)

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


class CoachActionProposal(Base):
    """
    Phase 10: Coach Action Automation proposal object.

    Stores a validated proposal (actions_json), its lifecycle status, and an apply receipt.
    """

    __tablename__ = "coach_action_proposals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)

    # Actor envelope (bounded; avoid dumping sensitive user data here)
    created_by = Column(JSONB, nullable=False, default=dict)

    # proposed | confirmed | rejected | applied | failed
    status = Column(Text, nullable=False, index=True)

    # Validated allowlist payload: {"version": 1, "actions": [...]}
    actions_json = Column(JSONB, nullable=False)

    # Plain-language reason shown to athlete
    reason = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    applied_at = Column(DateTime(timezone=True), nullable=True)
    error = Column(Text, nullable=True)

    # Idempotency key for propose (nullable; unique per athlete when present)
    idempotency_key = Column(Text, nullable=True)

    # Optional: bind proposal to a plan id to prevent TOCTOU between propose and confirm.
    target_plan_id = Column(UUID(as_uuid=True), ForeignKey("training_plan.id"), nullable=True)

    # Stored apply receipt for idempotent confirm responses.
    apply_receipt_json = Column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_coach_action_proposals_created_at", "created_at"),
        Index("ix_coach_action_proposals_status", "status"),
        Index(
            "ux_coach_action_proposals_athlete_id_idempotency_key",
            "athlete_id",
            "idempotency_key",
            unique=True,
            postgresql_where=(idempotency_key.isnot(None)),
        ),
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


class CoachChat(Base):
    """
    Coach conversation sessions.
    
    Stores conversations between athlete and GPT coach.
    Context-aware: knows what day/week/build the athlete is asking about.
    
    Each session captures:
    - Context type: day, week, build, or open
    - Context reference: specific date, week number, or build ID
    - Full conversation history
    - Context snapshot (what the coach "saw" when responding)
    """
    __tablename__ = "coach_chat"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False)
    
    # Context type: 'day', 'week', 'build', 'open'
    context_type = Column(Text, nullable=False, default='open')
    
    # Context references (depending on type)
    context_date = Column(Date, nullable=True)  # For 'day' context
    context_week = Column(Integer, nullable=True)  # For 'week' context
    context_plan_id = Column(UUID(as_uuid=True), ForeignKey("training_plan.id"), nullable=True)  # For 'build' context
    
    # Session title (auto-generated or user-set)
    title = Column(Text, nullable=True)
    
    # Conversation messages stored as JSONB array
    # Format: [{"role": "user", "content": "...", "timestamp": "..."}, {"role": "coach", "content": "...", "timestamp": "..."}]
    messages = Column(JSONB, nullable=False, default=list)
    
    # Context snapshot at session start (what data the coach had access to)
    context_snapshot = Column(JSONB, nullable=True)
    
    # Session status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        Index("ix_coach_chat_athlete_id", "athlete_id"),
        Index("ix_coach_chat_context_type", "context_type"),
        Index("ix_coach_chat_created_at", "created_at"),
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

class FeatureFlag(Base):
    """
    Feature flags for gating any feature without deploy.
    
    Features can be gated by:
    - Global enable/disable
    - Subscription requirement
    - Tier requirement (pro, elite)
    - One-time payment
    - Rollout percentage
    - Beta tester list
    """
    __tablename__ = "feature_flag"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(Text, unique=True, nullable=False, index=True)  # e.g., "plan.semi_custom"
    name = Column(Text, nullable=False)  # Human-readable name
    description = Column(Text, nullable=True)
    
    # Gating options
    enabled = Column(Boolean, default=False, nullable=False)
    requires_subscription = Column(Boolean, default=False, nullable=False)
    requires_tier = Column(Text, nullable=True)  # "pro", "elite", etc.
    requires_payment = Column(Numeric(10, 2), nullable=True)  # One-time price
    
    # Rollout control
    rollout_percentage = Column(Integer, default=100, nullable=False)  # 0-100
    allowed_athlete_ids = Column(JSONB, nullable=True)  # Beta tester UUIDs
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Purchase(Base):
    """
    One-time purchases (e.g., semi-custom plans).
    """
    __tablename__ = "purchase"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)
    product_key = Column(Text, nullable=False, index=True)  # e.g., "plan.semi_custom"
    
    # Payment details
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(Text, default="USD", nullable=False)
    status = Column(Text, default="pending", nullable=False)  # "pending", "completed", "refunded"
    
    # External payment reference
    payment_provider = Column(Text, nullable=True)  # "stripe", "paypal"
    external_payment_id = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)


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


class CoachIntentSnapshot(Base):
    """
    Persisted self-guided coaching intent snapshot (athlete-led).

    This is NOT plan state. It's a lightweight, auditable record of the athlete's
    current intent + constraints so the coach can collaborate without asking
    the same questions every time.

    Key principle:
      - fatigue can trigger a conversation; it does NOT auto-impose taper/phase shifts.
    """

    __tablename__ = "coach_intent_snapshot"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, unique=True, index=True)

    # Athlete-led intent (free-form string constrained at service layer).
    training_intent = Column(Text, nullable=True)  # e.g. 'through_fatigue', 'build_fitness', 'freshen_for_event'
    next_event_date = Column(Date, nullable=True)
    next_event_type = Column(Text, nullable=True)  # 'race', 'benchmark', etc.

    # Constraints + subjective state (athlete input).
    pain_flag = Column(Text, nullable=True)  # 'none' | 'niggle' | 'pain'
    time_available_min = Column(Integer, nullable=True)  # Typical available time for workouts
    weekly_mileage_target = Column(Float, nullable=True)  # Athlete-stated target for current period
    what_feels_off = Column(Text, nullable=True)  # 'legs' | 'lungs' | 'motivation' | 'life_stress' | free text

    # Optional extra structured fields (future-safe).
    extra = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (Index("ix_coach_intent_snapshot_updated_at", "updated_at"),)


class CoachUsage(Base):
    """
    Track LLM token usage per athlete for cost capping (ADR-061).
    
    Enforces hard limits:
    - Daily request caps
    - Monthly token budgets
    - Opus-specific allocation
    
    Reset logic:
    - Daily counters reset at midnight UTC
    - Monthly counters reset on 1st of month
    """
    
    __tablename__ = "coach_usage"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False)
    
    # Date for daily tracking (reset daily)
    date = Column(Date, nullable=False)
    
    # Daily counters
    requests_today = Column(Integer, default=0, nullable=False)
    opus_requests_today = Column(Integer, default=0, nullable=False)
    tokens_today = Column(Integer, default=0, nullable=False)
    opus_tokens_today = Column(Integer, default=0, nullable=False)
    
    # Monthly tracking (YYYY-MM format)
    month = Column(String(7), nullable=False)  # e.g., "2026-01"
    tokens_this_month = Column(Integer, default=0, nullable=False)
    opus_tokens_this_month = Column(Integer, default=0, nullable=False)
    
    # Cost tracking (in USD cents for precision)
    cost_today_cents = Column(Integer, default=0, nullable=False)
    cost_this_month_cents = Column(Integer, default=0, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        UniqueConstraint("athlete_id", "date", name="uq_coach_usage_athlete_date"),
        Index("ix_coach_usage_athlete_id", "athlete_id"),
        Index("ix_coach_usage_month", "month"),
    )


class RacePromoCode(Base):
    """
    Promo codes for race partnerships.
    
    Athletes signing up via QR code at packet pickup get extended trials
    and are attributed to the race for conversion tracking.
    """
    __tablename__ = "race_promo_code"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # The code itself (e.g., "MARATHON2026", "BOSTONFEB2026")
    code = Column(Text, unique=True, nullable=False, index=True)
    
    # Race details
    race_name = Column(Text, nullable=False)  # e.g., "Boston Marathon 2026"
    race_date = Column(Date, nullable=True)   # Optional: race date for context
    
    # Trial configuration
    trial_days = Column(Integer, default=30, nullable=False)  # 30 days for race signups
    
    # Validity period
    valid_from = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    valid_until = Column(DateTime(timezone=True), nullable=True)  # Null = never expires
    
    # Limits
    max_uses = Column(Integer, nullable=True)  # Null = unlimited
    current_uses = Column(Integer, default=0, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Admin tracking
    created_by = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        Index("ix_race_promo_code_code", "code"),
        Index("ix_race_promo_code_is_active", "is_active"),
    )


# =========================================================================
# Phase 2A: Readiness Score Models
# =========================================================================

class DailyReadiness(Base):
    """
    Daily readiness computation result.

    Stores the composite readiness score and per-signal breakdown.
    One row per athlete per day. The score is a SIGNAL — what fires from it
    is governed by per-athlete thresholds, not hardcoded constants.
    """
    __tablename__ = "daily_readiness"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    score = Column(Float, nullable=False)                    # 0-100 composite
    components = Column(JSONB, nullable=True)                # Per-signal breakdown
    signals_available = Column(Integer, nullable=False, default=0)
    signals_total = Column(Integer, nullable=False, default=5)
    confidence = Column(Float, nullable=False, default=0.0)  # 0-1
    weights_used = Column(JSONB, nullable=True)              # Weights at time of computation
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("athlete_id", "date", name="uq_daily_readiness_athlete_date"),
        Index("ix_daily_readiness_athlete_date", "athlete_id", "date"),
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


class ThresholdCalibrationLog(Base):
    """
    Logs every readiness-at-decision + outcome pair.

    This is the data that feeds the per-athlete threshold calibration process.
    Pattern: every workout → log readiness + scheduled type + outcome.
    When N >= 30: estimate per-athlete thresholds from outcome data.
    """
    __tablename__ = "threshold_calibration_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)
    workout_id = Column(UUID(as_uuid=True), ForeignKey("planned_workout.id"), nullable=True)

    # State at decision point
    readiness_score = Column(Float, nullable=False)
    workout_type_scheduled = Column(Text, nullable=True)

    # Outcome
    outcome = Column(Text, nullable=True)                  # "completed", "skipped", "modified"
    efficiency_delta = Column(Float, nullable=True)        # Next-day efficiency change
    subjective_feel = Column(Integer, nullable=True)       # From check-in if available (1-5)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_threshold_cal_log_athlete_date", "athlete_id", "created_at"),
    )


# =========================================================================
# Phase 2B: Self-Regulation + Intelligence Logging
# =========================================================================

class SelfRegulationLog(Base):
    """
    Records every planned ≠ actual delta as first-class data.

    When an athlete deviates from the plan — running quality instead of easy,
    cutting a long run short, adding an unplanned session — the delta is
    logged here with the outcome tracked over the following days.

    This data feeds:
    - Self-regulation pattern recognition ("you override easy → quality well")
    - Threshold calibration (readiness at decision → outcome)
    - Intelligence engine SUGGEST mode (personal patterns from outcome data)
    """
    __tablename__ = "self_regulation_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)
    workout_id = Column(UUID(as_uuid=True), ForeignKey("planned_workout.id"), nullable=True)
    activity_id = Column(UUID(as_uuid=True), ForeignKey("activity.id"), nullable=True)

    # What was planned
    planned_type = Column(Text, nullable=True)                  # e.g., "easy"
    planned_distance_km = Column(Float, nullable=True)
    planned_intensity = Column(Text, nullable=True)             # e.g., "easy_pace"

    # What actually happened
    actual_type = Column(Text, nullable=True)                   # e.g., "tempo_run"
    actual_distance_km = Column(Float, nullable=True)
    actual_intensity = Column(Text, nullable=True)              # e.g., "threshold_pace"

    # Delta classification
    delta_type = Column(Text, nullable=False)                   # "type_change", "distance_change", "intensity_change", "unplanned", "skipped"
    delta_direction = Column(Text, nullable=True)               # "upgraded" (easy→quality), "downgraded" (quality→easy), "shortened", "extended"

    # Context at time of decision
    readiness_at_decision = Column(Float, nullable=True)        # Readiness score
    trigger_date = Column(Date, nullable=False)

    # Outcome tracking (populated asynchronously, next day or later)
    outcome_efficiency_delta = Column(Float, nullable=True)     # Next-day efficiency change
    outcome_subjective = Column(Integer, nullable=True)         # From check-in if available (1-5)
    outcome_classification = Column(Text, nullable=True)        # "positive", "neutral", "negative" (set by outcome analysis)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_self_reg_log_athlete_date", "athlete_id", "trigger_date"),
    )


class InsightLog(Base):
    """
    Records every intelligence insight produced by the daily engine.

    Every INFORM, SUGGEST, FLAG, ASK, and LOG insight is persisted here.
    This provides:
    - Audit trail of what the system told the athlete
    - Data for measuring insight accuracy over time
    - Input for the narration trust scoring system (Phase 3)
    """
    __tablename__ = "insight_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)

    # Insight identity
    rule_id = Column(Text, nullable=False)                      # e.g., "LOAD_SPIKE", "SELF_REG_DELTA"
    mode = Column(Text, nullable=False)                         # "inform", "suggest", "flag", "ask", "log"
    message = Column(Text, nullable=True)                       # Human-readable insight text
    data_cited = Column(JSONB, nullable=True)                   # Evidence backing the insight

    # Context
    trigger_date = Column(Date, nullable=False)
    readiness_score = Column(Float, nullable=True)              # Readiness at time of insight
    confidence = Column(Float, nullable=True)                   # 0-1 confidence in the insight

    # Athlete response tracking
    athlete_seen = Column(Boolean, default=False, nullable=False)
    athlete_response = Column(Text, nullable=True)              # "acknowledged", "dismissed", "acted_on"
    athlete_response_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Phase 3A: Coach narration attached to this insight
    narrative = Column(Text, nullable=True)                      # AI-generated explanation of this insight
    narrative_score = Column(Float, nullable=True)               # 0-1 score from narration scorer
    narrative_contradicts = Column(Boolean, nullable=True)       # True if narration contradicted engine

    __table_args__ = (
        Index("ix_insight_log_athlete_date", "athlete_id", "trigger_date"),
        Index("ix_insight_log_rule_id", "rule_id"),
    )


class NarrationLog(Base):
    """
    Records every narration scoring evaluation.

    Each time the coach generates a narration for an intelligence insight,
    the narration is scored against the engine's ground truth on 3 binary
    criteria. Results stored here feed the Phase 3B gate (90% for 4 weeks).

    This is the AUDIT TRAIL for coach narration quality.
    """
    __tablename__ = "narration_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)
    insight_log_id = Column(UUID(as_uuid=True), ForeignKey("insight_log.id"), nullable=True)

    # The narration
    trigger_date = Column(Date, nullable=False)
    rule_id = Column(Text, nullable=False)                       # Which rule was narrated
    narration_text = Column(Text, nullable=True)                 # The generated narration
    prompt_used = Column(Text, nullable=True)                    # The prompt sent to the LLM (for debugging)

    # Ground truth
    ground_truth = Column(JSONB, nullable=True)                  # Engine data at narration time

    # 3 binary scoring criteria
    factually_correct = Column(Boolean, nullable=True)
    no_raw_metrics = Column(Boolean, nullable=True)
    actionable_language = Column(Boolean, nullable=True)
    criteria_passed = Column(Integer, nullable=True)             # 0-3
    score = Column(Float, nullable=True)                         # 0.0-1.0

    # Contradiction detection
    contradicts_engine = Column(Boolean, default=False, nullable=False)
    contradiction_detail = Column(Text, nullable=True)

    # Quality gate
    suppressed = Column(Boolean, default=False, nullable=False)  # True if narration quality too low → hidden
    suppression_reason = Column(Text, nullable=True)             # Why it was suppressed

    # LLM metadata
    model_used = Column(Text, nullable=True)                     # e.g., "gemini-2.5-flash"
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_narration_log_athlete_date", "athlete_id", "trigger_date"),
        Index("ix_narration_log_score", "score"),
    )


class CorrelationFinding(Base):
    """
    Persists significant correlation discoveries for each athlete.

    When the correlation engine finds a significant relationship (e.g.,
    "sleep > 7h → efficiency +8% two days later"), it is recorded here.
    Each subsequent confirmation of the same pattern increments
    times_confirmed, building reproducibility weight.

    Only reproducible findings (times_confirmed >= SURFACING_THRESHOLD)
    are eligible to be narrated to the athlete.  The coach speaks only
    when the pattern is real — not after a single lucky coincidence.

    Lifecycle:
        1. Correlation engine discovers a significant (p < 0.05, |r| >= 0.3)
           relationship between an input (e.g. sleep_hours) and an output
           metric (e.g. efficiency).
        2. persist_correlation_findings() upserts the row:
           - New finding → times_confirmed = 1.
           - Existing finding → times_confirmed += 1, stats updated.
        3. If a previously-significant finding drops below threshold in a
           later run, is_active is set to False (patterns can fade).
        4. Daily intelligence checks for reproducible findings
           (times_confirmed >= 3, is_active) and emits InsightLog entries
           with rule_id = "CORRELATION_CONFIRMED".
    """
    __tablename__ = "correlation_finding"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)

    # --- What was correlated ---
    input_name = Column(Text, nullable=False)          # e.g. "sleep_hours", "soreness_1_5"
    output_metric = Column(Text, nullable=False)       # e.g. "efficiency", "pace_easy"
    direction = Column(Text, nullable=False)           # "positive" or "negative"
    time_lag_days = Column(Integer, default=0, nullable=False)

    # --- Statistical strength (most recent computation) ---
    correlation_coefficient = Column(Float, nullable=False)
    p_value = Column(Float, nullable=False)
    sample_size = Column(Integer, nullable=False)
    strength = Column(Text, nullable=False)            # "weak", "moderate", "strong"

    # --- Reproducibility tracking ---
    times_confirmed = Column(Integer, default=1, nullable=False)
    first_detected_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_confirmed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_surfaced_at = Column(DateTime(timezone=True), nullable=True)

    # --- Human-readable insight text ---
    insight_text = Column(Text, nullable=True)

    # --- Categorization ---
    category = Column(Text, nullable=False)            # "what_works", "what_doesnt", "pattern"
    confidence = Column(Float, nullable=False)         # 0.0-1.0

    # --- Lifecycle ---
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        # One row per unique (athlete, input, output, lag) combination.
        Index(
            "uq_corr_finding_natural_key",
            "athlete_id", "input_name", "output_metric", "time_lag_days",
            unique=True,
        ),
        Index("ix_corr_finding_active", "athlete_id", "is_active"),
    )
