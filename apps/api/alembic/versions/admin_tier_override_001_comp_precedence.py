"""admin_tier_override_001 — add manual comp override fields to athlete

Adds four columns to the `athlete` table that implement the precedence contract
between manual admin comp and Stripe-driven entitlement writes:

  admin_tier_override           TEXT     — tier name set by admin comp (non-null = locked)
  admin_tier_override_set_at    TIMESTAMPTZ — when the override was applied
  admin_tier_override_set_by    UUID     — FK → athlete.id of the admin who set it
  admin_tier_override_reason    TEXT     — optional audit note

When admin_tier_override is non-null, Stripe sync/webhook MUST NOT downgrade
subscription_tier.  Clear the override column to restore Stripe authority.

Revision ID: admin_tier_override_001
Revises:     auto_discovery_phase1_001
"""

from alembic import op
import sqlalchemy as sa

revision = "admin_tier_override_001"
down_revision = "auto_discovery_phase1_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("athlete", sa.Column("admin_tier_override", sa.Text(), nullable=True))
    op.add_column("athlete", sa.Column("admin_tier_override_set_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("athlete", sa.Column("admin_tier_override_set_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("athlete", sa.Column("admin_tier_override_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("athlete", "admin_tier_override_reason")
    op.drop_column("athlete", "admin_tier_override_set_by")
    op.drop_column("athlete", "admin_tier_override_set_at")
    op.drop_column("athlete", "admin_tier_override")
