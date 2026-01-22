"""add_best_effort_table_for_pbs

Revision ID: 8c7b1b3c4d5e
Revises: 3a0f8c0e9c21
Create Date: 2026-01-20

PB integrity fix:
- The codebase derives PersonalBest from the Strava-derived BestEffort table.
- Some environments were created via `run_migrations.py` schema creation which did
  not include `BestEffort`, leaving the `best_effort` table missing.

This migration creates `best_effort` if it doesn't already exist.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = "8c7b1b3c4d5e"
down_revision = "3a0f8c0e9c21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "best_effort" in inspector.get_table_names():
        return

    op.create_table(
        "best_effort",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("athlete_id", UUID(as_uuid=True), nullable=False),
        sa.Column("activity_id", UUID(as_uuid=True), nullable=False),
        sa.Column("distance_category", sa.Text(), nullable=False),
        sa.Column("distance_meters", sa.Integer(), nullable=False),
        sa.Column("elapsed_time", sa.Integer(), nullable=False),
        sa.Column("achieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("strava_effort_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["activity_id"], ["activity.id"]),
        sa.ForeignKeyConstraint(["athlete_id"], ["athlete.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("activity_id", "strava_effort_id", name="uq_best_effort_activity_strava"),
    )

    op.create_index("ix_best_effort_activity_id", "best_effort", ["activity_id"], unique=False)
    op.create_index("ix_best_effort_athlete_id", "best_effort", ["athlete_id"], unique=False)
    op.create_index("ix_best_effort_distance_category", "best_effort", ["distance_category"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "best_effort" not in inspector.get_table_names():
        return

    op.drop_index("ix_best_effort_distance_category", table_name="best_effort")
    op.drop_index("ix_best_effort_athlete_id", table_name="best_effort")
    op.drop_index("ix_best_effort_activity_id", table_name="best_effort")
    op.drop_table("best_effort")

