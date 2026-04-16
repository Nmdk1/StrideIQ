"""Add Strava-fallback columns to activity table

Revision ID: strava_fallback_001
Revises: n1_repair_001
Create Date: 2026-04-16

When a Garmin run's per-second detail webhook never arrives,
`tasks.cleanup_stale_garmin_pending_streams` fail-closes the row to
`stream_fetch_status='unavailable'` after 30 minutes.  The activity then
renders without a chart, map, splits, or run-shape analysis -- a broken
page even when the same workout exists in the athlete's Strava account.

This migration adds the audit columns the new fallback pipeline uses to
track its repair attempts on a per-activity basis.  See
docs/specs/garmin_strava_fallback_plan.md sections 5 + 7 for the full
design.

Idempotent: every column is added with `IF NOT EXISTS` so the migration
is a no-op anywhere the columns already exist (manual prod patches, dev
rebases).  No data backfill -- existing rows correctly read NULL as
"never attempted."
"""

from alembic import op


revision = "strava_fallback_001"
down_revision = "n1_repair_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE activity
            ADD COLUMN IF NOT EXISTS strava_fallback_status TEXT,
            ADD COLUMN IF NOT EXISTS strava_fallback_attempted_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS strava_fallback_strava_activity_id BIGINT,
            ADD COLUMN IF NOT EXISTS strava_fallback_error TEXT,
            ADD COLUMN IF NOT EXISTS strava_fallback_attempt_count INTEGER NOT NULL DEFAULT 0;
        """
    )

    # Partial index for the fallback worker's eligibility scan and for ops
    # queries.  Only indexes rows that are actually candidates for repair --
    # tiny on disk, fast lookups, doesn't bloat the main btree.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_activity_strava_fallback_eligible
            ON activity (start_time DESC)
            WHERE provider = 'garmin'
              AND stream_fetch_status = 'unavailable'
              AND (strava_fallback_status IS NULL OR strava_fallback_status = 'failed');
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_activity_strava_fallback_eligible;")
    op.execute(
        """
        ALTER TABLE activity
            DROP COLUMN IF EXISTS strava_fallback_attempt_count,
            DROP COLUMN IF EXISTS strava_fallback_error,
            DROP COLUMN IF EXISTS strava_fallback_strava_activity_id,
            DROP COLUMN IF EXISTS strava_fallback_attempted_at,
            DROP COLUMN IF EXISTS strava_fallback_status;
        """
    )
