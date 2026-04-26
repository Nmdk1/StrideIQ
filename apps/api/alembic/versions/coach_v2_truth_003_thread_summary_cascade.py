"""Add cascade delete to Coach V2 thread summary athlete FK.

Revision ID: coach_v2_truth_003
Revises: coach_v2_truth_002
Create Date: 2026-04-26
"""

from alembic import op

revision = "coach_v2_truth_003"
down_revision = "coach_v2_truth_002"
branch_labels = None
depends_on = None

CONSTRAINT_NAME = "coach_thread_summary_athlete_id_fkey"


def upgrade() -> None:
    op.drop_constraint(
        CONSTRAINT_NAME,
        "coach_thread_summary",
        type_="foreignkey",
    )
    op.create_foreign_key(
        CONSTRAINT_NAME,
        "coach_thread_summary",
        "athlete",
        ["athlete_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        CONSTRAINT_NAME,
        "coach_thread_summary",
        type_="foreignkey",
    )
    op.create_foreign_key(
        CONSTRAINT_NAME,
        "coach_thread_summary",
        "athlete",
        ["athlete_id"],
        ["id"],
    )
