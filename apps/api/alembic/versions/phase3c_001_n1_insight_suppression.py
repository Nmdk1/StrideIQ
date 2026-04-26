"""Add n1_insight_suppression table (Phase 3C graduation).

Revision ID: phase3c_001
Revises: auto_discovery_002
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "phase3c_001"
down_revision = "auto_discovery_002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "n1_insight_suppression",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("athlete_id", UUID(as_uuid=True),
                  sa.ForeignKey("athlete.id"), nullable=False),
        sa.Column("insight_fingerprint", sa.Text, nullable=False),
        sa.Column("suppressed_by", sa.Text, nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_unique_constraint(
        "uq_n1_suppression_athlete_fingerprint",
        "n1_insight_suppression",
        ["athlete_id", "insight_fingerprint"],
    )
    op.create_index(
        "ix_n1_suppression_athlete",
        "n1_insight_suppression",
        ["athlete_id"],
    )


def downgrade():
    op.drop_index("ix_n1_suppression_athlete", table_name="n1_insight_suppression")
    op.drop_constraint("uq_n1_suppression_athlete_fingerprint",
                       "n1_insight_suppression", type_="unique")
    op.drop_table("n1_insight_suppression")
