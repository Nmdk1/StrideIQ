"""Add correlation_finding table for persistent reproducibility tracking

Revision ID: corr_persist_001
Revises: demo_guard_001
Create Date: 2026-02-13

Stores significant correlation findings (e.g., sleep → efficiency) with
a times_confirmed counter that grows each time the engine re-confirms the
relationship.  Only reproducible findings are surfaced to athletes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = "corr_persist_001"
down_revision: Union[str, None] = "demo_guard_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "correlation_finding",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("athlete_id", UUID(as_uuid=True), sa.ForeignKey("athlete.id"), nullable=False),

        # What was correlated
        sa.Column("input_name", sa.Text(), nullable=False),
        sa.Column("output_metric", sa.Text(), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("time_lag_days", sa.Integer(), nullable=False, server_default=sa.text("0")),

        # Statistical strength (most recent computation)
        sa.Column("correlation_coefficient", sa.Float(), nullable=False),
        sa.Column("p_value", sa.Float(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("strength", sa.Text(), nullable=False),

        # Reproducibility tracking
        sa.Column("times_confirmed", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("first_detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_confirmed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_surfaced_at", sa.DateTime(timezone=True), nullable=True),

        # Human-readable insight text
        sa.Column("insight_text", sa.Text(), nullable=True),

        # Categorization
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),

        # Lifecycle
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    # Indexes
    op.create_index("ix_corr_finding_athlete", "correlation_finding", ["athlete_id"])
    op.create_index(
        "uq_corr_finding_natural_key",
        "correlation_finding",
        ["athlete_id", "input_name", "output_metric", "time_lag_days"],
        unique=True,
    )
    op.create_index("ix_corr_finding_active", "correlation_finding", ["athlete_id", "is_active"])


def downgrade() -> None:
    op.drop_index("ix_corr_finding_active", table_name="correlation_finding")
    op.drop_index("uq_corr_finding_natural_key", table_name="correlation_finding")
    op.drop_index("ix_corr_finding_athlete", table_name="correlation_finding")
    op.drop_table("correlation_finding")
