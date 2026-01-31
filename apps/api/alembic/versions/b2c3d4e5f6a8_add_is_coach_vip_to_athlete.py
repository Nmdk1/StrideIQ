"""add_is_coach_vip_to_athlete

Revision ID: b2c3d4e5f6a8
Revises: 9033f613c815
Create Date: 2026-01-31 14:15:00.000000

Phase 11: Coach VIP flag for premium model access (gpt-5.2).
See ADR-060 for tiering rationale.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a8'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_coach_vip column with default False
    op.add_column(
        'athlete',
        sa.Column('is_coach_vip', sa.Boolean(), nullable=False, server_default='false')
    )


def downgrade() -> None:
    op.drop_column('athlete', 'is_coach_vip')
