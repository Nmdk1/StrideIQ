"""Add page_view table for usage telemetry

Revision ID: usage_telemetry_001
Revises: nutrition_planning_001
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "usage_telemetry_001"
down_revision = "nutrition_planning_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "page_view",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("athlete_id", UUID(as_uuid=True), sa.ForeignKey("athlete.id"), nullable=False, index=True),
        sa.Column("screen", sa.Text, nullable=False),
        sa.Column("referrer_screen", sa.Text, nullable=True),
        sa.Column("entered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("exited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Float, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
    )
    op.create_index("ix_page_view_athlete_entered", "page_view", ["athlete_id", "entered_at"])


def downgrade() -> None:
    op.drop_index("ix_page_view_athlete_entered", table_name="page_view")
    op.drop_table("page_view")
