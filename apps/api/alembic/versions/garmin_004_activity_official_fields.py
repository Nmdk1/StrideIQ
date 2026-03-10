"""garmin_004: Add Activity columns from official ClientActivity schema

Revision ID: garmin_004
Revises: garmin_003
Create Date: 2026-02-22

Phase 2 / D3 prerequisite — adds the Activity columns present in the
official Garmin ClientActivity schema that were missing from garmin_002.

The garmin_002 migration was based on the pre-portal discovery document
which assumed PascalCase field names and included several fields not
present in the official JSON API (running dynamics, Training Effect, etc.).
The portal verification (Feb 22 2026) confirmed the actual schema.

New columns from the official ClientActivity response:
  garmin_activity_id    — Garmin's native int64 activity ID (different
                          from summaryId stored in external_activity_id)
  avg_pace_min_per_km   — averagePaceInMinutesPerKilometer
  max_pace_min_per_km   — maxPaceInMinutesPerKilometer
  steps                 — per-activity step count (not daily total)
  device_name           — deviceName (e.g., "forerunner935")
  start_lat             — startingLatitudeInDegree
  start_lng             — startingLongitudeInDegree

All nullable — existing Strava activities are unaffected.

See docs/PHASE2_GARMIN_INTEGRATION_AC.md §D3.1
See docs/garmin-portal/HEALTH_API.md for official ClientActivity schema
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "garmin_004"
down_revision: Union[str, None] = "garmin_003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Garmin's native int64 activity ID (links activity summary to activity details)
    op.add_column("activity", sa.Column("garmin_activity_id", sa.BigInteger(), nullable=True))

    # Pace columns (officially documented in ClientActivity)
    op.add_column("activity", sa.Column("avg_pace_min_per_km", sa.Float(), nullable=True))
    op.add_column("activity", sa.Column("max_pace_min_per_km", sa.Float(), nullable=True))

    # Activity-level step count (separate from GarminDay.steps which is the daily total)
    op.add_column("activity", sa.Column("steps", sa.Integer(), nullable=True))

    # Device and location
    op.add_column("activity", sa.Column("device_name", sa.Text(), nullable=True))
    op.add_column("activity", sa.Column("start_lat", sa.Float(), nullable=True))
    op.add_column("activity", sa.Column("start_lng", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("activity", "start_lng")
    op.drop_column("activity", "start_lat")
    op.drop_column("activity", "device_name")
    op.drop_column("activity", "steps")
    op.drop_column("activity", "max_pace_min_per_km")
    op.drop_column("activity", "avg_pace_min_per_km")
    op.drop_column("activity", "garmin_activity_id")
