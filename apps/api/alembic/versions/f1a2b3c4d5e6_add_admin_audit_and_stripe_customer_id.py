"""add_admin_audit_and_stripe_customer_id

Revision ID: f1a2b3c4d5e6
Revises: e8f9a0b1c2d3
Create Date: 2026-01-24

Adds:
- admin_audit_event (append-only admin audit log)
- athlete.stripe_customer_id (nullable; Phase 6-ready)
- athlete.admin_permissions (JSONB; Phase 4 RBAC seam)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e8f9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Athlete: Phase 6-ready Stripe linkage (nullable)
    op.add_column("athlete", sa.Column("stripe_customer_id", sa.Text(), nullable=True))

    # Athlete: Phase 4 RBAC seam (JSONB permissions list)
    op.add_column(
        "athlete",
        sa.Column(
            "admin_permissions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )

    op.create_table(
        "admin_audit_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actor_athlete_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("athlete.id"), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_athlete_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("athlete.id"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_admin_audit_event_created_at", "admin_audit_event", ["created_at"], unique=False)
    op.create_index("ix_admin_audit_event_actor_athlete_id", "admin_audit_event", ["actor_athlete_id"], unique=False)
    op.create_index("ix_admin_audit_event_target_athlete_id", "admin_audit_event", ["target_athlete_id"], unique=False)
    op.create_index("ix_admin_audit_event_action", "admin_audit_event", ["action"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_admin_audit_event_action", table_name="admin_audit_event")
    op.drop_index("ix_admin_audit_event_target_athlete_id", table_name="admin_audit_event")
    op.drop_index("ix_admin_audit_event_actor_athlete_id", table_name="admin_audit_event")
    op.drop_index("ix_admin_audit_event_created_at", table_name="admin_audit_event")
    op.drop_table("admin_audit_event")

    op.drop_column("athlete", "admin_permissions")
    op.drop_column("athlete", "stripe_customer_id")

