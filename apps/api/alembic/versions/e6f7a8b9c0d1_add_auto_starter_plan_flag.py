"""add auto starter plan flag

Revision ID: e6f7a8b9c0d1
Revises: d5f6a7b8c9d0
Create Date: 2026-01-24
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "e6f7a8b9c0d1"
down_revision = "d5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fresh-install safety: ensure feature_flag exists before insert.
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

    # Starter plan auto-provisioning for new athletes (Calendar trust fix).
    op.execute(
        """
        INSERT INTO feature_flag (key, name, description, enabled, requires_subscription, requires_tier, requires_payment, rollout_percentage, created_at, updated_at)
        SELECT
          'onboarding.auto_starter_plan_v1',
          'Auto-create starter plan after onboarding',
          'When enabled, if an onboarding-complete athlete has no active plan, Calendar auto-provisions a deterministic starter plan from goals intake.',
          TRUE,
          FALSE,
          NULL,
          NULL,
          100,
          now(),
          now()
        WHERE NOT EXISTS (
          SELECT 1 FROM feature_flag WHERE key = 'onboarding.auto_starter_plan_v1'
        );
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM feature_flag WHERE key = 'onboarding.auto_starter_plan_v1';")

