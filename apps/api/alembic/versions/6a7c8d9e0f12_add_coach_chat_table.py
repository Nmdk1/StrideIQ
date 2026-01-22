"""add_coach_chat_table

Revision ID: 6a7c8d9e0f12
Revises: 5c9a1f3d2e11
Create Date: 2026-01-21

Creates `coach_chat` table used by calendar coach chat.

This table can be missing in some environments due to historical schema drift.
Migration is idempotent: if table already exists, upgrade is a no-op.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "6a7c8d9e0f12"
down_revision = "5c9a1f3d2e11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "coach_chat" in inspector.get_table_names():
        return

    op.create_table(
        "coach_chat",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("athlete_id", UUID(as_uuid=True), nullable=False),
        sa.Column("context_type", sa.Text(), nullable=False, server_default=sa.text("'open'")),
        sa.Column("context_date", sa.Date(), nullable=True),
        sa.Column("context_week", sa.Integer(), nullable=True),
        sa.Column("context_plan_id", UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("messages", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("context_snapshot", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["athlete_id"], ["athlete.id"]),
        sa.ForeignKeyConstraint(["context_plan_id"], ["training_plan.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_coach_chat_athlete_id", "coach_chat", ["athlete_id"], unique=False)
    op.create_index("ix_coach_chat_context_type", "coach_chat", ["context_type"], unique=False)
    op.create_index("ix_coach_chat_created_at", "coach_chat", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_coach_chat_created_at", table_name="coach_chat")
    op.drop_index("ix_coach_chat_context_type", table_name="coach_chat")
    op.drop_index("ix_coach_chat_athlete_id", table_name="coach_chat")
    op.drop_table("coach_chat")

