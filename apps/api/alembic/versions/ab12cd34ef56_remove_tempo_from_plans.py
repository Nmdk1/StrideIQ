"""remove tempo from planned workouts

Revision ID: ab12cd34ef56
Revises: f0a1b2c3d4e5
Create Date: 2026-01-24
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "ab12cd34ef56"
down_revision = "f0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Normalize ambiguous tempo labels to threshold (canonical).
    op.execute("UPDATE planned_workout SET workout_type = 'threshold' WHERE workout_type IN ('tempo', 'tempo_short');")

    # Best-effort normalization inside structured segments for planned workouts.
    # Replace segment type 'tempo' with 'threshold' (jsonb update).
    op.execute(
        """
        UPDATE planned_workout
        SET segments = (
          SELECT COALESCE(
            jsonb_agg(
              CASE
                WHEN (elem->>'type') = 'tempo'
                  THEN jsonb_set(elem, '{type}', '\"threshold\"'::jsonb, true)
                ELSE elem
              END
            ),
            segments
          )
          FROM jsonb_array_elements(segments) AS elem
        )
        WHERE segments IS NOT NULL
          AND jsonb_typeof(segments) = 'array';
        """
    )


def downgrade() -> None:
    # Downgrade is lossy (tempo had ambiguous meaning). We revert only the simple type mapping.
    op.execute("UPDATE planned_workout SET workout_type = 'tempo' WHERE workout_type = 'threshold';")

