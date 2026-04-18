from sqlalchemy import Column, Integer, BigInteger, Boolean, CheckConstraint, Float, Date, DateTime, ForeignKey, Numeric, Text, String, Index, UniqueConstraint, text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from core.database import Base
import uuid
from typing import Optional
from datetime import datetime, timezone

class NutritionGoal(Base):
    """
    Athlete's nutrition targets. One row per athlete (current goals only).
    Load-adaptive: rest-day base scaled by workout tier multipliers.
    """
    __tablename__ = "nutrition_goal"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False, unique=True, index=True)
    goal_type = Column(Text, nullable=False)
    calorie_target = Column(Integer, nullable=True)
    protein_g_per_kg = Column(Float, nullable=False, default=1.8)
    carb_pct = Column(Float, nullable=True, default=0.55)
    fat_pct = Column(Float, nullable=True, default=0.45)
    caffeine_target_mg = Column(Integer, nullable=True)
    load_adaptive = Column(Boolean, default=True, nullable=False)
    load_multipliers = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

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
    caffeine_mg = Column(Float, nullable=True)
    fluid_ml = Column(Float, nullable=True)
    carb_source = Column(Text, nullable=True)
    glucose_fructose_ratio = Column(Float, nullable=True)
    macro_source = Column(Text, nullable=True)  # 'usda_local', 'usda_api', 'llm_estimated', 'product_library', 'branded_barcode'
    fueling_product_id = Column(Integer, ForeignKey("fueling_product.id"), nullable=True)
    # Source identifier of the food this entry was created from. Set by the
    # frontend when the entry comes from a barcode scan or USDA lookup so the
    # backend can auto-learn per-athlete corrections (AthleteFoodOverride).
    source_fdc_id = Column(Integer, nullable=True)
    source_upc = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_nutrition_athlete_date", "athlete_id", "date"),
        Index(
            "ix_nutrition_entry_source_fdc",
            "source_fdc_id",
            postgresql_where=text("source_fdc_id IS NOT NULL"),
        ),
        Index(
            "ix_nutrition_entry_source_upc",
            "source_upc",
            postgresql_where=text("source_upc IS NOT NULL"),
        ),
    )

class USDAFood(Base):
    __tablename__ = "usda_food"

    id = Column(Integer, primary_key=True)
    fdc_id = Column(Integer, unique=True, nullable=False)
    description = Column(Text, nullable=False)
    food_category = Column(Text, nullable=True)
    calories_per_100g = Column(Float, nullable=True)
    protein_per_100g = Column(Float, nullable=True)
    carbs_per_100g = Column(Float, nullable=True)
    fat_per_100g = Column(Float, nullable=True)
    fiber_per_100g = Column(Float, nullable=True)
    upc_gtin = Column(Text, nullable=True, index=True)
    source = Column(Text, nullable=False, server_default="sr_legacy")
    cached_at = Column(DateTime(timezone=True), server_default=func.now())

class FuelingProduct(Base):
    __tablename__ = "fueling_product"

    id = Column(Integer, primary_key=True)
    brand = Column(Text, nullable=False, index=True)
    product_name = Column(Text, nullable=False)
    variant = Column(Text, nullable=True)
    category = Column(Text, nullable=False)  # 'gel', 'drink_mix', 'bar', 'chew', 'caffeine', 'electrolyte'
    serving_size_g = Column(Float, nullable=True)
    calories = Column(Float, nullable=True)
    carbs_g = Column(Float, nullable=True)
    protein_g = Column(Float, nullable=True)
    fat_g = Column(Float, nullable=True)
    fiber_g = Column(Float, nullable=True)
    caffeine_mg = Column(Float, server_default="0")
    sodium_mg = Column(Float, nullable=True)
    fluid_ml = Column(Float, server_default="0")
    carb_source = Column(Text, nullable=True)
    glucose_fructose_ratio = Column(Float, nullable=True)
    is_verified = Column(Boolean, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class MealTemplate(Base):
    __tablename__ = "meal_template"

    id = Column(Integer, primary_key=True)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("athlete.id"), nullable=False)
    meal_signature = Column(Text, nullable=False)
    items = Column(JSONB, nullable=False)
    times_confirmed = Column(Integer, server_default="1")
    last_used = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("athlete_id", "meal_signature", name="uq_meal_template_athlete_sig"),
    )


class AthleteFoodOverride(Base):
    """Per-athlete corrections to scanned/branded food macros.

    When an athlete edits the auto-populated values from a barcode scan or
    a USDA lookup, we remember the correction keyed on (athlete, identifier)
    and replay it the next time the same food is scanned. Solves the
    "David's protein bar always shows wrong calories" class of bug.

    Exactly one of (upc, fdc_id, fueling_product_id) must be set, enforced
    by a CHECK constraint and partial unique indexes.
    """

    __tablename__ = "athlete_food_override"

    id = Column(BigInteger, primary_key=True)
    athlete_id = Column(
        UUID(as_uuid=True),
        ForeignKey("athlete.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    upc = Column(Text, nullable=True)
    fdc_id = Column(Integer, nullable=True)
    fueling_product_id = Column(
        Integer,
        ForeignKey("fueling_product.id", ondelete="CASCADE"),
        nullable=True,
    )

    food_name = Column(Text, nullable=True)

    serving_size_g = Column(Float, nullable=True)
    calories = Column(Float, nullable=True)
    protein_g = Column(Float, nullable=True)
    carbs_g = Column(Float, nullable=True)
    fat_g = Column(Float, nullable=True)
    fiber_g = Column(Float, nullable=True)
    caffeine_mg = Column(Float, nullable=True)
    sodium_mg = Column(Float, nullable=True)

    times_applied = Column(Integer, nullable=False, server_default="0")
    last_applied_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN upc IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN fdc_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN fueling_product_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_athlete_food_override_one_identifier",
        ),
        Index(
            "uq_athlete_food_override_upc",
            "athlete_id",
            "upc",
            unique=True,
            postgresql_where=text("upc IS NOT NULL"),
        ),
        Index(
            "uq_athlete_food_override_fdc",
            "athlete_id",
            "fdc_id",
            unique=True,
            postgresql_where=text("fdc_id IS NOT NULL"),
        ),
        Index(
            "uq_athlete_food_override_fpid",
            "athlete_id",
            "fueling_product_id",
            unique=True,
            postgresql_where=text("fueling_product_id IS NOT NULL"),
        ),
    )

