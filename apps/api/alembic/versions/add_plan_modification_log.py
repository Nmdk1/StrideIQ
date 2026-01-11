"""Add plan modification log table

Revision ID: add_plan_mod_log
Revises: calendar_system_001
Create Date: 2026-01-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_plan_mod_log'
down_revision = 'calendar_system_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create plan_modification_log table
    op.create_table(
        'plan_modification_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('athlete_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workout_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('before_state', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('after_state', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('source', sa.Text(), server_default='web', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('ip_address', sa.Text(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['athlete_id'], ['athlete.id'], ),
        sa.ForeignKeyConstraint(['plan_id'], ['training_plan.id'], ),
        sa.ForeignKeyConstraint(['workout_id'], ['planned_workout.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_plan_modification_log_athlete_id', 'plan_modification_log', ['athlete_id'], unique=False)
    op.create_index('ix_plan_modification_log_plan_id', 'plan_modification_log', ['plan_id'], unique=False)
    op.create_index('ix_plan_modification_log_created_at', 'plan_modification_log', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_plan_modification_log_created_at', table_name='plan_modification_log')
    op.drop_index('ix_plan_modification_log_plan_id', table_name='plan_modification_log')
    op.drop_index('ix_plan_modification_log_athlete_id', table_name='plan_modification_log')
    op.drop_table('plan_modification_log')
