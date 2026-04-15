from sqlalchemy import Column, Integer, BigInteger, Boolean, CheckConstraint, Float, Date, DateTime, ForeignKey, Numeric, Text, String, Index, UniqueConstraint, text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from core.database import Base
import uuid
from typing import Optional
from datetime import datetime, timezone

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

    # Fact extraction tracking — how many messages have already been processed
    last_extracted_msg_count = Column(Integer, nullable=True, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        Index("ix_coach_chat_athlete_id", "athlete_id"),
        Index("ix_coach_chat_context_type", "context_type"),
        Index("ix_coach_chat_created_at", "created_at"),
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

