"""add_best_efforts_extracted_at_to_activity

Revision ID: 4b2f6d1a9c0e
Revises: 8c7b1b3c4d5e
Create Date: 2026-01-20

Adds an explicit marker for whether we've fetched Strava activity details
and attempted best_effort extraction.

Important: Strava's API `best_efforts` only appear when that activity set PRs,
so we cannot treat "has BestEffort rows" as a proxy for "processed."
"""

from alembic import op
import sqlalchemy as sa


revision = "4b2f6d1a9c0e"
down_revision = "8c7b1b3c4d5e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("activity", sa.Column("best_efforts_extracted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("activity", "best_efforts_extracted_at")

