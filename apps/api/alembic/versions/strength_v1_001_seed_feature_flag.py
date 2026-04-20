"""Seed strength.v1 feature flag (sandbox bootstrap)

Revision ID: strength_v1_001
Revises: fit_run_001
Create Date: 2026-04-19

Phase A bootstrap for the Strength v1 sandbox build (see
docs/specs/STRENGTH_V1_SCOPE.md).

Seeds a single feature flag, ``strength.v1``, disabled by default with
a 0% rollout and no allowed athletes. Every Strength v1 surface (nav
entry, manual logging routes, StrengthDetailV2, new engine inputs,
Personal Operating Manual strength domain, Garmin reconciliation nudge)
gates on this flag.

Until the flag is flipped — first for the founder via
``allowed_athlete_ids``, then to ``enabled=true`` at integration day —
the branch can ship arbitrary Strength v1 work to ``main`` without any
athlete seeing or being affected by it.

Idempotent. Safe to re-run. Down-migration removes only the seeded row.
"""

from alembic import op


revision = "strength_v1_001"
down_revision = "fit_run_001"
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
        VALUES (
            gen_random_uuid(),
            'strength.v1',
            'Strength v1 (sandbox)',
            'Sandbox flag for the Strength v1 build (manual logging, routines, goals, Garmin reconciliation, strength domain in the Personal Operating Manual). Disabled until the founder calls the branch ready. See docs/specs/STRENGTH_V1_SCOPE.md.',
            false,
            false,
            NULL,
            0,
            '[]'::jsonb
        )
        ON CONFLICT (key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM feature_flag WHERE key = 'strength.v1';")
