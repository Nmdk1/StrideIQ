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

