"""Add AI consent fields to athlete and create consent_audit_log table

Revision ID: consent_001
Revises: corr_persist_001
Create Date: 2026-02-19

Phase 1: Consent Infrastructure (P1-B)
Adds explicit opt-in consent tracking for AI processing.
Default deny: all existing athletes get ai_consent=False after migration.

See docs/PHASE1_CONSENT_INFRASTRUCTURE_AC.md for full spec.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = "consent_001"
down_revision: Union[str, None] = "corr_persist_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add ai_consent fields to athlete table
    # server_default="false" ensures existing rows get ai_consent=False (default deny)
    op.add_column(
        "athlete",
        sa.Column(
            "ai_consent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "athlete",
        sa.Column("ai_consent_granted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "athlete",
        sa.Column("ai_consent_revoked_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create consent_audit_log table
    op.create_table(
        "consent_audit_log",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "athlete_id",
            UUID(as_uuid=True),
            sa.ForeignKey("athlete.id"),
            nullable=False,
        ),
        sa.Column("consent_type", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("ip_address", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Indexes for audit log
    op.create_index("ix_consent_audit_log_athlete_id", "consent_audit_log", ["athlete_id"])
    op.create_index("ix_consent_audit_log_created_at", "consent_audit_log", ["created_at"])


def downgrade() -> None:
    # Drop consent_audit_log table
    op.drop_index("ix_consent_audit_log_created_at", table_name="consent_audit_log")
    op.drop_index("ix_consent_audit_log_athlete_id", table_name="consent_audit_log")
    op.drop_table("consent_audit_log")

    # Remove ai_consent fields from athlete
    op.drop_column("athlete", "ai_consent_revoked_at")
    op.drop_column("athlete", "ai_consent_granted_at")
    op.drop_column("athlete", "ai_consent")
