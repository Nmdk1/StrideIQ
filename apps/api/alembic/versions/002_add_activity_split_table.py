"""add activity split table

Revision ID: 002
Revises: 001
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create activity_split table
    op.create_table(
        'activity_split',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('activity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('split_number', sa.Integer(), nullable=False),
        sa.Column('distance', sa.Numeric(), nullable=True),
        sa.Column('elapsed_time', sa.Integer(), nullable=True),
        sa.Column('moving_time', sa.Integer(), nullable=True),
        sa.Column('average_heartrate', sa.Integer(), nullable=True),
        sa.Column('max_heartrate', sa.Integer(), nullable=True),
        sa.Column('average_cadence', sa.Numeric(), nullable=True),
        sa.ForeignKeyConstraint(['activity_id'], ['activity.id'], ),
    )
    op.create_index('ix_activity_split_activity_id', 'activity_split', ['activity_id'])


def downgrade() -> None:
    op.drop_index('ix_activity_split_activity_id', table_name='activity_split')
    op.drop_table('activity_split')


