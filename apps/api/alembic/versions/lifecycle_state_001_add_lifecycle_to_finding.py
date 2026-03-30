"""Add lifecycle_state to correlation_finding for limiter lifecycle tracking.

See LIMITER_TAXONOMY_ANNOTATED.md for state definitions:
  emerging, active, active_fixed, resolving, closed, structural

Revision ID: lifecycle_state_001
Revises: fingerprint_bridge_001
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa


revision = "lifecycle_state_001"
down_revision = "fingerprint_bridge_001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "correlation_finding",
        sa.Column("lifecycle_state", sa.Text(), nullable=True),
    )
    op.add_column(
        "correlation_finding",
        sa.Column(
            "lifecycle_state_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("correlation_finding", "lifecycle_state_updated_at")
    op.drop_column("correlation_finding", "lifecycle_state")
