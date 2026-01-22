"""add_plan_modification_log_table_idempotent

Revision ID: 7b8c9d0e1f23
Revises: 6a7c8d9e0f12
Create Date: 2026-01-21

Creates `plan_modification_log` table used by plan adjustment endpoints.

Historical note:
An older migration exists (`add_plan_modification_log.py`) but is on a different
revision chain in some environments. This migration is idempotent and ensures
the table exists on the current head path.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "7b8c9d0e1f23"
down_revision = "6a7c8d9e0f12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "plan_modification_log" in inspector.get_table_names():
        return

    op.create_table(
        "plan_modification_log",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("athlete_id", UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", UUID(as_uuid=True), nullable=False),
        sa.Column("workout_id", UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("before_state", JSONB, nullable=True),
        sa.Column("after_state", JSONB, nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default=sa.text("'web'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("ip_address", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["athlete_id"], ["athlete.id"]),
        sa.ForeignKeyConstraint(["plan_id"], ["training_plan.id"]),
        sa.ForeignKeyConstraint(["workout_id"], ["planned_workout.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_plan_modification_log_athlete_id", "plan_modification_log", ["athlete_id"], unique=False)
    op.create_index("ix_plan_modification_log_plan_id", "plan_modification_log", ["plan_id"], unique=False)
    op.create_index("ix_plan_modification_log_created_at", "plan_modification_log", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_plan_modification_log_created_at", table_name="plan_modification_log")
    op.drop_index("ix_plan_modification_log_plan_id", table_name="plan_modification_log")
    op.drop_index("ix_plan_modification_log_athlete_id", table_name="plan_modification_log")
    op.drop_table("plan_modification_log")

