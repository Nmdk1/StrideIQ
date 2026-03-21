"""workout_fluency_001 — nullable workout_variant_id on planned_workout

Phase 3 (workout fluency): persist registry variant id when the framework
generator can resolve a deterministic mapping from engine output.

Revision ID: workout_fluency_001
Revises:     admin_tier_override_001
"""

from alembic import op
import sqlalchemy as sa

revision = "workout_fluency_001"
down_revision = "admin_tier_override_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "planned_workout",
        sa.Column("workout_variant_id", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("planned_workout", "workout_variant_id")
