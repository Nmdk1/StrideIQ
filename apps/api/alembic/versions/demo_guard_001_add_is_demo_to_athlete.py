"""Add is_demo flag to athlete

Revision ID: demo_guard_001
Revises: sleep_quality_001
Create Date: 2026-02-15

Prevents shared demo accounts from linking real Strava/Garmin
accounts and leaking personal data to other demo users.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'demo_guard_001'
down_revision: Union[str, None] = 'sleep_quality_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'athlete',
        sa.Column('is_demo', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )


def downgrade() -> None:
    op.drop_column('athlete', 'is_demo')
