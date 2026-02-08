"""add strava_token_expires_at and timezone to athlete

Revision ID: a1b2c3d4e5f7
Revises: 9033f613c815, e5f6a7b8c9d0
Create Date: 2026-02-08 12:00:00.000000

This migration also merges two previously divergent Alembic heads.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f7'
down_revision: tuple = ('9033f613c815', 'e5f6a7b8c9d0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('athlete', sa.Column('strava_token_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('athlete', sa.Column('timezone', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('athlete', 'timezone')
    op.drop_column('athlete', 'strava_token_expires_at')
