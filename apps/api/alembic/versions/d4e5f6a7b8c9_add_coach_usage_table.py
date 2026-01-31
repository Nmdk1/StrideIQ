"""Add coach_usage table for LLM cost tracking (ADR-061)

Revision ID: d4e5f6a7b8c9
Revises: b2c3d4e5f6a8
Create Date: 2026-01-31

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = 'b2c3d4e5f6a8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create coach_usage table for LLM token/cost tracking per athlete
    op.create_table(
        'coach_usage',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('athlete_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('requests_today', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('opus_requests_today', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tokens_today', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('opus_tokens_today', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('month', sa.String(7), nullable=False),
        sa.Column('tokens_this_month', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('opus_tokens_this_month', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cost_today_cents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cost_this_month_cents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['athlete_id'], ['athlete.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('athlete_id', 'date', name='uq_coach_usage_athlete_date'),
    )
    
    # Create indexes for efficient querying
    op.create_index('ix_coach_usage_athlete_id', 'coach_usage', ['athlete_id'])
    op.create_index('ix_coach_usage_month', 'coach_usage', ['month'])


def downgrade() -> None:
    op.drop_index('ix_coach_usage_month', table_name='coach_usage')
    op.drop_index('ix_coach_usage_athlete_id', table_name='coach_usage')
    op.drop_table('coach_usage')
