"""add_feature_flag_gating_columns

Revision ID: 3a0f8c0e9c21
Revises: c1a6e2b7d9f0
Create Date: 2026-01-19

Fixes plan generation failures by aligning the existing `feature_flag` table
with the current `models.FeatureFlag` schema.

This migration is intentionally additive and safe for existing data.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "3a0f8c0e9c21"
down_revision = "c1a6e2b7d9f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fresh-install safety: feature_flag may not exist (older chains relied on create_all fallback).
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS feature_flag (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            key TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            description TEXT,
            enabled BOOLEAN NOT NULL DEFAULT false,
            requires_subscription BOOLEAN NOT NULL DEFAULT false,
            requires_tier TEXT,
            requires_payment NUMERIC(10,2),
            rollout_percentage INTEGER NOT NULL DEFAULT 100,
            allowed_athlete_ids JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    bind = op.get_bind()
    inspector = inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("feature_flag")}

    # Add gating columns (idempotent)
    if "requires_subscription" not in existing_cols:
        op.add_column(
            "feature_flag",
            sa.Column("requires_subscription", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
    if "requires_tier" not in existing_cols:
        op.add_column("feature_flag", sa.Column("requires_tier", sa.Text(), nullable=True))
    if "requires_payment" not in existing_cols:
        op.add_column("feature_flag", sa.Column("requires_payment", sa.Numeric(10, 2), nullable=True))
    if "allowed_athlete_ids" not in existing_cols:
        op.add_column("feature_flag", sa.Column("allowed_athlete_ids", JSONB(), nullable=True))

    # Align rollout default with the FeatureFlagService expectation (100% default rollout).
    try:
        op.alter_column("feature_flag", "rollout_percentage", server_default=sa.text("100"))
    except Exception:
        # If column doesn't exist yet in this chain, leave as-is.
        pass


def downgrade() -> None:
    # Revert rollout default (older schema used 0; keep downgrade simple)
    op.alter_column("feature_flag", "rollout_percentage", server_default=sa.text("0"))

    op.drop_column("feature_flag", "allowed_athlete_ids")
    op.drop_column("feature_flag", "requires_payment")
    op.drop_column("feature_flag", "requires_tier")
    op.drop_column("feature_flag", "requires_subscription")

