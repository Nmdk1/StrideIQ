"""Add confounder control fields to correlation_finding

Revision ID: correlation_quality_001
Revises: progress_narrative_001
Create Date: 2026-03-03
"""
from alembic import op
import sqlalchemy as sa

revision = 'correlation_quality_001'
down_revision = 'progress_narrative_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('correlation_finding', sa.Column('partial_correlation_coefficient', sa.Float(), nullable=True))
    op.add_column('correlation_finding', sa.Column('confounder_variable', sa.Text(), nullable=True))
    op.add_column('correlation_finding', sa.Column('is_confounded', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('correlation_finding', sa.Column('direction_expected', sa.Text(), nullable=True))
    op.add_column('correlation_finding', sa.Column('direction_counterintuitive', sa.Boolean(), server_default=sa.text('false'), nullable=False))


def downgrade() -> None:
    op.drop_column('correlation_finding', 'direction_counterintuitive')
    op.drop_column('correlation_finding', 'direction_expected')
    op.drop_column('correlation_finding', 'is_confounded')
    op.drop_column('correlation_finding', 'confounder_variable')
    op.drop_column('correlation_finding', 'partial_correlation_coefficient')
