"""Seed Coach Runtime V2 feature flags.

Revision ID: coach_runtime_v2_001
Revises: country_aware_units_001
Create Date: 2026-04-26

Seeds the shadow and visible runtime gates disabled by default with a 0%
rollout and empty allowlists. The explicit rollout value is intentional:
the generic feature_flag table defaults rollout_percentage to 100 for older
surfaces, which is unsafe for runtime replacement flags.
"""

from alembic import op


revision = "coach_runtime_v2_001"
down_revision = "country_aware_units_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
    op.execute(
        """
        INSERT INTO feature_flag (
            id,
            key,
            name,
            description,
            enabled,
            requires_subscription,
            requires_tier,
            rollout_percentage,
            allowed_athlete_ids
        )
        VALUES
            (
                gen_random_uuid(),
                'coach.runtime_v2.shadow',
                'Coach Runtime V2 shadow',
                'Legacy audit flag for Coach Runtime V2 shadow. V2 is now the site-wide default coach runtime.',
                true,
                false,
                NULL,
                100,
                '[]'::jsonb
            ),
            (
                gen_random_uuid(),
                'coach.runtime_v2.visible',
                'Coach Runtime V2 visible',
                'Coach Runtime V2 visible is the site-wide production coach runtime.',
                true,
                false,
                NULL,
                100,
                '[]'::jsonb
            )
        ON CONFLICT (key) DO UPDATE SET
            enabled = true,
            rollout_percentage = 100,
            allowed_athlete_ids = '[]'::jsonb,
            updated_at = now();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM feature_flag
        WHERE key IN ('coach.runtime_v2.shadow', 'coach.runtime_v2.visible');
        """
    )
