"""Add partial index on activity(athlete_id, start_time) WHERE sport = 'run'.

The overwhelming majority of queries filter Activity.sport == 'run'. With
cross-training data flowing in, a partial index keeps those queries fast
without indexing cycling/walking/hiking/strength/flexibility rows.

Revision ID: cross_training_002
Revises: cross_training_001
Create Date: 2026-04-01
"""
from alembic import op


revision = "cross_training_002"
down_revision = "cross_training_001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_activity_athlete_start_run",
        "activity",
        ["athlete_id", "start_time"],
        postgresql_where="sport = 'run'",
    )


def downgrade():
    op.drop_index("ix_activity_athlete_start_run", table_name="activity")
