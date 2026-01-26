"""add_3d_workout_selection_shadow_flag

Revision ID: b1c2d3e4f5a6
Revises: 7b8c9d0e1f23
Create Date: 2026-01-23

Adds a separate SHADOW rollout flag for ADR-036 3D workout selection.

We currently model off/shadow/on as:
- plan.3d_workout_selection (ON: serve 3D selection)
- plan.3d_workout_selection_shadow (SHADOW: compute + log diffs, serve legacy)
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "b1c2d3e4f5a6"
down_revision = "7b8c9d0e1f23"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fresh-install safety: ensure feature_flag exists before insert.
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

    op.execute(
        """
        INSERT INTO feature_flag (
            id,
            key,
            name,
            description,
            enabled,
            requires_subscription,
            requires_tier,
            rollout_percentage
        )
        VALUES (
            gen_random_uuid(),
            'plan.3d_workout_selection_shadow',
            '3D Workout Selection (SHADOW)',
            'ADR-036: Compute 3D quality-session selection and log diffs, but continue serving legacy prescriptions.',
            true,
            false,
            'elite',
            0
        )
        ON CONFLICT (key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM feature_flag WHERE key = 'plan.3d_workout_selection_shadow';")

