"""Add tool_telemetry_event for public /tools funnel analytics.

Revision ID: tool_telemetry_001
Revises: plan_engine_v2_001
Create Date: 2026-04-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "tool_telemetry_001"
down_revision = "plan_engine_v2_001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tool_telemetry_event",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("athlete_id", UUID(as_uuid=True), sa.ForeignKey("athlete.id"), nullable=True),
        sa.Column("metadata", JSONB(), nullable=True),
    )
    op.create_index("ix_tool_telemetry_event_event_type", "tool_telemetry_event", ["event_type"])
    op.create_index("ix_tool_telemetry_event_athlete_id", "tool_telemetry_event", ["athlete_id"])
    op.create_index(
        "ix_tool_telemetry_event_type_created",
        "tool_telemetry_event",
        ["event_type", "created_at"],
    )
    op.create_index(
        "ix_tool_telemetry_event_path_created",
        "tool_telemetry_event",
        ["path", "created_at"],
    )


def downgrade():
    op.drop_index("ix_tool_telemetry_event_path_created", table_name="tool_telemetry_event")
    op.drop_index("ix_tool_telemetry_event_type_created", table_name="tool_telemetry_event")
    op.drop_index("ix_tool_telemetry_event_athlete_id", table_name="tool_telemetry_event")
    op.drop_index("ix_tool_telemetry_event_event_type", table_name="tool_telemetry_event")
    op.drop_table("tool_telemetry_event")
