"""race_anchor: change unique constraint from athlete_id to (athlete_id, distance_key)

Revision ID: race_anchor_001
Revises: workout_fluency_001
Create Date: 2026-03-24

WS-A spec: allow one anchor row per distance key per athlete, preserving the best
result for each distance (10K, half, marathon, etc.) independently.

Production schema note: the existing single-athlete unique constraint lives as index
'uq_race_anchor_athlete' on athlete_id; 'ix_race_anchor_athlete_id' (non-unique) and
'ix_race_anchor_distance_key' already exist and are left unchanged.
"""
from __future__ import annotations

import sqlalchemy as sa  # noqa: F401 — reserved for future op compatibility
from alembic import op

# revision identifiers, used by Alembic.
revision = "race_anchor_001"
down_revision = "workout_fluency_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the old single-athlete unique constraint.
    # Production: named "uq_race_anchor_athlete" (a named constraint + backing index).
    # Fresh schema: may be named "ix_athlete_race_result_anchor_athlete_id" (plain unique index,
    # no separate constraint object). We handle both with conditional DDL.
    op.execute("""
        DO $$
        BEGIN
            -- Named constraint path (production)
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_race_anchor_athlete'
                  AND conrelid = 'athlete_race_result_anchor'::regclass
            ) THEN
                ALTER TABLE athlete_race_result_anchor DROP CONSTRAINT uq_race_anchor_athlete;
            END IF;
            -- Plain unique index path (fresh schema / CI)
            DROP INDEX IF EXISTS ix_athlete_race_result_anchor_athlete_id;
        END
        $$;
    """)
    # Add composite unique: one anchor row per (athlete, distance)
    op.create_unique_constraint(
        "uq_anchor_athlete_distance",
        "athlete_race_result_anchor",
        ["athlete_id", "distance_key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_anchor_athlete_distance", "athlete_race_result_anchor", type_="unique")
    # Restore single-athlete uniqueness under the production constraint name.
    op.create_unique_constraint(
        "uq_race_anchor_athlete",
        "athlete_race_result_anchor",
        ["athlete_id"],
    )
