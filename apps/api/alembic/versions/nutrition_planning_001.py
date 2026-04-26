"""Add nutrition_goal table for planning product

Revision ID: nutrition_planning_001
Revises: interval_view_001
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "nutrition_planning_001"
down_revision = "interval_view_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nutrition_goal",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("athlete_id", UUID(as_uuid=True), sa.ForeignKey("athlete.id"), nullable=False, unique=True),
        sa.Column("goal_type", sa.Text(), nullable=False),
        sa.Column("calorie_target", sa.Integer(), nullable=True),
        sa.Column("protein_g_per_kg", sa.Float(), nullable=False, server_default="1.8"),
        sa.Column("carb_pct", sa.Float(), nullable=True, server_default="0.55"),
        sa.Column("fat_pct", sa.Float(), nullable=True, server_default="0.45"),
        sa.Column("caffeine_target_mg", sa.Integer(), nullable=True),
        sa.Column("load_adaptive", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("load_multipliers", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_nutrition_goal_athlete", "nutrition_goal", ["athlete_id"])


def downgrade() -> None:
    op.drop_index("ix_nutrition_goal_athlete")
    op.drop_table("nutrition_goal")
