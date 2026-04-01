"""Add StrengthExerciseSet table and strength_session_type on Activity.

Phase A of cross-training session detail capture.
See docs/specs/CROSS_TRAINING_SESSION_DETAIL_SPEC.md

Revision ID: cross_training_003
Revises: cross_training_002
Create Date: 2026-04-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "cross_training_003"
down_revision = "cross_training_002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "strength_exercise_set",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("activity_id", UUID(as_uuid=True), sa.ForeignKey("activity.id", ondelete="CASCADE"), nullable=False),
        sa.Column("athlete_id", UUID(as_uuid=True), sa.ForeignKey("athlete.id", ondelete="CASCADE"), nullable=False),
        sa.Column("set_order", sa.Integer(), nullable=False),
        sa.Column("exercise_name_raw", sa.Text(), nullable=False),
        sa.Column("exercise_category", sa.Text(), nullable=False),
        sa.Column("movement_pattern", sa.Text(), nullable=False),
        sa.Column("muscle_group", sa.Text(), nullable=True),
        sa.Column("is_unilateral", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("set_type", sa.Text(), nullable=False, server_default="active"),
        sa.Column("reps", sa.Integer(), nullable=True),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("duration_s", sa.Float(), nullable=True),
        sa.Column("estimated_1rm_kg", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index("ix_strength_set_activity", "strength_exercise_set", ["activity_id"])
    op.create_index("ix_strength_set_athlete_pattern", "strength_exercise_set", ["athlete_id", "movement_pattern"])

    op.add_column(
        "activity",
        sa.Column("strength_session_type", sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_column("activity", "strength_session_type")
    op.drop_index("ix_strength_set_athlete_pattern", table_name="strength_exercise_set")
    op.drop_index("ix_strength_set_activity", table_name="strength_exercise_set")
    op.drop_table("strength_exercise_set")
