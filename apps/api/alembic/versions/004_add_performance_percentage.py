"""add_performance_percentage

Revision ID: d4f5e6a7b8c9
Revises: c820b73b7010
Create Date: 2026-01-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4f5e6a7b8c9'
down_revision: Union[str, None] = 'c047bd6a61d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add performance_percentage column to activity table
    # This stores the age-graded performance percentage (WMA standard)
    op.add_column('activity', sa.Column('performance_percentage', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('activity', 'performance_percentage')

