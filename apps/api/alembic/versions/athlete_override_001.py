"""athlete_override_001 — athlete overrides for fitness bank values

Athlete-specified overrides for peak_weekly_miles, peak_long_run_miles, and RPI.
The algorithm computes these from history, but the athlete knows context the
data can't capture (compromised races, illness, injury context).

Revision ID: athlete_override_001
Revises:     workout_fluency_001
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "athlete_override_001"
down_revision = "workout_fluency_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "athlete_override",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("athlete_id", UUID(as_uuid=True), sa.ForeignKey("athlete.id"), nullable=False, unique=True),
        sa.Column("peak_weekly_miles", sa.Float(), nullable=True),
        sa.Column("peak_long_run_miles", sa.Float(), nullable=True),
        sa.Column("rpi", sa.Float(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_athlete_override_athlete_id", "athlete_override", ["athlete_id"])


def downgrade() -> None:
    op.drop_index("ix_athlete_override_athlete_id", table_name="athlete_override")
    op.drop_table("athlete_override")
