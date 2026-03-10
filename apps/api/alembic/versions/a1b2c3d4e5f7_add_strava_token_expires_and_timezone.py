"""add strava_token_expires_at and timezone to athlete

Revision ID: a1b2c3d4e5f7
Revises: 9033f613c815, e5f6a7b8c9d0
Create Date: 2026-02-08 12:00:00.000000

This migration also merges two previously divergent Alembic heads.
Idempotent: skips columns that already exist (safe for re-runs).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f7'
down_revision: tuple = ('9033f613c815', 'e5f6a7b8c9d0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    """Check if a column already exists in the given table."""
    bind = op.get_bind()
    insp = inspect(bind)
    columns = [c["name"] for c in insp.get_columns(table)]
    return column in columns


def upgrade() -> None:
    if not _column_exists("athlete", "strava_token_expires_at"):
        op.add_column('athlete', sa.Column('strava_token_expires_at', sa.DateTime(timezone=True), nullable=True))
    if not _column_exists("athlete", "timezone"):
        op.add_column('athlete', sa.Column('timezone', sa.Text(), nullable=True))


def downgrade() -> None:
    if _column_exists("athlete", "timezone"):
        op.drop_column('athlete', 'timezone')
    if _column_exists("athlete", "strava_token_expires_at"):
        op.drop_column('athlete', 'strava_token_expires_at')
