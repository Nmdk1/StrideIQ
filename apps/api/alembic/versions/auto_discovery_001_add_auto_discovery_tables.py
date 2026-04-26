"""Add auto_discovery_run and auto_discovery_experiment tables.

Revision ID: auto_discovery_001
Revises: temporal_fact_001
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "auto_discovery_001"
down_revision = "temporal_fact_001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "auto_discovery_run",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("athlete_id", UUID(as_uuid=True), sa.ForeignKey("athlete.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="running"),
        sa.Column("loop_types", JSONB(), nullable=False, server_default="[]"),
        sa.Column("experiment_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("kept_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("discarded_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("report", JSONB(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_auto_discovery_run_athlete_started", "auto_discovery_run", ["athlete_id", "started_at"])
    op.create_index("ix_auto_discovery_run_status_started", "auto_discovery_run", ["status", "started_at"])

    op.create_table(
        "auto_discovery_experiment",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("auto_discovery_run.id"), nullable=False),
        sa.Column("athlete_id", UUID(as_uuid=True), sa.ForeignKey("athlete.id"), nullable=False),
        sa.Column("loop_type", sa.Text(), nullable=False),
        sa.Column("target_name", sa.Text(), nullable=False),
        sa.Column("baseline_config", JSONB(), nullable=False, server_default="{}"),
        sa.Column("candidate_config", JSONB(), nullable=False, server_default="{}"),
        sa.Column("baseline_score", sa.Float(), nullable=True),
        sa.Column("candidate_score", sa.Float(), nullable=True),
        sa.Column("score_delta", sa.Float(), nullable=True),
        sa.Column("kept", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("runtime_ms", sa.Integer(), nullable=True),
        sa.Column("result_summary", JSONB(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_auto_disc_exp_run_id", "auto_discovery_experiment", ["run_id"])
    op.create_index(
        "ix_auto_disc_exp_athlete_loop_created",
        "auto_discovery_experiment",
        ["athlete_id", "loop_type", "created_at"],
    )
    op.create_index(
        "ix_auto_disc_exp_loop_kept_created",
        "auto_discovery_experiment",
        ["loop_type", "kept", "created_at"],
    )


def downgrade():
    op.drop_index("ix_auto_disc_exp_loop_kept_created", table_name="auto_discovery_experiment")
    op.drop_index("ix_auto_disc_exp_athlete_loop_created", table_name="auto_discovery_experiment")
    op.drop_index("ix_auto_disc_exp_run_id", table_name="auto_discovery_experiment")
    op.drop_table("auto_discovery_experiment")
    op.drop_index("ix_auto_discovery_run_status_started", table_name="auto_discovery_run")
    op.drop_index("ix_auto_discovery_run_athlete_started", table_name="auto_discovery_run")
    op.drop_table("auto_discovery_run")
