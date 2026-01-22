"""add_athlete_ingestion_state_table

Revision ID: 5c9a1f3d2e11
Revises: 4b2f6d1a9c0e
Create Date: 2026-01-20

Adds a durable per-athlete ingestion state row for operational visibility:
- last task id
- last run start/finish
- last error
- last run counters

This intentionally does NOT store per-activity progress (that lives on `activity.*`).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "5c9a1f3d2e11"
down_revision = "4b2f6d1a9c0e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "athlete_ingestion_state",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("athlete_id", UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False, server_default=sa.text("'strava'")),
        sa.Column("last_best_efforts_task_id", sa.Text(), nullable=True),
        sa.Column("last_best_efforts_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_best_efforts_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_best_efforts_status", sa.Text(), nullable=True),
        sa.Column("last_best_efforts_error", sa.Text(), nullable=True),
        sa.Column("last_best_efforts_retry_after_s", sa.Integer(), nullable=True),
        sa.Column("last_best_efforts_activities_checked", sa.Integer(), nullable=True),
        sa.Column("last_best_efforts_efforts_stored", sa.Integer(), nullable=True),
        sa.Column("last_best_efforts_pbs_created", sa.Integer(), nullable=True),
        sa.Column("last_index_task_id", sa.Text(), nullable=True),
        sa.Column("last_index_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_index_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_index_status", sa.Text(), nullable=True),
        sa.Column("last_index_error", sa.Text(), nullable=True),
        sa.Column("last_index_pages_fetched", sa.Integer(), nullable=True),
        sa.Column("last_index_created", sa.Integer(), nullable=True),
        sa.Column("last_index_already_present", sa.Integer(), nullable=True),
        sa.Column("last_index_skipped_non_runs", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["athlete_id"], ["athlete.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("athlete_id", "provider", name="uq_ingestion_state_athlete_provider"),
    )

    op.create_index("ix_athlete_ingestion_state_athlete_id", "athlete_ingestion_state", ["athlete_id"], unique=False)
    op.create_index("ix_ingestion_state_provider", "athlete_ingestion_state", ["provider"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ingestion_state_provider", table_name="athlete_ingestion_state")
    op.drop_index("ix_athlete_ingestion_state_athlete_id", table_name="athlete_ingestion_state")
    op.drop_table("athlete_ingestion_state")

