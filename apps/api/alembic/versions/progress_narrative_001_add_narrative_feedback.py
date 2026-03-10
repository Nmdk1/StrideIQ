"""Add NarrativeFeedback table for progress narrative page.

Revision ID: progress_narrative_001
Revises:
Create Date: 2026-03-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'progress_narrative_001'
down_revision = 'runtoon_002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'narrative_feedback',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('athlete_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('athlete.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column('feedback_type', sa.Text(), nullable=False),
        sa.Column('feedback_detail', sa.Text(), nullable=True),
    )
    op.create_index(
        'ix_narrative_feedback_athlete_created',
        'narrative_feedback',
        ['athlete_id', 'created_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_narrative_feedback_athlete_created', table_name='narrative_feedback')
    op.drop_table('narrative_feedback')
