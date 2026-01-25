"""add coach action proposals

Revision ID: c10a0b1c2d3e
Revises: b39bc8e9ddf1
Create Date: 2026-01-25

Phase 10: Coach Action Automation (propose → confirm → apply)

Creates `coach_action_proposals` table to store a durable, auditable proposal
and an apply receipt for deterministic plan modifications.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c10a0b1c2d3e"
down_revision: Union[str, None] = "b39bc8e9ddf1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "coach_action_proposals" not in inspector.get_table_names():
        op.create_table(
            "coach_action_proposals",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("athlete_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("athlete.id"), nullable=False),
            sa.Column(
                "created_by",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("status", sa.Text(), nullable=False),
            sa.Column("actions_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            # Extras (Phase 10 design)
            sa.Column("idempotency_key", sa.Text(), nullable=True),
            sa.Column("target_plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("training_plan.id"), nullable=True),
            sa.Column("apply_receipt_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )

    existing_indexes = {ix["name"] for ix in inspector.get_indexes("coach_action_proposals")}

    if "ix_coach_action_proposals_athlete_id" not in existing_indexes:
        op.create_index("ix_coach_action_proposals_athlete_id", "coach_action_proposals", ["athlete_id"], unique=False)
    if "ix_coach_action_proposals_status" not in existing_indexes:
        op.create_index("ix_coach_action_proposals_status", "coach_action_proposals", ["status"], unique=False)
    if "ix_coach_action_proposals_created_at" not in existing_indexes:
        op.create_index(
            "ix_coach_action_proposals_created_at",
            "coach_action_proposals",
            ["created_at"],
            unique=False,
        )
    if "ux_coach_action_proposals_athlete_id_idempotency_key" not in existing_indexes:
        op.create_index(
            "ux_coach_action_proposals_athlete_id_idempotency_key",
            "coach_action_proposals",
            ["athlete_id", "idempotency_key"],
            unique=True,
            postgresql_where=sa.text("idempotency_key IS NOT NULL"),
        )


def downgrade() -> None:
    op.drop_index("ux_coach_action_proposals_athlete_id_idempotency_key", table_name="coach_action_proposals")
    op.drop_index("ix_coach_action_proposals_created_at", table_name="coach_action_proposals")
    op.drop_index("ix_coach_action_proposals_status", table_name="coach_action_proposals")
    op.drop_index("ix_coach_action_proposals_athlete_id", table_name="coach_action_proposals")
    op.drop_table("coach_action_proposals")

