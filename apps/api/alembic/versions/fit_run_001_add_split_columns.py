"""Add FIT-derived per-lap columns + extras JSONB to activity_split

Revision ID: fit_run_001
Revises: meal_template_named_001
Create Date: 2026-04-19

Phase 1 of the Garmin-data-completeness work. Adds first-class columns to
ActivitySplit so the FIT lap messages can be stored per-lap and the
correlation engine can reach them. Long-tail metrics (W/kg, GCT balance,
per-lap kcal/temp) go into a sibling `extras` JSONB column.

The Activity model's running-dynamics / power columns already exist
(garmin_002_activity_new_fields). They were never populated; they will
be after this migration ships and the FIT parser is wired in.

Idempotent — safe to re-run.
"""

from alembic import op


revision = "fit_run_001"
down_revision = "meal_template_named_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # First-class columns (correlation-queryable).
    op.execute(
        """
        ALTER TABLE activity_split
            ADD COLUMN IF NOT EXISTS total_ascent_m DOUBLE PRECISION,
            ADD COLUMN IF NOT EXISTS total_descent_m DOUBLE PRECISION,
            ADD COLUMN IF NOT EXISTS avg_power_w INTEGER,
            ADD COLUMN IF NOT EXISTS max_power_w INTEGER,
            ADD COLUMN IF NOT EXISTS avg_stride_length_m DOUBLE PRECISION,
            ADD COLUMN IF NOT EXISTS avg_ground_contact_ms DOUBLE PRECISION,
            ADD COLUMN IF NOT EXISTS avg_vertical_oscillation_cm DOUBLE PRECISION,
            ADD COLUMN IF NOT EXISTS avg_vertical_ratio_pct DOUBLE PRECISION,
            ADD COLUMN IF NOT EXISTS extras JSONB;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE activity_split
            DROP COLUMN IF EXISTS extras,
            DROP COLUMN IF EXISTS avg_vertical_ratio_pct,
            DROP COLUMN IF EXISTS avg_vertical_oscillation_cm,
            DROP COLUMN IF EXISTS avg_ground_contact_ms,
            DROP COLUMN IF EXISTS avg_stride_length_m,
            DROP COLUMN IF EXISTS max_power_w,
            DROP COLUMN IF EXISTS avg_power_w,
            DROP COLUMN IF EXISTS total_descent_m,
            DROP COLUMN IF EXISTS total_ascent_m;
        """
    )
