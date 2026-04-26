from sqlalchemy import Column, Integer, BigInteger, Boolean, CheckConstraint, Float, Date, DateTime, ForeignKey, Numeric, Text, String, Index, UniqueConstraint, text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from core.database import Base
import uuid
from typing import Optional
from datetime import datetime, timezone

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
    readiness_1_5 = Column(Integer, nullable=True)   # 1=poor, 5=high (morning readiness)

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

