"""Add calendar system tables

Revision ID: calendar_system_001
Revises: 57eb2e1473e1
Create Date: 2026-01-10

Creates tables for the calendar system:
- calendar_note: Flexible notes tied to calendar dates
- coach_chat: Coach conversation sessions
- calendar_insight: Auto-generated insights for calendar days
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = 'calendar_system_001'
down_revision = '57eb2e1473e1'
branch_labels = None
depends_on = None


def upgrade():
    # Create calendar_note table
    op.create_table(
        'calendar_note',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('athlete_id', UUID(as_uuid=True), sa.ForeignKey('athlete.id'), nullable=False),
        sa.Column('note_date', sa.Date(), nullable=False),
        sa.Column('note_type', sa.Text(), nullable=False),
        sa.Column('structured_data', JSONB(), nullable=True),
        sa.Column('text_content', sa.Text(), nullable=True),
        sa.Column('voice_memo_url', sa.Text(), nullable=True),
        sa.Column('voice_memo_transcript', sa.Text(), nullable=True),
        sa.Column('activity_id', UUID(as_uuid=True), sa.ForeignKey('activity.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    op.create_index('ix_calendar_note_athlete_id', 'calendar_note', ['athlete_id'])
    op.create_index('ix_calendar_note_date', 'calendar_note', ['note_date'])
    op.create_index('ix_calendar_note_athlete_date', 'calendar_note', ['athlete_id', 'note_date'])
    
    # Create coach_chat table
    op.create_table(
        'coach_chat',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('athlete_id', UUID(as_uuid=True), sa.ForeignKey('athlete.id'), nullable=False),
        sa.Column('context_type', sa.Text(), nullable=False, server_default='open'),
        sa.Column('context_date', sa.Date(), nullable=True),
        sa.Column('context_week', sa.Integer(), nullable=True),
        sa.Column('context_plan_id', UUID(as_uuid=True), sa.ForeignKey('training_plan.id'), nullable=True),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('messages', JSONB(), nullable=False, server_default='[]'),
        sa.Column('context_snapshot', JSONB(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    op.create_index('ix_coach_chat_athlete_id', 'coach_chat', ['athlete_id'])
    op.create_index('ix_coach_chat_context_type', 'coach_chat', ['context_type'])
    op.create_index('ix_coach_chat_created_at', 'coach_chat', ['created_at'])
    
    # Create calendar_insight table
    op.create_table(
        'calendar_insight',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('athlete_id', UUID(as_uuid=True), sa.ForeignKey('athlete.id'), nullable=False),
        sa.Column('insight_date', sa.Date(), nullable=False),
        sa.Column('insight_type', sa.Text(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='50'),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('activity_id', UUID(as_uuid=True), sa.ForeignKey('activity.id'), nullable=True),
        sa.Column('generation_data', JSONB(), nullable=True),
        sa.Column('is_dismissed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    op.create_index('ix_calendar_insight_athlete_id', 'calendar_insight', ['athlete_id'])
    op.create_index('ix_calendar_insight_date', 'calendar_insight', ['insight_date'])
    op.create_index('ix_calendar_insight_athlete_date', 'calendar_insight', ['athlete_id', 'insight_date'])
    op.create_index('ix_calendar_insight_type', 'calendar_insight', ['insight_type'])


def downgrade():
    op.drop_table('calendar_insight')
    op.drop_table('coach_chat')
    op.drop_table('calendar_note')
