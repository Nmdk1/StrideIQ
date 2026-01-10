"""add_national_performance_percentage

Revision ID: cfcf3fd63cf0
Revises: 860d504e676f
Create Date: 2026-01-04 16:23:33.065923

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cfcf3fd63cf0'
down_revision: Union[str, None] = '860d504e676f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add performance_percentage_national column to activity table
    op.add_column('activity', sa.Column('performance_percentage_national', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('activity', 'performance_percentage_national')



