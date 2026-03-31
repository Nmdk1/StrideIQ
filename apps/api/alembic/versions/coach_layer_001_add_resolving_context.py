"""Add resolving_context to correlation_finding for coach layer attribution.

When a finding transitions from active to resolving, this field captures
what the athlete did that caused the shift (e.g., "Volume emphasis during
build phase, weeks 4-12"). The coach reads it to attribute progress.

Revision ID: coach_layer_001
Revises: lifecycle_state_001
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa


revision = "coach_layer_001"
down_revision = "lifecycle_state_001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "correlation_finding",
        sa.Column("resolving_context", sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_column("correlation_finding", "resolving_context")
