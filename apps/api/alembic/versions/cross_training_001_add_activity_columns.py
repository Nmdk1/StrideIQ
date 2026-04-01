"""Add cross-training columns to activity table.

garmin_activity_type: preserves raw Garmin activityType string for audit.
cadence_unit: spm (run/walk/hike), rpm (cycling), null (strength/flexibility).
session_detail: JSONB for non-run detail payloads (Phase A parsing later).

Revision ID: cross_training_001
Revises: coach_layer_001
Create Date: 2026-04-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "cross_training_001"
down_revision = "coach_layer_001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "activity",
        sa.Column("garmin_activity_type", sa.Text(), nullable=True),
    )
    op.add_column(
        "activity",
        sa.Column("cadence_unit", sa.Text(), nullable=True),
    )
    op.add_column(
        "activity",
        sa.Column("session_detail", JSONB(), nullable=True),
    )


def downgrade():
    op.drop_column("activity", "session_detail")
    op.drop_column("activity", "cadence_unit")
    op.drop_column("activity", "garmin_activity_type")
