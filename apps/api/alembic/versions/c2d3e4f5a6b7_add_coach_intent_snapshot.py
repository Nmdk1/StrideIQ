"""add_coach_intent_snapshot

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-01-23

Adds a persisted athlete intent snapshot for self-guided coaching.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "coach_intent_snapshot",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("athlete.id"), nullable=False, unique=True),
        sa.Column("training_intent", sa.Text(), nullable=True),
        sa.Column("next_event_date", sa.Date(), nullable=True),
        sa.Column("next_event_type", sa.Text(), nullable=True),
        sa.Column("pain_flag", sa.Text(), nullable=True),
        sa.Column("time_available_min", sa.Integer(), nullable=True),
        sa.Column("weekly_mileage_target", sa.Float(), nullable=True),
        sa.Column("what_feels_off", sa.Text(), nullable=True),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_index("ix_coach_intent_snapshot_athlete_id", "coach_intent_snapshot", ["athlete_id"])
    op.create_index("ix_coach_intent_snapshot_updated_at", "coach_intent_snapshot", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_coach_intent_snapshot_updated_at", table_name="coach_intent_snapshot")
    op.drop_index("ix_coach_intent_snapshot_athlete_id", table_name="coach_intent_snapshot")
    op.drop_table("coach_intent_snapshot")

