"""add_athlete_trial_fields

Revision ID: c4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-01-24

Phase 6: add 7-day trial fields to athlete
- trial_started_at
- trial_ends_at
- trial_source
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("athlete", sa.Column("trial_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("athlete", sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("athlete", sa.Column("trial_source", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("athlete", "trial_source")
    op.drop_column("athlete", "trial_ends_at")
    op.drop_column("athlete", "trial_started_at")

