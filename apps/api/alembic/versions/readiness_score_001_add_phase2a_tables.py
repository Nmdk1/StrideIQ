"""Add Phase 2A readiness score tables

Revision ID: readiness_score_001
Revises: None (standalone — uses CREATE TABLE IF NOT EXISTS for safety)
Create Date: 2026-02-12

Creates tables for Phase 2A: Readiness Score (Signal, Not Rule):
- daily_readiness: stores daily readiness computation results
- athlete_adaptation_thresholds: per-athlete threshold parameters
- threshold_calibration_log: readiness-at-decision + outcome pairs for calibration
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = 'readiness_score_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ---------------------------------------------------------------
    # daily_readiness — one row per athlete per day
    # ---------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS daily_readiness (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            athlete_id UUID NOT NULL REFERENCES athlete(id),
            date DATE NOT NULL,
            score FLOAT NOT NULL,
            components JSONB,
            signals_available INTEGER NOT NULL DEFAULT 0,
            signals_total INTEGER NOT NULL DEFAULT 5,
            confidence FLOAT NOT NULL DEFAULT 0.0,
            weights_used JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_daily_readiness_athlete_date UNIQUE (athlete_id, date)
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_daily_readiness_athlete_date
        ON daily_readiness (athlete_id, date);
    """)

    # ---------------------------------------------------------------
    # athlete_adaptation_thresholds — per-athlete parameters
    # ---------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS athlete_adaptation_thresholds (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            athlete_id UUID NOT NULL REFERENCES athlete(id) UNIQUE,
            swap_quality_threshold FLOAT NOT NULL DEFAULT 35.0,
            reduce_volume_threshold FLOAT NOT NULL DEFAULT 25.0,
            skip_day_threshold FLOAT NOT NULL DEFAULT 15.0,
            increase_volume_threshold FLOAT NOT NULL DEFAULT 80.0,
            calibration_data_points INTEGER NOT NULL DEFAULT 0,
            last_calibrated_at TIMESTAMPTZ,
            calibration_confidence FLOAT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_aat_athlete_id
        ON athlete_adaptation_thresholds (athlete_id);
    """)

    # ---------------------------------------------------------------
    # threshold_calibration_log — readiness + outcome pairs
    # ---------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS threshold_calibration_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            athlete_id UUID NOT NULL REFERENCES athlete(id),
            workout_id UUID REFERENCES planned_workout(id),
            readiness_score FLOAT NOT NULL,
            workout_type_scheduled TEXT,
            outcome TEXT,
            efficiency_delta FLOAT,
            subjective_feel INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_threshold_cal_log_athlete_date
        ON threshold_calibration_log (athlete_id, created_at);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS threshold_calibration_log;")
    op.execute("DROP TABLE IF EXISTS athlete_adaptation_thresholds;")
    op.execute("DROP TABLE IF EXISTS daily_readiness;")
