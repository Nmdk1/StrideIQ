"""add_subscriptions_and_stripe_events

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-01-24

Phase 6: Stripe MVP
- subscriptions (stripe subscription mirror for entitlements)
- stripe_events (processed event ids for idempotency)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("athlete.id"), nullable=False),
        sa.Column("stripe_customer_id", sa.Text(), nullable=True),
        sa.Column("stripe_subscription_id", sa.Text(), nullable=True),
        sa.Column("stripe_price_id", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("athlete_id", name="uq_subscriptions_athlete_id"),
    )
    op.create_index("ix_subscriptions_athlete_id", "subscriptions", ["athlete_id"], unique=True)
    op.create_index("ix_subscriptions_stripe_customer_id", "subscriptions", ["stripe_customer_id"], unique=False)
    op.create_index("ix_subscriptions_stripe_subscription_id", "subscriptions", ["stripe_subscription_id"], unique=False)
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"], unique=False)

    op.create_table(
        "stripe_events",
        sa.Column("event_id", sa.Text(), primary_key=True, nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("stripe_created", sa.Integer(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_stripe_events_event_type", "stripe_events", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_stripe_events_event_type", table_name="stripe_events")
    op.drop_table("stripe_events")

    op.drop_index("ix_subscriptions_status", table_name="subscriptions")
    op.drop_index("ix_subscriptions_stripe_subscription_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_stripe_customer_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_athlete_id", table_name="subscriptions")
    op.drop_table("subscriptions")

