"""Add sleep_quality_1_5 to daily_checkin

Revision ID: sleep_quality_001
Revises: rsi_cache_001
Create Date: 2026-02-15

Separates sleep quality (1-5 scale) from sleep duration (hours).
Previously, quality taps (Great/OK/Poor) were silently mapped to
fake hour values — this column stores the actual quality signal.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'sleep_quality_001'
down_revision: Union[str, None] = 'rsi_cache_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'daily_checkin',
        sa.Column('sleep_quality_1_5', sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('daily_checkin', 'sleep_quality_1_5')
