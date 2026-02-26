"""Monetization tier migration and plan_purchase table.

Revision ID: monetization_001
Revises: sleep_quality_001
Create Date: 2026-02-26

Operations (forward):
1. Create monetization_migration_ledger — records which athletes were migrated
   from 'pro' → 'premium' so rollback is safe (touches only those rows).
2. Create plan_purchases — one-time race-plan unlock purchase records.
3. Populate ledger with all athletes currently at subscription_tier = 'pro'.
4. Migrate athlete.subscription_tier from 'pro' → 'premium' for those athletes.

Rollback (downgrade):
1. Restore original tier for ledger-tracked athletes only (safe: does not touch
   any 'premium' tier that was not part of this migration).
2. Delete ledger rows.
3. Drop plan_purchases table.
4. Drop monetization_migration_ledger table.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "monetization_001"
down_revision: Union[str, None] = "sleep_quality_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Migration ledger — tracks which athletes were touched by this run.
    #    Used exclusively for safe rollback; not a runtime entitlement table.
    # ------------------------------------------------------------------
    op.create_table(
        "monetization_migration_ledger",
        sa.Column("athlete_id", sa.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column("original_tier", sa.Text, nullable=False),
        sa.Column("migrated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ------------------------------------------------------------------
    # 2. Plan purchases — one-time race-plan unlock records.
    # ------------------------------------------------------------------
    op.create_table(
        "plan_purchases",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "athlete_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("athlete.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("plan_snapshot_id", sa.Text, nullable=False),
        sa.Column("stripe_session_id", sa.Text, nullable=True),
        sa.Column("stripe_payment_intent_id", sa.Text, nullable=True, unique=True),
        sa.Column("purchased_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount_cents", sa.Integer, nullable=True),
    )
    op.create_index(
        "ix_plan_purchases_athlete_id",
        "plan_purchases",
        ["athlete_id"],
    )
    op.create_index(
        "ix_plan_purchases_plan_snapshot_id",
        "plan_purchases",
        ["plan_snapshot_id"],
    )
    op.create_index(
        "ix_plan_purchases_payment_intent",
        "plan_purchases",
        ["stripe_payment_intent_id"],
        unique=True,
    )
    op.create_unique_constraint(
        "uq_plan_purchases_athlete_snapshot",
        "plan_purchases",
        ["athlete_id", "plan_snapshot_id"],
    )

    # ------------------------------------------------------------------
    # 3. Record athletes being migrated into the ledger (for safe rollback).
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO monetization_migration_ledger (athlete_id, original_tier)
        SELECT id, subscription_tier
        FROM athlete
        WHERE subscription_tier = 'pro'
        """
    )

    # ------------------------------------------------------------------
    # 4. Migrate 'pro' → 'premium' for those athletes.
    # ------------------------------------------------------------------
    op.execute(
        """
        UPDATE athlete
        SET subscription_tier = 'premium'
        WHERE subscription_tier = 'pro'
        """
    )


def downgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Restore original tier for ledger-tracked athletes only.
    #    This is deliberately scoped: any athlete who was already 'premium'
    #    before this migration is NOT reverted.
    # ------------------------------------------------------------------
    op.execute(
        """
        UPDATE athlete a
        SET subscription_tier = l.original_tier
        FROM monetization_migration_ledger l
        WHERE a.id = l.athlete_id
        """
    )

    # ------------------------------------------------------------------
    # 2. Clear ledger (migration reverted; ledger no longer valid).
    # ------------------------------------------------------------------
    op.execute("DELETE FROM monetization_migration_ledger")

    # ------------------------------------------------------------------
    # 3. Drop tables.
    # ------------------------------------------------------------------
    op.drop_table("plan_purchases")
    op.drop_table("monetization_migration_ledger")
