"""garmin_001: Replace credential-based Garmin fields with OAuth token fields

Revision ID: garmin_001
Revises: consent_001
Create Date: 2026-02-22

Phase 2 / D1.1 — removes the unofficial-library credential fields
(garmin_username, garmin_password_encrypted) and adds the OAuth token
fields required by the official Garmin Connect API.

See docs/PHASE2_GARMIN_INTEGRATION_AC.md §D1.1
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "garmin_001"
down_revision: Union[str, None] = "consent_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove credential fields from the unofficial library (compliance fix)
    op.drop_column("athlete", "garmin_username")
    op.drop_column("athlete", "garmin_password_encrypted")

    # Add OAuth token fields (same encryption-at-rest pattern as Strava)
    op.add_column(
        "athlete",
        sa.Column("garmin_oauth_access_token", sa.Text(), nullable=True),
    )
    op.add_column(
        "athlete",
        sa.Column("garmin_oauth_refresh_token", sa.Text(), nullable=True),
    )
    op.add_column(
        "athlete",
        sa.Column(
            "garmin_oauth_token_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    # Garmin's stable user identifier from the OAuth token response
    op.add_column(
        "athlete",
        sa.Column("garmin_user_id", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("athlete", "garmin_user_id")
    op.drop_column("athlete", "garmin_oauth_token_expires_at")
    op.drop_column("athlete", "garmin_oauth_refresh_token")
    op.drop_column("athlete", "garmin_oauth_access_token")

    # Restore credential fields so previous code can still run
    op.add_column(
        "athlete",
        sa.Column("garmin_password_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "athlete",
        sa.Column("garmin_username", sa.Text(), nullable=True),
    )
