"""add detailed metrics to activity

Revision ID: 003
Revises: 002
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to activity table (skip max_hr - already added in 001)
    # op.add_column('activity', sa.Column('max_hr', sa.Integer(), nullable=True))
    
    # Only add columns that don't exist yet
    conn = op.get_bind()
    
    # Check if columns exist before adding
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'activity' AND column_name IN ('total_elevation_gain', 'average_speed')"
    ))
    existing_columns = {row[0] for row in result}
    
    if 'total_elevation_gain' not in existing_columns:
        op.add_column('activity', sa.Column('total_elevation_gain', sa.Numeric(), nullable=True))
    if 'average_speed' not in existing_columns:
        op.add_column('activity', sa.Column('average_speed', sa.Numeric(), nullable=True))


def downgrade() -> None:
    op.drop_column('activity', 'average_speed')
    op.drop_column('activity', 'total_elevation_gain')
    op.drop_column('activity', 'max_hr')


