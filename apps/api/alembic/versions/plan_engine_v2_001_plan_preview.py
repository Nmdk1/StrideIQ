"""Add plan_preview table for Plan Engine V2.

V2 writes its generated plans here as JSON, leaving V1's training_plan
table completely untouched. Each row is one generated plan (one block).

Revision ID: plan_engine_v2_001
Revises: usage_telemetry_001
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "plan_engine_v2_001"
down_revision = "usage_telemetry_001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "plan_preview",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("athlete_id", UUID(as_uuid=True),
                  sa.ForeignKey("athlete.id", ondelete="CASCADE"),
                  nullable=False, index=True),

        # Plan identity
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("goal_event", sa.Text(), nullable=True),
        sa.Column("block_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("total_weeks", sa.Integer(), nullable=False),

        # The full plan output
        sa.Column("plan_json", JSONB(), nullable=False),

        # Build-over-build seeding
        sa.Column("peak_workout_state", JSONB(), nullable=True),

        # Metadata
        sa.Column("engine_version", sa.Text(), nullable=False, server_default="v2"),
        sa.Column("anchor_type", sa.Text(), nullable=True),
        sa.Column("athlete_type", sa.Text(), nullable=True),
        sa.Column("phase_structure", JSONB(), nullable=True),
        sa.Column("pace_ladder", JSONB(), nullable=True),

        # Lifecycle
        sa.Column("status", sa.Text(), nullable=False, server_default="preview"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),

        # Link to V1 plan if promoted
        sa.Column("promoted_plan_id", UUID(as_uuid=True),
                  sa.ForeignKey("training_plan.id", ondelete="SET NULL"),
                  nullable=True),
    )

    op.create_index(
        "ix_plan_preview_athlete_status",
        "plan_preview",
        ["athlete_id", "status"],
    )


def downgrade():
    op.drop_index("ix_plan_preview_athlete_status")
    op.drop_table("plan_preview")
