"""Add athlete_route table + route_id / route_geohash_set on activity

Revision ID: route_fp_001
Revises: strava_fallback_001
Create Date: 2026-04-17

Foundational table for Phase 2 of the comparison product family. Stores
athlete-scoped routes (groups of activities run on the same physical
course). Each activity that has a GPS stream gets a `route_geohash_set`
fingerprint (sorted unique geohash@7 cells, ~150m grid) and is attached
to an existing `athlete_route` if Jaccard similarity ≥ 0.6 with prior
runs of comparable distance, otherwise a new route is created.

Phase 3 will add an athlete-supplied `name` UX. This migration creates
the column nullable so it can be populated later without backfill.

Idempotent: column adds use IF NOT EXISTS; table create uses
IF NOT EXISTS.  No data backfill — that runs as a separate Celery task
(``tasks.backfill_route_fingerprints``) so the migration stays fast.
"""

from alembic import op


revision = "route_fp_001"
down_revision = "strava_fallback_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS athlete_route (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            athlete_id UUID NOT NULL REFERENCES athlete(id),
            name TEXT,
            centroid_lat DOUBLE PRECISION,
            centroid_lng DOUBLE PRECISION,
            distance_p50_m INTEGER,
            distance_min_m INTEGER,
            distance_max_m INTEGER,
            geohash_set JSONB NOT NULL DEFAULT '[]'::jsonb,
            run_count INTEGER NOT NULL DEFAULT 0,
            first_seen_at TIMESTAMPTZ,
            last_seen_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_athlete_route_athlete_id "
        "ON athlete_route (athlete_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_athlete_route_athlete_distance "
        "ON athlete_route (athlete_id, distance_p50_m);"
    )

    op.execute(
        """
        ALTER TABLE activity
            ADD COLUMN IF NOT EXISTS route_id UUID REFERENCES athlete_route(id),
            ADD COLUMN IF NOT EXISTS route_geohash_set JSONB;
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_activity_route_id "
        "ON activity (route_id);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_activity_route_id;")
    op.execute(
        "ALTER TABLE activity "
        "DROP COLUMN IF EXISTS route_id, "
        "DROP COLUMN IF EXISTS route_geohash_set;"
    )
    op.execute("DROP INDEX IF EXISTS ix_athlete_route_athlete_distance;")
    op.execute("DROP INDEX IF EXISTS ix_athlete_route_athlete_id;")
    op.execute("DROP TABLE IF EXISTS athlete_route;")
