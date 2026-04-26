"""Add Coach V2 thread summary table.

Revision ID: coach_v2_truth_002
Revises: coach_v2_truth_001
Create Date: 2026-04-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "coach_v2_truth_002"
down_revision = "coach_v2_truth_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "coach_thread_summary",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "athlete_id",
            UUID(as_uuid=True),
            sa.ForeignKey("athlete.id"),
            nullable=False,
        ),
        sa.Column(
            "thread_id",
            UUID(as_uuid=True),
            sa.ForeignKey("coach_chat.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "topic_tags", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "decisions", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "open_questions",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "stated_facts",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.UniqueConstraint("thread_id", name="uq_coach_thread_summary_thread_id"),
    )
    op.create_index(
        "ix_coach_thread_summary_athlete_id",
        "coach_thread_summary",
        ["athlete_id"],
        unique=False,
    )
    op.create_index(
        "ix_coach_thread_summary_thread_id",
        "coach_thread_summary",
        ["thread_id"],
        unique=False,
    )
    op.create_index(
        "ix_coach_thread_summary_athlete_generated",
        "coach_thread_summary",
        ["athlete_id", "generated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_coach_thread_summary_athlete_generated",
        table_name="coach_thread_summary",
    )
    op.drop_index(
        "ix_coach_thread_summary_thread_id", table_name="coach_thread_summary"
    )
    op.drop_index(
        "ix_coach_thread_summary_athlete_id", table_name="coach_thread_summary"
    )
    op.drop_table("coach_thread_summary")
