"""Add chip_time_seconds and campaign_data to performance_event

Phase 1C: DI-3 (chip time support) + CD-2 (campaign data storage).

Revision ID: phase1c_001
Revises: fingerprint_1b_001
Create Date: 2026-03-04
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = 'phase1c_001'
down_revision = 'fingerprint_1b_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('performance_event',
                  sa.Column('chip_time_seconds', sa.Integer(), nullable=True))
    op.add_column('performance_event',
                  sa.Column('campaign_data', postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column('performance_event', 'campaign_data')
    op.drop_column('performance_event', 'chip_time_seconds')
