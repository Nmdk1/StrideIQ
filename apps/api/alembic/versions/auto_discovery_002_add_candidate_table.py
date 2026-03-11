"""Add auto_discovery_candidate and auto_discovery_review_log tables (Phase 0C).

Revision ID: auto_discovery_002
Revises: auto_discovery_001
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "auto_discovery_002"
down_revision = "auto_discovery_001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "auto_discovery_candidate",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("athlete_id", UUID(as_uuid=True), sa.ForeignKey("athlete.id"), nullable=False),
        sa.Column("candidate_type", sa.Text(), nullable=False),
        sa.Column("candidate_key", sa.Text(), nullable=False),
        sa.Column(
            "first_seen_run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("auto_discovery_run.id"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("auto_discovery_run.id"),
            nullable=False,
        ),
        sa.Column("times_seen", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("current_status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("latest_summary", JSONB(), nullable=True),
        sa.Column("latest_score", sa.Float(), nullable=True),
        sa.Column("latest_score_delta", sa.Float(), nullable=True),
        sa.Column("provenance_snapshot", JSONB(), nullable=True),
        sa.Column("promotion_target", sa.Text(), nullable=True),
        sa.Column("promotion_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "athlete_id",
            "candidate_type",
            "candidate_key",
            name="uq_auto_disc_candidate_athlete_type_key",
        ),
    )
    op.create_index(
        "ix_auto_disc_candidate_athlete_status",
        "auto_discovery_candidate",
        ["athlete_id", "current_status"],
    )
    op.create_index(
        "ix_auto_disc_candidate_type_status",
        "auto_discovery_candidate",
        ["candidate_type", "current_status"],
    )
    op.create_index(
        "ix_auto_disc_candidate_times_seen",
        "auto_discovery_candidate",
        ["athlete_id", "times_seen"],
    )

    op.create_table(
        "auto_discovery_review_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "candidate_id",
            UUID(as_uuid=True),
            sa.ForeignKey("auto_discovery_candidate.id"),
            nullable=False,
        ),
        sa.Column("athlete_id", UUID(as_uuid=True), sa.ForeignKey("athlete.id"), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("previous_status", sa.Text(), nullable=True),
        sa.Column("new_status", sa.Text(), nullable=False),
        sa.Column("promotion_target", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_auto_disc_review_log_candidate",
        "auto_discovery_review_log",
        ["candidate_id"],
    )
    op.create_index(
        "ix_auto_disc_review_log_athlete_created",
        "auto_discovery_review_log",
        ["athlete_id", "created_at"],
    )


def downgrade():
    op.drop_index("ix_auto_disc_review_log_athlete_created", table_name="auto_discovery_review_log")
    op.drop_index("ix_auto_disc_review_log_candidate", table_name="auto_discovery_review_log")
    op.drop_table("auto_discovery_review_log")
    op.drop_index("ix_auto_disc_candidate_times_seen", table_name="auto_discovery_candidate")
    op.drop_index("ix_auto_disc_candidate_type_status", table_name="auto_discovery_candidate")
    op.drop_index("ix_auto_disc_candidate_athlete_status", table_name="auto_discovery_candidate")
    op.drop_table("auto_discovery_candidate")
