"""race_anchor: change unique constraint from athlete_id to (athlete_id, distance_key)

Revision ID: race_anchor_001
Revises: workout_fluency_001
Create Date: 2026-03-24

WS-A spec: allow one anchor row per distance key per athlete, preserving the best
result for each distance (10K, half, marathon, etc.) independently.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "race_anchor_001"
down_revision = "workout_fluency_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove the single-athlete unique constraint (index + unique column constraint)
    op.drop_index("ix_athlete_race_result_anchor_athlete_id", table_name="athlete_race_result_anchor")
    # The unique=True in SQLAlchemy creates both an index and a unique constraint.
    # Drop the unique constraint by recreating the index as non-unique:
    op.create_index(
        "ix_athlete_race_result_anchor_athlete_id",
        "athlete_race_result_anchor",
        ["athlete_id"],
        unique=False,
    )
    # Add composite unique: one anchor per athlete per distance
    op.create_unique_constraint(
        "uq_anchor_athlete_distance",
        "athlete_race_result_anchor",
        ["athlete_id", "distance_key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_anchor_athlete_distance", "athlete_race_result_anchor", type_="unique")
    op.drop_index("ix_athlete_race_result_anchor_athlete_id", table_name="athlete_race_result_anchor")
    op.create_index(
        "ix_athlete_race_result_anchor_athlete_id",
        "athlete_race_result_anchor",
        ["athlete_id"],
        unique=True,
    )
