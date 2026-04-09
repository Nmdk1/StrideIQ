"""AI Nutrition Intelligence: usda_food, fueling_product, athlete_fueling_profile, meal_template tables + NutritionEntry additions

Revision ID: nutrition_intelligence_001
Revises: adaptive_replan_001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "nutrition_intelligence_001"
down_revision = "adaptive_replan_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usda_food",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("fdc_id", sa.Integer, unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("food_category", sa.Text, nullable=True),
        sa.Column("calories_per_100g", sa.Float, nullable=True),
        sa.Column("protein_per_100g", sa.Float, nullable=True),
        sa.Column("carbs_per_100g", sa.Float, nullable=True),
        sa.Column("fat_per_100g", sa.Float, nullable=True),
        sa.Column("fiber_per_100g", sa.Float, nullable=True),
        sa.Column("upc_gtin", sa.Text, nullable=True),
        sa.Column("source", sa.Text, nullable=False, server_default="sr_legacy"),
        sa.Column("cached_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.execute(
        "CREATE INDEX idx_usda_food_description ON usda_food "
        "USING gin(to_tsvector('english', description))"
    )
    op.create_index(
        "idx_usda_food_upc", "usda_food", ["upc_gtin"],
        postgresql_where=sa.text("upc_gtin IS NOT NULL"),
    )

    op.create_table(
        "fueling_product",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("brand", sa.Text, nullable=False),
        sa.Column("product_name", sa.Text, nullable=False),
        sa.Column("variant", sa.Text, nullable=True),
        sa.Column("category", sa.Text, nullable=False),
        sa.Column("serving_size_g", sa.Float, nullable=True),
        sa.Column("calories", sa.Float, nullable=True),
        sa.Column("carbs_g", sa.Float, nullable=True),
        sa.Column("protein_g", sa.Float, nullable=True),
        sa.Column("fat_g", sa.Float, nullable=True),
        sa.Column("fiber_g", sa.Float, nullable=True),
        sa.Column("caffeine_mg", sa.Float, server_default="0"),
        sa.Column("sodium_mg", sa.Float, nullable=True),
        sa.Column("fluid_ml", sa.Float, server_default="0"),
        sa.Column("carb_source", sa.Text, nullable=True),
        sa.Column("glucose_fructose_ratio", sa.Float, nullable=True),
        sa.Column("is_verified", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_fueling_product_brand", "fueling_product", ["brand"])

    op.create_table(
        "athlete_fueling_profile",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("athlete_id", UUID(as_uuid=True), sa.ForeignKey("athlete.id"), nullable=False),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("fueling_product.id"), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("usage_context", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("athlete_id", "product_id", name="uq_athlete_fueling_profile"),
    )

    op.create_table(
        "meal_template",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("athlete_id", UUID(as_uuid=True), sa.ForeignKey("athlete.id"), nullable=False),
        sa.Column("meal_signature", sa.Text, nullable=False),
        sa.Column("items", JSONB, nullable=False),
        sa.Column("times_confirmed", sa.Integer, server_default="1"),
        sa.Column("last_used", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("athlete_id", "meal_signature", name="uq_meal_template_athlete_sig"),
    )

    with op.batch_alter_table("nutrition_entry") as batch_op:
        batch_op.add_column(sa.Column("caffeine_mg", sa.Float, nullable=True))
        batch_op.add_column(sa.Column("fluid_ml", sa.Float, nullable=True))
        batch_op.add_column(sa.Column("carb_source", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("glucose_fructose_ratio", sa.Float, nullable=True))
        batch_op.add_column(sa.Column("macro_source", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("fueling_product_id", sa.Integer, sa.ForeignKey("fueling_product.id"), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nutrition_entry") as batch_op:
        batch_op.drop_column("fueling_product_id")
        batch_op.drop_column("macro_source")
        batch_op.drop_column("glucose_fructose_ratio")
        batch_op.drop_column("carb_source")
        batch_op.drop_column("fluid_ml")
        batch_op.drop_column("caffeine_mg")

    op.drop_table("meal_template")
    op.drop_table("athlete_fueling_profile")
    op.drop_table("fueling_product")
    op.drop_index("idx_usda_food_upc", table_name="usda_food")
    op.execute("DROP INDEX IF EXISTS idx_usda_food_description")
    op.drop_table("usda_food")
