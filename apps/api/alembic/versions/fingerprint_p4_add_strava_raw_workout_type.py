"""Add strava_workout_type_raw to Activity

Racing Fingerprint Pre-Work P4: preserve original Strava workout type.
Backfill existing race-tagged Strava activities with value 3.

Revision ID: fingerprint_p4_001
Revises: fingerprint_p1_001
Create Date: 2026-03-04
"""
import sqlalchemy as sa
from alembic import op

revision = 'fingerprint_p4_001'
down_revision = 'fingerprint_p1_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('activity', sa.Column(
        'strava_workout_type_raw', sa.Integer(), nullable=True,
    ))

    op.execute("""
        UPDATE activity
        SET strava_workout_type_raw = 3
        WHERE provider = 'strava'
          AND is_race_candidate = true
          AND strava_workout_type_raw IS NULL
    """)


def downgrade() -> None:
    op.drop_column('activity', 'strava_workout_type_raw')
