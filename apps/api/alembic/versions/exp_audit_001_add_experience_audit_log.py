"""add experience_audit_log table

Revision ID: exp_audit_001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = 'exp_audit_001'
down_revision = 'activity_identity_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'experience_audit_log',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('athlete_id', UUID(as_uuid=True), sa.ForeignKey('athlete.id'), nullable=False, index=True),
        sa.Column('run_date', sa.Date(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('tier', sa.Text(), nullable=False),
        sa.Column('passed', sa.Boolean(), nullable=False),
        sa.Column('total_assertions', sa.Integer(), nullable=False),
        sa.Column('passed_count', sa.Integer(), nullable=False),
        sa.Column('failed_count', sa.Integer(), nullable=False),
        sa.Column('skipped_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('results', JSONB(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.UniqueConstraint('athlete_id', 'run_date', 'tier', name='uq_audit_athlete_date_tier'),
    )


def downgrade() -> None:
    op.drop_table('experience_audit_log')
