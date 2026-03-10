"""Add Phase 2B self-regulation and insight logging tables

Revision ID: self_regulation_001
Revises: readiness_score_001 (chained — uses IF NOT EXISTS / IF NOT ADD for safety)
Create Date: 2026-02-12

Phase 2B: Workout State Machine + Self-Regulation Tracking
- New fields on planned_workout: actual_workout_type, planned_vs_actual_delta,
  readiness_at_execution, execution_state
- New table: self_regulation_log
- New table: insight_log
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = 'self_regulation_001'
down_revision = 'readiness_score_001'
branch_labels = None
depends_on = None


def upgrade():
    # ---------------------------------------------------------------
    # New columns on planned_workout
    # ---------------------------------------------------------------
    conn = op.get_bind()

    # Check which columns already exist to be idempotent
    existing = set()
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'planned_workout'"
    ))
    for row in result:
        existing.add(row[0])

    if 'actual_workout_type' not in existing:
        op.add_column('planned_workout', sa.Column('actual_workout_type', sa.Text(), nullable=True))

    if 'planned_vs_actual_delta' not in existing:
        op.add_column('planned_workout', sa.Column('planned_vs_actual_delta', JSONB, nullable=True))

    if 'readiness_at_execution' not in existing:
        op.add_column('planned_workout', sa.Column('readiness_at_execution', sa.Float(), nullable=True))

    if 'execution_state' not in existing:
        op.add_column('planned_workout', sa.Column('execution_state', sa.Text(), nullable=True))

    # ---------------------------------------------------------------
    # self_regulation_log
    # ---------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS self_regulation_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            athlete_id UUID NOT NULL REFERENCES athlete(id),
            workout_id UUID REFERENCES planned_workout(id),
            activity_id UUID REFERENCES activity(id),

            planned_type TEXT,
            planned_distance_km FLOAT,
            planned_intensity TEXT,

            actual_type TEXT,
            actual_distance_km FLOAT,
            actual_intensity TEXT,

            delta_type TEXT NOT NULL,
            delta_direction TEXT,

            readiness_at_decision FLOAT,
            trigger_date DATE NOT NULL,

            outcome_efficiency_delta FLOAT,
            outcome_subjective INTEGER,
            outcome_classification TEXT,

            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_self_reg_log_athlete_date
        ON self_regulation_log (athlete_id, trigger_date);
    """)

    # ---------------------------------------------------------------
    # insight_log
    # ---------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS insight_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            athlete_id UUID NOT NULL REFERENCES athlete(id),

            rule_id TEXT NOT NULL,
            mode TEXT NOT NULL,
            message TEXT,
            data_cited JSONB,

            trigger_date DATE NOT NULL,
            readiness_score FLOAT,
            confidence FLOAT,

            athlete_seen BOOLEAN NOT NULL DEFAULT FALSE,
            athlete_response TEXT,
            athlete_response_at TIMESTAMPTZ,

            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_insight_log_athlete_date
        ON insight_log (athlete_id, trigger_date);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_insight_log_rule_id
        ON insight_log (rule_id);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS insight_log;")
    op.execute("DROP TABLE IF EXISTS self_regulation_log;")

    # Remove columns from planned_workout
    for col in ['actual_workout_type', 'planned_vs_actual_delta',
                'readiness_at_execution', 'execution_state']:
        try:
            op.drop_column('planned_workout', col)
        except Exception:
            pass
