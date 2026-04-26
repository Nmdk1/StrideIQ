"""Add training_block table

Revision ID: training_block_001
Revises: route_fp_001
Create Date: 2026-04-17

Phase 4 of the comparison product family. Stores detected training blocks
(multi-week periods of consistent training, labeled with phase: base /
build / peak / taper / race / recovery / off). Populated by a Celery
backfill task and re-detected nightly.

Idempotent: CREATE TABLE IF NOT EXISTS, no data backfill in the migration.
"""

from alembic import op


revision = "training_block_001"
down_revision = "route_fp_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS training_block (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            athlete_id UUID NOT NULL REFERENCES athlete(id),
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            weeks INTEGER NOT NULL,
            phase TEXT NOT NULL,
            total_distance_m INTEGER NOT NULL DEFAULT 0,
            total_duration_s INTEGER NOT NULL DEFAULT 0,
            run_count INTEGER NOT NULL DEFAULT 0,
            peak_week_distance_m INTEGER NOT NULL DEFAULT 0,
            longest_run_m INTEGER,
            workout_type_counts JSONB NOT NULL DEFAULT '{}'::jsonb,
            dominant_workout_types JSONB NOT NULL DEFAULT '[]'::jsonb,
            quality_pct INTEGER NOT NULL DEFAULT 0,
            goal_event_name TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_training_block_athlete_start "
        "ON training_block (athlete_id, start_date);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_training_block_athlete_phase "
        "ON training_block (athlete_id, phase);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_training_block_athlete_phase;")
    op.execute("DROP INDEX IF EXISTS ix_training_block_athlete_start;")
    op.execute("DROP TABLE IF EXISTS training_block;")
