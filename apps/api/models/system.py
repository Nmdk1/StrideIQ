from sqlalchemy import Column, Integer, BigInteger, Boolean, CheckConstraint, Float, Date, DateTime, ForeignKey, Numeric, Text, String, Index, UniqueConstraint, text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from core.database import Base
import uuid
from typing import Optional
from datetime import datetime, timezone

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

class PlanPurchase(Base):
    """One-time race-plan unlock purchase record.

    Created when a checkout.session.completed webhook arrives with mode=payment
    and purchase_type=plan_onetime in the session metadata.

    Entitlement key: (athlete_id, plan_snapshot_id). Cross-athlete reuse is
    blocked at checkout time (billing router ownership check) and here by design
    — the athlete_id is written from the session's client_reference_id, not from
    user input post-purchase.

    plan_snapshot_id is an immutable reference to a specific plan artifact.
    It must NOT change if the plan is later mutated; use a stable snapshot/version
    identifier once the plan artifact system is in place.
    """

    __tablename__ = "plan_purchases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)
    plan_snapshot_id = Column(Text, nullable=False, index=True)

    stripe_session_id = Column(Text, nullable=True)
    stripe_payment_intent_id = Column(Text, nullable=True, unique=True, index=True)

    purchased_at = Column(DateTime(timezone=True), nullable=False)
    amount_cents = Column(Integer, nullable=True)  # populated if available from Stripe event

    __table_args__ = (
        # One purchase per athlete+plan artifact.
        UniqueConstraint("athlete_id", "plan_snapshot_id", name="uq_plan_purchases_athlete_snapshot"),
        Index("ix_plan_purchases_athlete_id", "athlete_id"),
        Index("ix_plan_purchases_plan_snapshot_id", "plan_snapshot_id"),
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

class ConsentAuditLog(Base):
    """
    Immutable audit trail for AI processing consent actions.

    Every grant or revoke of ai_processing consent writes one row here,
    even if the action is idempotent (already granted / already revoked).
    This provides a complete chronological record for compliance purposes.

    consent_type is extensible — currently only 'ai_processing' is used.
    source tracks where the consent action originated.
    """
    __tablename__ = "consent_audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)
    consent_type = Column(Text, nullable=False)   # e.g. "ai_processing"
    action = Column(Text, nullable=False)          # "granted" or "revoked"
    ip_address = Column(Text, nullable=True)
    user_agent = Column(Text, nullable=True)
    source = Column(Text, nullable=True)           # "onboarding" | "settings" | "consent_prompt" | "admin"
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

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

class GarminDay(Base):
    """
    Unified daily wellness row. One row per (athlete_id, calendar_date).

    Architecture decision 3D: all Garmin daily data lives here — no
    separate GarminSleep or GarminHRV tables.

    CALENDAR DATE RULE (L1): calendar_date is the WAKEUP DAY (morning),
    not the night before. A run on Saturday that follows Friday night sleep
    will have calendar_date = Saturday. All correlation queries must join
    on garmin_day.calendar_date = activity.start_time::date.

    Upsert pattern: INSERT ... ON CONFLICT (athlete_id, calendar_date) DO UPDATE
    """
    __tablename__ = "garmin_day"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id", ondelete="CASCADE"), nullable=False)
    calendar_date = Column(Date, nullable=False)

    # --- Daily Summary ---
    resting_hr = Column(Integer, nullable=True)
    avg_stress = Column(Integer, nullable=True)              # -1 = insufficient data
    max_stress = Column(Integer, nullable=True)
    stress_qualifier = Column(Text, nullable=True)           # calm/balanced/stressful/very_stressful
    steps = Column(Integer, nullable=True)
    active_time_s = Column(Integer, nullable=True)
    active_kcal = Column(Integer, nullable=True)
    moderate_intensity_s = Column(Integer, nullable=True)
    vigorous_intensity_s = Column(Integer, nullable=True)
    min_hr = Column(Integer, nullable=True)
    max_hr = Column(Integer, nullable=True)

    # --- Sleep Summary ---
    sleep_total_s = Column(Integer, nullable=True)
    sleep_deep_s = Column(Integer, nullable=True)
    sleep_light_s = Column(Integer, nullable=True)
    sleep_rem_s = Column(Integer, nullable=True)
    sleep_awake_s = Column(Integer, nullable=True)
    sleep_score = Column(Integer, nullable=True)             # 0–100
    sleep_score_qualifier = Column(Text, nullable=True)      # EXCELLENT/GOOD/FAIR/POOR
    sleep_validation = Column(Text, nullable=True)

    # --- HRV Summary ---
    hrv_overnight_avg = Column(Integer, nullable=True)       # ms
    hrv_5min_high = Column(Integer, nullable=True)           # ms

    # --- User Metrics ---
    vo2max = Column(Float, nullable=True)                    # updates infrequently

    # --- Body Battery (from Stress Detail) ---
    body_battery_end = Column(Integer, nullable=True)        # end-of-day value

    # --- Raw JSONB (Tier 2 computed fields deferred) ---
    stress_samples = Column(JSONB, nullable=True)            # TimeOffsetStressLevelValues
    body_battery_samples = Column(JSONB, nullable=True)      # TimeOffsetBodyBatteryValues

    # --- Deduplication ---
    garmin_daily_summary_id = Column(Text, nullable=True)
    garmin_sleep_summary_id = Column(Text, nullable=True)
    garmin_hrv_summary_id = Column(Text, nullable=True)

    # --- Audit ---
    inserted_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # --- Relationships ---
    athlete = relationship("Athlete", back_populates="garmin_days")

    __table_args__ = (
        UniqueConstraint("athlete_id", "calendar_date", name="uq_garmin_day_athlete_date"),
        Index("ix_garmin_day_athlete_id", "athlete_id"),
        Index("ix_garmin_day_calendar_date", "calendar_date"),
    )


# ---------------------------------------------------------------------------
# Usage Telemetry
# ---------------------------------------------------------------------------

class PageView(Base):
    __tablename__ = "page_view"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)
    screen = Column(Text, nullable=False)
    referrer_screen = Column(Text, nullable=True)
    entered_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    exited_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    event_metadata = Column("metadata", JSONB, nullable=True)

    __table_args__ = (
        Index("ix_page_view_athlete_entered", "athlete_id", "entered_at"),
    )

