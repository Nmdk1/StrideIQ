"""Add athlete_fact table and coach_chat.last_extracted_msg_count.

Revision ID: athlete_fact_001
Revises: exp_audit_001
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "athlete_fact_001"
down_revision = "exp_audit_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "athlete_fact",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("athlete_id", UUID(as_uuid=True), sa.ForeignKey("athlete.id"), nullable=False, index=True),
        sa.Column("fact_type", sa.Text(), nullable=False),
        sa.Column("fact_key", sa.Text(), nullable=False),
        sa.Column("fact_value", sa.Text(), nullable=False),
        sa.Column("numeric_value", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Text(), nullable=False, server_default="athlete_stated"),
        sa.Column("source_chat_id", UUID(as_uuid=True), sa.ForeignKey("coach_chat.id"), nullable=False),
        sa.Column("source_excerpt", sa.Text(), nullable=False),
        sa.Column("confirmed_by_athlete", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("extracted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )

    op.create_index(
        "ix_athlete_fact_athlete_active", "athlete_fact", ["athlete_id", "is_active"],
    )
    op.create_index(
        "ix_athlete_fact_key_lookup", "athlete_fact", ["athlete_id", "fact_key"],
    )
    op.create_index(
        "uq_athlete_fact_active_key", "athlete_fact",
        ["athlete_id", "fact_key"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )

    op.add_column(
        "coach_chat",
        sa.Column("last_extracted_msg_count", sa.Integer(), nullable=True, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("coach_chat", "last_extracted_msg_count")
    op.drop_index("uq_athlete_fact_active_key", table_name="athlete_fact")
    op.drop_index("ix_athlete_fact_key_lookup", table_name="athlete_fact")
    op.drop_index("ix_athlete_fact_athlete_active", table_name="athlete_fact")
    op.drop_table("athlete_fact")
