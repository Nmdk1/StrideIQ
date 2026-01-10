"""initial schema with timescaledb extension

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable TimescaleDB extension
    op.execute('CREATE EXTENSION IF NOT EXISTS timescaledb;')
    
    # Create athlete table
    op.create_table(
        'athlete',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('email', sa.Text(), nullable=True),
        sa.Column('display_name', sa.Text(), nullable=True),
        sa.Column('birthdate', sa.Date(), nullable=True),
        sa.Column('sex', sa.Text(), nullable=True),
        sa.Column('subscription_tier', sa.Text(), server_default='free', nullable=False),
    )
    op.create_index('ix_athlete_email', 'athlete', ['email'], unique=True)
    
    # Create activity table
    op.create_table(
        'activity',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('athlete_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sport', sa.Text(), server_default='run', nullable=False),
        sa.Column('source', sa.Text(), server_default='manual', nullable=False),
        sa.Column('duration_s', sa.Integer(), nullable=True),
        sa.Column('distance_m', sa.Integer(), nullable=True),
        sa.Column('avg_hr', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['athlete_id'], ['athlete.id'], ),
    )
    op.create_index('ix_activity_athlete_id', 'activity', ['athlete_id'])
    
    # Create daily_checkin table
    op.create_table(
        'daily_checkin',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('athlete_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('sleep_h', sa.Numeric(), nullable=True),
        sa.Column('stress_1_5', sa.Integer(), nullable=True),
        sa.Column('soreness_1_5', sa.Integer(), nullable=True),
        sa.Column('rpe_1_10', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['athlete_id'], ['athlete.id'], ),
    )
    op.create_index('ix_daily_checkin_athlete_id', 'daily_checkin', ['athlete_id'])
    op.create_index('uq_athlete_date', 'daily_checkin', ['athlete_id', 'date'], unique=True)


def downgrade() -> None:
    op.drop_index('uq_athlete_date', table_name='daily_checkin')
    op.drop_index('ix_daily_checkin_athlete_id', table_name='daily_checkin')
    op.drop_table('daily_checkin')
    op.drop_index('ix_activity_athlete_id', table_name='activity')
    op.drop_table('activity')
    op.drop_index('ix_athlete_email', table_name='athlete')
    op.drop_table('athlete')
    op.execute('DROP EXTENSION IF EXISTS timescaledb;')