class ToolTelemetryEvent(Base):
    """
    Anonymous or authenticated funnel events for public /tools/* pages.
    Does not replace authenticated PageView — supplements acquisition analytics.
    """

    __tablename__ = "tool_telemetry_event"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    event_type = Column(Text, nullable=False, index=True)
    path = Column(Text, nullable=False)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=True, index=True)
    event_metadata = Column("metadata", JSONB, nullable=True)

    __table_args__ = (
        Index("ix_tool_telemetry_event_type_created", "event_type", "created_at"),
        Index("ix_tool_telemetry_event_path_created", "path", "created_at"),
    )


# ---------------------------------------------------------------------------
# Runtoon MVP Models
# ---------------------------------------------------------------------------

class RuntoonImage(Base):
    """
    AI-generated personalized caricature image for a run.

    Idempotency: UniqueConstraint on (activity_id, attempt_number) prevents
    duplicate auto-generation from concurrent Strava + Garmin sync hooks.
    attempt_number=1 is auto-generated; 2-3 are manual regenerations.

    Privacy invariant: storage_key is an R2 object key, NEVER a public URL.
    All access is via signed URLs generated server-side (15-min TTL).

    caption_text and stats_text are stored at generation time so the 9:16
    Pillow recompose can re-render them in the extended canvas without a
    second API call.
    """
    __tablename__ = "runtoon_image"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id", ondelete="CASCADE"), nullable=False, index=True)
    activity_id = Column(UUID(as_uuid=True), ForeignKey("activity.id", ondelete="CASCADE"), nullable=False, index=True)

    storage_key = Column(Text, nullable=False)          # R2 object key — never a public URL
    prompt_hash = Column(Text, nullable=True)            # SHA256 of assembled prompt (for debugging)
    generation_time_ms = Column(Integer, nullable=True)
    cost_usd = Column(Numeric(6, 4), nullable=True)      # e.g., 0.0670
    model_version = Column(Text, nullable=False, default="gemini-3.1-flash-image-preview")
    attempt_number = Column(Integer, nullable=False, default=1)  # 1=auto, 2-3=regeneration
    is_visible = Column(Boolean, default=True, nullable=False)

    # Stored at generation time — required for 9:16 Pillow recompose
    caption_text = Column(Text, nullable=True)           # AI-generated caption baked into image
    stats_text = Column(Text, nullable=True)             # Formatted stats line (e.g., "13.0 mi • 7:28/mi • 1:37:00")

    # --- Share tracking (set by POST /v1/runtoon/{id}/shared) ---
    # share_target is best-effort telemetry only — Web Share API does not
    # reliably report the selected app. Nullable, defaults to "unknown".
    # No logic should depend on this value.
    shared_at = Column(DateTime(timezone=True), nullable=True)
    share_format = Column(Text, nullable=True)            # "1:1" or "9:16"
    share_target = Column(Text, nullable=True)            # best-effort only; "unknown" if not reported

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    athlete = relationship("Athlete", back_populates="runtoon_images")
    activity = relationship("Activity")

    __table_args__ = (
        UniqueConstraint("activity_id", "attempt_number", name="uq_runtoon_activity_attempt"),
        Index("ix_runtoon_image_athlete_id", "athlete_id"),
        Index("ix_runtoon_image_activity_id", "activity_id"),
    )

class ExperienceAuditLog(Base):
    """Permanent log of daily production experience guardrail runs."""
    __tablename__ = "experience_audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, index=True)
    run_date = Column(Date, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    tier = Column(Text, nullable=False)
    passed = Column(Boolean, nullable=False)
    total_assertions = Column(Integer, nullable=False)
    passed_count = Column(Integer, nullable=False)
    failed_count = Column(Integer, nullable=False)
    skipped_count = Column(Integer, nullable=False, server_default='0')
    results = Column(JSONB, nullable=False)
    summary = Column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint('athlete_id', 'run_date', 'tier', name='uq_audit_athlete_date_tier'),
    )

