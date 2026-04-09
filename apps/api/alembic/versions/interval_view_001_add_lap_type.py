"""Add lap_type and interval_number to activity_split

Revision ID: interval_view_001
Revises: adaptive_replan_001_proposal_table
Create Date: 2026-04-09
"""
from alembic import op
import sqlalchemy as sa

revision = "interval_view_001"
down_revision = "nutrition_intelligence_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "activity_split",
        sa.Column("lap_type", sa.Text(), nullable=True),
    )
    op.add_column(
        "activity_split",
        sa.Column("interval_number", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("activity_split", "interval_number")
    op.drop_column("activity_split", "lap_type")
