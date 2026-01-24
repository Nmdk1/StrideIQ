"""add_invite_allowlist_and_audit

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-01-24

Phase 3: DB-backed invite allowlist (auditable domain object).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "d3e4f5a6b7c8"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invite_allowlist",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("invited_by_athlete_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("athlete.id"), nullable=True),
        sa.Column("invited_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_athlete_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("athlete.id"), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_by_athlete_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("athlete.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("email", name="uq_invite_allowlist_email"),
    )
    op.create_index("ix_invite_allowlist_email", "invite_allowlist", ["email"])
    op.create_index("ix_invite_allowlist_is_active", "invite_allowlist", ["is_active"])

    op.create_table(
        "invite_audit_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("invite_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invite_allowlist.id"), nullable=False),
        sa.Column("actor_athlete_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("athlete.id"), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_email", sa.Text(), nullable=False),
        sa.Column("event_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_invite_audit_event_invite_id", "invite_audit_event", ["invite_id"])
    op.create_index("ix_invite_audit_event_actor_athlete_id", "invite_audit_event", ["actor_athlete_id"])
    op.create_index("ix_invite_audit_event_action", "invite_audit_event", ["action"])
    op.create_index("ix_invite_audit_event_target_email", "invite_audit_event", ["target_email"])


def downgrade() -> None:
    op.drop_index("ix_invite_audit_event_target_email", table_name="invite_audit_event")
    op.drop_index("ix_invite_audit_event_action", table_name="invite_audit_event")
    op.drop_index("ix_invite_audit_event_actor_athlete_id", table_name="invite_audit_event")
    op.drop_index("ix_invite_audit_event_invite_id", table_name="invite_audit_event")
    op.drop_table("invite_audit_event")

    op.drop_index("ix_invite_allowlist_is_active", table_name="invite_allowlist")
    op.drop_index("ix_invite_allowlist_email", table_name="invite_allowlist")
    op.drop_table("invite_allowlist")

