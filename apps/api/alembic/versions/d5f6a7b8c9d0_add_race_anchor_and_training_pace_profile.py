"""add race anchor and training pace profile

Revision ID: d5f6a7b8c9d0
Revises: c4e5f6a7b8c9
Create Date: 2026-01-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "d5f6a7b8c9d0"
down_revision = "c4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fresh-install safety: ensure feature_flag exists before insert seeds below.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS feature_flag (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            key TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            description TEXT,
            enabled BOOLEAN NOT NULL DEFAULT false,
            requires_subscription BOOLEAN NOT NULL DEFAULT false,
            requires_tier TEXT,
            requires_payment NUMERIC(10,2),
            rollout_percentage INTEGER NOT NULL DEFAULT 100,
            allowed_athlete_ids JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    # --- AthleteRaceResultAnchor ---
    op.create_table(
        "athlete_race_result_anchor",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("athlete.id"), nullable=False),
        sa.Column("distance_key", sa.Text(), nullable=False),
        sa.Column("distance_meters", sa.Integer(), nullable=True),
        sa.Column("time_seconds", sa.Integer(), nullable=False),
        sa.Column("race_date", sa.Date(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default="user"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("athlete_id", name="uq_race_anchor_athlete"),
    )
    op.create_index("ix_race_anchor_athlete_id", "athlete_race_result_anchor", ["athlete_id"])
    op.create_index("ix_race_anchor_distance_key", "athlete_race_result_anchor", ["distance_key"])

    # --- AthleteTrainingPaceProfile ---
    op.create_table(
        "athlete_training_pace_profile",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("athlete.id"), nullable=False),
        sa.Column(
            "race_anchor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("athlete_race_result_anchor.id"),
            nullable=False,
        ),
        sa.Column("fitness_score", sa.Float(), nullable=True),
        sa.Column("paces", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("athlete_id", name="uq_training_pace_profile_athlete"),
    )
    op.create_index("ix_training_pace_profile_athlete_id", "athlete_training_pace_profile", ["athlete_id"])
    op.create_index("ix_training_pace_profile_race_anchor_id", "athlete_training_pace_profile", ["race_anchor_id"])

    # --- Feature flag seed: onboarding.pace_calibration_v1 ---
    # Insert only if missing (safe for re-runs).
    op.execute(
        """
        INSERT INTO feature_flag (key, name, description, enabled, requires_subscription, requires_tier, requires_payment, rollout_percentage, created_at, updated_at)
        SELECT
          'onboarding.pace_calibration_v1',
          'Onboarding pace calibration (race result)',
          'Collect a recent race/time-trial result in onboarding and compute Training Pace Calculator paces. If missing, show explicit no-prescriptive-paces messaging.',
          TRUE,
          FALSE,
          NULL,
          NULL,
          100,
          now(),
          now()
        WHERE NOT EXISTS (
          SELECT 1 FROM feature_flag WHERE key = 'onboarding.pace_calibration_v1'
        );
        """
    )

def downgrade() -> None:
    op.execute("DELETE FROM feature_flag WHERE key = 'onboarding.pace_calibration_v1';")

    op.drop_index("ix_training_pace_profile_race_anchor_id", table_name="athlete_training_pace_profile")
    op.drop_index("ix_training_pace_profile_athlete_id", table_name="athlete_training_pace_profile")
    op.drop_table("athlete_training_pace_profile")

    op.drop_index("ix_race_anchor_distance_key", table_name="athlete_race_result_anchor")
    op.drop_index("ix_race_anchor_athlete_id", table_name="athlete_race_result_anchor")
    op.drop_table("athlete_race_result_anchor")

