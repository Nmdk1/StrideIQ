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
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "3a0f8c0e9c21"
down_revision = "c1a6e2b7d9f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add gating columns (additive)
    op.add_column(
        "feature_flag",
        sa.Column("requires_subscription", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("feature_flag", sa.Column("requires_tier", sa.Text(), nullable=True))
    op.add_column("feature_flag", sa.Column("requires_payment", sa.Numeric(10, 2), nullable=True))
    op.add_column("feature_flag", sa.Column("allowed_athlete_ids", JSONB(), nullable=True))

    # Align rollout default with the FeatureFlagService expectation (100% default rollout).
    op.alter_column("feature_flag", "rollout_percentage", server_default=sa.text("100"))


def downgrade() -> None:
    # Revert rollout default (older schema used 0; keep downgrade simple)
    op.alter_column("feature_flag", "rollout_percentage", server_default=sa.text("0"))

    op.drop_column("feature_flag", "allowed_athlete_ids")
    op.drop_column("feature_flag", "requires_payment")
    op.drop_column("feature_flag", "requires_tier")
    op.drop_column("feature_flag", "requires_subscription")

